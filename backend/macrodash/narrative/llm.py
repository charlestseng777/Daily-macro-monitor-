"""
Optional LLM restyling of the daily commentary.

Claude receives the facts computed by the backend and the deterministic draft,
and returns the market-regime paragraph and the five regional summaries in a
sell-side research register. The output is accepted only if every number it
contains appears in the facts it was given, and the word limits hold.
Otherwise the deterministic draft is kept. The LLM can make the prose read
better; it cannot add facts.
"""

from __future__ import annotations

import json
import logging
import re

from ..config import get_settings

log = logging.getLogger(__name__)

SYSTEM = """You are a senior cross-asset strategist writing the morning note for a global markets research \
team (house style: JPMorgan Global Markets Research, Goldman Sachs GIR, Morgan Stanley Cross-Asset Strategy).

Rules, all mandatory:
- Use ONLY the facts in the FACTS JSON. Do not add events, data releases, quotes, causes or numbers that are not there.
- Every number you write must appear in FACTS (the same value, rounded the same way or less precisely).
- When FACTS gives no cause, describe the price action and do not speculate about why.
- Short, declarative, objective. No hype, no hedging filler, no first person, no recommendations.
- regime_paragraph: at most 100 words. Each regional summary: at most 60 words.
- Basis points as "bp" (e.g. "+6bp"), percentages with "%"."""

SCHEMA = {
    "type": "object",
    "properties": {
        "regime_paragraph": {"type": "string"},
        "regions": {
            "type": "object",
            "properties": {k: {"type": "string"} for k in ("US", "UK", "EU", "JP", "CN")},
            "required": ["US", "UK", "EU", "JP", "CN"],
            "additionalProperties": False,
        },
    },
    "required": ["regime_paragraph", "regions"],
    "additionalProperties": False,
}

_NUM = re.compile(r"(?<![\w.])[-+−]?\d+(?:\.\d+)?(?![\d])")
# Tokens like 2Y, 10s30s, 5y5y, S&P 500, Stoxx 50, FTSE 100, CSI 300 are names, not data.
_NAME_TOKENS = re.compile(r"\b\d+(?:[YyMmsS]\d*[sYy]?)\b|\b\d+s\d+s\b|\b\d+y\d+y\b|S&P 500|Stoxx 50|FTSE 100|CSI 300|Nikkei 225")


def _collect_numbers(obj, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(round(abs(float(obj)), 4))
    elif isinstance(obj, str):
        for m in _NUM.findall(obj.replace("−", "-")):
            out.add(round(abs(float(m)), 4))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numbers(v, out)


def _allowed(value: float, known: set[float]) -> bool:
    v = abs(value)
    for k in known:
        # Same number at the same or coarser precision.
        if abs(v - k) < 1e-9 or abs(v - round(k)) < 1e-9 or abs(v - round(k, 1)) < 1e-9 or abs(v - round(k, 2)) < 1e-9:
            return True
        # Fractions reported as percentages (e.g. share_be 0.62 -> 62%).
        if abs(v - round(k * 100)) < 1e-9 and k <= 1:
            return True
    return False


def ungrounded_numbers(text: str, facts: dict) -> list[str]:
    known: set[float] = set()
    _collect_numbers(facts, known)
    stripped = _NAME_TOKENS.sub(" ", text)
    bad = []
    for m in _NUM.findall(stripped.replace("−", "-")):
        if not _allowed(float(m), known):
            bad.append(m)
    return bad


def validate(result: dict, facts: dict) -> list[str]:
    problems = []
    if len(result.get("regime_paragraph", "").split()) > 100:
        problems.append("regime paragraph over 100 words")
    for k, v in result.get("regions", {}).items():
        if len(v.split()) > 60:
            problems.append(f"{k} summary over 60 words")
    for k, text in [("regime", result.get("regime_paragraph", ""))] + list(result.get("regions", {}).items()):
        bad = ungrounded_numbers(text, facts)
        if bad:
            problems.append(f"{k}: numbers not in facts: {bad[:5]}")
    return problems


def restyle(facts: dict, draft: dict) -> tuple[dict | None, dict]:
    """Returns (accepted result or None, status dict for the payload)."""
    s = get_settings()
    if not s.llm_enabled or not s.anthropic_api_key:
        return None, {"used": False, "reason": "no ANTHROPIC_API_KEY" if s.llm_enabled else "disabled"}
    try:
        import anthropic
    except ImportError:
        return None, {"used": False, "reason": "anthropic package not installed"}

    client = anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=3, timeout=120.0)
    prompt = ("FACTS:\n" + json.dumps(facts, separators=(",", ":"), default=str) +
              "\n\nDETERMINISTIC DRAFT (rewrite in house style; keep every claim grounded in FACTS):\n" +
              json.dumps(draft, ensure_ascii=False))
    try:
        # Server-side fallback: if the model declines, the API retries on a
        # substitute model chosen by refusal category.
        response = client.beta.messages.create(
            model=s.anthropic_model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as exc:
        log.warning("LLM rate limited: %s", exc)
        return None, {"used": False, "reason": "rate limited"}
    except anthropic.APIStatusError as exc:
        log.warning("LLM API error %s: %s", exc.status_code, exc)
        return None, {"used": False, "reason": f"API error {exc.status_code}"}
    except anthropic.APIConnectionError as exc:
        log.warning("LLM unreachable: %s", exc)
        return None, {"used": False, "reason": "connection error"}

    if response.stop_reason == "refusal":
        return None, {"used": False, "reason": "model declined"}
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None, {"used": False, "reason": "invalid JSON"}
    problems = validate(result, facts)
    if problems:
        log.warning("LLM commentary rejected: %s", "; ".join(problems))
        return None, {"used": False, "reason": "failed grounding check", "problems": problems[:5]}
    return result, {"used": True, "model": s.anthropic_model}

"""
Deterministic commentary. Every sentence restates numbers computed by the
analytics layer; nothing here is inferred beyond the rules written down.
This is the always-available layer; the LLM layer (llm.py) may restyle it,
under a check that it introduces no numbers of its own.
"""

from __future__ import annotations

from . import fmt

REGION_TITLES = {"US": "United States", "UK": "United Kingdom", "EU": "Europe", "JP": "Japan", "CN": "China"}


class Ctx:
    """Read-only view over the computed sections with safe lookups."""

    def __init__(self, stats: dict, curves: list[dict], spreads: list[dict], policy: list[dict],
                 attribution: list[dict], regime: dict, movers: dict):
        self.stats = stats
        self.curves = {c["id"]: c for c in curves}
        self.spreads = {s["id"]: s for s in spreads}
        self.policy = {p["id"]: p for p in policy}
        self.attribution = {(a["region"], a["horizon"]): a for a in attribution}
        self.regime = regime
        self.movers = movers

    def d1(self, iid: str) -> float | None:
        st = self.stats.get(iid) or self.curves.get(iid) or self.spreads.get(iid)
        return None if not st else st.get("d1")

    def st(self, iid: str) -> dict | None:
        return self.stats.get(iid)

    def has(self, *ids: str) -> bool:
        return all(self.d1(i) is not None for i in ids)


# --------------------------------------------------------------- pieces --

def _yield_phrase(ctx: Ctx, iid: str, label: str) -> str | None:
    st = ctx.st(iid)
    if not st or st.get("d1") is None:
        return None
    return f"{label} {fmt.bp(st['d1'])} to {fmt.level(st['last'])}"


def _curve_phrase(ctx: Ctx, cid: str) -> str | None:
    c = ctx.curves.get(cid)
    if not c or c.get("d1") is None:
        return None
    if c["shape_d1"] in ("unchanged",):
        return None
    if c["shape_d1"].startswith("parallel"):
        return f"a {c['shape_d1_label'].lower()} with {c['label']} {fmt.bp(c['d1'])}"
    return f"a {c['shape_d1_label'].lower()} in {c['label']} ({fmt.bp(c['d1'])} to {c['last']:.0f}bp)"


def _policy_phrase(ctx: Ctx, bank: str) -> str | None:
    p = ctx.policy.get(bank)
    if not p or not p.get("summary"):
        return None
    chg = p.get("priced_12m_chg_bp")
    s = p["summary"]
    total = s["priced_12m_bp"]
    what = "easing" if total < 0 else "tightening"
    proxy = " on the bill-curve proxy" if p.get("quality") == "low" else ""
    if chg is not None and abs(chg) >= 2:
        direction = "added" if (chg < 0) == (total < 0) else "removed"
        return f"markets {direction} {abs(chg):.0f}bp of {p['short']} {what} over 12 months{proxy} (now {fmt.bp(total)})"
    return f"{p['short']} pricing was steady at {fmt.bp(total)} over 12 months{proxy}"


def _asset_phrase(ctx: Ctx, iid: str, label: str) -> str | None:
    st = ctx.st(iid)
    if not st or st.get("d1") is None:
        return None
    if st["unit"] == "bp":
        return f"{label} {fmt.verb(st['d1'], 'widened', 'tightened', 'was unchanged')} {fmt.bp(st['d1'], signed=False)}"
    if abs(st["d1"]) < 0.05:
        return f"{label} was flat"
    return f"{label} {'rose' if st['d1'] > 0 else 'fell'} {fmt.pct(st['d1'], signed=False)}"


def _join(parts: list[str | None]) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


# --------------------------------------------------------------- regime --

def regime_paragraph(ctx: Ctx) -> str:
    r = ctx.regime
    sentences = []
    lead = _cap(r.get("summary", ""))
    us = _join([_yield_phrase(ctx, "US2Y", "2Y"), _yield_phrase(ctx, "US10Y", "10Y")])
    if lead and us:
        sentences.append(f"{lead}: US Treasury yields {us}")
    elif lead:
        sentences.append(lead)
    elif us:
        sentences.append(f"US Treasury yields {us}")
    curve = _curve_phrase(ctx, "US_2s10s")
    if curve:
        sentences.append(f"The US curve saw {curve}")
    cross = _join([_asset_phrase(ctx, "DXY", "the dollar"), _asset_phrase(ctx, "GOLD", "gold"),
                   _asset_phrase(ctx, "SPX", "the S&P 500"), _asset_phrase(ctx, "BRENT", "Brent")])
    if cross:
        sentences.append(_cap(cross))
    credit = _asset_phrase(ctx, "US_HY_OAS", "US high-yield spreads")
    if credit:
        sentences.append(_cap(credit))
    top = (ctx.movers.get("top") or [None])[0]
    if top and abs(top["z"]) >= 1.5:
        unit_move = fmt.bp(top["d1"]) if top["unit"] == "bp" else fmt.pct(top["d1"])
        sentences.append(f"The standout move was {top['name']} ({unit_move}, {abs(top['z']):.1f}x its 20-day volatility)")
    text = ". ".join(s.rstrip(".") for s in sentences) + "."
    return fmt.word_limit(text, 100)


# --------------------------------------------------------------- regions --

def _rates_sentence(ctx: Ctx, market: str, front: str, back: str, curve_id: str) -> str | None:
    f, b = ctx.d1(front), ctx.d1(back)
    if f is None or b is None:
        return None
    avg = (f + b) / 2
    action = "sold off" if avg > 0.5 else "rallied" if avg < -0.5 else "were little changed"
    leader = ""
    if abs(f - b) >= 1.5 and abs(avg) > 0.5:
        leader = " with the front end leading" if abs(f) > abs(b) else " with the long end leading"
    curve = ctx.curves.get(curve_id)
    tail = ""
    if curve and curve.get("shape_d1") not in (None, "unchanged") and not curve["shape_d1"].startswith("parallel"):
        tail = f": a {curve['shape_d1_label'].lower()} ({curve['label']} {fmt.bp(curve['d1'])})"
    st_f, st_b = ctx.st(front), ctx.st(back)
    return (f"{market} {action}{leader}, 2Y {fmt.bp(f)} to {fmt.level(st_f['last'])} and "
            f"10Y {fmt.bp(b)} to {fmt.level(st_b['last'])}{tail}.")


def regional_summaries(ctx: Ctx) -> dict[str, str]:
    out: dict[str, str] = {}

    us = [_rates_sentence(ctx, "Treasuries", "US2Y", "US10Y", "US_2s10s")]
    pol = _policy_phrase(ctx, "FED")
    if pol:
        us.append(_cap(pol) + ".")
    tail = _join([_asset_phrase(ctx, "DXY", "the dollar"), _asset_phrase(ctx, "SPX", "the S&P 500")])
    if tail:
        us.append(_cap(tail) + ".")
    out["US"] = fmt.word_limit(" ".join(s for s in us if s), 60)

    uk = [_rates_sentence(ctx, "Gilts", "UK2Y", "UK10Y", "UK_2s10s")]
    if ctx.has("UK10Y", "US10Y"):
        rel = ctx.d1("UK10Y") - ctx.d1("US10Y")
        if abs(rel) >= 2:
            uk.append(f"Gilts {'under' if rel > 0 else 'out'}performed Treasuries by {abs(rel):.0f}bp at 10Y.")
    pol = _policy_phrase(ctx, "BOE")
    if pol:
        uk.append(_cap(pol) + ".")
    tail = _join([_asset_phrase(ctx, "GBPUSD", "sterling"), _asset_phrase(ctx, "FTSE", "the FTSE 100")])
    if tail:
        uk.append(_cap(tail) + ".")
    out["UK"] = fmt.word_limit(" ".join(s for s in uk if s), 60)

    eu = [_rates_sentence(ctx, "Bunds", "DE2Y", "DE10Y", "DE_2s10s")]
    btp = ctx.spreads.get("IT10_DE10")
    if btp and btp.get("d1") is not None:
        eu.append(f"BTP-Bund {fmt.verb(btp['d1'], 'widened', 'tightened', 'was steady')} "
                  f"{fmt.bp(btp['d1'], signed=False)} to {btp['last']:.0f}bp.")
    pol = _policy_phrase(ctx, "ECB")
    if pol:
        eu.append(_cap(pol) + ".")
    tail = _join([_asset_phrase(ctx, "EURUSD", "the euro"), _asset_phrase(ctx, "SX5E", "the Euro Stoxx 50")])
    if tail:
        eu.append(_cap(tail) + ".")
    out["EU"] = fmt.word_limit(" ".join(s for s in eu if s), 60)

    jp = []
    if ctx.has("JP10Y"):
        st = ctx.st("JP10Y")
        moved = fmt.verb(st["d1"])
        how = (f"{moved} at {fmt.level(st['last'], 3)}" if abs(st["d1"]) < 0.5
               else f"{moved} {fmt.bp(st['d1'], signed=False)} to {fmt.level(st['last'], 3)}")
        jp.append(f"JGB 10Y yields {how}"
                  + (f", with 30Y {fmt.bp(ctx.d1('JP30Y'))}." if ctx.has("JP30Y") else "."))
    if ctx.has("USDJPY"):
        d = ctx.d1("USDJPY")
        jp.append(f"The yen {'weakened' if d > 0 else 'strengthened'} as USD/JPY moved {fmt.pct(d)} to {ctx.st('USDJPY')['last']:.2f}.")
    pol = _policy_phrase(ctx, "BOJ")
    if pol:
        jp.append(_cap(pol) + ".")
    eq = _asset_phrase(ctx, "NKY", "the Nikkei")
    if eq:
        jp.append(_cap(eq) + ".")
    out["JP"] = fmt.word_limit(" ".join(jp), 60) or "No Japanese market data available."

    cn = []
    if ctx.has("CN10Y"):
        st = ctx.st("CN10Y")
        moved = fmt.verb(st["d1"])
        cn.append(f"CGB 10Y yields {moved} at {fmt.level(st['last'])}." if abs(st["d1"]) < 0.5
                  else f"CGB 10Y yields {moved} {fmt.bp(st['d1'], signed=False)} to {fmt.level(st['last'])}.")
    if ctx.has("USDCNY"):
        d = ctx.d1("USDCNY")
        cn.append(f"The renminbi {'weakened' if d > 0 else 'firmed'} with USD/CNY {fmt.pct(d, places=2)} at {ctx.st('USDCNY')['last']:.4f}.")
    tail = _join([_asset_phrase(ctx, "CSI300", "the CSI 300"), _asset_phrase(ctx, "COPPER", "copper")])
    if tail:
        cn.append(_cap(tail) + ".")
    out["CN"] = fmt.word_limit(" ".join(cn), 60) or "No Chinese market data available."
    return out

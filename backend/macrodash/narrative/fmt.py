"""Number formatting shared by every generated sentence, so prose and
tables quote identical figures."""

from __future__ import annotations


def bp(x: float | None, signed: bool = True) -> str:
    if x is None:
        return "n/a"
    v = round(x)
    if v == 0:
        return "0bp" if not signed else "unch"
    return f"{v:+d}bp" if signed else f"{abs(v)}bp"


def pct(x: float | None, signed: bool = True, places: int = 1) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.{places}f}%" if signed else f"{abs(x):.{places}f}%"


def level(x: float | None, places: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{places}f}%"


def move(st: dict | None) -> str:
    """A move in the instrument's own unit, signed."""
    if not st or st.get("d1") is None:
        return "n/a"
    unit = st.get("unit", "bp")
    if unit == "bp":
        return bp(st["d1"])
    if unit == "%":
        return pct(st["d1"])
    return f"{st['d1']:+.1f}pts"


def verb(x: float | None, up: str = "rose", down: str = "fell", flat: str = "were little changed") -> str:
    if x is None or abs(x) < 0.5:
        return flat
    return up if x > 0 else down


def word_limit(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    cut = " ".join(words[:limit])
    # Prefer ending on a full sentence.
    end = cut.rfind(".")
    return cut[: end + 1] if end > len(cut) * 0.5 else cut.rstrip(",;") + "."

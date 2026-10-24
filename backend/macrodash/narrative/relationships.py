"""
Market relationships: the textbook causal links between assets, checked
against today's moves. Each rule fires only when both legs moved enough to
matter; it then reports whether the relationship HELD (teaching the link) or
BROKE (flagging something else was driving markets, which is often the more
interesting observation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import fmt
from .templates import Ctx


@dataclass
class Relationship:
    id: str
    topic: str
    statement: str
    status: str          # 'held' | 'broke' | 'signal'
    evidence: str
    lesson: str
    strength: float      # for ordering: how large the moves were

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _same(a: float, b: float) -> bool:
    return (a > 0) == (b > 0)


def r_yields_dollar(ctx: Ctx) -> Relationship | None:
    y, d = ctx.d1("US10Y"), ctx.d1("DXY")
    if y is None or d is None or abs(y) < 2 or abs(d) < 0.15:
        return None
    held = _same(y, d)
    if held:
        stmt = "Higher US yields supported the dollar." if y > 0 else "Lower US yields weighed on the dollar."
    else:
        stmt = ("The dollar fell despite higher Treasury yields." if y > 0
                else "The dollar rose despite lower Treasury yields.")
    return Relationship("yields_dollar", "Rates → FX", stmt, "held" if held else "broke",
                        f"UST 10Y {fmt.bp(y)}, DXY {fmt.pct(d)}",
                        "Higher US yields raise the return on dollar assets and attract capital. When the dollar "
                        "moves against yields, risk sentiment or non-US news is usually driving FX instead.",
                        abs(y) / 3 + abs(d) / 0.3)


def r_real_gold(ctx: Ctx) -> Relationship | None:
    r, g = ctx.d1("US10YREAL"), ctx.d1("GOLD")
    if r is None or g is None or abs(r) < 2 or abs(g) < 0.3:
        return None
    held = not _same(r, g)
    if held:
        stmt = "Higher real yields pressured gold." if r > 0 else "Lower real yields supported gold."
    else:
        stmt = "Gold rose despite higher real yields." if r > 0 else "Gold fell despite lower real yields."
    return Relationship("real_gold", "Real yields → Gold", stmt, "held" if held else "broke",
                        f"US 10Y real {fmt.bp(r)}, gold {fmt.pct(g)}",
                        "Gold pays no coupon, so higher real yields raise the opportunity cost of holding it. A break "
                        "often reflects central-bank buying, geopolitical hedging or dollar moves.",
                        abs(r) / 3 + abs(g) / 0.8)


def r_ust_bund_eur(ctx: Ctx) -> Relationship | None:
    s, e = ctx.d1("US10_DE10"), ctx.d1("EURUSD")
    if s is None or e is None or abs(s) < 2 or abs(e) < 0.15:
        return None
    held = not _same(s, e)
    if held:
        stmt = ("Wider Treasury–Bund spreads favoured USD over EUR." if s > 0
                else "Narrower Treasury–Bund spreads favoured EUR over USD.")
    else:
        stmt = ("EUR/USD rose even as the Treasury–Bund spread widened." if s > 0
                else "EUR/USD fell even as the Treasury–Bund spread narrowed.")
    return Relationship("ust_bund_eur", "Spreads → FX", stmt, "held" if held else "broke",
                        f"UST–Bund 10Y {fmt.bp(s)}, EUR/USD {fmt.pct(e)}",
                        "FX tends to follow relative rates: a wider US–German yield gap raises the carry on USD "
                        "versus EUR. Front-end (2Y) differentials usually matter more than 10Y.",
                        abs(s) / 3 + abs(e) / 0.3)


def r_us_curve(ctx: Ctx) -> Relationship | None:
    c = ctx.curves.get("US_2s10s")
    if not c or c.get("d1") is None or abs(c["d1"]) < 2:
        return None
    shape = c["shape_d1"]
    stmts = {
        "bear_steepener": "Bear steepening in Treasuries pointed to rising term premium or inflation risk rather than a policy repricing.",
        "bull_steepener": "Bull steepening in Treasuries reflected markets pricing earlier or deeper Fed cuts.",
        "bear_flattener": "Front-end-led selling flattened the Treasury curve: markets priced a more hawkish Fed.",
        "bull_flattener": "A long-end-led rally flattened the Treasury curve, consistent with growth concerns or demand for duration.",
        "twist_steepener": "The Treasury curve twisted steeper: easier near-term policy but more long-run risk premium.",
        "twist_flattener": "The Treasury curve twisted flatter: tighter policy priced while long-end yields fell on growth risk.",
    }
    if shape not in stmts:
        return None
    return Relationship("us_curve", "Curve shape", stmts[shape], "signal",
                        f"2s10s {fmt.bp(c['d1'])} (2Y {fmt.bp(c['front_d1'])}, 10Y {fmt.bp(c['back_d1'])})",
                        c["shape_d1_explain"], abs(c["d1"]) / 2)


def r_btp(ctx: Ctx) -> Relationship | None:
    s = ctx.spreads.get("IT10_DE10")
    if not s or s.get("d1") is None or abs(s["d1"]) < 3:
        return None
    eq = ctx.d1("SX5E")
    wider = s["d1"] > 0
    stmt = ("Wider BTP–Bund spreads indicated a higher Italian sovereign risk premium."
            if wider else "Tighter BTP–Bund spreads signalled stronger demand for periphery risk.")
    status = "signal"
    if eq is not None and abs(eq) >= 0.4:
        status = "held" if (wider and eq < 0) or (not wider and eq > 0) else "broke"
    return Relationship("btp_bund", "Sovereign risk", stmt, status,
                        f"BTP–Bund {fmt.bp(s['d1'])} to {s['last']:.0f}bp" + (f", Euro Stoxx {fmt.pct(eq)}" if eq is not None else ""),
                        "BTP–Bund is the euro area's main gauge of sovereign and fragmentation risk; it usually widens "
                        "with risk-off and narrows when risk appetite is strong.", abs(s["d1"]) / 3)


def r_uk_long_end(ctx: Ctx) -> Relationship | None:
    uk, us = ctx.d1("UK30Y"), ctx.d1("US30Y")
    if uk is None or us is None or uk < 3 or uk - us < 3:
        return None
    return Relationship("uk_term_premium", "Term premium", "Higher UK 30Y yields, outpacing Treasuries, suggested rising "
                        "UK term premium and fiscal supply concerns.", "signal",
                        f"Gilt 30Y {fmt.bp(uk)} vs UST 30Y {fmt.bp(us)}",
                        "When long gilts underperform without a matching front-end move, the market is demanding more "
                        "compensation for duration: issuance, fiscal credibility and pension demand matter most.",
                        (uk - us) / 3)


def r_oil_breakevens(ctx: Ctx) -> Relationship | None:
    o, b = ctx.d1("BRENT"), ctx.d1("US5YBE")
    if o is None or b is None or abs(o) < 1.5 or abs(b) < 1:
        return None
    held = _same(o, b)
    stmt = ("Higher oil lifted US breakevens." if o > 0 else "Lower oil pulled US breakevens down.") if held else \
        ("US breakevens fell despite higher oil." if o > 0 else "US breakevens rose despite lower oil.")
    return Relationship("oil_breakevens", "Commodities → Inflation", stmt, "held" if held else "broke",
                        f"Brent {fmt.pct(o)}, US 5Y breakeven {fmt.bp(b)}",
                        "Energy feeds directly into headline inflation, so short-dated breakevens track oil closely.",
                        abs(o) / 2 + abs(b) / 2)


def r_equity_credit(ctx: Ctx) -> Relationship | None:
    e, c = ctx.d1("SPX"), ctx.d1("US_HY_OAS")
    if e is None or c is None or abs(e) < 0.6 or abs(c) < 4:
        return None
    held = not _same(e, c)
    if held:
        stmt = ("Credit confirmed the equity sell-off as high-yield spreads widened." if e < 0
                else "Credit confirmed the equity rally as high-yield spreads tightened.")
    else:
        stmt = ("High-yield spreads widened even as equities rose: credit is not confirming the rally."
                if e > 0 else "High-yield spreads tightened despite weaker equities: credit is looking through the sell-off.")
    return Relationship("equity_credit", "Equities ↔ Credit", stmt, "held" if held else "broke",
                        f"S&P 500 {fmt.pct(e)}, US HY OAS {fmt.bp(c)}",
                        "Equities and credit both price corporate risk. When they disagree, credit (the more senior "
                        "claim) is often the better signal.", abs(e) / 0.8 + abs(c) / 8)


def r_usdjpy(ctx: Ctx) -> Relationship | None:
    us, jp, fx = ctx.d1("US10Y"), ctx.d1("JP10Y"), ctx.d1("USDJPY")
    if None in (us, jp, fx):
        return None
    diff = us - jp
    if abs(diff) < 2 or abs(fx) < 0.25:
        return None
    held = _same(diff, fx)
    if held:
        stmt = ("A wider US–Japan yield gap lifted USD/JPY." if diff > 0
                else "A narrower US–Japan yield gap pulled USD/JPY lower.")
    else:
        stmt = ("The yen strengthened despite a wider US–Japan yield gap, suggesting safe-haven demand."
                if diff > 0 else "The yen weakened despite a narrower US–Japan yield gap.")
    return Relationship("usdjpy_diff", "Rates → FX", stmt, "held" if held else "broke",
                        f"UST–JGB 10Y {fmt.bp(diff)}, USD/JPY {fmt.pct(fx)}",
                        "USD/JPY is one of the FX pairs most tightly linked to rate differentials, because the yen "
                        "is a funding currency for carry trades.", abs(diff) / 3 + abs(fx) / 0.4)


def r_china_growth(ctx: Ctx) -> Relationship | None:
    cu, eq = ctx.d1("COPPER"), ctx.d1("CSI300")
    if cu is None or eq is None or abs(cu) < 1 or abs(eq) < 0.7:
        return None
    held = _same(cu, eq)
    stmt = ("Copper and Chinese equities rose together, pointing to firmer China growth sentiment." if cu > 0
            else "Copper and Chinese equities fell together, pointing to softer China growth sentiment.") if held else \
        "Copper and Chinese equities diverged, so the move looks supply-driven rather than about China demand."
    return Relationship("china_growth", "Growth", stmt, "held" if held else "broke",
                        f"Copper {fmt.pct(cu)}, CSI 300 {fmt.pct(eq)}",
                        "China consumes about half the world's copper, so the metal is a real-time proxy for Chinese "
                        "industrial demand.", abs(cu) / 1.5 + abs(eq) / 1)


def r_gilt_bund(ctx: Ctx) -> Relationship | None:
    s = ctx.spreads.get("UK10_DE10")
    if not s or s.get("d1") is None or abs(s["d1"]) < 3:
        return None
    w = s["d1"] > 0
    stmt = ("Gilts underperformed Bunds, pointing to UK-specific drivers such as data, BoE pricing or fiscal supply."
            if w else "Gilts outperformed Bunds, pointing to UK-specific relief from data, BoE pricing or fiscal news.")
    return Relationship("gilt_bund", "Cross-market", stmt, "signal", f"Gilt–Bund 10Y {fmt.bp(s['d1'])} to {s['last']:.0f}bp",
                        "Cross-market spreads strip out the global rates move, isolating what was local.",
                        abs(s["d1"]) / 3)


RULES: list[Callable[[Ctx], Relationship | None]] = [
    r_yields_dollar, r_real_gold, r_ust_bund_eur, r_us_curve, r_btp, r_uk_long_end,
    r_oil_breakevens, r_equity_credit, r_usdjpy, r_china_growth, r_gilt_bund,
]


def build_relationships(ctx: Ctx, limit: int = 8) -> list[dict]:
    found = [r for rule in RULES if (r := rule(ctx)) is not None]
    found.sort(key=lambda r: -r.strength)
    return [r.as_dict() for r in found[:limit]]

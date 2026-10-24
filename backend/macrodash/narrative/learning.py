"""
Interview mode and flashcards.

Questions are generated from the day's most salient moves (salience = how
unusual the move was), each with a model answer assembled from computed data
plus the concept an interviewer is testing. Flashcards mix today's facts
(date-stamped, reviewed once or twice) with concept cards whose IDs are
stable, so spaced repetition keeps bringing them back.
"""

from __future__ import annotations

import hashlib

from . import fmt
from .templates import Ctx


def _cid(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


# ----------------------------------------------------------- interview ---

def _q_curve(ctx: Ctx) -> list[tuple[float, dict]]:
    out = []
    names = {"US": ("US", "Treasury", "FED"), "UK": ("UK", "gilt", "BOE"), "DE": ("German", "Bund", "ECB")}
    for cid in ("US_2s10s", "UK_2s10s", "DE_2s10s"):
        c = ctx.curves.get(cid)
        if not c or c.get("front_d1") is None or c.get("back_d1") is None or abs(c["d1"]) < 1:
            continue
        adj, market, bank = names[c["region"]]
        f, b = c["front_d1"], c["back_d1"]
        # Outperform = yields fell more / rose less.
        winner, loser = ("2Y", "10Y") if f < b else ("10Y", "2Y")
        pol = ctx.policy.get(bank, {})
        chg = pol.get("priced_12m_chg_bp")
        policy_line = ""
        if chg is not None and abs(chg) >= 1:
            policy_line = (f" Market pricing for the {pol.get('short', bank)} over 12 months moved {fmt.bp(chg)}, "
                           f"which is what drives the front end.")
        q = f"Why did the {adj} {winner} outperform the {loser}?"
        a = (f"The {adj} 2Y moved {fmt.bp(f)} and the 10Y {fmt.bp(b)}, so 2s10s moved {fmt.bp(c['d1'])} to "
             f"{c['last']:.0f}bp: a {c['shape_d1_label'].lower()}. {c['shape_d1_explain']}{policy_line} "
             f"Key framework: the 2Y is anchored by expected policy over two years; the 10Y adds term premium and "
             f"long-run growth and inflation expectations.")
        out.append((abs(c.get("z_d1") or 0) + abs(c["d1"]) / 5, {"topic": "Yield curves", "question": q, "answer": a}))
    return out


def _q_cross_market(ctx: Ctx) -> list[tuple[float, dict]]:
    out = []
    pairs = {"UK10_DE10": ("Gilts", "Bunds"), "US10_DE10": ("Treasuries", "Bunds"), "JP10_DE10": ("JGBs", "Bunds")}
    for sid, (a_name, b_name) in pairs.items():
        s = ctx.spreads.get(sid)
        if not s or s.get("d1") is None or abs(s["d1"]) < 2:
            continue
        da, db = ctx.d1(s["a"]), ctx.d1(s["b"])
        winner, loser = (b_name, a_name) if s["d1"] > 0 else (a_name, b_name)
        q = f"Why did {winner} outperform {loser}?"
        a = (f"10Y {a_name} moved {fmt.bp(da)} versus {fmt.bp(db)} for {b_name}, so the spread moved {fmt.bp(s['d1'])} "
             f"to {s['last']:.0f}bp ({s.get('pct_1y') or 0:.0f}th percentile of the past year). Cross-market spreads "
             f"remove the global rates move and isolate local drivers: domestic data surprises, relative central-bank "
             f"repricing, and supply or fiscal news. Check whether the front end (2Y spread) moved too: if it did, "
             f"it is a policy story; if only the long end moved, it is term premium.")
        out.append((abs(s.get("z_d1") or 0) + abs(s["d1"]) / 4, {"topic": "Cross-country spreads", "question": q, "answer": a}))
    return out


def _q_btp(ctx: Ctx) -> list[tuple[float, dict]]:
    s = ctx.spreads.get("IT10_DE10")
    if not s or s.get("d1") is None or abs(s["d1"]) < 2:
        return []
    verb = "widen" if s["d1"] > 0 else "tighten"
    q = f"Why did BTP–Bund spreads {verb}?"
    a = (f"BTP–Bund moved {fmt.bp(s['d1'])} to {s['last']:.0f}bp. The spread prices Italian sovereign credit and "
         f"redenomination risk relative to Germany. It widens with global risk-off, Italian fiscal or political news, "
         f"or a hawkish ECB (higher rates raise debt-servicing concerns), and tightens with strong risk appetite and "
         f"carry demand. The ECB's TPI backstop limits disorderly widening. Today's Euro Stoxx move was "
         f"{fmt.pct(ctx.d1('SX5E'))}.")
    return [(abs(s.get("z_d1") or 0) + abs(s["d1"]) / 3, {"topic": "Sovereign risk", "question": q, "answer": a})]


def _q_dollar(ctx: Ctx) -> list[tuple[float, dict]]:
    y, d = ctx.d1("US10Y"), ctx.d1("DXY")
    if y is None or d is None or abs(d) < 0.15:
        return []
    two = ctx.d1("US2_DE2")
    if (y > 0) != (d > 0) and abs(y) >= 1:
        q = (f"Why did the dollar {'strengthen' if d > 0 else 'weaken'} despite "
             f"{'lower' if y < 0 else 'higher'} Treasury yields?")
        a = (f"DXY moved {fmt.pct(d)} while the 10Y moved {fmt.bp(y)}. When the dollar and yields diverge, "
             f"rate differentials are not the driver: look at relative moves (US–Germany 2Y spread "
             f"{fmt.bp(two)}), risk sentiment (the dollar is a safe haven in sell-offs), and idiosyncratic moves "
             f"in EUR, JPY or GBP, which dominate DXY's weights (EUR is about 58%).")
    else:
        q = f"Why did the dollar {'strengthen' if d > 0 else 'weaken'}?"
        a = (f"DXY moved {fmt.pct(d)} alongside a {fmt.bp(y)} move in 10Y Treasuries and {fmt.bp(two)} in the "
             f"US–Germany 2Y spread. The textbook link is relative rates: higher US yields versus the rest of the "
             f"world raise the carry on USD.")
    return [(abs(d) / 0.3 + abs(y) / 5, {"topic": "FX", "question": q, "answer": a})]


def _q_attribution(ctx: Ctx) -> list[tuple[float, dict]]:
    a = ctx.attribution.get(("US", "d1"))
    if not a or a.get("d_nominal") is None or abs(a["d_nominal"]) < 2:
        return []
    move = "sell-off" if a["d_nominal"] > 0 else "rally"
    q = f"Was today's Treasury {move} driven by real yields or inflation expectations?"
    ans = (f"{a['text']} Nominal yield = real yield + breakeven inflation. Real-yield-led moves usually reflect "
           f"policy expectations or growth; breakeven-led moves reflect inflation risk, often energy prices. "
           f"Brent moved {fmt.pct(ctx.d1('BRENT'))}.")
    return [(abs(a["d_nominal"]) / 3, {"topic": "Inflation & real rates", "question": q, "answer": ans})]


def _q_policy(ctx: Ctx) -> list[tuple[float, dict]]:
    out = []
    for bank in ("FED", "BOE", "ECB", "BOJ"):
        p = ctx.policy.get(bank)
        if not p or not p.get("summary"):
            continue
        s = p["summary"]
        chg = p.get("priced_12m_chg_bp") or 0
        q = f"What is the market pricing for the {p['name']}, and what changed today?"
        a = (f"Policy rate {fmt.level(p['policy_rate'])}. {p['description']} The 12-month pricing moved "
             f"{fmt.bp(chg)} on the day. Method: {p['method_label']}. Remember that one 25bp move is 25bp of pricing, "
             f"so {fmt.bp(s['priced_12m_bp'])} is {abs(s['moves_12m']):.1f} moves.")
        out.append((abs(chg) / 3 + 0.5, {"topic": "Central bank pricing", "question": q, "answer": a}))
    return out


def _q_regime(ctx: Ctx) -> list[tuple[float, dict]]:
    r = ctx.regime
    if not r or r.get("name") in (None, "Insufficient data"):
        return []
    drivers = ", ".join(d.replace("_", " ") for d in r.get("drivers", [])) or "no single factor"
    q = "How would you characterise today's market regime, and what's your evidence?"
    a = (f"{r['name']}: {r.get('summary', '')}. The classifier scores each regime's expected cross-asset signature "
         f"against today's volatility-adjusted moves; the strongest factors were {drivers}. Confidence: "
         f"{r.get('confidence', 'low')}. In an interview, lead with the conclusion, then two or three confirming "
         f"moves, then the one asset that does not fit.")
    return [(1.0 + (r.get("score") or 0), {"topic": "Macro regime", "question": q, "answer": a})]


def _q_japan(ctx: Ctx) -> list[tuple[float, dict]]:
    st = ctx.st("JP10Y")
    if not st or st.get("z_d1") is None or abs(st["z_d1"]) < 1:
        return []
    q = "What is driving JGB yields, and why does it matter globally?"
    a = (f"JGB 10Y moved {fmt.bp(st['d1'])} to {fmt.level(st['last'], 3)} (a {abs(st['z_d1']):.1f}-sigma move). "
         f"JGB yields reflect BoJ normalisation expectations and the pace of bond-buying reduction. Higher JGB yields "
         f"can draw Japanese savings home, removing a marginal buyer of Treasuries and Bunds, which is why JGB moves "
         f"can lift global term premia. USD/JPY moved {fmt.pct(ctx.d1('USDJPY'))}.")
    return [(abs(st["z_d1"]), {"topic": "Japan", "question": q, "answer": a})]


GENERATORS = [_q_curve, _q_cross_market, _q_btp, _q_dollar, _q_attribution, _q_policy, _q_regime, _q_japan]


def interview_questions(ctx: Ctx, n: int = 5) -> list[dict]:
    pool: list[tuple[float, dict]] = []
    for gen in GENERATORS:
        pool.extend(gen(ctx))
    pool.sort(key=lambda t: -t[0])
    chosen, topics = [], {}
    for score, q in pool:
        # At most two questions per topic keeps the set varied.
        if topics.get(q["topic"], 0) >= 2:
            continue
        topics[q["topic"]] = topics.get(q["topic"], 0) + 1
        chosen.append({**q, "id": _cid(q["question"]), "salience": round(score, 2)})
        if len(chosen) == n:
            break
    return chosen


# ----------------------------------------------------------- flashcards --

CONCEPT_CARDS = [
    ("Yield curves", "What is a bear steepener, and what usually causes it?",
     "Yields rise with the long end rising more than the front. Usually term premium, fiscal supply or "
     "inflation risk, not a policy repricing."),
    ("Yield curves", "What is a bull flattener, and what usually causes it?",
     "Yields fall with the long end falling more. Usually growth fears, lower inflation risk or duration demand."),
    ("Yield curves", "What does a bear flattener signal?",
     "Front-end yields rise more than the long end: markets price a more hawkish central bank."),
    ("Macro relationships", "Higher real yields: what happens to gold, and why?",
     "Gold usually falls: it pays no coupon, so higher real yields raise the opportunity cost of holding it."),
    ("Macro relationships", "Decompose a nominal yield.", "Nominal = real yield + breakeven inflation (+ inflation risk "
     "premium and liquidity effects)."),
    ("Central bank pricing", "How do you convert OIS pricing into the probability of a 25bp move?",
     "Probability ≈ implied change at the meeting ÷ 25bp. For example, −18bp priced means about a 72% chance of a 25bp cut."),
    ("Cross-country spreads", "Which spread is the euro area's main sovereign-risk gauge?",
     "BTP–Bund 10Y. It widens on risk-off, Italian fiscal or political risk, or a hawkish ECB."),
    ("Macro relationships", "Why does USD/JPY track the UST–JGB yield differential?",
     "The yen funds carry trades. A wider US–Japan rate gap raises the carry from short JPY / long USD."),
    ("Central bank pricing", "How does CME FedWatch get meeting probabilities from fed funds futures?",
     "Each contract settles on the month's average EFFR. Solve avg = (d/N)·r_pre + ((N−d)/N)·r_post for "
     "the post-meeting rate."),
    ("Yield curves", "What is a 5y5y forward and why do central banks watch it?",
     "The 5-year rate starting in 5 years. In breakevens it measures long-run inflation expectations "
     "beyond the cycle, the anchoring test."),
]


def flashcards(ctx: Ctx, as_of: str, n: int = 5) -> list[dict]:
    cards: list[dict] = []

    def add(topic: str, front: str, back: str, kind: str):
        cid = _cid(front) if kind == "concept" else _cid(as_of, front)
        cards.append({"id": cid, "topic": topic, "front": front, "back": back, "kind": kind})

    c = ctx.curves.get("US_2s10s")
    if c and c.get("last") is not None:
        add("Yield curves", "Where is US 2s10s, and what did it do today?",
            f"{c['last']:.0f}bp ({c.get('pct_1y') or 0:.0f}th pct of 1Y). Today {fmt.bp(c['d1'])}: {c['shape_d1_label'].lower()}.", "fact")
    fed = ctx.policy.get("FED")
    if fed and fed.get("summary"):
        s = fed["summary"]
        add("Central bank pricing", "How much Fed easing or tightening is priced over 12 months?",
            f"{fmt.bp(s['priced_12m_bp'])} ≈ {abs(s['moves_12m']):.1f} moves; terminal {s['terminal_rate']:.2f}%.", "fact")
    btp = ctx.spreads.get("IT10_DE10")
    if btp and btp.get("last") is not None:
        add("Cross-country spreads", "Where is BTP–Bund 10Y?",
            f"{btp['last']:.0f}bp; 1Y range {btp.get('lo_1y') or 0:.0f}–{btp.get('hi_1y') or 0:.0f}bp; today {fmt.bp(btp['d1'])}.", "fact")
    top = (ctx.movers.get("top") or [None])[0]
    if top:
        mv = fmt.bp(top["d1"]) if top["unit"] == "bp" else fmt.pct(top["d1"])
        add("Recent market moves", "What was today's largest volatility-adjusted move?",
            f"{top['name']} {mv} ({abs(top['z']):.1f}σ vs its 20-day vol).", "fact")
    us10 = ctx.st("US10Y")
    if us10 and us10.get("last") is not None:
        add("Recent market moves", "US 10Y yield: level and 1-month change?",
            f"{fmt.level(us10['last'])}; 1M {fmt.bp(us10.get('m1'))}; 1Y percentile {us10.get('pct_1y') or 0:.0f}.", "fact")
    # Concept card rotates daily so every concept surfaces over two weeks.
    idx = sum(map(ord, as_of)) % len(CONCEPT_CARDS)
    for k in range(2):
        topic, front, back = CONCEPT_CARDS[(idx + k) % len(CONCEPT_CARDS)]
        add(topic, front, back, "concept")
    # Five per day: four facts (or fewer) topped up with concepts.
    facts = [c for c in cards if c["kind"] == "fact"][:4]
    concepts = [c for c in cards if c["kind"] == "concept"]
    return (facts + concepts)[:n]

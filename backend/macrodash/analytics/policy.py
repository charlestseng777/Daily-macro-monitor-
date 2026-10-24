"""
Market-implied central bank paths.

Two engines produce the same output shape (one row per meeting with the
implied rate after it):

1. `path_from_ois_curve`: from an OIS (or proxy) term structure. Spot rates
   are interpolated linearly in zero-rate space and turned into discount
   factors; the average forward across each inter-meeting window is the
   expected overnight rate after that meeting. This is the
   standard meeting-date bootstrap used on rates desks.

2. `path_from_fed_funds_futures`: from 30-day fed funds futures, using the
   CME FedWatch month-averaging method. A contract settles on the average
   effective rate across its month, so for a month with a meeting on day d of
   N:  avg = (d/N)*r_pre + ((N-d)/N)*r_post  =>  r_post = (avg*N - r_pre*d)/(N-d).

Expected moves are expressed relative to today's overnight fixing and then
added to the policy rate, so a constant overnight-to-policy basis
(e.g. EFFR vs the top of the Fed's range) drops out.
"""

from __future__ import annotations

import calendar
import datetime as dt
import math

DAY = 365.0


# ----------------------------------------------------- curve bootstrap ----

def _df(rate_pct: float, t: float) -> float:
    return math.exp(-rate_pct / 100.0 * t)


def interp_df(nodes: list[tuple[float, float]], t: float) -> float:
    """Discount factor at t (years) from (tenor, spot rate %) nodes, using
    linear interpolation of zero rates (flat beyond the end nodes).

    Linear-in-zero keeps forwards moving gradually between sparse nodes; a
    flat-forward scheme would load a whole 1Y node's slope onto the first
    meeting when the curve has few points (e.g. a bill-curve proxy).
    """
    if t <= 0:
        return 1.0
    pts = sorted(nodes)
    if t <= pts[0][0]:
        z = pts[0][1]
    elif t >= pts[-1][0]:
        z = pts[-1][1]
    else:
        z = pts[-1][1]
        for (t0, r0), (t1, r1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                z = r0 + (r1 - r0) * (t - t0) / (t1 - t0)
                break
    return _df(z, t)


def avg_forward(nodes: list[tuple[float, float]], t0: float, t1: float) -> float:
    """Average continuously-compounded forward between t0 and t1, in %."""
    if t1 <= t0:
        t1 = t0 + 1 / DAY
    return -math.log(interp_df(nodes, t1) / interp_df(nodes, t0)) / (t1 - t0) * 100.0


def path_from_ois_curve(today: dt.date, meetings: list[dt.date], overnight: float,
                        nodes: list[tuple[float, float]], horizon_months: int = 24) -> list[dict]:
    """Implied overnight rate after each upcoming meeting.

    `nodes` are (tenor years, spot rate %) pairs. The overnight fixing anchors
    the very front of the curve.
    """
    nodes = sorted((t, r) for t, r in nodes if t > 0)
    if not nodes:
        return []
    # Anchor: today's fixing at one day.
    nodes = [(1 / DAY, overnight)] + [n for n in nodes if n[0] > 1 / DAY]
    end = today + dt.timedelta(days=int(horizon_months * 30.5))
    future = [m for m in sorted(meetings) if today < m <= end]
    out, prev = [], overnight
    for i, m in enumerate(future):
        start_t = (m - today).days / DAY
        nxt = future[i + 1] if i + 1 < len(future) else m + dt.timedelta(days=45)
        end_t = (nxt - today).days / DAY
        rate = avg_forward(nodes, start_t, end_t)
        out.append({"date": m.isoformat(), "rate": rate, "change_bp": (rate - prev) * 100.0,
                    "cumulative_bp": (rate - overnight) * 100.0})
        prev = rate
    return out


# -------------------------------------------------- fed funds futures -----

def path_from_fed_funds_futures(today: dt.date, meetings: list[dt.date], effr: float,
                                futures: dict[tuple[int, int], float]) -> list[dict]:
    """`futures` maps (year, month) -> contract price (100 - average EFFR)."""
    implied = {k: 100.0 - p for k, p in futures.items() if p}
    meeting_by_month = {(m.year, m.month): m for m in meetings if m > today}
    out, r_start = [], effr
    months = sorted(k for k in implied if k >= (today.year, today.month))
    for idx, ym in enumerate(months):
        avg = implied[ym]
        meeting = meeting_by_month.get(ym)
        if meeting is None:
            r_start = avg
            continue
        n = calendar.monthrange(*ym)[1]
        d = meeting.day  # rate changes the day after the decision; d days at the old rate
        if n - d < 5:
            # Too few post-meeting days to solve reliably: use next month's average.
            nxt = months[idx + 1] if idx + 1 < len(months) else None
            r_post = implied[nxt] if nxt else avg
        else:
            r_post = (avg * n - r_start * d) / (n - d)
        out.append({"date": meeting.isoformat(), "rate": r_post, "change_bp": (r_post - r_start) * 100.0,
                    "cumulative_bp": (r_post - effr) * 100.0})
        r_start = r_post
    return out


# ------------------------------------------------------------ summary -----

def summarise_path(path: list[dict], today: dt.date, policy_rate: float, step_bp: float = 25.0) -> dict:
    """Next meeting, 3/6/12-month pricing and terminal rate, in policy-rate space."""
    if not path:
        return {}
    for row in path:
        row["policy_implied"] = round(policy_rate + row["cumulative_bp"] / 100.0, 3)
        row["rate"] = round(row["rate"], 3)
        row["change_bp"] = round(row["change_bp"], 1)
        row["cumulative_bp"] = round(row["cumulative_bp"], 1)

    def by(months: int) -> float:
        cutoff = today + dt.timedelta(days=int(months * 30.5))
        within = [r for r in path if dt.date.fromisoformat(r["date"]) <= cutoff]
        return within[-1]["cumulative_bp"] if within else 0.0

    nxt = path[0]
    p3, p6, p12 = by(3), by(6), by(12)
    # Terminal: the extreme of the path in the direction it is travelling.
    direction = -1 if by(24) < 0 else 1
    extreme = min(path, key=lambda r: r["cumulative_bp"]) if direction < 0 else max(path, key=lambda r: r["cumulative_bp"])
    prob = min(abs(nxt["change_bp"]) / step_bp, 1.0) * 100.0
    move = "cut" if nxt["change_bp"] < 0 else "hike"
    return {
        "next_meeting": nxt["date"], "next_change_bp": nxt["change_bp"],
        "next_prob_pct": round(prob), "next_move": move if abs(nxt["change_bp"]) >= 1 else "hold",
        "priced_3m_bp": round(p3, 1), "priced_6m_bp": round(p6, 1), "priced_12m_bp": round(p12, 1),
        "moves_12m": round(p12 / step_bp, 2),
        "terminal_rate": round(policy_rate + extreme["cumulative_bp"] / 100.0, 3),
        "terminal_date": extreme["date"],
    }


def describe(bank_short: str, s: dict) -> str:
    if not s:
        return f"{bank_short}: no market pricing available."
    n12 = s["moves_12m"]
    if abs(n12) < 0.2:
        horizon = "roughly no change over the next 12 months"
    else:
        what = "cuts" if n12 < 0 else "hikes"
        horizon = f"{abs(n12):.1f} {what} ({abs(s['priced_12m_bp']):.0f}bp) over 12 months"
    if s["next_move"] == "hold":
        nxt = "no move at the next meeting"
    else:
        nxt = f"a {s['next_prob_pct']}% chance of a 25bp {s['next_move']} at the next meeting"
    return f"Markets price {nxt} and {horizon}; terminal {s['terminal_rate']:.2f}%."

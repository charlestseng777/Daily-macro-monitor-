"""
The daily job: fetch -> store -> compute -> narrate -> snapshot.

`run()` is what the 05:30 UK scheduler calls. It ingests every instrument
(live providers, or the labelled demo generator), recomputes every statistic
from the stored history, and saves one JSON snapshot that the API serves
unchanged, so page loads never wait on a calculation.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from collections import Counter

import numpy as np
import pandas as pd

from . import instruments as reg
from .analytics import heatmap as hm
from .analytics import movers as mv
from .analytics import policy as pol
from .analytics import regime as rg
from .analytics.curves import build_curves, curve_shapes
from .analytics.inflation import build_attribution
from .analytics.series import compute_stats
from .analytics.spreads import build_forwards, build_spreads
from .clients import SourceRouter
from .clients import demo as demo_src
from .clients import feeds as feed_client
from .clients import fred, yahoo
from .clients.base import SourceError
from .config import get_settings
from .db import Repository
from .narrative import learning, llm, relationships, templates

log = logging.getLogger(__name__)

NUMBERS_TO_REMEMBER = [
    ("US", "United States", ["US2Y", "US5Y", "US10Y", "US30Y"]),
    ("UK", "United Kingdom", ["UK2Y", "UK5Y", "UK10Y", "UK30Y"]),
    ("DE", "Germany", ["DE2Y", "DE5Y", "DE10Y", "DE30Y"]),
    ("JP", "Japan", ["JP2Y", "JP10Y", "JP30Y"]),
]

INFLATION_IDS = ["US5YBE", "US10YBE", "US10YREAL", "UK10YBE", "DE10YBE", "JP10YBE"]

PANELS = {
    "bonds": ("Government bonds", ["US2Y", "US5Y", "US10Y", "US30Y", "UK2Y", "UK5Y", "UK10Y", "UK30Y", "DE2Y", "DE5Y",
                                   "DE10Y", "DE30Y", "JP2Y", "JP10Y", "JP30Y", "FR10Y", "IT10Y", "ES10Y", "CN10Y"]),
    "inflation": ("Inflation", INFLATION_IDS),
    "fx": ("FX", ["DXY", "EURUSD", "GBPUSD", "USDJPY", "USDCNY"]),
    "credit": ("Credit", ["US_IG_OAS", "US_HY_OAS", "EU_HY_OAS", "UK_CREDIT", "JP_CREDIT", "CN_CREDIT"]),
    "equities": ("Equities", ["SPX", "FTSE", "SX5E", "NKY", "CSI300", "VIX"]),
    "commodities": ("Commodities", ["BRENT", "WTI", "GOLD", "COPPER", "TTF"]),
}

METHOD_LABELS = {
    "refinitiv": "Refinitiv OIS curve",
    "fed_funds_futures": "Fed funds futures (CME FedWatch method)",
    "boe_ois_curve": "Bank of England SONIA OIS curve",
    "curve_proxy": "Government bill-curve proxy (indicative)",
    "demo": "Demo curve (synthetic)",
}
METHOD_QUALITY = {"refinitiv": "high", "fed_funds_futures": "high", "boe_ois_curve": "high",
                  "curve_proxy": "low", "demo": "demo"}


# ------------------------------------------------------------- ingest ----

def ingest_live(repo: Repository, router: SourceRouter) -> dict:
    registry = reg.registry()
    used, failed = {}, {}
    for inst in registry.values():
        if inst.sources and inst.sources[0].provider == "derived":
            continue
        got = router.fetch(inst)
        if got is None:
            failed[inst.id] = router.failures.get(inst.id, [])
            continue
        series, source = got
        repo.upsert_series(inst.id, series, source)
        used[inst.id] = source
    _derive(repo)
    return {"sources": used, "failed": failed}


def ingest_demo(repo: Repository, end: dt.date | None = None) -> dict:
    repo.clear_observations()
    data = demo_src.generate(reg.registry(), end=end)
    for iid, s in data.items():
        repo.upsert_series(iid, s, "demo")
    return {"sources": {k: "demo" for k in data}, "failed": {}}


def _derive(repo: Repository) -> None:
    panel = repo.load_panel(["BRENT", "USDJPY"])
    if {"BRENT", "USDJPY"} <= set(panel.columns):
        both = panel[["BRENT", "USDJPY"]].ffill(limit=3).dropna()
        repo.upsert_series("BRENT_JPY", (both["BRENT"] * both["USDJPY"]).round(2), "derived:BRENT*USDJPY")


# --------------------------------------------------------- statistics ----

def determine_as_of(stats: dict[str, dict]) -> str:
    """The latest date that a meaningful share of instruments has reached.
    Asian markets close first and US data lands last; this avoids calling a
    day 'today' when only one market has printed."""
    dates = Counter(st["date"] for st in stats.values() if st.get("date"))
    if not dates:
        return dt.date.today().isoformat()
    total = sum(dates.values())
    running = 0
    for d in sorted(dates, reverse=True):
        running += dates[d]
        if running / total >= 0.4:
            return d
    return max(dates)


def instrument_stats(panel: pd.DataFrame) -> dict[str, dict]:
    out = {}
    for iid, inst in reg.registry().items():
        if iid not in panel:
            continue
        st = compute_stats(panel[iid].dropna(), inst.kind)
        if st is None:
            continue
        out[iid] = {**st.as_dict(), "id": iid, "name": inst.name, "short": inst.short, "unit": inst.move_unit,
                    "kind": inst.kind, "region": inst.region, "asset_class": inst.asset_class}
    return out


def _row(st: dict | None, as_of: str) -> dict | None:
    if not st:
        return None
    keep = ("id", "name", "short", "last", "date", "d1", "w1", "m1", "ytd", "pct_1y", "pct_all", "z_d1", "z_level_1y",
            "vol20", "unit", "spark", "hi_1y", "lo_1y", "region", "asset_class")
    row = {k: st.get(k) for k in keep}
    row["stale"] = bool(st.get("date") and st["date"] < (pd.Timestamp(as_of) - pd.Timedelta(days=3)).date().isoformat())
    return row


# ------------------------------------------------------------- policy ----

def _latest(panel: pd.DataFrame, iid: str) -> float | None:
    if iid not in panel:
        return None
    s = panel[iid].dropna()
    return None if s.empty else float(s.iloc[-1])


def policy_pricing(panel: pd.DataFrame, repo: Repository, router: SourceRouter | None, mode: str,
                   as_of: dt.date) -> list[dict]:
    rows = []
    for bank in reg.central_banks():
        meetings = [dt.date.fromisoformat(d) for d in bank["meetings"]]
        policy_rate = _latest(panel, bank["policy_rate"])
        overnight = _latest(panel, bank["overnight"]) or policy_rate
        if policy_rate is None:
            continue
        path, method = [], None
        try:
            if mode == "demo":
                nodes = demo_src.demo_ois_nodes(bank["id"], as_of, meetings, overnight)
                path, method = pol.path_from_ois_curve(as_of, meetings, overnight, nodes), "demo"
            else:
                path, method = _live_path(bank, panel, router, meetings, overnight, as_of)
        except Exception as exc:  # noqa: BLE001 - one bank failing must not sink the run
            log.warning("%s pricing failed: %s", bank["id"], exc)
        summary = pol.summarise_path(path, as_of, policy_rate, bank.get("step_bp", 25)) if path else {}
        provisional = [m["date"] for m in path if m["date"] >= bank.get("provisional_from", "9999")]
        rows.append({
            "id": bank["id"], "name": bank["name"], "short": bank["short"], "region": bank["region"],
            "policy_rate": round(policy_rate, 3), "overnight": round(overnight, 3) if overnight else None,
            "method": method, "method_label": METHOD_LABELS.get(method or "", "Unavailable"),
            "quality": METHOD_QUALITY.get(method or "", "none"), "path": path[:12], "summary": summary,
            "description": pol.describe(bank["short"], summary), "provisional_meetings": provisional,
            "calendar_url": bank.get("calendar_url"),
        })
    _attach_pricing_history(rows, repo, as_of, mode)
    return rows


def _live_path(bank: dict, panel: pd.DataFrame, router: SourceRouter, meetings, overnight, as_of):
    ois = bank.get("ois", {})
    if router.rdp is not None and ois.get("refinitiv"):
        from .clients import refinitiv as rdp
        nodes = []
        for months, ric in ois["refinitiv"].items():
            try:
                s = rdp.fetch(router.rdp, ric, (as_of - dt.timedelta(days=10)).isoformat(), "rate")
                if len(s):
                    nodes.append((int(months) / 12.0, float(s.iloc[-1])))
            except SourceError as exc:
                log.info("%s %s: %s", bank["id"], ric, exc)
        if len(nodes) >= 3:
            return pol.path_from_ois_curve(as_of, meetings, overnight, nodes), "refinitiv"

    fallback = ois.get("fallback")
    if fallback == "fed_funds_futures":
        effr = _latest(panel, "EFFR") or overnight
        futures = {}
        for k in range(0, 18):
            y, m = divmod(as_of.month - 1 + k, 12)
            ym = (as_of.year + y, m + 1)
            price = yahoo.last_close(router.http, yahoo.fed_funds_contract(*ym))
            if price:
                futures[ym] = price
        if len(futures) >= 4:
            return pol.path_from_fed_funds_futures(as_of, meetings, effr, futures), "fed_funds_futures"
        raise SourceError("too few fed funds futures prices")
    if fallback == "boe_ois_curve":
        _, nodes = router.boe_curves.ois_latest()
        return pol.path_from_ois_curve(as_of, meetings, overnight, nodes), "boe_ois_curve"
    if fallback == "curve_proxy":
        nodes = [(int(m) / 12.0, v) for m, iid in ois.get("proxy_curve", {}).items()
                 if (v := _latest(panel, iid)) is not None]
        if len(nodes) >= 2:
            return pol.path_from_ois_curve(as_of, meetings, overnight, nodes), "curve_proxy"
    raise SourceError(f"no pricing method for {bank['id']}")


def _attach_pricing_history(rows: list[dict], repo: Repository, as_of: dt.date, mode: str) -> None:
    """Store today's 12M pricing as a time series so day-on-day changes (and
    a pricing-history chart) are available."""
    for r in rows:
        s = r["summary"]
        if not s:
            r["priced_12m_chg_bp"] = None
            r["pricing_history"] = []
            continue
        sid = f"PRICING_{r['id']}_12M"
        hist = repo.load_series(sid)
        if mode == "demo" and hist.empty:
            # Back-fill a plausible pricing history for the demo only.
            prev = s["priced_12m_bp"] - demo_src.DEMO_SHOCK_BP.get(r["id"], 0)
            idx = pd.bdate_range(end=as_of, periods=130)[:-1]
            steps = np.random.default_rng(11).normal(0, 1.6, len(idx))
            hist = pd.Series(prev + steps[::-1].cumsum()[::-1] - steps[-1], index=idx).round(1)
            repo.upsert_series(sid, hist, "demo")
        today = pd.Series({pd.Timestamp(as_of): s["priced_12m_bp"]})
        repo.upsert_series(sid, today, f"derived:{r['method']}")
        hist = repo.load_series(sid)
        prior = hist[hist.index < pd.Timestamp(as_of)]
        r["priced_12m_chg_bp"] = round(s["priced_12m_bp"] - float(prior.iloc[-1]), 1) if len(prior) else None
        r["pricing_history"] = [round(float(v), 1) for v in hist.iloc[-90:].values]


# ------------------------------------------------------------- extras ----

def economic_calendar(as_of: dt.date, http) -> list[dict]:
    end = as_of + dt.timedelta(days=21)
    events = []
    for bank in reg.central_banks():
        for d in bank["meetings"]:
            if as_of.isoformat() <= d <= end.isoformat():
                events.append({"date": d, "region": bank["region"], "event": f"{bank['name']} policy decision",
                               "type": "central_bank", "provisional": d >= bank.get("provisional_from", "9999")})
    if http is not None:
        for rid, name in reg.feeds().get("calendar_fred_releases", {}).items():
            if rid.startswith("_"):
                continue
            try:
                for d in fred.release_dates(http, rid, as_of.isoformat(), end.isoformat()):
                    events.append({"date": d, "region": "US", "event": name, "type": "data"})
            except Exception as exc:  # noqa: BLE001
                log.info("calendar %s: %s", name, exc)
    return sorted(events, key=lambda e: e["date"])


def speeches(http) -> list[dict]:
    if http is None:
        return []
    out = []
    for f in reg.feeds().get("speeches", []):
        try:
            out.extend(feed_client.fetch(http, f["url"], f["bank"]))
        except Exception as exc:  # noqa: BLE001
            log.info("speeches %s: %s", f["bank"], exc)
    return sorted(out, key=lambda i: i.get("date") or "", reverse=True)[:20]


def llm_facts(stats, curves, spreads, policy, attribution, regime, movers, as_of) -> dict:
    key = ["US2Y", "US10Y", "US30Y", "UK2Y", "UK10Y", "UK30Y", "DE2Y", "DE10Y", "JP10Y", "JP30Y", "CN10Y",
           "IT10Y", "US10YBE", "US10YREAL", "DXY", "EURUSD", "GBPUSD", "USDJPY", "USDCNY", "SPX", "FTSE",
           "SX5E", "NKY", "CSI300", "VIX", "BRENT", "GOLD", "COPPER", "US_HY_OAS"]
    return {
        "as_of": as_of,
        "regime": {k: regime.get(k) for k in ("name", "summary", "drivers", "confidence")},
        "levels": {k: {"name": stats[k]["name"], "last": stats[k]["last"], "d1": stats[k]["d1"],
                       "w1": stats[k]["w1"], "unit_of_change": stats[k]["unit"]} for k in key if k in stats},
        "curves": [{k: c[k] for k in ("id", "last", "d1", "shape_d1_label")} for c in curves],
        "spreads": [{k: s[k] for k in ("label", "last", "d1")} for s in spreads],
        "policy": [{"bank": p["short"], "policy_rate": p["policy_rate"], "priced_12m_bp": p["summary"].get("priced_12m_bp"),
                    "change_today_bp": p.get("priced_12m_chg_bp"), "next_meeting": p["summary"].get("next_meeting"),
                    "next_change_bp": p["summary"].get("next_change_bp"), "terminal": p["summary"].get("terminal_rate")}
                   for p in policy if p["summary"]],
        "attribution": [a["text"] for a in attribution if a["horizon"] == "d1"],
        "top_movers": [{k: m[k] for k in ("name", "d1", "unit", "z")} for m in movers.get("top", [])],
    }


# ---------------------------------------------------------------- run ----

def build_snapshot(repo: Repository, mode: str, router: SourceRouter | None, ingest_report: dict) -> dict:
    t0 = time.perf_counter()
    panel = repo.load_panel()
    if panel.empty:
        raise RuntimeError("no data in the database; run ingestion first")
    stats = instrument_stats(panel)
    as_of = determine_as_of(stats)
    as_of_d = dt.date.fromisoformat(as_of)
    registry = reg.registry()

    curves, _ = build_curves(panel, stats)
    spreads, _ = build_spreads(panel)
    forwards, _ = build_forwards(panel)
    policy = policy_pricing(panel, repo, router, mode, as_of_d)
    attribution = build_attribution(stats)

    z = {k: v.get("z_d1") for k, v in stats.items() if v.get("date") == as_of}
    z.update({c["id"]: c.get("z_d1") for c in curves})
    regime = rg.classify_regime(z)
    # Movers and the heatmap use each market's latest print if it is recent;
    # sources that publish a day later (BoE curves, FRED OAS, MOF) are kept
    # and flagged rather than dropped. The regime uses same-day moves only.
    floor = (as_of_d - dt.timedelta(days=4)).isoformat()
    recent = {k: {**v, "lagged": v["date"] < as_of} for k, v in stats.items() if v.get("date") and v["date"] >= floor}
    movers = mv.rank_movers(recent, registry, as_of)
    heat = hm.build_heatmap(recent, registry)

    ctx = templates.Ctx(stats, curves, spreads, policy, attribution, regime, movers)
    regime_text = templates.regime_paragraph(ctx)
    regions = templates.regional_summaries(ctx)
    rels = relationships.build_relationships(ctx)
    questions = learning.interview_questions(ctx)
    cards = learning.flashcards(ctx, as_of)

    facts = llm_facts(stats, curves, spreads, policy, attribution, regime, movers, as_of)
    llm_status = {"used": False, "reason": "demo mode"}
    if mode != "demo":
        styled, llm_status = llm.restyle(facts, {"regime_paragraph": regime_text, "regions": regions})
        if styled:
            regime_text, regions = styled["regime_paragraph"], styled["regions"]

    repo.add_flashcards(cards, dt.date.today())

    http = router.http if router else None
    numbers = [{"region": code, "name": name, "rows": [r for i in ids if (r := _row(stats.get(i), as_of))]}
               for code, name, ids in NUMBERS_TO_REMEMBER]
    infl_attr = next((a for a in attribution if a["region"] == "US" and a["horizon"] == "d1"), None)
    payload = {
        "meta": {
            "as_of": as_of, "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "mode": mode, "build_ms": None, "llm": llm_status,
            "sources": ingest_report.get("sources", {}),
            "failed_sources": {k: v[:3] for k, v in ingest_report.get("failed", {}).items()},
            "stale": sorted(k for k, v in stats.items() if v["date"] < (as_of_d - dt.timedelta(days=3)).isoformat()),
        },
        "regime": {**regime, "headline": regime["name"], "paragraph": regime_text},
        "movers": movers,
        "heatmap": heat,
        "numbers": numbers,
        "curves": curves,
        "curve_shapes": curve_shapes(panel),
        "spreads": spreads,
        "forwards": forwards,
        "policy": policy,
        "inflation": {
            "rows": [r for i in INFLATION_IDS if (r := _row(stats.get(i), as_of))],
            "forwards": [f for f in forwards if f["id"] == "US_BE_5y5y"],
            "attribution": attribution,
            "headline": infl_attr["text"] if infl_attr else None,
        },
        "regions": [{"id": k, "name": templates.REGION_TITLES[k], "text": v} for k, v in regions.items()],
        "relationships": rels,
        "interview": questions,
        "flashcards": cards,
        "panels": {
            key: {"title": title, "rows": [r for i in ids if (r := _row(stats.get(i), as_of))]}
            for key, (title, ids) in PANELS.items()
        },
        "calendar": economic_calendar(as_of_d, http if mode != "demo" else None),
        "speeches": speeches(http if mode != "demo" else None),
    }
    payload["meta"]["build_ms"] = round((time.perf_counter() - t0) * 1000)
    repo.save_snapshot(as_of_d, mode, payload)
    return payload


def run(demo: bool | None = None, skip_ingest: bool = False) -> dict:
    s = get_settings()
    mode = "demo" if (s.demo_mode if demo is None else demo) else "live"
    repo = Repository()
    run_id = repo.start_run(mode)
    router = None
    try:
        router = None if mode == "demo" else SourceRouter()
        if skip_ingest:
            report = {"sources": {}, "failed": {}}
        elif mode == "demo":
            report = ingest_demo(repo)
        else:
            report = ingest_live(repo, router)
        payload = build_snapshot(repo, mode, router, report)
        status = "ok" if not report["failed"] else "partial"
        repo.finish_run(run_id, status, {"as_of": payload["meta"]["as_of"], "failed": list(report["failed"]),
                                         "instruments": len(report["sources"])})
        log.info("snapshot %s built (%s, %d sources, %d failed)", payload["meta"]["as_of"], mode,
                 len(report["sources"]), len(report["failed"]))
        return payload
    except Exception as exc:
        repo.finish_run(run_id, "error", {"error": str(exc)})
        log.exception("pipeline failed")
        raise
    finally:
        if router is not None and router.rdp is not None:
            router.rdp.release()

import datetime as dt

import pytest

from macrodash.analytics.policy import (avg_forward, path_from_fed_funds_futures, path_from_ois_curve,
                                        summarise_path)
from macrodash.clients.demo import demo_ois_nodes

TODAY = dt.date(2026, 10, 23)
MEETINGS = [dt.date(2026, 10, 28), dt.date(2026, 12, 9), dt.date(2027, 1, 27), dt.date(2027, 3, 17),
            dt.date(2027, 4, 28), dt.date(2027, 6, 9)]


def test_flat_curve_prices_nothing():
    nodes = [(t, 4.0) for t in (1 / 12, 0.25, 0.5, 1.0, 2.0)]
    path = path_from_ois_curve(TODAY, MEETINGS, 4.0, nodes)
    assert path and all(abs(p["cumulative_bp"]) < 0.01 for p in path)


def test_forward_of_flat_is_flat():
    assert avg_forward([(1.0, 3.0), (2.0, 3.0)], 0.4, 1.7) == pytest.approx(3.0)


def test_bootstrap_recovers_step_path():
    """Build spot nodes from a known step path, then recover it."""
    from macrodash.clients import demo
    demo.DEMO_PATHS["TEST"] = [-25, -50, -50, -75, -75, -75]
    demo.DEMO_SHOCK_BP["TEST"] = 0
    nodes = demo_ois_nodes("TEST", TODAY, MEETINGS, 4.0, shocked=False)
    path = path_from_ois_curve(TODAY, MEETINGS, 4.0, nodes, horizon_months=6)
    # Node spacing smooths the path, but direction and rough size survive.
    assert path[0]["cumulative_bp"] < -5
    assert path[-1]["cumulative_bp"] < path[0]["cumulative_bp"]
    assert -90 < path[-1]["cumulative_bp"] < -40


def test_fed_funds_futures_meeting_math():
    # October: meeting on the 28th (too late in month) -> uses November average.
    # December: meeting on the 9th: avg = (9/31)*r_pre + (22/31)*r_post.
    effr = 3.60
    r_post = 3.35
    dec_avg = (9 * r_post + 22 * 3.10) / 31   # 25bp cut in Oct, another in Dec to 3.10
    futures = {(2026, 10): 100 - 3.58, (2026, 11): 100 - r_post, (2026, 12): 100 - dec_avg,
               (2027, 1): 100 - 3.10}
    path = path_from_fed_funds_futures(TODAY, MEETINGS, effr, futures)
    assert path[0]["date"] == "2026-10-28"
    assert path[0]["rate"] == pytest.approx(r_post)
    assert path[1]["rate"] == pytest.approx(3.10)
    assert path[1]["change_bp"] == pytest.approx(-25.0)


def test_summary_fields():
    path = [{"date": "2026-10-28", "rate": 3.4, "change_bp": -20.0, "cumulative_bp": -20.0},
            {"date": "2026-12-09", "rate": 3.2, "change_bp": -20.0, "cumulative_bp": -40.0},
            {"date": "2027-06-09", "rate": 3.1, "change_bp": -10.0, "cumulative_bp": -50.0}]
    s = summarise_path(path, TODAY, 3.75)
    assert s["next_move"] == "cut" and s["next_prob_pct"] == 80
    assert s["priced_3m_bp"] == -40.0
    assert s["terminal_rate"] == pytest.approx(3.25)

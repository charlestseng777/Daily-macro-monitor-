import numpy as np
import pandas as pd
import pytest

from macrodash.analytics.series import (compute_stats, difference_bp, move, percentile_rank, rolling_zscore,
                                        slice_range)


def _s(values, start="2024-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_move_units():
    assert move(4.10, 4.00, "yield") == pytest.approx(10.0)
    assert move(110, 100, "price") == pytest.approx(10.0)
    assert move(25, 20, "vol") == pytest.approx(5.0)
    assert move(55, 50, "bp") == pytest.approx(5.0)


def test_percentile_rank_bounds():
    w = pd.Series(range(100), dtype=float)
    assert percentile_rank(w, 99) == 100.0
    assert percentile_rank(w, -1) == 0.0
    assert percentile_rank(w, 49) == 50.0


def test_compute_stats_yield():
    s = _s(np.linspace(3.0, 4.0, 300))
    st = compute_stats(s, "yield")
    assert st.last == pytest.approx(4.0)
    step = 1.0 / 299 * 100
    assert st.d1 == pytest.approx(step, abs=0.01)
    assert st.pct_1y == 100
    assert st.w1 == pytest.approx(5 * step, abs=0.05)
    assert len(st.spark) <= 64


def test_z_score_excludes_today():
    rng = np.random.default_rng(0)
    vals = 4 + np.cumsum(rng.normal(0, 0.03, 100))
    vals[-1] = vals[-2] + 0.30          # 30bp jump on ~3bp daily vol
    st = compute_stats(_s(vals), "yield")
    assert st.z_d1 > 5


def test_difference_and_ranges():
    a, b = _s([4.0, 4.1, 4.2]), _s([3.0, 3.0, 3.1])
    assert list(difference_bp(a, b).round(6)) == [100.0, 110.0, 110.0]
    long = _s(np.arange(600.0))
    assert len(slice_range(long, "1M")) < 30
    assert slice_range(long, "YTD").index[0].month == 1
    assert len(slice_range(long, "MAX")) == 600


def test_rolling_zscore_finite():
    z = rolling_zscore(_s(np.sin(np.arange(400) / 10)), 60)
    assert np.isfinite(z.dropna()).all()

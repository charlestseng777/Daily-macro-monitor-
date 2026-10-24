import pytest

from macrodash.analytics.curves import classify


@pytest.mark.parametrize("front,back,expected", [
    (2, 8, "bear_steepener"),
    (-8, -2, "bull_steepener"),
    (8, 2, "bear_flattener"),
    (-2, -8, "bull_flattener"),
    (-3, 3, "twist_steepener"),
    (3, -3, "twist_flattener"),
    (5, 5.2, "parallel_up"),
    (-5, -5.2, "parallel_down"),
    (0.1, -0.2, "unchanged"),
    (None, 3, "unchanged"),
])
def test_classify(front, back, expected):
    assert classify(front, back) == expected

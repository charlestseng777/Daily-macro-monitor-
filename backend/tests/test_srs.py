import datetime as dt

from macrodash.srs import MIN_EASE, review

TODAY = dt.date(2026, 10, 23)


def test_intervals_grow():
    card = {"ease": 2.5, "reps": 0, "interval_days": 0, "lapses": 0}
    seen = []
    for _ in range(4):
        card = {**card, **review(card, 4, TODAY)}
        seen.append(card["interval_days"])
    assert seen[0] == 1 and seen[1] == 6 and seen[2] > seen[1] and seen[3] > seen[2]


def test_lapse_resets():
    card = {"ease": 2.5, "reps": 3, "interval_days": 15, "lapses": 0}
    out = review(card, 0, TODAY)
    assert out["interval_days"] == 1 and out["reps"] == 0 and out["lapses"] == 1
    assert out["ease"] < 2.5 and out["ease"] >= MIN_EASE
    assert out["due"] == TODAY + dt.timedelta(days=1)

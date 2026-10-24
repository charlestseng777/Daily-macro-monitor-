"""
SM-2 spaced repetition (the SuperMemo-2 algorithm Anki is based on).

Grades: 0 = again (forgot), 3 = hard, 4 = good, 5 = easy.
A failed card (grade < 3) restarts at a one-day interval and loses ease;
successful reviews grow the interval by the card's ease factor.
"""

from __future__ import annotations

import datetime as dt

MIN_EASE = 1.3


def review(card: dict, grade: int, today: dt.date) -> dict:
    grade = max(0, min(5, int(grade)))
    ease = float(card.get("ease", 2.5))
    reps = int(card.get("reps", 0))
    interval = int(card.get("interval_days", 0))
    lapses = int(card.get("lapses", 0))

    if grade < 3:
        reps, interval, lapses = 0, 1, lapses + 1
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 3 if grade == 3 else 6
        else:
            interval = max(1, round(interval * ease * (0.85 if grade == 3 else 1.0) * (1.3 if grade == 5 else 1.0)))
    ease = max(MIN_EASE, ease + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)))
    return {"ease": round(ease, 3), "reps": reps, "interval_days": interval, "lapses": lapses,
            "due": today + dt.timedelta(days=interval), "last_reviewed": today}

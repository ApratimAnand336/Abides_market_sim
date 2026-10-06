"""Predefined news headlines (moved from dashboard.py's PREDEFINED_NEWS)."""

PRESETS = [
    ("Company announces record quarterly earnings", 0.90),
    ("CEO unexpectedly resigns amid internal disputes", -0.85),
    ("FDA approves company's flagship drug", 0.92),
    ("Company faces major data breach affecting millions", -0.88),
    ("Strategic merger announced with industry leader", 0.75),
    ("Revenue misses analyst expectations by 15%", -0.78),
    ("Company wins $2B government contract", 0.82),
    ("Product recall issued due to safety concerns", -0.70),
    ("Analysts upgrade stock to strong buy", 0.65),
    ("Regulatory investigation launched into company practices", -0.72),
]


def presets():
    return [{"headline": h, "sentiment": s} for h, s in PRESETS]

"""Corrected gap half-life of the stored v1.3 lab runs (spec v1.4 N1).

No new simulations: reads runs/_lab/<config>/<seed>/series.npz (mid_1s and
val_1s, dollars, 1 s grid) of C-DEF and C-V20 and prints a markdown table
with the v1.3 estimator (de-meaned), the uncorrected reading h_read, the
correction of the median h_read and the median of per-seed h_corrected.

    python scripts/halflife_v13_recompute.py > runs/_logs/hl_v13.md
"""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api import lab, realism as R  # noqa: E402
from api.stats import gap_half_life  # noqa: E402

LAB_DIR = REPO / "runs" / "_lab"


def q(x, p):
    x = [v for v in x if v is not None]
    return float(np.percentile(x, p)) if x else None


def fmt(x, d=1):
    return "—" if x is None else f"{x:.{d}f}"


def main() -> int:
    rows = []
    for cid in ("C-DEF", "C-V20"):
        old, read, corr, above, means, engines = [], [], [], 0, [], set()
        for seed in lab.SEEDS:
            p = LAB_DIR / cid / str(seed) / "series.npz"
            m = LAB_DIR / cid / str(seed) / "metrics.json"
            if not p.exists():
                continue
            engines.add(json.loads(m.read_text(encoding="utf-8"))["engine_version"])
            with np.load(p) as z:
                gap = z["mid_1s"].astype(float) - z["val_1s"].astype(float)
            old.append(gap_half_life(gap, lags_s=R.LAB_GAP_LAGS)["half_life_min"])
            c = R.gap_half_life_corrected(gap)
            read.append(c["h_read"])
            means.append(c["gap_mean"])
            if c["above_table"]:
                above += 1
                corr.append(float("inf"))
            else:
                corr.append(c["h_corrected"])
        med_read = q(read, 50)
        cm = R.correct_half_life(med_read)
        rows.append((cid, len(read), old, read, corr, above, means, cm, sorted(engines)))
    print(f"Corrected gap half-life of the stored v1.3 runs (no new simulations), {date.today().isoformat()}.")
    print("Seeds: api.lab.SEEDS (20). Values in minutes: median [p10–p90] over seeds.\n")
    print("| config | seeds | v1.3 estimator (biased for slow mispricing) | h_read (no de-meaning) | "
          "correction of median h_read | median of per-seed h_corrected | range of the median reading | "
          "gap mean ($) | engine |")
    print("|---|---|---|---|---|---|---|---|---|")
    for cid, n, old, read, corr, above, means, cm, eng in rows:
        fin = [c for c in corr if np.isfinite(c)]
        medc = float(np.median(corr)) if corr else None
        rng = cm["h_range"]
        print(f"| {cid} | {n} | {fmt(q(old, 50))} [{fmt(q(old, 10))}–{fmt(q(old, 90))}] | "
              f"{fmt(q(read, 50))} [{fmt(q(read, 10))}–{fmt(q(read, 90))}] | {cm['text']} | "
              f"{'>240' if medc is not None and not np.isfinite(medc) else fmt(medc)} "
              f"({above} seeds >240; finite p10–p90 {fmt(q(fin, 10))}–{fmt(q(fin, 90))}) | "
              f"{'—' if not rng else f'{rng[0]:g}–{rng[1]:g}'} | {fmt(q(means, 50), 3)} | {', '.join(eng)} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())

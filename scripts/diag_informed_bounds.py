"""Diagnostic: why does the lab flag `informed_bounds` fail in value-jump runs?

Re-runs one lab config/seed and, for every fill of an informed fundamentalist
that leaves its position outside [w_min, w_max] x wealth at the fill price
(one-share tolerance, the flag's rule), records whether that fill INCREASED the
exposure beyond the bound (a budget-rule breach) or happened while the position
was already outside because the price moved (mark-to-market drift; the §4.5
rule limits new orders, not price moves). Prints a compact table.

    python scripts/diag_informed_bounds.py P0-S2 13
"""

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def main(cid: str, seed: int) -> None:
    from abides_core import abides
    from abides_markets.agents.fundamental import INFORMED_W_MAX, INFORMED_W_MIN
    from api import lab

    cfg = lab.lab_config(cid, seed)
    t0 = cfg["_mkt_open_ns"] + lab.T0_S * 10**9
    rows = []
    for a in cfg["agents"]:
        if type(a).__name__ != "FundamentalistAgent" or a.mode != "informed":
            continue
        orig = a.order_executed

        def wrapped(order, _a=a, _orig=orig):
            n0 = _a.holdings.get("ABM", 0)
            _orig(order)
            p = float(order.fill_price)
            n = _a.holdings.get("ABM", 0)
            W = _a.holdings["CASH"] + n * p
            hi, lo = INFORMED_W_MAX * W + p, INFORMED_W_MIN * W - p
            if n * p > hi + 1e-6 or n * p < lo - 1e-6:
                increased = abs(n) > abs(n0)
                rows.append((_a.id, int(_a.current_time), n0, n, round(n * p / W, 4) if W else None, increased,
                             order.side.is_bid()))

        a.order_executed = wrapped
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        abides.run(cfg)
    finally:
        os.chdir(cwd)
    inc = [r for r in rows if r[5]]
    after = [r for r in rows if r[1] >= t0]
    print(f"{cid} seed {seed}: {len(rows)} fills outside the bounds; {len(inc)} of them increased |position|; "
          f"{len(after)} after the event time t0")
    if rows:
        ratios = [r[4] for r in rows if r[4] is not None]
        print(f"  agents {len({r[0] for r in rows})}; position/wealth at those fills: min {min(ratios)}, max {max(ratios)}")
    for r in inc[:8]:
        print("  INCREASE:", r)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))

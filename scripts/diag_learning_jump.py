"""Diagnostic (spec v1.4.1 N4c): what does learning from prices do after a jump?

Runs one design's S2 config (+2% value jump at 11:00) on one seed to 11:30 and
classifies every market update with g > 1 (learning active) of the informed
fundamentalists in [t0, t0 + 30 min]:
  toward_value  the belief moved toward the post-jump value
  toward_stale  the belief moved away from the post-jump value (toward a price
                that has not caught up yet)
Prints a compact table; no payloads.

    python scripts/diag_learning_jump.py D-60fl2M-mod 42
"""

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api import lab  # noqa: E402


def main(design: str, seed: int) -> None:
    from abides_core import abides
    from abides_markets.configs.rmsc04_ekf import build_config
    from api.jobs import run_config_kwargs

    cid = design + "-S2"
    p = lab.run_params(cid, seed).model_copy(update={"end_time": "11:30:00"})
    kw = run_config_kwargs(p)
    kw.update(lab.CONFIGS[cid]["extra"])
    cfg = build_config(**kw)
    open_ns = cfg["_mkt_open_ns"]
    t0 = open_ns + lab.T0_S * 10**9
    oracle = cfg["custom_properties"]["oracle"]
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        es = abides.run(cfg)
    finally:
        os.chdir(cwd)
    import numpy as np

    o_t, o_v = oracle.path("ABM")
    v_new = float(o_v[np.searchsorted(o_t, t0 + 60 * 10**9)])
    rows = {"toward_value": 0, "toward_stale": 0, "learn_events": 0, "updates": 0, "research": 0}
    moves = {"toward_value": [], "toward_stale": []}
    for i in cfg["_ekf_agent_ids"]:
        a = es["agents"][i]
        prev = None
        for t, typ, ev in a.log:
            if typ == "RESEARCH_READING":
                prev = ev["x_hat_after"]
                if t >= t0:
                    rows["research"] += 1
            elif typ == "EKF_UPDATE":
                if t0 <= t <= t0 + 1800 * 10**9:
                    rows["updates"] += 1
                    if ev.get("g", 1.0) > 1.0 and prev is not None:
                        rows["learn_events"] += 1
                        d_before, d_after = abs(prev - v_new), abs(ev["x_hat"] - v_new)
                        k = "toward_value" if d_after < d_before else "toward_stale"
                        rows[k] += 1
                        moves[k].append(abs(ev["x_hat"] - prev) / 100.0)
                prev = ev["x_hat"]
    print(f"{design} seed {seed}: post-jump value ${v_new / 100:.2f}; window 11:00-11:30")
    for k, v in rows.items():
        print(f"  {k:14s} {v}")
    for k, m in moves.items():
        if m:
            print(f"  {k:14s} median belief move ${np.median(m):.2f}, total ${np.sum(m):.0f}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 42)

"""Fingerprint one lab run (spec v1.4.2 Part 1, T-S2 / T-S3).

Builds api.lab.lab_config(config_id, seed) (full day), runs it in this process,
and prints one JSON line: the I1/I8 fingerprint (sha256 of every EXEC and of the
final holdings, n_execs) and the wall time of abides.run. Run it in a fresh
process with PYTHONHASHSEED=0, from any working directory (logs go to a temp dir).

    python scripts/fingerprint_run.py D-60fl2M-S2 42
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))


def main(config_id: str, seed: int) -> dict:
    from abides_core import abides

    import realism_lab as RL
    from api import lab

    cfg = lab.lab_config(config_id, seed)
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        t0 = time.time()
        es = abides.run(cfg)
        wall = time.time() - t0
    finally:
        os.chdir(cwd)
    out = RL._fingerprint(es)
    out["wall_time_s"] = round(wall, 2)
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], int(sys.argv[2]))))

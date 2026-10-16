"""Profile one full lab day with cProfile (spec v1.5 A1.1).

    python scripts/profile_day.py P0-C 42 runs/_logs/profile_p0.pstats

Builds api.lab.lab_config(config_id, seed), runs abides.run under cProfile in this
process (logs to a temp dir) and writes the stats file, then prints the top 15 functions
by own time and by cumulative time, plus the run fingerprint (I1/I8 hashes).
"""

import cProfile
import io
import json
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))


def main(config_id: str, seed: int, out_path: str) -> None:
    from abides_core import abides

    import realism_lab as RL
    from api import lab

    cfg = lab.lab_config(config_id, seed)
    out_path = os.path.abspath(out_path)
    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    prof = cProfile.Profile()
    try:
        t0 = time.time()
        prof.enable()
        es = abides.run(cfg)
        prof.disable()
        wall = time.time() - t0
    finally:
        os.chdir(cwd)
    prof.dump_stats(out_path)
    fp = RL._fingerprint(es)
    fp["wall_time_s_profiled"] = round(wall, 2)
    print(json.dumps(fp))
    for key in ("tottime", "cumulative"):
        s = io.StringIO()
        pstats.Stats(out_path, stream=s).sort_stats(key).print_stats(15)
        print(f"=== top 15 by {key} ===")
        print("\n".join(s.getvalue().splitlines()[-22:]))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])

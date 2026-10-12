"""Realism-lab regression set as a pytest (spec v1.3 §7.6), marked slow.

Re-runs seeds 42, 7, 1 of C-DEF, S2 and IMP-1 (9 full days, about 1.5 min with
4 workers) and checks (a) the seed-42 C-DEF hash against
docs/v1.3/lab/reference_hashes.json and (b) the 3-seed medians against the
stored 20-seed [p10, p90]."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.slow
def test_lab_regression_set():
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "realism_lab.py"), "--campaign", "regression", "--workers", "4"],
        cwd=REPO, capture_output=True, text=True, timeout=1800,
    )
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-2000:]
    assert "REGRESSION PASSED" in out.stdout

"""Invariants (FinVerse spec v1.2, Part 5): properties every simulation must keep.

Each test runs a short real simulation (seed 42, 09:30-10:30, 5 fundamentalists,
4 momentum agents, default background population) through
api.jobs.build_run_config, the dashboard path.

I1 determinism            two fresh processes -> identical executions and holdings
I2 oracle stability       = T-O1 (test_oracle.py)
I3 conservation           total shares and total cash unchanged by trading
I4 long-only safety       our price-only / momentum agents never hold < 0 shares or < 0 cash;
                          informed fundamentalists: the §4.5 bounds (= T-N5)
I5 book sanity            bid < ask in every two-sided L1 snapshot; every fill price > 0
I6 no value agents        = T-M6 (test_market_maker.py)
I7 market-maker liveness  = T-M7 (test_market_maker.py)
I8 no drift               (spec v1.3 Part 2; re-recorded in v1.4 N6 and v1.5 A9) the invariant market (v1.5 default, 30 informed) is unchanged; I8-legacy-v14: the v1.4 market (P0, 30 informed); I8-legacy: the v1.3 test market reproduces v1.2 (aa5f606)
                          bit for bit
I9 budget respected       (spec v1.4 §10.4) = T-N13 (test_budget.py): with
                          abides_budget {"L": 2}, every Noise/Value/ABIDES
                          Momentum fill keeps |n| p <= 2 W_p (one-order tolerance)
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .sim_helpers import INVARIANT_PARAMS, LEGACY_PARAMS, V14_PARAMS, history, params
from .test_market_maker import (  # noqa: F401  (collected here as I6 / I7)
    default_market,
    empty_book_market,
    no_value_market,
    test_empty_book_cold_start as test_i6_runs_without_value_agents,
    test_liveness_default as test_i7_market_maker_liveness,
)
from .test_oracle import (  # noqa: F401  (collected here as I2)
    test_same_seed_different_market_same_path as test_i2_oracle_stability,
)

REPO = Path(__file__).resolve().parents[2]
OURS = ("FundamentalistAgent", "MomentumEKFAgent")

# ── I1 determinism ──────────────────────────────────────────────────────────

_FINGERPRINT = r"""
import hashlib, json, os, sys
sys.path.insert(0, sys.argv[1])
from api.jobs import build_run_config
from api.schema import RunParams
from abides_core import abides
p = RunParams(**json.loads(sys.argv[2])).model_copy(update={"end_time": "10:30:00"})
cfg = build_run_config(p)
es = abides.run(cfg)
h = es["agents"][0].order_books["ABM"].history
execs = [[x["time"], x["price"], x["quantity"], x["agent_id"], x["oppos_agent_id"]] for x in h if x["type"] == "EXEC"]
hold = [[a.id, sorted((k, int(v)) for k, v in a.holdings.items())] for a in es["agents"] if hasattr(a, "holdings")]
print(json.dumps({
    "execs": hashlib.sha256(json.dumps(execs).encode()).hexdigest(),
    "holdings": hashlib.sha256(json.dumps(hold).encode()).hexdigest(),
    "n_execs": len(execs),
}))
"""


def _fingerprint(tmp_path, hash_seed: str, base: dict = INVARIANT_PARAMS) -> dict:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONWARNINGS": "ignore"}
    out = subprocess.run(
        [sys.executable, "-c", _FINGERPRINT, str(REPO), json.dumps(base)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_i1_determinism_across_processes(tmp_path):
    """Two fresh processes, deliberately with different PYTHONHASHSEEDs (so any
    dependence on set/dict iteration order of strings would show), give the
    same sha256 of every execution and of every agent's final holdings."""
    a = _fingerprint(tmp_path, "1")
    b = _fingerprint(tmp_path, "2")
    assert a["n_execs"] > 0
    assert a == b


# ── I8 no drift (spec v1.3 Part 2.2) ───────────────────────────────────────

# I8-legacy: recorded ONCE on 2026-10-12 from a checkout of v1.2 (aa5f606)
# with PYTHONHASHSEED=0, using the I1 fingerprint above on the v1.3 test
# market (LEGACY_PARAMS: seed 42, 09:30-10:30, 5 price-only fundamentalists +
# 4 momentum, 97 value agents, no budget). It must hold forever (spec v1.4
# §6.1): the legacy market stays reproducible by explicit parameters.
I8_LEGACY_EXPECTED = {
    "execs": "5cfff6b231fc079fe3a3fb2c3bad354564d2d5dbbfc73b3b5721cbe0033bc1f5",
    "holdings": "34ec92b2a3763b3b1f32d455a042f2865e0b2f20a98fcdad7b2ceae9605032db",
    "n_execs": 2448,
}
# I8-legacy-v14: the I8 hash recorded in N6 (spec v1.4 §10.4, DECISIONS.md 2026-10-14) on
# the v1.4 invariant market (V14_PARAMS: P0 with 30 informed fundamentalists, seed 42,
# 09:30-10:30, PYTHONHASHSEED=0). Kept in v1.5 A9.3: the v1.4 market stays reproducible.
I8_LEGACY_V14_EXPECTED = {
    "execs": "bf455dc70f7c4746e52456d8df86972546f20f805e5dcf035d318fffe1751579",
    "holdings": "39be7b70119451afa9b80642c89cc6480682d9504ca2650f675ca1e2ef360b90",
    "n_execs": 1925,
}
# I8: re-recorded in A9 (spec v1.5 A9.3, DECISIONS.md A9) on the new invariant market
# (INVARIANT_PARAMS: the v1.5 default market with 30 informed fundamentalists, seed 42,
# 09:30-10:30) with PYTHONHASHSEED=0. Re-record only when an approved spec says so.
I8_EXPECTED = {
    "execs": "2d71911b7b3524c4b37d5e66cc44a1516401ab2e68291dc6bfaa9182d11a6bf3",
    "holdings": "b6cf93c5b05180311eac084979da965a401d1bd7e23bc9cd64f1e5e91edf2bba",
    "n_execs": 5053,
}


def test_i8_no_drift(tmp_path):
    """With every new parameter at its default the market is bit-identical to
    v1.2: same sha256 of every EXEC and of every agent's final holdings."""
    assert _fingerprint(tmp_path, "0") == I8_EXPECTED


def test_i8_legacy_v14_market_unchanged(tmp_path):
    """spec v1.5 A9.3: the v1.4 parameters (V14_PARAMS) reproduce the v1.4 I8 hash exactly."""
    assert _fingerprint(tmp_path, "0", V14_PARAMS) == I8_LEGACY_V14_EXPECTED


def test_i8_legacy_v13_market_unchanged(tmp_path):
    """spec v1.4 §10.4: the legacy parameters reproduce the v1.3 hash exactly."""
    assert _fingerprint(tmp_path, "0", LEGACY_PARAMS) == I8_LEGACY_EXPECTED


# ── shared 1-hour market for I3-I5 ─────────────────────────────────────────


@pytest.fixture(scope="module")
def market(tmp_path_factory):
    from abides_core import abides
    from api.jobs import build_run_config

    config = build_run_config(params())
    before = {
        a.id: (int(a.holdings.get("CASH", 0)), int(a.holdings.get("ABM", 0)))
        for a in config["agents"]
        if hasattr(a, "holdings")
    }
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("logs"))
    try:
        end_state = abides.run(config)
    finally:
        os.chdir(cwd)
    return config, end_state, before


def test_i3_conservation(market):
    """Trading moves cash and shares between agents but never creates or
    destroys them (no fees exist; tolerance 0 cents)."""
    _, end_state, before = market
    after = {
        a.id: (int(a.holdings.get("CASH", 0)), int(a.holdings.get("ABM", 0)))
        for a in end_state["agents"]
        if hasattr(a, "holdings")
    }
    assert set(after) == set(before)
    assert sum(c for c, _ in after.values()) == sum(c for c, _ in before.values())
    assert sum(s for _, s in after.values()) == sum(s for _, s in before.values())
    assert any(after[i] != before[i] for i in before)  # trading did happen


def test_i4_long_only_safety(market):
    """Our price-only fundamentalists and momentum EKF agents never hold
    negative shares or negative cash. Spec v1.4 §10.4 splits I4: informed
    fundamentalists may short and borrow within [w_min, w_max] x wealth,
    checked at every fill by T-N5 (test_fundamental_informed.py)."""
    _, end_state, _ = market
    checked = 0
    for a in end_state["agents"]:
        if type(a).__name__ not in OURS or getattr(a, "mode", "price_only") == "informed":
            continue
        for _, typ, ev in a.log:
            if typ == "HOLDINGS_UPDATED":
                assert ev.get("ABM", 0) >= 0, (a.name, ev)
                assert ev.get("CASH", 0) >= 0, (a.name, ev)
                checked += 1
    assert checked > 9  # at least the start point of each of the 9 agents


def test_i5_book_sanity(market):
    """In every L1 snapshot with both sides, bid < ask; every fill price > 0."""
    _, end_state, _ = market
    ob = end_state["agents"][0].order_books["ABM"]
    two_sided = 0
    for row in ob.book_log2:
        if len(row["bids"]) and len(row["asks"]):
            assert row["bids"][0][0] < row["asks"][0][0], row["QuoteTime"]
            two_sided += 1
    assert two_sided > 100
    execs = [x for x in history(end_state) if x["type"] == "EXEC"]
    assert execs and all(x["price"] is not None and x["price"] > 0 for x in execs)


# ── I9 budget respected (spec v1.4 §10.4) = T-N13 ────────────────────────
# Imported at the end: test_budget imports I8_EXPECTED from this module.
from .test_budget import (  # noqa: E402,F401
    budget_market,
    test_n13_fills_respect_the_gross_limit as test_i9_budget_respected,
)

# ── I4 (informed part, spec v1.4 §10.4) = T-N5 ───────────────────────────
from .test_fundamental_informed import (  # noqa: E402,F401
    informed_market,
    test_n5_budget_holds_at_every_fill as test_i4_informed_within_bounds,
)

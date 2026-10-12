"""Invariants (FinVerse spec v1.2, Part 5): properties every simulation must keep.

Each test runs a short real simulation (seed 42, 09:30-10:30, 5 fundamentalists,
4 momentum agents, default background population) through
api.jobs.build_run_config, the dashboard path.

I1 determinism            two fresh processes -> identical executions and holdings
I2 oracle stability       = T-O1 (test_oracle.py)
I3 conservation           total shares and total cash unchanged by trading
I4 long-only safety       our agents never hold < 0 shares or < 0 cash
I5 book sanity            bid < ask in every two-sided L1 snapshot; every fill price > 0
I6 no value agents        = T-M6 (test_market_maker.py)
I7 market-maker liveness  = T-M7 (test_market_maker.py)
I8 no drift               (spec v1.3 Part 2) default parameters reproduce v1.2 (aa5f606)
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

from .sim_helpers import history, params
from .test_market_maker import (  # noqa: F401  (collected here as I6 / I7)
    default_market,
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
p = RunParams(seed=42, end_time="10:00:00", num_fund=5, num_mom=4).model_copy(update={"end_time": "10:30:00"})
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


def _fingerprint(tmp_path, hash_seed: str) -> dict:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONWARNINGS": "ignore"}
    out = subprocess.run(
        [sys.executable, "-c", _FINGERPRINT, str(REPO)],
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

# Recorded ONCE on 2026-10-12 from a checkout of v1.2 (aa5f606) with
# PYTHONHASHSEED=0, using the I1 fingerprint above (seed 42, 09:30-10:30,
# 5 fundamentalists + 4 momentum, default RunParams). Re-record only when an
# approved spec changes behaviour and its DECISIONS.md entry says so
# (see docs/engine/TESTING.md, "I8").
I8_EXPECTED = {
    "execs": "5cfff6b231fc079fe3a3fb2c3bad354564d2d5dbbfc73b3b5721cbe0033bc1f5",
    "holdings": "34ec92b2a3763b3b1f32d455a042f2865e0b2f20a98fcdad7b2ceae9605032db",
    "n_execs": 2448,
}


def test_i8_no_drift(tmp_path):
    """With every new parameter at its default the market is bit-identical to
    v1.2: same sha256 of every EXEC and of every agent's final holdings."""
    assert _fingerprint(tmp_path, "0") == I8_EXPECTED


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
    """Our agents never hold negative shares or negative cash."""
    _, end_state, _ = market
    checked = 0
    for a in end_state["agents"]:
        if type(a).__name__ not in OURS:
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

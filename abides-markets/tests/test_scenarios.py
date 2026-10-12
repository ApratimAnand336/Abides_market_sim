"""Scenario tooling of the realism lab (FinVerse spec v1.3 Part 6, tests T-L1 … T-L9).

Every switch must be inert at its default (I8) and must not consume the global
numpy stream, so a scenario and its baseline share the true value, every agent
parameter and every random stream until the trigger."""

import hashlib
import json
import os
import subprocess
import sys
from math import exp
from pathlib import Path

import numpy as np
import pytest

from abides_core.utils import str_to_ns
from abides_markets.oracles.pregenerated_oracle import PregeneratedOracle, generate_path

from .test_invariants import I8_EXPECTED

REPO = Path(__file__).resolve().parents[2]
DATE = int(np.datetime64("2021-02-05", "ns").astype(np.int64))
OPEN, CLOSE = DATE + str_to_ns("09:30:00"), DATE + str_to_ns("16:00:00")
T11, T12 = DATE + str_to_ns("11:00:00"), DATE + str_to_ns("12:00:00")
TIMES = OPEN + 1_000_000_000 * np.arange(23_401, dtype=np.int64)
KAPPA = 1.67e-16


def _params(seed, **extra):
    p = {
        "r_bar": 100_000, "kappa": KAPPA, "sigma_s": 0, "fund_vol": 5e-5,
        "megashock_lambda_a": 2.77778e-18, "megashock_mean": 1000, "megashock_var": 50_000,
        "path_source": "synthetic_ou", "random_state": np.random.RandomState(seed),
    }
    p.update(extra)
    return p


def _path(seed, **extra):
    p = _params(seed, **extra)
    return generate_path(p, TIMES, p["random_state"])


# ── T-L1 ───────────────────────────────────────────────────────────────────
def test_l1_scenario_without_events_is_synthetic_ou():
    for seed in range(20):
        a = _path(seed)
        b = _path(seed, path_source="scenario", events=[])
        assert np.array_equal(a, b), seed


# ── T-L2 ───────────────────────────────────────────────────────────────────
def test_l2_jump_adds_a_decaying_step():
    t_jump = T11 + 500_000_000  # between grid points: applied at 11:00:01
    base = _path(3)
    jump = _path(3, path_source="scenario", events=[{"type": "jump", "t_ns": t_jump, "cents": 2000.0}])
    k0 = int(np.searchsorted(TIMES, t_jump, side="left"))
    assert TIMES[k0] == T11 + 1_000_000_000
    d = jump - base
    assert np.all(d[:k0] == 0.0)
    a = exp(-KAPPA * 1e9)
    expected = 2000.0 * a ** np.arange(len(d) - k0)
    assert np.max(np.abs(d[k0:] - expected)) < 1e-6
    # permanent in practice: a^18000 = exp(-0.003), i.e. 0.3% decay over the
    # 5 hours to 16:00 ($20.00 -> $19.94). Spec §6.1 writes "0.0003%", a slip
    # by a factor of 1000 (DECISIONS.md, 2026-10-12, L3).
    assert abs(d[-1] - 2000.0 * exp(-KAPPA * 1e9 * (len(d) - 1 - k0))) < 1e-6 and d[-1] > 1993.0

    oracle = PregeneratedOracle(OPEN, CLOSE, {"ABM": _params(3, path_source="scenario",
                                                      events=[{"type": "jump", "t_ns": t_jump, "cents": 2000.0}])})
    (ev,) = oracle.events["ABM"]
    assert ev["type"] == "jump" and ev["t_ns"] == t_jump and ev["t_grid_ns"] == T11 + 1_000_000_000
    assert ev["cents"] == 2000.0


# ── T-L3 ───────────────────────────────────────────────────────────────────
def test_l3_volatility_event():
    ev = [{"type": "vol", "t0_ns": T11, "t1_ns": T12, "mult": 3.0}]
    k0 = int(np.searchsorted(TIMES, T11, side="left"))
    k1 = int(np.searchsorted(TIMES, T12, side="left"))
    inside, outside = [], []
    for seed in range(200):
        base = _path(seed)
        burst = _path(seed, path_source="scenario", events=ev)
        assert np.array_equal(burst[:k0], base[:k0])
        inc = np.diff(burst)  # inc[k - 1] = x_k - x_{k-1}, scaled for k0 <= k < k1
        inside.append(inc[k0 - 1:k1 - 1])
        outside.append(np.concatenate([inc[:k0 - 1], inc[k1 - 1:]]))
    ratio = np.std(np.concatenate(inside)) / np.std(np.concatenate(outside))
    assert abs(ratio / 3.0 - 1.0) <= 0.05


# ── T-L4 ───────────────────────────────────────────────────────────────────
def _lab_kwargs(**extra):
    from api.jobs import run_config_kwargs
    from api.schema import RunParams

    p = RunParams(seed=42, end_time="10:00:00", num_fund=5, num_mom=4).model_copy(update={"end_time": "10:30:00"})
    kw = run_config_kwargs(p)
    kw.update(extra)
    return kw


def _agent_fingerprint(config):
    """Every agent's class, hyperparameters and RNG state (no simulation)."""
    out = []
    for a in config["agents"]:
        st = a.random_state.get_state()
        hp = {k: v for k, v in sorted(vars(a).items())
              if isinstance(v, (int, float, str)) and not k.startswith("_") and k not in ("kernel",)}
        out.append((type(a).__name__, a.id, hashlib.sha256(st[1].tobytes()).hexdigest(), st[2], json.dumps(hp, default=str)))
    return out


def test_l4_jump_config_keeps_path_and_agents():
    from abides_markets.configs.rmsc04_ekf import build_config

    base = build_config(**_lab_kwargs())
    assert base["custom_properties"]["oracle"].symbols["ABM"]["path_source"] == "synthetic_ou"
    jump = build_config(**_lab_kwargs(oracle_events=[{"type": "jump", "at": "00:30:00", "pct": 2.0}]))
    ob, oj = base["custom_properties"]["oracle"], jump["custom_properties"]["oracle"]
    assert oj.symbols["ABM"]["path_source"] == "scenario"
    _, vb = ob.path("ABM")
    _, vj = oj.path("ABM")
    k0 = 1800  # 10:00:00 on the 1 s grid
    assert np.array_equal(vb[:k0], vj[:k0])
    assert abs((vj[k0] - vb[k0]) - 2000.0) < 1e-6  # +2% of r_bar
    assert oj.events["ABM"][0]["t_grid_ns"] == DATE + str_to_ns("10:00:00")
    assert _agent_fingerprint(base) == _agent_fingerprint(jump)


# ── explicit defaults keep the I8 hash (T-L4, T-L8, T-L9 "the I8 hash holds") ──

_EXPLICIT_DEFAULTS = r"""
import hashlib, json, sys
sys.path.insert(0, sys.argv[1])
from api.jobs import run_config_kwargs
from api.schema import RunParams
from abides_core import abides
from abides_markets.configs.rmsc04_ekf import build_config
p = RunParams(seed=42, end_time="10:00:00", num_fund=5, num_mom=4).model_copy(update={"end_time": "10:30:00"})
kw = run_config_kwargs(p)
kw.update(json.loads(sys.argv[2]))
es = abides.run(build_config(**kw))
h = es["agents"][0].order_books["ABM"].history
execs = [[x["time"], x["price"], x["quantity"], x["agent_id"], x["oppos_agent_id"]] for x in h if x["type"] == "EXEC"]
hold = [[a.id, sorted((k, int(v)) for k, v in a.holdings.items())] for a in es["agents"] if hasattr(a, "holdings") and type(a).__name__ != "ImpactProbeAgent"]
print(json.dumps({"execs": hashlib.sha256(json.dumps(execs).encode()).hexdigest(),
                  "holdings": hashlib.sha256(json.dumps(hold).encode()).hexdigest(), "n_execs": len(execs)}))
"""


def fingerprint(tmp_path, extra: dict) -> dict:
    """I1/I8 fingerprint of the 1-hour invariant market built with extra
    build_config keyword arguments, in a fresh process (PYTHONHASHSEED=0).
    Holdings exclude an impact probe, so a null probe can be compared."""
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONWARNINGS": "ignore"}
    out = subprocess.run(
        [sys.executable, "-c", _EXPLICIT_DEFAULTS, str(REPO), json.dumps(extra)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_l4_explicit_oracle_default_holds_i8(tmp_path):
    assert fingerprint(tmp_path, {"oracle_events": None}) == I8_EXPECTED

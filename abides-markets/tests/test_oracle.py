"""PregeneratedOracle (FinVerse spec v1.2, Part 3): tests T-O1 .. T-O4."""

import os
from math import sqrt

import numpy as np
import pytest

from abides_markets.oracles.pregenerated_oracle import (
    PATH_SOURCES,
    PregeneratedOracle,
    generate_path,
    generate_synthetic_ou,
)

OPEN = 1_612_517_400_000_000_000  # 2021-02-05 09:30 in ns
CLOSE = OPEN + int(6.5 * 3600 * 1e9)
PARAMS = {  # rmsc04_ekf defaults
    "r_bar": 100_000,
    "kappa": 1.67e-16,
    "fund_vol": 5e-5,
    "megashock_lambda_a": 2.77778e-18,
    "megashock_mean": 1000,
    "megashock_var": 50_000,
}


def make_oracle(seed=1, **over):
    params = {**PARAMS, **over, "random_state": np.random.RandomState(seed)}
    return PregeneratedOracle(OPEN, CLOSE, {"ABM": params}, grid_s=1.0)


# ── T-O1: same seed, different market -> identical path ─────────────────────


def run_and_get_path(params, tmp_dir):
    """Run a real simulation through the dashboard path; return the oracle's
    (times, values) and served f_log values after the run."""
    from abides_core import abides
    from api.jobs import build_run_config

    cwd = os.getcwd()
    os.chdir(tmp_dir)
    try:
        config = build_run_config(params)
        abides.run(config)
    finally:
        os.chdir(cwd)
    oracle = config["custom_properties"]["oracle"]
    t, v = oracle.path("ABM")
    return t, v, [e["FundamentalValue"] for e in oracle.f_log["ABM"]]


def one_hour(**kw):
    from api.schema import RunParams

    base = dict(seed=42, end_time="10:00:00", num_fund=5, num_mom=4)
    base.update(kw)
    # 10:30 is not a dashboard end time; model_copy skips that validation
    return RunParams(**base).model_copy(update={"end_time": "10:30:00"})


NEWS = [{"offset": "00:10:00", "headline": "Company announces record quarterly earnings", "sentiment": 0.9}]


def test_same_seed_different_market_same_path(tmp_path):
    """T-O1 (also invariant I2)."""
    a = run_and_get_path(one_hour(), tmp_path)
    b = run_and_get_path(one_hour(news=NEWS), tmp_path)
    c = run_and_get_path(one_hour(num_value=20, num_fund=0), tmp_path)
    for other in (b, c):
        assert np.array_equal(a[0], other[0])
        assert np.array_equal(a[1], other[1])  # exact float equality
        assert a[2] == other[2]


# ── T-O2: statistics match the OU theory ────────────────────────────────────


def test_increment_std_matches_theory():
    """T-O2: 200 seeds; std of 10 s / 60 s / 300 s changes within +/-10% of
    sqrt(fund_vol^2 * d) (kappa * d ~ 5e-5 at 300 s: mean reversion is
    negligible)."""
    times = OPEN + np.arange(23_401, dtype=np.int64) * 1_000_000_000
    diffs = {10: [], 60: [], 300: []}
    for seed in range(200):
        v = generate_synthetic_ou(PARAMS, times, np.random.RandomState(seed))
        for L in diffs:
            diffs[L].append(v[L::L] - v[:-L:L])
    for L, chunks in diffs.items():
        sd = np.concatenate(chunks).std()
        theory = sqrt(PARAMS["fund_vol"] ** 2 * L * 1e9)
        assert sd == pytest.approx(theory, rel=0.10), (L, sd, theory)


def test_path_is_pure_function_of_seed():
    a, b = make_oracle(7), make_oracle(7)
    assert np.array_equal(a.path("ABM")[1], b.path("ABM")[1])
    assert not np.array_equal(a.path("ABM")[1], make_oracle(8).path("ABM")[1])
    # no global RNG involved: reseeding np.random changes nothing
    np.random.seed(123)
    c = make_oracle(7)
    assert np.array_equal(a.path("ABM")[1], c.path("ABM")[1])


def test_megashocks_jump_the_state():
    """Shocks come from the dedicated RNG, at the first grid point >= their time."""
    o = make_oracle(3, megashock_lambda_a=1e-12, fund_vol=0.0)  # ~23 shocks, no diffusion
    t, v = o.path("ABM")
    jumps = np.flatnonzero(np.abs(np.diff(v)) > 1.0)
    assert len(jumps) > 5
    assert np.all(np.abs(np.diff(v)[jumps]) > 300)  # |N(1000, 50000)| is far from 0


def test_unknown_path_source():
    with pytest.raises(ValueError):
        generate_path({**PARAMS, "path_source": "nope"}, np.arange(3), np.random.RandomState(0))
    assert "synthetic_ou" in PATH_SOURCES


# ── T-O3: exact observations are the step function, clamped at the ends ────


def test_exact_observation_is_step_function():
    o = make_oracle(5)
    t, v = o.path("ABM")
    served = np.rint(v).astype(int)
    rng = np.random.RandomState(0)
    for q in rng.randint(OPEN, CLOSE, size=500, dtype=np.int64):
        k = (q - OPEN) // 1_000_000_000
        assert o.observe_price("ABM", int(q), rng, sigma_n=0) == served[k]
        assert o.value_at("ABM", int(q)) == v[k]
    # just before the next grid point still returns the earlier value (no look-ahead)
    assert o.observe_price("ABM", OPEN + 1_999_999_999, rng, sigma_n=0) == served[1]
    assert o.observe_price("ABM", OPEN - 10**12, rng, sigma_n=0) == served[0] == 100_000
    assert o.observe_price("ABM", CLOSE + 10**12, rng, sigma_n=0) == served[-1]
    assert o.get_daily_open_price("ABM", OPEN) == 100_000
    assert len(o.f_log["ABM"]) == len(t) and o.f_log["ABM"][-1]["FundamentalValue"] == served[-1]


# ── T-O4: observation noise uses the caller's RNG ───────────────────────────


def test_noise_from_caller_rng():
    o = make_oracle(5)
    before = o.path("ABM")[1]
    q = OPEN + 3600 * 10**9
    x1 = o.observe_price("ABM", q, np.random.RandomState(11), sigma_n=1000)
    x2 = o.observe_price("ABM", q, np.random.RandomState(11), sigma_n=1000)
    others = {o.observe_price("ABM", q, np.random.RandomState(s), sigma_n=1000) for s in range(12, 30)}
    assert x1 == x2
    assert len(others - {x1}) > 0
    assert np.array_equal(before, o.path("ABM")[1])

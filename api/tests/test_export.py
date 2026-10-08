"""Export/stats tests on a real 30-minute simulation (spec Section 4)."""

import json
import os

import numpy as np
import pytest

from api.downsample import change_points, lttb_indices
from api.export import build_payload
from api.jobs import build_run_config
from api.schema import RunParams, SimPayload
from api.stats import acf, returns_1m, spread_ticks

FULL_DAY_BUDGET_BYTES = 8_000_000
FULL_DAY_S = 6.5 * 3600

PARAMS = RunParams(
    seed=42,
    end_time="10:00:00",
    num_fund=3,
    num_mom=3,
    news=[
        {"offset": "00:05:00", "headline": "Company announces record quarterly earnings", "sentiment": 0.9},
        {"offset": "00:15:00", "headline": "CEO unexpectedly resigns amid internal disputes", "sentiment": -0.85},
        # inside the last 5 minutes: no 5m / 30m after-price exists
        {"offset": "00:27:00", "headline": "Analysts upgrade stock to strong buy", "sentiment": 0.65},
    ],
)


@pytest.fixture(scope="module")
def sim(tmp_path_factory):
    from abides_core import abides

    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("abides_logs"))  # kernel summary log lands here
    try:
        config = build_run_config(PARAMS)
        end_state = abides.run(config)
    finally:
        os.chdir(cwd)
    payload = build_payload(end_state, config, PARAMS, "test", "test", 1.0)
    return end_state, config, payload


def _columnar_series(node, path=""):
    """Yield (path, dict) for every dict whose values are all equal-length
    candidates: a dict holding a 't' list."""
    if isinstance(node, dict):
        if isinstance(node.get("t"), list):
            yield path, node
        for k, v in node.items():
            yield from _columnar_series(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _columnar_series(v, f"{path}[{i}]")


def test_payload_validates(sim):
    _, _, payload = sim
    SimPayload.model_validate(payload)
    json.dumps(payload, allow_nan=False)  # strict JSON: no NaN / inf


def test_trades_equal_exec_count(sim):
    end_state, _, payload = sim
    history = end_state["agents"][0].order_books["ABM"].history
    n_exec = sum(1 for h in history if h.get("type") == "EXEC")
    assert payload["market"]["totals"]["trades"] == n_exec
    assert payload["stats"]["trades"] == n_exec


def test_close_is_last_mid(sim):
    _, _, payload = sim
    assert payload["stats"]["close"] == pytest.approx(payload["market"]["quotes"]["mid"][-1], abs=1e-4)


def test_final_value_matches_mark_to_market(sim):
    end_state, _, payload = sim
    for agent in payload["agents"]["fundamental"] + payload["agents"]["momentum"]:
        a = end_state["agents"][agent["id"]]
        mtm = a.mark_to_market(a.holdings) / 100.0
        assert agent["final"]["value"] == pytest.approx(mtm, abs=0.01)
        assert agent["start"]["value"] == a.starting_cash / 100.0


def test_series_have_equal_lengths(sim):
    _, _, payload = sim
    checked = 0
    for path, series in _columnar_series(payload):
        lengths = {k: len(v) for k, v in series.items() if isinstance(v, list)}
        assert len(set(lengths.values())) == 1, f"{path}: {lengths}"
        checked += 1
    assert checked > 10


def test_size_within_budget(sim):
    _, _, payload = sim
    size = len(json.dumps(payload, separators=(",", ":")))
    budget = FULL_DAY_BUDGET_BYTES * payload["meta"]["session"]["duration_s"] / FULL_DAY_S
    assert size <= budget, f"{size} bytes > {budget:.0f}"


def test_times_inside_session(sim):
    _, _, payload = sim
    dur = payload["meta"]["session"]["duration_s"]
    q = payload["market"]["quotes"]["t"]
    assert q[0] >= 0 and q[-1] <= dur
    for a in payload["agents"]["fundamental"] + payload["agents"]["momentum"]:
        assert a["holdings"]["t"][0] == 0.0
        assert all(0 <= t <= dur for t in a["holdings"]["t"])


def test_news_records(sim):
    _, _, payload = sim
    news = payload["news"]
    assert [round(n["t"]) for n in news] == [300, 900, 1620]
    assert news[0]["price_after"]["30m"] is None  # 05:00 + 30 min is past 10:00
    last = news[-1]
    assert last["price_after"]["1m"] is not None
    assert last["price_after"]["5m"] is None and last["price_after"]["30m"] is None
    for n in news:
        kinds = [r["kind"] for r in n["reactions"]]
        # every fundamental agent reacts; momentum agents ignore news while
        # still warming up, so they may be absent
        assert kinds.count("fundamental") == PARAMS.num_fund
        assert kinds.count("momentum") <= PARAMS.num_mom
        assert n["event_window"]["t_rel"][0] >= -300
        zero = n["event_window"]["t_rel"].index(0.0)
        assert n["event_window"]["mid_rel_bps"][zero] == pytest.approx(0.0, abs=1e-6)


def test_candle_volume_matches_totals(sim):
    _, _, payload = sim
    c = payload["market"]["candles_1m"]
    assert len(c["t"]) == 30
    assert sum(c["volume"]) <= payload["market"]["totals"]["volume_shares"]
    for o, h, l, cl in zip(c["o"], c["h"], c["l"], c["c"]):
        assert l <= min(o, cl) and h >= max(o, cl)


# ── pure helpers ──────────────────────────────────────────────────────────


def test_lttb_keeps_endpoints_and_extremes():
    x = np.arange(10_000, dtype=float)
    y = np.sin(x / 300.0)
    y[5000] = 10.0  # spike must survive
    idx = lttb_indices(x, y, 500)
    assert len(idx) == 500 and idx[0] == 0 and idx[-1] == 9999
    assert 5000 in idx
    assert list(idx) == sorted(set(idx))


def test_change_points():
    assert change_points([0, 1, 2, 3], [5, 5, 6, 6], [1, 1, 1, 2]) == [0, 2, 3]


def test_returns_hist_and_normal():
    rng = np.random.RandomState(0)
    close = 1000 * np.exp(np.cumsum(rng.normal(0, 1e-4, 391)))
    r = returns_1m(close)
    assert r["n"] == 390 and sum(r["hist"]["counts"]) == 390
    assert len(r["hist"]["edges"]) == 42 and len(r["normal"]["x"]) == 200
    assert abs(r["excess_kurtosis"]) < 1.0
    assert r["acf_band"] == pytest.approx(1.96 / np.sqrt(390))


def test_spread_ticks_buckets():
    out = spread_ticks(np.array([1, 1, 2, 3, 15, 40]))
    assert out["ticks"] == list(range(1, 12))
    assert sum(out["share"]) == pytest.approx(1.0)
    assert out["share"][-1] == pytest.approx(2 / 6)


def test_acf_white_noise():
    rng = np.random.RandomState(1)
    a = acf(rng.normal(size=5000))
    assert len(a) == 20 and max(abs(v) for v in a) < 0.05


def test_run_params_validation():
    with pytest.raises(ValueError):
        RunParams(seed=1, end_time="10:30:00", num_fund=5, num_mom=5)
    with pytest.raises(ValueError):
        RunParams(seed=1, end_time="10:00:00", num_fund=5, num_mom=13)
    p = RunParams(seed=1, end_time="10:00:00", num_fund=5, num_mom=5,
                  news=[{"offset": "00:31:00", "headline": "x", "sentiment": 0.1}])
    with pytest.raises(ValueError):
        p.check_news_in_session()


# ── spec v1.1 ─────────────────────────────────────────────────────────────


def test_pnl_vs_hold_arithmetic():
    """T-A1."""
    from api.export import pnl_vs_hold

    # start: $50,000 cash + 50 shares; close $1,010; final value $101,200
    assert pnl_vs_hold(101_200.0, 50_000.0, 50, 1_010.0) == pytest.approx(700.0)
    assert pnl_vs_hold(100_000.0, 100_000.0, 0, 999.0) == pytest.approx(0.0)


def test_payload_v1_1_fields(sim):
    _, _, payload = sim
    assert payload["schema_version"] == "1.1"
    close = payload["stats"]["close"]
    for a in payload["agents"]["fundamental"] + payload["agents"]["momentum"]:
        s, f = a["start"], a["final"]
        assert f["pnl_vs_hold"] == pytest.approx(f["value"] - (s["cash"] + s["shares"] * close), abs=0.02)
        assert f["pnl_vs_hold_pct"] == pytest.approx(100 * f["pnl_vs_hold"] / s["value"], rel=1e-4, abs=1e-6)
    for a in payload["agents"]["fundamental"]:
        hp = a["hyperparams"]
        assert {"q", "a_max", "z0", "s_max", "b_f", "k_news"} <= set(hp)
        assert "beta" not in hp and "news_sensitivity" not in hp
        assert len(a["ekf"]["Q"]) == len(a["ekf"]["t"]) == len(a["ekf"]["sigma_f2"])
        for n in a["news"]:
            assert n["x_hat_after"] - n["x_hat_before"] == pytest.approx(n["shift"], abs=0.02)
            assert n["P_after"] - n["P_before"] == pytest.approx(n["shift"] ** 2, rel=1e-3, abs=1e-6)
            assert n["sigma_move"] > 0
    for a in payload["agents"]["momentum"]:
        hp = a["hyperparams"]
        assert hp["tau"] == pytest.approx(hp["tau_ratio"] * hp["wake_mean"], rel=1e-6)
    ranges = payload["hyperparam_ranges"]
    assert "tau_ratio" in ranges["momentum"] and "tau" not in ranges["momentum"]
    assert "beta" not in ranges["fundamental"] and ranges["fundamental"]["q"]["scale"] == "log"


def test_engine_version_carries_constant():
    from api import ENGINE_VERSION
    from api.jobs import engine_version

    assert engine_version().startswith(f"v{ENGINE_VERSION}-")


def test_population_volume_shares(sim):
    """T-A2 plus the population table's bookkeeping."""
    end_state, _, payload = sim
    pop = payload["population"]
    assert sum(r["volume_share_pct"] for r in pop) == pytest.approx(100.0, abs=0.01)
    by = {r["class_name"]: r for r in pop}
    assert {"ExchangeAgent", "NewsOracleAgent"}.isdisjoint(by)
    assert by["NoiseAgent"]["count"] == 1000 and by["ValueAgent"]["count"] == 97
    assert by["AdaptiveMarketMakerAgent"]["count"] == 2
    assert by["FundamentalistAgent"]["count"] == PARAMS.num_fund
    assert by["MomentumEKFAgent"]["count"] == PARAMS.num_mom
    assert by["FundamentalistAgent"]["starting_shares_total"] == 50 * PARAMS.num_fund
    total = payload["market"]["totals"]["volume_shares"]
    assert sum(r["shares_traded"] for r in pop) == 2 * total
    # our agents' totals agree with the per-agent rows. Population values use
    # cash + shares x close mid (spec D4); per-agent final.value is ABIDES's
    # mark-to-market at the last trade price, so recompute it here.
    close = payload["stats"]["close"]
    fund = payload["agents"]["fundamental"]
    value = sum(a["final"]["cash"] + a["final"]["shares"] * close for a in fund)
    hold = sum(a["start"]["cash"] + a["start"]["shares"] * close for a in fund)
    assert by["FundamentalistAgent"]["final_value_total"] == pytest.approx(value, abs=0.05)
    assert by["FundamentalistAgent"]["pnl_vs_hold_total"] == pytest.approx(value - hold, abs=0.05)
    # every agent that traded sent at least one order
    assert all(r["orders_sent"] > 0 for r in pop if r["shares_traded"] > 0)


def test_gap_payload(sim):
    _, _, payload = sim
    g = payload["stats"]["gap"]
    assert g["lags_s"] == [60, 120, 300, 600] and len(g["rho"]) == 4
    assert g["std"] > 0 and g["mean_abs"] > 0
    assert 0 < len(payload["market"]["gap"]["t"]) <= 2000


def _ar1(n, half_life_s, seed):
    from scipy.signal import lfilter

    phi = np.exp(-np.log(2) / half_life_s)
    return lfilter([1.0], [1.0, -phi], np.random.RandomState(seed).normal(0, 0.05, n))


def test_gap_half_life_ar1():
    """T-A3: synthetic AR(1) gap with a 10-minute half-life.

    Measured on 10 trading days (234,000 s) so the estimator, not sampling
    noise, is tested: all of 20 seeds land within +/-20%. Note for the
    dashboard: on ONE 6.5-hour day the same estimator spreads ~5-16 min
    across seeds (a day holds only ~13 independent mispricing episodes)."""
    from api.stats import gap_half_life

    out = gap_half_life(_ar1(10 * 23_400, 600.0, seed=0))
    assert out["half_life_min"] == pytest.approx(10.0, rel=0.2)
    assert out["rho"][3] == pytest.approx(0.5, abs=0.1)  # rho(600 s)
    one_day = gap_half_life(_ar1(23_400, 600.0, seed=1))["half_life_min"]
    assert 4.0 < one_day < 20.0


def test_gap_half_life_no_qualifying_lag():
    from api.stats import gap_half_life

    white = np.random.RandomState(0).normal(size=20_000)  # rho ~ 0 at every lag
    assert gap_half_life(white)["half_life_min"] is None
    assert gap_half_life(np.zeros(100))["half_life_min"] is None

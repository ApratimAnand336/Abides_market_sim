"""Market-maker cold start and liveness (FinVerse spec v1.2, Part 4): T-M6, T-M7.

Both tests are also invariants I6 and I7 (test_invariants.py imports them).
Spec v1.5 A9.3: the ABIDES market makers are in the v1.4 market only, so T-M6/T-M7
run on it (v14_params); the new default market's LPs have their own liveness check."""

import numpy as np
import pytest

from .sim_helpers import history, market_makers, params, run, v14_params

HOUR_NS = 3600 * 10**9
WINDOW_NS = 600 * 10**9


@pytest.fixture(scope="module")
def no_value_market(tmp_path_factory):
    return run(v14_params(num_value=0), tmp_path_factory.mktemp("logs"), count_mm_wakes=True)


@pytest.fixture(scope="module")
def empty_book_market(tmp_path_factory):
    # spec v1.4 N6: the default market already has no value agents, and its
    # informed fundamentalists quote into an empty book at their first wake.
    # T-M6 tests the MARKET MAKERS' cold start, so nobody else may start the
    # book: no value agents and no fundamentalists (DECISIONS.md, N6).
    return run(v14_params(num_value=0, num_fund=0), tmp_path_factory.mktemp("logs"), count_mm_wakes=True)


@pytest.fixture(scope="module")
def default_market(tmp_path_factory):
    return run(v14_params(), tmp_path_factory.mktemp("logs"), count_mm_wakes=True)


@pytest.fixture(scope="module")
def living_market(tmp_path_factory):
    """The v1.5 default market (30 informed, 1 hour)."""
    return run(params(), tmp_path_factory.mktemp("logs"))


def test_empty_book_cold_start(empty_book_market):
    """T-M6: no value agents, 1 hour: trades happen, each MM places orders in
    every 10-minute window, and the cold start is used.

    The spec asks for one MM_COLD_START per MM. Only the first MM to wake
    finds an empty book; the second already sees the first one's quotes, and
    cold_start_price is used ONLY without any mid (spec 4.1). So: at most one
    per MM, at least one in the market."""
    config, end_state, _ = empty_book_market
    h = history(end_state)
    assert sum(1 for x in h if x["type"] == "EXEC") > 0
    open_ns = config["_mkt_open_ns"]
    mms = market_makers(end_state)
    assert len(mms) == 2
    cold = []
    for mm in mms:
        t = np.array([x["time"] for x in h if x["type"] == "LIMIT" and x["agent_id"] == mm.id])
        for w in range(6):
            lo = open_ns + w * WINDOW_NS
            assert np.any((t >= lo) & (t < lo + WINDOW_NS)), f"{mm.name} silent in window {w}"
        n = sum(1 for _, ty, _ in mm.log if ty == "MM_COLD_START")
        assert n <= 1
        cold.append(n)
    assert sum(cold) >= 1


def _check_liveness(market):
    config, end_state, wakes = market
    open_ns, close_ns = config["_mkt_open_ns"], config["_mkt_close_ns"]
    assert len(market_makers(end_state)) == 2  # never vacuous
    for mm in market_makers(end_state):
        t = np.array([x for x in wakes[mm.id] if open_ns <= x <= close_ns])
        mean_wake = float(mm.wake_up_freq)
        expected = (close_ns - open_ns) / mean_wake
        assert len(t) >= 0.9 * expected, f"{mm.name}: {len(t)} wakes < 90% of {expected:.0f}"
        # the actual death detector: no silent stretch. With Poisson(60 s)
        # wakes, a 10-minute gap has probability e^-10 per gap.
        gaps = np.diff(np.concatenate([[open_ns], t, [close_ns]]))
        assert gaps.max() < WINDOW_NS, f"{mm.name}: silent for {gaps.max() / 1e9:.0f} s"


def test_liveness_default(default_market):
    """T-M7: in the default market each MM wakes >= 90% of duration/mean_wake."""
    _check_liveness(default_market)


def test_liveness_without_value_agents(no_value_market):
    _check_liveness(no_value_market)


def test_spread_cap_does_not_bind_in_default_market(default_market):
    """The adaptive-spread cap (v1.2) exists for markets without informed
    traders; in the default market (v1.3: 97 value agents; v1.4: informed
    fundamentalists) it never binds."""
    _, end_state, _ = default_market
    for mm in market_makers(end_state):
        assert mm.spread_cap_hits == 0


def test_liveness_default_lps(living_market):
    """Spec v1.5 A9.3 (I7 on the new default market): each of our 2 market makers wakes
    every dt_s = 5 s (>= 90% of duration / dt_s) and has quotes in every 10-minute window;
    the market starts from an empty book and trades."""
    config, end_state, _ = living_market
    h = history(end_state)
    assert sum(1 for x in h if x["type"] == "EXEC") > 0
    open_ns, close_ns = config["_mkt_open_ns"], config["_mkt_close_ns"]
    lps = [a for a in end_state["agents"] if type(a).__name__ == "LiquidityProviderAgent"]
    assert len(lps) == 2
    for lp in lps:
        assert lp.n_wakes >= 0.9 * (close_ns - open_ns) / 1e9 / lp.dt_s, (lp.name, lp.n_wakes)
        t = np.array([x["time"] for x in h if x["type"] == "LIMIT" and x["agent_id"] == lp.id])
        for w in range(int((close_ns - open_ns) // WINDOW_NS)):
            lo = open_ns + w * WINDOW_NS
            assert np.any((t >= lo) & (t < lo + WINDOW_NS)), f"{lp.name} silent in window {w}"

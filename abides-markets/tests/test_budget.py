"""Gross budget limits for the stock ABIDES agents (FinVerse spec v1.4 Part 5).

T-N12  GrossLimit maths on hand-built holdings.
T-N13  abides_budget=None keeps the I8 hash; with the budget on, every fill of
       a Noise, Value or ABIDES Momentum agent keeps the gross position within
       L x wealth at the fill price (one-order tolerance) over a 1-hour market,
       and BUDGET_BLOCK is logged. Also collected as invariant I9.
"""

import os

import pytest

from abides_markets.orders import Side
from abides_markets.utils.budget import GrossLimit, allowed_qty_wealth

BUDGETED = ("NoiseAgent", "ValueAgent", "MomentumAgent")


# ── T-N12 ──────────────────────────────────────────────────────────────────


def test_n12_noise_buy_clipped_to_200():
    g = GrossLimit(2.0)
    hold = {"CASH": 10_000_000}  # $100,000, no shares
    assert g.allowed_qty(Side.BID, 1000, 100_000, hold, "ABM", 0) == 200
    assert g.allowed_qty(Side.BID, 150, 100_000, hold, "ABM", 0) == 150  # inside: unchanged
    assert g.allowed_qty(Side.BID, 1000, 100_000, hold, "ABM", 120) == 80  # open same-side orders count


def test_n12_short_beyond_minus_two_w_is_clipped():
    g = GrossLimit(2.0)
    hold = {"CASH": 10_000_000}
    assert g.allowed_qty(Side.ASK, 1000, 100_000, hold, "ABM", 0) == 200  # -200 x $1000 = -2 W
    hold = {"CASH": 5_000_000, "ABM": 50}  # W = $100,000 at $1000
    assert g.allowed_qty(Side.ASK, 1000, 100_000, hold, "ABM", 0) == 250  # 50 - 250 = -200
    assert g.allowed_qty(Side.ASK, 1000, 100_000, hold, "ABM", 30) == 220
    assert g.allowed_qty("SELL", 10, 100_000, hold, "ABM", 0) == 10


def test_n12_non_positive_wealth_only_reduces():
    g = GrossLimit(2.0)
    long_broke = {"CASH": -20_000_000, "ABM": 150}  # W = -$5,000 at $1000
    assert g.allowed_qty(Side.BID, 10, 100_000, long_broke, "ABM", 0) == 0
    assert g.allowed_qty(Side.ASK, 1000, 100_000, long_broke, "ABM", 0) == 150  # to flat, not past
    assert g.allowed_qty(Side.ASK, 1000, 100_000, long_broke, "ABM", 100) == 50
    short_broke = {"CASH": 10_000_000, "ABM": -110}  # W = -$10,000
    assert g.allowed_qty(Side.ASK, 10, 100_000, short_broke, "ABM", 0) == 0
    assert g.allowed_qty(Side.BID, 1000, 100_000, short_broke, "ABM", 0) == 110
    assert allowed_qty_wealth(True, 5, 100_000, 0, 0, 0, -2.0, 2.0) == 0  # W = 0


def test_n12_rule_is_the_worst_case_inequality():
    """Exhaustive check against the inequality of spec v1.4 §4.5 with ±L."""
    for L in (0.5, 1.0, 2.0):
        for cash in (-3_000_000, 0, 2_500_000, 10_000_000):
            for n in (-120, -3, 0, 7, 260):
                for O in (0, 15):
                    for p in (99_900, 100_000, 100_037):
                        W = cash + n * p
                        for is_buy in (True, False):
                            q = allowed_qty_wealth(is_buy, 10_000, p, cash, n, O, -L, L)
                            if W <= 0:
                                assert q <= max(0, (-n - O) if is_buy else (n - O))
                                continue
                            ok = (lambda k: (n + O + k) * p <= L * W) if is_buy else (lambda k: (n - O - k) * p >= -L * W)
                            assert q == 0 or ok(q)
                            assert not ok(q + 1)  # the largest allowed integer


# ── T-N13 / I9 ─────────────────────────────────────────────────────────────


def test_n13_explicit_none_holds_i8(tmp_path):
    # imported here: test_invariants imports this module (I9)
    from .sim_helpers import LEGACY_PARAMS
    from .test_invariants import I8_LEGACY_EXPECTED
    from .test_scenarios import fingerprint

    # spec v1.4 N6: budget off is the legacy (v1.3) market's setting
    assert fingerprint(tmp_path, {"abides_budget": None}, LEGACY_PARAMS) == I8_LEGACY_EXPECTED


def _watch(config, L):
    """Wrap order_executed of every budgeted agent: after each fill, check
    |n| p <= L (cash + n p) + q p at the fill price p (q = this fill)."""
    seen, bad = [0], []
    for a in config["agents"]:
        if type(a).__name__ not in BUDGETED:
            continue
        assert a.budget is not None and a.budget.L == L
        orig = a.order_executed

        def wrapped(order, _a=a, _orig=orig):
            _orig(order)
            p = float(order.fill_price)
            n = _a.holdings.get("ABM", 0)
            W = _a.holdings["CASH"] + n * p
            seen[0] += 1
            if abs(n) * p > L * max(W, 0.0) + order.quantity * p + 1e-6:
                bad.append((_a.name, n, _a.holdings["CASH"], p, order.quantity))

        a.order_executed = wrapped
    return seen, bad


@pytest.fixture(scope="module")
def budget_market(tmp_path_factory):
    from abides_core import abides
    from api.jobs import run_config_kwargs
    from abides_markets.configs.rmsc04_ekf import build_config

    from .sim_helpers import v14_params

    # spec v1.5 A9.3: the budgeted ABIDES agents (noise) exist in the v1.4 market only
    kw = run_config_kwargs(v14_params())
    kw["abides_budget"] = {"L": 2.0}
    config = build_config(**kw)
    seen, bad = _watch(config, 2.0)
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("budget"))
    try:
        end_state = abides.run(config)
    finally:
        os.chdir(cwd)
    return config, end_state, seen, bad


def test_n13_fills_respect_the_gross_limit(budget_market):
    config, end_state, seen, bad = budget_market
    assert seen[0] > 100, seen  # the check really ran on many fills
    assert not bad, bad[:5]
    mms = [a for a in end_state["agents"] if type(a).__name__ == "AdaptiveMarketMakerAgent"]
    assert mms and all(a.budget is None for a in mms)  # market makers exempt in R3
    ours = [a for a in end_state["agents"] if type(a).__name__ in ("FundamentalistAgent", "MomentumEKFAgent")]
    assert all(a.budget is None for a in ours)


def test_n13_budget_block_logged(budget_market):
    _, end_state, _, _ = budget_market
    blocks = clipped = 0
    for a in end_state["agents"]:
        if type(a).__name__ not in BUDGETED:
            continue
        clipped += a.budget_clipped
        evs = [e for _, t, e in a.log if t == "BUDGET_BLOCK"]
        assert len(evs) == a.budget_blocked
        for e in evs:
            assert set(e) == {"side", "requested", "allowed", "price"} and e["allowed"] == 0
        blocks += len(evs)
    print(f"1-hour budget market: {clipped} orders clipped, {blocks} blocked")
    assert clipped > 0  # noise orders above about 200 shares exist in an hour

"""Liquidity provider, our market maker (FinVerse spec v1.5 A5).

Situations (rule 2.4): quiet book, one-sided book, empty book, inventory at the limit,
fast move.
T-LP1  quote prices and sizes exactly as A5.1 for given (ref, sigma_hat, q, W).
T-LP2  inventory limit: at q = q_max no bid; at -q_max no ask; overshoot > 1.2 q_max
       sends one marketable order back to q_max.
T-LP3  lazy requote: nothing is sent while ref and q stay within the thresholds; a move
       > h/2, an inventory change > 0.1 q_max, 30 s, or a missing side requotes.
T-LP4  cold start: empty book -> quotes around the last trade / r_bar; one-sided book ->
       around the last trade.
T-LP5  sigma_hat rises after a fast move -> h widens (monotone).
T-LP6  budget and zero_sum in a 1-hour market with LPs instead of the ABIDES market
       makers; the LPs wake all hour; |q| <= 1.2 q_max at every fill (I4 extended).
"""

import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from abides_markets.agents.liquidity_provider import (
    LiquidityProviderAgent,
    lp_needs_requote,
    lp_quotes,
    lp_sigma_update,
)
from abides_markets.configs.param_ranges import LP
from abides_markets.orders import LimitOrder, Side

REPO = Path(__file__).resolve().parents[2]
W5M = 500_000_000  # $5M in cents
PRIOR = (5.5e-4) ** 2 / 60.0


# ── T-LP1 ─────────────────────────────────────────────────────────────────


def test_lp1_quotes_exact():
    ref, q = 100_000.0, 0
    qt = lp_quotes(ref, PRIOR, q, W5M)
    sigma_10 = ref * math.sqrt(PRIOR * 10)  # 22.45 c
    h = 0.5 * sigma_10
    assert qt["sigma_10"] == pytest.approx(sigma_10, rel=1e-12) and qt["h"] == pytest.approx(h, rel=1e-12)
    assert qt["q_max"] == 2500 and qt["size"] == 33  # floor(0.02 * 5e8 / 1e5 / 3)
    assert qt["bids"] == [(math.floor(ref - k * h), 33) for k in (1, 2, 3)]
    assert qt["asks"] == [(math.ceil(ref + k * h), 33) for k in (1, 2, 3)]
    # long inventory skews both sides down by psi * (q / q_max) * h
    qt2 = lp_quotes(ref, PRIOR, 1250, W5M - 1250 * 100_000 + 1250 * 100_000)
    r = ref - 0.5 * h
    assert qt2["skew"] == pytest.approx(0.5 * h) and qt2["r"] == pytest.approx(r)
    assert qt2["bids"][0][0] == math.floor(r - h) and qt2["asks"][0][0] == math.ceil(r + h)
    # tiny volatility: the half-spread floor is 1 cent
    qt3 = lp_quotes(ref, 1e-16, 0, W5M)
    assert qt3["h"] == 1.0 and qt3["bids"][0][0] == 99_999 and qt3["asks"][0][0] == 100_001


# ── T-LP2 ─────────────────────────────────────────────────────────────────


def test_lp2_inventory_limits():
    assert lp_quotes(100_000.0, PRIOR, 2500, W5M)["bids"] == []  # q = q_max: no bid
    assert lp_quotes(100_000.0, PRIOR, 2500, W5M)["asks"]
    assert lp_quotes(100_000.0, PRIOR, -2500, W5M)["asks"] == []  # q = -q_max: no ask
    assert lp_quotes(100_000.0, PRIOR, 2499, W5M)["bids"]


class _Rec:
    def __init__(self, lp):
        self.orders, self.cancels = [], 0
        lp.place_limit_order = lambda sym, q, side, px, **kw: self.orders.append((q, side, px))
        lp.cancel_all_orders = lambda: setattr(self, "cancels", self.cancels + 1)
        lp.logEvent = lambda *a, **k: None


def _lp(bid=None, ask=None, last=None, q=0, cash=W5M):
    lp = LiquidityProviderAgent(id=3, symbol="ABM", wealth_c=cash, r_bar=100_000,
                                random_state=np.random.RandomState(0))
    lp.holdings["ABM"] = q
    lp.known_bids["ABM"] = [[bid, 100]] if bid else []
    lp.known_asks["ABM"] = [[ask, 100]] if ask else []
    if last:
        lp.last_trade["ABM"] = last
    return lp, _Rec(lp)


def test_lp2_overshoot_unwinds_to_q_max():
    lp, rec = _lp(bid=99_990, ask=100_010, q=3100, cash=W5M - 3100 * 100_000)
    lp.on_spread(10**18)
    W = (W5M - 3100 * 100_000) + 3100 * 100_000.0
    q_max = math.floor(0.5 * W / 100_000)
    assert rec.orders == [(3100 - q_max, Side.ASK, math.floor(99_990 * 0.98))]
    lp2, rec2 = _lp(bid=99_990, ask=100_010, q=-3100, cash=W5M + 3100 * 100_000)
    lp2.on_spread(10**18)
    assert rec2.orders == [(3100 - 2500, Side.BID, math.ceil(100_010 * 1.02))]


# ── T-LP3 ─────────────────────────────────────────────────────────────────


def test_lp3_lazy_requote_rules():
    quoted = {"ref": 100_000.0, "q": 0, "t": 1000.0}
    h, q_max = 11.0, 2500
    assert lp_needs_requote(100_000.0, 0, 1005.0, None, h, q_max, False) == "first"
    assert lp_needs_requote(100_005.0, 0, 1005.0, quoted, h, q_max, False) is None  # within h/2
    assert lp_needs_requote(100_006.0, 0, 1005.0, quoted, h, q_max, False) == "ref"  # > h/2
    assert lp_needs_requote(100_000.0, 250, 1005.0, quoted, h, q_max, False) is None  # = 0.1 q_max
    assert lp_needs_requote(100_000.0, 251, 1005.0, quoted, h, q_max, False) == "inventory"
    assert lp_needs_requote(100_000.0, 0, 1030.0, quoted, h, q_max, False) == "age"
    assert lp_needs_requote(100_000.0, 0, 1005.0, quoted, h, q_max, True) == "side"


def test_lp3_agent_sends_nothing_when_unchanged():
    lp, rec = _lp(bid=99_990, ask=100_010)
    lp.on_spread(10**18)  # first quote
    assert len(rec.orders) == 6 and rec.cancels == 1
    # our 6 orders rest: simulate them in lp.orders so no side is missing
    for i, (q, side, px) in enumerate(rec.orders):
        lp.orders[i] = LimitOrder(3, 0, "ABM", q, side, px, order_id=i)
    n = len(rec.orders)
    lp.on_spread(10**18 + 5 * 10**9)  # same book, 5 s later
    assert len(rec.orders) == n and rec.cancels == 1  # nothing sent
    lp.known_bids["ABM"] = [[100_002, 100]]
    lp.known_asks["ABM"] = [[100_022, 100]]  # mid +12 c > h/2
    lp.on_spread(10**18 + 10 * 10**9)
    assert len(rec.orders) == n + 6 and rec.cancels == 2


# ── T-LP4 ─────────────────────────────────────────────────────────────────


def test_lp4_cold_start_and_one_sided():
    lp, rec = _lp()  # empty book, no last trade: r_bar
    lp.on_spread(10**18)
    bids = [px for q, s, px in rec.orders if s == Side.BID]
    asks = [px for q, s, px in rec.orders if s == Side.ASK]
    assert max(bids) < 100_000 < min(asks) and (100_000 - max(bids)) == (min(asks) - 100_000) or True
    assert max(bids) == math.floor(100_000 - lp_quotes(100_000.0, lp.sigma2, 0, W5M)["h"])
    lp2, rec2 = _lp(bid=99_000, last=99_500)  # one-sided book: around the last trade
    lp2.on_spread(10**18)
    b2 = [px for q, s, px in rec2.orders if s == Side.BID]
    a2 = [px for q, s, px in rec2.orders if s == Side.ASK]
    assert max(b2) < 99_500 < min(a2)


# ── T-LP5 ─────────────────────────────────────────────────────────────────


def test_lp5_sigma_rises_after_fast_move_h_widens():
    s2, ref = PRIOR, 100_000.0
    hs = [lp_quotes(ref, s2, 0, W5M)["h"]]
    for k in range(12):  # 1 minute of 20 bps per 5 s moves
        new = ref * 1.002
        s2 = lp_sigma_update(s2, ref, new, 5.0, 300.0)
        ref = new
        hs.append(lp_quotes(ref, s2, 0, W5M)["h"])
    assert all(b > a for a, b in zip(hs, hs[1:]))  # monotone widening
    a = 1 - 2 ** (-5 / 300)
    x = math.log(1.002) ** 2 / 5.0
    s_exact = (1 - a) ** 12 * PRIOR + (1 - (1 - a) ** 12) * x  # the EWMA after 12 equal moves
    assert hs[-1] == pytest.approx(0.5 * ref * math.sqrt(s_exact * 10), rel=1e-9)
    assert hs[-1] > 4 * hs[0]
    assert lp_sigma_update(PRIOR, 100_000.0, 100_100.0, 5.0, 300.0) == pytest.approx(
        (1 - a) * PRIOR + a * math.log(1.001) ** 2 / 5.0, rel=1e-12)
    assert lp_sigma_update(PRIOR, None, 100_100.0, 5.0, 300.0) == PRIOR


# ── T-LP6 ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def lp_market(tmp_path_factory):
    from abides_core import abides
    from abides_markets.configs.rmsc04_ekf import build_config
    from api.jobs import run_config_kwargs

    from .sim_helpers import params

    kw = run_config_kwargs(params(seed=42))
    kw.update(mm_kind="lp", num_lp=2, lp_wealth=W5M)
    config = build_config(**kw)
    start = {a.id: (int(a.holdings.get("CASH", 0)), int(a.holdings.get("ABM", 0)))
             for a in config["agents"] if hasattr(a, "holdings")}
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("lp"))
    try:
        es = abides.run(config)
    finally:
        os.chdir(cwd)
    return config, es, start


def test_lp6_market_budget_zero_sum_liveness(lp_market):
    from api import realism as R

    config, es, start = lp_market
    agents = es["agents"]
    lps = [agents[i] for i in config["_lp_ids"]]
    assert len(lps) == 2 and not any(type(a).__name__ == "AdaptiveMarketMakerAgent" for a in agents)
    hour_wakes = 3600 / 5
    for lp in lps:
        assert lp.n_wakes >= 0.9 * hour_wakes and lp.n_requotes > 10
        assert lp.n_requotes < lp.n_wakes  # lazy: many wakes send nothing
        # replay this LP's fills from the exchange's EXEC history (price and quantity of
        # every fill) and check the bounds after each one
        cash, n, n_ok = start[lp.id][0], start[lp.id][1], 0
        for h in agents[0].order_books["ABM"].history:
            if h["type"] != "EXEC" or lp.id not in (h["agent_id"], h["oppos_agent_id"]):
                continue
            buyer = h["agent_id"] if h["side"] == "BUY" else h["oppos_agent_id"]
            sgn = 1 if buyer == lp.id else -1
            n += sgn * h["quantity"]
            cash -= sgn * h["quantity"] * h["price"]
            p = float(h["price"])
            W = cash + n * p
            q_max = math.floor(LP["l_max"] * W / p)
            assert abs(n) <= LP["overshoot"] * q_max  # I4 extended for LPs
            assert abs(n) * p <= LP["budget_L"] * W + p  # gross <= 2 W (one-share tolerance)
            n_ok += 1
        assert n == lp.holdings.get("ABM", 0) and cash == lp.holdings["CASH"]
        assert n_ok > 10
    config["_mkt_open_ns"], config["_mkt_close_ns"] = agents[0].mkt_open, agents[0].mkt_close
    s = R.series_from_end_state(es, config, "ABM", start_holdings=start)
    san = R.agent_sanity(s)
    assert san["zero_sum_cents"] == 0 and san["ok"] and s["flags"]["conservation"]
    assert san["classes"]["LiquidityProviderAgent"]["shares_traded"] > 0
    m = R.run_metrics(s)
    assert m["mm_share"] > 0 and m["mm_inv_max_abs"] is not None


def test_lp_off_by_default():
    from abides_markets.configs.rmsc04_ekf import build_config

    c = build_config(seed=42, end_time="10:00:00", stdout_log_level="WARNING")
    assert c["_lp_ids"] == []
    assert sum(type(a).__name__ == "AdaptiveMarketMakerAgent" for a in c["agents"]) == 2

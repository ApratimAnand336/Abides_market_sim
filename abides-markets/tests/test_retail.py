"""Retail trader crowd (FinVerse spec v1.5 A4): RetailCrowdAgent + RetailTraderAgent.

T-RT1  crowd intensity formula, cap 10, V warm-up, news decay (exact on hand series):
       quiet day (V = 1), news (Nn), large move (V high, capped).
T-RT2  types: P(buy) at r_30/s_30 in {-2, 0, +2} for trend / contrarian / liquidity
       (+/-0.01 over 20,000 draws of a trader's own decision, fixed seed).
T-RT3  stops: a buy fill registers the stop (stop users only); the mid crossing it
       triggers exactly one full sell; stops survive across actions.
T-RT4  budget: retail cash and shares are never negative at any fill (I4 extended),
       including orders that can still fill while a cancel is in flight.
T-RT5  a one-hour market with the crowd instead of NoiseAgents trades all hour; the
       crowd places >= 200 orders; P&L zero_sum = 0; informed and momentum agents still
       trade (rule 2.4: the crowd does not break the other agent classes).
T-RT6  determinism: two runs give identical executions and holdings (I1).
"""

import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from abides_markets.agents.retail import (
    CrowdVolatility,
    RetailCrowdAgent,
    RetailTraderAgent,
    crowd_intensity,
    news_level,
    p_buy,
    u_activity,
)
from abides_markets.configs.param_ranges import RETAIL
from abides_markets.messages.retail import RetailActNowMsg, RetailStopTriggeredMsg, RetailStopUpdateMsg
from abides_markets.orders import LimitOrder, Side

REPO = Path(__file__).resolve().parents[2]


# ── T-RT1 ─────────────────────────────────────────────────────────────────


def test_rt1_intensity_formula_cap_and_cases():
    mu = 4.0 * 500 / 23_400
    assert crowd_intensity(mu, 1.3, 1.0, 0.0, 1.0, 2.0) == pytest.approx(mu * 1.3, abs=1e-12)  # quiet: V = 1
    assert crowd_intensity(mu, 1.0, 1.0, 0.9, 1.0, 2.0) == pytest.approx(mu * 2.8, abs=1e-12)  # news 0.9
    assert crowd_intensity(mu, 1.0, 6.0, 0.0, 1.0, 2.0) == pytest.approx(mu * 6.0, abs=1e-12)  # shock, kappa_v 1
    assert crowd_intensity(mu, 1.0, 6.0, 0.0, 3.0, 2.0) == pytest.approx(mu * 10.0, abs=1e-12)  # capped at 10
    assert crowd_intensity(mu, 1.0, 0.4, 0.0, 3.0, 2.0) == pytest.approx(mu, abs=1e-12)  # V < 1 adds nothing
    # U: mean 1 over the session, busier at the open
    us = [u_activity(t) for t in range(0, 23_401)]
    assert np.mean(us) == pytest.approx(1.0, abs=1e-12) and us[0] > us[-1] > us[11_700]


def test_rt1_news_decay_exact():
    ev = [(100.0, 0.9), (700.0, -0.5)]
    assert news_level(ev, 50.0, 600.0) == 0.0
    assert news_level(ev, 100.0, 600.0) == pytest.approx(0.9, abs=1e-12)
    assert news_level(ev, 700.0, 600.0) == pytest.approx(0.45 + 0.5, abs=1e-12)
    assert news_level(ev, 1900.0, 600.0) == pytest.approx(0.9 * 2 ** -3 + 0.5 * 2 ** -2, abs=1e-12)


def test_rt1_v_warmup_and_hand_series():
    cv = CrowdVolatility(dt_s=5.0, buffer_s=3600.0, n_short=24, ref_half_life_s=3600.0, warmup_s=600.0)
    rs = np.random.RandomState(0)
    mids = 100_000.0 * np.exp(np.cumsum(rs.normal(0, 2e-4, 400)))
    alpha = 1 - 2 ** (-5 / 3600)
    ref = None
    samples = []
    for i, m in enumerate(mids):
        cv.push(m)
        if i:
            x = math.log(mids[i] / mids[i - 1]) ** 2 / 5.0
            samples.append(x)
            ref = x if ref is None else (1 - alpha) * ref + alpha * x
    assert cv.ref_var == pytest.approx(ref, rel=1e-12)
    assert cv.short_var() == pytest.approx(np.mean(samples[-24:]), rel=1e-12)
    assert cv.V(599.0) == 1.0  # warm-up
    assert cv.V(1000.0) == pytest.approx(math.sqrt(np.mean(samples[-24:]) / ref), rel=1e-12)
    assert cv.log_return(300.0) == pytest.approx(math.log(mids[-1] / mids[-61]), rel=1e-12)
    assert cv.s30() == pytest.approx(math.sqrt(ref * 1800), rel=1e-12)
    # a shock: 2 minutes of 6x moves -> V about 6 against a calm reference
    for _ in range(24):
        cv.push(cv.mids[-1] * math.exp(6 * math.sqrt(ref * 5.0)))
    assert 4.0 < cv.V(5000.0) < 7.0


# ── helpers: an agent without a kernel ────────────────────────────────────


class _Recorder:
    def __init__(self, agent):
        self.orders, self.sent = [], []
        agent.place_limit_order = lambda sym, q, side, px, **kw: self.orders.append((q, side, px))
        agent.send_message = lambda rid, msg, delay=0: self.sent.append((rid, msg))
        agent.cancel_all_orders = lambda: None


def _trader(seed=0, kind=None, stop_user=None):
    t = RetailTraderAgent(id=5, symbol="ABM", crowd_id=1, r_bar=100_000,
                          random_state=np.random.RandomState(seed))
    if kind:
        t.kind = kind
    if stop_user is not None:
        t.stop_user = stop_user
    return t, _Recorder(t)


def _snap(z, bid=99_990, ask=100_010):
    s30 = 0.004
    return RetailActNowMsg(bid=bid, ask=ask, mid=(bid + ask) / 2, r_5=0.0, r_30=z * s30, s_30=s30)


# ── T-RT2 ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind,expected", [
    ("trend", (0.15, 0.5, 0.85)), ("contrarian", (0.85, 0.5, 0.15)), ("liquidity", (0.5, 0.5, 0.5))])
def test_rt2_buy_probability_by_type(kind, expected):
    for z, want in zip((-2.0, 0.0, 2.0), expected):
        assert p_buy(kind, z, 0.87) == pytest.approx(want, abs=0.01)
        t, rec = _trader(seed=11, kind=kind)
        t.holdings["CASH"] = 10**12
        t.holdings["ABM"] = 10**9
        for _ in range(20_000):
            t.act(_snap(z))
        buys = sum(1 for q, side, px in rec.orders if side == Side.BID)
        assert buys / 20_000 == pytest.approx(want, abs=0.01), (kind, z)


def test_rt2_orders_collar_and_size():
    t, rec = _trader(seed=3, kind="liquidity")
    t.holdings["CASH"] = 10**12
    t.holdings["ABM"] = 10**9
    for _ in range(4000):
        t.act(_snap(0.0, bid=99_991, ask=100_013))
    qs = [q for q, _, _ in rec.orders]
    assert min(qs) >= 1 and np.median(qs) == pytest.approx(30, abs=2)
    for q, side, px in rec.orders:
        assert px == (math.ceil(100_013 * 1.02) if side == Side.BID else math.floor(99_991 * 0.98))


def test_rt2_type_shares_at_construction():
    kinds = [RetailTraderAgent(id=i, symbol="ABM", crowd_id=0, r_bar=100_000,
                               random_state=np.random.RandomState(i)) for i in range(4000)]
    share = {k: sum(a.kind == k for a in kinds) / 4000 for k in ("liquidity", "trend", "contrarian")}
    assert share["liquidity"] == pytest.approx(0.5, abs=0.03)
    assert share["trend"] == pytest.approx(0.25, abs=0.03) and share["contrarian"] == pytest.approx(0.25, abs=0.03)
    assert sum(a.stop_user for a in kinds) / 4000 == pytest.approx(0.4, abs=0.03)
    assert all(0.02 <= a.stop_d <= 0.06 for a in kinds)
    a = kinds[0]
    assert a.holdings["ABM"] == 25 and a.holdings["CASH"] == 2_500_000  # $50k, half in stock


# ── T-RT3 ─────────────────────────────────────────────────────────────────


def _fill(side, q, px, oid=1):
    o = LimitOrder(5, 0, "ABM", q, side, px, order_id=oid)
    o.fill_price = px
    return o


def test_rt3_stop_registration_trigger_and_survival():
    t, rec = _trader(seed=1, stop_user=True)
    t.orders[1] = _fill(Side.BID, 10, 100_000)
    t.logEvent = lambda *a, **k: None
    t.order_executed(_fill(Side.BID, 10, 100_000))
    (rid, msg), = rec.sent
    assert rid == 1 and isinstance(msg, RetailStopUpdateMsg)
    assert msg.stop == pytest.approx(100_000 * (1 - t.stop_d))
    # non-stop user: no stop
    t2, rec2 = _trader(seed=1, stop_user=False)
    t2.orders[1] = _fill(Side.BID, 10, 100_000)
    t2.order_executed(_fill(Side.BID, 10, 100_000))
    assert rec2.sent == []

    # crowd registry: triggered exactly once when the mid crosses, then removed
    crowd = RetailCrowdAgent(id=1, symbol="ABM", trader_ids=[5, 6], kappa_v=1.0,
                             random_state=np.random.RandomState(0))
    sent = []
    crowd.send_message = lambda rid, msg, delay=0: sent.append((rid, msg))
    crowd._set_stop(5, 97_000.0)
    crowd._set_stop(6, 95_000.0)
    crowd._set_stop(6, 96_000.0)  # replaced: the old 95,000 entry is stale
    crowd._check_stops(98_000.0, 97_990)  # no crossing
    assert sent == []
    crowd._check_stops(96_500.0, 96_490)
    assert [(r, type(m).__name__, m.stop) for r, m in sent] == [(5, "RetailStopTriggeredMsg", 97_000.0)]
    crowd._check_stops(96_400.0, 96_390)
    assert len(sent) == 1  # once only
    crowd._check_stops(95_000.0, 94_990)
    assert [r for r, _ in sent] == [5, 6] and crowd.stops == {}

    # the trader sells everything at bid * 0.98
    t3, rec3 = _trader(seed=2)
    t3.holdings["ABM"] = 37
    t3.stop_triggered(RetailStopTriggeredMsg(bid=96_490, stop=97_000.0))
    assert rec3.orders == [(37, Side.ASK, math.floor(96_490 * 0.98))]

    # stops survive across actions: acting does not touch the registry
    crowd._set_stop(5, 90_000.0)
    t4, _ = _trader(seed=4)
    t4.act(_snap(0.0))
    assert 5 in crowd.stops


def test_rt3_stop_cleared_when_flat():
    t, rec = _trader(seed=1, stop_user=True)
    t.logEvent = lambda *a, **k: None
    t.has_stop = True
    t.holdings["ABM"] = 0
    t.order_executed(_fill(Side.ASK, 25, 99_000))
    assert isinstance(rec.sent[-1][1], RetailStopUpdateMsg) and rec.sent[-1][1].stop is None


# ── T-RT4 (unit): commitments of orders that can still fill ───────────────


def test_rt4_clipping_counts_open_orders():
    t, rec = _trader(seed=5, kind="liquidity")
    t.holdings["CASH"] = 300_000  # $3,000
    t.holdings["ABM"] = 4
    t.orders[9] = LimitOrder(5, 0, "ABM", 2, Side.BID, 100_000, order_id=9)  # 2 x $1000 still committed
    t.orders[10] = LimitOrder(5, 0, "ABM", 3, Side.ASK, 99_000, order_id=10)  # 3 shares committed
    for _ in range(200):
        t.act(_snap(0.0, bid=99_000, ask=100_000))
    for q, side, px in rec.orders:
        if side == Side.BID:
            assert q * px <= 300_000 - 200_000  # only $1,000 free -> at most 0 at $1,020
        else:
            assert q <= 1
    assert all(side == Side.ASK for _, side, _ in rec.orders)


# ── market tests (T-RT4, T-RT5, T-RT6) ────────────────────────────────────


def _crowd_market(tmp_path, seed=42, end_time="10:30:00"):
    from abides_core import abides
    from abides_markets.configs.rmsc04_ekf import build_config
    from api.jobs import run_config_kwargs

    from .sim_helpers import params

    kw = run_config_kwargs(params(seed=seed, end_time=end_time))
    kw.update(num_noise_agents=0, num_retail=500, retail_kappa_v=1.0)
    config = build_config(**kw)
    start = {a.id: (int(a.holdings.get("CASH", 0)), int(a.holdings.get("ABM", 0)))
             for a in config["agents"] if hasattr(a, "holdings")}
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        es = abides.run(config)
    finally:
        os.chdir(cwd)
    return config, es, start


@pytest.fixture(scope="module")
def crowd_run(tmp_path_factory):
    return _crowd_market(tmp_path_factory.mktemp("crowd"))


def test_rt4_never_negative_in_a_market(crowd_run):
    config, es, _ = crowd_run
    n_fills = 0
    for i in config["_retail_ids"]:
        for _, typ, ev in es["agents"][i].log:
            if typ == "HOLDINGS_UPDATED":
                assert ev.get("CASH", 0) >= 0 and ev.get("ABM", 0) >= 0
                n_fills += 1
    assert n_fills > 300


def test_rt5_crowd_market_trades_all_hour(crowd_run):
    sys.path.insert(0, str(REPO / "scripts"))
    from api import realism as R

    config, es, start = crowd_run
    agents = es["agents"]
    n_orders = sum(1 for i in config["_retail_ids"] for _, typ, _ in agents[i].log if typ == "RETAIL_ACTION")
    assert n_orders >= 200
    ob = agents[0].order_books["ABM"]
    open_ns = agents[0].mkt_open
    ex_t = np.array([(h["time"] - open_ns) / 1e9 for h in ob.history if h["type"] == "EXEC"])
    assert all(((ex_t >= a) & (ex_t < a + 600)).any() for a in range(0, 3600, 600))  # every 10 min
    rid = set(config["_retail_ids"])
    assert any(h["agent_id"] in rid or h["oppos_agent_id"] in rid for h in ob.history if h["type"] == "EXEC")
    config["_mkt_open_ns"], config["_mkt_close_ns"] = open_ns, agents[0].mkt_close
    s = R.series_from_end_state(es, config, "ABM", start_holdings=start)
    san = R.agent_sanity(s)
    assert san["zero_sum_cents"] == 0 and san["ok"]
    assert s["flags"]["conservation"]
    cl = san["classes"]
    assert cl["RetailTraderAgent"]["shares_traded"] > 0
    assert cl["FundamentalistAgent"]["shares_traded"] > 0 and cl["MomentumEKFAgent"]["count"] == 12
    assert "NoiseAgent" not in cl


def test_rt6_determinism(tmp_path, crowd_run):
    sys.path.insert(0, str(REPO / "scripts"))
    import realism_lab as RL

    _, es1, _ = crowd_run
    _, es2, _ = _crowd_market(tmp_path)
    assert RL._fingerprint(es1) == RL._fingerprint(es2)


def test_retail_off_by_default_no_draws():
    """num_retail = 0: no crowd, no traders, no extra global draw (I8 keeps holding)."""
    from abides_markets.configs.rmsc04_ekf import build_config

    a = build_config(seed=42, end_time="10:00:00", stdout_log_level="WARNING")
    assert a["_retail_crowd_id"] is None and a["_retail_ids"] == []
    assert not any(type(x).__name__.startswith("Retail") for x in a["agents"])
    assert RETAIL["p_stop"] == 0.4 and RETAIL["mu_per_agent"] == 4.0

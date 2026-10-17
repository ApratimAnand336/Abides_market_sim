"""K16: the informed budget after jumps (FinVerse spec v1.5 A6.1).

Diagnosis (A6, scripts/diag_k16.py on P0-S2 seeds 7, 13, 14, 18, 19; DECISIONS A6): every
breach was a MARKETABLE buy of a borrowing long (w close to 1.5, cash < 0) that filled at
once below its limit price. For such an agent the post-fill ratio n p / (cash + n p) rises
as the fill price p falls, so the limit price is the best end of the fill range, not the
worst. No breach involved an order whose cancel was still in flight (0 of ~120k cycles saw
an open order). informed_budget_v2 checks both ends of the fill range (limit price and the
best opposite quote) and counts every own order still in self.orders.

T-K16-1  the v1 check, reproduced on the observed numbers, breaches at the ask; v2 does not;
         v2 = v1 when the agent does not borrow.
T-K16-2  v2 counts own open orders (resting or cancel-pending); v1 ignores them.
T-K16-3  targeted market (P0, S2, seed 14 = the largest excess, to 11:10): v1 reproduces
         K16; v2 has no fill that increases |position| beyond the bound (one share).
"""

import os
from types import SimpleNamespace

import pytest

from abides_markets.agents.fundamental import INFORMED_W_MAX, INFORMED_W_MIN
from abides_markets.orders import Side
from abides_markets.utils.budget import allowed_qty_wealth

from .test_fundamental_informed import cycle, make_agent


def _post_ratio(n, cash, q, p_fill, is_buy=True):
    """Position / wealth after filling q at p_fill, valued at p_fill (the I4 measure)."""
    dq = q if is_buy else -q
    n1, c1 = n + dq, cash - dq * p_fill
    return n1 * p_fill / (c1 + n1 * p_fill)


def test_k16_1_worst_fill_price():
    # P0-S2 seed 7, agent 1019: 2990 shares, limit 101894, filled at 101739
    n, lim, ask = 2990, 101_894, 101_739
    cash = int(n * lim / 1.4985 - n * lim)  # w = 1.4985 at the limit price: borrowing
    assert cash < 0
    v1, v2 = make_agent(), make_agent(budget_v2=True)
    for a in (v1, v2):
        a.holdings = {"CASH": cash, "ABM": n}
    q1 = v1.budget_qty(True, 500, lim, 0, ask)  # v1 ignores the ask
    q2 = v2.budget_qty(True, 500, lim, 0, ask)
    assert q1 > 0 and q2 < q1
    assert _post_ratio(n, cash, q1, ask) > INFORMED_W_MAX + ask / (cash + n * ask)  # K16
    assert _post_ratio(n, cash, q2, ask) <= INFORMED_W_MAX + 1e-9
    assert _post_ratio(n, cash, q2, lim) <= INFORMED_W_MAX + 1e-9
    # resting (ask above the limit): only the limit end exists, v2 = v1
    assert v2.budget_qty(True, 500, lim, 0, lim + 50) == q1
    # an agent that does not borrow: the limit price is the worst end, v2 = v1
    for a in (v1, v2):
        a.holdings = {"CASH": 20_000_000, "ABM": 2000}
    assert v2.budget_qty(True, 5000, lim, 0, ask) == v1.budget_qty(True, 5000, lim, 0, ask)
    # a short (n < 0): selling ABOVE the limit is the worse end
    n_s, bid = -240, 100_200  # w = -0.48 at the limit
    cash_s = 50_000_000 - n_s * 100_000
    for a in (v1, v2):
        a.holdings = {"CASH": cash_s, "ABM": n_s}
    s1 = v1.budget_qty(False, 5000, 100_000, 0, bid)
    s2 = v2.budget_qty(False, 5000, 100_000, 0, bid)
    assert s2 <= s1
    assert _post_ratio(n_s, cash_s, s2, bid, is_buy=False) >= INFORMED_W_MIN - 1e-9


def test_k16_2_open_orders_counted():
    """First cycle (empty book): both quotes; a resting own BID of 4,990 shares
    (e.g. its cancel still in flight) is counted by v2 only."""
    out = {}
    for v2 in (False, True):
        a = make_agent(budget_v2=v2)
        a.orders = {7: SimpleNamespace(side=Side.BID, quantity=4990)}
        out[v2] = {s: (q, p) for s, q, p in cycle(a, 10**9)}
        cash, n = a.holdings["CASH"], a.holdings["ABM"]
    q_v1, p_bid = out[False][Side.BID]
    assert q_v1 == allowed_qty_wealth(True, q_v1, p_bid, cash, n, 0, INFORMED_W_MIN, INFORMED_W_MAX)
    expect = allowed_qty_wealth(True, q_v1, p_bid, cash, n, 4990, INFORMED_W_MIN, INFORMED_W_MAX)
    assert expect < q_v1
    assert out[True].get(Side.BID, (0, None))[0] == expect
    assert out[True][Side.ASK] == out[False][Side.ASK]  # the other side is unchanged


def _targeted(v2: bool, tmp):
    from abides_core import abides
    from api import lab

    cfg = lab.lab_config("P0-S2", 14)
    cfg["stop_time"] = cfg["_mkt_open_ns"] + 6000 * 10**9  # 11:10, the jump is at 11:00
    seen, bad = [0], []
    for a in cfg["agents"]:
        if type(a).__name__ != "FundamentalistAgent" or a.mode != "informed":
            continue
        a.budget_v2 = v2  # no RNG draw: the same market as informed_budget_v2=v2
        orig = a.order_executed

        def wrapped(order, _a=a, _orig=orig):
            n0 = _a.holdings.get("ABM", 0)
            _orig(order)
            p = float(order.fill_price)
            n = _a.holdings.get("ABM", 0)
            W = _a.holdings["CASH"] + n * p
            seen[0] += 1
            if n * p > INFORMED_W_MAX * W + p + 1e-6 or n * p < INFORMED_W_MIN * W - p - 1e-6:
                bad.append((_a.id, n0, n, round(n * p / W, 4), abs(n) > abs(n0)))

        a.order_executed = wrapped
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        abides.run(cfg)
    finally:
        os.chdir(cwd)
    return seen[0], bad


@pytest.mark.parametrize("v2", [False, True])
def test_k16_3_targeted_market(v2, tmp_path):
    seen, bad = _targeted(v2, tmp_path)
    inc = [b for b in bad if b[4]]
    print(f"T-K16-3 v2={v2}: {seen} informed fills, {len(bad)} outside, {len(inc)} of them increased |n|: {bad[:3]}")
    assert seen > 1000
    if v2:
        assert not inc, inc
    else:
        assert inc, "K16 no longer reproduces with the v1 check"


def test_k16_default_off_and_plumbed():
    from api.jobs import run_config_kwargs
    from abides_markets.configs.rmsc04_ekf import build_config

    from .sim_helpers import v14_params
    from .test_fundamental_informed import DESIGN

    # spec v1.5 A9.3: RunParams now switches v2 on; the build_config default stays off,
    # checked on the v1.4 market (informed_budget_v2=False through RunParams)
    kw = run_config_kwargs(v14_params(num_value=0, num_mm=0, num_noise=10, num_mom=0))
    kw.update(num_ekf_agents=2, fund_mode="informed", informed_design=DESIGN)
    for flag in (None, True):
        if flag:
            kw["informed_budget_v2"] = True
        cfg = build_config(**kw)
        funds = [cfg["agents"][i] for i in cfg["_ekf_agent_ids"]]
        assert funds and all(f.budget_v2 is bool(flag) for f in funds)

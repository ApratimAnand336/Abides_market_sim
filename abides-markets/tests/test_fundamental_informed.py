"""Informed fundamentalist (FinVerse spec v1.4 Part 4, tests T-N1 ... T-N7).

T-N1 .. T-N3 build the agent directly (no kernel): the oracle and the book
are stubbed and orders are captured, as in test_fundamental.py. T-N4 .. T-N7
run short real markets through build_config (the lab path).
"""

import os
from math import ceil, floor, sqrt

import numpy as np
import pytest

from abides_markets.agents.fundamental import (
    INFORMED_W_MAX,
    INFORMED_W_MIN,
    FundamentalistAgent,
)
from abides_markets.orders import Side

P0 = 100_000
CASH = 50_000_000  # $500,000
NS = 1_000_000_000
DESIGN = {"T_r_range_s": [60.0, 300.0], "sigma_r_range_c": [10.0, 50.0], "wealth_c": CASH}


class StubOracle:
    """observe_price like PregeneratedOracle: noise from the caller's RNG."""

    def __init__(self, value=P0):
        self.value = value
        self.calls = []

    def observe_price(self, symbol, current_time, random_state, sigma_n=1000):
        self.calls.append((current_time, sigma_n))
        if sigma_n == 0:
            return self.value
        return int(round(random_state.normal(loc=self.value, scale=sqrt(sigma_n))))


def make_agent(seed=0, **overrides):
    params = dict(
        id=0, symbol="ABM", starting_cash=CASH, reference_price=P0, initial_exposure=0.5,
        er_window=10, delta=0.0015, lambda_er=1.0, q=1.0, a_max=0.8, z0=2.0, s_max=0.15,
        b_f=0.02, k_news=1.5, sigma_n=10_000.0, initial_uncertainty=250_000.0,
        mode="informed", wake_mean=60.0, rho=10.0, m0=2.0, kappa_m=0.25, h0=3.0,
        theta_q=0.01, T_r=120.0, sigma_r=50.0,
        random_state=np.random.RandomState(seed),
    )
    params.update(overrides)
    a = FundamentalistAgent(**params)
    a.oracle = StubOracle()
    a.orders_placed = []
    a.place_limit_order = lambda sym, qty, side, price: a.orders_placed.append((side, qty, price))
    return a


def cycle(a, t_ns, bid=None, ask=None):
    a.current_time = t_ns
    a.get_known_bid_ask = lambda sym: (bid, 1 if bid else 0, ask, 1 if ask else 0)
    a.orders_placed = []
    a.informed_cycle()
    return list(a.orders_placed)


def events(a, typ):
    return [ev for _, t, ev in a.log if t == typ]


# ── T-N1 research update ───────────────────────────────────────────────────


def test_n1_research_update_exact():
    a = make_agent(sigma_r=50.0)
    a.x_hat, a.P = 100_000.0, 900.0
    K = a.research_update(100_300)
    K_exp = 900.0 / 3400.0
    assert abs(K - K_exp) < 1e-12
    assert abs(a.x_hat - (100_000.0 + K_exp * 300.0)) < 1e-9
    assert abs(a.P - (1.0 - K_exp) * 900.0) < 1e-9


def test_n1_research_reading_in_the_cycle():
    """The reading in a cycle uses variance sigma_r^2 and is logged with every key."""
    a = make_agent(sigma_r=50.0)
    cycle(a, 0, P0 - 1, P0 + 1)  # step 0
    a.next_research = 5 * NS
    cycle(a, 10 * NS, P0 - 1, P0 + 1)
    ev = events(a, "RESEARCH_READING")
    assert len(ev) == 1 and a.oracle.calls[-1] == (10 * NS, 2500.0)
    assert set(ev[0]) == {"y_r", "sigma_r", "K_r", "x_hat_before", "x_hat_after", "P_after"}


# ── T-N2 research clock ────────────────────────────────────────────────────


def test_n2_research_clock():
    """50 agents, T_r = 120 s, 2 hours, forced wakes every 10 s: about 60
    readings per agent on average (+/-10%), never more than one per wake."""
    counts = []
    for i in range(50):
        a = make_agent(seed=100 + i, T_r=120.0)
        per_wake = []
        for k in range(0, 7201, 10):
            n0 = len(events(a, "RESEARCH_READING"))
            cycle(a, k * NS, P0 - 1, P0 + 1)
            per_wake.append(len(events(a, "RESEARCH_READING")) - n0)
        assert max(per_wake) <= 1
        counts.append(sum(per_wake))
        # every reading is logged and is a call with variance sigma_r^2
        assert sum(1 for c in a.oracle.calls if c[1] == 2500.0) == counts[-1]
    mean = float(np.mean(counts))
    print(f"T-N2: mean readings per agent {mean:.1f} (expected about 60)")
    assert abs(mean / 60.0 - 1.0) <= 0.10


# ── T-N3 belief-anchored prices ────────────────────────────────────────────


def test_n3_prices_do_not_depend_on_the_book():
    books = [(99_900, 99_901), (100_500, 100_520)]
    priced = []
    for bid, ask in books:
        a = make_agent(rho=1e15)  # market readings negligible: x_hat, P fixed
        a.x_hat, a.P, a.t_last = 100_000.4, 400.0, 0
        a.next_research = 10**18
        a.get_known_bid_ask = lambda sym, b=bid, k=ask: (b, 1, k, 1)
        pr = a.belief_prices()
        orders = cycle(a, 1 * NS, bid, ask)
        q = events(a, "FUND_QUOTES")[-1]
        dec = events(a, "FUND_DECISION")[-1]
        priced.append((pr, (q["bid_price"], q["ask_price"]), dec))
        m = 2.0 + 0.25 * sqrt(a.P)
        assert dec["limit_price"] in (None, floor(a.x_hat - m), ceil(a.x_hat + m))
        assert all(p in (pr["buy"], pr["sell"], pr["bid"], pr["ask"]) for _, _, p in orders)
    (pa, qa, da), (pb, qb, db) = priced
    assert pa == pb and qa == qb
    assert da["m"] == db["m"] and da["h"] == db["h"]
    # the books disagree on the side (cheap book -> buy, rich book -> sell)
    assert da["side"] == "BUY" and da["limit_price"] == pa["buy"]
    assert db["side"] == "SELL" and db["limit_price"] == pa["sell"]


# ── T-N4 empty book ────────────────────────────────────────────────────────


def test_n4_first_wake_on_an_empty_book_quotes_both_sides():
    a = make_agent()
    orders = cycle(a, 0, None, None)
    assert a.x_hat is not None
    sides = {s: (q, p) for s, q, p in orders}
    assert set(sides) == {Side.BID, Side.ASK} and len(orders) == 2
    assert sides[Side.BID][1] < a.x_hat < sides[Side.ASK][1]
    q_q = max(1, floor(a.theta_q * (a.holdings["CASH"] + a.holdings["ABM"] * a.x_hat) / a.x_hat))
    assert sides[Side.BID][0] == q_q == sides[Side.ASK][0]
    assert events(a, "FUND_DECISION")[-1]["skipped_reason"] == "first_cycle"


def _run(kw, tmp, watch=None):
    from abides_core import abides
    from abides_markets.configs.rmsc04_ekf import build_config

    config = build_config(**kw)
    state = watch(config) if watch else None
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        end_state = abides.run(config)
    finally:
        os.chdir(cwd)
    return config, end_state, state


def _kw(**over):
    from api.jobs import run_config_kwargs

    from .sim_helpers import params

    num_ekf = over.pop("num_ekf_agents", 20)
    kw = run_config_kwargs(params(num_value=0, **over))
    kw.update(num_ekf_agents=num_ekf, fund_mode="informed", informed_design=DESIGN, abides_budget={"L": 2.0})
    return kw


def test_n4_market_without_value_agents_or_market_makers_trades(tmp_path):
    kw = _kw(num_mm=0, num_fund=0, num_mom=0, num_noise=100, num_ekf_agents=5)
    _, es, _ = _run(kw, tmp_path)
    h = es["agents"][0].order_books["ABM"].history
    n = sum(1 for x in h if x["type"] == "EXEC")
    print(f"T-N4: {n} executions in one hour (5 informed + 100 noise, no MM, no value)")
    assert n > 0


# ── T-N5 budget ────────────────────────────────────────────────────────────


def _watch_informed(config):
    seen, bad = [0], []
    for a in config["agents"]:
        if type(a).__name__ != "FundamentalistAgent" or a.mode != "informed":
            continue
        orig = a.order_executed

        def wrapped(order, _a=a, _orig=orig):
            _orig(order)
            p = float(order.fill_price)
            n = _a.holdings.get("ABM", 0)
            W = _a.holdings["CASH"] + n * p
            seen[0] += 1
            # post-fill position within [w_min, w_max] x W at the fill price, one share tolerance
            if n * p > INFORMED_W_MAX * W + p + 1e-6 or n * p < INFORMED_W_MIN * W - p - 1e-6:
                bad.append((_a.name, n, _a.holdings["CASH"], p, round(n * p / W, 4) if W else None))

        a.order_executed = wrapped
    return seen, bad


@pytest.fixture(scope="module")
def informed_market(tmp_path_factory):
    return _run(_kw(), tmp_path_factory.mktemp("inf"), _watch_informed)


def test_n5_budget_holds_at_every_fill(informed_market):
    _, es, (seen, bad) = informed_market
    print(f"T-N5: {seen[0]} informed fills checked, {len(bad)} outside the bounds")
    assert seen[0] > 50
    assert not bad, bad[:5]


def test_n5_logs_and_modes(informed_market):
    config, es, _ = informed_market
    funds = [es["agents"][i] for i in config["_ekf_agent_ids"]]
    assert len(funds) == 20 and all(a.mode == "informed" for a in funds)
    for a in funds:
        q = events(a, "FUND_QUOTES")
        assert q and set(q[0]) == {"bid_price", "bid_qty", "ask_price", "ask_qty", "blocked_sides"}
        d = events(a, "FUND_DECISION")
        assert {"mode", "m", "h", "x_hat"} <= set(d[0])
        assert all(ev["mode"] == "informed" for ev in d)
        ek = events(a, "EKF_UPDATE")
        assert ek and {"R_m", "rho", "K_m"} <= set(ek[-1])
    assert sum(len(events(a, "RESEARCH_READING")) for a in funds) > 20


# ── T-N6 price_only keeps I8 ───────────────────────────────────────────────


def test_n6_price_only_with_explicit_defaults_holds_i8(tmp_path):
    from .test_invariants import I8_EXPECTED
    from .test_scenarios import fingerprint

    extra = {"fund_mode": "price_only", "informed_design": None, "abides_budget": None}
    assert fingerprint(tmp_path, extra) == I8_EXPECTED


# ── T-N7 RNG ───────────────────────────────────────────────────────────────


def test_n7_oracle_path_unchanged_and_runs_reproducible(tmp_path):
    from .test_scenarios import fingerprint

    from abides_markets.configs.rmsc04_ekf import build_config
    from api.jobs import run_config_kwargs

    from .sim_helpers import params

    # I2 with informed agents: the true-value path is the same in the default
    # market and in the informed market of the same seed, before and after a run
    base = build_config(**run_config_kwargs(params()))
    kw = _kw()
    inf = build_config(**kw)
    t0, v0 = base["custom_properties"]["oracle"].path("ABM")
    t1, v1 = inf["custom_properties"]["oracle"].path("ABM")
    assert np.array_equal(t0, t1) and np.array_equal(v0, v1)
    cfg, _, _ = _run(_kw(), tmp_path)  # research readings draw from agents' RNGs only
    t2, v2 = cfg["custom_properties"]["oracle"].path("ABM")
    assert np.array_equal(t0, t2) and np.array_equal(v0, v2)
    # two fresh processes, same seed -> identical executions and holdings
    extra = {"num_value_agents": 0, "num_ekf_agents": 20, "fund_mode": "informed",
             "informed_design": DESIGN, "abides_budget": {"L": 2.0}}
    a = fingerprint(tmp_path, extra)
    b = fingerprint(tmp_path, extra)
    assert a == b and a["n_execs"] > 0


# ══════════════════════════════════════════════════════════════════════════
# spec v1.4.1 Part 2: learning from prices (T-N16 .. T-N19)
# ══════════════════════════════════════════════════════════════════════════

R_NOISE = 45_000.0
Q_LOOK = 180.0  # q * sigma_f2 * dt per look


def pl_agent(level, rho, eps_thr, a_pl=0.3):
    n_pl = {"mod": 3, "strong": 2}[level]
    a = make_agent(rho=rho, price_learning=level, n_pl=n_pl, eps_thr=eps_thr, a_pl=a_pl)
    a.x_hat, a.P = 0.0, 900.0
    return a


def look(a, mid):
    """One market look as in informed_cycle step 1 + 3 (fixed R_noise)."""
    a.P += Q_LOOK
    R_m, pl = a.price_learning_step(mid, R_NOISE)
    a.x_hat, a.P, K = a.correction(a.x_hat, a.P, mid, R_m)
    return pl, K


def test_n16_off_is_v14_informed(tmp_path):
    """Absent key and "price_learning": "off" give identical agents and markets."""
    from abides_markets.configs.rmsc04_ekf import build_config

    from .test_scenarios import fingerprint

    base = _kw()
    off = _kw()
    off["informed_design"] = {**DESIGN, "price_learning": "off"}
    ca, cb = build_config(**base), build_config(**off)
    keys = ["er_window", "delta", "sigma_n", "rho", "m0", "kappa_m", "h0", "theta_q", "T_r", "sigma_r",
            "wake_mean", "price_learning", "starting_cash"]
    for i, j in zip(ca["_ekf_agent_ids"], cb["_ekf_agent_ids"]):
        A, B = ca["agents"][i], cb["agents"][j]
        assert all(getattr(A, k) == getattr(B, k) for k in keys)
        assert A.price_learning == "off"
    ex = {"num_value_agents": 0, "num_ekf_agents": 20, "fund_mode": "informed", "abides_budget": {"L": 2.0}}
    fa = fingerprint(tmp_path, {**ex, "informed_design": DESIGN})
    fb = fingerprint(tmp_path, {**ex, "informed_design": {**DESIGN, "price_learning": "off"}})
    assert fa == fb and fa["n_execs"] > 0


def test_n17_maths_exact():
    a = pl_agent("mod", rho=20.0, eps_thr=1.5, a_pl=0.25)
    mids = [300.0, 2000.0, 2100.0, 1900.0, -50.0, 2050.0, 2000.0, 2000.0, 400.0]
    x, P, hist, eb = 0.0, 900.0, [], 0.0
    for mid in mids:
        P += Q_LOOK
        a.P += Q_LOOK
        R_m, pl = a.price_learning_step(mid, R_NOISE)
        # reference, spec v1.4.1 §2.2
        y = mid - x
        eps = y * y / (P + R_NOISE)
        hist = (hist + [eps])[-3:]
        e_pers = min(hist) if len(hist) == 3 else 0.0
        eb = 0.75 * eb + 0.25 * e_pers
        g = min(20.0, max(1.0, eb / 1.5))
        if g > 1:
            P = max(P, (eb - 1.5) * (P + R_NOISE))
        rho_eff = 20.0 / g
        Rm = rho_eff * R_NOISE
        assert abs(a.P - P) < 1e-9 * max(1.0, P) and abs(R_m - Rm) < 1e-9 * Rm
        assert abs(a.epsbar - eb) < 1e-12 and abs(pl["g"] - round(g, 6)) < 1e-12
        assert 1.0 <= g <= 20.0 and rho_eff >= 1.0
        K = P / (P + Rm)
        a.x_hat, a.P, K_a = a.correction(a.x_hat, a.P, mid, R_m)
        x, P = x + K * y, (1 - K) * P
        assert abs(K_a - K) < 1e-12 and abs(a.x_hat - x) < 1e-9 * max(1.0, abs(x)) and abs(a.P - P) < 1e-9 * P


@pytest.mark.parametrize("rho", [3.0, 100.0])
@pytest.mark.parametrize("eps_thr", [1.0, 4.0])
def test_n18_mod_behaviour(rho, eps_thr):
    a = pl_agent("mod", rho, eps_thr)
    adopted = []
    for _ in range(4):
        look(a, 2000.0)
        adopted.append(a.x_hat / 2000.0)
    print(f"mod rho {rho} eps_thr {eps_thr}: adopted {[round(v, 3) for v in adopted]}")
    assert adopted[2] >= 0.50 and adopted[3] >= 0.90
    b = pl_agent("mod", rho, eps_thr)  # two-look blip, then the price returns to the belief
    look(b, 800.0)
    look(b, 800.0)
    for _ in range(5):
        look(b, b.x_hat)
    assert abs(b.x_hat) < 20.0


@pytest.mark.parametrize("rho", [3.0, 100.0])
@pytest.mark.parametrize("eps_thr", [0.5, 2.0])
def test_n18_strong_behaviour(rho, eps_thr):
    a = pl_agent("strong", rho, eps_thr)
    look(a, 2000.0)
    look(a, 2000.0)
    print(f"strong rho {rho} eps_thr {eps_thr}: adopted {a.x_hat / 2000.0:.3f} at look 2")
    assert a.x_hat / 2000.0 >= 0.70


@pytest.mark.parametrize("level,eps_thr", [("mod", 1.0), ("mod", 4.0), ("strong", 0.5), ("strong", 2.0)])
def test_n18_normal_noise_never_triggers(level, eps_thr):
    rng = np.random.default_rng(18)
    for rho in (3.0, 100.0):
        a = pl_agent(level, rho, eps_thr)
        for gap in rng.normal(0.0, 40.0, 3000):
            pl, _ = look(a, a.x_hat + gap)
            assert pl["g"] == 1.0 and not pl["P_inflated"]


def test_n18_learning_logged_in_a_market(tmp_path):
    """A 1-hour market with "mod" learning runs, draws eps_thr/a_pl in range and
    logs the §2.2 keys in EKF_UPDATE."""
    kw = _kw()
    kw["informed_design"] = {**DESIGN, "price_learning": "mod"}
    config, es, _ = _run(kw, tmp_path)
    funds = [es["agents"][i] for i in config["_ekf_agent_ids"]]
    assert all(a.price_learning == "mod" and a.n_pl == 3 and 1.0 <= a.eps_thr <= 4.0 and 0.2 <= a.a_pl <= 0.4
               for a in funds)
    ev = [e for a in funds for _, t, e in a.log if t == "EKF_UPDATE"]
    assert ev and {"eps", "e_pers", "epsbar", "g", "rho_eff", "P_inflated"} <= set(ev[-1])
    assert all(1.0 <= e["g"] for e in ev) and all(e["rho_eff"] >= 1.0 - 1e-9 for e in ev)

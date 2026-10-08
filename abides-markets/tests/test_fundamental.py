"""Unit tests for the FundamentalistAgent (FinVerse spec v1.1, Part 2 / 6.2).

No simulation kernel: the agent is built directly, the order book is stubbed
through get_known_bid_ask, and orders are captured instead of sent.
"""

from math import atanh, ceil, sqrt

import numpy as np
import pytest

from abides_markets.agents.fundamental import (
    NEWS_HORIZON_S,
    SIGMA_F_FLOOR,
    FundamentalistAgent,
)
from abides_markets.orders import Side

P0 = 100_000  # cents
CASH = 10_000_000
DT_NS = 10_000_000_000  # 10 s


def make_agent(**overrides):
    params = dict(
        id=0,
        symbol="ABM",
        starting_cash=CASH,
        reference_price=P0,
        initial_exposure=0.5,
        er_window=10,
        delta=0.0015,
        lambda_er=1.0,
        q=1.0,
        a_max=0.8,
        z0=2.0,
        s_max=0.15,
        b_f=0.02,
        k_news=1.5,
        random_state=np.random.RandomState(0),
    )
    params.update(overrides)
    agent = FundamentalistAgent(**params)
    agent.orders_placed = []
    agent.place_limit_order = lambda sym, qty, side, price: agent.orders_placed.append(
        (side, qty, price)
    )
    return agent


def start(agent, x_hat=float(P0), P=250_000.0, t_ns=0, mid=float(P0)):
    """Put the agent past its oracle initialisation at time t_ns."""
    agent.x_hat, agent.P = x_hat, P
    agent.price_log.append(mid)
    agent.time_log.append(t_ns)


def step(agent, t_ns, bid, ask):
    """One wake cycle against a stubbed quote."""
    agent.current_time = t_ns
    agent.get_known_bid_ask = lambda sym: (bid, 1, ask, 1)
    agent.execute_strategy()


def events(agent, typ):
    return [ev for _, t, ev in agent.log if t == typ]


# ── T-F1 No nudge ──────────────────────────────────────────────────────────


def test_no_nudge_after_order():
    agent = make_agent()
    start(agent, x_hat=P0 + 2_000.0, P=10_000.0)  # strong edge -> order
    returned = {}
    real = agent.correction

    def spy(*args):
        out = real(*args)
        returned["x_hat"] = out[0]
        return out

    agent.correction = spy
    step(agent, DT_NS, P0, P0 + 2)  # mid rises vs previous: old step 9 would nudge
    assert agent.orders_placed, "expected an order"
    assert agent.x_hat == returned["x_hat"]


# ── T-F2 Q keeps learning ──────────────────────────────────────────────────


def _run_constant(agent, n, mid=P0):
    for i in range(1, n + 1):
        step(agent, i * DT_NS, mid - 1, mid + 1)
    return [ev["K"] for ev in events(agent, "EKF_UPDATE")]


def test_gain_converges_and_stays_positive():
    agent = make_agent()
    start(agent)
    K = _run_constant(agent, 2000)
    assert min(K) > 0.003
    last = np.array(K[-100:])
    assert abs(last[-1] - last[0]) / last[0] < 0.01
    assert agent.P > 1.0
    # constant mid: no measured value speed, so the floor applies
    assert agent.sigma_f2_hat == pytest.approx(SIGMA_F_FLOOR)


# ── T-F3 Tracking ──────────────────────────────────────────────────────────


def test_tracks_a_step():
    agent = make_agent()
    start(agent)
    K_ss = _run_constant(agent, 2000)[-1]
    x0 = agent.x_hat
    n_max = int(ceil(3 / K_ss))
    t0 = 2000 * DT_NS
    jump = 200
    for i in range(1, n_max + 1):
        step(agent, t0 + i * DT_NS, P0 + jump - 1, P0 + jump + 1)
    assert agent.x_hat - x0 >= 0.9 * jump


# ── T-F4 sigma_f2_hat ──────────────────────────────────────────────────────


def _sigma_f2_after_hour(seed, var_per_s=5.0, noise_sd=2.0, dt_s=10.0):
    rng = np.random.RandomState(seed)
    agent = make_agent()
    n = int(3600 / dt_s) + 1
    value = P0 + np.cumsum(rng.normal(0, sqrt(var_per_s * dt_s), n))
    mid = value + rng.normal(0, noise_sd, n)
    for i in range(n):
        t = int(i * dt_s * 1e9)
        agent.time_log.append(t)
        agent.price_log.append(float(mid[i]))
        agent.update_sigma_f2(t, float(mid[i]))
    return agent.sigma_f2_hat


def test_sigma_f2_estimate():
    """Deviation from spec 6.2 T-F4 (reported): the F3 estimator (300 s lag,
    60-update EWMA at 10 s wakes) averages only a few independent 5-minute
    changes, so a single 1-hour path lands within +/-30% of the truth only
    ~40% of the time (5th-95th percentile over seeds: ~2.0-10.3 for a true
    5). The estimator is unbiased, so the +/-30% bound is checked on the
    mean over 50 independent paths; the spread is bounded loosely."""
    est = np.array([_sigma_f2_after_hour(s) for s in range(50)])
    assert est.mean() == pytest.approx(5.0, rel=0.3)
    assert np.median(est) == pytest.approx(5.0, rel=0.3)
    assert np.all(est > 0.5) and np.all(est < 25)


def test_sigma_f2_uses_long_lag_only():
    agent = make_agent()
    for i in range(29):  # 280 s of data: no sample 300 s old yet
        agent.time_log.append(i * DT_NS)
        agent.price_log.append(P0 + 50.0 * (i % 2))
        agent.update_sigma_f2(i * DT_NS, agent.price_log[-1])
    assert agent.sigma_f2_hat == 3.0  # prior untouched


# ── T-F5 Sizing ────────────────────────────────────────────────────────────


def test_zero_edge_holds_endowment():
    agent = make_agent()
    agent.x_hat, agent.P = float(P0), 2_500.0
    dec = agent.target_position(float(P0), 0.5)
    assert dec["w_star"] == pytest.approx(0.5)
    assert dec["d"] == 0 and dec["skipped_reason"] == "dead_band"


def test_target_reached_in_capped_steps_without_creep():
    agent = make_agent()
    mid, C = float(P0), 0.5
    agent.P = 2_500.0
    agent.x_hat = mid + 50 * sqrt(agent.P)  # z = 50: tanh saturates
    w_star = 0.5 + agent.a_max * C
    steps = []
    for _ in range(40):
        dec = agent.target_position(mid, C)
        cash, n = agent.holdings["CASH"], agent.holdings["ABM"]
        W = cash + n * mid
        assert abs(dec["d"]) <= agent.s_max * W / mid
        steps.append(dec["d"])
        agent.holdings["CASH"] = cash - dec["d"] * mid
        agent.holdings["ABM"] = n + dec["d"]
    W = agent.holdings["CASH"] + agent.holdings["ABM"] * mid
    assert agent.holdings["ABM"] == round(w_star * W / mid)  # 90 shares
    assert all(d > 0 for d in steps[:3]) and all(d == 0 for d in steps[-10:])


def test_dead_band_blocks_small_orders():
    agent = make_agent(b_f=0.03)
    mid, C = float(P0), 0.5
    agent.P = 10_000.0
    # w_star = 0.52 -> d_star = 2 shares = 2% of W < 3%
    z = agent.z0 * atanh(0.02 / (agent.a_max * C))
    agent.x_hat = mid + z * sqrt(agent.P)
    dec = agent.target_position(mid, C)
    assert dec["d_star"] == 2 and dec["d"] == 0 and dec["skipped_reason"] == "dead_band"
    agent.b_f = 0.01  # 2% >= 1%: allowed
    assert agent.target_position(mid, C)["d"] == 2


# ── T-F6 Side from d ───────────────────────────────────────────────────────


def test_side_from_d_takes_profit():
    agent = make_agent()
    start(agent, P=10_000.0)
    agent.holdings = {"CASH": CASH - 90 * P0, "ABM": 90}  # 90% stock at mid P0
    mid = float(P0)
    # small positive z giving w_star = 0.6 (C = 0.5)
    z = agent.z0 * atanh(0.1 / (agent.a_max * 0.5))
    # v1.2: z = gap / sqrt(P + R), with R the variance of this very update
    agent.correction = lambda xp, Pp, zobs, R: (mid + z * sqrt(Pp + R), Pp, 0.01)
    step(agent, DT_NS, P0 - 1, P0 + 1)
    dec = events(agent, "FUND_DECISION")[-1]
    assert dec["z"] > 0 and dec["w_star"] == pytest.approx(0.6, abs=1e-3)
    assert dec["side"] == "SELL"
    side, qty, price = agent.orders_placed[-1]
    assert side == Side.ASK and qty == -dec["d"] > 0
    assert agent.D_prev == 1.0  # caution direction still follows sign(x_hat - mid)


def test_long_only_and_no_leverage():
    rng = np.random.RandomState(3)
    for _ in range(300):
        agent = make_agent()
        start(agent, P=float(rng.uniform(100, 1e5)))
        cash, n = int(rng.uniform(0, 2 * CASH)), int(rng.randint(0, 200))
        agent.holdings = {"CASH": cash, "ABM": n}
        agent.x_hat = P0 + float(rng.normal(0, 500))
        step(agent, DT_NS, P0 - 2, P0 + 2)
        for side, qty, price in agent.orders_placed:
            assert qty >= 1
            if side == Side.BID:
                assert qty * price <= cash
            else:
                assert qty <= n


# ── T-F7 News ──────────────────────────────────────────────────────────────


def test_news_shift_scaled_by_volatility():
    agent = make_agent(k_news=2.0)
    agent.x_hat, agent.P, agent.sigma_f2_hat = float(P0), 900.0, 3.0
    shift = agent.apply_news(0.9, "Company announces record quarterly earnings")
    expected = 0.9 * 2.0 * sqrt(3.0 * NEWS_HORIZON_S)
    assert shift == pytest.approx(expected)
    assert expected == pytest.approx(132.27, abs=0.01)  # +$1.32
    assert agent.x_hat == pytest.approx(P0 + expected)
    assert agent.P == pytest.approx(900.0 + expected ** 2)
    ev = events(agent, "NEWS_RECEIVED")[-1]
    assert set(ev) == {
        "headline", "sentiment", "shift", "sigma_move",
        "x_hat_before", "x_hat_after", "P_before", "P_after",
    }
    assert ev["x_hat_before"] == P0 and ev["shift"] == pytest.approx(expected, abs=1e-4)
    # negative news moves the belief down
    assert agent.apply_news(-0.5) < 0


def test_ekf_update_log_keys():
    agent = make_agent()
    start(agent)
    step(agent, DT_NS, P0 - 1, P0 + 1)
    ev = events(agent, "EKF_UPDATE")[-1]
    assert {"mid", "x_hat", "P", "R", "K", "ER", "Q", "dt", "sigma_f2"} <= set(ev)
    assert ev["dt"] == 10.0 and ev["Q"] == pytest.approx(agent.q * 3.0 * 10.0)


# ── spec v1.2: signal-to-noise edge (T-F8 .. T-F10) ───────────────────────


def _v12_agent(gap, P=900.0, R=43_681.0):
    """Holdings at the 50% endowment, W = $100k, mid = $1000."""
    agent = make_agent(a_max=0.9, z0=2.1)  # b_f default 0.02, s_max 0.15
    agent.P, agent.R_last = P, R
    agent.x_hat = P0 + gap
    return agent


def test_z_uses_p_plus_r():
    """T-F8."""
    agent = _v12_agent(100.0, P=900.0, R=40_000.0)
    dec = agent.target_position(float(P0), 0.5)
    assert dec["z"] == pytest.approx(100.0 / sqrt(40_900.0), abs=1e-9)
    assert dec["z_den"] == pytest.approx(sqrt(40_900.0))


def test_z_guard_zero_variance():
    agent = _v12_agent(100.0, P=0.0, R=0.0)
    assert agent.target_position(float(P0), 0.5)["z"] == 0.0


def test_typical_gap_holds():
    """T-F9: a 13-cent gap is 0.06 of a normal wiggle -> no order.

    Target: w* = 0.5 + 0.45 tanh(0.0616 / 2.1) = 0.513, i.e. about 1.3 shares,
    which rounds to 1 share = 1% of W, inside the 2% dead band (b_f default)."""
    agent = _v12_agent(13.0)
    dec = agent.target_position(float(P0), 0.5)
    assert dec["z"] == pytest.approx(13.0 / sqrt(900.0 + 43_681.0))
    assert dec["d"] == 0 and dec["skipped_reason"] == "dead_band"
    # end to end: no order placed
    agent = _v12_agent(13.0)
    agent.price_log.append(float(P0)); agent.time_log.append(0)
    agent.correction = lambda xp, Pp, zobs, R: (agent.x_hat, 900.0, 0.01)
    agent._compute_observation_variance = lambda mid: 43_681.0
    step(agent, DT_NS, P0 - 1, P0 + 1)
    assert agent.orders_placed == []
    assert events(agent, "FUND_DECISION")[-1]["z_den"] == pytest.approx(sqrt(900.0 + 43_681.0), abs=1e-3)


def test_large_gap_buys_within_step_cap():
    """T-F10: a $6 gap (z = 2.84) buys, capped at s_max * W / mid."""
    agent = _v12_agent(600.0)
    agent.price_log.append(float(P0)); agent.time_log.append(0)
    agent.correction = lambda xp, Pp, zobs, R: (agent.x_hat, 900.0, 0.01)
    agent._compute_observation_variance = lambda mid: 43_681.0
    step(agent, DT_NS, P0 - 1, P0 + 1)
    (side, qty, price), = agent.orders_placed
    W = CASH  # holdings at the endowment, valued at mid = P0
    assert side == Side.BID and 1 <= qty <= agent.s_max * W / P0

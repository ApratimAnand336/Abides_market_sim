"""Unit tests for the MomentumEKFAgent (FinVerse spec v1.0, Part H.2).

No simulation kernel is needed: the maths is tested through the pure helpers
in momentum_ekf.py, and the decision logic by building an agent directly and
feeding it scripted observations.
"""

from math import exp, log

import numpy as np
import pytest

from abides_markets.agents.fundamental import FundamentalistAgent
from abides_markets.agents.momentum_ekf import (
    BEAR,
    BULL,
    NEUTRAL,
    STOP,
    WATCH,
    MomentumEKFAgent,
    apply_news,
    endowment,
    kaufman_er,
    kf_correct,
    kf_predict,
    obs_variance,
    ratchet_bear,
    ratchet_bull,
    regime_update,
    target_exposure,
    target_shares_delta,
    transition,
    trend_strength,
    warmup_fit,
)
from abides_markets.orders import Side

P0_CENTS = 100_000
CASH = 10_000_000


# ── helpers ────────────────────────────────────────────────────────────────


def run_filter(
    t,
    z,
    N_w=20,
    n_er=15,
    tau=600.0,
    lambda_er=3.0,
    kappa_R=1.0,
    c_P=2.0,
    kappa_l=0.2,
    kappa_v=1.0,
    a_eps=0.2,
    eps_thr=3.0,
    g_max=10.0,
):
    """Warm-up + filter loop built from the pure helpers, exactly as
    MomentumEKFAgent.process_observation chains them. Returns per-update
    (x, P, T)."""
    sigma_q2 = 1.0 / (12.0 * exp(z[N_w - 1]) ** 2)
    fit = warmup_fit(t[:N_w], z[:N_w], sigma_q2, c_P, kappa_R, kappa_l, kappa_v, tau)
    x, P = fit["x"], fit["P"]
    epsbar, g_Q = 1.0, 1.0
    out = []
    for k in range(N_w, len(z)):
        F, Q = transition(t[k] - t[k - 1], tau, fit["sigma_l2"], fit["sigma_vinf"], g_Q)
        x_minus, P_minus = kf_predict(x, P, F, Q)
        er = kaufman_er(z[k - n_er : k + 1])
        R = obs_variance(fit["R_base"], lambda_er, er)
        x, P, y, S, _ = kf_correct(x_minus, P_minus, z[k], R)
        _, epsbar, g_Q = regime_update(epsbar, y, S, a_eps, eps_thr, g_max)
        out.append((x.copy(), P.copy(), trend_strength(x, P)))
    return out


def make_agent(**overrides):
    params = dict(
        id=0,
        symbol="ABM",
        starting_cash=CASH,
        reference_price=P0_CENTS,
        initial_exposure=0.5,
        N_w=16,
        n_er=10,
        tau=600.0,
        theta_in=2.0,
        theta_out=0.75,
        ER_min=0.3,
        k_stop=3.0,
        k_re=0.35,
        k_add=0.5,
        e_max=0.9,
        mu_m=50.0,
        wake_mean=30.0,
        random_state=np.random.RandomState(0),
    )
    params.update(overrides)
    return MomentumEKFAgent(**params)


def neutral_agent(**overrides):
    """Agent in NEUTRAL with 10 flat observations of history (dt = 30 s)."""
    agent = make_agent(**overrides)
    agent.mstate = NEUTRAL
    for i in range(10):
        agent.t_log.append(30.0 * i)
        agent.price_log.append(float(P0_CENTS))
    return agent


def sm_step(agent, t, p, T, v=None, er=0.9, sigma_tau=10.0, a=0.6):
    """One state-machine + ratchet step with scripted inputs (Parts E, F.3)."""
    v = T * 1e-7 if v is None else v
    agent.t_log.append(t)
    agent.price_log.append(p)
    hi, lo = agent._window_extremes(t)
    exit_kind, entered = agent._step_state_machine(t, p, T, er, v, hi, lo, sigma_tau, a)
    _, e_target = agent._target_with_ratchet(p, a, v, sigma_tau, entered)
    return exit_kind, entered, e_target


def is_psd(P, tol=0.0):
    return np.all(np.linalg.eigvalsh(P) >= -tol)


# ── 1. Pure trend ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("seed", range(5))
def test_pure_trend_detected(seed):
    """Note: the damped-trend model has a steady-state bias of v_hat toward 0
    whose size depends on how Q splits drift between level (kappa_l) and
    velocity (kappa_v). The 20% tolerance holds for low kappa_l / high
    kappa_v (used here, both inside the Part G ranges); at kappa_l = 0.5,
    kappa_v = 1 the steady-state v_hat is ~55% of v."""
    rng = np.random.RandomState(seed)
    n = 20 + 50
    t = np.cumsum(rng.uniform(5, 60, n))  # irregular dt
    v = 2e-6  # log-return per second
    z = log(P0_CENTS) + v * t + rng.normal(0, 2e-6, n)
    x, P, T = run_filter(t, z, tau=1800.0, kappa_l=0.05, kappa_v=2.0)[-1]
    assert abs(x[1] - v) / v < 0.2
    assert T > 2


# ── 2. Pure noise ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("seed", range(5))
def test_pure_noise_rarely_signals(seed):
    rng = np.random.RandomState(100 + seed)
    n = 520
    t = np.cumsum(rng.uniform(5, 60, n))
    dt = np.diff(t, prepend=0.0)
    z_iid = log(P0_CENTS) + rng.normal(0, 5e-5, n)
    z_walk = log(P0_CENTS) + np.cumsum(rng.normal(0, 1, n) * 1e-5 * np.sqrt(dt))
    for z in (z_iid, z_walk):
        Ts = [T for _, _, T in run_filter(t, z)]
        assert np.mean(np.abs(Ts) > 2) < 0.15


# ── 3. Numerical stability ─────────────────────────────────────────────────


def test_stability_long_run():
    rng = np.random.RandomState(7)
    n = 10_000 + 20
    dt = rng.uniform(1, 120, n)
    t = np.cumsum(dt)
    jumps = rng.binomial(1, 0.01, n) * rng.normal(0, 2e-3, n)
    z = log(P0_CENTS) + np.cumsum(rng.normal(0, 1, n) * 2e-5 * np.sqrt(dt) + jumps)
    for x, P, T in run_filter(t, z):
        assert np.all(np.isfinite(x)) and np.all(np.isfinite(P)) and np.isfinite(T)
        assert P[0, 1] == P[1, 0]
        assert np.all(np.linalg.eigvalsh(P) > 0)


# ── 4. Large dt ────────────────────────────────────────────────────────────


def test_large_dt_refreshes_velocity_noise():
    sigma_vinf = 3e-7
    F, Q = transition(1e6, 600.0, 1e-10, sigma_vinf, 1.0)
    assert Q[1, 1] == pytest.approx(sigma_vinf ** 2, rel=1e-9)
    assert F[1, 1] == pytest.approx(0.0, abs=1e-12)
    # monotone approach: longer gaps never refresh less
    q = [transition(dt, 600.0, 1e-10, sigma_vinf, 1.0)[1][1, 1] for dt in (1, 60, 600, 6000)]
    assert q == sorted(q) and q[-1] < sigma_vinf ** 2


# ── 5. News ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("s_n", [-1.0, -0.4, 0.3, 0.9])
def test_news_primes_velocity_only(s_n):
    x = np.array([log(P0_CENTS), 1e-7])
    P = np.array([[4e-9, 3e-12], [3e-12, 5e-14]])
    x_new, P_new = apply_news(x, P, s_n, eta=0.3, rho=3.0, sigma_vinf=4e-7)
    assert x_new[0] == x[0]
    assert np.sign(x_new[1] - x[1]) == np.sign(s_n)
    assert is_psd(P_new)
    assert P_new[1, 1] > P[1, 1]
    assert P_new[0, 1] == P_new[1, 0]


def test_news_ignored_during_warmup():
    agent = make_agent()
    agent.on_news(0.9, "headline")
    assert agent.x_hat is None
    assert not any(e[1] == "NEWS_RECEIVED" for e in agent.log)


# ── 6. State machine ───────────────────────────────────────────────────────


def test_breakout_entry_requires_all_three_conditions():
    # T just below theta_in
    agent = neutral_agent()
    sm_step(agent, 300, 100_010, T=1.9)
    assert agent.mstate == NEUTRAL
    # choppy (ER below ER_min)
    agent = neutral_agent()
    sm_step(agent, 300, 100_010, T=2.5, er=0.2)
    assert agent.mstate == NEUTRAL
    # no breakout (price not above the tau-window high)
    agent = neutral_agent()
    sm_step(agent, 300, P0_CENTS, T=2.5)
    assert agent.mstate == NEUTRAL
    # all three
    agent = neutral_agent()
    _, entered, _ = sm_step(agent, 300, 100_010, T=2.5)
    assert entered and agent.mstate == BULL
    assert agent.state_history[-1]["reason"] == "BREAKOUT"
    # mirror
    agent = neutral_agent()
    sm_step(agent, 300, 99_990, T=-2.5)
    assert agent.mstate == BEAR


def test_no_breakout_without_window_history():
    agent = make_agent(tau=120.0)
    agent.mstate = NEUTRAL
    agent.t_log, agent.price_log = [0.0], [float(P0_CENTS)]
    sm_step(agent, 500.0, 100_100, T=5.0)  # previous obs is older than tau
    assert agent.mstate == NEUTRAL


def test_pyramiding_adds_only_at_new_highs():
    agent = neutral_agent()
    sigma_tau, k_add = 10.0, agent.k_add  # add spacing = 5 cents
    _, _, e = sm_step(agent, 300, 100_010, T=2.5, a=0.3, sigma_tau=sigma_tau)
    e_entry = 0.5 + 0.3 * (0.9 - 0.5)
    assert e == pytest.approx(e_entry) and agent.e_cap == pytest.approx(e_entry)

    # higher conviction but no new high beyond p_add + k_add*sigma_tau: no add
    _, _, e = sm_step(agent, 330, 100_012, T=2.5, a=0.8, sigma_tau=sigma_tau)
    assert e == pytest.approx(e_entry)
    # a dip: never averages down
    _, _, e = sm_step(agent, 360, 100_000, T=2.5, a=0.8, sigma_tau=sigma_tau)
    assert e == pytest.approx(e_entry) and agent.e_cap == pytest.approx(e_entry)
    assert agent.mstate == BULL

    # new high beyond the add spacing: confirmation event
    p_new = 100_010 + k_add * sigma_tau
    _, _, e = sm_step(agent, 390, p_new, T=2.5, a=0.8, sigma_tau=sigma_tau)
    e_high = 0.5 + 0.8 * (0.9 - 0.5)
    assert e == pytest.approx(e_high) and agent.p_add == p_new

    # exposure may decrease at any time
    _, _, e = sm_step(agent, 420, p_new, T=2.5, a=0.2, sigma_tau=sigma_tau)
    assert e == pytest.approx(0.5 + 0.2 * 0.4)
    # ... and never exceeds the confirmed cap without a new add event
    _, _, e = sm_step(agent, 450, p_new - 3, T=2.5, a=0.99, sigma_tau=sigma_tau)
    assert e <= agent.e_cap + 1e-12 and agent.e_cap == pytest.approx(e_high)


def test_bear_ratchet_mirror():
    agent = neutral_agent()
    _, _, e = sm_step(agent, 300, 99_990, T=-2.5, a=0.3, sigma_tau=10.0)
    assert agent.mstate == BEAR and e == pytest.approx(0.5 - 0.3 * 0.5)
    _, _, e = sm_step(agent, 330, 99_995, T=-2.5, a=0.8, sigma_tau=10.0)  # bounce
    assert e == pytest.approx(0.35)
    _, _, e = sm_step(agent, 360, 99_984, T=-2.5, a=0.8, sigma_tau=10.0)  # new low
    assert e == pytest.approx(0.5 - 0.8 * 0.5)


def test_trailing_stop_then_reentry():
    agent = neutral_agent()
    sm_step(agent, 300, 100_010, T=2.5)
    sm_step(agent, 330, 100_040, T=2.5)  # peak 100_040
    kind, _, _ = sm_step(agent, 360, 100_015, T=2.5)  # 25 < 3*10 below peak
    assert kind is None and agent.mstate == BULL
    kind, _, e = sm_step(agent, 390, 100_009, T=2.5)  # 31 below peak
    assert kind == STOP and agent.mstate == WATCH
    assert agent.L == 100_040 and agent.came_from == BULL and e == 0.5

    margin = agent.k_re * 10.0
    sm_step(agent, 420, 100_040 + margin - 1, T=1.0)  # not past L + margin
    assert agent.mstate == WATCH
    sm_step(agent, 450, 100_040 + margin + 1, T=-0.5)  # past L but v < 0
    assert agent.mstate == WATCH
    _, entered, _ = sm_step(agent, 480, 100_040 + margin + 1, T=0.5)  # v > 0
    assert entered and agent.mstate == BULL
    assert agent.state_history[-1]["reason"] == "REENTRY"


def test_fade_exit_and_watch_timeout():
    agent = neutral_agent()
    sm_step(agent, 300, 100_010, T=2.5)
    kind, _, _ = sm_step(agent, 330, 100_011, T=0.7)
    assert kind == "FADE" and agent.mstate == WATCH
    sm_step(agent, 330 + agent.tau - 1, 100_011, T=0.0)
    assert agent.mstate == WATCH
    sm_step(agent, 330 + agent.tau, 100_011, T=0.0)
    assert agent.mstate == NEUTRAL


def test_watch_allows_opposite_breakout():
    agent = neutral_agent()
    sm_step(agent, 300, 100_010, T=2.5)
    sm_step(agent, 330, 100_011, T=0.5)  # FADE -> WATCH (came_from BULL)
    assert agent.mstate == WATCH
    sm_step(agent, 360, 99_950, T=-2.5)
    assert agent.mstate == BEAR


def test_no_flip_flop_between_thresholds():
    rng = np.random.RandomState(3)
    agent = neutral_agent()
    # NEUTRAL: T hovering below theta_in never enters, even on breakouts
    for i in range(30):
        sm_step(agent, 300 + 30 * i, 100_000 + 2 * (i + 1), T=rng.uniform(0.8, 1.99))
    assert agent.mstate == NEUTRAL and agent.state_history == []
    # BULL: T hovering above theta_out never exits
    sm_step(agent, 1300, 100_200, T=2.5)
    for i in range(30):
        sm_step(agent, 1330 + 30 * i, 100_200 + i, T=rng.uniform(0.76, 1.99))
    assert agent.mstate == BULL and len(agent.state_history) == 1


def test_end_to_end_uptrend_enters_and_buys():
    """Scripted bid/ask path through process_observation (no kernel).

    Warm-up noise is comparable to the later trend steps. (With a near-flat
    warm-up, F.1's volatility scaling g = sqrt(sigma_ref^2 / sigma_hat^2)
    reads the trend itself as ~10x volatility, shrinks a to ~0.1 and the
    dead-band then suppresses every order.)"""
    agent = make_agent()
    rng = np.random.RandomState(11)
    t_ns, orders = 0, []
    bid = P0_CENTS
    for i in range(16 + 40):
        t_ns += int(30e9)
        if i < 16:
            bid = P0_CENTS + int(rng.randint(-10, 11))
        else:
            bid += 10 + int(rng.randint(-3, 4))
        order = agent.process_observation(t_ns, bid, bid + 1)
        if order is not None:
            orders.append((agent.mstate, order))
    assert any(e[1] == "MOM_WARMUP_DONE" for e in agent.log)
    assert any(h["to"] == BULL for h in agent.state_history)
    buys = [o for state, o in orders if o[0] == Side.BID]
    assert buys and all(state == BULL for state, o in orders if o[0] == Side.BID)


def test_missing_quote_skips_cycle():
    agent = make_agent()
    assert agent.process_observation(1, None, 100_001) is None
    assert agent.process_observation(2, 100_000, None) is None
    assert agent.price_log == []


# ── 7. Sizing ──────────────────────────────────────────────────────────────


def _warm_agent():
    agent = make_agent()
    rng = np.random.RandomState(5)
    for i in range(20):
        b = P0_CENTS + int(rng.randint(-3, 4))
        agent.process_observation(int(30e9) * (i + 1), b, b + 1)
    assert agent.x_hat is not None
    return agent


def test_orders_respect_cash_and_holdings():
    agent = _warm_agent()
    rng = np.random.RandomState(9)
    for _ in range(2000):
        cash = int(rng.uniform(0, 2 * CASH))
        n = int(rng.randint(0, 200))
        agent.holdings = {"CASH": cash, "ABM": n}
        agent.mstate = rng.choice([NEUTRAL, BULL, BEAR, WATCH])
        bid = int(rng.randint(99_000, 101_000))
        ask = bid + int(rng.randint(1, 5))
        p = (bid + ask) / 2
        order = agent._decide_order(
            bid, ask, p, rng.normal(0, 1e-6), rng.uniform(0, 1), 0.5, 0.5, 0.5, 1.0,
            0.5, rng.uniform(0, 1), rng.choice([None, STOP, "FADE"]),
        )
        if order is None:
            continue
        side, qty, price = order
        assert qty >= 1
        if side == Side.BID:
            assert qty * price <= cash and bid <= price <= ask
        else:
            assert qty <= n and bid <= price <= ask


def test_e_target_within_bounds():
    rng = np.random.RandomState(4)
    e0, e_max, e_min = 0.5, 0.85, 0.0
    for state, ratchet in ((BULL, ratchet_bull), (BEAR, ratchet_bear)):
        for _ in range(200):
            p = p_add = 100_000.0
            a, v = rng.uniform(0, 1), rng.normal(0, 1e-6)
            e_lim = target_exposure(state, a, v, e0, e_max, e_min)
            for _ in range(50):
                p += rng.normal(0, 10)
                a, v = rng.uniform(0, 1), rng.normal(0, 1e-6)
                e_star = target_exposure(state, a, v, e0, e_max, e_min)
                e_t, e_lim, p_add, _ = ratchet(e_star, e_lim, p_add, p, 0.5, 10.0)
                assert e_min <= e_t <= e_max
                assert (e_t >= e0) if state == BULL else (e_t <= e0)


def test_dead_band():
    W_cash, n, p = 5_000_000, 50, 100_000.0
    assert target_shares_delta(0.5, W_cash, n, p, 0.1, 1) == (50, 0, True)
    _, dn, skip = target_shares_delta(0.53, W_cash, n, p, 0.1, 1)  # 3 < 5.3
    assert dn == 3 and skip
    _, dn, skip = target_shares_delta(0.6, W_cash, n, p, 0.1, 1)  # 10 >= 6
    assert dn == 10 and not skip
    # e_target = 0: threshold falls to n_min, so the last share can be sold
    _, dn, skip = target_shares_delta(0.0, 9_900_000, 1, p, 0.1, 1)
    assert dn == -1 and not skip


# ── 8. Endowment ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "agent_cls", [MomentumEKFAgent, FundamentalistAgent], ids=["momentum", "fundamental"]
)
def test_endowment(agent_cls):
    agent = agent_cls(
        id=0,
        symbol="ABM",
        starting_cash=CASH,
        initial_exposure=0.5,
        reference_price=P0_CENTS,
        random_state=np.random.RandomState(0),
    )
    assert agent.starting_cash == CASH
    assert agent.holdings == {"CASH": CASH - 50 * P0_CENTS, "ABM": 50}
    assert agent.holdings["CASH"] + agent.holdings["ABM"] * P0_CENTS == CASH
    assert agent.C_t == 0.5

    poor = agent_cls(
        id=1,
        symbol="ABM",
        starting_cash=150_000,
        initial_exposure=0.5,
        reference_price=P0_CENTS,
        random_state=np.random.RandomState(0),
    )
    assert poor.holdings == {"CASH": 150_000}
    assert endowment(150_000, 0.5, P0_CENTS) == (150_000, 0)

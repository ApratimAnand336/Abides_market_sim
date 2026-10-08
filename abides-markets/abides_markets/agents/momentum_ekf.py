# EKF-Based Momentum Investor Agent  (FinVerse spec v1.0, with the v1.1
# changes M1-M7: detrended volatility, ratchet that follows down, re-entry
# needs T >= theta_out, persistent stop exit)
#
# Same three-layer template as the FundamentalistAgent (fundamental.py):
#
# LAYER 1 — State estimator: damped-trend Kalman filter on z = ln(mid).
#   State x = [l, v]: log-price level and trend velocity (log-return / s).
#   The model is linear in log-price, so the EKF equations reduce exactly to
#   the standard Kalman filter; the "EKF" name is kept for consistency with
#   the project's vocabulary.
#
# LAYER 2 — Caution modulator: identical to the FundamentalistAgent, with the
#   directional view D = sign(v_hat).
#
# DECISION — NEUTRAL / BULL / BEAR / WATCH state machine (whether and in which
#   direction to deviate from the neutral exposure e_0).
#
# LAYER 3 — Target-exposure sizing with a pyramiding ratchet, and an urgency /
#   anti-chase limit price.
#
# The maths lives in small pure module-level functions so it can be unit
# tested without a simulation kernel (tests/test_momentum_ekf.py).
# The oracle is never used by this agent.

import logging
from math import ceil, exp, floor, log, sqrt, tanh
from typing import Dict, List, Optional, Tuple

import numpy as np

from abides_core import Message, NanosecondTime

from ..messages.news import NewsSentimentMsg
from ..messages.query import QuerySpreadResponseMsg
from ..orders import Side
from .trading_agent import TradingAgent


logger = logging.getLogger(__name__)

NEUTRAL, BULL, BEAR, WATCH = "NEUTRAL", "BULL", "BEAR", "WATCH"
TREND, STOP, OTHER = "TREND", "STOP", "OTHER"
H = np.array([1.0, 0.0])


# ══════════════════════════════════════════════════════════════════════════
# PURE HELPERS
# ══════════════════════════════════════════════════════════════════════════


def endowment(starting_cash: int, e0: float, p_ref: int) -> Tuple[int, int]:
    """B.2: (cash, shares) after buying floor(e0 * W0 / p_ref) shares at p_ref."""
    n0 = int(floor(e0 * starting_cash / p_ref))
    return starting_cash - n0 * p_ref, n0


def detrended_var(t, z) -> float:
    """Spec v1.1 M2: variance per second of log returns after removing the
    window's time-weighted mean drift, so a trend does not count as
    volatility (E[r^2/dt] = sigma^2 + v^2*dt for raw returns).

        r_i = z_i - z_{i-1},  dt_i = t_i - t_{i-1}
        v_bar = sum(r_i) / sum(dt_i)
        e_i = r_i - v_bar * dt_i
        variance = mean(e_i^2 / dt_i)
    """
    r = np.diff(np.asarray(z, dtype=float))
    dt = np.diff(np.asarray(t, dtype=float))
    if len(r) == 0:
        return 0.0
    v_bar = float(r.sum() / dt.sum())
    e = r - v_bar * dt
    return float(np.mean(e ** 2 / dt))


def warmup_fit(
    t: List[float],
    z: List[float],
    sigma_q2: float,
    c_P: float,
    kappa_R: float,
    kappa_l: float,
    kappa_v: float,
    tau: float,
) -> Dict:
    """C.2: OLS fit of z on [1, t - t_last] and self-calibration of the noise
    scales. Times in seconds, z in log-cents.

    sigma_ref2 is the detrended return variance (spec v1.1 M2)."""
    t = np.asarray(t, dtype=float)
    z = np.asarray(z, dtype=float)
    X = np.column_stack([np.ones_like(t), t - t[-1]])
    XtX_inv = np.linalg.inv(X.T @ X)
    c = XtX_inv @ X.T @ z
    resid = z - X @ c
    s2_res = max(float(resid @ resid) / (len(z) - 2), sigma_q2)
    P0 = c_P * s2_res * XtX_inv

    dt = np.diff(t)
    sigma_ref2 = max(detrended_var(t, z), sigma_q2 / float(np.mean(dt)))

    return {
        "x": c.copy(),
        "P": (P0 + P0.T) / 2.0,
        "s2_res": s2_res,
        "sigma_ref2": sigma_ref2,
        "R_base": kappa_R * s2_res,
        "sigma_l2": kappa_l * sigma_ref2,
        "sigma_vinf": kappa_v * sqrt(sigma_ref2) / sqrt(tau),
    }


def transition(
    dt: float, tau: float, sigma_l2: float, sigma_vinf: float, g_Q: float = 1.0
) -> Tuple[np.ndarray, np.ndarray]:
    """C.3: damped-trend transition matrix F and process noise Q for a gap dt."""
    phi = exp(-dt / tau)
    F = np.array([[1.0, tau * (1.0 - phi)], [0.0, phi]])
    Q = np.array(
        [
            [sigma_l2 * dt, 0.0],
            [0.0, g_Q * sigma_vinf ** 2 * (1.0 - phi ** 2)],
        ]
    )
    return F, Q


def kf_predict(
    x: np.ndarray, P: np.ndarray, F: np.ndarray, Q: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    return F @ x, F @ P @ F.T + Q


def kf_correct(
    x_minus: np.ndarray, P_minus: np.ndarray, z: float, R: float
) -> Tuple[np.ndarray, np.ndarray, float, float, np.ndarray]:
    """C.5: Kalman correction with H = [1, 0], Joseph-form covariance update.

    Returns (x, P, y, S, K)."""
    y = z - x_minus[0]
    S = P_minus[0, 0] + R
    K = P_minus[:, 0] / S
    x = x_minus + K * y
    A = np.eye(2) - np.outer(K, H)
    P = A @ P_minus @ A.T + R * np.outer(K, K)
    P = (P + P.T) / 2.0
    return x, P, float(y), float(S), K


def kaufman_er(z_window: List[float]) -> float:
    """C.4: Kaufman efficiency ratio over a window of n+1 log prices."""
    direction = abs(z_window[-1] - z_window[0])
    volatility = sum(abs(z_window[i + 1] - z_window[i]) for i in range(len(z_window) - 1))
    if volatility == 0:
        return 1.0
    return min(direction / volatility, 1.0)


def obs_variance(R_base: float, lambda_er: float, er: float) -> float:
    """C.4: R_k = R_base * exp(lambda_er * (1 - ER_k))."""
    return R_base * exp(lambda_er * (1.0 - er))


def regime_update(
    epsbar: float, y: float, S: float, a_eps: float, eps_thr: float, g_max: float
) -> Tuple[float, float, float]:
    """C.6: normalised innovation, its EWMA and the Q multiplier for k+1."""
    eps = y * y / S
    epsbar = (1.0 - a_eps) * epsbar + a_eps * eps
    g_Q = min(g_max, max(1.0, epsbar / eps_thr))
    return eps, epsbar, g_Q


def trend_strength(x: np.ndarray, P: np.ndarray) -> float:
    """C.7: T = v_hat / sd(v)."""
    return float(x[1] / sqrt(max(P[1, 1], 1e-30)))


def realised_var(t: List[float], z: List[float], n: int, floor_var: float = 0.0) -> float:
    """C.7: detrended variance per second of the last n log returns
    (spec v1.1 M2: the window's mean drift is removed first, see
    detrended_var).

    floor_var: lower bound. The agent passes sigma_q^2 / mean(dt) — the same
    tick-quantisation floor used for sigma_ref^2 in C.2 — so a perfectly flat
    price path does not give sigma_tau = 0 (which would fire the trailing stop
    on any half-tick dip) or a division by zero in g_k. (Spec ambiguity: C.7
    gives no floor; this mirrors the C.2 floor.)"""
    t = np.asarray(t[-(n + 1):], dtype=float)
    z = np.asarray(z[-(n + 1):], dtype=float)
    if len(z) < 2:
        return floor_var
    return max(detrended_var(t, z), floor_var)


def forecast(
    x: np.ndarray,
    P: np.ndarray,
    R: float,
    h: float,
    tau: float,
    sigma_l2: float,
    sigma_vinf: float,
    g_Q: float,
) -> Tuple[float, float]:
    """C.7: forecast of z at the next decision (horizon h seconds).

    Returns (z_fc, sigma_fc)."""
    F_h, Q_h = transition(h, tau, sigma_l2, sigma_vinf, g_Q)
    z_fc = float((F_h @ x)[0])
    P_h = F_h @ P @ F_h.T + Q_h
    return z_fc, sqrt(P_h[0, 0] + R)


def apply_news(
    x: np.ndarray, P: np.ndarray, s_n: float, eta: float, rho: float, sigma_vinf: float
) -> Tuple[np.ndarray, np.ndarray]:
    """F2 ("primed"): lean the velocity toward the headline and widen its
    uncertainty. The level estimate is never moved. Scaling P[1,1] by f and
    the off-diagonals by sqrt(f) multiplies det(P) by f, so P stays PSD."""
    x = x.copy()
    P = P.copy()
    x[1] += eta * s_n * sigma_vinf
    f = 1.0 + rho * abs(s_n)
    P[1, 1] *= f
    P[0, 1] *= sqrt(f)
    P[1, 0] *= sqrt(f)
    return x, P


def conviction(
    C: float,
    T: float,
    T_0: float,
    er: float,
    lambda_v: float,
    sigma_ref2: float,
    sigma_hat2: float,
) -> Tuple[float, float, float, float]:
    """F.1: returns (a, s, m, g)."""
    s = tanh(abs(T) / T_0)
    m = exp(-lambda_v * (1.0 - er))
    g = min(1.0, sqrt(sigma_ref2 / sigma_hat2)) if sigma_hat2 > 0 else 1.0
    return C * s * m * g, s, m, g


def target_exposure(
    state: str, a: float, v_hat: float, e0: float, e_max: float, e_min: float = 0.0
) -> float:
    """F.2: e*_k before the ratchet."""
    if state == BULL and v_hat > 0:
        return e0 + a * (e_max - e0)
    if state == BEAR and v_hat < 0:
        return e0 - a * (e0 - e_min)
    return e0


def ratchet_bull(
    e_star: float, e_cap: float, p_add: float, p: float, k_add: float, sigma_tau: float
) -> Tuple[float, float, float, bool]:
    """F.3 (BULL): exposure may only rise at a new high k_add*sigma_tau above
    the last add point. Spec v1.1 M4: the cap first follows e_star down, so
    after a cut the exposure is rebuilt only at a fresh high.
    Returns (e_target, e_cap, p_add, added)."""
    added = False
    e_cap = min(e_cap, e_star)
    if p >= p_add + k_add * sigma_tau:
        e_cap = max(e_cap, e_star)
        p_add = p
        added = True
    return min(e_star, e_cap), e_cap, p_add, added


def ratchet_bear(
    e_star: float, e_floor: float, p_add: float, p: float, k_add: float, sigma_tau: float
) -> Tuple[float, float, float, bool]:
    """F.3 (BEAR, mirror; spec v1.1 M4: the floor follows e_star up first).
    Returns (e_target, e_floor, p_add, added)."""
    added = False
    e_floor = max(e_floor, e_star)
    if p <= p_add - k_add * sigma_tau:
        e_floor = min(e_floor, e_star)
        p_add = p
        added = True
    return max(e_star, e_floor), e_floor, p_add, added


def target_shares_delta(
    e_target: float, cash: float, n: int, p: float, b: float, n_min: int
) -> Tuple[int, int, bool]:
    """F.2: target position, required change and dead-band test.

    Returns (n_star, dn, skip)."""
    W = cash + n * p
    n_star = int(floor(e_target * W / p))
    dn = n_star - n
    skip = abs(dn) < max(n_min, b * n_star)
    return n_star, dn, skip


def limit_price(
    is_buy: bool,
    order_class: str,
    bid: int,
    ask: int,
    p: float,
    v_hat: float,
    h: float,
    C: float,
    z_fc: float,
    sigma_fc: float,
    mu_m: float,
) -> Tuple[Optional[int], float]:
    """F.4: urgency within the spread plus the anti-chase cap/floor for TREND
    orders. Returns (P_L or None if the order must not be placed, u)."""
    if order_class == STOP:
        u = 1.0
    elif order_class == TREND:
        spread_rel = (ask - bid) / p
        if spread_rel <= 0:
            u = C  # locked book: rho -> infinity
        else:
            rho = abs(v_hat) * h / (spread_rel / 2.0)
            u = C * rho / (1.0 + rho)
    else:
        u = 0.0

    # Rounding: half-ticks round TOWARD the opposite side so that u >= 0.5
    # crosses a 1-cent spread and u < 0.5 joins our own side, as F.4 intends
    # (Python's round() is banker's rounding and would not guarantee this).
    if is_buy:
        P_L = bid + u * (ask - bid)
        if order_class == TREND:
            P_cap = exp(z_fc + mu_m * sigma_fc)
            if P_cap < bid:
                return None, u
            P_L = min(P_L, P_cap)
        return max(bid, int(floor(P_L + 0.5))), u
    else:
        P_L = ask - u * (ask - bid)
        if order_class == TREND:
            P_flr = exp(z_fc - mu_m * sigma_fc)
            if P_flr > ask:
                return None, u
            P_L = max(P_L, P_flr)
        return min(ask, int(ceil(P_L - 0.5))), u


def _sign(v: float) -> float:
    return 1.0 if v > 0 else (-1.0 if v < 0 else 0.0)


# ══════════════════════════════════════════════════════════════════════════
# AGENT
# ══════════════════════════════════════════════════════════════════════════


class MomentumEKFAgent(TradingAgent):
    """
    Damped-trend Kalman momentum investor (long-only).

    Each decision cycle (one spread response):
      observe -> warm-up or filter update -> caution -> state machine ->
      target exposure -> at most one net limit order.
    """

    def __init__(
        self,
        id: int,
        symbol: str = "ABM",
        starting_cash: int = 100_000,
        name: Optional[str] = None,
        type: Optional[str] = "EKF_Momentum",
        random_state: Optional[np.random.RandomState] = None,
        log_orders: bool = False,
        # --- Endowment (B.2) ---
        initial_exposure: float = 0.5,
        reference_price: int = 100_000,
        # --- Layer 1 (C) ---
        N_w: int = 20,
        n_er: int = 15,
        lambda_er: float = 3.0,
        kappa_R: float = 1.0,
        c_P: float = 2.0,
        tau: float = 600.0,
        tau_ratio: Optional[float] = None,  # v1.1 M3: tau / wake_mean (display)
        kappa_l: float = 0.2,
        kappa_v: float = 1.0,
        a_eps: float = 0.2,
        eps_thr: float = 3.0,
        g_max: float = 10.0,
        # --- Layer 2 (D) ---
        gamma: float = 0.8,
        k_c: float = 1.0,
        # --- Decision (E) ---
        theta_in: float = 2.0,
        theta_out: float = 0.75,
        ER_min: float = 0.3,
        k_stop: float = 3.0,
        k_re: float = 0.35,
        # --- Layer 3 (F) ---
        T_0: float = 2.0,
        lambda_v: float = 1.0,
        e_max: float = 0.8,
        e_min: float = 0.0,
        b: float = 0.1,
        n_min: int = 1,
        k_add: float = 0.5,
        mu_m: float = 1.0,
        # --- News (F2) ---
        eta_news: float = 0.25,
        rho_news: float = 3.0,
        # --- Scheduling (F3) ---
        wake_mean: float = 30.0,
    ) -> None:
        super().__init__(id, name, type, random_state, starting_cash, log_orders)

        assert N_w >= max(n_er + 1, 5), "N_w must be >= max(n_er + 1, 5)"
        assert theta_in > theta_out, "hysteresis requires theta_in > theta_out"

        self.symbol: str = symbol

        # ── Hyperparameters (exposed for run_dashboard_sim.py) ──────────
        self.initial_exposure = initial_exposure
        self.e_0 = initial_exposure
        self.reference_price = reference_price
        self.N_w, self.n_er, self.lambda_er = int(N_w), int(n_er), lambda_er
        self.kappa_R, self.c_P, self.tau = kappa_R, c_P, tau
        self.kappa_l, self.kappa_v = kappa_l, kappa_v
        self.a_eps, self.eps_thr, self.g_max = a_eps, eps_thr, g_max
        self.gamma, self.k_c = gamma, k_c
        self.theta_in, self.theta_out, self.ER_min = theta_in, theta_out, ER_min
        self.k_stop, self.k_re = k_stop, k_re
        self.T_0, self.lambda_v = T_0, lambda_v
        self.e_max, self.e_min, self.b, self.n_min = e_max, e_min, b, int(n_min)
        self.k_add, self.mu_m = k_add, mu_m
        self.eta_news, self.rho_news = eta_news, rho_news
        self.wake_mean = wake_mean
        self.tau_ratio = tau_ratio if tau_ratio is not None else tau / wake_mean

        # ── Endowment (B.2): starting_cash stays = total starting wealth ─
        cash, n0 = endowment(starting_cash, initial_exposure, reference_price)
        self.holdings["CASH"] = cash
        if n0 > 0:
            self.holdings[symbol] = n0

        # ── Layer 1 state ───────────────────────────────────────────────
        self.x_hat: Optional[np.ndarray] = None
        self.P: Optional[np.ndarray] = None
        self.sigma_q2: Optional[float] = None
        self.s2_res: Optional[float] = None
        self.sigma_ref2: Optional[float] = None
        self.R_base: Optional[float] = None
        self.sigma_l2: Optional[float] = None
        self.sigma_vinf: Optional[float] = None
        self.epsbar: float = 1.0
        self.g_Q: float = 1.0

        # Observation history: ns timestamps, seconds, mid (cents), ln(mid)
        self.time_log: List[NanosecondTime] = []
        self.t_log: List[float] = []
        self.price_log: List[float] = []
        self.z_log: List[float] = []

        # ── Layer 2 state (C_0 = 0.5 = sigmoid(0)) ──────────────────────
        self.E_t: float = 0.0
        self.D_prev: float = 0.0
        self.C_t: float = 0.5

        # ── Decision state ──────────────────────────────────────────────
        self.mstate: Optional[str] = None  # None while warming up
        self.peak: Optional[float] = None
        self.trough: Optional[float] = None
        self.L: Optional[float] = None
        self.came_from: Optional[str] = None
        self.t_w: Optional[float] = None
        self.e_cap: Optional[float] = None
        self.e_floor: Optional[float] = None
        self.p_add: Optional[float] = None
        self.added: bool = False
        # v1.1 M6: a STOP exit stays urgent until the target is reached
        self.exit_pending: bool = False
        self.state_history: List[Dict] = []

        # ── Messaging state ─────────────────────────────────────────────
        self.trading: bool = False
        self.state: str = "AWAITING_WAKEUP"

    # ══════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════════════

    def kernel_stopping(self) -> None:
        super().kernel_stopping()
        self.logEvent(
            "MOM_FINAL",
            {
                "state": self.mstate,
                "l_hat": None if self.x_hat is None else float(self.x_hat[0]),
                "v_hat": None if self.x_hat is None else float(self.x_hat[1]),
                "P": None if self.P is None else self.P.tolist(),
                "holdings": dict(self.holdings),
            },
        )

    def wakeup(self, current_time: NanosecondTime) -> None:
        can_trade = super().wakeup(current_time)

        self.state = "INACTIVE"

        if not self.mkt_open or not self.mkt_close:
            return

        if not self.trading:
            self.trading = True

        if self.mkt_closed or not can_trade:
            return

        self.set_wakeup(current_time + self.get_wake_frequency())

        self.cancel_all_orders()
        self.get_current_spread(self.symbol)
        self.state = "AWAITING_SPREAD"

    def receive_message(
        self, current_time: NanosecondTime, sender_id: int, message: Message
    ) -> None:
        super().receive_message(current_time, sender_id, message)

        if isinstance(message, NewsSentimentMsg):
            if message.symbol == self.symbol:
                self.on_news(message.sentiment, message.headline)
            return

        if self.state == "AWAITING_SPREAD" and isinstance(
            message, QuerySpreadResponseMsg
        ):
            if self.mkt_closed:
                return
            self.execute_strategy()
            self.state = "AWAITING_WAKEUP"

    def get_wake_frequency(self) -> NanosecondTime:
        """F3: Poisson wake-ups, gap = max(1 s, Exponential(wake_mean))."""
        gap_s = max(1.0, self.random_state.exponential(scale=self.wake_mean))
        return int(round(gap_s * 1e9))

    # ══════════════════════════════════════════════════════════════════
    # NEWS (F2)
    # ══════════════════════════════════════════════════════════════════

    def on_news(self, sentiment: float, headline: str = "") -> None:
        """Prime the velocity estimate. Ignored during warm-up. Does NOT
        trigger a trading cycle; the effect shows at the next wake-up."""
        if self.x_hat is None:
            return
        self.x_hat, self.P = apply_news(
            self.x_hat, self.P, sentiment, self.eta_news, self.rho_news, self.sigma_vinf
        )
        self.logEvent(
            "NEWS_RECEIVED",
            {
                "headline": headline,
                "sentiment": float(sentiment),
                "v_hat_new": float(self.x_hat[1]),
                "P11_new": float(self.P[1, 1]),
            },
        )

    # ══════════════════════════════════════════════════════════════════
    # STRATEGY
    # ══════════════════════════════════════════════════════════════════

    def execute_strategy(self) -> None:
        bid, _, ask, _ = self.get_known_bid_ask(self.symbol)
        order = self.process_observation(self.current_time, bid, ask)
        if order is not None:
            side, qty, price = order
            self.place_limit_order(self.symbol, qty, side, price)

    def process_observation(
        self, t_ns: NanosecondTime, bid: Optional[int], ask: Optional[int]
    ) -> Optional[Tuple[Side, int, int]]:
        """One full decision cycle. Returns (side, qty, limit price) or None.

        Separated from execute_strategy so the whole decision logic can be
        driven in tests without a kernel."""
        # ── C.1 Observation ─────────────────────────────────────────────
        if not bid or not ask:
            return None
        p = (bid + ask) / 2.0
        z = log(p)
        t = t_ns / 1e9
        self.time_log.append(t_ns)
        self.t_log.append(t)
        self.price_log.append(p)
        self.z_log.append(z)

        # ── C.2 Warm-up ─────────────────────────────────────────────────
        if self.x_hat is None:
            if len(self.z_log) >= self.N_w:
                self._finish_warmup(p)
            return None

        # ── C.3–C.6 Filter ──────────────────────────────────────────────
        dt = t - self.t_log[-2]
        F, Q = transition(dt, self.tau, self.sigma_l2, self.sigma_vinf, self.g_Q)
        x_minus, P_minus = kf_predict(self.x_hat, self.P, F, Q)
        er = kaufman_er(self.z_log[-(self.n_er + 1):])
        R = obs_variance(self.R_base, self.lambda_er, er)
        self.x_hat, self.P, y, S, K = kf_correct(x_minus, P_minus, z, R)
        eps, self.epsbar, self.g_Q = regime_update(
            self.epsbar, y, S, self.a_eps, self.eps_thr, self.g_max
        )

        # ── C.7 Derived quantities ──────────────────────────────────────
        v_hat = float(self.x_hat[1])
        T = trend_strength(self.x_hat, self.P)
        mean_dt = float(np.mean(np.diff(self.t_log[-(self.n_er + 1):])))
        sigma_hat2 = realised_var(
            self.t_log, self.z_log, self.n_er, self.sigma_q2 / mean_dt
        )
        sigma_tau = p * sqrt(sigma_hat2) * sqrt(self.tau)

        self.logEvent(
            "MOM_KF_UPDATE",
            {
                "mid": p,
                "l_hat": round(float(self.x_hat[0]), 8),
                "v_hat": float(v_hat),
                "P00": float(self.P[0, 0]),
                "P01": float(self.P[0, 1]),
                "P11": float(self.P[1, 1]),
                "R": float(R),
                "S": float(S),
                "K0": round(float(K[0]), 6),
                "K1": float(K[1]),
                "ER": round(er, 4),
                "eps": round(eps, 4),
                "epsbar": round(self.epsbar, 4),
                "g_Q": round(self.g_Q, 4),
                "T": round(T, 4),
            },
        )

        # ── D Caution ───────────────────────────────────────────────────
        self._update_caution(p)

        # ── F.1 Conviction (state-independent; needed for entry e_cap) ──
        a, s, m, g = conviction(
            self.C_t, T, self.T_0, er, self.lambda_v, self.sigma_ref2, sigma_hat2
        )

        # ── E State machine ─────────────────────────────────────────────
        hi_tau, lo_tau = self._window_extremes(t)
        exit_kind, entered = self._step_state_machine(
            t, p, T, er, v_hat, hi_tau, lo_tau, sigma_tau, a
        )

        # ── F.2/F.3 Target exposure with ratchet ────────────────────────
        e_star, e_target = self._target_with_ratchet(p, a, v_hat, sigma_tau, entered)

        return self._decide_order(
            bid, ask, p, v_hat, er, a, s, m, g, e_star, e_target, exit_kind,
            {"sigma_hat2": sigma_hat2, "sigma_tau": sigma_tau},
        )

    # ── helpers for process_observation ─────────────────────────────────

    def _finish_warmup(self, p: float) -> None:
        # sigma_q^2 uses p_ref = mid at the end of warm-up (one tick = 1 cent)
        self.sigma_q2 = 1.0 / (12.0 * p * p)
        fit = warmup_fit(
            self.t_log[-self.N_w:],
            self.z_log[-self.N_w:],
            self.sigma_q2,
            self.c_P,
            self.kappa_R,
            self.kappa_l,
            self.kappa_v,
            self.tau,
        )
        self.x_hat, self.P = fit["x"], fit["P"]
        self.s2_res = fit["s2_res"]
        self.sigma_ref2 = fit["sigma_ref2"]
        self.R_base = fit["R_base"]
        self.sigma_l2 = fit["sigma_l2"]
        self.sigma_vinf = fit["sigma_vinf"]
        # D_0 = sign(v_hat_0): the warm-up fit is the agent's first directional
        # view, so the first filter update can already score it (Part D).
        self.D_prev = _sign(float(self.x_hat[1]))
        self.mstate = NEUTRAL
        self.logEvent(
            "MOM_WARMUP_DONE",
            {
                "l0": float(self.x_hat[0]),
                "v0": float(self.x_hat[1]),
                "P0": self.P.tolist(),
                "s2_res": float(self.s2_res),
                "sigma_ref2": float(self.sigma_ref2),
                "R_base": float(self.R_base),
                "sigma_l2": float(self.sigma_l2),
                "sigma_vinf": float(self.sigma_vinf),
            },
        )

    def _update_caution(self, p: float) -> None:
        """Part D (same as FundamentalistAgent.update_caution). W_k scores the
        previous view against the move since the previous observation."""
        if self.D_prev != 0.0:
            W = self.D_prev * (p - self.price_log[-2])
            self.E_t = self.gamma * self.E_t + (1.0 - self.gamma) * W
            self.C_t = 1.0 / (1.0 + exp(-self.k_c * self.E_t))
        self.logEvent(
            "CAUTION_UPDATE",
            {"D_prev": self.D_prev, "E_t": round(self.E_t, 2), "C_t": round(self.C_t, 4)},
        )
        self.D_prev = _sign(float(self.x_hat[1]))

    def _window_extremes(self, t: float) -> Tuple[Optional[float], Optional[float]]:
        """Highest / lowest mid with time in [t - tau, t), current excluded."""
        window = []
        for i in range(len(self.t_log) - 2, -1, -1):
            if self.t_log[i] < t - self.tau:
                break
            window.append(self.price_log[i])
        if not window:
            return None, None
        return max(window), min(window)

    def _breakout(
        self, direction: str, p: float, T: float, er: float, hi: Optional[float], lo: Optional[float]
    ) -> bool:
        if hi is None or er < self.ER_min:
            return False
        if direction == BULL:
            return p > hi and T >= self.theta_in
        return p < lo and T <= -self.theta_in

    def _enter(self, new_state: str, t: float, p: float, a: float, v_hat: float, reason: str) -> None:
        e_star = target_exposure(new_state, a, v_hat, self.e_0, self.e_max, self.e_min)
        if new_state == BULL:
            self.peak, self.e_cap = p, e_star
        else:
            self.trough, self.e_floor = p, e_star
        self.p_add = p
        self.exit_pending = False
        self._record_transition(t, new_state, reason, p)

    def _exit_to_watch(self, t: float, kind: str, extreme: float) -> None:
        if kind == STOP:
            self.exit_pending = True
        self.came_from = self.mstate
        self.L = extreme
        self.t_w = t
        self._record_transition(t, WATCH, kind, extreme)

    def _record_transition(self, t: float, to: str, reason: str, extreme: Optional[float]) -> None:
        event = {
            "from": self.mstate,
            "to": to,
            "reason": reason,
            "L": self.L,
            "peak_or_trough": extreme,
        }
        self.state_history.append({"time_s": t, **event})
        self.logEvent("MOM_STATE", event)
        self.mstate = to

    def _step_state_machine(
        self,
        t: float,
        p: float,
        T: float,
        er: float,
        v_hat: float,
        hi: Optional[float],
        lo: Optional[float],
        sigma_tau: float,
        a: float,
    ) -> Tuple[Optional[str], bool]:
        """Part E: at most one transition. Returns (exit_kind, entered)."""
        st = self.mstate

        if st == NEUTRAL:
            for d in (BULL, BEAR):
                if self._breakout(d, p, T, er, hi, lo):
                    self._enter(d, t, p, a, v_hat, "BREAKOUT")
                    return None, True
            return None, False

        if st == BULL:
            self.peak = max(self.peak, p)
            if p <= self.peak - self.k_stop * sigma_tau:
                self._exit_to_watch(t, STOP, self.peak)
                return STOP, False
            if T < self.theta_out:
                self._exit_to_watch(t, "FADE", self.peak)
                return "FADE", False
            return None, False

        if st == BEAR:
            self.trough = min(self.trough, p)
            if p >= self.trough + self.k_stop * sigma_tau:
                self._exit_to_watch(t, STOP, self.trough)
                return STOP, False
            if T > -self.theta_out:
                self._exit_to_watch(t, "FADE", self.trough)
                return "FADE", False
            return None, False

        # WATCH
        # v1.1 M5: re-entry also needs the trend strength back past theta_out
        if (self.came_from == BULL and p >= self.L + self.k_re * sigma_tau
                and v_hat > 0 and T >= self.theta_out):
            self._enter(BULL, t, p, a, v_hat, "REENTRY")
            return None, True
        if (self.came_from == BEAR and p <= self.L - self.k_re * sigma_tau
                and v_hat < 0 and T <= -self.theta_out):
            self._enter(BEAR, t, p, a, v_hat, "REENTRY")
            return None, True
        opposite = BEAR if self.came_from == BULL else BULL
        if self._breakout(opposite, p, T, er, hi, lo):
            self._enter(opposite, t, p, a, v_hat, "BREAKOUT")
            return None, True
        if t - self.t_w >= self.tau:
            self._record_transition(t, NEUTRAL, "TIMEOUT", None)
        return None, False

    def _target_with_ratchet(
        self, p: float, a: float, v_hat: float, sigma_tau: float, entered: bool
    ) -> Tuple[float, float]:
        """F.2/F.3: returns (e_star, e_target). On the entry update the
        ratchet was just initialised (e_cap/e_floor = e*, p_add = p), so no
        add event is evaluated."""
        e_star = target_exposure(self.mstate, a, v_hat, self.e_0, self.e_max, self.e_min)
        self.added = False
        if self.mstate == BULL:
            if entered:
                return e_star, min(e_star, self.e_cap)
            e_target, self.e_cap, self.p_add, self.added = ratchet_bull(
                e_star, self.e_cap, self.p_add, p, self.k_add, sigma_tau
            )
            return e_star, e_target
        if self.mstate == BEAR:
            if entered:
                return e_star, max(e_star, self.e_floor)
            e_target, self.e_floor, self.p_add, self.added = ratchet_bear(
                e_star, self.e_floor, self.p_add, p, self.k_add, sigma_tau
            )
            return e_star, e_target
        return e_star, self.e_0

    def _decide_order(
        self,
        bid: int,
        ask: int,
        p: float,
        v_hat: float,
        er: float,
        a: float,
        s: float,
        m: float,
        g: float,
        e_star: float,
        e_target: float,
        exit_kind: Optional[str],
        extra: Optional[Dict] = None,
    ) -> Optional[Tuple[Side, int, int]]:
        """F.2 sizing + F.4 limit price; logs MOM_DECISION.

        v1.1 M6: while exit_pending, orders use STOP (urgent) pricing and
        ignore the dead band; the flag clears once |n - n_star| < n_min."""
        cash = self.holdings.get("CASH", 0)
        n = self.holdings.get(self.symbol, 0)
        n_star, dn, skip = target_shares_delta(e_target, cash, n, p, self.b, self.n_min)
        if self.exit_pending:
            if abs(dn) < self.n_min:
                self.exit_pending = False
            else:
                skip = False

        decision = {
            "state": self.mstate,
            "a": round(a, 4),
            "s": round(s, 4),
            "m": round(m, 4),
            "g": round(g, 4),
            "e_star": round(e_star, 4),
            "e_target": round(e_target, 4),
            "n_star": n_star,
            "n": n,
            "dn": dn,
            "order_class": None,
            "u": None,
            "P_L": None,
            "skipped_reason": None,
            "added": bool(self.added),
            "exit_pending": self.exit_pending,
            "sigma_hat2": None if extra is None else float(extra["sigma_hat2"]),
            "sigma_tau": None if extra is None else float(extra["sigma_tau"]),
        }

        order = None
        if skip:
            decision["skipped_reason"] = "dead_band"
        else:
            is_buy = dn > 0
            if exit_kind == STOP or self.exit_pending:
                order_class = STOP
            elif (self.mstate == BULL and is_buy) or (self.mstate == BEAR and not is_buy):
                order_class = TREND
            else:
                order_class = OTHER

            z_fc, sigma_fc = forecast(
                self.x_hat,
                self.P,
                obs_variance(self.R_base, self.lambda_er, er),
                self.wake_mean,
                self.tau,
                self.sigma_l2,
                self.sigma_vinf,
                self.g_Q,
            )
            P_L, u = limit_price(
                is_buy, order_class, bid, ask, p, v_hat, self.wake_mean,
                self.C_t, z_fc, sigma_fc, self.mu_m,
            )
            decision.update(order_class=order_class, u=round(u, 4), P_L=P_L)

            if P_L is None:
                decision["skipped_reason"] = "anti_chase"
            elif is_buy:
                # P_L first: qty is capped by what CASH buys at P_L.
                qty = min(dn, int(cash // P_L))
                if qty <= 0:
                    decision["skipped_reason"] = "no_cash"
                else:
                    order = (Side.BID, qty, P_L)
            else:
                qty = min(-dn, n)
                if qty <= 0:
                    decision["skipped_reason"] = "no_shares"
                else:
                    order = (Side.ASK, qty, P_L)

        decision["qty"] = None if order is None else order[1]
        self.logEvent("MOM_DECISION", decision)
        return order

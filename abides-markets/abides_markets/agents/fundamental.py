# EKF-Based Fundamental Investor Agent  (FinVerse spec v1.1, Part 2)
#
# Three-layered decision system modeled for fundamental investors:
#
# LAYER 1 — Kalman core:
#   - Prediction: random walk x_t = x_{t-1} with process noise
#     Q = q * sigma_f2_hat * dt, where sigma_f2_hat (cents^2 / s) is the
#     agent's own estimate of how fast value moves, measured from 5-minute
#     mid changes (F3). Q keeps the gain from decaying to zero.
#   - Observation: market mid-price with variance derived from Kaufman's
#     Efficiency Ratio + Price-Anchored Exponential Scaling (F2)
#   - Correction: standard scalar Kalman update
#   x_hat changes ONLY in the correction step and on news (F5).
#
# LAYER 2 — Caution modulator: EWMA of a virtual trade score, squashed by a
#   sigmoid into a confidence C_t in [0, 1].
#
# LAYER 3 — Target position (F4): the edge z = (x_hat - mid) / sqrt(P) sets a
#   target fraction of wealth in the stock; the agent trades only the
#   difference, with a step cap and a dead band. The limit price slides
#   within the spread with confidence, bounded by a safety margin mu.

import logging
from bisect import bisect_right
from math import exp, floor, sqrt, tanh
from typing import Dict, List, Optional, Tuple

import numpy as np

from abides_core import Message, NanosecondTime
from abides_core.utils import str_to_ns

from ..messages.query import QuerySpreadResponseMsg
from ..messages.news import NewsSentimentMsg
from ..orders import Side
from .trading_agent import TradingAgent


logger = logging.getLogger(__name__)

# ── Value-speed estimate sigma_f2_hat (spec v1.1 F3) ─────────────────────
SIGMA_F_LAG_S = 300.0  # lag (s): long enough that mid wiggles are noise
SIGMA_F_PRIOR = 3.0  # cents^2 / s, calibrated from the seed-42 oracle
SIGMA_F_FLOOR = 0.1  # cents^2 / s
SIGMA_F_EWMA_N = 60  # EWMA memory in updates (alpha = 1 / 60)

# ── News (spec v1.1 F5) ───────────────────────────────────────────────────
NEWS_HORIZON_S = 1800.0  # news is worth k_news "typical 30-minute moves"


class FundamentalistAgent(TradingAgent):
    """
    Kalman-filter fundamental investor.

    The agent maintains a Kalman estimate x_hat (variance P) of the asset's
    fundamental value.  At each wake cycle it:

      1. **Predicts** with a random walk: x_pred = x_hat, P_pred = P + Q.
      2. **Observes** the market mid-price and computes observation variance
         using Kaufman's Efficiency Ratio + Price-Anchored Exponential Scaling.
      3. **Corrects** the prediction via the standard Kalman update.
      4. Updates its caution C_t and trades toward a target position set by
         the edge z = (x_hat - mid) / sqrt(P).
    """

    def __init__(
        self,
        id: int,
        symbol: str = "ABM",
        starting_cash: int = 100_000,
        name: Optional[str] = None,
        type: Optional[str] = None,
        random_state: Optional[np.random.RandomState] = None,
        log_orders: bool = False,
        # --- Scheduling ---
        wake_up_freq: NanosecondTime = str_to_ns("10S"),  # default 10 seconds
        # --- EKF Hyperparameters ---
        er_window: int = 10,              # Lookback window for Kaufman's ER
        delta: float = 0.0015,            # Fraction of price for R_base  (R_base = (delta * P)^2)
        lambda_er: float = 1.0,           # Exponential penalty strength on (1 - ER)
        initial_uncertainty: float = 250_000, # P_0: initial prediction variance  ((delta*r_bar)^2)
        q: float = 1.0,                   # Process-noise multiplier: Q = q * sigma_f2_hat * dt
        # --- Oracle observation noise (for getting a private fundamental signal) ---
        sigma_n: float = 10_000.0,        # Observation noise VARIANCE passed to oracle.observe_price()
        # --- Caution Modulator Hyperparameters ---
        gamma: float = 0.8,               # Memory weight for EWMA
        k: float = 1.0,                   # Sigmoid sensitivity
        # --- Limit Price Hyperparameters ---
        mu: float = 0.1,                  # Safety margin multiplier (smaller = tighter limits)
        # --- Target position sizing (F4) ---
        a_max: float = 0.8,               # Max tilt of the target stock fraction away from w0
        z0: float = 2.0,                  # Edge (in sd of the belief) giving tanh(1) of the tilt
        s_max: float = 0.15,              # Max trade per wake, as a fraction of wealth
        b_f: float = 0.02,                # Dead band: skip trades smaller than b_f * wealth
        # --- News Sentiment (F5) ---
        k_news: float = 1.5,              # News shift in units of a typical 30-minute move
        # --- Initial share endowment ---
        initial_exposure: float = 0.5,    # e_0: fraction of wealth held in shares at start
        reference_price: int = 100_000,   # p_ref0 (cents) used to value the endowment
    ) -> None:
        super().__init__(id, name, type, random_state, starting_cash, log_orders)

        # Trading parameters
        self.symbol: str = symbol

        # ── Initial share endowment ──────────────────────────────────────
        # starting_cash stays equal to TOTAL starting wealth so that
        # kernel_stopping's gain (mark_to_market - starting_cash) does not
        # report the endowment as profit.
        self.initial_exposure: float = initial_exposure
        self.reference_price: int = reference_price
        n_0 = int(floor(initial_exposure * starting_cash / reference_price))
        self.holdings["CASH"] = starting_cash - n_0 * reference_price
        if n_0 > 0:
            self.holdings[symbol] = n_0
        self.wake_up_freq: NanosecondTime = wake_up_freq

        # ── EKF Hyperparameters ──────────────────────────────────────────
        self.er_window: int = er_window
        self.delta: float = delta
        self.lambda_er: float = lambda_er
        self.q: float = q
        self.sigma_n: float = sigma_n

        # ── Target position sizing (F4) ──────────────────────────────────
        self.a_max: float = a_max
        self.z0: float = z0
        self.s_max: float = s_max
        self.b_f: float = b_f
        self.k_news: float = k_news

        # ── Caution Modulator Parameters ─────────────────────────────────
        self.gamma: float = gamma
        self.k: float = k

        # ── Caution State Variables ──────────────────────────────────────
        self.E_t: float = 0.0             # Emotional memory accumulator
        self.D_prev: float = 0.0          # Previous expected direction (+1 / -1)
        self.C_t: float = 0.5             # Current confidence multiplier (sigmoid(0))
        self.mu: float = mu

        # ── EKF State Variables ──────────────────────────────────────────
        # x_hat: current posterior estimate of fundamental value (cents)
        self.x_hat: Optional[float] = None
        # P: current posterior uncertainty / variance of the estimate
        self.P: float = initial_uncertainty
        # sigma_f2_hat: estimated speed of value moves (cents^2 / s), F3
        self.sigma_f2_hat: float = SIGMA_F_PRIOR
        # R_last: observation variance used in the latest update (cents^2);
        # the noise term of the edge z (spec v1.2 Part 2)
        self.R_last: float = 0.0

        # ── Internal Market Price Log ────────────────────────────────────
        # Every time we query the spread, we append the observed mid-price.
        # This forms our internal time series for computing volatility / ER.
        self.price_log: List[float] = []
        # Parallel timestamp log (for potential future use)
        self.time_log: List[NanosecondTime] = []

        # ── Agent State Machine ──────────────────────────────────────────
        self.trading: bool = False
        self.state: str = "AWAITING_WAKEUP"

    # ══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ══════════════════════════════════════════════════════════════════════

    def kernel_starting(self, start_time: NanosecondTime) -> None:
        super().kernel_starting(start_time)
        self.oracle = self.kernel.oracle

    def kernel_stopping(self) -> None:
        super().kernel_stopping()
        # Log final EKF state for post-sim analysis
        self.logEvent("EKF_FINAL_ESTIMATE", {
            "x_hat": self.x_hat,
            "P": self.P,
            "num_observations": len(self.price_log),
        })

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 1a — PREDICTION  (internal model)
    # ══════════════════════════════════════════════════════════════════════

    def prediction(self, dt: float) -> Tuple[float, float, float]:
        """
        Predict the next fundamental value (spec v1.1 F3).

        Model: **random walk** with process noise
            x_predicted = x_hat_{t-1}
            P_predicted = P_{t-1} + Q,     Q = q * sigma_f2_hat * dt

        Without Q the gain decays like 1/n and the belief freezes into an
        all-day average; with Q it settles at K_ss ~= sqrt(Q / R).

        Args:
            dt: seconds since the previous Kalman update.

        Returns:
            (x_predicted, P_predicted, Q)
        """
        Q = self.q * self.sigma_f2_hat * max(dt, 0.0)
        return self.x_hat, self.P + Q, Q

    def update_sigma_f2(self, now: NanosecondTime, mid: float) -> None:
        """
        Update sigma_f2_hat (cents^2 / s), the agent's estimate of how fast
        value moves, from the squared mid change over the last
        SIGMA_F_LAG_S seconds (spec v1.1 F3). Long lags are used because
        short-lag changes are dominated by microstructure noise.

        Call after appending (now, mid) to time_log / price_log.
        """
        j = bisect_right(self.time_log, now - int(SIGMA_F_LAG_S * 1e9)) - 1
        if j < 0:
            return
        lag_s = (now - self.time_log[j]) / 1e9
        if lag_s <= 0:
            return
        sample = (mid - self.price_log[j]) ** 2 / lag_s
        alpha = 1.0 / SIGMA_F_EWMA_N
        self.sigma_f2_hat = max(
            (1.0 - alpha) * self.sigma_f2_hat + alpha * sample, SIGMA_F_FLOOR
        )

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 1b — OBSERVATION VARIANCE  (Kaufman ER + Price-Anchored Scaling)
    # ══════════════════════════════════════════════════════════════════════

    def _compute_kaufman_er(self) -> float:
        """
        Compute Kaufman's Efficiency Ratio over the last `er_window` prices
        in the internal price log.

            ER = direction / volatility
            direction  = |P_t - P_{t-n}|           (net price change)
            volatility = sum(|P_i - P_{i-1}|)      (sum of absolute changes)

        Returns:
            ER in [0, 1].  1 = perfectly trending, 0 = pure noise.
            Returns 0.5 (neutral) if not enough data.
        """
        n = self.er_window
        if len(self.price_log) < n + 1:
            # Not enough data — return neutral ER
            return 0.5

        window = self.price_log[-(n + 1):]  # n+1 prices → n changes

        direction = abs(window[-1] - window[0])
        volatility = sum(abs(window[i + 1] - window[i]) for i in range(n))

        if volatility == 0:
            # No movement at all — treat as perfectly efficient
            return 1.0

        er = direction / volatility
        return min(er, 1.0)  # Clamp to [0, 1]

    def _compute_observation_variance(self, price: float) -> float:
        """
        Compute the observation variance R_t using Price-Anchored Exponential
        Scaling driven by the Kaufman Efficiency Ratio.

            R_base = (delta * P_t)^2
            R_t    = R_base * exp(lambda * (1 - ER_t))

        Intuition:
        - When ER → 1 (strong trend): R_t ≈ R_base  (trust the market more)
        - When ER → 0 (choppy noise): R_t >> R_base  (distrust the market)

        Args:
            price: Current market mid-price (cents).

        Returns:
            R_t (observation variance, in cents^2).
        """
        er = self._compute_kaufman_er()

        R_base = (self.delta * price) ** 2
        R_t = R_base * exp(self.lambda_er * (1.0 - er))

        return R_t

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 1c — CORRECTION  (Kalman update)
    # ══════════════════════════════════════════════════════════════════════

    def correction(self, x_predicted: float, P_predicted: float,
                   z: float, R: float) -> Tuple[float, float, float]:
        """
        Standard scalar Kalman correction step.

        Fuses the predicted estimate with the market observation under a
        Gaussian assumption.

            Innovation:  y = z - x_predicted
            Kalman Gain: K = P_predicted / (P_predicted + R)
            Posterior:   x_hat = x_predicted + K * y
            Post. Var:   P     = (1 - K) * P_predicted

        Args:
            x_predicted: Prior estimate from the internal model.
            P_predicted: Prior uncertainty.
            z:           Market observation (mid-price, in cents).
            R:           Observation variance (from ER-based computation).

        Returns:
            (x_hat, P, K) — posterior estimate, posterior variance, Kalman gain.
        """
        # Innovation (measurement residual)
        y = z - x_predicted

        # Innovation covariance
        S = P_predicted + R

        # Kalman gain
        K = P_predicted / S if S > 0 else 0.5

        # Posterior estimate
        x_hat = x_predicted + K * y

        # Posterior covariance (Joseph form for numerical stability reduces to
        # this in the scalar case when H=1)
        P = (1.0 - K) * P_predicted

        return x_hat, P, K

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 2 — CAUTION MODULATOR
    # ══════════════════════════════════════════════════════════════════════

    def update_caution(self, current_price: float) -> float:
        """
        Updates the agent's emotional memory and computes a confidence multiplier
        based on the accuracy of their previous prediction.

        Returns:
            C_t (confidence multiplier) in [0, 1]
        """
        if len(self.price_log) < 2 or self.D_prev == 0.0:
            # Not enough history to evaluate a previous trade
            return self.C_t

        P_prev = self.price_log[-2]
        
        # 1. Virtual Trade Score (Direction expected * Actual price move)
        W_t = self.D_prev * (current_price - P_prev)

        # 2. Update Emotional Memory (EWMA)
        self.E_t = self.gamma * self.E_t + (1.0 - self.gamma) * W_t

        # 3. Confidence Multiplier (Sigmoid)
        # We use a logistic curve to compress E_t into [0, 1]
        # Adding a small constant shift if needed, but standard sigmoid works:
        self.C_t = 1.0 / (1.0 + exp(-self.k * self.E_t))

        return self.C_t

    # ══════════════════════════════════════════════════════════════════════
    # LAYER 3 — LIMIT PRICE & TARGET POSITION
    # ══════════════════════════════════════════════════════════════════════

    def decision_limit_price(
        self, bid: float, ask: float, confidence: float, is_buy: bool
    ) -> Optional[int]:
        """
        Computes the final limit price using emotional urgency within the spread,
        constrained by an epistemic safety margin.

        The key insight: the order must land WITHIN or NEAR the bid-ask spread
        to have any chance of filling. The safety margin acts as a percentage-based
        constraint, not a raw variance offset.

        The side is passed in explicitly (spec v1.1 F4.4): it comes from the
        target-position change, not from the sign of (x_hat - mid). There is
        no minimum-gap check; the sizing dead band replaces it.
        """
        if self.x_hat is None:
            return None

        spread = ask - bid

        # 1. Urgency price: confidence slides the order within the spread
        #    High confidence → aggressive (closer to opposite side)
        #    Low confidence → passive (closer to own side)
        if is_buy:
            # Place bid between current bid and ask, scaled by confidence
            P_urgency = bid + confidence * spread
            
            # Safety ceiling: don't pay more than x_hat + mu% of x_hat
            P_ceiling = self.x_hat * (1.0 + self.mu)
            P_L = min(P_urgency, P_ceiling)
            
            # Floor: at least at the current bid (otherwise order is useless)
            P_L = max(P_L, bid)
            return int(round(P_L))
            
        else:
            # Place ask between current ask and bid, scaled by confidence
            P_urgency = ask - confidence * spread
            
            # Safety floor: don't sell for less than x_hat - mu% of x_hat
            P_floor = self.x_hat * (1.0 - self.mu)
            P_L = max(P_urgency, P_floor)
            
            # Ceiling: at most at the current ask
            P_L = min(P_L, ask)
            return int(round(P_L))

    def target_position(self, mid: float, confidence: float) -> Dict:
        """
        Target-position sizing (spec v1.1 F4): decide how much to HOLD given
        the edge, then trade only the difference.

            z      = (x_hat - mid) / sqrt(P + R_last)  edge as signal / noise
            w_star = clip(w0 + a_max * C * tanh(z / z0), 0, 1)
            d_star = round((w_star * W - shares * mid) / mid)

        d_star is capped at floor(s_max * W / mid) shares per wake and
        dropped (dead band) when |d| * mid < b_f * W.  Long-only, no
        leverage caps are applied later, once the limit price is known.

        Spec v1.2: P + R is the variance of (belief - price) when nothing is
        mispriced (own uncertainty + normal price noise), so z is a
        t-statistic: z = 1 is one normal wiggle, z = 3 a real mispricing.
        (v1.1 used sqrt(P) alone, which made every wiggle look like a strong
        signal and synchronised the agents.)

        Returns a dict with z, z_den, w_star, w_now, d_star, d (after the step cap
        and dead band; 0 when skipped) and skipped_reason.
        """
        cash = self.holdings.get("CASH", 0)
        shares = self.holdings.get(self.symbol, 0)
        W = cash + shares * mid
        var = self.P + self.R_last
        z_den = sqrt(var) if var > 0 else 0.0
        z = (self.x_hat - mid) / z_den if var > 0 else 0.0
        w_star = min(1.0, max(0.0, self.initial_exposure
                              + self.a_max * confidence * tanh(z / self.z0)))
        w_now = shares * mid / W if W > 0 else 0.0
        d_star = int(round((w_star * W - shares * mid) / mid)) if W > 0 else 0

        cap = int(floor(self.s_max * W / mid)) if W > 0 else 0
        d = max(-cap, min(cap, d_star))
        skipped_reason = None
        if abs(d) < 1 or abs(d) * mid < self.b_f * W:
            d, skipped_reason = 0, "dead_band"
        return {
            "z": z,
            "z_den": z_den,
            "w_star": w_star,
            "w_now": w_now,
            "d_star": d_star,
            "d": d,
            "skipped_reason": skipped_reason,
        }

    # ══════════════════════════════════════════════════════════════════════
    # STRATEGY EXECUTION  (ties the layers together)
    # ══════════════════════════════════════════════════════════════════════

    def execute_strategy(self) -> None:
        """
        Full Kalman cycle: observe → log → predict → correct → trade.
        """
        # ── 1. Observe the market ────────────────────────────────────────
        bid, bid_vol, ask, ask_vol = self.get_known_bid_ask(self.symbol)
        if not bid or not ask:
            logger.debug(f"{self.name}: No bid/ask available, skipping cycle.")
            return

        mid = (bid + ask) / 2.0

        # ── 2. Append to internal price log ──────────────────────────────
        self.price_log.append(mid)
        self.time_log.append(self.current_time)

        # ── 3. Initialize estimate on first observation ──────────────────
        if self.x_hat is None:
            # Query the oracle for a noisy fundamental value to use as our baseline anchor
            obs = self.oracle.observe_price(
                self.symbol, self.current_time, sigma_n=self.sigma_n, random_state=self.random_state
            )
            self.x_hat = obs
            logger.debug(f"{self.name}: Initialized x_hat = {self.x_hat:.0f} via Oracle")
            return  # Need at least one prior before we can predict+correct

        # ── 4. Prediction step (F3) ──────────────────────────────────────
        dt = (self.time_log[-1] - self.time_log[-2]) / 1e9
        self.update_sigma_f2(self.current_time, mid)
        x_predicted, P_predicted, Q = self.prediction(dt)

        # ── 5. Compute observation variance ──────────────────────────────
        R = self._compute_observation_variance(mid)
        self.R_last = R

        # ── 6. Correction step ───────────────────────────────────────────
        self.x_hat, self.P, K = self.correction(x_predicted, P_predicted, mid, R)

        # ── 7. Log the EKF state ─────────────────────────────────────────
        er = self._compute_kaufman_er()
        self.logEvent("EKF_UPDATE", {
            "mid": mid,
            "x_hat": round(self.x_hat, 2),
            "P": round(self.P, 2),
            "R": round(R, 2),
            "K": round(K, 4),
            "ER": round(er, 4),
            "Q": round(Q, 4),
            "dt": round(dt, 3),
            "sigma_f2": round(self.sigma_f2_hat, 4),
        })

        logger.debug(
            f"{self.name}: mid={mid:.0f}  x̂={self.x_hat:.0f}  "
            f"P={self.P:.0f}  R={R:.0f}  K={K:.4f}  ER={er:.4f}"
        )

        # ── 7.5. Update Caution Modulator ────────────────────────────────
        confidence = self.update_caution(mid)

        self.logEvent("CAUTION_UPDATE", {
            "D_prev": self.D_prev,
            "E_t": round(self.E_t, 2),
            "C_t": round(confidence, 4)
        })

        # ── 8. Trading decision ──────────────────────────────────────────
        # Record expected direction for the NEXT tick's caution evaluation
        diff = self.x_hat - mid
        if diff > 0:
            self.D_prev = 1.0
        elif diff < 0:
            self.D_prev = -1.0
        else:
            self.D_prev = 0.0

        # Target position (F4): the side comes from d, not from sign(diff)
        decision = self.target_position(mid, confidence)
        d = decision["d"]
        side, limit_price = None, None
        if d != 0:
            is_buy = d > 0
            side = "BUY" if is_buy else "SELL"
            limit_price = self.decision_limit_price(bid, ask, confidence, is_buy)
            if is_buy:
                d = min(d, int(self.holdings.get("CASH", 0) // limit_price))
                if d <= 0:
                    d, decision["skipped_reason"] = 0, "no_cash"
            else:
                d = -min(-d, self.holdings.get(self.symbol, 0))
                if d >= 0:
                    d, decision["skipped_reason"] = 0, "no_shares"
        decision["d"] = d

        self.logEvent("FUND_DECISION", {
            "z": round(decision["z"], 4),
            "z_den": round(decision["z_den"], 4),
            "w_star": round(decision["w_star"], 4),
            "w_now": round(decision["w_now"], 4),
            "d_star": decision["d_star"],
            "d": d,
            "skipped_reason": decision["skipped_reason"],
            "side": side,
            "limit_price": limit_price,
        })

        if d > 0:
            self.place_limit_order(self.symbol, d, Side.BID, limit_price)
        elif d < 0:
            self.place_limit_order(self.symbol, -d, Side.ASK, limit_price)

    # ══════════════════════════════════════════════════════════════════════
    # WAKEUP / MESSAGE HANDLING  (standard periodic-agent pattern)
    # ══════════════════════════════════════════════════════════════════════

    def wakeup(self, current_time: NanosecondTime) -> None:
        can_trade = super().wakeup(current_time)

        self.state = "INACTIVE"

        if not self.mkt_open or not self.mkt_close:
            return

        if not self.trading:
            self.trading = True
            logger.debug(f"{self.name} is ready to start trading.")

        if self.mkt_closed:
            return

        if not can_trade:
            return

        # Schedule next wakeup
        self.set_wakeup(current_time + self.get_wake_frequency())

        # Cancel stale orders, then request fresh spread data
        self.cancel_all_orders()
        self.get_current_spread(self.symbol)
        self.state = "AWAITING_SPREAD"

    def apply_news(self, sentiment: float, headline: str = "") -> float:
        """
        Volatility-scaled news shift (spec v1.1 F5). Returns the shift (cents).

            sigma_move = sqrt(sigma_f2_hat * NEWS_HORIZON_S)
            shift      = sentiment * k_news * sigma_move
            x_hat     += shift,    P += shift^2

        News is worth k_news "typical 30-minute moves". The added P makes
        the next market readings count more, so the market confirms or fades
        the news; if it does not follow, the belief drifts back.
        """
        x_before, P_before = self.x_hat, self.P
        sigma_move = sqrt(self.sigma_f2_hat * NEWS_HORIZON_S)
        shift = sentiment * self.k_news * sigma_move
        self.x_hat = x_before + shift
        self.P = P_before + shift * shift
        self.logEvent("NEWS_RECEIVED", {
            "headline": headline,
            "sentiment": sentiment,
            "shift": round(shift, 4),
            "sigma_move": round(sigma_move, 4),
            "x_hat_before": round(x_before, 2),
            "x_hat_after": round(self.x_hat, 2),
            "P_before": round(P_before, 4),
            "P_after": round(self.P, 4),
        })
        return shift

    def receive_message(
        self, current_time: NanosecondTime, sender_id: int, message: Message
    ) -> None:
        super().receive_message(current_time, sender_id, message)

        # ── Handle News Sentiment ────────────────────────────────────────
        if isinstance(message, NewsSentimentMsg):
            if message.symbol == self.symbol and self.x_hat is not None:
                self.apply_news(message.sentiment, message.headline)

                logger.debug(
                    f"{self.name}: News [{message.symbol}] sent={message.sentiment:+.2f} "
                    f"=> x_hat shifted to {self.x_hat:.0f}"
                )

                # Force an immediate trading cycle to react to the news
                if not self.mkt_closed:
                    self.cancel_all_orders()
                    self.get_current_spread(self.symbol)
                    self.state = "AWAITING_SPREAD"
            return

        # ── Handle Spread Response (normal trading cycle) ────────────────
        if self.state == "AWAITING_SPREAD":
            if isinstance(message, QuerySpreadResponseMsg):
                if self.mkt_closed:
                    return
                self.execute_strategy()
                self.state = "AWAITING_WAKEUP"

    def get_wake_frequency(self) -> NanosecondTime:
        return self.wake_up_freq

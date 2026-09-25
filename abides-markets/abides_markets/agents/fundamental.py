# EKF-Based Fundamental Investor Agent
#
# Three-layered decision system modeled for fundamental investors:
#
# LAYER 1 — EKF Core (implemented here):
#   - Prediction: Internal model (currently persistence: x_t = x_{t-1})
#   - Observation: Market mid-price with variance derived from Kaufman's
#     Efficiency Ratio + Price-Anchored Exponential Scaling
#   - Correction: Standard Kalman update fusing prediction with observation
#
# LAYER 2 — Caution Modulator (stub — to be implemented):
#   - Tracks P&L of previous trades, outputs confidence factor in [0, 1]
#   - Used to scale order volume or tighten/widen limit price
#
# LAYER 3 — Limit Price & Volume Decision (stub — to be implemented):
#   - Extrapolates the corrected estimate to produce a limit price
#   - Determines trade volume based on conviction and caution

import logging
from math import exp, sqrt
from typing import List, Optional, Tuple

import numpy as np

from abides_core import Message, NanosecondTime
from abides_core.utils import str_to_ns

from ..messages.query import QuerySpreadResponseMsg
from ..messages.news import NewsSentimentMsg
from ..orders import Side
from .trading_agent import TradingAgent


logger = logging.getLogger(__name__)


class FundamentalistAgent(TradingAgent):
    """
    EKF-inspired fundamental investor.

    The agent maintains an internal Kalman-style estimate of the asset's
    fundamental value.  At each wake cycle it:

      1. **Predicts** the next fundamental value using an internal model
         (currently a persistence / random-walk prior: x_t = x_{t-1}).
      2. **Observes** the market mid-price and computes observation variance
         using Kaufman's Efficiency Ratio + Price-Anchored Exponential Scaling.
      3. **Corrects** the prediction via the standard Kalman update, producing
         a posterior estimate and updated uncertainty.
      4. *(Future)* Feeds the posterior into a caution modulator and a limit-
         price / volume decision layer.
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
        delta: float = 0.005,             # Fraction of price for R_base  (R_base = (delta * P)^2)
        lambda_er: float = 3.0,           # Exponential penalty strength on (1 - ER)
        initial_uncertainty: float = 1e8, # P_0: initial prediction variance (large = unsure)
        # --- Oracle observation noise (for getting a private fundamental signal) ---
        sigma_n: float = 10_000.0,        # Observation noise passed to oracle.observe_price()
        # --- Caution Modulator Hyperparameters ---
        gamma: float = 0.8,               # Memory weight for EWMA
        k: float = 1.0,                   # Sigmoid sensitivity
        # --- Limit Price Hyperparameters ---
        mu: float = 0.5,                  # Safety margin multiplier
        # --- News Sentiment ---
        news_sensitivity: float = 0.02,   # Max % shift per news event (2%)
    ) -> None:
        super().__init__(id, name, type, random_state, starting_cash, log_orders)

        # Trading parameters
        self.symbol: str = symbol
        self.wake_up_freq: NanosecondTime = wake_up_freq

        # ── EKF Hyperparameters ──────────────────────────────────────────
        self.er_window: int = er_window
        self.delta: float = delta
        self.lambda_er: float = lambda_er
        self.sigma_n: float = sigma_n

        # ── Caution Modulator Parameters ─────────────────────────────────
        self.gamma: float = gamma
        self.k: float = k

        # ── Caution State Variables ──────────────────────────────────────
        self.E_t: float = 0.0             # Emotional memory accumulator
        self.D_prev: float = 0.0          # Previous expected direction (+1 / -1)
        self.C_t: float = 1.0             # Current confidence multiplier
        self.beta: float = self.random_state.uniform(5.0, 20.0) # Baseline aggression
        self.mu: float = mu
        self.news_sensitivity: float = news_sensitivity

        # ── EKF State Variables ──────────────────────────────────────────
        # x_hat: current posterior estimate of fundamental value (cents)
        self.x_hat: Optional[float] = None
        # P: current posterior uncertainty / variance of the estimate
        self.P: float = initial_uncertainty

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

    def prediction(self) -> Tuple[float, float]:
        """
        Predict the next fundamental value using the internal model.

        Current model: **Persistence (random walk)**
            x_predicted = x_hat_{t-1}
            P_predicted  = P_{t-1}       (no process noise Q for now)

        Returns:
            (x_predicted, P_predicted)
        """
        # Persistence: our best guess for the next value is the current estimate.
        # Since we have no process noise Q yet, uncertainty doesn't grow.
        x_predicted = self.x_hat
        P_predicted = self.P
        # NOTE: When you add a proper internal model later, you would:
        #   x_predicted = f(x_hat)          # your transition function
        #   P_predicted = F * P * F^T + Q   # with Jacobian F and process noise Q
        return x_predicted, P_predicted

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
    # LAYER 3 — LIMIT PRICE & VOLUME DECISION  (stub)
    # ══════════════════════════════════════════════════════════════════════

    def decision_limit_price(self, bid: float, ask: float, confidence: float) -> Optional[int]:
        """
        Computes the final limit price bounding the emotional urgency price 
        by the epistemic safety margin derived from the EKF uncertainty.
        """
        if self.x_hat is None:
            return None
        
        # 1. Epistemic Limits (Safety Margin)
        # m = mu * sqrt(S_t) where S_t is self.P
        m = self.mu * (max(0.0, self.P) ** 0.5)
        P_max_buy = self.x_hat - m
        P_min_sell = self.x_hat + m
        
        # 2. Emotional Urgency Price
        spread = ask - bid
        P_urgency_buy = bid + confidence * spread
        P_urgency_sell = ask - confidence * spread
        
        # 3. Final Limit Price (The Intersection)
        diff = self.x_hat - ((bid + ask) / 2.0)
        
        if diff > 0:
            P_L = min(P_urgency_buy, P_max_buy)
            return int(round(P_L))
        elif diff < 0:
            P_L = max(P_urgency_sell, P_min_sell)
            return int(round(P_L))
        else:
            return None

    def decision_volume(self, confidence: float, current_price: float) -> int:
        """
        Decides trade volume using the Wealth-Bounded Allocation method.
        """
        if self.x_hat is None:
            return 0
            
        gap_fraction = abs(self.x_hat - current_price) / current_price
        A_t = min(1.0, self.beta * confidence * gap_fraction)
        
        diff = self.x_hat - current_price
        if diff > 0:
            # BUYING: allocate fraction of available cash
            cash = self.holdings.get("CASH", 0)
            size = int((A_t * cash) / current_price)
        elif diff < 0:
            # SELLING: liquidate fraction of current holdings
            shares_owned = self.holdings.get(self.symbol, 0)
            size = int(A_t * shares_owned)
        else:
            size = 0
            
        return max(0, size)

    # ══════════════════════════════════════════════════════════════════════
    # STRATEGY EXECUTION  (ties the layers together)
    # ══════════════════════════════════════════════════════════════════════

    def execute_strategy(self) -> None:
        """
        Full EKF cycle: observe → log → predict → correct → trade.
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

        # ── 4. Prediction step ───────────────────────────────────────────
        x_predicted, P_predicted = self.prediction()

        # ── 5. Compute observation variance ──────────────────────────────
        R = self._compute_observation_variance(mid)

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
        # Compare our EKF posterior estimate to the market mid-price.
        diff = self.x_hat - mid

        # Record expected direction for the NEXT tick's caution evaluation
        if diff > 0:
            self.D_prev = 1.0
        elif diff < 0:
            self.D_prev = -1.0
        else:
            self.D_prev = 0.0

        # Decide size using Wealth-Bounded Allocation
        size = self.decision_volume(confidence, mid)

        if size <= 0:
            logger.debug(f"{self.name}: Allocation fraction yielded size 0. Sitting out.")
            return

        # Decide limit price using Safety Margin + Emotional Urgency
        limit_price = self.decision_limit_price(bid, ask, confidence)

        if limit_price is None:
            return

        if diff > 0:
            # We believe price is too low → buy
            self.place_limit_order(self.symbol, size, Side.BID, limit_price)
        else:
            # We believe price is too high → sell
            self.place_limit_order(self.symbol, size, Side.ASK, limit_price)

        # ── 9. Slow-moving Fundamental Equation Update ───────────────────
        # When the agent executes a trade, it shifts its intrinsic anchor
        # by 1% depending on the recent market direction.
        if len(self.price_log) >= 2:
            recent_direction = mid - self.price_log[-2]
            if recent_direction > 0:
                self.x_hat *= 1.01  # Increase fundamental estimate by 1%
            elif recent_direction < 0:
                self.x_hat *= 0.99  # Decrease fundamental estimate by 1%

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

    def receive_message(
        self, current_time: NanosecondTime, sender_id: int, message: Message
    ) -> None:
        super().receive_message(current_time, sender_id, message)

        # ── Handle News Sentiment ────────────────────────────────────────
        if isinstance(message, NewsSentimentMsg):
            if message.symbol == self.symbol and self.x_hat is not None:
                # Shift fundamental estimate proportionally to sentiment
                # e.g. sentiment=+0.9, sensitivity=0.02 => +1.8% shift
                shift = 1.0 + (self.news_sensitivity * message.sentiment)
                self.x_hat *= shift

                self.logEvent("NEWS_RECEIVED", {
                    "headline": message.headline,
                    "sentiment": message.sentiment,
                    "shift": round(shift, 4),
                    "x_hat_new": round(self.x_hat, 2),
                })

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

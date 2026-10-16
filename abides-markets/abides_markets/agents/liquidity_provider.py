"""Liquidity provider: our market maker (FinVerse spec v1.5 A5, D-R4-4).

Replaces the ABIDES AdaptiveMarketMakerAgent, which quotes a 10-level ladder with spacing
tied to its own spread estimate, has no inventory management and unlimited inventory.

Every 5 s (first wake offset by the agent's index so LPs do not collide) it queries the
spread and then:
  ref       = mid if both sides exist, else the last trade, else r_bar (cold start)
  sigma^2   = EWMA (half-life 5 min) of (ln ref_t - ln ref_{t-5s})^2 / 5 s, per-second
              variance; prior (5.5 bps/min)^2 / 60 s
  sigma_10  = ref * sqrt(sigma^2 * 10 s)                typical 10-s move (cents)
  h         = max(1 c, c_h * sigma_10), c_h = 0.5         half-spread
  q_max     = floor(l_max * W / ref), l_max = 0.5         inventory limit (shares)
  skew      = psi * (q / q_max) * h, psi = 1               long inventory -> lower quotes
  r         = ref - skew                                   reservation price
  ladder    3 levels per side at r -/+ h * (1, 2, 3) (bids floored, asks ceiled to cents),
            each of max(1, floor(theta_lp * W / ref / 3)) shares, theta_lp = 0.02
  limits    no bids if q >= q_max, no asks if q <= -q_max; if |q| > 1.2 q_max (overshoot
            by fills) a marketable order (2% collar) brings |q| back to q_max
  lazy      requote only if |ref - ref_quoted| > h/2, |q - q_quoted| > 0.1 q_max, 30 s
            have passed, or a side that should be quoted has no open order; otherwise
            nothing is sent this wake
  budget    GrossLimit(2): gross position value <= 2 W (worst case, as the stock agents);
            the LP may short within q_max
W = cash + q * ref (wealth marked at ref). Deterministic: no random draws.

Log events: LP_QUOTE {ref, h, sigma2, q, q_max, skew, r, bids, asks, reason} at every
requote; LP_UNWIND {q, q_max, side, qty, limit}.
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from abides_core import Message, NanosecondTime

from ..configs.param_ranges import LP
from ..messages.query import QuerySpreadResponseMsg
from ..orders import LimitOrder, Side
from ..utils.budget import GrossLimit
from .trading_agent import TradingAgent


# ── pure functions (T-LP1, T-LP3, T-LP5) ──────────────────────────────────


def lp_sigma_update(sigma2: float, ref_prev: Optional[float], ref: float, dt_s: float, half_life_s: float) -> float:
    """EWMA of the per-second variance of log ref changes (unchanged without a previous ref)."""
    if not ref_prev or ref_prev <= 0 or ref <= 0:
        return sigma2
    x = math.log(ref / ref_prev) ** 2 / dt_s
    a = 1.0 - 2.0 ** (-dt_s / half_life_s)
    return (1.0 - a) * sigma2 + a * x


def lp_quotes(ref: float, sigma2: float, q: int, wealth: float, c_h: float = LP["c_h"],
              l_max: float = LP["l_max"], psi: float = LP["psi"], theta: float = LP["theta_lp"],
              levels: int = LP["levels"]) -> Dict:
    """The quote ladder of A5.1 for given (ref, sigma^2, q, W): prices in integer cents."""
    sigma_10 = ref * math.sqrt(max(sigma2, 0.0) * 10.0)
    h = max(1.0, c_h * sigma_10)
    q_max = int(math.floor(l_max * wealth / ref)) if wealth > 0 else 0
    skew = psi * (q / q_max) * h if q_max > 0 else 0.0
    r = ref - skew
    size = max(1, int(math.floor(theta * wealth / ref / levels))) if wealth > 0 else 0
    bids, asks = [], []
    if q_max > 0 and size > 0:
        if q < q_max:
            bids = [(max(1, int(math.floor(r - k * h))), size) for k in range(1, levels + 1)]
        if q > -q_max:
            asks = [(max(1, int(math.ceil(r + k * h))), size) for k in range(1, levels + 1)]
    return {"h": h, "sigma_10": sigma_10, "q_max": q_max, "skew": skew, "r": r, "size": size,
            "bids": bids, "asks": asks}


def lp_needs_requote(ref: float, q: int, now_s: float, quoted: Optional[Dict], h: float, q_max: int,
                     sides_missing: bool, max_age_s: float = LP["requote_max_s"],
                     q_frac: float = LP["requote_q_frac"], ref_frac_h: float = LP["requote_ref_frac_h"]) -> Optional[str]:
    """Why to requote now (None: keep the quotes)."""
    if quoted is None:
        return "first"
    if abs(ref - quoted["ref"]) > ref_frac_h * h:
        return "ref"
    if abs(q - quoted["q"]) > q_frac * q_max:
        return "inventory"
    if now_s - quoted["t"] >= max_age_s:
        return "age"
    if sides_missing:
        return "side"
    return None


# ── the agent ─────────────────────────────────────────────────────────────


class LiquidityProviderAgent(TradingAgent):
    def __init__(
        self,
        id: int,
        symbol: str,
        wealth_c: int,
        r_bar: int,
        wake_offset_ns: int = 0,
        l_max: float = LP["l_max"],
        name: Optional[str] = None,
        type: Optional[str] = None,
        random_state: Optional[np.random.RandomState] = None,
        log_orders: bool = False,
    ) -> None:
        super().__init__(id, name, type, random_state, starting_cash=int(wealth_c), log_orders=log_orders)
        self.symbol = symbol
        self.r_bar = int(r_bar)
        self.wake_offset_ns = int(wake_offset_ns)
        self.dt_ns = int(round(LP["dt_s"] * 1e9))
        self.dt_s = float(LP["dt_s"])
        self.l_max = float(l_max)
        self.half_life_s = float(LP["sigma_half_life_s"])
        bps_min = LP["sigma_prior_bps_per_min"] * 1e-4
        self.sigma2 = bps_min * bps_min / 60.0
        self.ref_prev: Optional[float] = None
        self.quoted: Optional[Dict] = None
        self.budget = GrossLimit(LP["budget_L"])
        self.n_wakes = 0
        self.n_requotes = 0
        self._awaiting_spread = False

    def get_wake_frequency(self) -> NanosecondTime:
        return self.wake_offset_ns  # first wake at the open + offset, then every 5 s

    def wakeup(self, current_time: NanosecondTime) -> None:
        can_trade = super().wakeup(current_time)
        if not can_trade:
            return
        self.n_wakes += 1
        self._awaiting_spread = True
        self.get_current_spread(self.symbol)
        self.set_wakeup(current_time + self.dt_ns)  # always reschedule while open

    def receive_message(self, current_time: NanosecondTime, sender_id: int, message: Message) -> None:
        super().receive_message(current_time, sender_id, message)
        if isinstance(message, QuerySpreadResponseMsg) and self._awaiting_spread:
            self._awaiting_spread = False
            if not self.mkt_closed:
                self.on_spread(current_time)

    # ── one wake ──────────────────────────────────────────────────────────

    def reference_price(self) -> float:
        bid, _, ask, _ = self.get_known_bid_ask(self.symbol)
        if bid and ask:
            return (bid + ask) / 2.0
        last = self.last_trade.get(self.symbol)
        return float(last) if last else float(self.r_bar)

    def _open_sides(self) -> Tuple[int, int]:
        nb = na = 0
        for o in self.orders.values():
            if isinstance(o, LimitOrder):
                if o.side.is_bid():
                    nb += 1
                else:
                    na += 1
        return nb, na

    def on_spread(self, current_time: NanosecondTime) -> None:
        ref = self.reference_price()
        self.sigma2 = lp_sigma_update(self.sigma2, self.ref_prev, ref, self.dt_s, self.half_life_s)
        self.ref_prev = ref
        q = int(self.holdings.get(self.symbol, 0))
        wealth = float(self.holdings.get("CASH", 0)) + q * ref
        qt = lp_quotes(ref, self.sigma2, q, wealth, l_max=self.l_max)
        q_max = qt["q_max"]

        if q_max > 0 and abs(q) > LP["overshoot"] * q_max:
            self._unwind(q, q_max, ref)
            self.quoted = None  # requote at the next wake from the new inventory
            return

        nb, na = self._open_sides()
        missing = (bool(qt["bids"]) and nb == 0) or (bool(qt["asks"]) and na == 0)
        now_s = current_time / 1e9
        reason = lp_needs_requote(ref, q, now_s, self.quoted, qt["h"], q_max, missing)
        if reason is None:
            return
        self.cancel_all_orders()
        for px, size in qt["bids"]:
            self.place_limit_order(self.symbol, size, Side.BID, px)
        for px, size in qt["asks"]:
            self.place_limit_order(self.symbol, size, Side.ASK, px)
        self.quoted = {"ref": ref, "q": q, "t": now_s}
        self.n_requotes += 1
        self.logEvent("LP_QUOTE", {
            "ref": ref, "h": qt["h"], "sigma2": self.sigma2, "q": q, "q_max": q_max, "skew": qt["skew"],
            "r": qt["r"], "bids": [p for p, _ in qt["bids"]], "asks": [p for p, _ in qt["asks"]],
            "size": qt["size"], "reason": reason,
        }, deepcopy_event=False)

    def _unwind(self, q: int, q_max: int, ref: float) -> None:
        self.cancel_all_orders()
        bid, _, ask, _ = self.get_known_bid_ask(self.symbol)
        collar = LP["collar"]
        if q > 0:
            qty, side = q - q_max, Side.ASK
            limit = max(1, int(math.floor((bid or ref) * (1.0 - collar))))
        else:
            qty, side = -q - q_max, Side.BID
            limit = int(math.ceil((ask or ref) * (1.0 + collar)))
        if qty > 0:
            self.place_limit_order(self.symbol, qty, side, limit)
        self.logEvent("LP_UNWIND", {"q": q, "q_max": q_max, "side": "SELL" if q > 0 else "BUY",
                                    "qty": qty, "limit": limit}, deepcopy_event=False)

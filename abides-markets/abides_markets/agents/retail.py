"""Retail trader crowd (FinVerse spec v1.5 A4): RetailCrowdAgent + RetailTraderAgent.

Replaces the ABIDES NoiseAgents (D-R4-3), fixing their gaps (spec §0.4):
  G-a no reaction to the market  -> crowd activity rises with recent volatility and news
  G-b one order a day             -> many small actions at a varying intensity
  G-c no positions, no stops      -> each trader holds cash and shares; 40% use stop-losses
  G-d no behaviour types          -> liquidity 50%, trend-chaser 25%, contrarian 25%
  G-e stock ABIDES agent          -> our own agent
Deliberately simple: no beliefs, no filters; a few rules and one shared scheduler.

RetailCrowdAgent (exactly one) wakes every dt_c = 5 s, reads the L1 book with a spread
query, keeps a 60-min ring buffer of 5-s mids and computes the crowd intensity

    lambda(t) = mu * U(t) * min(cap, 1 + kappa_v * max(0, V(t) - 1) + kappa_n * Nn(t))  [actions/s]

with mu = mu_per_agent * N_r / 23,400 s, U the intraday shape of A3.1, V = sigma_short /
sigma_ref (2-min mean vs 60-min half-life EWMA of the per-second variance of 5-s log
returns; V = 1 in the first 10 min) and Nn the news level (+|sentiment| per headline,
half-life 10 min). It draws n ~ Poisson(lambda * dt_c), sends n RetailActNowMsg to
traders picked uniformly (with replacement), and runs the STOP REGISTRY: a trader's stop
is triggered once when the mid is <= it.

RetailTraderAgent (N_r) has no wakeups of its own after the standard TradingAgent start.
Wealth $50,000, half in stock at r_bar; long-only and cash-only. On ActNow: cancel own
orders, pick a side by type, size round(LogNormal(ln 30, 0.8)) >= 1 clipped by the cash
or shares not committed to orders that can still fill, and send a marketable limit order
with a 2% broker collar (buy limit = ceil(ask * 1.02), sell limit = floor(bid * 0.98));
any remainder rests at the collar until the next action. Stop users register
stop = fill * (1 - d) after each buy fill; on StopTriggered they sell everything at
floor(bid * 0.98).

Log events: CROWD_TICK {lam, n, V, Nn, U, mid} (every tick with a mid), RETAIL_ACTION
{kind, side, q, limit, z}, RETAIL_SKIP {reason}, STOP_SET {stop}, STOP_TRIGGERED {stop,
q}, STOP_CLEARED.
"""

import heapq
import math
from collections import deque
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from abides_core import Message, NanosecondTime

from ..configs.param_ranges import LIVING_V1, RETAIL
from ..messages.news import NewsSentimentMsg
from ..messages.query import QuerySpreadResponseMsg
from ..messages.retail import RetailActNowMsg, RetailStopTriggeredMsg, RetailStopUpdateMsg
from ..orders import LimitOrder, Order, Side
from .trading_agent import TradingAgent

SESSION_S = 23_400
KINDS = ("liquidity", "trend", "contrarian")


# ── pure functions (T-RT1, T-RT2) ─────────────────────────────────────────


def _u_num(t_h: float, cfg=LIVING_V1) -> float:
    tau, T = cfg["u_tau_h"], cfg["session_h"]
    return 1.0 + cfg["u_open"] * math.exp(-t_h / tau) + cfg["u_close"] * math.exp(-(T - t_h) / tau)


_C_U = float(np.mean([_u_num(k / 3600.0) for k in range(SESSION_S + 1)]))


def u_activity(t_s: float) -> float:
    """U(t) of A3.1 at t seconds after the 09:30 open (mean 1 over the session)."""
    return _u_num(t_s / 3600.0) / _C_U


def crowd_intensity(mu_per_s: float, u: float, v: float, nn: float, kappa_v: float,
                    kappa_n: float, cap: float = 10.0) -> float:
    """lambda = mu * U * min(cap, 1 + kappa_v * max(0, V - 1) + kappa_n * Nn), actions/s."""
    return mu_per_s * u * min(cap, 1.0 + kappa_v * max(0.0, v - 1.0) + kappa_n * nn)


def news_level(events: Sequence[Tuple[float, float]], t_s: float, half_life_s: float) -> float:
    """Nn(t) = sum over past headlines of |sentiment| * 2^(-(t - t_j) / half_life)."""
    return float(sum(abs(s) * 2.0 ** (-(t_s - tj) / half_life_s) for tj, s in events if tj <= t_s))


def p_buy(kind: str, z: float, beta: float) -> float:
    """Buy probability by type; z = r_30 / s_30 (a 30-min move in typical sds)."""
    if kind == "liquidity":
        return 0.5
    if kind == "trend":
        return 1.0 / (1.0 + math.exp(-beta * z))
    if kind == "contrarian":
        return 1.0 / (1.0 + math.exp(beta * z))
    raise ValueError(kind)


class CrowdVolatility:
    """5-s mid ring buffer and the V(t) ratio of A4.1 (2).

    push(mid) once per 5-s tick (the last known mid if the book is one-sided). Each new
    5-s log return r gives a per-second variance sample r^2 / dt. sigma_short^2 = mean of
    the last n_short samples; sigma_ref^2 = EWMA of all samples with the given half-life
    (alpha = 1 - 2^(-dt / half_life)), started at the first sample. V = 1 during the
    warm-up (t < warmup_s since the open) or while sigma_ref^2 = 0.
    """

    def __init__(self, dt_s: float, buffer_s: float, n_short: int, ref_half_life_s: float, warmup_s: float):
        self.dt = float(dt_s)
        self.mids: deque = deque(maxlen=int(round(buffer_s / dt_s)) + 1)
        self.samples: deque = deque(maxlen=int(n_short))
        self.alpha = 1.0 - 2.0 ** (-dt_s / ref_half_life_s)
        self.ref_var: Optional[float] = None
        self.warmup_s = float(warmup_s)

    def push(self, mid: float) -> None:
        if self.mids:
            r = math.log(mid / self.mids[-1])
            x = r * r / self.dt
            self.samples.append(x)
            self.ref_var = x if self.ref_var is None else (1.0 - self.alpha) * self.ref_var + self.alpha * x
        self.mids.append(mid)

    def short_var(self) -> float:
        return float(sum(self.samples) / len(self.samples)) if self.samples else 0.0

    def V(self, t_since_open_s: float) -> float:
        if t_since_open_s < self.warmup_s or not self.ref_var or self.ref_var <= 0.0:
            return 1.0
        return math.sqrt(self.short_var() / self.ref_var)

    def log_return(self, lag_s: float) -> float:
        """ln(mid / mid lag_s ago); with less history, against the oldest mid kept."""
        if len(self.mids) < 2:
            return 0.0
        k = int(round(lag_s / self.dt))
        past = self.mids[-1 - k] if len(self.mids) > k else self.mids[0]
        return math.log(self.mids[-1] / past)

    def s30(self) -> float:
        return math.sqrt((self.ref_var or 0.0) * 1800.0)


# ── the crowd scheduler ───────────────────────────────────────────────────


class RetailCrowdAgent(TradingAgent):
    def __init__(
        self,
        id: int,
        symbol: str,
        trader_ids: List[int],
        kappa_v: float,
        mu_per_agent: float = RETAIL["mu_per_agent"],
        kappa_n: float = RETAIL["kappa_n"],
        cap: float = RETAIL["cap"],
        dt_c_s: float = RETAIL["dt_c_s"],
        name: Optional[str] = None,
        type: Optional[str] = None,
        random_state: Optional[np.random.RandomState] = None,
    ) -> None:
        super().__init__(id, name, type, random_state, starting_cash=0, log_orders=False)
        self.symbol = symbol
        self.trader_ids = list(trader_ids)
        self.kappa_v = float(kappa_v)
        self.kappa_n = float(kappa_n)
        self.cap = float(cap)
        self.dt_ns = int(round(dt_c_s * 1e9))
        self.dt_s = float(dt_c_s)
        self.mu_per_s = float(mu_per_agent) * len(self.trader_ids) / SESSION_S
        self.vol = CrowdVolatility(dt_c_s, RETAIL["buffer_s"], RETAIL["n_short"], RETAIL["ref_half_life_s"],
                                   RETAIL["warmup_s"])
        self.news: List[Tuple[float, float]] = []  # (t since open in s, sentiment)
        self.news_half_life_s = float(RETAIL["news_half_life_s"])
        self.last_mid: Optional[float] = None
        # stop registry: trader id -> (stop, version); a max-heap of (-stop, version, id)
        self.stops: Dict[int, Tuple[float, int]] = {}
        self._stop_heap: List[Tuple[float, int, int]] = []
        self._stop_version = 0
        self._awaiting_spread = False
        self.n_actions = 0
        self.n_stops_triggered = 0

    def get_wake_frequency(self) -> NanosecondTime:
        return 0  # first tick at the open; then every dt_c

    def wakeup(self, current_time: NanosecondTime) -> None:
        can_trade = super().wakeup(current_time)
        if not can_trade:
            return
        self._awaiting_spread = True
        self.get_current_spread(self.symbol)
        self.set_wakeup(current_time + self.dt_ns)  # always reschedule while open

    def receive_message(self, current_time: NanosecondTime, sender_id: int, message: Message) -> None:
        super().receive_message(current_time, sender_id, message)
        if isinstance(message, NewsSentimentMsg):
            if message.symbol == self.symbol and self.mkt_open is not None:
                self.news.append(((current_time - self.mkt_open) / 1e9, float(message.sentiment)))
        elif isinstance(message, RetailStopUpdateMsg):
            self._set_stop(sender_id, message.stop)
        elif isinstance(message, QuerySpreadResponseMsg) and self._awaiting_spread:
            self._awaiting_spread = False
            if not self.mkt_closed:
                self._tick(current_time)

    # ── stop registry ─────────────────────────────────────────────────────

    def _set_stop(self, trader_id: int, stop: Optional[float]) -> None:
        if stop is None:
            self.stops.pop(trader_id, None)
            return
        self._stop_version += 1
        self.stops[trader_id] = (float(stop), self._stop_version)
        heapq.heappush(self._stop_heap, (-float(stop), self._stop_version, trader_id))

    def _check_stops(self, mid: float, bid: Optional[int]) -> None:
        h = self._stop_heap
        while h and -h[0][0] >= mid:
            neg_stop, ver, tid = heapq.heappop(h)
            cur = self.stops.get(tid)
            if cur is None or cur[1] != ver:
                continue  # replaced or removed: stale heap entry
            del self.stops[tid]
            self.n_stops_triggered += 1
            self.send_message(tid, RetailStopTriggeredMsg(bid=bid, stop=-neg_stop))

    # ── one 5-s tick ──────────────────────────────────────────────────────

    def _tick(self, current_time: NanosecondTime) -> None:
        bid, _, ask, _ = self.get_known_bid_ask(self.symbol)
        if bid and ask:
            self.last_mid = (bid + ask) / 2.0
        if self.last_mid is None:
            return  # no two-sided book seen yet: no snapshot to act on
        mid = self.last_mid
        self.vol.push(mid)
        t = (current_time - self.mkt_open) / 1e9
        u = u_activity(t)
        v = self.vol.V(t)
        nn = news_level(self.news, t, self.news_half_life_s)
        lam = crowd_intensity(self.mu_per_s, u, v, nn, self.kappa_v, self.kappa_n, self.cap)
        n = int(self.random_state.poisson(lam * self.dt_s))
        self._check_stops(mid, bid or None)
        if n:
            snap = dict(bid=bid or None, ask=ask or None, mid=mid, r_5=self.vol.log_return(300.0),
                        r_30=self.vol.log_return(1800.0), s_30=self.vol.s30())
            for _ in range(n):
                tid = self.trader_ids[int(self.random_state.randint(len(self.trader_ids)))]
                self.send_message(tid, RetailActNowMsg(**snap))
            self.n_actions += n
        self.logEvent("CROWD_TICK", {"lam": lam, "n": n, "V": v, "Nn": nn, "U": u, "mid": mid}, deepcopy_event=False)


# ── one retail trader ─────────────────────────────────────────────────────


class RetailTraderAgent(TradingAgent):
    def __init__(
        self,
        id: int,
        symbol: str,
        crowd_id: int,
        r_bar: int,
        p_stop: float = RETAIL["p_stop"],
        name: Optional[str] = None,
        type: Optional[str] = None,
        random_state: Optional[np.random.RandomState] = None,
    ) -> None:
        wealth = int(RETAIL["wealth_c"])
        shares = int(round(wealth * RETAIL["stock_frac"] / r_bar))
        super().__init__(id, name, type, random_state, starting_cash=wealth - shares * int(r_bar), log_orders=False)
        self.symbol = symbol
        self.crowd_id = int(crowd_id)
        self.p_stop = float(p_stop)  # kept for the payload's parameter card (no draw)
        self.starting_shares = shares  # endowment, for the payload's population table
        self.start_value = wealth  # cents: cash + shares at r_bar
        self.holdings[symbol] = shares
        # construction draws, fixed order: type, stop user, stop distance
        u_kind = self.random_state.random_sample()
        p_liq, p_trend, _ = RETAIL["p_kinds"]
        self.kind = "liquidity" if u_kind < p_liq else ("trend" if u_kind < p_liq + p_trend else "contrarian")
        self.stop_user = bool(self.random_state.random_sample() < p_stop)
        lo, hi = RETAIL["stop_d_range"]
        self.stop_d = float(self.random_state.uniform(lo, hi))
        self.beta = float(RETAIL["beta"])
        self.collar = float(RETAIL["collar"])
        self.size_median = float(RETAIL["size_median"])
        self.size_sigma = float(RETAIL["size_sigma_ln"])
        self.has_stop = False

    def get_wake_frequency(self) -> NanosecondTime:
        return 0  # the standard start wake only (market hours, close price)

    def wakeup(self, current_time: NanosecondTime) -> None:
        # TradingAgent.wakeup returns a bool; the kernel treats any non-None wakeup
        # result as a gym interruption and stops, so it must not be passed on
        super().wakeup(current_time)

    # ── commitments of orders that can still fill (resting or cancel in flight) ──

    def _committed(self, side_bid: bool) -> Tuple[int, int]:
        """(shares, cents) of own open orders on one side (worst case at the limit)."""
        q = c = 0
        for o in self.orders.values():
            if isinstance(o, LimitOrder) and o.side.is_bid() == side_bid:
                q += int(o.quantity)
                c += int(o.quantity) * int(o.limit_price)
        return q, c

    def receive_message(self, current_time: NanosecondTime, sender_id: int, message: Message) -> None:
        super().receive_message(current_time, sender_id, message)
        if isinstance(message, RetailActNowMsg):
            self.act(message)
        elif isinstance(message, RetailStopTriggeredMsg):
            self.stop_triggered(message)

    def act(self, m: RetailActNowMsg) -> None:
        self.cancel_all_orders()
        z = (m.r_30 / m.s_30) if m.s_30 and m.s_30 > 0 else 0.0
        buy = self.random_state.random_sample() < p_buy(self.kind, z, self.beta)
        q = max(1, int(round(self.random_state.lognormal(math.log(self.size_median), self.size_sigma))))
        if buy:
            if not m.ask:
                return self._skip("no ask")
            limit = int(math.ceil(m.ask * (1.0 + self.collar)))
            _, committed_c = self._committed(True)
            free_cash = int(self.holdings.get("CASH", 0)) - committed_c
            q = min(q, max(0, free_cash // limit))
            if q <= 0:
                return self._skip("no cash")
            side = Side.BID
        else:
            if not m.bid:
                return self._skip("no bid")
            limit = max(1, int(math.floor(m.bid * (1.0 - self.collar))))
            committed_q, _ = self._committed(False)
            q = min(q, int(self.holdings.get(self.symbol, 0)) - committed_q)
            if q <= 0:
                return self._skip("no shares")
            side = Side.ASK
        self.place_limit_order(self.symbol, q, side, limit)
        self.logEvent("RETAIL_ACTION", {"kind": self.kind, "side": "BUY" if buy else "SELL", "q": q,
                                        "limit": limit, "z": z}, deepcopy_event=False)

    def stop_triggered(self, m: RetailStopTriggeredMsg) -> None:
        self.has_stop = False
        self.cancel_all_orders()
        committed_q, _ = self._committed(False)
        q = int(self.holdings.get(self.symbol, 0)) - committed_q
        self.logEvent("STOP_TRIGGERED", {"stop": m.stop, "q": max(q, 0)}, deepcopy_event=False)
        if q <= 0 or not m.bid:
            return self._skip("stop: no shares" if q <= 0 else "stop: no bid")
        limit = max(1, int(math.floor(m.bid * (1.0 - self.collar))))
        self.place_limit_order(self.symbol, q, Side.ASK, limit)

    def _skip(self, reason: str) -> None:
        self.logEvent("RETAIL_SKIP", {"reason": reason}, deepcopy_event=False)

    def order_executed(self, order: Order) -> None:
        super().order_executed(order)
        if order.side.is_bid():
            if self.stop_user:
                stop = float(order.fill_price) * (1.0 - self.stop_d)
                self.has_stop = True
                self.send_message(self.crowd_id, RetailStopUpdateMsg(stop=stop))
                self.logEvent("STOP_SET", {"stop": stop}, deepcopy_event=False)
        elif self.has_stop and int(self.holdings.get(self.symbol, 0)) <= 0:
            self.has_stop = False  # nothing left to protect
            self.send_message(self.crowd_id, RetailStopUpdateMsg(stop=None))
            self.logEvent("STOP_CLEARED", {}, deepcopy_event=False)

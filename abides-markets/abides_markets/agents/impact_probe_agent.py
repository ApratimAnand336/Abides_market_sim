"""Impact probe: a test instrument that executes one parent order (FinVerse spec v1.3, §6.2).

Not a market participant. It splits a parent order of `quantity` shares into
n = duration_s / child_interval_s MARKET orders, one every child_interval_s
seconds from start_time, of size floor(quantity / n) (the remainder added to
the last child). It uses no random numbers; its random_state is only there
because every agent has one, and build_config gives it a constant
RandomState(0) so the global stream is not consumed.

With quantity == 0 it requests no wakeup beyond the one every TradingAgent
gets at kernel start and never sends an order (the C-NULL / T-L6 probe).

Log events: PROBE_CHILD {i, planned, time} at each child; PROBE_ARRIVAL_MID
{mid} (from a spread query sent with the first child, before its order);
PROBE_SUMMARY {planned, filled, unfilled, vwap_cents, arrival_mid} at kernel
stop; ORDER_EXECUTED / HOLDINGS_UPDATED as every TradingAgent.
"""

from typing import Dict, Optional

import numpy as np

from abides_core import Message, NanosecondTime

from ..messages.query import QuerySpreadResponseMsg
from ..orders import Order, Side
from .trading_agent import TradingAgent


class ImpactProbeAgent(TradingAgent):
    def __init__(
        self,
        id: int,
        symbol: str,
        side: str,
        quantity: int,
        start_time: NanosecondTime,
        duration_s: int = 300,
        child_interval_s: int = 10,
        starting_cash: int = 0,
        starting_shares: int = 0,
        name: Optional[str] = None,
        type: Optional[str] = None,
        random_state: Optional[np.random.RandomState] = None,
        log_orders: bool = True,
    ) -> None:
        super().__init__(id, name, type, random_state, starting_cash, log_orders)
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL, got {side!r}")
        if quantity < 0:
            raise ValueError("quantity must be >= 0")
        self.symbol = symbol
        self.side = side
        self.quantity = int(quantity)
        self.start_time = int(start_time)
        self.duration_s = int(duration_s)
        self.child_interval_s = int(child_interval_s)
        self.starting_shares = int(starting_shares)
        if self.starting_shares:
            self.holdings[symbol] = self.starting_shares

        n = max(1, self.duration_s // self.child_interval_s)
        base = self.quantity // n
        sizes = [base] * n
        sizes[-1] += self.quantity - base * n
        step = self.child_interval_s * 1_000_000_000
        # child time (ns) -> (index, planned quantity); zero-size children are skipped
        self.children: Dict[int, tuple] = {
            self.start_time + i * step: (i, q) for i, q in enumerate(sizes) if q > 0
        } if self.quantity > 0 else {}

        self._children_done = set()  # TradingAgent also wakes us at the open
        self.filled = 0
        self.filled_cost = 0  # cents
        self.arrival_mid: Optional[float] = None
        self._awaiting_arrival = False

    # ── lifecycle ─────────────────────────────────────────────────────────

    def kernel_starting(self, start_time: NanosecondTime) -> None:
        super().kernel_starting(start_time)  # the one wakeup every TradingAgent gets
        for t in self.children:
            self.set_wakeup(t)

    def kernel_stopping(self) -> None:
        super().kernel_stopping()
        self.logEvent("PROBE_SUMMARY", {
            "side": self.side,
            "planned": self.quantity,
            "filled": self.filled,
            "unfilled": self.quantity - self.filled,
            "vwap_cents": (self.filled_cost / self.filled) if self.filled else None,
            "arrival_mid": self.arrival_mid,
            "n_children": len(self.children),
        })

    def wakeup(self, current_time: NanosecondTime) -> None:
        can_trade = super().wakeup(current_time)
        child = self.children.get(int(current_time))
        if child is None or child[0] in self._children_done:
            return
        i, q = child
        self._children_done.add(i)
        self.logEvent("PROBE_CHILD", {"i": i, "planned": q, "time": int(current_time), "can_trade": bool(can_trade)})
        if not can_trade:
            return
        if i == 0:
            # the arrival mid: queried before the first order is sent, so the
            # exchange answers it first (messages are delivered in send order)
            self._awaiting_arrival = True
            self.get_current_spread(self.symbol)
        self.place_market_order(self.symbol, q, Side.BID if self.side == "BUY" else Side.ASK, ignore_risk=True)

    # ── messages ──────────────────────────────────────────────────────────

    def receive_message(self, current_time: NanosecondTime, sender_id: int, message: Message) -> None:
        super().receive_message(current_time, sender_id, message)
        if self._awaiting_arrival and isinstance(message, QuerySpreadResponseMsg):
            self._awaiting_arrival = False
            bid, _, ask, _ = self.get_known_bid_ask(self.symbol)
            if bid and ask:
                self.arrival_mid = (bid + ask) / 2.0
            self.logEvent("PROBE_ARRIVAL_MID", {"mid": self.arrival_mid})

    def order_executed(self, order: Order) -> None:
        super().order_executed(order)
        self.filled += int(order.quantity)
        self.filled_cost += int(order.quantity) * int(order.fill_price)

    def get_wake_frequency(self) -> NanosecondTime:
        # TradingAgent asks for an offset from the open once it knows the
        # market hours; the probe needs no other wakeups than its children
        return 0

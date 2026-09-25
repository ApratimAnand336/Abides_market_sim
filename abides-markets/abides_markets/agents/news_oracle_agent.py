"""
News Oracle Agent
─────────────────
A lightweight ABIDES agent that acts as a broadcast tower for news sentiment.

It does NOT interact with the Exchange. It receives news events (injected
externally or scheduled) and broadcasts a NewsSentimentMsg to every other
agent in the simulation via the Kernel's generic messaging system.
"""

import logging
from typing import List, Optional

import numpy as np

from abides_core import NanosecondTime
from abides_core.agent import Agent
from abides_core.message import Message

from ..messages.news import NewsSentimentMsg

logger = logging.getLogger(__name__)


class NewsOracleAgent(Agent):
    """
    Broadcasts news sentiment to all agents in the simulation.

    Usage:
        1. Instantiate and add to the agent list in your config.
        2. Call `enqueue_news(symbol, sentiment, headline, delivery_time)`
           before the simulation starts to schedule news events.
        3. During the simulation, the agent wakes at each scheduled time
           and broadcasts the corresponding NewsSentimentMsg.
    """

    def __init__(
        self,
        id: int,
        name: Optional[str] = "NewsOracle",
        type: Optional[str] = "NewsOracleAgent",
        random_state: Optional[np.random.RandomState] = None,
    ) -> None:
        super().__init__(id, name, type, random_state)

        # Queue of news events: list of (delivery_time_ns, symbol, sentiment, headline)
        self._news_queue: List[tuple] = []
        # Index into the queue for the next event to deliver
        self._next_idx: int = 0

    # ── Public API (call before simulation starts) ───────────────────────

    def enqueue_news(
        self,
        symbol: str,
        sentiment: float,
        headline: str,
        delivery_time: NanosecondTime,
    ) -> None:
        """
        Schedule a news event for broadcast at a specific simulation time.

        Args:
            symbol:        Ticker the news refers to (e.g. "ABM").
            sentiment:     Float in [-1, 1].
            headline:      Raw headline string.
            delivery_time: Nanosecond timestamp at which to broadcast.
        """
        self._news_queue.append((delivery_time, symbol, sentiment, headline))
        # Keep sorted by time
        self._news_queue.sort(key=lambda x: x[0])

    # ── Lifecycle ────────────────────────────────────────────────────────

    def kernel_starting(self, start_time: NanosecondTime) -> None:
        # Do NOT call super().kernel_starting() — that schedules a
        # wakeup at start_time which we don't need unless we have news.
        self.current_time = start_time

        # Schedule wakeup for the first news event
        if self._news_queue:
            self.set_wakeup(self._news_queue[0][0])
            logger.info(
                f"{self.name}: {len(self._news_queue)} news events queued. "
                f"First at t={self._news_queue[0][0]}"
            )

    def kernel_stopping(self) -> None:
        pass

    # ── Wakeup: broadcast the news ──────────────────────────────────────

    def wakeup(self, current_time: NanosecondTime) -> None:
        super().wakeup(current_time)

        # Deliver all news events whose time has arrived
        while (
            self._next_idx < len(self._news_queue)
            and self._news_queue[self._next_idx][0] <= current_time
        ):
            _, symbol, sentiment, headline = self._news_queue[self._next_idx]
            self._broadcast(symbol, sentiment, headline)
            self._next_idx += 1

        # Schedule wakeup for the next event (if any remain)
        if self._next_idx < len(self._news_queue):
            self.set_wakeup(self._news_queue[self._next_idx][0])

    # ── Internal: broadcast to all agents ───────────────────────────────

    def _broadcast(self, symbol: str, sentiment: float, headline: str) -> None:
        """Send a NewsSentimentMsg to every agent except ourselves."""
        msg = NewsSentimentMsg(
            symbol=symbol,
            sentiment=sentiment,
            headline=headline,
        )

        num_recipients = 0
        for agent in self.kernel.agents:
            if agent.id != self.id:
                self.send_message(agent.id, msg)
                num_recipients += 1

        self.logEvent("NEWS_BROADCAST", {
            "symbol": symbol,
            "sentiment": round(sentiment, 4),
            "headline": headline,
            "recipients": num_recipients,
        })

        logger.info(
            f"{self.name}: Broadcast [{symbol}] sentiment={sentiment:+.4f} "
            f"to {num_recipients} agents  |  \"{headline}\""
        )

    # ── We don't process inbound messages ────────────────────────────────

    def receive_message(
        self, current_time: NanosecondTime, sender_id: int, message: Message
    ) -> None:
        super().receive_message(current_time, sender_id, message)

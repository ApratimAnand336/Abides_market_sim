"""Messages between the retail crowd scheduler and its traders (FinVerse spec v1.5 A4).

They use the kernel's generic messaging (as NewsSentimentMsg), not the exchange protocol.
Prices are integer cents (None if that side of the book is empty); returns are log returns.
"""

from dataclasses import dataclass
from typing import Optional

from abides_core.message import Message


@dataclass
class RetailActNowMsg(Message):
    """Crowd -> trader: act now, with the crowd's market snapshot."""

    bid: Optional[int] = None
    ask: Optional[int] = None
    mid: Optional[float] = None
    r_5: float = 0.0  # ln(mid / mid 5 min ago)
    r_30: float = 0.0  # ln(mid / mid 30 min ago)
    s_30: float = 0.0  # typical 30-min sd of log returns, sqrt(sigma_ref^2 * 1800 s)


@dataclass
class RetailStopTriggeredMsg(Message):
    """Crowd -> trader: the mid crossed your stop (sent once; the stop is removed)."""

    bid: Optional[int] = None
    stop: float = 0.0


@dataclass
class RetailStopUpdateMsg(Message):
    """Trader -> crowd: register (or replace) my stop price in cents; None removes it."""

    stop: Optional[float] = None

"""
News Sentiment Message
──────────────────────
Custom ABIDES Message subclass for broadcasting news sentiment
to trading agents. This bypasses the ITCH/OUCH exchange protocol
and uses the Kernel's generic message system.
"""

from dataclasses import dataclass
from abides_core.message import Message


@dataclass
class NewsSentimentMsg(Message):
    """
    Broadcast by the NewsOracleAgent to all trading agents.

    Attributes:
        symbol:    The ticker symbol the news refers to (e.g., "ABM").
        sentiment: A float in [-1, 1].  +1 = maximally positive, -1 = maximally negative.
        headline:  The raw news headline string (for logging / display).
    """
    symbol: str = ""
    sentiment: float = 0.0
    headline: str = ""

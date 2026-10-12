"""Gross budget limit for the stock ABIDES agents (FinVerse spec v1.4 Part 5, K10).

The worst-case rule of spec v1.4 §4.5 with w_max = L and w_min = -L: after
the order, and assuming every open order on the same side also fills, the
position value at the order price stays within L x current wealth:

    n = shares held, O = open same-side quantity, p = order price,
    W_p = cash + n * p
    BUY  q allowed iff (n + O + q) * p <=  L * W_p
    SELL q allowed iff (n - O - q) * p >= -L * W_p
    W_p <= 0: only orders that reduce |n| (never past zero).

Pure integer/float arithmetic, no randomness.
"""

import math
from typing import Dict


def allowed_qty_wealth(
    is_buy: bool, q: int, price: float, cash: float, n: int, open_same_side_qty: int,
    w_min: float, w_max: float,
) -> int:
    """Largest quantity <= q allowed by the worst-case rule with position
    bounds [w_min, w_max] x wealth (shared with the informed fundamentalist,
    spec v1.4 §4.5)."""
    q = int(q)
    if q <= 0:
        return 0
    p = float(price)
    if p <= 0:
        return 0
    W = cash + n * p
    O = int(open_same_side_qty)
    if W <= 0:
        # only orders that reduce |n|, never past zero
        room = (-n - O) if is_buy else (n - O)
        return max(0, min(q, room))
    if is_buy:
        room = math.floor(w_max * W / p - n - O + 1e-9)
    else:
        room = math.floor(n - O - w_min * W / p + 1e-9)
    return max(0, min(q, room))


class GrossLimit:
    """Gross position value <= L x current wealth at the order price."""

    def __init__(self, L: float = 2.0) -> None:
        self.L = float(L)

    def allowed_qty(
        self, side, q: int, price: float, holdings: Dict[str, int], symbol: str, open_same_side_qty: int,
    ) -> int:
        """side: Side (is_bid()) or "BUY"/"SELL"."""
        is_buy = side.is_bid() if hasattr(side, "is_bid") else str(side).upper() in ("BUY", "BID")
        return allowed_qty_wealth(
            is_buy, q, price, holdings.get("CASH", 0), holdings.get(symbol, 0), open_same_side_qty,
            -self.L, self.L,
        )

    def __repr__(self) -> str:
        return f"GrossLimit(L={self.L:g})"

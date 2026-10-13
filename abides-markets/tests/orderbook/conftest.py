"""spec v1.4.2 Part 1 (T-S1): every order-book unit test runs with the running
visible totals checked against a full recomputation after every book event.
OrderBook.DEBUG_TOTALS stays False outside tests."""

import pytest

from abides_markets.order_book import OrderBook


@pytest.fixture(autouse=True)
def _assert_running_totals():
    OrderBook.DEBUG_TOTALS = True
    yield
    OrderBook.DEBUG_TOTALS = False

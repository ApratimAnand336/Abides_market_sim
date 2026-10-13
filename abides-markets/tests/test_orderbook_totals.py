"""OrderBook running visible totals (FinVerse spec v1.4.2 Part 1).

T-S1  the running totals equal a full recomputation after every book event:
      hand-built books (hidden orders, partial cancel, modify up/down, replace,
      partial and full fills; the upstream orderbook/ tests also run with the
      check on via orderbook/conftest.py), a 1-hour default market and a 1-hour
      D-60fl2M market.
T-S2  bit-identical results: the full-day seed-42 D-60fl2M-S2 fingerprint equals
      the one recorded BEFORE the change (docs/v1.4/lab/reference_hashes.json);
      I8 (test_invariants.py) covers the v1.3 default market.
"""

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from abides_markets.order_book import OrderBook
from abides_markets.orders import LimitOrder, MarketOrder, Side

from .orderbook import SYMBOL, TIME, FakeExchangeAgent

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def debug_totals():
    OrderBook.DEBUG_TOTALS = True
    yield
    OrderBook.DEBUG_TOTALS = False


def _lo(qty, side, price, hidden=False, agent=1):
    return LimitOrder(agent, TIME, SYMBOL, qty, side, price, is_hidden=hidden)


def test_s1_hand_built_book(debug_totals):
    book = OrderBook(FakeExchangeAgent(), SYMBOL)
    o = [_lo(40, Side.BID, 100), _lo(10, Side.BID, 100, hidden=True), _lo(25, Side.BID, 99),
         _lo(30, Side.ASK, 105), _lo(5, Side.ASK, 105, hidden=True), _lo(20, Side.ASK, 106)]
    for x in o:
        book.handle_limit_order(x)
    assert (book._vis_bid_qty, book._vis_ask_qty) == (65, 50)
    book.partial_cancel_order(o[0], 15)  # 40 -> 25
    assert book._vis_bid_qty == 50
    m = deepcopy(o[2])
    m.quantity = 35  # modify up (moves to the back of its level)
    book.modify_order(o[2], m)
    assert book._vis_bid_qty == 60
    m2 = deepcopy(o[3])
    m2.quantity = 12  # modify down
    book.modify_order(o[3], m2)
    assert book._vis_ask_qty == 32
    new = _lo(7, Side.ASK, 107)
    book.replace_order(1, o[5], new)  # 20 at 106 -> 7 at 107
    assert book._vis_ask_qty == 19
    book.handle_limit_order(_lo(5, Side.BID, 105, agent=2))  # partial fill of the visible 12
    assert book._vis_ask_qty == 14
    book.handle_market_order(MarketOrder(2, TIME, SYMBOL, 20, Side.BID))  # visible 7, hidden 5, then 107
    book.cancel_order(o[1])  # hidden bid: no change to the visible total
    book.handle_market_order(MarketOrder(3, TIME, SYMBOL, 100, Side.ASK))  # sweep the bids
    assert book._recompute_vis() == (book._vis_bid_qty, book._vis_ask_qty)


def _market(extra, tmp):
    from abides_core import abides
    from abides_markets.configs.rmsc04_ekf import build_config
    from api.jobs import run_config_kwargs

    from .sim_helpers import params

    kw = run_config_kwargs(params())
    kw.update(extra)
    cfg = build_config(**kw)
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        es = abides.run(cfg)
    finally:
        os.chdir(cwd)
    return es


@pytest.mark.parametrize("name", ["default", "D-60fl2M"])
def test_s1_markets_keep_totals(name, debug_totals, tmp_path):
    """1-hour markets with the check on: any mismatch raises inside the run."""
    from api import lab

    extra = {} if name == "default" else {**lab.design_extra("D-60fl2M"), "num_value_agents": 0}
    es = _market(extra, tmp_path)
    ob = es["agents"][0].order_books["ABM"]
    assert sum(1 for h in ob.history if h["type"] == "EXEC") > 100
    assert ob._recompute_vis() == (ob._vis_bid_qty, ob._vis_ask_qty)


def test_s2_full_day_d60fl2m_s2_bit_identical(tmp_path):
    ref = json.loads((REPO / "docs/v1.4/lab/reference_hashes.json").read_text(encoding="utf-8"))
    want = ref["runs"]["D-60fl2M-S2/42"]
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONWARNINGS": "ignore"}
    out = subprocess.run([sys.executable, str(REPO / "scripts/fingerprint_run.py"), "D-60fl2M-S2", "42"],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=900)
    assert out.returncode == 0, out.stderr[-2000:]
    got = json.loads(out.stdout.strip().splitlines()[-1])
    print(f"T-S2: wall time {got['wall_time_s']} s")
    assert {k: got[k] for k in ("execs", "holdings", "n_execs")} == want

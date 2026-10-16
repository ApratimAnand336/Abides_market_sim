"""Bit-identical engine speed-up (FinVerse spec v1.5 A1).

T-S4  the full-day seed-42 P0 EXEC hash and final holdings hash equal the ones recorded
      before the change (docs/v1.4/lab/reference_hashes.json, "P0-C/42"); I8 and
      I8-legacy (test_invariants.py) cover the short markets.
T-S5  the lab metrics of P0 seed 42 are identical (exact equality of every metric, the
      sanity table and the fingerprint) with and without sparse depth logging
      (book_log_depth_interval_s, A1.2c).
Unit tests, one per change:
  - kernel message heap pops in exactly the order of queue.PriorityQueue (ties included);
  - Agent._event_copy equals copy.deepcopy (values, independence, shared sub-objects);
  - fmt_ts equals the pandas formatting it replaces;
  - ExchangeAgent.get_time_dropout equals the former DataFrame.iterrows scan;
  - sparse depth rows: every row's first level equals the full-depth query's first level;
  - no agent's open-order entry is the object resting in the book (A1.2a: the order copy
    the agent no longer makes is not needed because the exchange copies the order).
"""

import json
import math
import os
import queue
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from abides_core.agent import _event_copy
from abides_core.kernel import _MessageHeap
from abides_core.utils import fmt_ts
from abides_markets.order_book import OrderBook
from abides_markets.orders import LimitOrder, Side

from .orderbook import SYMBOL, TIME, FakeExchangeAgent
from .sim_helpers import params, run

REPO = Path(__file__).resolve().parents[2]


# ── unit tests, one per change ────────────────────────────────────────────


def test_message_heap_order_equals_priority_queue():
    rs = np.random.RandomState(7)
    pq, mh = queue.PriorityQueue(), _MessageHeap()
    out_pq, out_mh = [], []
    for step in range(20_000):
        if rs.rand() < 0.6 or pq.empty():
            # many ties on time and on (sender, recipient): the third key decides
            item = (int(rs.randint(0, 50)), (int(rs.randint(0, 3)), int(rs.randint(0, 3)), int(rs.randint(0, 10**6))))
            pq.put(item)
            mh.put(item)
        else:
            out_pq.append(pq.get())
            out_mh.append(mh.get())
        assert pq.qsize() == mh.qsize() and pq.empty() == mh.empty()
    while not pq.empty():
        out_pq.append(pq.get())
        out_mh.append(mh.get())
    assert out_pq == out_mh and mh.empty()


class _Obj:
    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        return type(other) is _Obj and other.v == self.v


def test_event_copy_equals_deepcopy():
    shared = [1, 2]
    tup_atomic = (1, "a", None)
    events = [
        "", "x", 3, 2.5, None, True, np.float64(1.5), np.int64(3),
        {"z": 1.25, "side": "BUY", "blocked_sides": ["ASK"], "x_hat": np.float64(2.0)},
        [(100, 5), (99, 7)], [[100, 5], [99, 7]], [],
        {"a": shared, "b": shared, "t": tup_atomic, "nested": {"l": [1, (2, [3])]}},
        {"obj": _Obj([1]), "arr": np.arange(3)},
        (1, [2], {"k": (3,)}),
    ]
    for ev in events:
        got, ref = _event_copy(ev, {}), deepcopy(ev)
        assert type(got) is type(ref)
        if isinstance(ev, dict) and "arr" in ev:
            assert got["obj"] == ref["obj"] and got["obj"] is not ev["obj"]
            assert np.array_equal(got["arr"], ref["arr"]) and got["arr"] is not ev["arr"]
        else:
            assert got == ref
    # independence: containers are new objects; a tuple of atomics is returned as is
    ev = {"a": shared, "b": shared, "t": tup_atomic}
    got = _event_copy(ev, {})
    assert got is not ev and got["a"] is not shared and got["t"] is tup_atomic
    assert got["a"] is got["b"]  # shared sub-objects stay shared, as with deepcopy
    shared.append(3)
    assert got["a"] == [1, 2]


def test_fmt_ts_equals_pandas():
    ref = lambda t: pd.Timestamp(t, unit="ns").strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
    rs = np.random.RandomState(0)
    day = int(pd.Timestamp("2021-02-05 09:30").value)
    vals = [0, -1, 1, 999_999_999, 10**9, -(10**9), -(10**9) - 1,
            int(pd.Timestamp.min.value), int(pd.Timestamp.max.value)]
    vals += [int(x) for x in rs.randint(-(2**62), 2**62, 5000, dtype=np.int64)]
    vals += [day + int(x) for x in rs.randint(0, 30_000 * 10**9, 5000, dtype=np.int64)]
    for v in vals:
        assert fmt_ts(v) == ref(v) and fmt_ts(np.int64(v)) == ref(np.int64(v))
    assert fmt_ts(day + 0.5e9) == ref(day + 0.5e9)  # non-integer: pandas path


def _time_dropout_iterrows(book):
    """The pre-v1.5 ExchangeAgent.get_time_dropout scan (reference)."""
    df = pd.DataFrame(book)
    total_time = df["QuoteTime"].iloc[-1] - df["QuoteTime"].iloc[0]
    nb = na = False
    tb0 = ta0 = 0
    Tb = Ta = 0
    for _, row in df.iterrows():
        if (len(row["bids"]) == 0) & (nb == False):  # noqa: E712
            tb0, nb = row["QuoteTime"], True
        elif (len(row["bids"]) != 0) & (nb == True):  # noqa: E712
            Tb += row["QuoteTime"] - tb0
            nb = False
        if (len(row["asks"]) == 0) & (na == False):  # noqa: E712
            ta0, na = row["QuoteTime"], True
        elif (len(row["asks"]) != 0) & (na == True):  # noqa: E712
            Ta += row["QuoteTime"] - ta0
            na = False
    return (Ta / 1e9, Tb / 1e9, 100 * Ta / total_time, 100 * Tb / total_time)


def test_time_dropout_equals_iterrows():
    from abides_markets.agents.exchange_agent import ExchangeAgent

    rs = np.random.RandomState(3)
    t = int(pd.Timestamp("2021-02-05 09:30").value)
    book = []
    for _ in range(3000):
        t += int(rs.randint(1, 5 * 10**9, dtype=np.int64))
        bids = np.array([(99_990, 5)]) if rs.rand() > 0.1 else np.array([])
        asks = np.array([(100_010, 5), (100_011, 2)]) if rs.rand() > 0.15 else np.array([])
        book.append({"QuoteTime": t, "bids": bids, "asks": asks})
    ex = ExchangeAgent.__new__(ExchangeAgent)
    ex.metric_trackers = {}
    ExchangeAgent.get_time_dropout(ex, book, SYMBOL)
    m = ex.metric_trackers[SYMBOL]
    got = (m.total_time_no_liquidity_asks, m.total_time_no_liquidity_bids,
           m.pct_time_no_liquidity_asks, m.pct_time_no_liquidity_bids)
    assert got == _time_dropout_iterrows(book)


def test_sparse_depth_rows_keep_l1():
    agent = FakeExchangeAgent()
    agent.book_logging = True
    agent.book_log_depth = 10
    agent.book_log_depth_interval_ns = 10**9
    sparse = OrderBook(agent, SYMBOL)
    agent_full = FakeExchangeAgent()
    agent_full.book_logging = True
    agent_full.book_log_depth = 10
    full = OrderBook(agent_full, SYMBOL)
    rs = np.random.RandomState(5)
    for i in range(400):
        agent.current_time = agent_full.current_time = TIME + i * 250_000_000  # 4 events per s
        side = Side.BID if rs.rand() < 0.5 else Side.ASK
        px = int(100_000 + (-1 if side.is_bid() else 1) * rs.randint(1, 30))
        hidden = rs.rand() < 0.1  # hidden-only levels: the first visible level is deeper
        q = int(rs.randint(1, 9))
        sparse.handle_limit_order(LimitOrder(1, agent.current_time, SYMBOL, q, side, px, is_hidden=hidden))
        full.handle_limit_order(LimitOrder(1, agent.current_time, SYMBOL, q, side, px, is_hidden=hidden))
    assert len(sparse.book_log2) == len(full.book_log2) > 300
    n_depth = 0
    last = None
    for rs_, rf in zip(sparse.book_log2, full.book_log2):
        assert rs_["QuoteTime"] == rf["QuoteTime"]
        for k in ("bids", "asks"):
            assert len(rs_[k]) == 0 if len(rf[k]) == 0 else (rs_[k][0] == rf[k][0]).all()
        if len(rs_["bids"]) > 1 or len(rs_["asks"]) > 1:
            assert np.array_equal(rs_["bids"], rf["bids"]) and np.array_equal(rs_["asks"], rf["asks"])
            assert last is None or rs_["QuoteTime"] - last >= 10**9
            last = rs_["QuoteTime"]
            n_depth += 1
    assert 50 <= n_depth <= 101  # about one full-depth row per second of the 100 s


def test_agent_orders_never_alias_the_book(tmp_path):
    _, es, _ = run(params(end_time="10:00:00"), str(tmp_path))
    ob = es["agents"][0].order_books["ABM"]
    resting = {id(o) for side in (ob.bids, ob.asks) for pl in side
               for o, _ in pl.visible_orders + pl.hidden_orders}
    assert resting
    for a in es["agents"]:
        for o in getattr(a, "orders", {}).values():
            assert id(o) not in resting


# ── T-S4, T-S5: full days ─────────────────────────────────────────────────


def test_s4_full_day_p0_bit_identical(tmp_path):
    ref = json.loads((REPO / "docs/v1.4/lab/reference_hashes.json").read_text(encoding="utf-8"))
    want = ref["runs"]["P0-C/42"]
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONWARNINGS": "ignore"}
    out = subprocess.run([sys.executable, str(REPO / "scripts/fingerprint_run.py"), "P0-C", "42"],
                         cwd=tmp_path, env=env, capture_output=True, text=True, timeout=900)
    assert out.returncode == 0, out.stderr[-2000:]
    got = json.loads(out.stdout.strip().splitlines()[-1])
    print(f"T-S4: wall time {got['wall_time_s']} s")
    assert {k: got[k] for k in ("execs", "holdings", "n_execs")} == {k: want[k] for k in ("execs", "holdings", "n_execs")}


def _same(a, b):
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _lab_metrics(interval, log_dir):
    sys.path.insert(0, str(REPO / "scripts"))
    import realism_lab as RL
    from abides_core import abides
    from abides_markets.configs.rmsc04_ekf import build_config
    from api import lab
    from api import realism as R
    from api.jobs import run_config_kwargs

    kw = run_config_kwargs(lab.run_params("P0-C", 42))
    kw.update(lab.CONFIGS["P0-C"].get("extra", {}))
    kw["book_log_depth_interval_s"] = interval
    config = build_config(**kw)
    start = {a.id: (int(a.holdings.get("CASH", 0)), int(a.holdings.get("ABM", 0)))
             for a in config["agents"] if hasattr(a, "holdings")}
    cwd = os.getcwd()
    os.chdir(log_dir)
    try:
        es = abides.run(config)
    finally:
        os.chdir(cwd)
    s = R.series_from_end_state(es, config, "ABM", start_holdings=start)
    out = {"metrics": json.loads(json.dumps(RL._jsonable(R.run_metrics(s)))),
           "sanity": json.loads(json.dumps(RL._jsonable(R.agent_sanity(s)))),
           "fingerprint": RL._fingerprint(es)}
    rows = es["agents"][0].order_books["ABM"].book_log2
    out["n_depth_rows"] = sum(1 for r in rows if len(r["bids"]) > 1 or len(r["asks"]) > 1)
    out["n_rows"] = len(rows)
    return out


def test_s5_lab_metrics_identical_with_sparse_depth(tmp_path):
    full = _lab_metrics(None, str(tmp_path))
    sparse = _lab_metrics(1.0, str(tmp_path))
    print(f"T-S5: book_log2 rows {full['n_rows']}, depth rows {full['n_depth_rows']} -> {sparse['n_depth_rows']}")
    assert full["n_rows"] == sparse["n_rows"]
    assert sparse["n_depth_rows"] < full["n_depth_rows"] / 5
    for k in ("metrics", "sanity", "fingerprint"):
        assert _same(full[k], sparse[k]), k

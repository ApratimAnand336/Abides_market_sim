# Engine profile and bit-identical speed-up (spec v1.5 A1)

Date 2026-10-16. Machine: the owner's Windows 11 laptop (Python 3.13, numpy 2.2.6), 1 process.
Config: lab `P0-C`, seed 42, full day 09:30–16:00 (the v1.4 default market P0: 60 informed
fundamentalists D-60fl2M, 12 momentum EKF, 1000 noise agents, 2 ABIDES market makers).
Tools: `scripts/profile_day.py` (cProfile), `scripts/fingerprint_run.py` (wall time of
`abides.run` and the I1/I8 fingerprint), `scripts/profile_report.py` (these tables).

## Result

- **Median wall time of a full P0 day: 22.69 s → 12.13 s (−47%)**, 1 worker, 3 repeats per
  level, levels interleaved round-robin. The spec expected −20% to −40% (A1.4).
- **Bit-identical:** all 24 timed runs (8 levels × 3) have the same EXEC hash, holdings hash and
  execution count (20,518), equal to the v1.4 reference `P0-C/42` in
  `docs/v1.4/lab/reference_hashes.json` (T-S4). I8, I8-legacy and the regression sets are
  unchanged (A1.3; TESTING.md).
- Lab metrics with sparse depth logging (option c) equal those with full depth exactly
  (T-S5: every metric, the sanity table and the fingerprint).

## What changed (each bit-identical by construction and by test)

| level | change | why it is identical | unit test (`tests/test_engine_speed.py`) |
|---|---|---|---|
| 1 | Kernel message queue: `queue.PriorityQueue` → `_MessageHeap` (same `heapq` calls, no lock) | PriorityQueue is a lock around `heappush`/`heappop` on a list; the kernel is single-threaded | pops equal PriorityQueue's on 20,000 random operations with ties |
| 2 | `Agent.logEvent`: `_event_copy` instead of `deepcopy` for dict/list/tuple/scalars | copies exactly as `copy.deepcopy` (same memo, shared sub-objects stay shared, tuples of atomics returned as is); other objects still go to `deepcopy` | equality with `deepcopy`, independence, aliasing |
| 3 | 68 `logger.debug/info` statements whose arguments are formatted eagerly (f-strings, `.format`, `fmt_ts`, `Order.__str__`) wrapped in `if logger.isEnabledFor(...)` (AST transform; kernel, agent, exchange, trading agent, order book, fundamentalist, news oracle) | the messages are emitted unchanged when the level is on; the skipped arguments have no side effects | (output unchanged: T-S4, I8) |
| 4 | `fmt_ts`: integer ns → floor seconds → `datetime` + cache, instead of `pd.Timestamp(...).strftime` | same string for every integer in pandas' range (negative times included); other inputs keep the pandas path | 10,009 values incl. limits and negatives |
| 5 | `ExchangeAgent.get_time_dropout`: loop over `book_log2` instead of `DataFrame(book).iterrows()` | the same scan; times are integer ns (< 2^53, exact in float64); `total_time` keeps the int64 Series subtraction | equality with the old scan on 3,000 random rows |
| 6 | `TradingAgent.place_limit_order / place_market_order / place_multiple_orders`: no `deepcopy(order)` into `self.orders` (A1.2a) | the exchange deep-copies `message.order` before the book sees it; nothing mutates an order between placement and that copy (the only mutation outside the book is `order_executed`'s decrement, after the exchange processed the order) | no agent's open order is ever the object resting in the book (1-hour market) |
| 7 | `book_log_depth_interval_s` (A1.2c; `build_config`, `ExchangeAgent`; default None = every event). The lab sets 1.0 s: every `book_log2` row keeps L1, L2–L10 only every ≥ 1 s | between full-depth rows a row holds exactly the first level of the full-depth query (hidden-only levels skipped the same way), so L1 and empty-side times are unchanged; the dashboard path keeps every event | first level equal row by row; full-depth rows ≥ 1 s apart; T-S5 |

Not done: the order book's internal deep copies (enter_order, execute_order: hidden/visible
halves, matched and filled orders) are each needed because the book mutates its own copies;
`Order.to_dict` (deepcopy + `fmt_ts`, now cheap) is left as is.

## Remaining profile (after)

The largest items now are `isinstance` checks in message dispatch, the event copies themselves,
the order book's own order copies and the kernel loop; none is above 5% of own time.

### Top 15 by own time, before (v1.4 engine)

Total profiled time 58.2 s.

| # | function | calls | own s | cum s | own % |
|---|---|---|---|---|---|
| 1 | `abides-core/abides_core/utils.py:78(fmt_ts)` | 688,686 | 3.99 | 3.99 | 6.9 |
| 2 | `copy.py:119(deepcopy)` | 4,150,445 | 3.57 | 9.15 | 6.1 |
| 3 | `~:0(<built-in method builtins.isinstance>)` | 16,865,287 | 2.42 | 3.87 | 4.2 |
| 4 | `~:0(<built-in method builtins.sum>)` | 3,370,705 | 1.64 | 2.92 | 2.8 |
| 5 | `abides-core/abides_core/kernel.py:275(runner)` | 1 | 1.48 | 49.48 | 2.5 |
| 6 | `queue.py:177(get)` | 882,952 | 1.05 | 3.96 | 1.8 |
| 7 | `abides-markets/abides_markets/price_level.py:265(<genexpr>)` | 10,458,580 | 1.05 | 1.05 | 1.8 |
| 8 | `queue.py:137(put)` | 883,029 | 0.98 | 3.69 | 1.7 |
| 9 | `abides-markets/abides_markets/price_level.py:260(total_quantity)` | 3,245,205 | 0.96 | 3.51 | 1.7 |
| 10 | `abides-markets/abides_markets/agents/exchange_agent.py:302(receive_message)` | 180,220 | 0.92 | 20.65 | 1.6 |
| 11 | `copy.py:232(_keep_alive)` | 948,883 | 0.91 | 1.08 | 1.6 |
| 12 | `abides-markets/abides_markets/orders.py:153(__deepcopy__)` | 572,692 | 0.86 | 1.61 | 1.5 |
| 13 | `~:0(<method 'get' of 'dict' objects>)` | 7,515,327 | 0.85 | 0.85 | 1.5 |
| 14 | `abides-markets/abides_markets/orders.py:129(__str__)` | 438,304 | 0.85 | 4.55 | 1.5 |
| 15 | `~:0(<built-in method numpy.array>)` | 320,978 | 0.82 | 0.82 | 1.4 |

### Top 15 by cumulative time, before (v1.4 engine)

Total profiled time 58.2 s.

| # | function | calls | own s | cum s | own % |
|---|---|---|---|---|---|
| 1 | `abides-core/abides_core/abides.py:15(run)` | 1 | 0.00 | 58.79 | 0.0 |
| 2 | `abides-core/abides_core/kernel.py:194(run)` | 1 | 0.00 | 58.78 | 0.0 |
| 3 | `abides-core/abides_core/kernel.py:275(runner)` | 1 | 1.48 | 49.48 | 2.5 |
| 4 | `abides-markets/abides_markets/agents/exchange_agent.py:302(receive_message)` | 180,220 | 0.92 | 20.65 | 1.6 |
| 5 | `abides-markets/abides_markets/agents/fundamental.py:679(receive_message)` | 159,352 | 0.18 | 13.26 | 0.3 |
| 6 | `abides-markets/abides_markets/order_book.py:33(wrapper)` | 142,181 | 0.13 | 12.63 | 0.2 |
| 7 | `copy.py:119(deepcopy)` | 4,150,445 | 3.57 | 9.15 | 6.1 |
| 8 | `abides-core/abides_core/kernel.py:444(terminate)` | 1 | 0.00 | 9.10 | 0.0 |
| 9 | `abides-markets/abides_markets/agents/exchange_agent.py:248(kernel_terminating)` | 1 | 0.00 | 8.82 | 0.0 |
| 10 | `abides-markets/abides_markets/agents/exchange_agent.py:904(analyse_order_book)` | 1 | 0.00 | 8.71 | 0.0 |
| 11 | `abides-markets/abides_markets/agents/exchange_agent.py:909(get_time_dropout)` | 1 | 0.29 | 8.71 | 0.5 |
| 12 | `abides-markets/abides_markets/order_book.py:127(handle_limit_order)` | 81,547 | 0.49 | 8.68 | 0.8 |
| 13 | `abides-markets/abides_markets/agents/trading_agent.py:274(receive_message)` | 209,192 | 0.48 | 7.79 | 0.8 |
| 14 | `abides-markets/abides_markets/agents/fundamental.py:817(informed_cycle)` | 23,347 | 0.47 | 6.74 | 0.8 |
| 15 | `abides-core/abides_core/agent.py:144(logEvent)` | 745,655 | 0.47 | 6.19 | 0.8 |

### Top 15 by own time, after (A1)

Total profiled time 28.0 s.

| # | function | calls | own s | cum s | own % |
|---|---|---|---|---|---|
| 1 | `~:0(<built-in method builtins.isinstance>)` | 8,374,791 | 1.45 | 2.54 | 5.2 |
| 2 | `abides-core/abides_core/agent.py:25(_event_copy)` | 3,282,029 | 1.36 | 2.55 | 4.9 |
| 3 | `abides-core/abides_core/kernel.py:308(runner)` | 1 | 1.25 | 27.92 | 4.5 |
| 4 | `copy.py:119(deepcopy)` | 824,908 | 1.08 | 3.91 | 3.9 |
| 5 | `abides-markets/abides_markets/agents/exchange_agent.py:312(receive_message)` | 180,220 | 0.77 | 13.31 | 2.8 |
| 6 | `~:0(<built-in method builtins.sum>)` | 880,840 | 0.69 | 1.18 | 2.5 |
| 7 | `abides-markets/abides_markets/orders.py:153(__deepcopy__)` | 491,145 | 0.69 | 1.37 | 2.5 |
| 8 | `~:0(<built-in method _heapq.heappop>)` | 882,952 | 0.69 | 1.11 | 2.5 |
| 9 | `abides-markets/abides_markets/order_book.py:398(enter_order)` | 69,482 | 0.65 | 2.40 | 2.3 |
| 10 | `~:0(<built-in method _abc._abc_instancecheck>)` | 2,877,914 | 0.60 | 0.60 | 2.2 |
| 11 | `~:0(<built-in method _heapq.heappush>)` | 883,029 | 0.59 | 1.05 | 2.1 |
| 12 | `copy.py:232(_keep_alive)` | 567,223 | 0.57 | 0.68 | 2.0 |
| 13 | `abides-markets/abides_markets/price_level.py:200(order_has_better_price)` | 1,066,188 | 0.53 | 0.69 | 1.9 |
| 14 | `abides-markets/abides_markets/orders.py:102(__init__)` | 572,692 | 0.50 | 0.80 | 1.8 |
| 15 | `<frozen abc>:117(__instancecheck__)` | 2,877,914 | 0.48 | 1.09 | 1.7 |

### Top 15 by cumulative time, after (A1)

Total profiled time 28.0 s.

| # | function | calls | own s | cum s | own % |
|---|---|---|---|---|---|
| 1 | `abides-core/abides_core/abides.py:15(run)` | 1 | 0.00 | 28.60 | 0.0 |
| 2 | `abides-core/abides_core/kernel.py:225(run)` | 1 | 0.00 | 28.59 | 0.0 |
| 3 | `abides-core/abides_core/kernel.py:308(runner)` | 1 | 1.25 | 27.92 | 4.5 |
| 4 | `abides-markets/abides_markets/agents/exchange_agent.py:312(receive_message)` | 180,220 | 0.77 | 13.31 | 2.8 |
| 5 | `abides-markets/abides_markets/order_book.py:33(wrapper)` | 142,181 | 0.11 | 7.99 | 0.4 |
| 6 | `abides-markets/abides_markets/agents/fundamental.py:683(receive_message)` | 159,352 | 0.16 | 6.84 | 0.6 |
| 7 | `abides-markets/abides_markets/order_book.py:129(handle_limit_order)` | 81,547 | 0.46 | 5.57 | 1.6 |
| 8 | `abides-markets/abides_markets/agents/fundamental.py:822(informed_cycle)` | 23,347 | 0.43 | 4.14 | 1.5 |
| 9 | `copy.py:119(deepcopy)` | 824,908 | 1.08 | 3.91 | 3.9 |
| 10 | `abides-core/abides_core/agent.py:199(logEvent)` | 745,655 | 0.42 | 3.08 | 1.5 |
| 11 | `abides-markets/abides_markets/agents/trading_agent.py:276(receive_message)` | 209,192 | 0.41 | 2.99 | 1.5 |
| 12 | `abides-core/abides_core/agent.py:25(_event_copy)` | 3,282,029 | 1.36 | 2.55 | 4.9 |
| 13 | `~:0(<built-in method builtins.isinstance>)` | 8,374,791 | 1.45 | 2.54 | 5.2 |
| 14 | `abides-markets/abides_markets/order_book.py:398(enter_order)` | 69,482 | 0.65 | 2.40 | 2.3 |
| 15 | `abides-markets/abides_markets/order_book.py:479(cancel_order)` | 60,634 | 0.47 | 2.31 | 1.7 |

### Wall time per change

| level | change | runs (s) | median s | vs v1.4 | step |
|---|---|---|---|---|---|
| 0 | v1.4 engine (20465e2) | 22.8, 22.7, 22.6 | 22.69 | +0% | +0% |
| 1 | + kernel message heap (no locking) | 28.4, 21.1, 21.1 | 21.15 | -7% | -7% |
| 2 | + logEvent: fast exact copy of plain events | 29.4, 20.6, 20.6 | 20.62 | -9% | -3% |
| 3 | + debug/info logging guarded (no eager formatting) | 17.4, 17.4, 17.3 | 17.37 | -23% | -16% |
| 4 | + fmt_ts without pandas | 16.0, 15.8, 16.1 | 16.04 | -29% | -8% |
| 5 | + get_time_dropout without DataFrame.iterrows | 14.0, 13.8, 13.7 | 13.79 | -39% | -14% |
| 6 | + no agent-side order deepcopy (A1.2a) | 13.9, 13.6, 13.6 | 13.58 | -40% | -2% |
| 7 | + sparse depth rows in the lab (A1.2c, 1 s) | 12.4, 12.1, 12.0 | 12.13 | -47% | -11% |

Distinct (execs, holdings, n_execs) fingerprints over all 24 runs: 1 (all identical)

# Retail trader crowd (RetailCrowdAgent + RetailTraderAgent)

Spec v1.5 A4 (D-R4-3). Code: `abides_markets/agents/retail.py`, messages
`abides_markets/messages/retail.py`, constants `RETAIL` in `configs/param_ranges.py`, tests
`tests/test_retail.py`. Built by `build_config(num_retail=N_r, retail_kappa_v=k,
retail_p_stop=None)`; `num_retail=0` (the default until A9) builds nothing and draws nothing.

## Why: the gaps of the ABIDES NoiseAgents

The 1000 ABIDES NoiseAgents each wake once a day, flip a coin, send one order at the
opposite best price and do nothing else (7.5% of P0 volume). The crowd fixes exactly their
gaps:

| gap | NoiseAgent | retail crowd |
|---|---|---|
| G-a | never reacts to the market | activity rises with recent volatility (V) and news (Nn) |
| G-b | one order a day, fixed rate | about 4 small actions per trader per day at a varying intensity |
| G-c | no position, no stops | each trader holds cash and shares; 40% use stop-losses |
| G-d | no behaviour types | liquidity 50%, trend-chaser 25%, contrarian 25% |
| G-e | stock ABIDES agent | our own agent |

Deliberately simple: no beliefs, no filters, a few rules, one shared scheduler (fast: one
agent wakes every 5 s instead of thousands of agents).

## RetailCrowdAgent (exactly one)

Every dt_c = 5 s (first tick at the open; rescheduled at every tick while the market is open):

1. Spread query, then the mid (if one side is empty, the last two-sided mid; no snapshot before the first two-sided book). The mid goes into a 60-min ring buffer of 5-s mids.
2. Intensity in actions per second:

       lambda(t) = mu · U(t) · min(10, 1 + kappa_v · max(0, V(t) − 1) + kappa_n · Nn(t))

   | term | definition |
   |---|---|
   | mu | 4 actions per trader per day / 23,400 s × N_r |
   | U(t) | the intraday shape of A3.1 (mean 1 over the session) |
   | V | σ_short / σ_ref: each 5-s log return r gives a per-second variance sample r²/5 s; σ_short² = mean of the last 24 samples (2 min); σ_ref² = EWMA of all samples, half-life 60 min (α = 1 − 2^(−5/3600)), started at the first sample. V = 1 during the first 10 min or while σ_ref² = 0 |
   | Nn | Σ \|sentiment\| · 2^(−Δt/600 s) over the headlines received |
   | kappa_n | 2.0, fixed |
   | kappa_v | the sweep dial (1 or 3) |

3. n ~ Poisson(lambda · 5 s). Each action goes to a trader picked uniformly (with replacement) as a `RetailActNowMsg` carrying the snapshot:
   - bid, ask, mid;
   - r_5 = ln(mid / mid 5 min ago);
   - r_30 = ln(mid / mid 30 min ago);
   - s_30 = sqrt(σ_ref² · 1800 s).

   With less history, the returns are taken against the oldest mid kept.
4. **Stop registry:** one stop per trader (the latest one registered). If mid ≤ stop, the crowd sends `RetailStopTriggeredMsg` once and removes the stop. It uses a max-heap with lazy deletion of replaced stops.

## RetailTraderAgent (N_r)

- **Endowment:** $50,000, half in stock at r_bar (25 shares and $25,000). Long-only and cash-only.
- **Construction draws** from its own RandomState, in this order:
  1. type: liquidity if u < 0.5, trend if u < 0.75, else contrarian;
  2. stop user if u < p_stop (0.4);
  3. stop distance d ~ U[0.02, 0.06], drawn for every trader so the order does not depend on p_stop.
- No wakeups of its own after the standard TradingAgent start wake (market hours and close price, needed for the end-of-day mark-to-market). `wakeup` returns None: any other return value is the kernel's gym interruption signal.
- **On ActNow:**
  1. Cancel all its open orders.
  2. Pick a side by type, with z = r_30 / s_30 (0 if s_30 = 0):
     - liquidity: P(buy) = 0.5;
     - trend: P(buy) = 1/(1 + e^(−0.87 z));
     - contrarian: P(buy) = 1/(1 + e^(+0.87 z)).
  3. Size q = max(1, round(LogNormal(ln 30, 0.8))).
  4. Clip q by the cash or shares **not committed to its own orders that can still fill**. Resting orders, and orders whose cancel is in flight, are valued at their limit (worst case).
  5. A buy with no free cash or a sell with no free shares is skipped and logged.
  6. Send a marketable limit order with the 2% broker collar: buy limit = ceil(ask × 1.02), sell limit = floor(bid × 0.98). It fills up to the collar; any remainder rests at the collar until the trader's next action cancels it.
- **Stops:** a stop user registers stop = fill price × (1 − d) after every buy fill (it replaces the previous stop). On StopTriggered it cancels its orders and sells all free shares at floor(bid × 0.98). When a sell leaves it with no shares, it clears its stop (`STOP_CLEARED`), so trigger counts only include traders with something to protect.

## Log events

| event | fields |
|---|---|
| `CROWD_TICK` (crowd) | lam, n, V, Nn, U, mid |
| `RETAIL_ACTION` | kind, side, q, limit, z |
| `RETAIL_SKIP` | reason |
| `STOP_SET` | stop |
| `STOP_TRIGGERED` | stop, q |
| `STOP_CLEARED` | — |

## Determinism and the default market

- New agents come after every existing agent: ids, latency coordinates, and one global draw made after the latency model that seeds a dedicated RandomState for the crowd and the traders.
- With `num_retail = 0` nothing is built and nothing is drawn, so I8 is unchanged.

## Tests

| test | what it checks |
|---|---|
| T-RT1 | intensity formula, cap, V warm-up, news decay (exact on hand series) |
| T-RT2 | P(buy) by type at z = −2, 0, +2 over 20,000 of a trader's own decisions; collar and size; type and stop-user shares |
| T-RT3 | stop registration, a single trigger, full sell, survival across actions |
| T-RT4 | clipping with in-flight orders; no negative cash or shares at any fill of a 1-hour market |
| T-RT5 | a 1-hour crowd market trades every 10 minutes; ≥ 200 retail orders; zero_sum 0; informed and momentum agents keep trading |
| T-RT6 | two runs identical |

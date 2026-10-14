# Architecture

## In one paragraph

A simulation is a list of **agents** that only talk to each other by sending **messages**.
A **kernel** keeps a queue of messages sorted by delivery time and hands them out one by one;
time jumps straight from one event to the next (a *discrete-event* simulation). One special
agent, the **exchange**, holds the **order book**: it receives buy and sell orders, matches
them, and tells both sides when they trade. Every other agent is a trader that wakes up from
time to time, asks the exchange for the current prices, decides, and sends orders. A hidden
**oracle** knows the company's true value; some traders may look at it with noise. After the
run our **export** reads the agents' logs and the exchange's history and writes one JSON
**payload**, which the **web dashboard** draws.

## Data flow

```
 configs/rmsc04_ekf.py: build_config(seed, counts, news, ...)
        │  creates every agent (with its own seeded RNG), the oracle, the latency model
        ▼
 abides_core.Kernel  ── delivers messages in time order (latency + computation delay)
        │
        ├── ExchangeAgent (id 0) ── OrderBook: matching, book_log2 (L1–L10 snapshots), history (LIMIT/EXEC/CANCEL…)
        │        ▲   │
        │ orders │   │ fills, quotes, market hours
        │        │   ▼
        ├── traders: Noise, Value, MarketMaker, ABIDES Momentum, our Fundamentalist, our MomentumEKF
        │        │   each keeps agent.log: (time, event type, dict)
        │        └── oracle.observe_price(...)   (value agents, fundamentalist init, exchange)
        │
        └── NewsOracleAgent ── broadcasts NewsSentimentMsg (headline, sentiment) at set times
        ▼
 end_state["agents"]  (all agent objects, their logs, the exchange's books)
        ▼
 api/export.py: build_payload() ── quotes, candles, oracle path, depth, per-agent series,
        │                         news reactions, population, market stats (api/stats.py);
        │                         downsampled (LTTB) and validated against api/schema.py
        ▼
 runs/<run_id>.json  (cached by params + engine version, api/jobs.py)
        ▼
 api/server.py (FastAPI) ──► web/ (React + ECharts): four tabs
```

Entry points: `api/jobs.py:build_run_config` (the single place the dashboard and tests turn
`RunParams` into a config) and `api/jobs.py:execute`.

**"News oracle" ≠ "value oracle".** `NewsOracleAgent` is an *agent* that broadcasts
headlines with a sentiment score; it knows nothing about value. The *oracle*
(`kernel.oracle`) is not an agent; it is the source of the true value
([ORACLE.md](ORACLE.md)). In v1.2 news changes beliefs only, never the true value
([KNOWN_ISSUES.md](KNOWN_ISSUES.md), K6).

## The agent population

**Since v1.4 (N6) the default market is P0**, the RunParams / dashboard / CLI defaults
(spec v1.4 §6.1, v1.4.2 D-R3-7):
- 0 ValueAgents;
- 60 informed fundamentalists of design D-60fl2M: research every log-U[60, 300] s, noise
  log-U[10, 50]¢, $2M each, learning from prices off;
- 12 momentum EKF, 1000 noise agents, 2 market makers;
- a gross budget L = 2 on the Noise/Value/ABIDES-Momentum agents.

The **legacy (v1.3) market** stays reproducible by explicit parameters: `num_value=97,
num_fund=20, fund_mode="price_only"`, which switches the budget off by default (`budget=None`
means auto: on for informed). It is bit-identical to v1.2/v1.3 (I8-legacy). `build_config`'s
own keyword defaults stay the low-level, legacy-compatible API; the default market is defined
by RunParams and `api.jobs.run_config_kwargs`.

| v1.4 default (P0) | count | starting position |
|---|---|---|
| NoiseAgent | 1000 † | $100,000 cash (gross budget 2×) |
| ValueAgent | 0 † (0–150) | — |
| FundamentalistAgent, informed | 60 † (0–200) | $2,000,000 = $1,000,000 cash + 1,000 shares |
| AdaptiveMarketMakerAgent | 2 † | $100,000 cash (no budget in R3) |
| MomentumEKFAgent | 12 † | $50,000 + 50 shares |

The table below lists every agent class, with `rmsc04_ekf.build_config`'s own defaults (the
legacy market). The dashboard sidebar changes the counts marked †. Agent ids are assigned in
this order.

| Group | Count | Starting position | Wakes | Information | Role |
|---|---|---|---|---|---|
| ExchangeAgent | 1 | – | on messages | everything in the book | matching engine |
| NoiseAgent | 1000 † (0–2000) | $100,000 cash | **once per day**, at a time drawn from a U-quadratic distribution over 09:00–16:00 (more mass near both ends) | best bid/ask only | random-direction liquidity taker |
| ValueAgent | 97 † (0–150) | $100,000 cash | Poisson, mean ≈175 s (`lambda_a = 5.7e-12`/ns) | **noisy true value** (variance 1000 cents², sd ≈ 32¢) + best bid/ask | informed trader; pulls price to value |
| FundamentalistAgent (ours) | 0–200 † | price-only: $50,000 + 50 shares; informed (v1.4): design wealth, half in shares | price-only: every 10 s; informed: Poisson, mean 30–120 s | price-only: market mid (one oracle look at start-up); informed: + research readings every Exp(T_r) | Kalman value investor; informed mode quotes around its belief (AGENT_FUNDAMENTALIST.md) |
| AdaptiveMarketMakerAgent | 2 † (0–2) | $100,000 cash | Poisson, mean 60 s | best bid/ask, recent volume | quotes ladders on both sides |
| MomentumAgent (ABIDES MA) | 12 − our momentum count | $100,000 cash | Poisson, mean 37 s | mid history | 20/50 moving-average crossover |
| MomentumEKFAgent (ours) | 0–12 † | $50,000 + 50 shares | Poisson, mean `wake_mean` ∈ [10, 60] s | market mid only | Kalman trend follower |
| NewsOracleAgent | 1 | – | at scheduled news times | the headlines | broadcasts news |
| ImpactProbeAgent (v1.3, lab only) | 0 or 1 | $10¹⁰ cash (buy) or Q shares (sell) | at its child times only | best bid/ask at its first child | a **test instrument**: executes one parent order of Q shares as 30 market orders over 5 minutes (spec v1.3 §6.2). Built only when `build_config(probe=…)` is given; never in the dashboard |

Details of the stock agents are in [AGENTS_ABIDES.md](AGENTS_ABIDES.md), and of ours in
[AGENT_FUNDAMENTALIST.md](AGENT_FUNDAMENTALIST.md) and [AGENT_MOMENTUM.md](AGENT_MOMENTUM.md).
"Starting position" for our agents: `starting_cash` stays $100,000 (total wealth) and
`floor(0.5 · 100,000 / 1000) = 50` shares are bought at the reference price r̄ = $1000
before the open, so P&L is measured against total starting wealth.

## Units and session

| Quantity | Unit inside the engine | Notes |
|---|---|---|
| prices, cash | integer cents | $1000.00 = 100,000. Mid can be a half-cent ((bid+ask)/2). |
| variances (P, R, Q, sigma_n) | cents² | `oracle.observe_price(sigma_n=…)` takes a **variance**, not a standard deviation. |
| time | integer nanoseconds | `str_to_ns("10S")` = 10,000,000,000. |
| rates (`lambda_a`, `kappa`, `megashock_lambda_a`) | per nanosecond | e.g. `lambda_a = 5.7e-12`/ns ⇒ mean gap 1/λ = 175 s. |
| momentum filter | log-price, seconds | z = ln(mid in cents); v̂ in log-return per second. |

Session: the market opens at 09:30 and closes at `end_time` (10:00–16:00). Noise agents may
wake from 09:00. The kernel stops 1 s after the close. The date (2021-02-05) is a label only.

## Where randomness comes from

A run is meant to be a pure function of its parameters. All randomness is seeded from the
single `seed` in `build_config`:

| RNG | Created where | Seeded from | Used for |
|---|---|---|---|
| global `np.random` | `build_config`: `np.random.seed(seed)` | `seed` | **config time only**: every agent's seed below, hyperparameter draws (`param_ranges.draw`), noise-agent wake times (`get_wake_time`) |
| oracle `random_state` (per symbol) | `build_config` | `np.random.randint(0, 2³¹)` | the true-value path. v1.2: the whole path is drawn at construction from this RNG only ([ORACLE.md](ORACLE.md)) |
| each agent's `random_state` | `build_config` | `np.random.randint(0, 2³¹)`, in agent order | everything the agent randomises: wake gaps, order sizes and sides, noisy oracle looks |
| informed fundamentalists (v1.4) | — | — | `fund_mode="informed"` draws 8 more global values per fundamentalist (INFORMED_RANGES + the design's T_r, σ_r) right after its FUNDAMENTAL_RANGES draws and before its RandomState seed, so the agents built after the fundamentalists get different seeds than in a price_only market (agents before them are unchanged). At run time the informed agent's wake gaps, research clock and research readings all come from its own RandomState; the oracle path is unaffected (T-N7). price_only draws nothing new (I8) |
| latency model RNG | `generate_latency_model` | `np.random.randint(0, 2³¹)` | pairwise message latencies (fixed at config time) |
| kernel `random_state` | `build_config` | `np.random.randint(0, 2³¹)` | kernel-level randomness |
| impact probe `random_state` (v1.3, lab only) | `build_config(probe=…)` | the **constant** `RandomState(0)`, not drawn from the global stream | nothing (the probe uses no random numbers). The probe is appended as the last agent, after the news oracle and before the kernel RNG and the latency model are drawn; the latency model draws one more coordinate after the existing agents', so every existing agent's latencies, seeds and parameters are unchanged (tests T-L6, T-L7) |

Consequences:

- Changing the number of agents of one type changes every seed drawn **after** it, so
  "same seed, one more noise agent" is a different market. v1.2's oracle is drawn **before**
  any agent, so the true-value path is the same whatever the agent counts (tested, I2).
- Before v1.2 the oracle generated values lazily, one random draw per query, and drew
  megashock times from the global `np.random` during the run. The true value therefore
  depended on how often agents looked at it ([DECISIONS.md](DECISIONS.md), 2026-10-09).
- Determinism across processes is tested by invariant I1 ([TESTING.md](TESTING.md)).

## The realism lab (v1.3)

```
 api/lab.py: CONFIGS (run matrix), lab_config(id, seed)
        │  = build_config(**run_config_kwargs(RunParams), oracle_events / probe /
        │                  mm_pause_windows / mom_capital_mult)
        ▼
 scripts/realism_lab.py ── one spawned process per run ── abides.run
        │      api/realism.py: series_from_end_state → run_metrics, agent_sanity
        ▼
 runs/_lab/<config>/<seed>/metrics.json + series.npz   (git-ignored)
        ▼
 report step: realism.scorecard (bands, grades), scenario analysis (treated − baseline
        │      on the same seed), impact summary, figures
        ▼
 docs/v1.3/lab/summary.json, figures/, BASELINE.md   ──► GET /api/lab/summary ──► Realism tab
```

The same `api/realism.py` computes the single-run realism block of every dashboard payload.
See [REALISM_LAB.md](REALISM_LAB.md).

## Code map

| Path | Contents |
|---|---|
| `abides-core/abides_core/` | kernel, base `Agent`, message plumbing, time utilities |
| `abides-markets/abides_markets/agents/` | exchange and trader agents; ours are `fundamental.py`, `momentum_ekf.py`, `news_oracle_agent.py`, and the lab's `impact_probe_agent.py` |
| `abides-markets/abides_markets/order_book.py` | matching, `history`, `book_log2` |
| `abides-markets/abides_markets/oracles/` | true-value sources |
| `abides-markets/abides_markets/configs/rmsc04_ekf.py` | the market we run (`build_config`) |
| `abides-markets/abides_markets/configs/param_ranges.py` | ranges of every randomised hyperparameter (single source of truth, also sent to the dashboard) |
| `api/` | `jobs.py` (run + cache), `export.py` (payload), `stats.py` (market statistics), `realism.py` (realism metrics, bands, scenario analysis), `lab.py` (lab run matrix), `schema.py` (payload contract), `server.py` (HTTP) |
| `web/src/` | dashboard: `tabs/`, `components/`, `charts/`, `types/payload.ts` (TypeScript mirror of `api/schema.py`) |
| `abides-markets/tests/`, `api/tests/` | unit and invariant tests |
| `scripts/` | `dev.sh`, acceptance scripts, `realism_lab.py` (the lab runner) |

## Performance (v1.4.2)

`OrderBook.get_imbalance`, which serves both market makers' BookImbalance subscriptions on every
book event, used to sum the visible quantity of every resting order. That was about 40% of the
profile once informed agents spread quotes over many levels. Since v1.4.2 the order book keeps
running visible totals per side. They are updated at every insert, fill, cancel, partial cancel,
modify and replace, and checked against a full recomputation when `OrderBook.DEBUG_TOTALS` is
set (tests only).

Results are bit-identical: I8 holds, and so does the full-day D-60fl2M-S2 seed-42 hash in
`docs/v1.4/lab/reference_hashes.json`. One full D-60fl2M day (seed 42, 1 worker, i7-13620H)
took 63.6 / 62.7 s before and 48.9 / 48.0 s after (about −23%). Remaining costs are spread
out: order deepcopies (about 15%) and debug-log timestamp formatting (about 8%).


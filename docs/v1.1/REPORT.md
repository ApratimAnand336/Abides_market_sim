# FinVerse spec v1.1 — implementation report

Branch `v1.1` (from `origin/dashboard` aa38353), one commit per milestone, not pushed.
Date: 2026-10-08.

| Milestone | Commit | Scope |
|---|---|---|
| V1 | e40df56 | Fundamentalist F1–F6 + tests T-F1..T-F7 |
| V2 | 2ddee51 | Momentum EKF M1–M7 + tests T-M1..T-M5 |
| V3 | 2caaed7 | Payload 1.1, export changes 4.1–4.2, D2 "vs holding" |
| V4 | e2a6e02 | D1 off-scale overlays, D3 overlay agent selection |
| V5 | 49c46bc | D4 market population, D5 price vs true value |
| V6 | (this commit) | Acceptance script, this report, screenshots |

## Tests

`pytest api/tests abides-markets/tests`: **147 passed**. Two pre-existing failures are unrelated to v1.1
and fail identically on `origin/dashboard`:
`test_gym_runner.py` (the `gym` package is not installed) and `test_ou_process.py` (pandas/datetime
incompatibility in untouched ABIDES code). `npm run build` (tsc + vite) passes.

## What changed

**V1 — `agents/fundamental.py`, `configs/param_ranges.py`, `configs/rmsc04_ekf.py`**
- F1: the step-9 nudge block is deleted; `x_hat` changes only in `correction()` and `apply_news()`.
- F2: `delta` (0.0005, 0.003), `lambda_er` (0.5, 2.0); defaults 0.0015 / 1.0.
- F3: `prediction(dt)` returns `(x, P + Q, Q)` with `Q = q·sigma_f2_hat·dt`; `update_sigma_f2()` is an EWMA
  (α = 1/60) of squared 300 s mid changes found with `bisect`, floored at 0.1. EKF_UPDATE logs Q, dt, sigma_f2.
- F4: `target_position()` (z, w*, step cap, dead band) replaces `decision_volume`; the side comes from d;
  `decision_limit_price(..., is_buy)` drops its min-gap check; `beta` is removed; FUND_DECISION is logged each wake.
- F5: `apply_news()` adds `sentiment·k_news·sqrt(sigma_f2_hat·1800)` to x̂ and shift² to P; new NEWS_RECEIVED keys;
  `news_sensitivity` is removed. The forced trading cycle after news is kept.
- F6: config draws q, a_max, z0, s_max, b_f, k_news.

**V2 — `agents/momentum_ekf.py`**
- M1 ranges; M2 `detrended_var()` used by `warmup_fit` and `realised_var`; M3 `tau_ratio` (config draws
  `wake_mean` first, `tau = tau_ratio·wake_mean`, agent stores `tau_ratio`); M4 ratchets follow down first;
  M5 re-entry needs `T ≥ theta_out` (bear mirror); M6 `exit_pending`; M7 log keys and `.gitignore` (`log/`, `*.pkl`).
- Two v1.0 tests asserted the old ratchet/re-entry behaviour and were updated to the intended M4/M5 behaviour.

**V3 — `api/`, `web/`**: `SCHEMA_VERSION = ENGINE_VERSION = "1.1"`; `engine_version()` is now
`v1.1-<git hash>[+dirty]`, so old cached runs are never reused. Fundamental news, EKF Q/sigma_f2 and
hyperparameter lists are exported as specified. `final.pnl_vs_hold(_pct)`; a Leaderboard "vs holding" column
with a header tooltip; a KPI on both agent detail views (fundamentals got a KPI row, which they did not have).

**V4 — `charts/series.ts`**: `clipToDomain()` / `offScaleMarkerSeries()` / `markersNear()`, used by MarketOverview
and FundamentalDetail. "Overlay agents" chips on MarketOverview.

**V5**: `RunParams.num_value / num_noise / num_mm` (bounds and defaults as specified; `build_config(num_mm=…)`);
`export.population()`; `stats.gap_series()` / `gap_half_life()`; payload `population`, `stats.gap`, `market.gap`;
"Market population" and "Price vs true value" cards at the top of Market Health; a collapsed sidebar section.

## Acceptance (6.3) — seed 42, 09:30–16:00, 20 fundamentalists, 12 momentum EKF

Reproduce with `python scripts/acceptance_v1_1.py` (about 25 s per run); it writes
`runs/_acceptance/summary_42_160000.json`. **Every target passes in both runs.** No parameter was tuned to get there.

| Target | Run A (no news) | Run B (news +0.9 at 00:10) |
|---|---|---|
| median of per-agent median \|x̂ − mid\| < $1.00 | **$0.135** | **$0.127** |
| max \|x̂ − mid\| (excl. 5 min after news) < $5 | **$1.02** | **$0.80** |
| median K over last hour > 0.003 | **0.025** | **0.031** |
| agents ending at 0 shares ≤ 2/20 | **0** | **0** |
| agents ending > 95% stock ≤ 2/20 | **0** | **0** |
| median news shift in [$0.30, $4] | – | **$1.08** (min 0.28, max 1.55) |
| momentum agents reaching \|T\| ≥ θ_in ≥ 6/12 | **12** | **12** |
| re-entries reversed within 3 looks ≤ 25% | **11/53 = 21%** | **10/54 = 19%** |
| median g in BULL/BEAR ≥ 0.7 | **0.91** | **0.98** |

Fundamentalist detail (A / B): K at the close has median 0.030 / 0.022 (range 0.005–0.10); √P at the close is about $0.31–0.33;
`sigma_f2_hat` ends at 2.5 / 1.8 cents²/s (prior 3.0); x̂ spans $996.54–$1000.09 in A, tracking the
market with no drift (v1.0: down to about $949). Endowment: final holdings are 33–52 shares (33–52% stock), so no agent dumped
its endowment.
Momentum (A / B): 159 / 172 entries (106 / 118 breakouts, 53 / 54 re-entries), 1 / 0 STOP exits (the rest are FADE),
1283 / 1262 orders.

Market sanity (no target): corr(mid, oracle) 0.985 / 0.966; gap std $0.155 / $0.162; mean |gap| $0.13;
gap half-life 1.6 / 1.9 min.

Same seed and same run B parameters on v1.0 (`origin/dashboard`) and with no EKF agents, for comparison:

| | lag-1 ACF of 1-min returns | corr(mid, oracle) | tracking RMS |
|---|---|---|---|
| no EKF agents | 0.406 | 0.930 | $0.39 |
| v1.0, 20+12 | 0.456 | 0.933 | $0.19 |
| v1.1, 20+12 | 0.405 | 0.966 | $0.17 |

## Dashboard screenshots (run B, `screenshots/`)

`1_market_overview` (x̂ overlays for the default selection, chips), `2_agent_performance` (leaderboard with
"vs holding", KPI rows, new personality cards), `3_news_sentiment`, `4_market_health` (population card and
price vs true value), `5_sidebar_population`, `6_overlay_selection` (one momentum chip switched on).

**D1 needs a synthetic check:** with the v1.1 fixes, no x̂ or l̂ point in run B leaves the price range, so
clipping never triggers on real data. `D1_synthetic_*.png` use run B with one agent's x̂ shifted by
+$3 (10:30–10:50) and −$3 (12:00–12:20), injected **in the browser only** (Playwright request interception).
Nothing was written to the cached run. The line breaks with no vertical streaks, and each run gets one edge triangle.

## Deviations from the spec, with reasons

1. **T-F4 is checked on 50 paths, not one.** The F3 estimator (300 s lag, 60-update EWMA at 10 s) averages only
   about 2–4 independent 5-minute changes. On a single 1-hour path it lands within ±30% of the truth only about 40% of
   the time (5th–95th percentile 2.0–10.3 for a true 5). It is unbiased (mean 5.27 over 200 paths). The test checks
   the mean and median over 50 paths within ±30%, plus a loose per-path bound. The estimator was not changed.
2. **T-A3 uses a 10-day AR(1) sample.** On one 6.5 h day the half-life estimate for a true 10 min ranges from
   4.8 to 15.8 min across seeds (only about 13 independent mispricings per day), so ±20% on one day is luck.
   On 10 days every seed lands within ±20%. A one-day sanity bound is also tested, and the dashboard tooltip warns about this spread.
3. **`orders_sent` (D4)** counts distinct order ids from LIMIT entries **plus the aggressor order of EXEC
   entries**. An order that fills completely on arrival never gets a LIMIT entry, so a LIMIT-only count
   would undercount aggressive traders.
4. **MM wake description** comes from the agent: "Poisson, mean 60 s" (the config sets `poisson_arrival=True`),
   not the spec's "every 60 s".
5. **Population values use cash + shares × closing mid** (as specified). Per-agent `final.value` remains ABIDES's
   mark-to-market at the last trade price, so the two can differ by cents per agent.
6. **Old cached runs are hidden** from the run list (their schema 1.0 payloads lack v1.1 fields). Opening one by URL
   shows a notice instead of crashing. The files are kept.
7. The momentum hyperparameter card shows both `tau_ratio` (with its range) and the realised `tau` (no range).

## Open questions

1. **The seed-42 reference numbers no longer match.** The spec's "std $0.37, half-life about 7.5 min" caption differs from this run's
   $0.16 / 1.9 min (runs A/B with 20+12 agents). With no EKF agents the tracking RMS is $0.39, close to the reference,
   so the 20 fundamentalists now help pin the price to value. Should the caption's reference be updated or tied to a stated configuration?
2. **Fundamentalist order count.** The dead band (1–3% of W, i.e. 1–3 shares) lets each fundamentalist place
   about 940–990 small orders a day (median; range 390–1670 of about 2340 wakes). That is about 3.9% of volume. It is not churn of the
   endowment (holdings stay at 33–52 shares), but the order traffic is heavy. Would you like a larger `b_f` or a minimum hold time?
3. **All 20 fundamentalists finish slightly behind "holding"** ($35–$76 on $100k in run B), while most momentum agents
   finish ahead. That is plausible for small mean-reversion trades that pay the spread, but it is worth watching once
   value agents are replaced (Part 5).
4. **STOP exits almost never fire** (1 in run A, 0 in run B); exits come from FADE (T < θ_out). With k_stop in [2, 4]
   and σ_τ from the detrended variance, the trailing stop is wide. Is that intended?
5. **The 1-minute return autocorrelation (lag 1 ≈ 0.4)** is a property of the base ABIDES market (same with no EKF agents),
   so the "No linear return autocorrelation" stylised fact shows WARN regardless of v1.1.
6. Payload size for a full day with 20+12 agents is 8.98 MB (the new fundamental EKF columns, the momentum decision
   fields and the gap series). That is above the 8 MB full-day budget, which `test_size_within_budget` scales for its 3+3-agent test run.

# Testing

Three layers, from fast to slow:

1. **Unit tests**: the maths of each agent and helper, with no simulation kernel (seconds).
2. **Invariant tests**: short real simulations that check properties which must *always* hold: determinism, conservation of cash and shares, book sanity, liveness (added in v1.2, milestone W4).
3. **Acceptance runs**: full trading days with the release's targets, reported in `docs/v<version>/REPORT.md` (about 25 s per simulated day).

## How to run

```bash
# everything except the gym runner (needs the optional `gym` package)
python -m pytest abides-markets/tests api/tests -q --ignore=abides-markets/tests/test_gym_runner.py

# one area
python -m pytest abides-markets/tests/test_fundamental.py -q
python -m pytest api/tests -q

# acceptance (v1.2 targets): one full-day simulation per call (~25 s), then the table
python scripts/acceptance_v1_2.py --run A        # also B, C, Z
python scripts/acceptance_v1_2.py --report
python scripts/acceptance_v1_1.py --end 11:00:00 --runs A   # v1.1 script, quick smoke run
```

`api/tests/test_export.py` builds one real 30-minute simulation (seed 42, 3 + 3 of our
agents, three news items) once per session and checks the payload against it.

## What is covered

| File | Tests | Covers |
|---|---|---|
| `abides-markets/tests/test_fundamental.py` | 16 | FundamentalistAgent: no nudge (T-F1), gain does not decay (T-F2), step tracking (T-F3), value-speed estimate (T-F4), target-position sizing and dead band (T-F5), side from d (T-F6), news shift (T-F7), log keys, long-only orders; v1.2 edge z = gap/√(P+R) (T-F8), a typical 13¢ gap holds (T-F9), a $6 gap buys within the step cap (T-F10) |
| `abides-markets/tests/test_momentum_ekf.py` | 43 | MomentumEKFAgent: trend detection, noise rejection, numerical stability, news priming, state machine, ratchet, sizing, endowment; v1.1 T-M1 … T-M5 (ramp bias, detrended variance, ratchet follows down, re-entry, persistent stop) |
| `abides-markets/tests/test_oracle.py` | 7 | PregeneratedOracle: the same seed gives the same path in three different markets (T-O1, also invariant I2; three 1-hour simulations), increment std matches OU theory over 200 seeds (T-O2), exact observations are the step function with clamped ends (T-O3), the noise comes from the caller's RNG (T-O4), the path ignores the global RNG, megashocks, unknown sources |
| `abides-markets/tests/test_market_maker.py` | 4 | Market maker cold start and liveness: without value agents the market trades and each MM quotes in every 10-minute window (T-M6, invariant I6); each MM wakes ≥ 90% of duration/mean wake and is never silent for 10 minutes, with and without value agents (T-M7, invariant I7); the spread cap does not bind in the default market. Two 1-hour simulations, ≈8 s |
| `abides-markets/tests/test_scenarios.py` | 11 | Realism-lab tooling (spec v1.3 T-L*): the scenario path source without events equals `synthetic_ou` bit for bit on 20 seeds (T-L1); a jump adds J·a^(k−k0) from its grid point and is recorded (T-L2); a ×3 volatility window triples the 1 s increments over 200 seeds and leaves the earlier path unchanged (T-L3); a jump config keeps every agent's parameters and RNG, and `oracle_events=None` keeps the I8 hash (T-L4); a 600-share probe sends exactly 30 children 10 s apart, fills + unfilled = 600, conservation, book sanity and zero_sum hold (T-L5); a null probe keeps the I8 hash (T-L6); the probe uses no global RNG and changes nothing before its start (T-L7); a 10:00–10:15 market-maker pause places no MM order and leaves none resting in the window, logs one MM_PAUSED and one MM_RESUMED per MM and changes nothing before 10:00 (T-L8); ×3 momentum capital gives 3× wealth and 150 shares and changes no other agent (T-L9); every v1.3 switch passed explicitly at its default keeps the I8 hash. About 1 minute |
| `abides-markets/tests/test_invariants.py` | 10 | Invariants I1–I9 (below; I4 has two parts since v1.4) |
| `abides-markets/tests/test_fundamental_informed.py` | 25 | Spec v1.4 T-N1 (research update exact to 1e-9; the reading uses variance σ_r² and is logged), T-N2 (50 agents, T_r = 120 s, 2 h of 10 s wakes: 58.6 readings per agent vs 60 ± 10%, never two per wake), T-N3 (prices identical for two different books), T-N4 (an empty first wake posts a two-sided quote; a 1-hour market with 0 value agents, 0 MMs, 5 informed + 100 noise trades: 261 executions), T-N5 (1,590 informed fills in a 1-hour market with 20 informed agents, all within [−0.5, 1.5]·W at the fill price ± 1 share), T-N6 (price_only with every new argument explicit keeps I8), T-N7 (oracle path identical with informed agents; two processes give identical runs). Spec v1.4.1: T-N16 ("off" = absent key: identical agents and fingerprint), T-N17 (learning maths exact to 1e-9 against a reference over a hand-built sequence; 1 ≤ g ≤ ρ, ρ_eff ≥ 1), T-N18 (mod adopts ≥ 50% by look 3 and ≥ 90% by look 4, a two-look blip moves < 20¢; strong ≥ 70% by look 2; N(0, 40¢) noise never triggers, for ρ ∈ {3, 100} and both ends of ε_thr; a 1-hour market with mod learning logs the new keys). About 45 s |
| `abides-markets/tests/test_orderbook_totals.py` | 4 | Spec v1.4.2 T-S1: OrderBook running visible totals equal a full recomputation after every book event (hand-built book with hidden orders, partial cancel, modify up/down, replace, fills; 1-hour default and D-60fl2M markets with `OrderBook.DEBUG_TOTALS` on; every upstream `orderbook/` test also runs with the check on via `orderbook/conftest.py`). T-S2: the full-day seed-42 D-60fl2M-S2 fingerprint equals the pre-change reference (`docs/v1.4/lab/reference_hashes.json`). About 75 s |
| `abides-markets/tests/test_budget.py` | 7 | Spec v1.4 T-N12 (GrossLimit maths: a 1000-share buy at $1000 with $100,000 is clipped to 200; shorts beyond −2W clipped; W ≤ 0 only reduces; exhaustive check of the inequality) and T-N13 (`abides_budget=None` keeps the I8 hash; with L = 2 every Noise/Value/ABIDES-Momentum fill in a 1-hour market keeps |n|·p ≤ 2·W_p within one order; market makers and our agents are not budgeted; BUDGET_BLOCK logged and counted). About 1 minute |
| `api/tests/test_export.py` | 22 | payload validity (schema, no NaN), trade counts, close, mark-to-market, equal-length series, size budget, news records, candles, P&L vs holding, population (volume shares sum to 100), gap half-life on a synthetic AR(1); v1.3: the payload's realism block equals the lab's computation, carries every band and grades G1, G3–G11, and is < 50 KB |
| `api/tests/test_realism.py` | 117 | Realism metrics on synthetic inputs (spec v1.3 T-R1 … T-R12): σ_1m, ac1, VR(5), clustering, kurtosis, vv_corr, regime-contrast floor, gap half-life (45 and 90 min are strict xfails: the estimator's bias, see [REALISM_LAB.md](REALISM_LAB.md)), jump analysis, impact β and noise floor, every band boundary, aggregation, zero_sum. Spec v1.4 T-N8 … T-N11: corrected half-life within ±25% at 1.5/10/45/90 min; the correction table rebuilds identically and is monotone; h_range brackets the reading (its ≥ 80% coverage is a strict xfail, DECISIONS.md N1); jump-window metrics on a hand-built series; every R3 scorecard boundary. Spec v1.4.1 T-N14 (spread_bps, spread_jump_ratio and informed_share_updated on hand-built series; L1/T6/L6 definitions and boundaries exactly as written) and T-N15 (vol ratio by horizon: price = value + noise is > 1 at 1 min and near 1 at 60 min; a 10-min moving average is < 1 at 1 min and rises with the horizon); G8 boundaries in bps. No simulation; about 5 s |
| `api/tests/test_server.py` | 20 | HTTP validation (readable 400s, including population bounds), presets, 404s, run listing; v1.3: `/api/lab/summary` served when present, 404 when absent |
| `abides-markets/tests/orderbook/*`, `test_orders.py`, `test_generators.py`, `test_sim.py`, `agent_utils_test.py` | 48 | upstream ABIDES order book and utilities |

## Latest results

| Date | Branch / commit | Result |
|---|---|---|
| 2026-10-09 | `v1.2` at 3c0b859 (v1.1 code) | 147 passed, 1 failed (`test_ou_process`, pre-existing, see below) |
| 2026-10-09 | `v1.2` W4 | 169 passed, 1 failed (`test_ou_process`, pre-existing); invariants 7/7 in 32 s |
| 2026-10-09 | `v1.2` W6 | 169 passed, 1 failed (`test_ou_process`, pre-existing); acceptance A, B, C, Z: all targets met (`docs/v1.2/REPORT.md`) |
| 2026-10-12 | `v1.3` L7 | 261 passed, 1 skipped (the slow regression wrapper), 2 xfailed (T-R8 45/90 min, strict), 1 failed (`test_ou_process`, pre-existing) in 85 s; invariants I1–I8 pass; lab regression set PASSED (1.4 min); `npm run build` passes |
| 2026-10-12 | `v1.4` N1 | api/tests: 150 passed, 1 skipped, 3 xfailed (T-R8 45/90, T-N9 coverage; strict) in 8 s |
| 2026-10-12 | `v1.4` N2 | 300 passed, 1 skipped, 3 xfailed (T-R8 45/90, T-N9 coverage; strict), 1 failed (`test_ou_process`, pre-existing) in 125 s; invariants I1–I9 pass (I8 unchanged) |
| 2026-10-12 | `v1.4` N3 | 311 passed, 1 skipped, 3 xfailed (strict), 1 failed (`test_ou_process`, pre-existing) in 143 s; invariants 10 passed (I8 unchanged) |
| 2026-10-13 | `v1.4` N4a | api/tests 157 passed, 1 skipped, 3 xfailed (strict); `npm run build` passes |
| 2026-10-13 | `v1.4` N4b | 332 passed, 1 skipped, 3 xfailed (strict), 1 failed (`test_ou_process`, pre-existing) in 153 s; invariants I1–I9 pass, I8 unchanged (T-N19) |
| 2026-10-13 | `v1.4` N4d | 336 passed, 1 skipped, 3 xfailed (strict), 1 failed (`test_ou_process`, pre-existing) in 277 s; I8 unchanged; T-S2 bit-identical |
| 2026-10-14 | `v1.4` N6 | 338 passed, 1 skipped, 3 xfailed (strict), 1 failed (`test_ou_process`, pre-existing) in 185 s; I8 re-recorded, I8-legacy passes; regression (v1.4, 41 checks) and regression-legacy (42 checks) PASSED; `npm run build` passes |
| 2026-10-16 | `v1.5` A1 | 338 passed, 1 skipped, 3 xfailed (strict), 1 failed (`test_ou_process`, pre-existing) in 147 s, plus 13 errors in `test_export.py` caused by the uncommitted A2 work in `api/realism.py` (nested metrics vs the payload schema; fixed in A2); on the A1 state alone `test_export.py` 23 passed; invariants 11 passed (I8, I8-legacy unchanged); T-S4 bit-identical, T-S5 lab metrics identical; regression (41 checks) and regression-legacy (42) PASSED |
| 2026-10-16 | `v1.5` A2 | api/tests realism + export + v1.5 metrics: 143 passed, 3 xfailed (strict) in 6 s; regression PASSED (41 checks) |
| 2026-10-16 | `v1.5` A3 | 368 passed, 1 skipped, 4 xfailed (strict; new: T-O5 normal-day daily sd, spec number), 1 failed (`test_ou_process`, pre-existing) in 149 s; invariants 11 passed (I8 unchanged) |
| 2026-10-16 | `v1.5` A4 | test_retail.py 15 passed (T-RT1..T-RT6); invariants 11 passed (I8 unchanged); full suite at A5 |
| 2026-10-16 | `v1.5` A5 | 392 passed, 1 skipped, 4 xfailed (strict), 1 failed (`test_ou_process`, pre-existing) in 191 s; test_liquidity_provider.py 9 passed (T-LP1..T-LP6); invariants 11 passed (I8 unchanged); campaign a-lp 40/40 runs, zero_sum 0 |

### Pre-existing failures (not caused by our code)

- `test_gym_runner.py`: needs the `gym` package, which is not installed. Excluded with `--ignore`.
- `test_ou_process.py::test_ou_process`: a pandas/`datetime` incompatibility inside the upstream
  `MeanRevertingOracle` (not used by our market). It fails identically on `origin/dashboard`.

## Realism-lab regression set (v1.3)

```bash
python scripts/realism_lab.py --campaign regression   # ~1.5 min with 4 workers
python -m pytest api/tests -m slow                    # the same, as a test
```

9 full days (C-DEF, S2, IMP-1 × seeds 42, 7, 1): the seed-42 C-DEF hash must equal reference run A,
and every graded metric's 3-seed median must lie inside the stored 20-seed [p10, p90]. See
[REALISM_LAB.md](REALISM_LAB.md). Run times (2026-10-12, development laptop): one full day ≈ 25 s
and ≈ 470 MB; Campaign c1 (80 runs) 9 min with 4 workers; all 360 runs ≈ 45 min of wall time.

## Invariants

`abides-markets/tests/test_invariants.py` (spec v1.2 Part 5). Each runs a short real
simulation through `api.jobs.build_run_config` (the dashboard path): seed 42, 09:30–10:30,
5 fundamentalists, 4 momentum agents, the default background population. Run alone:

```bash
python -m pytest abides-markets/tests/test_invariants.py -q
```

| # | Invariant | What it guarantees | How | Time* |
|---|---|---|---|---|
| I1 | Determinism | The same parameters give the same market, in any process | two fresh subprocesses, **with different `PYTHONHASHSEED`s** (so string set/dict ordering cannot hide); sha256 of every EXEC (time, price, quantity, agent_id, oppos_agent_id) and of every agent's final holdings must match | 9 s |
| I2 | Oracle stability | The true value does not depend on the market | T-O1: default, + one news item, and 20 value agents with 0 fundamentalists give bit-identical paths | 12 s |
| I3 | Conservation | Trading moves cash and shares between agents but never creates or destroys them | holdings snapshot from `config["agents"]` before `abides.run`; totals of CASH and of shares after the run equal, tolerance **0 cents** | 4 s |
| I4 | Long-only safety (split in v1.4) | Price-only fundamentalists and momentum EKF agents never short-sell or borrow; informed fundamentalists stay within [−0.5, 1.5] × wealth | every `HOLDINGS_UPDATED` of every price-only FundamentalistAgent and MomentumEKFAgent has shares ≥ 0 and CASH ≥ 0; informed: T-N5 at every fill | (shared) + 15 s |
| I5 | Book sanity | The book is never crossed; trades have real prices | bid < ask in every two-sided L1 snapshot of `book_log2`; every EXEC price > 0 | (shared) |
| I6 | Runs without value agents | The market starts and trades with no value agents (needs ≥ 1 MM) | T-M6 | 3 s |
| I7 | Market-maker liveness | No market maker dies silently | T-M7: wakes ≥ 90% of duration / mean wake and no 10-minute silence | 3 s |
| I9 | Budget respected (v1.4) | With `abides_budget {"L": 2}`, no budgeted ABIDES agent's gross position exceeds 2× its wealth at the fill price (one-order tolerance) | T-N13 on the 1-hour invariant market with the budget on | 9 s |
| I8 | No drift (re-recorded in v1.4 N6) | The invariant market (the v1.4 default market P0 with 30 informed fundamentalists, seed 42, 09:30–10:30) does not change | the I1 fingerprint in a fresh process with `PYTHONHASHSEED=0` must equal the constants recorded 2026-10-14 (DECISIONS N6) | 13 s |
| I8-legacy | Legacy market (v1.4 N6) | The v1.3 test market (LEGACY_PARAMS: 5 price-only fundamentalists, 4 momentum, 97 value agents, no budget) stays bit-identical to v1.2 (aa5f606) | the same fingerprint must equal the original I8 constants | 13 s |

\*Measured 2026-10-09 on the development laptop; the whole file takes about 32 s.

I1 found no non-determinism, so nothing needed fixing ([DECISIONS.md](DECISIONS.md)).

### I8: how the expected hash was recorded, and when it may change

Spec v1.3 Part 2 makes R2 a measurement-only release: every new switch (oracle scenario
events, the impact probe, market-maker pause windows, the momentum capital multiplier) must
be inert at its default. I8 enforces it. The constants `I8_EXPECTED` in
`test_invariants.py` were recorded **once**, on 2026-10-12, from a checkout of `v1.2`
(aa5f606), by running I1's fingerprint script with `PYTHONHASHSEED=0` (seed 42,
09:30–10:30, 5 + 4 of our agents, default `RunParams`): 2,448 executions, 121,622 shares.
The full-day run A (seed 42, 20 + 12) hash is stored in `docs/v1.3/lab/reference_hashes.json`
and checked by the lab's regression set (`scripts/realism_lab.py --campaign regression`).

The hash may be re-recorded **only** when an approved spec changes market behaviour (for
example R3) and that spec's DECISIONS.md entry says so. If a change cannot be made
without breaking I8, the milestone report says so instead (spec v1.3 §2.3).

Note on I7's "≥ 90%" criterion: wakes are Poisson, so for an arbitrary seed a 1-hour count
falls below 90% of its mean (60) about 20% of the time without anything being wrong. The
seed-42 market passes deterministically. The no-10-minute-silence check is the robust
death detector (a false alarm has probability ≈ e⁻¹⁰ per gap).

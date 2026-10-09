# FinVerse spec v1.2 (R1) — implementation report

Branch `v1.2` (from `origin/v1.1` 3c0b859), one commit per milestone, not pushed.
Date: 2026-10-09. Spec: [`docs/specs/spec_v1.2.txt`](../specs/spec_v1.2.txt).
Engine documentation: [`docs/engine/`](../engine/README.md).

| Milestone | Commit | Scope |
|---|---|---|
| W0 | 91cbeb4 | `docs/engine/` skeleton; specs copied into `docs/specs/` |
| W1 | d0d75ab | Fundamentalist edge z = gap / √(P + R); T-F8–T-F10; AGENT_FUNDAMENTALIST.md |
| W2 | b94d5aa | `PregeneratedOracle`; T-O1–T-O4; ORACLE.md |
| W3 | d93f9f4 | Market-maker cold start, rescheduling and spread cap; T-M6, T-M7; AGENTS_ABIDES.md |
| W4 | 54cbe17 | Invariants I1–I7 |
| W5 | b145739 | Dashboard U1–U3, `ENGINE_VERSION` 1.2; AGENT_MOMENTUM.md |
| W6 | (this commit) | Acceptance runs, this report, CHANGELOG, KNOWN_ISSUES, screenshots |

## Tests

`pytest abides-markets/tests api/tests`: **169 passed**. One failure, `test_ou_process`, is
pre-existing (pandas/datetime in the unused upstream `MeanRevertingOracle`; it fails the same way on
`origin/dashboard`). `test_gym_runner.py` needs the `gym` package and is excluded. The invariants
file runs in about 32 s. `npm run build` passes.

## What changed

**Fundamentalist (W1)** — `target_position` uses z = (x̂ − mid) / √(P + R_last); `R_last` is
stored in each update; `z_den` is logged. Nothing else in the agent changed.

**Oracle (W2)** — new `oracles/pregenerated_oracle.py`. The true-value path is generated once,
at construction, on a 1 s grid, from the symbol's dedicated RNG (ε vector, then megashocks), using the
exact OU step. It is served as a step function (no look-ahead), with `f_log` over the whole grid, `value_at` and
`path`. Sources are pluggable (`generate_path` / `PATH_SOURCES`). `rmsc04_ekf` builds it for
09:30–16:00 whatever the session length. The stock `SparseMeanRevertingOracle` is untouched.

**Market makers (W3)** — `cold_start_price` (= r̄); the polling branch **always** schedules the next
wake. Also `max_spread` (100¢), no quotes below 1¢, EXEC history with fill prices, and a numerically
stable caution sigmoid in both of our agents (see Deviations).

**Invariants (W4)** — `tests/test_invariants.py`, I1–I7. I1 runs the two processes with different
`PYTHONHASHSEED`s. No non-determinism was found.

**Dashboard (W5)** — U1: the price-vs-value caption has no hard-coded reference. U2: a compact table
mode and compact dollar amounts (exact on hover); measured at 1280 px, the population table's
scroll width equals its box width (814 px), so nothing is clipped. U3: the oracle series is
LTTB-downsampled to ≤ 2000 points; see the payload sizes below. `ENGINE_VERSION` is 1.2; the payload schema is
unchanged (1.1).

## Acceptance (7.2) — full day 09:30–16:00, 20 fundamentalists + 12 momentum

Reproduce: `python scripts/acceptance_v1_2.py --run A|B|C|Z` (one simulation per call, about 25 s
each), then `--report`. Results: `runs/_acceptance/v1_2_*.json` and `v1_2_report.txt`.
**Every target passes.** Nothing was tuned to get there.

### Fundamentalists

| Target | A (seed 42) | B (seed 42 + news) | C (seed 7) |
|---|---|---|---|
| median shares traded per agent per day ∈ [100, 400] | **192** | **186** | **166** |
| (min / max agent) | 12 / 1433 | 6 / 1456 | 0 / 687 |
| holdings 10th–90th percentile within [35, 65] | **48–52** | **48–52** | **48–53** |
| worst agent's time at 0 or ≥ 100 shares ≤ 1% | **0%** | **0%** | **0%** |
| median of per-agent median \|x̂ − mid\| < $1 | **$0.112** | **$0.115** | **$0.154** |
| max \|x̂ − mid\| excl. 5 min after news < $5 | **$0.83** | **$0.75** | **$0.95** |
| median K over the last hour > 0.003 | **0.015** | **0.017** | **0.014** |

Holdings are sampled every 10 s from each agent's HOLDINGS_UPDATED history and pooled over the 20
agents. v1.1 for comparison: about 1,900 shares/day per agent, swinging 0 ↔ 100 (spec §0.4).
Run B news shifts: $0.34–$1.84 (median $0.66).

### Oracle and runs without value agents

| Target | Result |
|---|---|
| A and B true-value paths identical | **PASS** (same sha256 of the float path) |
| Run Z: trades > 0 | **PASS**: 2,539 trades |
| Run Z: both MMs active all session | **PASS**: 397 and 385 wakes (390 expected), longest silence 401 s |

### Market statistics and P&L

| | A | B | C | Z (no value agents) |
|---|---|---|---|---|
| trades | 13,759 | 13,566 | 13,214 | 2,539 |
| close (day range) | $1002.79 ($999.60–1002.79) | $1002.70 | $998.52 ($997.60–1000.63) | $991.26 ($988.32–1012.75) |
| 1-min return std | 0.62 bps | 0.64 bps | 0.70 bps | 5.64 bps |
| 1-min lag-1 autocorrelation | 0.33 | 0.40 | 0.37 | 0.06 |
| \|r\| lag-1 autocorrelation | 0.05 | 0.18 | 0.20 | 0.49 |
| excess kurtosis (1-min) | 2.9 | 1.8 | 3.2 | 219 |
| gap std / mean \|gap\| | $0.13 / $0.11 | $0.14 / $0.11 | $0.14 / $0.12 | $1.45 / $9.60 |
| gap half-life | 1.3 min | 1.4 min | 1.3 min | 4.4 min |
| corr(mid, value) | 0.989 | 0.988 | 0.981 | −0.18 |
| spread mean / p95 / max | 1.4¢ / 4¢ / 55¢ | 1.5¢ / 4¢ / 55¢ | 1.5¢ / 4¢ / 32¢ | 13.8¢ / 73¢ / $22.50 |
| payload size | 8.40 MB | 8.41 MB | 8.32 MB | 7.78 MB |

**P&L vs holding by group** ($, at the closing mid; the sum over every agent is exactly $0.00 in all four runs, as it must be):

| Group | A | B | C | Z |
|---|---|---|---|---|
| ValueAgent (97) | +9,907 | +13,831 | −334 | — |
| NoiseAgent (1000) | +3,315 | +2,695 | +3,385 | +2,311 |
| MomentumEKFAgent (12) | +85 | +116 | +128 | −68 |
| FundamentalistAgent (20) | −134 | −112 | −130 | −2,120 |
| AdaptiveMarketMakerAgent (2) | −13,172 | −16,530 | −3,048 | −123 |

Per-agent medians: fundamentalists −$3 to −$5 (v1.1: −$35 to −$76 in run B), momentum +$6 to +$9.
Market maker P&L: A −$4,842 / −$8,330; B −$7,010 / −$9,520; C −$1,077 / −$1,972; Z +$90 / −$214.
The spread cap bound in Z only (9 and 3 times); it never bound in A, B or C.

### Run Z, the baseline for R3

With market makers but no value agents the market now runs all day. It is a different market:
volatility is about 9× higher, the price decouples from value (correlation −0.18, mean gap $9.60), and returns are
spiky (kurtosis 219; spreads up to $22.50). Our fundamentalists lose $2,120 together: with no
informed traders their price-only beliefs have nothing to anchor to (K9). Note that a shorter Z-type market
(1 hour, 5 + 4 of our agents) slid from $999.75 to about $589 (W3 probe); the full-day 20 + 12 market
stayed within $988–$1013. Without value agents the outcome depends strongly on the population.

## Dashboard screenshots (run B, `screenshots/`)

`1_overview.png`, `2_agents.png`, `3_news.png`, `4_health.png` (1600 px), and
`health_population_1280px.png` (U2: the population table fits at 1280 px).

## Deviations from the spec, with reasons

1. **Market-maker spread cap (new, W3).** Not in the spec, but Run Z could not run without it. When
   the market maker is the main source of quotes it observes its own spread, and its adaptive spread
   estimate grew geometrically (1.6¢ → $46.50 in 10 minutes, seed 42, no value agents). The price
   fell through the gaps toward zero and the simulation stalled. `max_spread = 100¢` stops this; it
   is logged when it binds, never binds with value agents (tested; A/B/C: 0 hits), and is not the
   inventory management deferred to R4.
2. **Two crash fixes found while making Run Z work:** a numerically stable caution sigmoid in both of
   our agents (`math.exp` overflowed; identical values otherwise), and market makers never quote
   below 1¢. The momentum agent's behaviour is otherwise unchanged.
3. **EXEC history now records the fill price** (upstream left it `None`). I1 and I5 need it.
4. **T-M6 "one MM_COLD_START per MM"** became "at most one per MM, at least one in the market". The
   second market maker already sees the first one's quotes, and §4.1 allows the cold start only
   without any mid.
5. **Test end time 10:30** is not a dashboard choice; the tests build it with `model_copy`, which skips
   that validation.
6. **Megashocks enter the OU state** at their grid point and then evolve with the OU dynamics (as in
   the sparse oracle), rather than a permanent offset. The two differ by at most 0.39% of a shock over a full day.
7. **The oracle path always covers 09:30–16:00**, so runs of different lengths share their true value.
8. **Market statistics now keep 8 significant figures** (was 6), which had rounded half-cent closes
   away ($1000.705 → $1000.71). Found by the export tests on the new seed-42 path.
9. **Seed 42 gives a different true-value path than in v1.1**, because the path is drawn in one block.
   v1.1 seed-42 numbers are therefore not directly comparable with v1.2 seed-42 numbers.

## Open questions

1. **Excess kurtosis.** Spec §0.4 P1 expected 6.7–8.0 with the new sizing. We measure 1.8–3.2 in
   A/B/C. The spec's experiment ran on the lazy oracle and a different true-value path; is
   6.7–8.0 still the expectation?
2. **One fundamentalist per run still trades a lot** (1,433 / 1,456 / 687 shares in A / B / C,
   vs a median of about 190). The cause has not been investigated yet (a small R from its δ and λ_ER
   draw would make z large). Worth a look in R3; a floor on R is one option.
3. **Market makers lose about $3k–17k a day together** ($1.1k–9.5k each; K8). Inventory skew (R4) is the plan.
4. **I7's "≥ 90% of expected wakes"** is a Poisson count: run A's market makers made 353 and 355 of 390
   (90.5%, 91.0%). It passes, but by little; the no-10-minute-silence check is the robust death
   detector.
5. **The payload is about 8.4 MB** for a full 20 + 12 day: within the 9 MB U3 target, above the old 8 MB
   budget (K12).

# The realism lab

Spec: [`docs/specs/spec_v1.3.txt`](../specs/spec_v1.3.txt) (R2). Code: `api/realism.py` (metrics,
bands, grading, scenario analysis), `api/lab.py` (the run matrix), `scripts/realism_lab.py`
(the runner). Results: [`docs/v1.3/lab/`](../v1.3/lab/).

## What the lab is for

Single simulated days are not evidence. On seed 42 the 1-minute excess kurtosis moved from
6.7–8.0 to 1.8–3.2 between two true-value paths (spec v1.3 §0.3). The lab runs a fixed
matrix of market configurations and scenarios over **20 seeds**, measures every run with the
same code, and grades the **20-seed medians** against bands taken from a real large-cap
stock. Every later change to the market (R3 onward) is then judged against this baseline.

The lab **measures** the market. It changes nothing an agent decides.

## The measurement-only rule and I8

Spec v1.3 Part 2: with every new parameter at its default, a simulation is **bit-identical**
to v1.2 (aa5f606). Invariant **I8** (`abides-markets/tests/test_invariants.py`) checks the
sha256 of every execution and of every agent's final holdings of the 1-hour invariant
market against constants recorded once from aa5f606 ([TESTING.md](TESTING.md)). The new
switches are scenario tooling only:

| Switch | Where | Default (inert) |
|---|---|---|
| `oracle_events` | `rmsc04_ekf.build_config` → oracle path source `"scenario"` | `None` → path source `"synthetic_ou"` |
| `probe` | `build_config` → `ImpactProbeAgent` | `None` → no probe agent |
| `mm_pause_windows` | `build_config` → `AdaptiveMarketMakerAgent(pause_windows=…)` | `None` |
| `mom_capital_mult` | `build_config` | `1.0` |

None of them is in `RunParams` or the dashboard sidebar in R2. Nothing is tuned: every
number is reported as measured (§2.4).

## Inputs of every metric

`realism.series_from_end_state(end_state, config)` builds, for one run (times in seconds
since 09:30, a 1 s grid t = 0 … duration):

| Series | Definition |
|---|---|
| `mid_1s` | L1 mid ($) of the last **two-sided** book at or before t (forward-filled through one-sided moments). Before the first two-sided book of the day: the first two-sided mid. |
| `val_1s` | true value ($) in force at t: `oracle.value_at`, the exact float path (a step function on the oracle's 1 s grid) |
| `spr_1s` | L1 spread (cents) of the last book state at or before t; one-sided or empty book → NaN |
| `close_1m` | `mid_1s` at the end of each 1-minute bar, t = 60, 120, … (390 for a full day) |
| `r1` | 1-minute log returns of `close_1m` (389 for a full day). `r1[i]` covers minute i + 1. |
| `vol_1m` | shares executed per 1-minute bar (each EXEC counted once) |
| `net_1m` | per agent class, net shares **bought** per bar (the buyer of an EXEC is the passive party when the passive order's side is BUY, else the aggressor) |

The payload's own statistics (Market Health tab) interpolate the true value linearly between
oracle points; the lab uses the step function, as the agents see it. The gap std therefore
differs in the fourth digit between the two (seed 42, 1 hour: $0.18586 vs $0.18575).

## Metrics (spec v1.3 Part 3)

| Key | Formula | Meaning |
|---|---|---|
| `sigma_1m_bps` | 1e4 · std(r1, ddof = 1) | 1-minute volatility |
| `sigma_day_implied` | σ_1m · √389 / 100 (%) | the daily volatility a random walk with that σ_1m would have |
| `day_return` | ln(mid 16:00 / mid 09:30) | one day's move; `sigma_day_xseed` = std over seeds (%) |
| `ac1`, `ac_1_5`, `n_out` | autocorrelation of r1 at lags 1…5 (`api.stats.acf`); how many lie outside ±2/√n (±0.101 for n = 389) | predictability |
| `vr5`, `vr30` | Var(ln p(t+k) − ln p(t)) / (k · Var(r1)), overlapping k-minute returns | variance ratio: 1 for a random walk, > 1 when the price trails a target |
| `acf_abs`, `cs`, `ps` | acf of \|r1\| at lags 1…30; CS = mean lags 1–5, PS = mean lags 10–30 | volatility clustering and its persistence |
| `kurt`, `skew` | Fisher excess kurtosis, skewness of r1 (`scipy.stats`) | fat tails |
| `vv_corr` | Spearman correlation over 5-minute buckets of RV_b = √Σ r1² and V_b = shares | do volume and volatility move together? |
| `u_ratio` | (vol 09:30–10:00 + vol 15:30–16:00) / (2 × mean 30-min vol 10:00–15:30) | intraday U-shape (full days only) |
| `spread_med/p95/max_ticks`, `one_sided_share` | over two-sided grid seconds; share of seconds with an empty side | liquidity |
| `gap_std`, `gap_mean_abs`, `corr_mid_value` | gap = mid_1s − val_1s ($) | how far the price wanders from value |
| `gap_half_life_min` | `api.stats.gap_half_life(gap, lags_s = (60, 120, 300, 600, 1200, 1800, 3600))` | how fast a mispricing halves (spring model); `gap_half_life_min_dash` uses the dashboard's (60, 120, 300, 600) |
| `vol_ratio_price_value` | std(r1) / std(1-min log returns of the true value at the same bar ends) | is the price smoother than the value it follows? (§0.5) |
| `regime_contrast` | max/min over the 13 non-overlapping 30-minute windows of std(r1 in the window) | calm vs stressed periods |
| `trend_share` | share of 1-minute-stepped 30-minute windows with \|return\| > 2 × the day's median | trending stretches |

**Accounting and agent sanity** (`realism.agent_sanity`, §3.9–3.10): P&L vs holding per agent
(`api.export.pnl_vs_hold`, at the closing mid) and per class (total, median, p10, p90);
orders sent, shares traded (both sides), volume share; turnover and pooled holdings p10–p90
(sampled every 10 s) of our agents; the largest single fundamentalist's volume share and
turnover (heavy-trader watch). **zero_sum** = the sum of P&L vs holding over every agent,
the probe included, computed in integer half-cents. It must be exactly 0: a non-zero value
fails the run.

### Known limit of the half-life estimator

The spec's estimator de-means the gap of **one** 6.5-hour day and fits ρ(L) = e^(−kL). For long
half-lives the sample autocorrelation is biased low by about (1 + φ)/((1 − φ) N), which is
large when a day holds only a few half-lives. Measured on synthetic AR(1) gaps
(2026-10-12, 20 paths each, test T-R8):

| True half-life | Median estimate | p10–p90 |
|---|---|---|
| 1 min | 1.00 min | 0.86–1.06 |
| 10 min | 8.97 min (−10%) | 6.41–10.86 |
| 45 min | 20.8 min (**−54%**) | 12.6–34.3 |
| 90 min | 27.1 min (**−70%**) | 16.0–55.6 |

So on one day the estimator can tell 1 minute from 10 minutes, but it reads a true 45–90 min
half-life as 20–30 min. The G10 PASS band (30–90 min) is therefore reachable only by a market
whose true half-life is well above 90 minutes. This is reported, not fixed, in R2: the bands are
provisional and revisited before R5 (D-R2-1).

## Bands and grades (spec v1.3 Part 4)

One table, `api/realism.py:BANDS`, also sent to the dashboard. Source of every band: *owner
D-R2-1, 2026-10-11, large-cap reference* (a liquid stock moving about 1–2% a day; provisional).

| # | Metric | PASS | WARN | FAIL |
|---|---|---|---|---|
| G1 | σ_1m (bps) | 5–10 | 2.5–5 or 10–20 | otherwise |
| G2 | σ_day across seeds (%, lab only) | 1–2 | 0.5–1 or 2–4 | otherwise |
| G3 | \|ac1\| | ≤ 0.10 | 0.10–0.20 | > 0.20 |
| G4 | VR(5) | 0.80–1.25 | 0.60–0.80 or 1.25–1.60 | otherwise |
| G5 | clustering | CS ≥ 0.10 and PS > 0.03 | CS 0.05–0.10, or CS ≥ 0.10 with PS ≤ 0.03 | CS < 0.05 |
| G6 | excess kurtosis | ≥ 3 | 1–3 | < 1 |
| G7 | vv_corr | ≥ 0.30 | 0.10–0.30 | < 0.10 |
| G8 | spread (ticks) | median ≤ 1 and p95 ≤ 5 | p95 ≤ 10 | otherwise |
| G9 | gap std ($) | 1–3 | 0.50–1 or 3–5 | otherwise |
| G10 | gap half-life (min) | 30–90 | 10–30 or 90–180 | otherwise, or none |
| G11 | regime contrast | ≥ 5 | 3–5 | < 3 |
| G12 | impact exponent β (lab only) | 0.40–0.70 | 0.25–0.40 or 0.70–0.90 | otherwise |
| G13 | impact recovery I_perm / I_peak (lab only) | 0.1–0.8 | 0–0.1 or 0.8–1 | otherwise |

A value exactly on a boundary takes the better grade (all intervals are closed and PASS is
tested first; for G5 a PS of exactly 0.03 passes; for G13 a ratio of exactly 0 is WARN).

**Over seeds** (`realism.aggregate`, `realism.scorecard`): median, p10, p90, min, max
(`numpy.percentile`, linear interpolation) and the number of valid seeds. The grade is that of
the **median**; `pass_share` is the share of seeds whose own value passes. Fewer than 15 valid
seeds → **INCOMPLETE**. A sampling floor to remember for G11: with constant volatility and
29–30 returns per window, the regime contrast is about 1.55 by chance alone (median of 500
normal days, test T-R7), so 2–3× means "no regimes".

**Single run** (dashboard): the same bands applied to one day, G1 and G3–G11 only, labelled
"single run — the 20-seed lab report is authoritative".

## Configurations and scenarios

(to be completed with the runner, L2–L5)

## Scenario analysis definitions (spec v1.3 §7.3)

Every scenario is compared with its **baseline on the same seed**: until the trigger the true
value, every agent's parameters and every random stream are identical, so later differences
are caused by the trigger (Appendix A8). Differences are on the 1 s grid; "smoothed" means a
centred 30 s rolling mean. Times are minutes after the trigger t0 (11:00 unless stated).

| Scenario | Function | Outputs |
|---|---|---|
| Value jump (S2, S2n, S3, S7c), J = jump ($) | `jump_response` | f(t) = (mid_T − mid_B)/J; t50, t90 (first smoothed f ≥ 0.5 / 0.9 within 90 min); overshoot = max(0, max smoothed f over 60 min − 1); settle = mean f over 60–90 min; belief_5/30 = median over fundamentalists of (x̂_T − x̂_B)/J; mom_entries = BREAKOUT + REENTRY in the jump's direction within 30 min, T − B; net_flow per class over 60 min, T − B; vol and volume uplift over 30 min, T / B |
| News only (S4, S4n), s = sign of the sentiment | `news_response` | R(t) = s · 1e4 · ln(mid_T / mid_B) (bps); R_peak, t_peak over 30 min (smoothed); t_half_rev; R_60 = mean over 55–65 min; belief shifts from the agents' NEWS_RECEIVED logs |
| Volatility burst (S5) | `vol_burst` | σ_1m over 11:00–12:00 and 12:00–13:00, T / B; spread, volume and gap std ratios in the burst |
| Market-maker pause (S6), W = 13:00–13:30 | `mm_pause` | spread mean/p95/max and one-sided share in W, T and B; σ and volume ratios; max \|mid_T − mid_B\|; recovery_min = minutes after 13:30 until the mean spread over the **next** 5 minutes is ≤ 1.2× the baseline's over the same 5 minutes |
| Price impact (IMP-*), s = +1 buy, −1 sell | `impact_run`, `impact_beta`, `noise_floor` | I(t) = s · 1e4 · ln(mid_T / mid_B); I_end (last 10 s of the execution), I_peak (max of the smoothed I up to 2 min after), I_perm (mean 25–35 min after); shortfall vs the arrival mid; fill rate; who absorbed the order; noise floor = p90 of \|I\| for the 100-share placebo; β = OLS slope of ln(median I_end) on ln(median q), 90% bootstrap CI over seeds (2000 resamples, seed 0) |

## How to run

(to be completed with the runner, L2)

## How to read the outputs

(to be completed with the runner, L2)

## Known limits

(to be completed in L7)

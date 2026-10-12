# Realism lab — interim report, Campaign c1 (milestone L2)

*Interim. The final findings report is [BASELINE.md](BASELINE.md) (milestone L7).*

**Runs:** C-DEF, C-V20, S4, S4n × 20 seeds (42, 7, 1–6, 8–19) = 80 full days
(09:30–16:00, 20 fundamentalists + 12 momentum EKF, 1000 noise, 2 market makers,
97 value agents except C-V20). **Engine:** `v1.2-a72d6cf+dirty` (the L1 commit; the market
code is identical to v1.2 aa5f606, checked by I8 and by the seed-42 C-DEF run reproducing the
reference run A hash). **Date:** 2026-10-12. **Data:** [`summary.json`](summary.json);
per-run files in `runs/_lab/` (not committed). Every number is a 20-seed median
[p10–p90] unless stated. Nothing was tuned.

**Run health.** 80/80 runs completed; zero_sum = 0 exactly in every run; conservation,
book sanity and long-only flags hold in every run; 25 s per run (24–27), peak memory
≈ 466 MB per process.

## 1. The market today in numbers (C-DEF)

A one-tick, very liquid market whose price follows the true value too closely and too
smoothly: 1-minute volatility **0.71 bps** (a large-cap: 5–10), a day moves **0.19%** (std over
seeds; 1–2% is the reference), the next minute's return is predictable (**ac1 = +0.37**,
VR(5) = **1.90**), mispricings are **$0.145** (std) and halve in **1.5 minutes**, there are no
calm or stressed periods (regime contrast **2.39**, sampling noise alone gives ≈ 1.55) and no
volatility clustering (CS **0.038**). Volume is **591,000** shares a day, 86.7% of it value agents.

## 2. Scorecards

### C-DEF (default market, = S1 quiet day)

| # | Metric | Band (PASS) | Median [p10–p90] | Grade | pass_share |
|---|---|---|---|---|---|
| G1 | σ_1m (bps) | 5–10 | 0.712 [0.631–0.774] | FAIL | 0% |
| G2 | σ_day across seeds | 1–2% | 0.191% | FAIL | — |
| G3 | \|ac1\| | ≤ 0.10 | 0.374 [0.313–0.432] | FAIL | 0% |
| G4 | VR(5) | 0.80–1.25 | 1.90 [1.74–2.15] | FAIL | 0% |
| G5 | CS / PS | CS ≥ 0.10, PS > 0.03 | CS 0.038 [0.014–0.079] / PS 0.0005 [−0.009–0.021] | FAIL | 0% |
| G6 | excess kurtosis | ≥ 3 | 3.02 [2.03–7.54] | PASS (knife edge) | 50% |
| G7 | vv_corr | ≥ 0.30 | **−0.252** [−0.354 – −0.085] | FAIL | 0% |
| G8 | spread median / p95 (ticks) | ≤ 1 / ≤ 5 | 1 [1–1] / 3 [3–3] | PASS | 100% |
| G9 | gap std | $1–3 | $0.145 [0.132–0.156] | FAIL | 0% |
| G10 | gap half-life | 30–90 min | 1.51 min [1.34–2.01] | FAIL | 0% |
| G11 | regime contrast | ≥ 5 | 2.39 [1.81–3.09] | FAIL | 0% |

Reported only: VR(30) 2.14 [1.36–2.73]; ac lags 1–5 (median) +0.374, +0.218, +0.095, +0.041,
−0.002 (3 [2–4] of 5 outside ±0.101); \|r\| acf lags 1–5 +0.198, +0.038, +0.018, −0.004, −0.011;
skew −0.16; u_ratio 1.16 [1.11–1.18]; corr(mid, value) 0.979 [0.954–0.990];
**vol_ratio_price_value 0.577 [0.535–0.628]**; trend_share 0.17; σ_day implied 0.14%;
spread max 50 ticks [23–98], mean 1.35; one-sided 0.04% of seconds; mean \|gap\| $0.119;
dashboard-lag half-life 1.45 min; 13,500 trades.

| Class | volume share % | P&L vs hold total $ | P&L vs hold median $ |
|---|---|---|---|
| Value (97) | 86.7 [85.9–87.6] | −15 [−6,120 – +12,700] | +17 |
| Noise (1000) | 7.18 [6.85–7.38] | +462 [−5,420 – +3,360] | 0 |
| Market maker (2) | 5.40 [4.75–5.94] | +1,110 [−16,100 – +6,090] | +553 |
| Fundamentalist (20) | 0.404 [0.288–0.557] | −112 [−182 – −24] | −2.92 |
| Momentum EKF (12) | 0.383 [0.151–0.601] | +86 [+9 – +354] | +3.13 |

Our agents: fundamentalist turnover median 160 shares/day (p90 562, max 790), holdings 48–52
(p10–p90); momentum turnover median 248 (p90 697), holdings 48–51.

**Heavy-trader watch (D-R2-4):** the largest fundamentalist's share of volume is 0.067%
[0.047–0.118], at most 0.126% (seed 10); its turnover 790 [552–1,430] shares. **No seed exceeds
1%.** On seed 42 it is agent 1109 with the draw of spec §0.4 (δ 0.00088, λ_ER 0.59, a_max 0.99,
z0 1.48, b_f 0.012, k 2.49), 0.118% of volume.

### C-V20 (20 value agents instead of 97)

| # | Metric | Median [p10–p90] | Grade | pass_share |
|---|---|---|---|---|
| G1 | σ_1m | 0.612 [0.532–1.22] bps | FAIL | 0% |
| G2 | σ_day across seeds | 0.244% | FAIL | — |
| G3 | \|ac1\| | 0.243 [0.107–0.348] | FAIL | 10% |
| G4 | VR(5) | 1.57 [0.43–1.95] | WARN | 15% |
| G5 | CS / PS | 0.115 [0.041–0.172] / 0.004 [−0.013–0.032] | WARN | 15% |
| G6 | kurtosis | 15.6 [6.5–241] | PASS | 95% |
| G7 | vv_corr | −0.050 [−0.177–0.139] | FAIL | 0% |
| G8 | spread | 1 / 4 [4–5] ticks | PASS | 100% |
| G9 | gap std | $0.256 [0.226–0.301] | FAIL | 0% |
| G10 | half-life | 3.91 min [2.40–4.77] | FAIL | 0% |
| G11 | regime contrast | 4.94 [2.92–15.4] | WARN | 50% |

Volume 129,000 shares (−78% vs C-DEF), 4,720 trades (−65%); value agents 61% of volume,
noise 32%, fundamentalists 1.45%. vol_ratio_price_value 0.50 [0.44–1.06]; corr(mid, value)
0.938; spread max 248 ticks (vs 50). The heavy fundamentalist is 0.245% [0.18–0.40] of the
(much smaller) volume, max 0.47%: no seed above 1%. Fewer value agents loosen the pinning a
little (gap ×1.8, half-life ×2.6) and make the day spikier (kurtosis, regime contrast up) but
not more volatile, and the spread's tail widens.

## 3. The §0.5 hypothesis (price smoother than value)

**Confirmed.** vol_ratio_price_value = **0.577** [0.535–0.628]: the price's 1-minute returns
have 58% of the standard deviation of the true value's 1-minute changes at the same instants.
VR(5) = **1.90** [1.74–2.15] and VR(30) = 2.14: 5- and 30-minute moves are much larger than √k
times the 1-minute moves, the signature of a price that trails its target. The positive
autocorrelation is concentrated at lags 1–2 (+0.37, +0.22). The value's own 1-minute
std is ≈ 12¢ (≈1.2 bps), so even a price that tracked today's value perfectly would show ≈ 1.2
bps per minute, a quarter of the bottom of the G1 band. Reaching 5–10 bps needs a more
volatile value process **and** volatility the market creates itself, not only looser
tracking. (Observation for R3/R4; no design decision here.)

## 4. Hype news S4 / S4n (headline at 11:00, ±0.9, beliefs only)

| | S4 (+0.9) | S4n (−0.9) |
|---|---|---|
| fundamentalist belief shift, per-run median | **+$0.69** [0.36–1.09] | **−$0.69** [−1.09 – −0.36] |
| belief shift range over agents (median run) | $0.22–1.13 | −$1.13 – −0.22 |
| momentum v̂ change, per-run median | +1.1e-7 /s | −1.1e-7 /s |
| R_peak (bps, smoothed, first 30 min) | 0.87 [0.50–1.66] | 0.82 [0.49–1.42] |
| t_peak (min) | 22 [11–26] | 17 [5–26] |
| t_half_rev (min) | 23 [12–28] | 19 [5–27] |
| R_60 (bps) | −0.005 [−0.39 – +0.55] | −0.08 [−0.38 – +0.16] |

**The headline does not move the price measurably.** Beliefs move as designed, and
symmetrically for the two signs. But the median response curve R(t)
([news_response.png](figures/news_response.png)) stays within ±0.3 bps of zero, inside the
seed-to-seed band. R_peak is the maximum of a noisy difference over 30 minutes, which is
positive even with no effect. Its timing (17–22 min, not just after the news) and its equal
size for good and bad news say it is post-trigger divergence (spec App. A8), not a reaction. The
IMP-0 placebo of Campaign c3 will measure that divergence floor. No asymmetry between good and bad
news is visible. Market statistics of S4/S4n are indistinguishable from C-DEF.

## 5. Verdicts so far

| | Expectation | Verdict |
|---|---|---|
| E1 | C-DEF fails G1, G2, G3, G4, G9, G10, G11; WARN on G6; PASS on G8; G5, G7 unknown | **Partly.** All the expected FAILs and the G8 PASS confirmed. G6 is PASS on the median (3.02, on the boundary; pass_share 50%), not WARN. G5 FAIL (CS 0.04), G7 FAIL with a *negative* correlation (−0.25). |
| E2 | vol_ratio_price_value < 1 and VR(5) > 1.25 | **Confirmed**: 0.577 and 1.90 (on every seed: vol ratio at most 0.71, VR(5) at least 1.61). |
| E3 | C-V20: gap std ≈ $0.2–0.3, half-life ≈ 4 min (still FAIL), activity ≈ 60% lower | **Partly**: gap $0.256 and half-life 3.9 min confirmed, still FAIL; activity is **78%** lower in shares (65% in trades), more than expected. |
| E5 | S4/S4n: R_peak a few bps or less, reverting within ≈ 10–20 min; belief shifts $0.3–1.8 | **Partly**: R_peak below 1 bps, but it is not a measurable response (indistinguishable from divergence noise, see §4), so "reversion" has no meaning here. Belief shifts $0.22–1.13 (medians $0.69), inside the expected range. |

## 6. Notes for the owner

- **G7 is negative.** Over 5-minute buckets, volume is *higher* when the price is *calmer*
  (−0.25). Real markets show the opposite. A likely mechanism, to check in R3: value agents
  trade most when the price is pinned at value and their own noisy estimates straddle it.
- **The G10 estimator cannot reach its PASS band on one day.** A true 45–90 min half-life reads
  as 21–27 min ([REALISM_LAB.md](../../engine/REALISM_LAB.md), T-R8). Irrelevant today (1.5
  min) but important before R5.
- **Seeds.** The spec's seed list contains 7 twice; the lab uses 42, 7, 1–6, 8–19
  (DECISIONS.md, 2026-10-12).

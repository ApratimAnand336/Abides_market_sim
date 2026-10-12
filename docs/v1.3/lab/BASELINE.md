# The realism baseline (R2 findings report)

Spec: [`docs/specs/spec_v1.3.txt`](../../specs/spec_v1.3.txt), Part 11.4. Methods:
[`docs/engine/REALISM_LAB.md`](../../engine/REALISM_LAB.md). Data: [`summary.json`](summary.json).
Interim c1 report: [BASELINE_c1.md](BASELINE_c1.md).

**What was run.** All 18 configurations of Appendix C × 20 seeds (42, 7, 1–6, 8–19) = **360
full days** (09:30–16:00; 20 fundamentalists + 12 momentum EKF, 1000 noise, 2 market makers,
97 value agents unless stated). Every run completed; **zero_sum = 0 exactly in all 360**;
conservation, book sanity and long-only flags hold in all 360. Dates 2026-10-12. Engine
versions: c1 `v1.2-a72d6cf`, c2 `v1.2-c19ee3a`, c3 `v1.2-c6a0e38`, c4 `v1.2-5a386e0` (all
"+dirty", see the note at the end). The market code is the same in all four: the default market
is bit-identical to v1.2 (invariant I8) and the seed-42 C-DEF run reproduces the reference
run A hash. Numbers are 20-seed **medians [p10–p90]** unless stated. Nothing was tuned.

---

## 1. The market today, in numbers

FinVerse's default market (C-DEF) is a one-tick, very liquid market whose price follows the
true value too closely and too smoothly. Its 1-minute volatility is **0.71 bps** [0.63–0.77];
a large-cap's is 5–10. A day moves **0.19%** (std over seeds; reference 1–2%). The next
minute's return is predictable: lag-1 autocorrelation **+0.37** and VR(5) **1.90**.
Mispricings are **$0.145** (std) and halve in **1.5 minutes**. There are no calm or stressed
periods (regime contrast **2.39**, where chance alone gives ≈ 1.55) and no volatility clustering
(CS **0.038**). Volume and volatility move in **opposite** directions (−0.25). The spread is
1 tick (p95 3). The value agents are **86.7%** of the volume; our 32 agents are 0.8%.

## 2. Scorecards

### C-DEF: the default market (= S1, a quiet day)

| # | Metric | Band (PASS) | Median [p10–p90] | Grade | pass_share |
|---|---|---|---|---|---|
| G1 | σ_1m | 5–10 bps | 0.712 [0.631–0.774] bps | **FAIL** | 0% |
| G2 | σ_day across seeds | 1–2% | 0.191% (n = 20) | **FAIL** | — |
| G3 | \|ac1\| | ≤ 0.10 | 0.374 [0.313–0.432] | **FAIL** | 0% |
| G4 | VR(5) | 0.80–1.25 | 1.90 [1.74–2.15] | **FAIL** | 0% |
| G5 | CS / PS | CS ≥ 0.10 and PS > 0.03 | 0.038 [0.014–0.079] / 0.0005 [−0.009–0.021] | **FAIL** | 0% |
| G6 | excess kurtosis | ≥ 3 | 3.02 [2.03–7.54] | **PASS** (on the edge) | 50% |
| G7 | vv_corr | ≥ 0.30 | −0.252 [−0.354 – −0.085] | **FAIL** | 0% |
| G8 | spread median / p95 | ≤ 1 / ≤ 5 ticks | 1 [1–1] / 3 [3–3] | **PASS** | 100% |
| G9 | gap std | $1–3 | $0.145 [0.132–0.156] | **FAIL** | 0% |
| G10 | gap half-life | 30–90 min | 1.51 [1.34–2.01] min | **FAIL** | 0% |
| G11 | regime contrast | ≥ 5 | 2.39 [1.81–3.09] | **FAIL** | 0% |
| G12 | impact exponent β | 0.40–0.70 | 0.90 (90% CI 0.77–1.25) | **FAIL** | — |
| G13 | impact recovery (1% order) | 0.1–0.8 | −0.02 [−0.17 – +0.28] | **FAIL** | — |

### C-V20: 20 value agents instead of 97 (a different market with the same true value)

| # | Metric | Median [p10–p90] | Grade | pass_share |
|---|---|---|---|---|
| G1 | σ_1m | 0.612 [0.532–1.22] bps | FAIL | 0% |
| G2 | σ_day across seeds | 0.244% | FAIL | — |
| G3 | \|ac1\| | 0.243 [0.107–0.348] | FAIL | 10% |
| G4 | VR(5) | 1.57 [0.43–1.95] | WARN | 15% |
| G5 | CS / PS | 0.115 [0.041–0.172] / 0.004 [−0.013–0.032] | WARN | 15% |
| G6 | kurtosis | 15.6 [6.5–241] | PASS | 95% |
| G7 | vv_corr | −0.050 [−0.177–0.139] | FAIL | 0% |
| G8 | spread median / p95 | 1 / 4 [4–5] ticks | PASS | 100% |
| G9 | gap std | $0.256 [0.226–0.301] | FAIL | 0% |
| G10 | half-life | 3.91 [2.40–4.77] min | FAIL | 0% |
| G11 | regime contrast | 4.94 [2.92–15.4] | WARN | 50% |

### Reported-only diagnostics

| | C-DEF | C-V20 |
|---|---|---|
| VR(30) | 2.14 [1.36–2.73] | 2.68 [0.36–3.76] |
| ac lags 1–5 (median) | +0.37, +0.22, +0.10, +0.04, −0.00 | +0.24, +0.19, +0.14, +0.09, +0.09 |
| lags of 1–5 outside ±2/√n | 3 [2–4] | 4 [1.9–5] |
| acf of \|r\|, lags 1–5 | +0.20, +0.04, +0.02, −0.00, −0.01 | +0.21, +0.17, +0.10, +0.03, +0.05 |
| skew | −0.16 [−0.62–0.37] | −0.09 [−2.86–3.16] |
| u_ratio (intraday U) | 1.16 [1.11–1.18] | 1.73 [1.59–2.06] |
| corr(mid, value) | 0.979 [0.954–0.990] | 0.938 [0.831–0.973] |
| **vol_ratio_price_value** | **0.577** [0.535–0.628] | 0.499 [0.436–1.06] |
| trend_share | 0.17 [0.09–0.21] | 0.18 [0.09–0.29] |
| σ_day implied by σ_1m | 0.14% | 0.12% |
| spread mean / max (ticks) | 1.35 / 50 [23–98] | 1.75 / 248 [28–255] |
| one-sided seconds | 0.04% | 0.05% |
| mean \|gap\| | $0.119 | $0.199 |
| half-life, dashboard lags | 1.45 min | 3.58 min |
| shares / trades per day | 591,000 / 13,500 | 129,000 / 4,720 |
| wall time / peak memory per run | 25 s / 466 MB | 23 s / 427 MB |

### Agent sanity (C-DEF)

| Class | volume share % | P&L vs hold total $ | median $ per agent |
|---|---|---|---|
| Value (97) | 86.7 [85.9–87.6] | −15 [−6,120 – +12,700] | +17 |
| Noise (1000) | 7.18 [6.85–7.38] | +462 [−5,420 – +3,360] | 0 |
| Market maker (2) | 5.40 [4.75–5.94] | +1,110 [−16,100 – +6,090] | +553 |
| Fundamentalist (20) | 0.404 [0.288–0.557] | −112 [−182 – −24] | −2.92 |
| Momentum EKF (12) | 0.383 [0.151–0.601] | +86 [+9 – +354] | +3.13 |

Fundamentalists trade a median 160 shares a day each (p90 562) and hold 48–52 shares
(p10–p90). Momentum agents trade a median 248 (p90 697) and hold 48–51. Over 20 seeds the
market makers' total P&L is spread widely around zero (K8 said "they lose every day" from 3 runs:
not confirmed as a rule).

**Heavy-trader watch (D-R2-4).** In C-DEF the largest single fundamentalist is 0.067% [0.047–0.118]
of volume (max 0.126%, seed 10) and trades 790 [552–1,430] shares. On seed 42 it is agent 1109 with
spec §0.4's draw (δ 0.00088, λ_ER 0.59, a_max 0.99, z0 1.48, b_f 0.012, k 2.49). **No seed of any of the
18 configurations exceeds 1%**; the largest is 0.47% in C-V20, where total volume is 78% lower.

## 3. The §0.5 hypothesis: is the price smoother than the value it follows?

**Yes.** The price's 1-minute returns have **58%** of the standard deviation of the true value's
1-minute changes at the same instants (vol_ratio_price_value 0.577 [0.535–0.628]; at most
0.71 on any seed). VR(5) = **1.90** (at least 1.61 on any seed) and VR(30) = 2.14. Five- and
thirty-minute moves are much larger than √k times the 1-minute moves, so the price trails its
target step by step, with the positive autocorrelation concentrated at lags 1–2 (+0.37, +0.22).

What follows (observation, no decision). The value's own 1-minute std is ≈ 11–12¢, about 1.2 bps. A
price that tracked today's value *perfectly* would therefore show ≈ 1.2 bps a minute, a quarter of the
bottom of the G1 band. Looser tracking alone cannot reach 5–10 bps: it needs a more volatile value
process **and** volatility the market creates by itself. S5 confirms the first part: tripling the
value's volatility raises the price's by only 2.4× (§4.3).

## 4. Scenarios (treated − baseline on the same seed, t0 = 11:00)

### 4.1 Value jumps S2 (+2%), S2n (−2%), S3 (+2% with a +0.9 headline)

[jump_response.png](figures/jump_response.png)

| | S2 | S2n | S3 |
|---|---|---|---|
| t50 (min) | 10.4 [6.1–15.5] | 11.2 [6.9–14.1] | 11.6 [7.7–16.4] |
| t90 (min) | 11.8 [7.8–17.1] | 12.8 [8.1–18.4] | 13.1 [9.4–19.1] |
| overshoot (fraction of J) | 0 [0–0.0001] | 0 [0–0.0003] | 0 [0–0.004] |
| settle (f over 60–90 min) | 0.976 [0.975–0.977] | 0.977 [0.977–0.978] | 0.976 [0.975–0.977] |
| fundamentalist belief at +5 / +30 min | 0.02 / 0.97 | 0.03 / 0.97 | 0.03 / 0.97 |
| extra momentum entries (12 agents) | +12 [8.7–14.1] | +12 [3.8–14.2] | +12 [4.8–13.1] |
| net shares bought in 60 min: value agents | +7,980 [3,470–14,500] | −9,250 [−19,900 – −4,680] | +8,470 |
| market makers | −6,530 [−13,300 – −2,690] | +8,280 [3,870–18,600] | −7,190 |
| noise | −882 | +696 | −918 |
| fundamentalists / momentum EKF | −6 / +5.5 | +9 / −7 | −8 / −3 |
| σ_1m in 30 min, T / B | 23.5× [14.5–38.9] | 19.9× | 22.0× |
| volume in 30 min, T / B | **0.75** [0.68–0.90] | 0.76 | 0.72 |

S3 − S2 on the same seed: t50 +0.42 min [−3.0 – +6.7], t90 +0.56 [−3.3 – +8.4]: the headline does
not speed up price discovery.

**How the jump gets priced.** Not by trading. For about 8 minutes the value agents buy and the
market makers sell into them, and the price creeps to about 20% of the jump. Then the sell side
of the book empties, and the mid gaps up to about 97% within a minute. On seed 42 the spread
reaches 33–156 ticks and volume falls from about 1,500 to 40–150 shares a minute. Volume over the
first 30 minutes is 25% *lower* than without the jump. The price settles at 97.6% of the jump, not
100%. A plausible reason, to verify in R3: the value agents' own model pulls the value back
toward r̄ by the close. Our fundamentalists only follow the price: 2% of the jump at +5 min, 97%
at +30 min.

### 4.2 Hype news S4 (+0.9), S4n (−0.9)

[news_response.png](figures/news_response.png)

| | S4 | S4n |
|---|---|---|
| fundamentalist belief shift, per-run median | +$0.69 [0.36–1.09] | −$0.69 [−1.09 – −0.36] |
| belief shift range over agents (median run) | $0.22–1.13 | −$1.13 – −$0.22 |
| momentum v̂ change, per-run median | +1.1e-7 /s | −1.1e-7 /s |
| R_peak (bps) | 0.87 [0.50–1.66] | 0.82 [0.49–1.42] |
| t_peak / t_half_rev (min) | 22 / 23 | 17 / 19 |
| R_60 (bps) | −0.00 [−0.39 – +0.55] | −0.08 [−0.38 – +0.16] |

**No measurable price response.** Beliefs move as designed, symmetrically. But the median R(t)
stays within ±0.3 bps of zero, R_peak is of the size of the impact placebo's divergence (I_peak of
a 100-share order: 0.17 [0.00–0.37] bps; p90 |I_end| 0.40 bps), and it peaks 17–22 minutes after
the news with the same size for good and bad news. It is post-trigger divergence, not a reaction.
No good/bad asymmetry is visible.

### 4.3 Volatility burst S5 (value innovations ×3, 11:00–12:00)

[vol_burst.png](figures/vol_burst.png)

| Metric | Median [p10–p90] |
|---|---|
| value's own σ_1m in the burst, T / B | 3.00 [2.99–3.01] |
| **price σ_1m in the burst, T / B (in_ratio)** | **2.38** [2.16–3.05] |
| price σ_1m 12:00–13:00, T / B (after_ratio) | 1.13 [0.89–1.28] |
| spread mean in the burst, T / B | 1.30 [1.18–1.47] |
| volume in the burst, T / B | 0.88 [0.84–0.92] |
| gap std in the burst, T / B | 3.01 [2.68–3.47] ($0.376 vs $0.131) |

The price passes on about 80% of the value's extra volatility. Its mispricing triples and its
volume falls by 12%. After the burst, volatility is back near the baseline: the median is 13%
above it, within the seed-to-seed range.

### 4.4 Market makers paused S6 (13:00–13:30)

[mm_pause.png](figures/mm_pause.png)

| In W = 13:00–13:30 | S6 | C-DEF |
|---|---|---|
| spread mean (ticks) | 2.96 [2.22–4.14] | 1.31 [1.18–1.48] |
| spread p95 | 11 [5.9–16.1] | 3 [2–4] |
| spread max | 83 [44–202] | 10 [6–20] |
| one-sided seconds | 0.5% [0–3.1%] | 0% |
| σ_1m, T / B | 1.86 [1.39–3.70] | |
| volume, T / B | 0.92 [0.87–0.97] | |
| max \|mid_T − mid_B\| | $0.61 [0.33–1.06] | |
| recovery after 13:30 | 0 min [0–0.4] | |

Without the market makers the value agents' passive orders keep the market trading at 92% of its
volume. The spread more than doubles, its tail grows eightfold, and the book is occasionally
one-sided. Everything is back to normal within the first 5 minutes after 13:30.

### 4.5 Momentum capital S7a (×3), S7b (×10), S7c (×10 + value jump)

| vs C-DEF, same seed | S7a ×3 | S7b ×10 |
|---|---|---|
| momentum volume share | 1.02% [0.52–1.85] (base 0.38%) | 3.58% [1.86–5.80] |
| entries per agent per day | 6.5 (base 6.1) | 6.4 |
| momentum P&L vs hold, total | +$257 (base +$86) | **−$549** [−1,340 – +1,430] |
| Δ σ_1m (bps) | +0.006 | +0.053 [0.016–0.108] |
| Δ ac1 / Δ VR(5) | −0.004 / −0.04 | +0.029 / −0.01 |
| Δ CS / Δ vv_corr | +0.002 / +0.05 | +0.034 / +0.13 |
| Δ gap std / Δ half-life | −$0.0006 / −0.04 min | −$0.0003 / −0.11 min |

S7c vs S7b: t90 13.1 [6.7–19.1] min, **overshoot 0** [0–0.002], settle 0.977. The momentum
agents buy 47 shares net in the hour (−105 to +530). Against S2 on the same seed, t90 is +0.34 min
and overshoot +0. Ten times more trend-following money does not create an overshoot. It changes
market statistics by less than seed noise, except a small rise in clustering and in the
volume–volatility correlation, and at ×10 the momentum agents lose money.

## 5. Price impact (IMP-*)

[impact_curve.png](figures/impact_curve.png) · [impact_path.png](figures/impact_path.png)

The probe buys (or sells) Q shares from 11:00 over 5 minutes as 30 market orders. q = Q / the
seed's baseline daily volume (591,000 shares median). Baseline: C-DEF on the same seed; the null
probe is neutral (T-L6), so C-NULL was not needed.

**Noise floor** (100-share placebo IMP-0, p90 over seeds): **0.40 bps** for |I_end|, **0.57 bps** for
|I_perm|. A size is *resolved* when its median |I| ≥ 2 × the floor (0.81 / 1.15 bps).

| | q | I_end (bps) | I_peak | I_perm | shortfall (bps) | fill | resolved (I_end / I_perm) |
|---|---|---|---|---|---|---|---|
| IMP-0, 100 | 0.017% | 0.00 [−0.25–0.23] | 0.17 | +0.02 | −0.05 | 100% | — |
| IMP-0.1, 600 | 0.10% | 0.14 [−0.12–0.58] | 0.48 | −0.04 | +0.04 | 100% | no / no |
| IMP-0.5, 3,000 | 0.51% | 0.76 [0.43–1.43] | 1.03 | −0.00 | +0.32 | 100% | no (0.76 < 0.81) / no |
| IMP-1, 6,000 | 1.01% | **1.39** [0.90–2.58] | 1.97 [1.27–2.85] | −0.06 [−0.25–0.36] | 1.18 [−0.92–3.52] | 100% | **yes** / no |
| IMP-5, 30,000 | 5.07% | **4.92** [1.68–**171**] | 23.1 [6.1–166] | −0.01 | **20.0** [4.8–40.9] | 98.5% [97.3–100] | **yes** / no |
| IMP-1s, sell 6,000 | 1.01% | 1.57 [1.14–2.41] | 2.21 [1.50–3.73] | −0.03 | 1.44 [−0.24–3.70] | 100% | **yes** / no |

**Exponent (G12):** β(I_end) = **0.90**, 90% CI **0.77–1.25** (bootstrap over seeds, 2000 resamples,
seed 0; 117 resamples dropped because the 600-share median was ≤ 0) → **FAIL**. β(I_peak) = 0.99
(0.87–1.11). Impact grows roughly *linearly* with size, not as the square root. Caveat: two of the
four sizes are below 2× the noise floor. With the two resolved sizes only (1% and 5%), the slope is
ln(4.92 / 1.39) / ln 5 ≈ 0.79, still above the band.

**Recovery (G13):** I_perm / I_peak = −0.02 [−0.17 – +0.28] for IMP-1 and −0.000 [−0.04 – +0.03] for
IMP-5 → **FAIL** (ratio ≤ 0). The impact disappears completely, within about 5 minutes after the order
ends (impact_path.png). No permanent impact can exist here: the true value does not change and the
value agents pull the price back to it.

**Who takes the other side.** For the 1% buy: value agents 5,348 shares (89%), market makers 520 (9%),
noise 98, our agents 28. For the 5% buy: **market makers 17,184 (57%)**, value agents 11,732 (39%),
noise 232. The large order exhausts the value agents' willingness to sell and runs through the
market makers' ladders. On bad seeds the ask side empties (I_end up to 171 bps; 1.5% left unfilled).

**Side asymmetry.** Selling 6,000 costs slightly more than buying 6,000: I_end 1.57 vs 1.39 bps,
shortfall 1.44 vs 1.18 bps, both within each other's p10–p90. I_perm ≈ 0 for both.

**What a student's order does to the price.** An order for **1% of the day's volume** (6,000 shares,
about $6 million), executed over 5 minutes, pushes the price about **1.4 bps (14¢)** against the
trader, costs about **1.2 bps (≈ $700)** against the arrival price, and leaves no trace 10 minutes
later. An order for **5%** (30,000 shares, $30 million) moves the price about 5 bps at the end and
23 bps at the worst moment. It costs about **20 bps (≈ $60,000)**, and on an unlucky day it can
empty the book (171 bps). Anything below about 0.5% of daily volume cannot be told apart from the
market's own noise.

## 6. Pre-registered expectations

| | Expectation | Verdict |
|---|---|---|
| E1 | C-DEF fails G1, G2, G3, G4, G9, G10, G11; WARN on G6; PASS on G8; G5, G7 unknown | **Partly.** Every expected FAIL and the G8 PASS confirmed. G6 is a PASS on the median (3.02, right on the boundary, pass_share 50%), not a WARN. G5 FAIL (CS 0.04); G7 FAIL with a *negative* correlation (−0.25). |
| E2 | vol_ratio_price_value < 1 and VR(5) > 1.25 | **Confirmed**: 0.577 and 1.90, on every seed (vol ratio ≤ 0.71, VR(5) ≥ 1.61). |
| E3 | C-V20: gap std ≈ $0.2–0.3, half-life ≈ 4 min (still FAIL), activity ≈ 60% lower | **Partly**: $0.256 and 3.9 min, still FAIL, confirmed. Activity is **78%** lower in shares (65% in trades). |
| E4 | S2/S3: fast discovery (t90 within a few minutes), driven by value agents, no overshoot, few extra momentum entries; S3 not faster than S2 by more than a minute | **Partly.** Driven by value agents (they buy +8,000 shares, the MMs sell −6,500), no overshoot (0), S3 not faster (+0.56 min): confirmed. But t90 is **≈ 12 minutes**, and the jump is priced through a liquidity gap, not gradually. Momentum: every one of the 12 agents enters once (+12 entries), but with only ±5–50 shares net. |
| E5 | S4/S4n: R_peak of a few bps or less, reverting within ≈ 10–20 min; belief shifts $0.3–1.8 | **Partly.** Belief shifts $0.22–1.13 (median $0.69): confirmed. R_peak < 1 bps, but it is not a measurable response (at the divergence level, peaking 17–22 min after the news), so "reversion" does not apply. |
| E6 | S5: in_ratio rises toward the value's own increase; after_ratio ≈ 1 | **Confirmed**: 2.38 for a ×3 value increase; after_ratio 1.13 [0.89–1.28], within the seed range of 1. |
| E7 | S6: spreads widen; value agents' passive orders keep the book from emptying; recovery within one or two MM wakes | **Mostly confirmed**: mean spread 1.3 → 3.0 ticks, max 10 → 83; volume holds at 92%; but the book is one-sided 0.5% of the window's seconds (p90 3.1%); recovery within the first 5 minutes after 13:30. |
| E8 | S7a/S7b small effects; S7c overshoot stays small | **Confirmed**: Δσ_1m +0.006 / +0.053 bps; S7c overshoot 0. At ×10 the momentum agents become 3.6% of volume and lose money (−$549 together). |
| E9 | Impact absorbed mainly by value agents and MMs; I_perm ≈ 0; β unknown | **Confirmed**: value agents 89% at 1%, market makers 57% at 5%; I_perm within the noise for every size; β = 0.90 (0.77–1.25). |

## 7. What the numbers imply for R3 / R4 (observations only; the owner decides)

1. **Volatility needs two sources.** The price passes on only 58% of the value's own (already
   small) 1-minute volatility, and 80% of an extra burst. A 5–10 bps market needs a more volatile
   value process (R4) *and* endogenous volatility. Tracking the value better or worse alone stays
   near 1 bp.
2. **The value agents are the market.** They are 87% of the volume, absorb 89% of a 1% order and
   set the price after a jump. Cutting them to 20 (C-V20) loosens the pinning only a little (gap
   $0.26, half-life 3.9 min) but removes 78% of the volume, widens the spread's tail and fattens the
   tails (kurtosis 15.6). R3's replacement must bring back liquidity, not only information.
3. **Information arrives through a liquidity gap.** A +2% value jump is priced after ≈ 10 minutes,
   when one side of the book empties, with *less* volume than usual. Real markets trade more on
   news. This, and the negative volume–volatility correlation (G7 −0.25), suggests that nobody
   supplies liquidity at a *new* price: the value agents quote around their own estimate and the
   market makers around the last mid.
4. **News without value change does nothing to the price.** Our 32 agents' belief shifts
   ($0.2–1.1) are invisible next to the value agents' 87% of volume. Two news types (R4) will
   matter only if the agents that read news have weight in the market.
5. **Impact is transient and linear.** β ≈ 0.8–1.0 instead of 0.5, with no permanent part, while
   value agents can short without limit (D-R2-5). R3's budget limits are the natural point to
   re-measure (spec D-R2-5).
6. **Market makers are a backstop, not the liquidity.** Pausing them costs a wider spread for 30
   minutes and nothing else. In a 5% order, though, they take 57% of the flow.
7. **The G10 estimator cannot reach its band on one day.** A true 45–90 min half-life reads as 21–27
   min ([REALISM_LAB.md](../../engine/REALISM_LAB.md)). Worth settling before R5 calibrates
   toward 30–90 min.

## 8. Open questions

1. **G10's estimator** (above): keep it, change it (e.g. no de-meaning, pooled seeds), or move the band?
2. **Settle at 97.6%** of a value jump on every seed: the value agents' mean-reversion toward r̄
   (κ = 1.67e-15/ns in their own model) is the suspect. Is that intended for "information" news?
3. **G6 sits on its boundary** (median 3.02, pass_share 50%). A grade that flips with the seed set
   is weak evidence either way.
4. **Negative vv_corr** (−0.25): worth a mechanism check before R3, since R3 changes the volume source.
5. **Spec errata found while building:** the seed list repeats 7 (§5.0; the lab uses 19 instead);
   a +2% jump decays 0.3% (not 0.0003%) over 5 hours (§6.1). See DECISIONS.md.

---

*Note on engine versions.* `api.jobs.engine_version()` appends "+dirty" whenever a tracked file
has uncommitted changes. During all campaigns the owner's tracked `sim_data.pkl` was modified in
the working tree (not by R2), so every version carries "+dirty" even where the code was committed.
Each campaign also ran before its own milestone's code was committed (the version names the previous milestone's commit). The default-market
code was identical throughout (I8, regression hash).

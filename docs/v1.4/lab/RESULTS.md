# R3 results (spec v1.4) — in progress

Sections 1–9 of spec v1.4 §12.3 are filled in milestone by milestone. Until N7 this file holds
the interim pieces.

## Measurement: the corrected half-life of the v1.3 markets (N1)

Corrected gap half-life of the stored v1.3 runs (no new simulations), 2026-10-12.
Seeds: api.lab.SEEDS (20). Values in minutes: median [p10–p90] over seeds.

| config | seeds | v1.3 estimator (biased for slow mispricing) | h_read (no de-meaning) | correction of median h_read | median of per-seed h_corrected | range of the median reading | gap mean ($) | engine |
|---|---|---|---|---|---|---|---|---|
| C-DEF | 20 | 1.5 [1.3–2.0] | 1.7 [1.4–2.9] | 1.6 min | 1.6 (0 seeds >240; finite p10–p90 1.4–2.8) | — | 0.014 | v1.2-a72d6cf+dirty |
| C-V20 | 20 | 3.8 [2.4–4.8] | 4.0 [2.4–5.4] | 4.0 min | 4.0 (0 seeds >240; finite p10–p90 2.4–5.5) | 5–5 | 0.023 | v1.2-a72d6cf+dirty |

v1.3 runs: `runs/_lab` (engine v1.2-a72d6cf+dirty, the stored v1.3 campaign). Recomputed by
`scripts/halflife_v13_recompute.py` with no new simulations, so the correction changes nothing
here. The v1.3 markets' mispricings are short (1.5–4 min), in the part of the table where
the estimator is nearly unbiased. The v1.3 G10 FAIL (far below 30 min) stands with the
corrected ruler. The v1.3 bias concerned slow mispricings, which these markets do not have.

## 2. Budget alone: C-BL vs C-DEF (N2, interim)

The full tables are in [CAMPAIGN_b.md](CAMPAIGN_b.md) (generated from `summary_b.json`).
- C-BL and S2-BL: 20 seeds (api.lab.SEEDS), engine v1.3-ce7beae, 2026-10-12.
- C-DEF and S2: the stored v1.3 runs. The budget-off market is bit-identical (I8).
- Campaign: 40 runs, 0 failed, zero_sum = 0 in every run, 5.0 min with 4 workers
  (median 26 s per run).

- **Scorecard: unchanged in grade.** Every v1.3 band keeps its grade (G6 and G8 PASS, the rest
  FAIL), and the medians move little: ac1 0.374 → 0.365, VR(5) 1.90 → 1.92, σ_1m 0.71 → 0.70
  bps, gap std $0.145 → $0.157. vv_corr is less negative (−0.25 → −0.18) but still fails.
- **Volume falls 28%:** 591,360 → 424,077 shares/day (median), still above L2's 295,500.
- **Who is limited.** NoiseAgents: about 62 orders clipped per run (orders above about 200
  shares) and none blocked. ValueAgents: about 4,080 clipped and 2,160 blocked per run (22 per
  agent).
- **When.** The ValueAgent blocks are spread over the whole day and rise only mildly
  (112 in the first half-hour, 201 in the last). In S2-BL they rise after the jump
  (≈200 → 370 per half-hour), as value agents run into the limit chasing the new value.
- **Jump (S2-BL vs S2).** The budget slows pricing slightly: t50 10.4 → 11.3 min, t90 11.8 →
  13.0 min. Volume uplift is lower (0.75 → 0.66). The spread in the jump window is wider
  (p95 30 → 37.5 ticks, max 190 → 276). The book is never literally one-sided on the 1 s grid
  (one_sided_share_jump median 0 in both); the "emptied book" of R2 shows up as a wide
  spread, not an empty side.

**E1 verdict (interim).** Small effects on the scorecard: yes. Noise orders clipped: yes.
Value agents block often: yes. "Late in the day": only mildly; the blocks are nearly uniform
through the day. Not anticipated: the 28% volume loss.

## 3. The design sweep, round 1 (N4, interim; full tables in [RESULTS_s1.md](RESULTS_s1.md))

Campaign s1:
- 16 designs × {no trigger, S2} × seeds 42, 7, 1, 2, 3 = 160 runs, on engine v1.3-344fcbf,
  2026-10-12.
- 0 failed; 5/5 seeds in every config; zero_sum = 0 in every run.
- 80 min with 2 workers (the 120-agent runs use about 1 GB each).

**Selection result: no design passes the limits, so the §7.4 rule names no winner.**
- Step 1 rejects all 16 designs: 14 on L1 (median spread 3–5 ticks, p95 up to 19), 7 on L2
  (volume below 295,500 at $500k wealth), some on both.
- The two designs that miss only one limit:
  - D-60fl2M fails L1 on the median alone (3 ticks; p95 = 10 passes) and has 5/7 targets;
  - D-120fl500k fails L2 alone (266,907 shares) and has 4/7 targets.
- D-60fl500k fails only L2 (146,245) and has 5/7 targets.
- L5 passes everywhere: 34–76 s median. The single-run probe of D-120fl2M took 101 s.

**Across designs:**
- **T4, T5 and T7 pass in all 16 designs.** vv_corr is +0.32 to +0.66 (it was −0.25), the
  volume uplift after the jump is 2.3–5.3× (it was 0.75), and informed P&L is positive in
  total and per agent.
- **T3 fails in all 16.** The price/value volatility ratio is 0.45–0.74 (it was 0.58).
- **T6 fails in all 16.** The book is never one-sided on the 1 s grid, but the spread p95 in
  the 30 minutes after the jump is 92–516 ticks.
- **T1 and T2 pass only with fast, low-noise research** (D-60fl*: ac1 −0.04/−0.05, VR(5)
  1.18/1.19). The N = 120 fl designs pass T1 but miss T2 (VR(5) 1.30/1.40). Slow or noisy
  research gives negative autocorrelation (ac1 −0.19 to −0.40) and VR(5) 0.29–0.63, which is
  overshooting and mean reversion rather than book-creep.

The main effects (median change over the 8 matched pairs) are tabulated in RESULTS_s1.md.
- Slower or noisier research makes ac1 more negative and lowers VR(5); it raises the spread
  in the jump window and the gap half-life.
- More wealth raises volume (+398k shares) but also the median spread.
- More agents raise volume (+192k) and wall time (+36 s).

**What the spec does not cover.** §7.4 round 2 is defined from a round-1 winner, and §2.4
from "the best design by the selection rule". Neither exists when step 1 rejects every
design. Per the owner's instruction, I stop here after N4: the owner decides how to proceed.
The selection itself is mechanical and has not been changed.

## 3b. Spec v1.4.1: corrected limits and learning from prices (N4a–N4c, interim)

Full tables, selection printouts and E11–E15 verdicts: [RESULTS_s2.md](RESULTS_s2.md).
- Under the bps limits and L6, all 8 round-1 designs at $2M pass every limit.
- Learning from prices (campaign s2, 240 runs, plus a 50-run refinement) did not fix T3 or
  T6, and it slowed jump pricing: learning makes researched agents follow the stale price.
- The mechanical selection ends at D-60fl2M (no learning): 5/7 targets, T3 and T6 fail.
  Per §3.5 the work STOPPED for the owner.

## 4–6. Step-down and final campaigns (N5, interim; full tables in [RESULTS_n5.md](RESULTS_n5.md))

Campaign setup (spec v1.4.2 Part 2):
- Design D-60fl2M, learning off, budget on.
- Engine v1.3-c1dfa51, 2026-10-13/14.
- 245 runs, all valid; zero_sum = 0 in every run.
- P97/50/20 use 10 seeds (they show the trend and decide nothing); P0 and the final campaign
  use 20 seeds.

**R3 confirmed on P0 (20 seeds).**
- PASS: T1 (ac1 −0.005), T2 (VR(5) 1.2488, inside the 1.25 limit by 0.001; 10 of 20 seeds
  are above 1.25), T4 (vv_corr +0.53), T5 (volume uplift 2.54 / 2.58), T7 (informed P&L
  total +$1,023, median +$112) and L1–L6.
- L3 part 2: without market makers there are 19.6–23.3k executions per day on 5 seeds.
- FAIL, as in screening: T3 (1-min vol ratio 0.49) and T6 (spread_jump_ratio 14.8 / 16.0;
  the book never empties).

**Step-down 97 → 0 ValueAgents.** T1 and T2 improve monotonically: ac1 0.29 → 0.17 → 0.04 →
−0.005, VR(5) 2.0 → 1.59 → 1.36 → 1.25. The jump is priced within about 5–6 min at every
step (v1.3: about 12 min); see `figures/jump_response_r3.png`. While ValueAgents remain, the
informed agents lose money to them (P97: −$12,418, ValueAgents +$12,340 per run). Only at
P0 do they earn their information.

**Impact on P0.**
- β = 0.94 [0.81–1.12], over sizes 0.5/1/5 only (the trim dropped IMP-0.1). G12 FAIL, as in
  v1.3 (0.90).
- Recovery I_perm/I_peak = 0.23, so G13 PASS (v1.3 −0.02 FAIL). A permanent impact of about
  0.3 bps after a 1% probe now appears: informed agents move their beliefs with the order
  flow.
- Buy vs sell (6,000 shares): I_end 0.56 vs 0.89 bps, shortfall 0.72 vs 1.14 bps. Selling is
  dearer, an asymmetry that v1.3 did not have.

**News +0.9 (S4).** A fast overreaction and reversal: peak +5.5 bps at 0.27 min, half
reverted in 1.1 min. In v1.3 the response was +0.9 bps at 22 min.

**Run-flag finding (new K16).** In 13 of the 100 P-step and P0 jump runs, the lab flag
`informed_bounds` fails. 1–3 fills by 1–2 informed agents end up beyond the §4.5 leverage
bounds, at most 1.507× and −0.509× of wealth, always right after the jump. Diagnostic:
`scripts/diag_informed_bounds.py`. Two mechanisms, both inherent to §4.5 as written:
- The rule is checked at the order's limit price, but a borrowing (or short) agent fills at
  better prices, which leaves it slightly more leveraged.
- Fills of the previous cycle's orders whose cancellation is still in flight; §4.5 assumes
  those orders are already gone.

Quiet markets are within ±1 share (T-N5 / I4 pass). No code change was made; the owner
decides.

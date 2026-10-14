# R3 results: informed fundamentalists replace the value agents (spec v1.4, v1.4.1, v1.4.2)

Detailed reports:
- [CAMPAIGN_b.md](CAMPAIGN_b.md): budget alone;
- [RESULTS_s1.md](RESULTS_s1.md): design sweep, round 1;
- [RESULTS_s2.md](RESULTS_s2.md): corrected limits and learning from prices;
- [RESULTS_n5.md](RESULTS_n5.md): step-down and final campaigns.

Unless stated otherwise, every number is a median over seeds, with the config, seed count and
engine given in the section. Final market P0: 20 lab seeds (api.lab.SEEDS), engine
v1.3-c1dfa51 (the N5 engine, which includes the bit-identical N4d speed-up), 2026-10-13/14.

## 1. The final market in one paragraph, and whether R3 succeeded

**P0** has no ValueAgents and 60 informed fundamentalists. They follow design D-60fl2M:
research every log-U[60, 300] s, with noise log-U[10, 50]¢, $2M each, and learning from prices
off. The rest of the market is 12 momentum EKF agents, 1000 noise agents, 2 market makers and
a gross budget L = 2 on the stock agents.

P0 has unpredictable 1-minute returns (ac1 −0.005, VR(5) 1.25) and a positive
volume–volatility relation (+0.53). It prices a ±2% value jump in about 5½ minutes (t90 5.6 /
5.1 min; v1.3: 11.8 / 12.9), with 2.5× the volume. Its informed traders earn their information
(+$1,023 per run in total, +$112 median per agent). Spreads are 0.30 bps median and 1.0 bps
p95, and 522,000 shares trade per day. A full day takes 26 s.

The price is still too smooth minute by minute (1-min volatility ratio 0.49; 0.62 bps per
minute). After a jump the spread widens to 15–16× its baseline while informed traders disagree.

**R3 closes per spec v1.4.2 Part 3:** T1, T2, T4, T5, T7 and L1–L6 pass on 20 seeds. T3 and
T6 are reported and carried into R4 as K14 and K15.

| item | measure | P0, 20 seeds | threshold | result | v1.3 C-DEF |
|---|---|---|---|---|---|
| T1 | \|ac1\| of 1-min returns | 0.005 | ≤ 0.10 | **PASS** | 0.374 |
| T2 | VR(5) | 1.2488 (10 of 20 seeds above 1.25) | 0.80–1.25 | **PASS** (by 0.001) | 1.90 |
| T3 | price vol / value vol, 1 min | 0.493 | ≥ 0.90 | **FAIL** (K14) | 0.577 |
| T4 | volume–volatility Spearman | +0.528 | > 0 | **PASS** | −0.252 |
| T5 | volume uplift after ±2% jump | 2.54 / 2.58 | > 1 (both) | **PASS** | 0.75 / 0.76 |
| T6 | one-sided share / spread_jump_ratio after ±2% | 0 / 14.8, 0 / 16.0 | ≤ 1% and ≤ 3 | **FAIL** (K15) | 0 / 11.4, 0 / 9.2 |
| T7 | informed P&L vs hold, total / median | +$1,023 / +$112 | > 0 | **PASS** | −$112 / −$2.92 (price-only) |
| L1 | spread median / p95 | 0.30 / 1.00 bps | ≤ 2.5 / ≤ 10 bps | **PASS** | 0.10 / 0.30 |
| L2 | shares per day | 522,042 | ≥ 295,500 | **PASS** | 591,360 |
| L3 | trades all day; trades without market makers | every half-hour; 19.6–23.3k executions per day (5 seeds) | yes / > 0 | **PASS** | — |
| L4 | zero_sum = 0 in every run; invariants | 0 in all 2,000+ v1.4 runs; I1–I9 + I8-legacy pass | — | **PASS** | — |
| L5 | median wall time per full day | 27.2 s (lab, 2 workers) | ≤ 90 s | **PASS** | 25 s |
| L6 | max \|mid − value\| over the day | $0.78 | ≤ $10 | **PASS** | $0.59 |

## 2. Budget alone (C-BL vs C-DEF; campaign b, 20 seeds, engine v1.3-ce7beae, 2026-10-12)

- **Grades.** No v1.3 band changes grade. ac1 0.374 → 0.365, VR(5) 1.90 → 1.92, vv_corr
  −0.25 → −0.18.
- **Volume** falls 28% (591,360 → 424,077 shares per day).
- **Who is limited.**
  - NoiseAgents: about 62 orders clipped per run (above about 200 shares), none blocked.
  - ValueAgents: about 4,080 clipped and 2,160 blocked per run (22 per agent), nearly uniform
    through the day and rising after a jump.
- **Jump.** Pricing is slightly slower (t90 11.8 → 13.0 min), and the window spread is wider
  (p95 30 → 37.5 ticks).
- **E1 verdict.** Small effects on the scorecard, noise clipped, value agents block often: yes.
  "Late in the day": only mildly. Not anticipated: the 28% volume loss.

## 3. The design sweep (s1, s2, refinement; seeds 42, 7, 1, 2, 3)

**Round 1 (16 designs, 160 runs, engine v1.3-344fcbf).** Results:
- T4, T5 and T7 pass in every design.
- T1 and T2 pass with fast, precise research.
- T3 and T6 fail everywhere.
- Under the v1.4 tick limits, no design passed L1/L2, so the rule named no winner.

Spec v1.4.1 corrected L1/G8 to bps of the mid and T6 to a ratio against the baseline (both
spec unit errors), and added L6. With those, the 8 designs at $2M pass every limit; the rule
picks D-60fl2M (5/7).

**Learning from prices (s2: 16 designs × C/S2/S2n, 240 runs, engine v1.3-0d20335; refinement:
50 runs).** It did not fix T3 or T6, and it slowed jump pricing (off → mod/strong: t90 +5.8 /
+16.1 min). The rule is symmetric: researched agents follow the stale price. On quiet days it
never triggers. It is kept with default "off" as a documented negative result (D-R3-9).

**Selection.** The rule over 32 candidates picks D-60fl2M (off). In the refinement round:
- N = 30 fails L2.
- N = 240 fails L5 (186 s).
- W = $5M ties on targets and loses the tie-break by 0.002.

D-60fl2M stays the selection; the owner fixed it as the R3 design (D-R3-7). The full tables
and printouts are in RESULTS_s1.md and RESULTS_s2.md.

**What each dial does (round 1, median over 8 matched pairs):**
- **Slower research** (T_r 60–300 → 300–1800 s): ac1 −0.17, VR(5) −0.37, t90 +14 to +22 min;
  the gap half-life rises from about 5 to about 10 min at low noise (23 → 40 min at high noise).
- **Noisier research** (σ_r 10–50 → 50–200¢): ac1 −0.14, VR(5) −0.51; the half-life rises from
  about 5 to about 23 min (fast research) or from 10 to 40 min (slow).
- **More wealth** ($0.5M → $2M): +398k shares per day and a wider spread.
- **More agents** (60 → 120): +192k shares and +36 s per day.

## 4. Step-down 97 → 50 → 20 → 0 ValueAgents (P97/50/20: 10 seeds; P0: 20 seeds)

The 10-seed medians are about 1.4× noisier; they show the trend and decide nothing.

| measure | v1.3 C-DEF | P97 (10) | P50 (10) | P20 (10) | P0 (20) |
|---|---|---|---|---|---|
| ac1 | 0.374 | 0.286 | 0.170 | 0.044 | −0.005 |
| VR(5) | 1.90 | 2.00 | 1.59 | 1.36 | 1.25 |
| vol ratio 1 min | 0.577 | 0.449 | 0.454 | 0.488 | 0.493 |
| vv_corr | −0.252 | 0.429 | 0.479 | 0.515 | 0.528 |
| volume uplift S2 | 0.75 | 1.63 | 1.91 | 2.18 | 2.54 |
| spread_jump_ratio S2 | 11.4 | 24.5 | 21.3 | 25.7 | 14.8 |
| informed P&L total ($) | −112 (price-only) | −12,418 | −6,946 | −2,877 | +1,023 |
| ValueAgent share of volume | 87% | 42% | 28% | 13% | — |
| shares per day | 591k | 933k | 704k | 598k | 522k |
| t90 S2 (min) | 11.8 | 4.9 | 4.7 | 5.2 | 5.6 |

Every step with informed agents prices a jump in about 5 min (`figures/jump_response_r3.png`).
While ValueAgents remain, they take money from the informed agents (P97: ValueAgents
+$12,340, informed −$12,418 per run). Figures: `figures/stepdown_lines.png` (seed counts in
the legend) and `figures/r3_scorecard.png`.

## 5. The final market P0 (20 seeds)

**v1.3 scorecard:**

| band | median | grade |
|---|---|---|
| G1 1-min volatility | 0.62 bps | FAIL (expected, E7) |
| G2 daily volatility | 0.20% | FAIL |
| G3 \|ac1\| | 0.005 | PASS |
| G4 VR(5) | 1.25 | PASS |
| G5 clustering | CS 0.087, PS 0.032 | WARN (v1.3: FAIL) |
| G6 excess kurtosis | 1.47 | WARN (v1.3: PASS) |
| G7 volume–volatility | +0.53 | PASS |
| G8 spread | 0.30 / 1.00 bps | PASS |
| G9 gap std | $0.197 | FAIL |
| G10 half-life (corrected) | 3.6 min | FAIL |
| G11 regime contrast | 2.47 | FAIL |
| G12 impact β | 0.94 | FAIL |
| G13 impact recovery | 0.23 | PASS (v1.3: FAIL) |

The R3 scorecard is in section 1.

**Diagnostics:**
- gap std $0.197 [0.179–0.218];
- corrected gap half-life 3.6 min [3.0–5.6], range 2–5 min (uncorrected reading 3.6 min; the
  v1.3 estimator reads alike at this short half-life);
- gap mean −$0.012;
- corr(mid, value) 0.963;
- price/value volatility ratio by horizon 0.49 / 0.57 / 0.75 / 0.84 / 0.90 at 1 / 5 / 15 /
  30 / 60 min;
- VR(30) 2.17;
- u_ratio 1.14.

**Per class (P&L vs holding, total per run, median; share of volume):**
- informed fundamentalists +$1,023 (88.1% of volume);
- noise agents −$885 (7.5%);
- market makers −$107 [−2,582 – +1,977] (4.2%);
- momentum EKF +$13 (0.03%).

## 6. Jumps, news, impact on P0 vs v1.3 (20 seeds)

| | P0 | v1.3 |
|---|---|---|
| +2% jump: t50 / t90 / settle | 2.6 / 5.6 min / 0.992 | 10.4 / 11.8 min / 0.976 |
| −2% jump: t50 / t90 / settle | 2.9 / 5.1 min / 0.993 | 11.2 / 12.9 min / 0.977 |
| volume uplift, 30 min | 2.54 / 2.58 | 0.75 / 0.76 |
| informed agents updated at +5 / +10 min (S2) | 33% / 86% | — |
| spread p95 in the window (ticks) / spread_jump_ratio | 148 / 14.8 | 30 / 11.4 |
| news +0.9: R_peak, t_peak, half-reversal | +5.5 bps, 0.27 min, 1.1 min | +0.9 bps, 22 min, 23 min |
| impact β (sizes 0.5/1/5) | 0.94 [0.81–1.12] | 0.90 [0.77–1.25] |
| IMP-1: I_end / I_peak / I_perm (bps) | 0.56 / 1.22 / 0.29 | 1.39 / — / −0.06 |
| recovery I_perm/I_peak | 0.23 | −0.02 |
| buy vs sell 6,000 sh: I_end, shortfall | 0.56 vs 0.89 bps; 0.72 vs 1.14 bps | 1.39 vs 1.57 bps |
| who absorbs a 1% buy | informed 5,498, MMs 436, noise 89 shares | value agents and MMs |

The settle values near 1 reflect that the ValueAgents' κ mismatch (§0.3) is gone. The volatility
burst (S5) was dropped by the trim (D-R3-11).

## 7. Expectations E1–E15

| | expectation | verdict |
|---|---|---|
| E1 | budget: small scorecard effect, noise clipped, value agents block late | mostly: small effects and clipping yes; blocks nearly uniform; volume −28% not anticipated |
| E2 | at P0 \|ac1\| < 0.15 and VR(5) < 1.4 for most designs; T3 toward 1 | partly: true for fast/precise research (fl designs, N = 60); slow or noisy research overshoots (ac1 −0.19 to −0.43, VR(5) 0.29–0.63); T3 did not rise (0.45–0.74) |
| E3 | vv_corr turns positive | **met** in every design (+0.32 to +0.66); P0 +0.53 |
| E4 | volume rises after a jump; the book does not empty; t90 set by research speed | met for volume (2.5×) and "never empty" (one-sided 0); the spread widens 15×, so T6 fails; t90 fast/precise designs about 5–6 min, slow or noisy 11–38 min (RESULTS_s1.md): met |
| E5 | gap std and half-life grow with slower and noisier research | **met** (fl $0.20 / 5 min, sh $0.54 / 40 min; RESULTS_s1.md) |
| E6 | informed profit, noise lose, MMs about even | **met** at P0 (+$1,023, −$885, −$107); not while ValueAgents remain |
| E7 | G1 still fails; G5, G11 still fail | G1 FAIL (0.62 bps) and G11 FAIL as expected; G5 improved to WARN |
| E8 | every T-measure improves monotonically 97 → 0 | T1, T2, T4, T5, T7 monotone; T3 nearly flat (0.45 → 0.49); T6 not monotone (24.5, 21.3, 25.7, 14.8) |
| E9 | permanent impact only where beliefs change; I_perm near 0 | not met: I_perm about 0.3 bps (recovery 0.23); informed agents read the probe's flow as information |
| E10 | wall time about 0.2 s per informed agent per day | not met: before N4d about 0.6 s per agent (60 → 120 agents: +36 s at 2 workers; 240: 186 s); after N4d a P0 day is 26 s, and 200 agents take 94 s |
| E11–E15 | learning from prices | not met (see RESULTS_s2.md §6): no faster updating, T6 not fixed, no long-horizon improvement, no herding observed, slow designs got slower |

## 8. What remains for R4 (observations only; the owner decides)

- **K14 (T3), price too smooth at 1–5 min.** Value news reaches the price only through research
  readings every 1–5 min per agent, and the oracle's own 1-min moves are small. Needed:
  short-horizon variation not driven by research arrivals (R4 endogenous volatility, a livelier
  value process).
- **K15 (T6), the spread widens 15× after a value jump.** The book does not empty, but informed
  quotes split into an old-belief cluster and a new-belief cluster. Needed: liquidity that stays
  tight while informed traders disagree (R4 market makers: inventory, quoting around the last
  trade under stress).
- **K16, informed budget slightly exceeded right after jumps** (≤ 0.9 percentage points of
  wealth beyond the bound). Options: check the rule at the worst fill price, or count orders
  whose cancellation is still in flight.
- **Learning from prices:** a one-directional variant (no learning for an agent with fresh
  research) is an R4 candidate (D-R3-9).
- **Still failing:** G1/G2 (volatility), G9/G10 (mispricing size and life), G11 (regimes).
  G12 impact is linear (β 0.94).
- **Engine speed:** after N4d no single hotspot remains; order deepcopies (about 15%) and
  debug-log formatting (about 8%) lead.

## 9. Open questions

1. **T2 margin.** T2 passes by 0.001 (VR(5) 1.2488) with 10 of 20 seeds above 1.25. Should R4
   track VR(5) as at risk?
2. **K16.** Is a ≤ 0.9 pp leverage excess after jumps acceptable for R6 user trading, or should
   §4.5 be tightened (worst fill price, in-flight orders)? Any change alters the market and
   needs an I8 re-record.
3. **IMP-0.1.** The trim dropped IMP-0.1, so β rests on three sizes. Re-add it for R5
   calibration?
4. **Git history.** The two files committed by accident in 9e6b063 are untracked but remain
   in history (owner decision).

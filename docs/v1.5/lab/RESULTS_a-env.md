# A3.7 living_v1 alone (P0 + living_v1, normal day, auto news)

Spec v1.5; engine `v1.4-e1c9714`; seeds [42, 7, 1, 2, 3, 4, 5, 6, 8, 9] (10); date 2026-10-16. Medians over seeds; jump rows are treated (S2, +2% value jump at 11:00) minus the same seed's C.

## Completeness

| config | valid seeds | zero_sum ≠ 0 | flags failing | wall time median (s) | errors |
|---|---|---|---|---|---|
| P0-C | 10/10 | 0 | 0 | 14.7 |  |
| P0-S2 | 10/10 | 0 | 1 | 16.2 |  |
| A-ENV-C | 10/10 | 0 | 0 | 15.7 |  |
| A-ENV-S2 | 10/10 | 0 | 2 | 16.6 |  |

## Measures vs P0

| measure | P0 (v1.4) | a-env |
|---|---|---|
| G1 sigma 1 min (bps) | 0.62 | 5.04 |
| day realised vol (%) | 0.122 | 0.994 |
| T1 ac1 | -0.0202 | 0.0141 |
| T2 VR(5) | 1.239 | 1.219 |
| T3 vol ratio 1 min | 0.493 | 0.802 |
| vol ratio 5 min | 0.562 | 0.866 |
| vol ratio 15 min | 0.731 | 0.936 |
| vol ratio 60 min | 0.882 | 0.975 |
| T4 vv_corr | 0.528 | 0.735 |
| G5 clustering CS | 0.0872 | 0.0532 |
| G5 PS | 0.0196 | 0.000262 |
| G6 excess kurtosis | 1.5 | 14.7 |
| U-shape u_ratio | 1.14 | 1.17 |
| spread median (bps) | 0.3 | 0.803 |
| spread p95 (bps) | 1 | 4.4 |
| shares per day | 515,420 | 1,187,124 |
| max |mid - value| ($) | 0.79 | 4.93 |
| regime contrast (per day) | 2.38 | 3.44 |
| retail share (%) | 0 | 0 |
| MM share (%) | 4.15 | 6.11 |
| MM max |inventory| (sh) | 1,190 | 5,994 |
| T7 informed P&L total ($) | 1,460 | 37,076 |
| T7 informed P&L median ($) | 112 | 416 |
| MM group P&L ($) | 173 | -28,819 |
| noise P&L total ($) | -1,337 | -10,109 |
| retail P&L total ($) | — | — |
| info news f_10 (median) | — | 1.03 |
| info news volume uplift | — | 1.44 |
| T5 volume uplift (S2) | 2.48 | 1.08 |
| T6 spread_jump_ratio (S2) | 11.7 | 1.91 |
| T6 one-sided share (S2) | 0 | 0 |
| t90 of the jump (min) | 5.05 | 2.53 |
| wall time (s) | 14.7 | 15.7 |

## v1.3 scorecard grades (median over the 10 seeds; G2 from the cross-seed sd of day returns)

| grade | P0 (v1.4) | a-env |
|---|---|---|
| G1 | FAIL | PASS |
| G2 | FAIL | PASS |
| G3 | PASS | PASS |
| G4 | PASS | PASS |
| G5 | WARN | WARN |
| G6 | WARN | PASS |
| G7 | PASS | PASS |
| G8 | PASS | PASS |
| G9 | FAIL | WARN |
| G10 | FAIL | FAIL |
| G11 | FAIL | WARN |

## Notes (A3, 2026-10-16)

- **Flags:** the only failing flag is `informed_bounds` in 3 jump runs (A-ENV-S2 seeds 2 and 8, P0-S2 seed 7). This is the known K16: the informed budget is exceeded right after a jump, and the fix is milestone A6. zero_sum = 0 in all 40 runs.
- **E-A1** (pre-registered: living_v1 alone gives σ_1m ≈ 3 bps, price smoother than value at ratio ≈ 0.5) is **not confirmed, in the better direction**: σ_1m = 5.04 bps and the 1-min vol ratio = 0.80.
  - With a faster value, informed research readings move the price more per arrival, and 3 information jumps a day add short-horizon moves.
  - Kurtosis rises to 14.7 (jumps and stress).
- **Market makers:** the ABIDES market makers lose a median $28.8k a day (P0: +$173), while informed traders gain $37k: the stock market makers are run over on the faster value.
  - Their max |inventory| rises from 1,190 to 5,994 shares.
  - This is what A5's market makers (volatility-scaled spread, inventory skew and limits) address.
- **Jump response (S2):** the spread_jump_ratio falls from 11.7 to 1.91 and t90 from 5.1 to 2.5 min, because the C baseline itself is busier (spread p95 4.4 bps instead of 1.0). The volume uplift falls to 1.08 for the same reason (C volume ×2.3).
- **Information news:** median f_10 = 1.03, i.e. the jump is fully priced within 10 minutes (research every 1–5 min); volume uplift 1.44.
- Graded in the sweep and confirmation (A7–A8), not here; this campaign measures the component alone.

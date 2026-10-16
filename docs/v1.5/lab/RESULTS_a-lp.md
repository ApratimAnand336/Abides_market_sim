# A5.5 our market makers alone (P0 with 2 LPs of $5M instead of the ABIDES MMs)

Spec v1.5; engine `v1.4-11c2ed0`; seeds [42, 7, 1, 2, 3, 4, 5, 6, 8, 9] (10); date 2026-10-16. Medians over seeds; jump rows are treated (S2, +2% value jump at 11:00) minus the same seed's C.

## Completeness

| config | valid seeds | zero_sum ≠ 0 | flags failing | wall time median (s) | errors |
|---|---|---|---|---|---|
| P0-C | 10/10 | 0 | 0 | 14.9 |  |
| P0-S2 | 10/10 | 0 | 1 | 15.5 |  |
| A-LP-C | 10/10 | 0 | 0 | 15.2 |  |
| A-LP-S2 | 10/10 | 0 | 1 | 15.7 |  |

## Measures vs P0

| measure | P0 (v1.4) | a-lp |
|---|---|---|
| G1 sigma 1 min (bps) | 0.62 | 0.497 |
| day realised vol (%) | 0.122 | 0.098 |
| T1 ac1 | -0.0202 | 0.159 |
| T2 VR(5) | 1.239 | 1.666 |
| T3 vol ratio 1 min | 0.493 | 0.402 |
| vol ratio 5 min | 0.562 | 0.533 |
| vol ratio 15 min | 0.731 | 0.721 |
| vol ratio 60 min | 0.882 | 0.876 |
| T4 vv_corr | 0.528 | 0.572 |
| G5 clustering CS | 0.0872 | 0.12 |
| G5 PS | 0.0196 | 0.0366 |
| G6 excess kurtosis | 1.5 | 1.32 |
| U-shape u_ratio | 1.14 | 1.12 |
| spread median (bps) | 0.3 | 0.2 |
| spread p95 (bps) | 1 | 0.5 |
| shares per day | 515,420 | 573,294 |
| max |mid - value| ($) | 0.79 | 0.735 |
| regime contrast (per day) | 2.38 | 2.54 |
| retail share (%) | 0 | 0 |
| MM share (%) | 4.15 | 17.7 |
| MM max |inventory| (sh) | 1,190 | 1,572 |
| T7 informed P&L total ($) | 1,460 | 4,954 |
| T7 informed P&L median ($) | 112 | 139 |
| MM group P&L ($) | 173 | -4,438 |
| noise P&L total ($) | -1,337 | -1,064 |
| retail P&L total ($) | — | — |
| info news f_10 (median) | — | — |
| info news volume uplift | — | — |
| T5 volume uplift (S2) | 2.48 | 1.86 |
| T6 spread_jump_ratio (S2) | 11.7 | 18.7 |
| T6 one-sided share (S2) | 0 | 0 |
| t90 of the jump (min) | 5.05 | 3.72 |
| wall time (s) | 14.9 | 15.2 |

## v1.3 scorecard grades (median over the 10 seeds; G2 from the cross-seed sd of day returns)

| grade | P0 (v1.4) | a-lp |
|---|---|---|
| G1 | FAIL | FAIL |
| G2 | FAIL | FAIL |
| G3 | PASS | WARN |
| G4 | PASS | FAIL |
| G5 | WARN | PASS |
| G6 | WARN | WARN |
| G7 | PASS | PASS |
| G8 | PASS | PASS |
| G9 | FAIL | FAIL |
| G10 | FAIL | FAIL |
| G11 | FAIL | FAIL |

## Notes (A5, 2026-10-16)

- **Flags:** only `informed_bounds` (K16, fixed in A6) in 2 jump runs (P0-S2 seed 7, A-LP-S2 seed 8). zero_sum = 0 in all 40 runs.
- **E-A3** (pre-registered: LPs alone cut the post-jump spread ratio below 5) is **not confirmed**: the ratio is 18.7 vs P0's 11.7.
  - The numerator does fall: the p95 spread in [11:00, 11:30] after the jump is 8.4 bps vs 10.7 (−21%), and the p95 jump-window spread in ticks 85.5 vs 108.5.
  - The denominator falls more: the same window on the calm baseline is 0.45 bps vs 1.0, because the LPs quote tighter than the ABIDES MMs on calm days (day median 0.2 vs 0.3 bps, p95 0.5 vs 1.0).
  - The book still empties briefly after the jump (max spread in the window 1,014 ticks vs 1,246); t90 of the jump is shorter (3.7 vs 5.1 min).
  - The ratio as defined (T6, spec v1.4.1) rewards a wide baseline; that is a property of the measure, reported, not changed.
- **LP P&L:** the two LPs lose $4,438 a day (group median; ABIDES MMs in P0 gain $173) while informed traders gain $4,954 in total (P0: $1,460). With 17.7% of volume (P0 MMs 4.15%) the LPs are the informed traders' main counterparty and are adversely selected on a calm day. E-A6 (MMs earn a small positive P&L) is judged on the combined market in A8.
- **Price path:** ac1 0.159 and VR(5) 1.67 (P0 −0.020, 1.24): with tighter quotes that requote lazily, mid moves in more persistent small steps (G4 FAIL, G3 WARN). σ1m falls to 0.50 bps (P0 0.62). Clustering CS rises to 0.12 (G5 PASS).
- Wall time 15.2 s per day (E-A8 limit 40 s).

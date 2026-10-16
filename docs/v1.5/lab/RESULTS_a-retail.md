# A4.5 retail crowd alone (P0 with the crowd instead of NoiseAgents, N_r 500, kappa_v 1)

Spec v1.5; engine `v1.4-dcfb205`; seeds [42, 7, 1, 2, 3, 4, 5, 6, 8, 9] (10); date 2026-10-16. Medians over seeds; jump rows are treated (S2, +2% value jump at 11:00) minus the same seed's C.

## Completeness

| config | valid seeds | zero_sum ≠ 0 | flags failing | wall time median (s) | errors |
|---|---|---|---|---|---|
| P0-C | 10/10 | 0 | 0 | 14.5 |  |
| P0-S2 | 10/10 | 0 | 1 | 15.6 |  |
| A-RET-C | 10/10 | 0 | 0 | 16.7 |  |
| A-RET-S2 | 10/10 | 0 | 2 | 20.9 |  |

## Measures vs P0

| measure | P0 (v1.4) | a-retail |
|---|---|---|
| G1 sigma 1 min (bps) | 0.62 | 0.622 |
| day realised vol (%) | 0.122 | 0.123 |
| T1 ac1 | -0.0202 | 0.0097 |
| T2 VR(5) | 1.239 | 1.278 |
| T3 vol ratio 1 min | 0.493 | 0.49 |
| vol ratio 5 min | 0.562 | 0.569 |
| vol ratio 15 min | 0.731 | 0.742 |
| vol ratio 60 min | 0.882 | 0.893 |
| T4 vv_corr | 0.528 | 0.467 |
| G5 clustering CS | 0.0872 | 0.089 |
| G5 PS | 0.0196 | 0.0272 |
| G6 excess kurtosis | 1.5 | 2.06 |
| U-shape u_ratio | 1.14 | 1.02 |
| spread median (bps) | 0.3 | 0.3 |
| spread p95 (bps) | 1 | 1 |
| shares per day | 515,420 | 513,785 |
| max |mid - value| ($) | 0.79 | 0.741 |
| regime contrast (per day) | 2.38 | 2.61 |
| retail share (%) | 0 | 3.54 |
| MM share (%) | 4.15 | 4.07 |
| MM max |inventory| (sh) | 1,190 | 845 |
| T7 informed P&L total ($) | 1,460 | 883 |
| T7 informed P&L median ($) | 112 | 99.3 |
| MM group P&L ($) | 173 | 685 |
| noise P&L total ($) | -1,337 | — |
| retail P&L total ($) | — | -820 |
| info news f_10 (median) | — | — |
| info news volume uplift | — | — |
| T5 volume uplift (S2) | 2.48 | 2.67 |
| T6 spread_jump_ratio (S2) | 11.7 | 17.1 |
| T6 one-sided share (S2) | 0 | 0 |
| t90 of the jump (min) | 5.05 | 4.86 |
| wall time (s) | 14.5 | 16.7 |

## v1.3 scorecard grades (median over the 10 seeds; G2 from the cross-seed sd of day returns)

| grade | P0 (v1.4) | a-retail |
|---|---|---|
| G1 | FAIL | FAIL |
| G2 | FAIL | FAIL |
| G3 | PASS | PASS |
| G4 | PASS | WARN |
| G5 | WARN | WARN |
| G6 | WARN | WARN |
| G7 | PASS | PASS |
| G8 | PASS | PASS |
| G9 | FAIL | FAIL |
| G10 | FAIL | FAIL |
| G11 | FAIL | FAIL |

## Notes (A4, 2026-10-16)

- **Flags:** only `informed_bounds` (K16, fixed in A6) in 2 jump runs (A-RET-S2 seeds 2 and 5). zero_sum = 0 in all 40 runs.
- **Size of the crowd:** at N_r = 500 the crowd takes 3.5% of volume (both sides counted). P0's 1000 NoiseAgents take 7.5% (v1.4 RESULTS) and 4,000 actions a day. The crowd's ~2,000 actions of median 30 shares are a smaller flow; N_r is a sweep dial (500 / 1500, A7).
- **E-A2** (pre-registered: the crowd alone raises clustering CS and the U-shape) is **not confirmed at N_r = 500 on the calm synthetic_ou value**:
  - CS 0.089 vs 0.087; u_ratio 1.02 vs 1.14.
  - On a calm value V rarely leaves 1, so the self-excitation seldom acts.
  - Removing the NoiseAgents' U-quadratic wake times lowers the U-shape more than the crowd's open/close intensity adds at this size.
  - The kappa_v = 3 comparison is in the sweep.
- **P&L:** retail traders lose $820 a day in total (NoiseAgents in P0: −$1,337); informed traders still gain ($883 total, $99 median).
- The jump response is unchanged in kind (T5 2.67, T6 ratio 17.1 vs 11.7): the crowd does not supply liquidity after a jump. That is the LPs' job (A5).

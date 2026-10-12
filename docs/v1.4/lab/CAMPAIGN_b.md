# Campaign b — budget alone (spec v1.4 §7.2)

C-BL = C-DEF + abides_budget {"L": 2} (GrossLimit on Noise, Value and ABIDES Momentum agents; market makers exempt). S2-BL = S2 + budget. 20 seeds (api.lab.SEEDS). C-BL/S2-BL: engine ['v1.3-ce7beae'], runs ['2026-10-12']. C-DEF/S2: the stored v1.3 runs (runs/_lab, engine ['v1.2-a72d6cf+dirty']); the budget-off market is bit-identical across these engines (I8). Report generated 2026-10-12.

## v1.3 scorecard: C-BL vs C-DEF (20-seed median, grade)

| band | metric | C-DEF | grade | C-BL | grade |
|---|---|---|---|---|---|
| G1 | 1-min volatility | 0.712 | FAIL | 0.702 | FAIL |
| G2 | Daily volatility (across seeds) | 0.191 | FAIL | 0.184 | FAIL |
| G3 | Return predictability |ac1| | 0.374 | FAIL | 0.365 | FAIL |
| G4 | Variance ratio VR(5) | 1.9 | FAIL | 1.92 | FAIL |
| G5 | Volatility clustering (CS, PS) | 0.0381; 0.000526 | FAIL | 0.049; 0.00158 | FAIL |
| G6 | Fat tails (excess kurtosis) | 3.02 | PASS | 3.37 | PASS |
| G7 | Volume–volatility correlation | -0.252 | FAIL | -0.177 | FAIL |
| G8 | Spread (median, p95) | 1; 3 | PASS | 1; 3 | PASS |
| G9 | Mispricing size (gap std) | 0.145 | FAIL | 0.157 | FAIL |
| G10 | Mispricing half-life | 1.57 | FAIL | 2.23 | FAIL |
| G11 | Regime contrast | 2.39 | FAIL | 2.23 | FAIL |

Other medians:

| measure | C-DEF | C-BL |
|---|---|---|
| shares_executed | 591,360 | 424,077 |
| spread_max_ticks | 50 | 48 |
| one_sided_share | 0.000385 | 0.000385 |
| gap_half_life_read_min | 1.65 | 2.3 |
| gap_half_life_min | 1.51 | 1.69 |
| gap_mean | 0.0137 | -0.00201 |
| wall_time_s | 25 | 25.9 |

## BUDGET_BLOCK and clipped orders per class (median over 20 seeds, per run)

| config | class | agents | orders clipped | orders blocked | blocked per agent | blocks by half-hour (09:30 … 15:30, median) |
|---|---|---|---|---|---|---|
| C-BL | NoiseAgent | 1,000 | 62.5 | 0 | 0 | 0 0 0 0 0 0 0 0 0 0 0 0 0 |
| C-BL | ValueAgent | 97 | 4,077 | 2,162 | 22.3 | 112 167 165 155 169 164 159 175 167 175 169 178 201 |
| S2-BL | NoiseAgent | 1,000 | 75 | 0 | 0 | 0 0 0 0 0 0 0 0 0 0 0 0 0 |
| S2-BL | ValueAgent | 97 | 4,826 | 2,917 | 30.1 | 112 167 165 154 199 212 207 226 244 260 246 315 368 |

## Jump: S2-BL vs S2 (+2% value jump at 11:00; treated minus same-seed baseline; median over seeds)

| measure | S2 (v1.3 market) | S2-BL (+ budget) |
|---|---|---|
| t50 | 10.4 | 11.3 |
| t90 | 11.8 | 13 |
| settle | 0.976 | 0.973 |
| overshoot | 0 | 0 |
| volume_uplift | 0.746 | 0.664 |
| vol_uplift | 23.5 | 22 |
| one_sided_share_jump | 0 | 0 |
| spread_p95_jump_ticks | 30 | 37.5 |
| spread_max_jump_ticks | 190 | 276 |
| price_path_steps | 1 | 1 |
| n_seeds | 20 | 20 |

## Completeness

| config | valid seeds | zero_sum ≠ 0 | flags failing | wall time median (s) | errors |
|---|---|---|---|---|---|
| C-BL | 20/20 | 0 | 0 | 26.6 |  |
| S2-BL | 20/20 | 0 | 0 | 25.3 |  |

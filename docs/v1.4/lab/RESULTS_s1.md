# Campaign s1 — design sweep, screening (spec v1.4 §7.3, §7.4)

Final population: 0 ValueAgents, informed fundamentalists (design dials below), budget L=2 on Noise/ABIDES Momentum, 1000 noise, 2 MMs, 12 momentum EKF. Seeds [42, 7, 1, 2, 3]; full day; runs: engine ['v1.3-344fcbf'], dates ['2026-10-12'], 2 workers on an i7-13620H (16 threads, 15.6 GB); report generated 2026-10-12. Each design: D-x (no trigger) and D-x-S2 (+2% value jump at 11:00, baseline D-x). Values are 5-seed medians; ✓/✗ = target met/missed in screening (T5, T6 on S2 only).

## Round 1: the 16 designs

| design | N | T_r | σ_r | W | T1 ac1 | T2 VR5 | T3 vol ratio | T4 vv | T5 uplift S2 | T6 one-sided / p95 S2 | T7 total / median $ | targets | L1 spread med / p95 | L2 volume | L5 wall s | L4 | gap std $ | half-life read → corr (range) min | gap mean $ | t90 S2 min | seeds C/S2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D-60fl500k | 60 | 60–300 s | 10–50 c | $500,000 | -0.0413 ✓ | 1.18 ✓ | 0.499 ✗ | 0.47 ✓ | 2.69 ✓ | 0 / 196 ✗ | 2,079 / 50.2 ✓ | 5/7 | 2 / 8 PASS | 146,245 FAIL | 54.6 PASS | PASS | 0.206 | 4.76 → 4.8 min (5–5) | -0.0372 | 5.48 | 5/5 |
| D-60fl2M | 60 | 60–300 s | 10–50 c | $2,000,000 | -0.051 ✓ | 1.19 ✓ | 0.493 ✗ | 0.52 ✓ | 2.42 ✓ | 0 / 92 ✗ | 1,040 / 108 ✓ | 5/7 | 3 / 10 FAIL | 492,172 PASS | 43.2 PASS | PASS | 0.2 | 4.6 → 4.6 min (5–5) | -0.0219 | 5.8 | 5/5 |
| D-60fh500k | 60 | 60–300 s | 50–200 c | $500,000 | -0.19 ✗ | 0.477 ✗ | 0.655 ✗ | 0.48 ✓ | 3.59 ✓ | 0 / 263 ✗ | 2,249 / 30.8 ✓ | 3/7 | 3 / 12 FAIL | 127,385 FAIL | 35.4 PASS | PASS | 0.468 | 19.3 → 22.8 min (15–45) | -0.0491 | 12.6 | 5/5 |
| D-60fh2M | 60 | 60–300 s | 50–200 c | $2,000,000 | -0.332 ✗ | 0.378 ✗ | 0.631 ✗ | 0.431 ✓ | 3.81 ✓ | 0 / 278 ✗ | 2,494 / 76.8 ✓ | 3/7 | 4 / 15 FAIL | 411,225 PASS | 42.3 PASS | PASS | 0.459 | 21.2 → 25.5 min (20–45) | -0.0401 | 11.9 | 5/5 |
| D-60sl500k | 60 | 300–1800 s | 10–50 c | $500,000 | -0.257 ✗ | 0.571 ✗ | 0.671 ✗ | 0.475 ✓ | 2.83 ✓ | 0 / 467 ✗ | 2,316 / 39.5 ✓ | 3/7 | 3 / 14 FAIL | 139,698 FAIL | 43.5 PASS | PASS | 0.339 | 9.99 → 10.3 min (10–15) | -0.0589 | 20.7 | 5/5 |
| D-60sl2M | 60 | 300–1800 s | 10–50 c | $2,000,000 | -0.336 ✗ | 0.467 ✗ | 0.659 ✗ | 0.386 ✓ | 2.94 ✓ | 0 / 406 ✗ | 961 / 76.9 ✓ | 3/7 | 4 / 16 FAIL | 478,949 PASS | 34.2 PASS | PASS | 0.341 | 10 → 10.4 min (10–15) | -0.0347 | 19.7 | 5/5 |
| D-60sh500k | 60 | 300–1800 s | 50–200 c | $500,000 | -0.315 ✗ | 0.395 ✗ | 0.704 ✗ | 0.317 ✓ | 4.36 ✓ | 0 / 395 ✗ | 1,884 / 38.3 ✓ | 3/7 | 3 / 15 FAIL | 117,960 FAIL | 34.6 PASS | PASS | 0.541 | 29.7 → 40.2 min (20–180) | -0.138 | 34.4 | 5/5 |
| D-60sh2M | 60 | 300–1800 s | 50–200 c | $2,000,000 | -0.369 ✗ | 0.326 ✗ | 0.739 ✗ | 0.454 ✓ | 5.18 ✓ | 0 / 436 ✗ | 1,873 / 46.9 ✓ | 3/7 | 5 / 19 FAIL | 369,973 PASS | 34.8 PASS | PASS | 0.531 | 28.5 → 37.8 min (20–180) | -0.125 | 38.6 | 5/5 |
| D-120fl500k | 120 | 60–300 s | 10–50 c | $500,000 | 0.0203 ✓ | 1.3 ✗ | 0.483 ✗ | 0.536 ✓ | 2.29 ✓ | 0 / 174 ✗ | 978 / 34.1 ✓ | 4/7 | 2 / 8 PASS | 266,907 FAIL | 70.3 PASS | PASS | 0.199 | 4.99 → 5.0 min (5–5) | -0.026 | 4.6 | 5/5 |
| D-120fl2M | 120 | 60–300 s | 10–50 c | $2,000,000 | 0.0544 ✓ | 1.4 ✗ | 0.453 ✗ | 0.49 ✓ | 2.31 ✓ | 0 / 179 ✗ | 353 / 159 ✓ | 4/7 | 3 / 9 FAIL | 993,279 PASS | 74 PASS | PASS | 0.195 | 5.08 → 5.1 min (5–5) | -0.0175 | 5.57 | 5/5 |
| D-120fh500k | 120 | 60–300 s | 50–200 c | $500,000 | -0.375 ✗ | 0.402 ✗ | 0.594 ✗ | 0.661 ✓ | 4.04 ✓ | 0 / 267 ✗ | 1,559 / 20 ✓ | 3/7 | 3 / 11 FAIL | 219,676 FAIL | 74.1 PASS | PASS | 0.477 | 22.6 → 27.6 min (20–60) | -0.045 | 10.9 | 5/5 |
| D-120fh2M | 120 | 60–300 s | 50–200 c | $2,000,000 | -0.326 ✗ | 0.427 ✗ | 0.538 ✗ | 0.579 ✓ | 3.97 ✓ | 0 / 276 ✗ | 1,938 / 26.5 ✓ | 3/7 | 4 / 13 FAIL | 783,984 PASS | 75.6 PASS | PASS | 0.476 | 24.3 → 30.0 min (20–60) | -0.044 | 11.5 | 5/5 |
| D-120sl500k | 120 | 300–1800 s | 10–50 c | $500,000 | -0.263 ✗ | 0.626 ✗ | 0.594 ✗ | 0.492 ✓ | 3.11 ✓ | 0 / 482 ✗ | 743 / 35.9 ✓ | 3/7 | 3 / 13 FAIL | 252,936 FAIL | 72.5 PASS | PASS | 0.339 | 11.6 → 12.4 min (10–20) | -0.0434 | 18.5 | 5/5 |
| D-120sl2M | 120 | 300–1800 s | 10–50 c | $2,000,000 | -0.277 ✗ | 0.617 ✗ | 0.558 ✗ | 0.418 ✓ | 3.5 ✓ | 0 / 516 ✗ | 168 / 127 ✓ | 3/7 | 4 / 15 FAIL | 938,418 PASS | 73 PASS | PASS | 0.343 | 11.9 → 12.7 min (10–20) | -0.0303 | 18.6 | 5/5 |
| D-120sh500k | 120 | 300–1800 s | 50–200 c | $500,000 | -0.335 ✗ | 0.353 ✗ | 0.648 ✗ | 0.452 ✓ | 5.02 ✓ | 0 / 374 ✗ | 1,484 / 30.5 ✓ | 3/7 | 4 / 15 FAIL | 183,795 FAIL | 73.5 PASS | PASS | 0.569 | 31.1 → 42.9 min (30–180) | -0.162 | 35.7 | 5/5 |
| D-120sh2M | 120 | 300–1800 s | 50–200 c | $2,000,000 | -0.401 ✗ | 0.29 ✗ | 0.625 ✗ | 0.392 ✓ | 5.25 ✓ | 0 / 359 ✗ | 1,011 / 88.5 ✓ | 3/7 | 4 / 16 FAIL | 633,525 PASS | 75.7 PASS | PASS | 0.572 | 33.2 → 46.8 min (30–180) | -0.155 | 34.4 | 5/5 |

## Selection printout (round 1)

```
Selection rule (spec v1.4 §7.4), applied to 5-seed medians.

Step 1 — reject designs failing any limit L1, L2, L4, L5:
  D-60fl500k: REJECTED (L2: shares_executed=146,245 >= 295500 FAIL)
  D-60fl2M: REJECTED (L1: spread_med_ticks=3 <= 2 FAIL, spread_p95_ticks=10 <= 10 PASS)
  D-60fh500k: REJECTED (L1: spread_med_ticks=3 <= 2 FAIL, spread_p95_ticks=12 <= 10 FAIL; L2: shares_executed=127,385 >= 295500 FAIL)
  D-60fh2M: REJECTED (L1: spread_med_ticks=4 <= 2 FAIL, spread_p95_ticks=15 <= 10 FAIL)
  D-60sl500k: REJECTED (L1: spread_med_ticks=3 <= 2 FAIL, spread_p95_ticks=14 <= 10 FAIL; L2: shares_executed=139,698 >= 295500 FAIL)
  D-60sl2M: REJECTED (L1: spread_med_ticks=4 <= 2 FAIL, spread_p95_ticks=16 <= 10 FAIL)
  D-60sh500k: REJECTED (L1: spread_med_ticks=3 <= 2 FAIL, spread_p95_ticks=15 <= 10 FAIL; L2: shares_executed=117,960 >= 295500 FAIL)
  D-60sh2M: REJECTED (L1: spread_med_ticks=5 <= 2 FAIL, spread_p95_ticks=19 <= 10 FAIL)
  D-120fl500k: REJECTED (L2: shares_executed=266,907 >= 295500 FAIL)
  D-120fl2M: REJECTED (L1: spread_med_ticks=3 <= 2 FAIL, spread_p95_ticks=9 <= 10 PASS)
  D-120fh500k: REJECTED (L1: spread_med_ticks=3 <= 2 FAIL, spread_p95_ticks=11 <= 10 FAIL; L2: shares_executed=219,676 >= 295500 FAIL)
  D-120fh2M: REJECTED (L1: spread_med_ticks=4 <= 2 FAIL, spread_p95_ticks=13 <= 10 FAIL)
  D-120sl500k: REJECTED (L1: spread_med_ticks=3 <= 2 FAIL, spread_p95_ticks=13 <= 10 FAIL; L2: shares_executed=252,936 >= 295500 FAIL)
  D-120sl2M: REJECTED (L1: spread_med_ticks=4 <= 2 FAIL, spread_p95_ticks=15 <= 10 FAIL)
  D-120sh500k: REJECTED (L1: spread_med_ticks=4 <= 2 FAIL, spread_p95_ticks=15 <= 10 FAIL; L2: shares_executed=183,795 >= 295500 FAIL)
  D-120sh2M: REJECTED (L1: spread_med_ticks=4 <= 2 FAIL, spread_p95_ticks=16 <= 10 FAIL)
No design passes the limits L1, L2, L4, L5: step 1 rejects every design, so the rule names no winner and round 2 (defined from a round-1 winner) cannot start. §7.4 does not cover this case: the owner decides.
```

## Selected design

**none** — every round-1 design fails at least one limit (see step 1); §7.4 has no rule for this case.

## What each dial does (main effects over the 16 designs)

Median over the 8 matched pairs (the other three dials fixed) of the change from the low to the high level.

| dial (low → high) | ac1 | VR(5) | vol ratio | vv_corr | vol uplift S2 | one-sided S2 | spread p95 S2 | fund P&L total $ | fund P&L median $ | volume | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N 60 → 120 | 0.000304 | 0.0523 | -0.0695 | 0.0491 | 0.224 | 0 | 1 | -742 | -5.73 | 192,107 | 36 |
| T_r fast → slow | -0.171 | -0.373 | 0.106 | -0.104 | 0.898 | 0 | 214 | -210 | -4.43 | -24,926 | -0.915 |
| σ_r low → high | -0.136 | -0.514 | 0.0826 | -0.00729 | 1.71 | 0 | 48.5 | 792 | -24.7 | -75,044 | 0.84 |
| W $0.5M → $2M | -0.0341 | -0.0357 | -0.0239 | -0.0546 | 0.167 | 0 | 7 | -524 | 52 | 397,828 | 0.96 |

## Completeness

| config | valid seeds | zero_sum ≠ 0 | flags failing | wall time median (s) | errors |
|---|---|---|---|---|---|
| D-60fl500k | 5/5 | 0 | 5 | 49.9 |  |
| D-60fl500k-S2 | 5/5 | 0 | 5 | 58 |  |
| D-60fl2M | 5/5 | 0 | 5 | 52 |  |
| D-60fl2M-S2 | 5/5 | 0 | 5 | 36 |  |
| D-60fh500k | 5/5 | 0 | 5 | 34.2 |  |
| D-60fh500k-S2 | 5/5 | 0 | 5 | 35.8 |  |
| D-60fh2M | 5/5 | 0 | 5 | 34.2 |  |
| D-60fh2M-S2 | 5/5 | 0 | 5 | 44.3 |  |
| D-60sl500k | 5/5 | 0 | 5 | 43.9 |  |
| D-60sl500k-S2 | 5/5 | 0 | 5 | 37.5 |  |
| D-60sl2M | 5/5 | 0 | 5 | 33.1 |  |
| D-60sl2M-S2 | 5/5 | 0 | 5 | 35.1 |  |
| D-60sh500k | 5/5 | 0 | 5 | 33.8 |  |
| D-60sh500k-S2 | 5/5 | 0 | 5 | 35.7 |  |
| D-60sh2M | 5/5 | 0 | 5 | 34.9 |  |
| D-60sh2M-S2 | 5/5 | 0 | 5 | 34.8 |  |
| D-120fl500k | 5/5 | 0 | 5 | 63 |  |
| D-120fl500k-S2 | 5/5 | 0 | 5 | 71.3 |  |
| D-120fl2M | 5/5 | 0 | 5 | 73 |  |
| D-120fl2M-S2 | 5/5 | 0 | 5 | 74.9 |  |
| D-120fh500k | 5/5 | 0 | 5 | 73.3 |  |
| D-120fh500k-S2 | 5/5 | 0 | 5 | 74.9 |  |
| D-120fh2M | 5/5 | 0 | 5 | 77 |  |
| D-120fh2M-S2 | 5/5 | 0 | 5 | 74.9 |  |
| D-120sl500k | 5/5 | 0 | 5 | 66.9 |  |
| D-120sl500k-S2 | 5/5 | 0 | 5 | 76.2 |  |
| D-120sl2M | 5/5 | 0 | 5 | 70.3 |  |
| D-120sl2M-S2 | 5/5 | 0 | 5 | 76.7 |  |
| D-120sh500k | 5/5 | 0 | 5 | 70.8 |  |
| D-120sh500k-S2 | 5/5 | 0 | 5 | 77.3 |  |
| D-120sh2M | 5/5 | 0 | 5 | 72.7 |  |
| D-120sh2M-S2 | 5/5 | 0 | 5 | 76 |  |

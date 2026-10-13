# Campaign s2 — learning from prices, and the corrected round 1 (spec v1.4.1)

Seeds [42, 7, 1, 2, 3]; full day; final population (0 ValueAgents, budget L=2). Values are 5-seed medians. Report generated 2026-10-13 (report engine v1.3-0d20335+dirty).

## 1. Round 1 re-evaluated under the corrected rules (§3.1, no new runs)

Stored s1 runs (engine ['v1.3-344fcbf']); L1 and G8 in bps of the mid, T6 as spread_jump_ratio, new limit L6, diagnostics of Part 1 recomputed from series.npz. Round 1 has no S2n runs, so T5/T6 are judged on S2 here.

| design | T1 ac1 | T2 VR5 | T3 vol ratio 1m | T4 vv | T5 uplift S2 / S2n | T6 one-sided S2/S2n · ratio S2/S2n | T7 total / median $ | targets | L1 spread med / p95 bps | L2 volume | L5 wall s | L6 max gap $ | L4 | vol ratio 5/15/30/60 m | VR(30) | updated +1/2/5/10/15 m (S2) | t50 / t90 S2 min | spread p95 ticks S2 | seeds C/S2/S2n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D-60fl500k | -0.0413 ✓ | 1.18 ✓ | 0.499 ✗ | 0.47 ✓ | 2.69 / — ✓ | 0/— · 28.4/— ✗ | 2,079 / 50.2 ✓ | 5/7 | 0.2 / 0.801 PASS | 146,245 FAIL | 54.6 PASS | 0.73 PASS | PASS | 0.57 / 0.73 / 0.85 / 0.92 | 2.1 | 0 / 0 / 0.35 / 0.8 / 0.98 | 2.45 / 5.48 | 196 | 5/5/0 |
| **D-60fl2M** | -0.051 ✓ | 1.19 ✓ | 0.493 ✗ | 0.52 ✓ | 2.42 / 2.41 ✓ | 0/0 · 8.69/16.7 ✗ | 1,040 / 108 ✓ | 5/7 | 0.299 / 0.999 PASS | 492,172 PASS | 45.9 PASS | 0.73 PASS | PASS | 0.57 / 0.73 / 0.85 / 0.93 | 2.2 | 0 / 0.017 / 0.33 / 0.87 / 0.98 | 2.8 / 5.8 | 92 | 5/5/5 |
| D-60fh500k | -0.19 ✗ | 0.477 ✗ | 0.655 ✗ | 0.48 ✓ | 3.59 / — ✓ | 0/— · 20.1/— ✗ | 2,249 / 30.8 ✓ | 3/7 | 0.3 / 1.2 PASS | 127,385 FAIL | 35.4 PASS | 1.4 PASS | PASS | 0.47 / 0.48 / 0.57 / 0.66 | 0.627 | 0 / 0 / 0 / 0.17 / 0.55 | 7.52 / 12.6 | 263 | 5/5/0 |
| D-60fh2M | -0.332 ✗ | 0.378 ✗ | 0.631 ✗ | 0.431 ✓ | 3.81 / — ✓ | 0/— · 22.9/— ✗ | 2,494 / 76.8 ✓ | 3/7 | 0.4 / 1.5 PASS | 411,225 PASS | 42.3 PASS | 1.49 PASS | PASS | 0.44 / 0.49 / 0.58 / 0.68 | 0.662 | 0 / 0 / 0 / 0.15 / 0.65 | 6.87 / 11.9 | 278 | 5/5/0 |
| D-60sl500k | -0.257 ✗ | 0.571 ✗ | 0.671 ✗ | 0.475 ✓ | 2.83 / — ✓ | 0/— · 29.3/— ✗ | 2,316 / 39.5 ✓ | 3/7 | 0.3 / 1.4 PASS | 139,698 FAIL | 43.5 PASS | 1.27 PASS | PASS | 0.52 / 0.6 / 0.76 / 0.84 | 0.952 | 0.017 / 0.017 / 0.083 / 0.18 / 0.37 | 9.08 / 20.7 | 467 | 5/5/0 |
| D-60sl2M | -0.336 ✗ | 0.467 ✗ | 0.659 ✗ | 0.386 ✓ | 2.94 / — ✓ | 0/— · 25.2/— ✗ | 961 / 76.9 ✓ | 3/7 | 0.4 / 1.6 PASS | 478,949 PASS | 34.2 PASS | 1.22 PASS | PASS | 0.48 / 0.59 / 0.75 / 0.84 | 0.965 | 0.017 / 0.017 / 0.067 / 0.2 / 0.35 | 7.77 / 19.7 | 406 | 5/5/0 |
| D-60sh500k | -0.315 ✗ | 0.395 ✗ | 0.704 ✗ | 0.317 ✓ | 4.36 / — ✓ | 0/— · 21.5/— ✗ | 1,884 / 38.3 ✓ | 3/7 | 0.3 / 1.5 PASS | 117,960 FAIL | 34.6 PASS | 1.64 PASS | PASS | 0.46 / 0.45 / 0.46 / 0.53 | 0.344 | 0 / 0 / 0 / 0 / 0.017 | 18.8 / 34.4 | 395 | 5/5/0 |
| D-60sh2M | -0.369 ✗ | 0.326 ✗ | 0.739 ✗ | 0.454 ✓ | 5.18 / — ✓ | 0/— · 20/— ✗ | 1,873 / 46.9 ✓ | 3/7 | 0.499 / 1.9 PASS | 369,973 PASS | 34.8 PASS | 1.64 PASS | PASS | 0.44 / 0.4 / 0.46 / 0.53 | 0.293 | 0 / 0 / 0 / 0 / 0.017 | 19.7 / 38.6 | 436 | 5/5/0 |
| D-120fl500k | 0.0203 ✓ | 1.3 ✗ | 0.483 ✗ | 0.536 ✓ | 2.29 / — ✓ | 0/— · 19.9/— ✗ | 978 / 34.1 ✓ | 4/7 | 0.2 / 0.799 PASS | 266,907 FAIL | 70.3 PASS | 0.749 PASS | PASS | 0.57 / 0.73 / 0.85 / 0.92 | 2.65 | 0 / 0.0083 / 0.39 / 0.91 / 0.98 | 2.05 / 4.6 | 174 | 5/5/0 |
| D-120fl2M | 0.0544 ✓ | 1.4 ✗ | 0.453 ✗ | 0.49 ✓ | 2.31 / — ✓ | 0/— · 16.3/— ✗ | 353 / 159 ✓ | 4/7 | 0.299 / 0.898 PASS | 993,279 PASS | 74 PASS | 0.749 PASS | PASS | 0.56 / 0.74 / 0.84 / 0.93 | 2.75 | 0 / 0.0083 / 0.38 / 0.89 / 0.97 | 2.7 / 5.57 | 179 | 5/5/0 |
| D-120fh500k | -0.375 ✗ | 0.402 ✗ | 0.594 ✗ | 0.661 ✓ | 4.04 / — ✓ | 0/— · 22.6/— ✗ | 1,559 / 20 ✓ | 3/7 | 0.3 / 1.1 PASS | 219,676 FAIL | 74.1 PASS | 1.43 PASS | PASS | 0.39 / 0.44 / 0.55 / 0.65 | 0.666 | 0 / 0 / 0 / 0.18 / 0.69 | 7.07 / 10.9 | 267 | 5/5/0 |
| D-120fh2M | -0.326 ✗ | 0.427 ✗ | 0.538 ✗ | 0.579 ✓ | 3.97 / — ✓ | 0/— · 22.7/— ✗ | 1,938 / 26.5 ✓ | 3/7 | 0.399 / 1.3 PASS | 783,984 PASS | 75.6 PASS | 1.48 PASS | PASS | 0.35 / 0.44 / 0.55 / 0.65 | 0.809 | 0 / 0 / 0 / 0.17 / 0.67 | 6.98 / 11.5 | 276 | 5/5/0 |
| D-120sl500k | -0.263 ✗ | 0.626 ✗ | 0.594 ✗ | 0.492 ✓ | 3.11 / — ✓ | 0/— · 47.9/— ✗ | 743 / 35.9 ✓ | 3/7 | 0.3 / 1.3 PASS | 252,936 FAIL | 72.5 PASS | 1.23 PASS | PASS | 0.46 / 0.57 / 0.74 / 0.84 | 1.21 | 0.0083 / 0.017 / 0.058 / 0.18 / 0.35 | 8.32 / 18.5 | 482 | 5/5/0 |
| D-120sl2M | -0.277 ✗ | 0.617 ✗ | 0.558 ✗ | 0.418 ✓ | 3.5 / — ✓ | 0/— · 49.1/— ✗ | 168 / 127 ✓ | 3/7 | 0.4 / 1.5 PASS | 938,418 PASS | 73 PASS | 1.23 PASS | PASS | 0.44 / 0.56 / 0.72 / 0.84 | 1.24 | 0.0083 / 0.017 / 0.058 / 0.16 / 0.38 | 8.65 / 18.6 | 516 | 5/5/0 |
| D-120sh500k | -0.335 ✗ | 0.353 ✗ | 0.648 ✗ | 0.452 ✓ | 5.02 / — ✓ | 0/— · 23.8/— ✗ | 1,484 / 30.5 ✓ | 3/7 | 0.399 / 1.5 PASS | 183,795 FAIL | 73.5 PASS | 1.64 PASS | PASS | 0.38 / 0.35 / 0.41 / 0.49 | 0.352 | 0 / 0 / 0 / 0 / 0.025 | 19.3 / 35.7 | 374 | 5/5/0 |
| D-120sh2M | -0.401 ✗ | 0.29 ✗ | 0.625 ✗ | 0.392 ✓ | 5.25 / — ✓ | 0/— · 22.3/— ✗ | 1,011 / 88.5 ✓ | 3/7 | 0.4 / 1.6 PASS | 633,525 PASS | 75.7 PASS | 1.68 PASS | PASS | 0.35 / 0.33 / 0.42 / 0.5 | 0.332 | 0 / 0 / 0 / 0 / 0.017 | 19.8 / 34.4 | 359 | 5/5/0 |

```
Round 1 under the corrected rules (spec v1.4.1 §3.1; v1.4 §7.4 rule, T5/T6 on S2 only; for the record only).

Step 1 — reject designs failing any limit L1, L4, L5, L2, L6:
  D-60fl500k: REJECTED (L2: shares_executed=146,245 >= 295500 FAIL)
  D-60fl2M: kept
  D-60fh500k: REJECTED (L2: shares_executed=127,385 >= 295500 FAIL)
  D-60fh2M: kept
  D-60sl500k: REJECTED (L2: shares_executed=139,698 >= 295500 FAIL)
  D-60sl2M: kept
  D-60sh500k: REJECTED (L2: shares_executed=117,960 >= 295500 FAIL)
  D-60sh2M: kept
  D-120fl500k: REJECTED (L2: shares_executed=266,907 >= 295500 FAIL)
  D-120fl2M: kept
  D-120fh500k: REJECTED (L2: shares_executed=219,676 >= 295500 FAIL)
  D-120fh2M: kept
  D-120sl500k: REJECTED (L2: shares_executed=252,936 >= 295500 FAIL)
  D-120sl2M: kept
  D-120sh500k: REJECTED (L2: shares_executed=183,795 >= 295500 FAIL)
  D-120sh2M: kept

Step 2 — number of targets passed among T1–T7 (T5, T6 on S2 only):
  D-60fl2M: 5 (T1, T2, T4, T5, T7)
  D-60fh2M: 3 (T4, T5, T7)
  D-60sl2M: 3 (T4, T5, T7)
  D-60sh2M: 3 (T4, T5, T7)
  D-120fl2M: 4 (T1, T4, T5, T7)
  D-120fh2M: 3 (T4, T5, T7)
  D-120sl2M: 3 (T4, T5, T7)
  D-120sh2M: 3 (T4, T5, T7)
  maximum 5: ['D-60fl2M']

Winner: D-60fl2M
```

### G8 re-graded (v1.3 markets)

| market (v1.3 runs, 20 seeds) | spread median / p95 (bps) | G8 (v1.4.1) | G8 as graded in v1.3 (ticks) |
|---|---|---|---|
| C-DEF | 0.1 / 0.3 | PASS | 1 / 3 ticks: PASS |
| C-V20 | 0.1 / 0.4 | PASS | 1 / 4 ticks: PASS |

## 2. Campaign s2: learning from prices (§3.2)

16 designs D-<N><T><S>2M-<L> × {C, S2, S2n} × seeds [42, 7, 1, 2, 3] = 240 runs; engine ['v1.3-0d20335']; dates ['2026-10-13']; W fixed at $2M (7 of 8 $500k designs failed L2 in round 1).

| design | T1 ac1 | T2 VR5 | T3 vol ratio 1m | T4 vv | T5 uplift S2 / S2n | T6 one-sided S2/S2n · ratio S2/S2n | T7 total / median $ | targets | L1 spread med / p95 bps | L2 volume | L5 wall s | L6 max gap $ | L4 | vol ratio 5/15/30/60 m | VR(30) | updated +1/2/5/10/15 m (S2) | t50 / t90 S2 min | spread p95 ticks S2 | seeds C/S2/S2n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D-60fl2M-mod | -0.0365 ✓ | 1.23 ✓ | 0.49 ✗ | 0.491 ✓ | 2.48 / 2.35 ✓ | 0/0 · 17.5/14.5 ✗ | 343 / 131 ✓ | 5/7 | 0.299 / 1 PASS | 574,963 PASS | 46 PASS | 0.792 PASS | PASS | 0.57 / 0.74 / 0.85 / 0.93 | 2.6 | 0 / 0.017 / 0.23 / 0.9 / 1 | 2.8 / 5.92 | 165 | 5/5/5 |
| D-60fl2M-strong | -0.0365 ✓ | 1.23 ✓ | 0.49 ✗ | 0.491 ✓ | 2.21 / 2.13 ✓ | 0/0 · 12.3/11.8 ✗ | 343 / 131 ✓ | 5/7 | 0.299 / 1 PASS | 574,963 PASS | 45.3 PASS | 0.792 PASS | PASS | 0.57 / 0.74 / 0.85 / 0.93 | 2.6 | 0 / 0 / 0.017 / 0.8 / 0.98 | 4.67 / 7.98 | 100 | 5/5/5 |
| D-60fh2M-mod | -0.36 ✗ | 0.375 ✗ | 0.599 ✗ | 0.404 ✓ | 4.24 / 4.09 ✓ | 0/0 · 16.1/15.3 ✗ | 1,549 / 21 ✓ | 3/7 | 0.4 / 1.4 PASS | 434,374 PASS | 47.3 PASS | 1.52 PASS | PASS | 0.41 / 0.46 / 0.57 / 0.68 | 0.577 | 0 / 0 / 0 / 0.12 / 0.67 | 7.75 / 11.3 | 211 | 5/5/5 |
| D-60fh2M-strong | -0.36 ✗ | 0.364 ✗ | 0.599 ✗ | 0.404 ✓ | 4.1 / 4.2 ✓ | 0/0 · 11.7/14 ✗ | 1,567 / 33 ✓ | 3/7 | 0.4 / 1.4 PASS | 434,374 PASS | 46.1 PASS | 1.52 PASS | PASS | 0.41 / 0.46 / 0.57 / 0.68 | 0.577 | 0 / 0 / 0 / 0.05 / 0.67 | 7.87 / 12.4 | 147 | 5/5/5 |
| D-60sl2M-mod | -0.297 ✗ | 0.501 ✗ | 0.671 ✗ | 0.368 ✓ | 2.92 / 2.66 ✓ | 0/0 · 19.3/15.7 ✗ | 891 / 104 ✓ | 3/7 | 0.4 / 1.6 PASS | 539,046 PASS | 47.9 PASS | 1.2 PASS | PASS | 0.49 / 0.59 / 0.74 / 0.82 | 0.792 | 0 / 0 / 0.033 / 0.033 / 0.083 | 31.4 / 54.3 | 214 | 5/5/5 |
| D-60sl2M-strong | -0.297 ✗ | 0.501 ✗ | 0.671 ✗ | 0.383 ✓ | 2.07 / 1.87 ✓ | 0/0 · 6.71/7.64 ✗ | 894 / 104 ✓ | 3/7 | 0.4 / 1.6 PASS | 539,046 PASS | 48.6 PASS | 1.2 PASS | PASS | 0.49 / 0.59 / 0.74 / 0.82 | 0.792 | 0 / 0 / 0 / 0 / 0.033 | 82.8 / 76.6 | 98 | 5/5/5 |
| D-60sh2M-mod | -0.392 ✗ | 0.286 ✗ | 0.695 ✗ | 0.433 ✓ | 4.37 / 4.41 ✓ | 0/0 · 15.3/15.4 ✗ | 2,609 / 4.47 ✓ | 3/7 | 0.499 / 1.7 PASS | 357,954 PASS | 47.8 PASS | 1.7 PASS | PASS | 0.38 / 0.34 / 0.36 / 0.41 | 0.193 | 0 / 0 / 0 / 0.017 / 0.017 | 26.6 / 49.4 | 277 | 5/5/5 |
| D-60sh2M-strong | -0.392 ✗ | 0.286 ✗ | 0.695 ✗ | 0.382 ✓ | 3.61 / 3.73 ✓ | 0/0 · 9.68/9.26 ✗ | 2,571 / 4.47 ✓ | 3/7 | 0.499 / 1.7 PASS | 357,954 PASS | 48.4 PASS | 1.7 PASS | PASS | 0.38 / 0.34 / 0.36 / 0.41 | 0.199 | 0 / 0 / 0 / 0 / 0.017 | 43.9 / 68.7 | 162 | 5/5/5 |
| D-120fl2M-mod | -0.00178 ✓ | 1.41 ✗ | 0.442 ✗ | 0.525 ✓ | 2.45 / 2.42 ✓ | 0/0 · 15.7/16.1 ✗ | 3,253 / 212 ✓ | 4/7 | 0.299 / 0.9 PASS | 1,058,685 PASS | 89.3 PASS | 0.734 PASS | PASS | 0.54 / 0.74 / 0.84 / 0.93 | 3.07 | 0 / 0.0083 / 0.17 / 0.89 / 0.98 | 2.83 / 5.7 | 118 | 5/5/5 |
| D-120fl2M-strong | -0.00178 ✓ | 1.41 ✗ | 0.442 ✗ | 0.526 ✓ | 2.29 / 2.16 ✓ | 0/0 · 17.2/11.3 ✗ | 3,253 / 212 ✓ | 4/7 | 0.299 / 0.9 PASS | 1,058,685 PASS | 78.9 PASS | 0.734 PASS | PASS | 0.54 / 0.74 / 0.84 / 0.93 | 3.07 | 0 / 0 / 0.083 / 0.88 / 0.98 | 4.57 / 6.97 | 140 | 5/5/5 |
| D-120fh2M-mod | -0.429 ✗ | 0.34 ✗ | 0.584 ✗ | 0.454 ✓ | 4.24 / 4.47 ✓ | 0/0 · 16.1/15.5 ✗ | 856 / 156 ✓ | 3/7 | 0.399 / 1.3 PASS | 795,869 PASS | 78 PASS | 1.46 PASS | PASS | 0.37 / 0.45 / 0.55 / 0.64 | 0.693 | 0 / 0 / 0 / 0.11 / 0.69 | 7.33 / 12.3 | 203 | 5/5/5 |
| D-120fh2M-strong | -0.429 ✗ | 0.34 ✗ | 0.585 ✗ | 0.447 ✓ | 4.3 / 4.33 ✓ | 0/0 · 14.5/14 ✗ | 707 / 148 ✓ | 3/7 | 0.399 / 1.3 PASS | 795,568 PASS | 79.6 PASS | 1.46 PASS | PASS | 0.37 / 0.45 / 0.55 / 0.64 | 0.676 | 0 / 0 / 0 / 0.033 / 0.64 | 8.57 / 13.6 | 161 | 5/5/5 |
| D-120sl2M-mod | -0.333 ✗ | 0.591 ✗ | 0.565 ✗ | 0.342 ✓ | 2.77 / 2.91 ✓ | 0/0 · 19.1/19.7 ✗ | -3.42 / 36.4 ✗ | 2/7 | 0.4 / 1.4 PASS | 967,118 PASS | 82.8 PASS | 1.2 PASS | PASS | 0.41 / 0.54 / 0.7 / 0.82 | 1.33 | 0.0083 / 0.0083 / 0.033 / 0.042 / 0.083 | 30.7 / 44 | 247 | 5/5/5 |
| D-120sl2M-strong | -0.335 ✗ | 0.591 ✗ | 0.528 ✗ | 0.315 ✓ | 1.92 / 1.98 ✓ | 0/0 · 8.08/7.29 ✗ | 12.2 / 36.4 ✓ | 3/7 | 0.4 / 1.5 PASS | 967,877 PASS | 83.2 PASS | 1.21 PASS | PASS | 0.4 / 0.54 / 0.7 / 0.82 | 1.32 | 0.0083 / 0 / 0 / 0.025 / 0.033 | 64.5 / 78 | 98 | 5/5/5 |
| D-120sh2M-mod | -0.413 ✗ | 0.283 ✗ | 0.545 ✗ | 0.483 ✓ | 4.82 / 4.7 ✓ | 0/0 · 14.3/13.5 ✗ | 470 / 70.2 ✓ | 3/7 | 0.4 / 1.6 PASS | 606,335 PASS | 81.7 PASS | 1.68 PASS | PASS | 0.32 / 0.31 / 0.33 / 0.41 | 0.278 | 0 / 0 / 0 / 0.0083 / 0.017 | 28.1 / 49.1 | 244 | 5/5/5 |
| D-120sh2M-strong | -0.418 ✗ | 0.281 ✗ | 0.553 ✗ | 0.482 ✓ | 4.14 / 3.81 ✓ | 0/0 · 8.7/8.69 ✗ | 990 / 87.9 ✓ | 3/7 | 0.4 / 1.6 PASS | 605,803 PASS | 99.7 FAIL | 1.69 PASS | PASS | 0.32 / 0.31 / 0.33 / 0.41 | 0.283 | 0 / 0 / 0 / 0.0083 / 0.017 | 44.1 / 64.4 | 149 | 5/5/5 |

### What learning and the dials do (median change over matched pairs)

| change | ac1 | VR(5) | VR(30) | vol ratio 1m | vol ratio 15m | vol ratio 30m | vv_corr | max gap $ | spread med bps | spread p95 bps | jump ratio S2 | updated +2m | updated +5m | t90 S2 | volume | fund P&L total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| off → mod (same N, T, S at $2M) | -0.0258 | -0.00482 | -0.0698 | -0.00702 | -0.0104 | -0.012 | -0.0241 | -0.00837 | 7.18e-05 | -0.000136 | -6.26 | 0 | -0.0125 | 5.82 | 25,924 | -356 |
| off → strong | -0.0258 | -0.0113 | -0.0671 | -0.0205 | -0.0106 | -0.012 | -0.0281 | -0.00337 | 6.98e-05 | -0.000179 | -10.8 | -0.00417 | -0.0292 | 16.1 | 26,304 | -111 |
| mod → strong | 0 | 0 | 0 | 0 | 0 | 0 | -0.000372 | 0 | 0 | 0 | -5.39 | 0 | -0.0167 | 8.64 | 0 | 1.87 |
| N 60 → 120 (s2) | -0.0308 | 0.0443 | 0.292 | -0.0773 | -0.0171 | -0.0253 | 0.039 | -0.0413 | -0.000315 | -0.0999 | -0.0801 | 0 | 0 | -0.25 | 394,784 | -871 |
| T_r fast → slow (s2) | -0.146 | -0.411 | -1.08 | 0.0963 | -0.147 | -0.178 | -0.0646 | 0.318 | 0.0998 | 0.401 | -1.91 | 0 | -0.00833 | 49.6 | -83,614 | 415 |
| σ_r low → high (s2) | -0.209 | -0.584 | -1.54 | 0.0668 | -0.266 | -0.33 | -0.0361 | 0.611 | 0.0994 | 0.299 | -1.03 | 0 | -0.0333 | 4.76 | -221,954 | 1,092 |

## 3. Selection over 32 candidates (§3.3)

```
Selection over 32 candidates (spec v1.4.1 §3.3): limits L1, L4, L5, L2, L6; targets T1–T7 (s2 designs: T5, T6 on S2 AND S2n; round-1 designs: as re-evaluated by §3.1, S2 only).

Step 1 — reject designs failing any limit L1, L4, L5, L2, L6:
  D-60fl500k: REJECTED (L2: shares_executed=146,245 >= 295500 FAIL)
  D-60fl2M: kept
  D-60fh500k: REJECTED (L2: shares_executed=127,385 >= 295500 FAIL)
  D-60fh2M: kept
  D-60sl500k: REJECTED (L2: shares_executed=139,698 >= 295500 FAIL)
  D-60sl2M: kept
  D-60sh500k: REJECTED (L2: shares_executed=117,960 >= 295500 FAIL)
  D-60sh2M: kept
  D-120fl500k: REJECTED (L2: shares_executed=266,907 >= 295500 FAIL)
  D-120fl2M: kept
  D-120fh500k: REJECTED (L2: shares_executed=219,676 >= 295500 FAIL)
  D-120fh2M: kept
  D-120sl500k: REJECTED (L2: shares_executed=252,936 >= 295500 FAIL)
  D-120sl2M: kept
  D-120sh500k: REJECTED (L2: shares_executed=183,795 >= 295500 FAIL)
  D-120sh2M: kept
  D-60fl2M-mod: kept
  D-60fl2M-strong: kept
  D-60fh2M-mod: kept
  D-60fh2M-strong: kept
  D-60sl2M-mod: kept
  D-60sl2M-strong: kept
  D-60sh2M-mod: kept
  D-60sh2M-strong: kept
  D-120fl2M-mod: kept
  D-120fl2M-strong: kept
  D-120fh2M-mod: kept
  D-120fh2M-strong: kept
  D-120sl2M-mod: kept
  D-120sl2M-strong: kept
  D-120sh2M-mod: kept
  D-120sh2M-strong: REJECTED (L5: wall_time_s=99.7 <= 90 FAIL)

Step 2 — number of targets passed among T1–T7 (T5, T6 on S2 AND S2n; designs without S2n runs: S2 only):
  D-60fl2M: 5 (T1, T2, T4, T5, T7)
  D-60fh2M: 3 (T4, T5, T7)
  D-60sl2M: 3 (T4, T5, T7)
  D-60sh2M: 3 (T4, T5, T7)
  D-120fl2M: 4 (T1, T4, T5, T7)
  D-120fh2M: 3 (T4, T5, T7)
  D-120sl2M: 3 (T4, T5, T7)
  D-120sh2M: 3 (T4, T5, T7)
  D-60fl2M-mod: 5 (T1, T2, T4, T5, T7)
  D-60fl2M-strong: 5 (T1, T2, T4, T5, T7)
  D-60fh2M-mod: 3 (T4, T5, T7)
  D-60fh2M-strong: 3 (T4, T5, T7)
  D-60sl2M-mod: 3 (T4, T5, T7)
  D-60sl2M-strong: 3 (T4, T5, T7)
  D-60sh2M-mod: 3 (T4, T5, T7)
  D-60sh2M-strong: 3 (T4, T5, T7)
  D-120fl2M-mod: 4 (T1, T4, T5, T7)
  D-120fl2M-strong: 4 (T1, T4, T5, T7)
  D-120fh2M-mod: 3 (T4, T5, T7)
  D-120fh2M-strong: 3 (T4, T5, T7)
  D-120sl2M-mod: 2 (T4, T5)
  D-120sl2M-strong: 3 (T4, T5, T7)
  D-120sh2M-mod: 3 (T4, T5, T7)
  maximum 5: ['D-60fl2M', 'D-60fl2M-mod', 'D-60fl2M-strong']

Step 3 — tie-break: minimise the sum of normalised misses over T1–T4 (scales T1 0.10, T2 0.45, T3 0.90, T4 0.30), then maximise daily volume, then the lexically smallest id:
  D-60fl2M: misses T1–T4 ['0', '0', '0.452', '0'] sum 0.452; volume 492,172
  D-60fl2M-mod: misses T1–T4 ['0', '0', '0.455', '0'] sum 0.455; volume 574,963
  D-60fl2M-strong: misses T1–T4 ['0', '0', '0.455', '0'] sum 0.455; volume 574,963

Winner: D-60fl2M
```

Winner D-60fl2M fails T3, T6: refinement round (§3.4) with ['D-30fl2M', 'D-240fl2M', 'D-60fl5M'] (C + S2 + S2n, 5 seeds), plus S2n runs of the winner itself where missing.

## 4. Refinement round (§3.4)

| design | T1 ac1 | T2 VR5 | T3 vol ratio 1m | T4 vv | T5 uplift S2 / S2n | T6 one-sided S2/S2n · ratio S2/S2n | T7 total / median $ | targets | L1 spread med / p95 bps | L2 volume | L5 wall s | L6 max gap $ | L4 | vol ratio 5/15/30/60 m | VR(30) | updated +1/2/5/10/15 m (S2) | t50 / t90 S2 min | spread p95 ticks S2 | seeds C/S2/S2n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **D-60fl2M** | -0.051 ✓ | 1.19 ✓ | 0.493 ✗ | 0.52 ✓ | 2.42 / 2.41 ✓ | 0/0 · 8.69/16.7 ✗ | 1,040 / 108 ✓ | 5/7 | 0.299 / 0.999 PASS | 492,172 PASS | 45.9 PASS | 0.73 PASS | PASS | 0.57 / 0.73 / 0.85 / 0.93 | 2.2 | 0 / 0.017 / 0.33 / 0.87 / 0.98 | 2.8 / 5.8 | 92 | 5/5/5 |
| D-30fl2M | -0.12 ✗ | 0.833 ✓ | 0.63 ✗ | 0.464 ✓ | 2.5 / 2.6 ✓ | 0/0 · 13.2/17.4 ✗ | 485 / 86 ✓ | 4/7 | 0.3 / 1.1 PASS | 279,014 FAIL | 26.9 PASS | 0.763 PASS | PASS | 0.6 / 0.76 / 0.84 / 0.92 | 1.59 | 0 / 0.033 / 0.33 / 0.83 / 0.97 | 2.47 / 5.25 | 132 | 5/5/5 |
| D-240fl2M | 0.108 ✗ | 1.68 ✗ | 0.414 ✗ | 0.571 ✓ | 2.44 / 2.6 ✓ | 0/0 · 24.2/21.9 ✗ | 737 / 107 ✓ | 3/7 | 0.299 / 0.8 PASS | 1,980,584 PASS | 186 FAIL | 0.687 PASS | PASS | 0.55 / 0.75 / 0.85 / 0.93 | 3.23 | 0.0042 / 0.013 / 0.36 / 0.89 / 0.98 | 2.43 / 5.15 | 195 | 5/5/5 |
| D-60fl5M | -0.0525 ✓ | 1.2 ✓ | 0.491 ✗ | 0.497 ✓ | 2.49 / 2.64 ✓ | 0/0 · 19.2/14.8 ✗ | 4,644 / 230 ✓ | 5/7 | 0.3 / 1 PASS | 1,181,036 PASS | 47.5 PASS | 0.73 PASS | PASS | 0.57 / 0.74 / 0.85 / 0.93 | 2.21 | 0 / 0.017 / 0.37 / 0.83 / 0.98 | 3.02 / 5.92 | 215 | 5/5/5 |

```
Refinement round (spec v1.4.1 §3.4): the winner and its three refinements, T5/T6 on S2 AND S2n.

Step 1 — reject designs failing any limit L1, L4, L5, L2, L6:
  D-60fl2M: kept
  D-30fl2M: REJECTED (L2: shares_executed=279,014 >= 295500 FAIL)
  D-240fl2M: REJECTED (L5: wall_time_s=186 <= 90 FAIL)
  D-60fl5M: kept

Step 2 — number of targets passed among T1–T7 (T5, T6 on S2 AND S2n):
  D-60fl2M: 5 (T1, T2, T4, T5, T7)
  D-60fl5M: 5 (T1, T2, T4, T5, T7)
  maximum 5: ['D-60fl2M', 'D-60fl5M']

Step 3 — tie-break: minimise the sum of normalised misses over T1–T4 (scales T1 0.10, T2 0.45, T3 0.90, T4 0.30), then maximise daily volume, then the lexically smallest id:
  D-60fl2M: misses T1–T4 ['0', '0', '0.452', '0'] sum 0.452; volume 492,172
  D-60fl5M: misses T1–T4 ['0', '0', '0.454', '0'] sum 0.454; volume 1,181,036

Winner: D-60fl2M
```

## 5. Selected design and decision (§3.5)

**D-60fl2M** — fails T3, T6: STOP and report to the owner (§3.5).

Jump timeline of the selected design (5-seed medians; cf. spec v1.4.1 §0.2 for D-60fl2M without learning):

| jump | updated +1 m | +2 m | +5 m | +10 m | +15 m | t50 min | t90 min | spread_jump_ratio | one-sided | volume uplift |
|---|---|---|---|---|---|---|---|---|---|---|
| +2% (S2) | 0 | 0.017 | 0.33 | 0.87 | 0.98 | 2.8 | 5.8 | 8.69 | 0 | 2.42 |
| −2% (S2n) | 0 | 0.017 | 0.38 | 0.88 | 0.98 | 3.13 | 5.6 | 16.7 | 0 | 2.41 |

Failed targets/limits and their evidence:

- T3 (price vol / value vol): C vol_ratio_price_value = 0.493 >= 0.9 → FAIL
- T6 (no emptied book during a jump): S2 one_sided_share_jump = 0 <= 0.01 → PASS; S2 spread_jump_ratio = 8.69 <= 3 → FAIL; S2n one_sided_share_jump = 0 <= 0.01 → PASS; S2n spread_jump_ratio = 16.7 <= 3 → FAIL


## 6. Findings and E11–E15 verdicts (spec v1.4.1 Part 4)

All numbers are 5-seed medians (seeds 42, 7, 1, 2, 3), engine v1.3-0d20335 (s2, s2r) and
v1.3-344fcbf (s1), 2026-10-13.

**Learning from prices did not spread information faster; it slowed the pricing of jumps.**
- Matched pairs, off → mod / off → strong (same N, T, S at $2M):
  - t90 after the +2% jump: +5.8 / +16.1 min;
  - informed share updated at +5 min: −0.01 / −0.03;
  - spread_jump_ratio: −6.3 / −10.8. The spread widens less after the jump, but the ratio
    is still 6.7–19, against a limit of 3.
- **Mechanism (diagnostic `scripts/diag_learning_jump.py`, seed 42, 11:00–11:30).** Most
  learning-driven belief moves go *away* from the new value, and they are 2–3× larger
  (toward value / toward stale):

  | design | moves | median move ($) |
  |---|---|---|
  | D-60fl2M-mod | 81 / 99 | 0.34 / 1.12 |
  | D-60fl2M-strong | 183 / 216 | 0.30 / 0.89 |
  | D-60sl2M-mod | 150 / 354 | 0.52 / 1.05 |

  The rule is symmetric. An agent that has just researched the new value sees a price that
  has not moved yet, so its gate opens. It inflates P, trusts the stale price and pulls its
  belief back. The agents who carry the information are talked out of it by the price they
  should be moving.
- **On quiet days the gate never opens** in the fast, precise designs. D-60fl2M-mod and
  D-60fl2M-strong are bit-identical there: both draw two values per agent, so every seed
  matches. Quiet-day differences between "off" and a learning design therefore come from the
  two extra draws per agent, which reseed the agents built later, not from learning.

| | verdict | evidence |
|---|---|---|
| E11 informed_share_updated ≥ 50% within 2–3 min | **not met** | updated at +2 min: 0–2% in every learning design (round 1: 0–2%); at +5 min, D-60fl2M: 33% off, 23% mod, 2% strong |
| E12 T6 passes for most learning designs | **not met** | T6 passes in 0 of 16 designs; spread_jump_ratio 6.7–19 (round-1 designs 8.7–49); never one-sided |
| E13 vol ratio at 15/30 min rises toward 1; T3 rises | **not met** | off → mod: 15 min −0.01, 30 min −0.01, 1 min −0.01; T3 stays 0.44–0.70 |
| E14 "strong" herds (higher ac1/VR(30), larger max gap); L6 catches it | **not observed** | quiet days identical to mod; max gap ≤ $1.7 in every design, so L6 never binds; after jumps strong is slower than mod (t90 +8.6 min) |
| E15 slow/noisy designs improve most | **not met; they worsen after jumps** | ac1 unchanged (−0.30 to −0.43); D-60sl2M t90 S2: 19.7 min off, 54 mod, 77 strong |

**Why T3 and T6 fail in the selected design (D-60fl2M, evidence).**
- **T3.** The price/value volatility ratio rises with the horizon: 0.49 (1 min), 0.57 (5),
  0.73 (15), 0.85 (30) and 0.93 (60 min). The price tracks value over an hour but is too
  smooth minute by minute. Value news reaches the price only through research readings every
  1–5 min per agent, so 1-minute value moves are mostly not traded on.
- **T6.** In the 30 minutes after a ±2% jump, the p95 spread is 8.7× (S2) and 16.7× (S2n) the
  same seed's baseline. The book never empties (one-sided share 0). It widens while beliefs
  are split between agents who have and have not researched the jump; 33% have updated at
  +5 min, 87% at +10 min.

**Other notes**
- **Close second.** D-60fl5M ties with the winner on 5/7 targets and loses the tie-break by
  0.002 in normalised miss.
- **N.** N = 30 fails L2 (279k shares) and N = 240 fails L5 (186 s, run one at a time to stay
  within memory).
- **A borderline L5 rejection.** D-120sh2M-strong was rejected on L5 (median 99.7 s). Its
  runs came late in the campaign, when per-run times rose from about 82 s to about 100 s
  under unchanged settings (machine load). It ranks below the winner anyway (3/7 targets).

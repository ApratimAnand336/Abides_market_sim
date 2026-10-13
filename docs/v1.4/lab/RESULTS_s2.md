# Campaign s2 — learning from prices, and the corrected round 1 (spec v1.4.1)

Seeds [42, 7, 1, 2, 3]; full day; final population (0 ValueAgents, budget L=2). Values are 5-seed medians. Report generated 2026-10-13 (report engine v1.3-73734ef+dirty).

## 1. Round 1 re-evaluated under the corrected rules (§3.1, no new runs)

Stored s1 runs (engine ['v1.3-344fcbf']); L1 and G8 in bps of the mid, T6 as spread_jump_ratio, new limit L6, diagnostics of Part 1 recomputed from series.npz. Round 1 has no S2n runs, so T5/T6 are judged on S2 here.

| design | T1 ac1 | T2 VR5 | T3 vol ratio 1m | T4 vv | T5 uplift S2 / S2n | T6 one-sided S2/S2n · ratio S2/S2n | T7 total / median $ | targets | L1 spread med / p95 bps | L2 volume | L5 wall s | L6 max gap $ | L4 | vol ratio 5/15/30/60 m | VR(30) | updated +1/2/5/10/15 m (S2) | t50 / t90 S2 min | spread p95 ticks S2 | seeds C/S2/S2n |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D-60fl500k | -0.0413 ✓ | 1.18 ✓ | 0.499 ✗ | 0.47 ✓ | 2.69 / — ✓ | 0/— · 28.4/— ✗ | 2,079 / 50.2 ✓ | 5/7 | 0.2 / 0.801 PASS | 146,245 FAIL | 54.6 PASS | 0.73 PASS | PASS | 0.57 / 0.73 / 0.85 / 0.92 | 2.1 | 0 / 0 / 0.35 / 0.8 / 0.98 | 2.45 / 5.48 | 196 | 5/5/0 |
| **D-60fl2M** | -0.051 ✓ | 1.19 ✓ | 0.493 ✗ | 0.52 ✓ | 2.42 / — ✓ | 0/— · 8.69/— ✗ | 1,040 / 108 ✓ | 5/7 | 0.299 / 0.999 PASS | 492,172 PASS | 43.2 PASS | 0.73 PASS | PASS | 0.57 / 0.73 / 0.85 / 0.93 | 2.2 | 0 / 0.017 / 0.33 / 0.87 / 0.98 | 2.8 / 5.8 | 92 | 5/5/0 |
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

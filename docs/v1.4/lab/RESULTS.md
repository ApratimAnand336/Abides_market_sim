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

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

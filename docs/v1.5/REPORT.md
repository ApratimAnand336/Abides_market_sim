# FinVerse spec v1.5 (R4: a living market, realistic crashes, circuit breakers) — implementation report

Spec: [`spec_v1.5.txt`](../specs/spec_v1.5.txt). Branch `v1.5`, from 20465e2 (v1.4). Nothing is
pushed. Decisions: [`../engine/DECISIONS.md`](../engine/DECISIONS.md) (D-R4-1 … D-R4-9 and every
deviation below).

## Commits

| milestone | commit | content |
|---|---|---|
| A0 | 528ae6e | spec copy, D-R4-1..9, doc skeletons, HANDOFF rows |
| A1 | d6ad914 | bit-identical engine speed-up (−47% per full P0 day), PROFILE.md, T-S4, T-S5 |
| A2 | (this) | measurement additions (day_rv, RS, retail/mm shares, MM inventory, info-news response), T-R4-1/2 |

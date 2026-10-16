# FinVerse spec v1.5 (R4: a living market, realistic crashes, circuit breakers) — implementation report

Spec: [`spec_v1.5.txt`](../specs/spec_v1.5.txt). Branch `v1.5`, from 20465e2 (v1.4). Nothing is
pushed. Decisions: [`../engine/DECISIONS.md`](../engine/DECISIONS.md) (D-R4-1 … D-R4-9 and every
deviation below).

## Commits

| milestone | commit | content |
|---|---|---|
| A0 | 528ae6e | spec copy, D-R4-1..9, doc skeletons, HANDOFF rows |
| A1 | d6ad914 | bit-identical engine speed-up (−47% per full P0 day), PROFILE.md, T-S4, T-S5 |
| A2 | f7245d2 | measurement additions (day_rv, RS, retail/mm shares, MM inventory, info-news response), T-R4-1/2 |
| A3 | e1c9714, c57015f | living_v1 value process, automatic information news (66 stored-FinBERT templates), day_info, T-O5..T-O9, v1.5 lab runner; campaign a-env (40 runs) |
| A4 | dcfb205, 8f77538 | retail crowd (RetailCrowdAgent + RetailTraderAgent), T-RT1..T-RT6; campaign a-retail (40 runs) |
| A5 | b27d161, (this) | LiquidityProviderAgent, build_config(mm_kind="lp", num_lp, lp_wealth, lp_l_max), T-LP1..T-LP6; campaign a-lp (40 runs): E-A3 not confirmed (T6 ratio 18.7, post-jump p95 spread 8.4 vs 10.7 bps), LPs −$4.4k/day |
| A7 | db1a3db, (this) | design sweep 160 + refinement 40 runs (`lab/RESULTS_a-sweep.md`): 15 of 16 designs fail L7 (retail share < 5%) or L6; selected R-25M15003 (2 LPs of $5M, N_r 1500, κ_v 3), 5/10 screened targets; fails A-T1 (σ1m 4.9 bps), A-T5 (0.81), A-T7 (CS 0.026), A-T10 (LPs −$6.0k), A-T12 (u 1.2) |

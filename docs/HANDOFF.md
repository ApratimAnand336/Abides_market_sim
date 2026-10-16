# Handoff (read this first; keep it under ~60 lines; update at the end of every milestone)

Last updated: 2026-10-16 (A7), spec v1.5 (R4) started on branch `v1.5` (from 20465e2).

## Where we are
- Done: v1.2 (R1), v1.3 (R2), v1.4 (R3, branch `v1.4`; `docs/v1.4/lab/RESULTS.md`).
- **Now: spec v1.5 (R4)**, `docs/specs/spec_v1.5.txt`. Part A living market (A0–A9), Part B
  crashes (B1–B4, STOP to owner after B4), Part C circuit breaker (C1–C2).

## Resume here (2026-10-16: A7 done; next milestone A8)
- **A7 done** (WIP code commit db1a3db + results commit). Sweep 160 + refinement 40 runs, 0 failed,
  zero_sum 0, no invariant flag failing. Report `docs/v1.5/lab/RESULTS_a-sweep.md`.
- **Selected design R-25M15003** = 2 LPs of $5M, N_r 1500, kappa_v 3 (`docs/v1.5/lab/selection_sweep.json`,
  `final_winner`). build_config extra = `lab.sweep_extra("R-25M15003")` (+ day_type per config in A8).
  5-seed screening: sigma1m 4.9 bps, ac1 -0.003, VR(5) 1.24, vol ratio 0.81, vv 0.74, CS 0.026, PS -0.005,
  kurt 22, uplift 1.1, spread ratio 3.0, informed +$23.6k, LP group -$6.0k, u 1.2, retail 7%, 1.42M shares,
  ~22 s/day. Fails A-T1, A-T5, A-T7, A-T10, A-T12 -> A8 will very likely hit A8.4 = STOP after A9.2.
- 13/16 designs failed L7 (retail share 1.2-4.8% < 5%). Bigger LPs: lower sigma1m and vol ratio, higher VR(5),
  kurtosis and LP losses. Refinement: R-25M30003 passed 7/10 targets but failed L6 (gap $20.7).
- **NEXT STEP: A8** confirmation (spec A9.1, 240 runs) with R-25M15003: D-mix (auto), D-calm, D-volatile,
  N-C/N-S2/N-S2n, N-IMP-* (`lab_v15.impact_configs("N")`), N-S4. Register in api/lab.py V15 section
  (base = `sweep_extra`, override day_type), score with `realism.r4a_scorecard` (screening=False; MIX scope
  = D-mix: sigma_day_xseed, day_rv_regime_spread, spreads), then RESULTS_A.md (A9.2).
- **Open questions for the owner:** (1) A6.1 "every fill" -> "every fill that increases exposure"?
  (A7 L4 already uses informed_budget, DECISIONS A7). (2) A8: T6 as a ratio penalises a tight calm book;
  LPs lose to informed flow. (3) L7 floor 5% excludes most designs: as specified, kept.

## Milestone status (spec v1.5)
| ID | Status | Commit | Notes |
|---|---|---|---|
| A0 | done | 528ae6e | spec copy, D-R4-1..9, skeletons |
| A1 | done | d6ad914 | bit-identical speed-up 22.7 → 12.1 s per P0 day (1 worker) |
| A2 | done | f7245d2 | day_rv, RS, shares, MM inventory, info_news; detail in metrics.json diagnostics |
| A3 | done | e1c9714, c57015f | living_v1, auto news; a-env: σ1m 5.0 bps, vol ratio 0.80, ABIDES MMs −$29k |
| A4 | done | dcfb205, 8f77538 | crowd N_r 500: 3.5% of volume; E-A2 not confirmed on the calm value |
| A5 | done | b27d161, (this) | LPs; a-lp: E-A3 not confirmed (ratio 18.7), LPs −$4.4k/day |
| A6 | done | (this) | K16 v2 (0 increasing breaches), IMP-0.1 set, G11 REPORTED, flag informed_budget |
| A7 | done | db1a3db, (this) | sweep 160 + refinement 40; selected R-25M15003 (5/10 screened targets) |
| A8 | todo | | confirmation 240 runs, RESULTS_A.md (STOP if A8.4 fails) |
| A9 | todo | | default switch, dashboard, I8 re-record, legacy invariants |
| B1–B4 | todo | | forced seller, margin calls, crashes; STOP after B4 |
| C1–C2 | todo | | circuit breaker, campaign cb |

## Key facts you would otherwise re-derive
- **Default market P0** (RunParams defaults, dashboard, CLI): 0 value agents, 60 informed
  fundamentalists D-60fl2M (research log-U[60, 300] s, noise log-U[10, 50]¢, $2M, learning
  off), 12 momentum EKF, 1000 noise, 2 ABIDES MMs, budget L = 2 (`budget=None` = auto).
  Legacy market: `num_value=97, num_fund=20, fund_mode="price_only"`. The lab pins the legacy
  base and builds v1.4 populations through params/extra (`api/lab.py`).
- **P0, 20 seeds:** ac1 −0.005; VR(5) 1.2488; vol ratio 1 min 0.49 (K14); vv +0.53; jump
  volume ×2.5; spread_jump_ratio 14.8/16.0 (K15); informed +$1,023; spread 0.30/1.0 bps;
  522k shares; 26 s per day; L6 $0.78.
- **I8** = P0 with 30 informed, 09:30–10:30, seed 42 (re-recorded N6). **I8-legacy** = v1.3
  hash (`LEGACY_PARAMS` in `tests/sim_helpers.py`). Regression: `--campaign regression`
  (P0 vs `docs/v1.4/lab/summary.json`) and `regression-legacy`.
- Campaigns need a committed, clean engine label ("+dirty" redoes every run). 2 workers when
  L5 is measured. Memory ~0.6 GB per 60-agent run; machine 15.6 GB, often 3–5 GB free.
- Lab seeds `api.lab.SEEDS` (42, 7, 1–6, 8–19); screening 42, 7, 1, 2, 3; t0 = 11:00.
- **Engine (A1):** full P0 day 12.1 s in `abides.run` (1 worker). The lab writes L2–L10 depth
  rows every 1 s only (`LAB_BOOK_LOG_DEPTH_INTERVAL_S`); build_config default = every event.
- A3: T-O5 normal-day daily sd 1.28% vs spec 1.49% is a strict xfail (spec number; DECISIONS).
- **v1.5 lab:** `scripts/lab_v15.py`, root `runs/_lab_v15`, reports `docs/v1.5/lab/`. Component
  campaigns = P0-C/S2 reference + C/S2 of the component on the first 10 seeds (40 runs, ~3 min
  at 4 workers). New campaigns: register configs in `api/lab.py` (V15 section, V15_CAMPAIGNS),
  add the id to the realism_lab.py choices, and to `lab_v15.COMPONENTS`/`campaign_configs`.

## Open issues / owner decisions pending
- K14, K15 (`docs/engine/KNOWN_ISSUES.md`) open; K16 fixed behind informed_budget_v2 (A9 switch).
- `git stash` holds 2 stale generated-report entries (safe to drop). `sim_data.pkl` clean.
  CLAUDE.md and .claude/ stay untracked.

## Log (newest first, one line each)
- 2026-10-16 A7: design sweep + refinement (200 runs); selected R-25M15003; fails A-T1/5/7/10/12.
- 2026-10-16 A6: K16 diagnosed and fixed behind informed_budget_v2; IMP-0.1 in the impact set; G11 REPORTED.
- 2026-10-16 A5 (WIP): LPs + tests done; paused before full suite check and campaign a-lp.
- 2026-10-16 A4: retail crowd (T-RT1..6); a-retail 40 runs: retail 3.5% of volume, −$820/day.
- 2026-10-16 A3: living_v1 + auto news; a-env 40 runs (E-A1 not confirmed: σ1m 5.0 bps, ratio 0.80).
- 2026-10-16 A2: measurement additions (scalar keys in run_metrics; run_diagnostics in the lab).
- 2026-10-16 A1: bit-identical speed-up (heap, event copy, log guards, fmt_ts, dropout loop, order copy, sparse lab depth), −47%.
- 2026-10-16 A0: spec v1.5 stored, D-R4-1..9, doc skeletons, branch v1.5.
- 2026-10-14 N7: R3 complete (RESULTS.md, REPORT.md, KNOWN_ISSUES K14–K16).

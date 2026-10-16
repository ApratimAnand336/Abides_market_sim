# Handoff (read this first; keep it under ~60 lines; update at the end of every milestone)

Last updated: 2026-10-16, spec v1.5 (R4) started on branch `v1.5` (from 20465e2).

## Where we are
- Done: v1.2 (R1), v1.3 (R2), v1.4 (R3, branch `v1.4`; `docs/v1.4/lab/RESULTS.md`).
- **Now: spec v1.5 (R4)**, `docs/specs/spec_v1.5.txt`. Part A living market (A0–A9), Part B
  crashes (B1–B4, STOP to owner after B4), Part C circuit breaker (C1–C2).

## Milestone status (spec v1.5)
| ID | Status | Commit | Notes |
|---|---|---|---|
| A0 | done | (see log) | spec copy, D-R4-1..9, skeletons |
| A1 | todo | | engine speed-up (bit-identical), PROFILE.md |
| A2 | todo | | measurement additions |
| A3 | todo | | living_v1 value, auto news, templates; campaign a-env |
| A4 | todo | | retail crowd; campaign a-retail |
| A5 | todo | | liquidity providers; campaign a-lp |
| A6 | todo | | K16 fix (informed_budget_v2), IMP-0.1, G11 to reported |
| A7 | todo | | design sweep 160 (+40) runs |
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
- A3.3 check (A0, DECISIONS): long-run normal-day daily sd is 1.32% vs spec 1.49%; T-O5's
  ±10% band may be borderline on that statistic.

## Open issues / owner decisions pending
- K14, K15, K16 (`docs/engine/KNOWN_ISSUES.md`) are R4's starting point.
- `git stash` holds 2 stale generated-report entries (safe to drop). `sim_data.pkl` clean.
  CLAUDE.md and .claude/ stay untracked.

## Log (newest first, one line each)
- 2026-10-16 A0: spec v1.5 stored, D-R4-1..9, doc skeletons, branch v1.5.
- 2026-10-14 N7: R3 complete (RESULTS.md, REPORT.md, KNOWN_ISSUES K14–K16).

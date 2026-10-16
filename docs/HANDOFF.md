# Handoff (read this first; keep it under ~60 lines; update at the end of every milestone)

Last updated: 2026-10-16, spec v1.5 (R4) started on branch `v1.5` (from 20465e2).

## Where we are
- Done: v1.2 (R1), v1.3 (R2), v1.4 (R3, branch `v1.4`; `docs/v1.4/lab/RESULTS.md`).
- **Now: spec v1.5 (R4)**, `docs/specs/spec_v1.5.txt`. Part A living market (A0–A9), Part B
  crashes (B1–B4, STOP to owner after B4), Part C circuit breaker (C1–C2).

## Milestone status (spec v1.5)
| ID | Status | Commit | Notes |
|---|---|---|---|
| A0 | done | 528ae6e | spec copy, D-R4-1..9, skeletons |
| A1 | done | d6ad914 | bit-identical speed-up 22.7 → 12.1 s per P0 day (1 worker) |
| A2 | done | f7245d2 | day_rv, RS, shares, MM inventory, info_news; detail in metrics.json diagnostics |
| A3 | done | e1c9714, c57015f | living_v1, auto news; a-env: σ1m 5.0 bps, vol ratio 0.80, ABIDES MMs −$29k |
| A4 | done | dcfb205 + (see log) | crowd N_r 500: 3.5% of volume; E-A2 not confirmed on the calm value |
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
- **Engine (A1):** full P0 day 12.1 s in `abides.run` (1 worker). The lab writes L2–L10 depth
  rows every 1 s only (`LAB_BOOK_LOG_DEPTH_INTERVAL_S`); build_config default = every event.
- A3: T-O5 normal-day daily sd 1.28% vs spec 1.49% is a strict xfail (spec number; DECISIONS).
- **v1.5 lab:** `scripts/lab_v15.py`, root `runs/_lab_v15`, reports `docs/v1.5/lab/`. Component
  campaigns = P0-C/S2 reference + C/S2 of the component on the first 10 seeds (40 runs, ~3 min
  at 4 workers). New campaigns: register configs in `api/lab.py` (V15 section, V15_CAMPAIGNS),
  add the id to the realism_lab.py choices, and to `lab_v15.COMPONENTS`/`campaign_configs`.

## Open issues / owner decisions pending
- K14, K15, K16 (`docs/engine/KNOWN_ISSUES.md`) are R4's starting point.
- `git stash` holds 2 stale generated-report entries (safe to drop). `sim_data.pkl` clean.
  CLAUDE.md and .claude/ stay untracked.

## Log (newest first, one line each)
- 2026-10-16 A4: retail crowd (T-RT1..6); a-retail 40 runs: retail 3.5% of volume, −$820/day.
- 2026-10-16 A3: living_v1 + auto news; a-env 40 runs (E-A1 not confirmed: σ1m 5.0 bps, ratio 0.80).
- 2026-10-16 A2: measurement additions (scalar keys in run_metrics; run_diagnostics in the lab).
- 2026-10-16 A1: bit-identical speed-up (heap, event copy, log guards, fmt_ts, dropout loop, order copy, sparse lab depth), −47%.
- 2026-10-16 A0: spec v1.5 stored, D-R4-1..9, doc skeletons, branch v1.5.
- 2026-10-14 N7: R3 complete (RESULTS.md, REPORT.md, KNOWN_ISSUES K14–K16).

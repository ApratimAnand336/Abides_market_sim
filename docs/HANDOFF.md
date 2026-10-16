# Handoff (read this first; keep it under ~60 lines; update at the end of every milestone)

Last updated: 2026-10-16, spec v1.5 (R4) started on branch `v1.5` (from 20465e2).

## Where we are
- Done: v1.2 (R1), v1.3 (R2), v1.4 (R3, branch `v1.4`; `docs/v1.4/lab/RESULTS.md`).
- **Now: spec v1.5 (R4)**, `docs/specs/spec_v1.5.txt`. Part A living market (A0–A9), Part B
  crashes (B1–B4, STOP to owner after B4), Part C circuit breaker (C1–C2).

## Resume here (paused 2026-10-16, milestone A5 = WIP)
- **Done (b27d161):** `agents/liquidity_provider.py` (LiquidityProviderAgent; pure `lp_quotes`,
  `lp_sigma_update`, `lp_needs_requote`), `LP` constants in `param_ranges.py`,
  `build_config(mm_kind="abides"|"lp", num_lp, lp_wealth, lp_l_max)` (LPs appended after retail,
  RNG from the post-latency v1.5 draw), `tests/test_liquidity_provider.py` (9 passed),
  invariants 11 passed (I8 unchanged), A-LP-C/S2 configs + "a-lp" in `api/lab.py`,
  `retail_stop_trigger_pct` + diagnostics `retail_stops` in `api/realism.py`, AGENTS_LP.md,
  DECISIONS (A5), CHANGELOG row.
- **Running at pause:** full suite `python -m pytest abides-markets/tests api/tests -q
  --ignore=abides-markets/tests/test_gym_runner.py -p no:warnings > runs/_logs/suite_A5.log`.
  Check: `tail -n 3 runs/_logs/suite_A5.log` (expect only `test_ou_process` failing). If it did
  not finish, rerun it.
- **NEXT STEP:** check suite_A5.log, then run `python scripts/realism_lab.py --campaign a-lp
  --workers 4 > runs/_logs/a-lp.log 2>&1` (40 runs, ~4 min, clean label b27d161 or later).
  Then add Notes to `docs/v1.5/lab/RESULTS_a-lp.md` (E-A3: post-jump spread ratio < 5?),
  a TESTING.md A5 row, REPORT/HANDOFF rows, and commit "A5: campaign a-lp results".
- **Remaining checklist:** A5 results → A6 (K16 fix behind `informed_budget_v2`, IMP-0.1, G11
  to reported) → A7 sweep (160 runs) → A8 confirmation (240) + RESULTS_A.md → A9 switch → B1–B4
  → C1–C2. lab_v15.py still needs the sweep/confirm/crash campaign code.
- **Numbers found:** LP 1-hour smoke (2×$5M, calm value): requotes on ~37% of wakes, 33% of
  shares, spread median 3¢ / p95 10¢. a-env: σ1m 5.04 bps, vol ratio 0.80 (E-A1 not confirmed,
  better), ABIDES MMs −$28.8k/day. a-retail: retail 3.5% of volume, E-A2 not confirmed.
- **K16 diagnosis note (for A6):** the current §4.5 check already prices position AND wealth at
  the limit price; uncounted in-flight cancels are a real gap. A third cause: after a down-jump,
  mark-to-market alone lifts a leveraged long's w (1.5 → ~1.515 for −2%), which no order rule can
  stop. Diagnose with the targeted test first (spec A6.1); the spec's fix may not reach
  "every fill within one share". If so, that is a spec question for the owner.
- **Open questions:** none blocking A5.

## Milestone status (spec v1.5)
| ID | Status | Commit | Notes |
|---|---|---|---|
| A0 | done | 528ae6e | spec copy, D-R4-1..9, skeletons |
| A1 | done | d6ad914 | bit-identical speed-up 22.7 → 12.1 s per P0 day (1 worker) |
| A2 | done | f7245d2 | day_rv, RS, shares, MM inventory, info_news; detail in metrics.json diagnostics |
| A3 | done | e1c9714, c57015f | living_v1, auto news; a-env: σ1m 5.0 bps, vol ratio 0.80, ABIDES MMs −$29k |
| A4 | done | dcfb205, 8f77538 | crowd N_r 500: 3.5% of volume; E-A2 not confirmed on the calm value |
| A5 | WIP | b27d161 | code + tests done; full suite, campaign a-lp, results pending |
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
- 2026-10-16 A5 (WIP): LPs + tests done; paused before full suite check and campaign a-lp.
- 2026-10-16 A4: retail crowd (T-RT1..6); a-retail 40 runs: retail 3.5% of volume, −$820/day.
- 2026-10-16 A3: living_v1 + auto news; a-env 40 runs (E-A1 not confirmed: σ1m 5.0 bps, ratio 0.80).
- 2026-10-16 A2: measurement additions (scalar keys in run_metrics; run_diagnostics in the lab).
- 2026-10-16 A1: bit-identical speed-up (heap, event copy, log guards, fmt_ts, dropout loop, order copy, sparse lab depth), −47%.
- 2026-10-16 A0: spec v1.5 stored, D-R4-1..9, doc skeletons, branch v1.5.
- 2026-10-14 N7: R3 complete (RESULTS.md, REPORT.md, KNOWN_ISSUES K14–K16).

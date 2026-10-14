# Handoff (read this first; keep it under ~60 lines; update at the end of every milestone)

Last updated: 2026-10-14, after spec v1.4 / v1.4.1 / v1.4.2 (R3), which is **COMPLETE**.

## Where we are
- Done: v1.2 (R1), v1.3 (R2 realism lab), **v1.4 (R3)** on branch `v1.4` (not pushed; no
  upstream set). Reports: `docs/v1.4/lab/RESULTS.md` (findings) and `docs/v1.4/REPORT.md`
  (implementation).
- **Next: the R4 spec** (value dynamics, information news, market-maker inventory, endogenous
  volatility). It starts from K14, K15 and K16 in `docs/engine/KNOWN_ISSUES.md`.

## Milestone status (spec v1.4 + amendments)
| ID | Status | Commit | Notes |
|---|---|---|---|
| N0–N3 | done | 9537703, 9e6b063, ce7beae+3a46289, 344fcbf | spec, measurement, budget, informed mode |
| N4 | done, STOPPED | 73734ef | s1: no design passed the v1.4 limits (tick units) |
| N4a–N4c | done, STOPPED | 153f032, 0d20335, 78deb78 | v1.4.1: bps limits, L6, learning from prices (negative result) |
| N4d | done | 89a4f20 | v1.4.2: OrderBook running totals, bit-identical, −23% time |
| N5 | done | c1dfa51 + 188f196 | step-down + final, 245 runs |
| N6 | done | 65b1307 (WIP) + 60152f0 | default switch to P0 |
| N7 | done | a51037a (+ handoff) | R3 closed |

## Key facts you would otherwise re-derive
- **Default market P0** (RunParams defaults, dashboard, CLI): 0 value agents, 60 informed
  fundamentalists of design D-60fl2M (research log-U[60, 300] s, noise log-U[10, 50]¢, $2M,
  learning off), 12 momentum EKF, 1000 noise, 2 MMs, gross budget L = 2 (`budget=None` = auto).
  - Legacy market: `num_value=97, num_fund=20, fund_mode="price_only"`.
  - The lab pins the legacy base for every config and builds v1.4 populations through
    params/extra (`api/lab.py`).
- **P0, 20 seeds (engine v1.3-c1dfa51):**
  - T1 ac1 −0.005; T2 VR(5) 1.2488 (passes by 0.001); T3 vol ratio 0.49 (FAIL); T4 vv +0.53;
  - T5 ×2.5; T6 spread_jump_ratio 14.8/16.0 (FAIL); T7 +$1,023;
  - L1 0.30/1.0 bps; L2 522k shares; L5 26 s per day; L6 $0.78; t90 of a ±2% jump 5.6/5.1 min.
- **I8** = the new invariant market (P0 with 30 informed, 09:30–10:30, seed 42), re-recorded in
  N6. **I8-legacy** = the v1.3 hash (`LEGACY_PARAMS` in `tests/sim_helpers.py`).
- **Regression:** `--campaign regression` checks P0 against `docs/v1.4/lab/summary.json`;
  `--campaign regression-legacy` checks the v1.3 set. Both PASSED on 2026-10-14.
- **Campaigns** must run on a committed, clean engine label (otherwise the runner sees
  "+dirty" and redoes every run). Use 2 workers when L5 is being measured. Memory: about 0.6 GB
  per 60-agent run, 1 GB at 120, 2 GB at 240. The machine has 15.6 GB, often about 3–5 GB free.
- Lab seeds: `api.lab.SEEDS` (42, 7, 1–6, 8–19); screening seeds 42, 7, 1, 2, 3; t0 = 11:00.

## Open issues / owner decisions pending
- **K16:** the informed budget is exceeded by ≤ 0.9 pp of wealth right after jumps (§4.5 is
  checked at the limit price; in-flight cancels are not counted). Fix or accept.
- **T2 margin:** VR(5) 1.2488 with 10 of 20 seeds above 1.25.
- **IMP-0.1** was dropped by the trim, so β rests on 3 sizes; re-add it for R5?
- **Git history:** the files of 9e6b063 (`docs/finverse_journey`, the "(1)" spec copy) are
  untracked but remain in history.
- **git stash** holds 2 stale generated-report entries (safe to drop). `runs/_n6_wip/` holds
  the N6 patch scripts (git-ignored).
- `sim_data.pkl` is clean (owner-confirmed). CLAUDE.md and .claude/ stay untracked.

## Log (newest first, one line each)
- 2026-10-14 N7: R3 complete (RESULTS.md, REPORT.md, KNOWN_ISSUES K14–K16). Next: R4 spec.
- 2026-10-14 N6: default switch, I8 re-record + legacy, payload 4.6 MB, regression PASSED.
- 2026-10-14 N5: step + final campaigns (245 runs); R3 confirmed on 20 seeds.
- 2026-10-13 N4d: OrderBook running totals (bit-identical), 63 → 48 s per day.
- 2026-10-13 N4a–N4c: v1.4.1 (bps limits, learning from prices: negative), STOP.
- 2026-10-12 N0–N4: spec v1.4, measurement, budget, informed mode, s1 (no winner, STOP).

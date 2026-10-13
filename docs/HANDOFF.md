# Handoff (read this first; keep it under ~60 lines; update at the end of every milestone)

Last updated: 2026-10-12, spec v1.4 in progress on branch `v1.4` (no upstream set).

## Where we are
- Done: v1.2 (R1 foundation fixes), v1.3 (R2 realism lab, measurement only; branch `v1.3`,
  head 502b572). Findings: `docs/v1.3/lab/BASELINE.md`.
- Next: spec v1.4 (R3) `docs/specs/spec_v1.4.txt` — informed fundamentalists replace the
  ValueAgents. Branch `v1.4` from `origin/v1.3`. Milestones N0..N7.
  **STOP after N4** and report the selected design to the owner before the step-down.

## Milestone status (spec v1.4)
| ID | Status | Commit | Notes |
|---|---|---|---|
| N0 | done | 9537703 | sim_data.pkl clean (owner, 2026-10-12) |
| N1 | done | 9e6b063 | G10 key now gap_half_life_corr_min; T-N9 coverage strict xfail (spec issue, 59%) |
| N2 | done | ce7beae + (this) | campaign b: volume −28%, grades unchanged |
| N3 | done | 344fcbf | informed mode; T-N1..7 pass; I8 unchanged |
| N4 | done, STOPPED | 73734ef | s1: NO design passes L1/L2 -> no winner; owner decides |
| N4a | done | 153f032 | v1.4.1: bps limits, L6, diagnostics; round 1 re-evaluated (D-60fl2M, 5/7) |
| N4b | done | 0d20335 | price learning + T-N16..19; s2/s2r plumbing |
| N4c | done, STOPPED | 78deb78 | selected D-60fl2M fails T3, T6 -> STOP (§3.5); learning slows jumps |
| N4d | done | (this) | v1.4.2: OrderBook totals, bit-identical, about −23% |
| N5 | todo | | trimmed campaigns (v1.4.2 Part 2) |
| N6 | todo | | default switch; re-record I8; add I8-legacy |
| N7 | todo | | |

## Key facts you would otherwise re-derive
- R2 baseline (20 seeds, v1.3 default market): σ_1m 0.71 bps; ac1 +0.37; VR(5) 1.90;
  price/value vol 0.58; vv_corr −0.25; spread 1 tick (p95 3); 591k shares/day;
  ValueAgents 86.7% of volume; +2% jump t90 ≈ 12 min via an emptied book, volume −25%.
- Root cause: ValueAgent prices from the book (ask − U[0, 2·spread]), not from its value
  estimate. ValueAgent κ = 1.67e-15/ns vs oracle 1.67e-16 (jumps settle at 97.6%).
- One full day ≈ 25 s and ≈ 466 MB per process (v1.3 market). Campaigns used 4 workers.
- Lab seeds: `api.lab.SEEDS` (42, 7, 1–6, 8–19). Event time t0 = 11:00.
- I8 hash = v1.3 default market; must hold until N6.

## Open issues / owner decisions pending
- Owner answered N4c with spec v1.4.2: D-60fl2M (learning off) is the R3 design; T3/T6 open -> R4 (K14/K15); trimmed campaigns; then N6, N7, STOP.
- git stash holds 2 entries of stale generated reports (safe to drop) and the applied N4c code stash.
- Owner answered N4 with spec v1.4.1 (docs/specs/spec_v1.4.1.txt): bps limits, L6, price learning, campaign s2.
- Files of 9e6b063 (docs/finverse_journey, the "(1)" spec copy) are untracked now but remain in that commit's history (owner decides).
- Optional engine speed-up: OrderBook.get_imbalance is 40% of run time (ABIDES core; owner's call).
- N1 commit 9e6b063 accidentally included untracked owner files docs/finverse_journey/ and docs/v1.1/finverse_spec_v1.1 (1).txt (amend was blocked); owner to decide.
- (sim_data.pkl: clean, owner-confirmed; HANDOFF.md tracked from N0; CLAUDE.md/.claude stay untracked.)

## Log (newest first, one line each)
- 2026-10-13 N4d: OrderBook running totals (T-S1/T-S2 pass), 63 s -> 48 s per D-60fl2M day.
- 2026-10-13 N4c: s2 240 runs + s2r 50 runs; selection D-60fl2M; STOP.
- 2026-10-13 N4b: price learning mechanism, tests; suite 332 passed.
- 2026-10-13 N4a: v1.4.1 Part 1 metrics/limits, housekeeping, corrected round 1.
- 2026-10-12 N4: s1 160 runs (80 min, 2 workers), selection: no winner; long_only flag split.
- 2026-10-12 N3: informed mode + tests; suite 311 passed.
- 2026-10-12 N2 campaign b: 40/40 runs, 5 min; CAMPAIGN_b.md, RESULTS.md §2.
- 2026-10-12 N2 code: GrossLimit, budget switch, I9, lab_v14 (b/s1/s1r2, selection). Suite 300 passed.
- 2026-10-12 N1: corrected half-life + table, jump-window metrics, r3_scorecard; v1.3 HL recomputed (1.6/4.0 min).
- 2026-10-12 N0: spec copy, D-R3-1..6, doc skeletons.
- 2026-10-13 spec v1.4 written and approved; this handoff file created.

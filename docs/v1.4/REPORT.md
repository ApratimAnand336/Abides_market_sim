# FinVerse spec v1.4 (R3: informed fundamentalists replace the value agents) — implementation report

Specs:
- [`spec_v1.4.txt`](../specs/spec_v1.4.txt);
- amendment 1 [`spec_v1.4.1.txt`](../specs/spec_v1.4.1.txt) (corrected limits, learning from prices);
- amendment 2 [`spec_v1.4.2.txt`](../specs/spec_v1.4.2.txt) (close R3, faster engine, trimmed runs).

Branch `v1.4`, from 502b572 (v1.3), commits N0 … N7. Nothing is pushed. Findings:
[`lab/RESULTS.md`](lab/RESULTS.md). Decisions: [`../engine/DECISIONS.md`](../engine/DECISIONS.md)
(D-R3-1 … D-R3-11 and every deviation below).

**Status:** R3 is complete per spec v1.4.2 Part 3. On P0 (20 seeds), T1, T2, T4, T5, T7 and
L1–L6 pass. T3 and T6 fail and are carried into R4 as K14 and K15.

## Commits

| milestone | commit | content |
|---|---|---|
| N0 | 9537703 | spec copy, D-R3-1..6, doc skeletons |
| N1 | 9e6b063 | corrected half-life + table, jump-window metrics, R3 scorecard |
| N2 | ce7beae, 3a46289 | budget (GrossLimit, I9), v1.4 lab plumbing; campaign b report |
| N3 | 344fcbf | informed mode (Part 4), T-N1..T-N7, I4 split |
| N4 | 73734ef | campaign s1, mechanical selection: no winner (STOP) |
| N4a | 153f032 | v1.4.1: spreads in bps, T6 ratio, L6, diagnostics, round 1 re-evaluated |
| N4b | 0d20335 | v1.4.1: learning from prices, T-N16..T-N19, s2 plumbing |
| N4c | 78deb78 | campaign s2 + refinement: D-60fl2M fails T3/T6 (STOP) |
| N4d | 89a4f20 | v1.4.2: OrderBook running totals (bit-identical speed-up), D-R3-7..11 |
| N5 | c1dfa51, 188f196 | step-down + final configs; 245-run results, figures, lab summary |
| N6 | 65b1307 (WIP), 60152f0 | default switch to P0, schema 1.3, ENGINE 1.4, payload, dashboard, I8 re-record + I8-legacy, regression |
| N7 | this commit | RESULTS.md final, this report, KNOWN_ISSUES K14–K16, glossary, screenshot |

## What changed (files and functions)

**Agents and engine:**
- **`abides_markets/agents/fundamental.py`.** Informed mode: `informed_cycle`,
  `research_update`, `belief_prices`, `informed_target`, `budget_qty`, a Poisson
  `get_wake_frequency`, and learning from prices (`price_learning_step`, default off). The
  price-only paths are unchanged (I8-legacy).
- **`abides_markets/utils/budget.py`** (new): `GrossLimit` and `allowed_qty_wealth`.
  `agents/trading_agent.py`: `budget` (default None) and `_apply_budget`, applied in limit and
  market orders.
- **`abides_markets/order_book.py`.** Running visible totals per side (`_vis_bid_qty` /
  `_vis_ask_qty`, `_adj_vis`) and the `DEBUG_TOTALS` check; `get_imbalance` reads the totals.
  Bit-identical (T-S1, T-S2).
- **`configs/param_ranges.py`.** `INFORMED_RANGES`, `PRICE_LEARNING_LEVELS`,
  `DEFAULT_INFORMED_DESIGN`, and `ranges_for_export(design)`.
- **`configs/rmsc04_ekf.py`.** `abides_budget`, `fund_mode`, `informed_design`, and
  `_fund_mode` / `_informed_design` metadata. No new global draws in price-only mode.

**Measurement (`api/realism.py`):**
- `gap_half_life_corrected` with its table (`realism_halflife_table.json`), and
  `jump_window_metrics`;
- `spread_bps`, `spread_jump_ratio`, `vol_ratio_horizon`, `informed_share_updated`;
- `R3_TARGETS`, `R3_LIMITS`, `r3_scorecard`;
- G8 in bps, G10 on the corrected half-life, and the lab flags `long_only` / `informed_bounds`
  (I4 split).

**Dashboard backend:**
- `api/schema.py`: RunParams defaults are now P0 (num_fund 60, 0..200; fund_mode; budget
  auto; num_value 0). Payload schema 1.3: mode, detail, research, learning series,
  informed/price_learning ranges, `agents_detail_note`.
- `api/jobs.py` (run kwargs), `api/export.py` (≤ 20 detailed fundamentalists, research
  markers, population label), `api/server.py` (the v1.4 lab summary), `api/cli.py` (new
  defaults, `--fund-mode`, `--num-value`), `api/__init__.py` (SCHEMA 1.3, ENGINE 1.4).

**Lab:**
- `api/lab.py`: design ids D-<N><T><S><W>[-<L>], and campaigns b, s1, s1r2, s2, s2r, step and
  final with per-config seeds. It pins the v1.3 base for every config. `REGRESSION` is on P0,
  with `REGRESSION_LEGACY` kept.
- `scripts/realism_lab.py`: the v1.4 dispatch, budget and informed counters, and
  `regression(legacy=)`.
- `scripts/lab_v14.py`: reports, the §7.4 / §3.3 selections, N5 report and figures, and
  `write_lab_summary`.
- Diagnostics: `diag_learning_jump.py`, `diag_informed_bounds.py`, `fingerprint_run.py`,
  `halflife_v13_recompute.py`.

**Dashboard (`web/src`):**
- types 1.3;
- Sidebar: mode toggle and a 0–200 slider;
- informed and price-learning parameter cards;
- FundamentalDetail: research markers, a learning chart, and a notice for agents without
  stored detail;
- Realism: corrected G10 with its range and the v1.3 reading in a tooltip, an R3 targets card,
  and the lab baseline on P0.

## Tests

- **Final suite (N6, 2026-10-14):** 338 passed, 1 skipped (the slow regression wrapper),
  3 xfailed (strict), 1 failed (`test_ou_process`, upstream pandas, pre-existing), in 185 s.
- **Invariants:** I1–I9, I8 re-recorded on the new invariant market, and I8-legacy (the v1.3
  hash) all pass.
- **New:**
  - T-N1..T-N7 (informed agent);
  - T-N8..T-N11 (measurement);
  - T-N12, T-N13 (budget);
  - T-N14, T-N15 (v1.4.1 metrics);
  - T-N16..T-N19 (learning);
  - T-S1, T-S2 (speed-up);
  - I9, I8-legacy.
- **Strict xfail (spec issue, reported in N1):** T-N9 coverage. The h_range contains H for 59%
  of paths against the specified 80%, because a non-grid H (1.5 min) falls between the table's
  intervals.
- **Regression:** both `--campaign regression` (P0, 41 checks) and `regression-legacy` (v1.3,
  42 checks) PASSED on 2026-10-14. `npm run build` passes.

## Acceptance (spec v1.4 §12.1)

| | check | result |
|---|---|---|
| A1 | every run completed or listed; ≥ 19/20 and ≥ 5/5 valid seeds | all completed. Two P97-S2 runs timed out during a machine sleep and were re-run successfully; 3 runs timed with 3 workers were set aside and re-run with 2 (DECISIONS N4c) |
| A2 | zero_sum = 0 in every run | yes (b 40, s1 160, s2 240, s2r 50, step 120, final 125) |
| A3 | I1–I9, I8-legacy and unit tests pass | yes (only the pre-existing `test_ou_process` fails) |
| A4 | selection printouts | RESULTS_s1.md, RESULTS_s2.md (rounds, limits, targets, tie-breaks) |
| A5 | payload ≤ 9 MB; npm build | 4.60 MB (default day), 4.46 MB (200 fundamentalists); build passes |

## Run times (development machine: i7-13620H, 16 threads, 15.6 GB, Windows 11)

| campaign | runs | workers | wall time |
|---|---|---|---|
| b | 40 | 4 | 5.0 min (about 26 s per run) |
| s1 | 160 | 2 | 80 min (34–76 s per run; 120 agents about 1 GB per process) |
| s2 | 240 | 2 | about 139 min in two parts (stopped once by the memory reaper; resumed) |
| s2r | 50 | 2 + 1 | 12 + 47 min (240-agent runs: 186 s each, one at a time) |
| step | 120 (+2 re-runs) | 2 | 62 min |
| final | 125 | 2, then 4 | about 93 min (the large-probe runs take about 3 min each) |

Engine speed (N4d, T-S3): one full D-60fl2M day, alternating old/new engine, 1 worker, took
63.6 / 62.7 s before and 48.9 / 48.0 s after (−23%). A P0 day in the lab takes 26 s; a
200-fundamentalist day takes 94 s.

## Deviations from the spec, with reasons (all in DECISIONS.md)

**Spec errors:**
- L1/G8 and T6 in absolute ticks (corrected by v1.4.1).
- §7.4 has no rule when no design passes (stopped for the owner).
- The learning hand simulation tested only an un-updated agent (D-R3-9).
- T-N9's ≥ 80% coverage cannot hold for a non-grid H (strict xfail).

**Implementation choices:**
- **First informed cycle:** quotes only, with W_ref = cash + n·x̂.
- **Informed draws** come after the agent's FUNDAMENTAL_RANGES draws and before its seed.
- **Budget** counts in-flight cancels for ABIDES agents; this cycle only for informed agents
  (§4.5 as written; see K16).
- **The informed-ranges export** was deferred to N6 (schema change).

**Process:**
- N2 and N5 are two commits each, because campaigns must run on a committed, clean engine
  label.
- N6 has a WIP commit, made at the owner's request before a usage limit.
- Uncommitted report code was stashed during runs to keep the label clean.

**Lab and tests:**
- **`long_only` flag** split like I4 (N4).
- **T-M6** uses its own market (no value agents, no fundamentalists): informed agents now
  start the book.
- **The regression set** skips G11 on P0-S2: a jump run's regime contrast measures the jump
  window.
- **Payload:** agents without stored detail keep only start/end holdings (11.45 → 4.46 MB at
  200 fundamentalists).
- **IMP-0.1** was dropped by the v1.4.2 trim, so β is fitted on three sizes.

## Open questions

See [`lab/RESULTS.md`](lab/RESULTS.md) §9:
1. the T2 margin (VR(5) 1.2488);
2. K16 (informed budget after jumps);
3. re-adding IMP-0.1 for R5;
4. the files from 9e6b063 that remain in git history.

Next: the R4 spec (value dynamics, information news, market-maker inventory; K14, K15).

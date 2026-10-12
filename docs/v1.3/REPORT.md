# FinVerse spec v1.3 (R2, the realism lab) — implementation report

Branch `v1.3` (from `v1.2` aa5f606, = origin/v1.2), one commit per milestone, not pushed.
Date: 2026-10-12. Spec: [`docs/specs/spec_v1.3.txt`](../specs/spec_v1.3.txt). Findings:
[`lab/BASELINE.md`](lab/BASELINE.md). Engine documentation: [`docs/engine/`](../engine/README.md).

| Milestone | Commit | Scope |
|---|---|---|
| L0 | 26b9558 | spec copy; owner-line correction of spec v1.1/v1.2; invariant I8 with the hash recorded from aa5f606; `reference_hashes.json` (run A); decisions D-R2-1 … D-R2-5; REALISM_LAB.md skeleton |
| L1 | a72d6cf | `api/realism.py` (Part 3 metrics, bands, grading, aggregation, §7.3 analysis); T-R1 … T-R12 |
| L2 | c19ee3a | `api/lab.py`, `scripts/realism_lab.py`; Campaign c1 (80 runs); `BASELINE_c1.md` |
| L3 | c6a0e38 | oracle path source `"scenario"`; T-L1 … T-L4; Campaign c2 (80 runs) |
| L4 | 5a386e0 | `ImpactProbeAgent`; T-L5 … T-L7; Campaign c3 (120 runs); impact figures |
| L5 | 1785b6d | MM pause windows, momentum capital multiplier; T-L8, T-L9; Campaign c4 (80 runs) |
| L6 | 7eae12d | payload `realism` + `oracle_events` (schema 1.2, engine 1.3); Realism tab; `GET /api/lab/summary` |
| L7 | (this commit) | regression set (+ slow pytest); BASELINE.md, this report; KNOWN_ISSUES, CHANGELOG, TESTING, REALISM_LAB, README synced |

## What changed

**Measurement (no market effect).**
- `api/realism.py` (new): `series_from_end_state` (1 s grid mid, value, spread; 1-min closes,
  returns, volume; per-class net flow; our agents' beliefs and states; agent records; invariant
  flags); `run_metrics` (every Part 3 metric); `agent_sanity` (§3.9–3.10; `zero_sum` in exact
  integer half-cents); `BANDS`, `grade_value`, `grade_run`, `aggregate`, `scorecard` (Part 4);
  `jump_response`, `news_response`, `vol_burst`, `mm_pause`, `impact_run`, `impact_beta`,
  `noise_floor`, `resolved` (§7.3). `api/stats.py` is reused unchanged.
- `api/lab.py` (new): the run matrix `CONFIGS`, `CAMPAIGNS`, `SEEDS`, `lab_config(config_id, seed)`.
  `api/jobs.py`: `run_config_kwargs(params)` factored out of `build_run_config` (no behaviour change).
- `scripts/realism_lab.py` (new): the runner, report step, figures, regression set.
- `api/export.py`, `api/schema.py`, `api/__init__.py`: payload `realism` and `oracle_events`,
  SCHEMA_VERSION 1.2, ENGINE_VERSION 1.3; the probe gets its own population row ("Impact probe
  (test)"). `api/server.py`: `GET /api/lab/summary`.
- `web/`: `tabs/Realism.tsx` (new; this run, lab baseline, diagnostics), `App.tsx`,
  `types/payload.ts`, `lib/api.ts`, `lib/urlState.ts`.

**Scenario tooling (every default inert, checked by I8 and by an explicit-defaults test).**
- `oracles/pregenerated_oracle.py`: `_ou_draws` / `_add_shocks` shared by `synthetic_ou` and the
  new `generate_scenario_ou` (jumps and volatility windows, no extra draws); `applied_events`;
  `oracle.events`. `rmsc04_ekf.build_config(oracle_events=None)`.
- `agents/impact_probe_agent.py` (new): `ImpactProbeAgent`; `build_config(probe=None)` appends it
  last with a constant `RandomState(0)`.
- `agents/market_makers/adaptive_market_maker_agent.py`: `pause_windows=None`;
  `build_config(mm_pause_windows=None)` (clock times).
- `build_config(mom_capital_mult=1.0)`.

**Repository.** `.gitignore`: `!web/src/lib/`. The generic Python rule `lib/` had kept
`web/src/lib/` (api.ts, format.ts, urlState.ts, cn.ts, agents.ts) out of git on every branch, so a
fresh clone could not build the dashboard. L6 adds the five files. `requirements-dev.txt`:
matplotlib.

## Tests

`pytest abides-markets/tests api/tests --ignore=…/test_gym_runner.py`: **261 passed**, 1 skipped
(the slow regression wrapper), 2 xfailed (T-R8 45 and 90 min, strict, see deviation 3),
1 failed (`test_ou_process`, pre-existing upstream). 85 s. v1.2 had 169 passing.

| Group | Result |
|---|---|
| I1–I7 | pass, unchanged |
| **I8** no drift | **pass**; also with every new switch passed explicitly at its default |
| T-R1 … T-R12 | pass, except T-R8 at 45/90 min (strict xfail, deviation 3) |
| T-L1 … T-L9 | pass. **T-L6 passes** (the null probe is neutral): C-DEF is the impact baseline, C-NULL not needed |
| server / export | `/api/lab/summary` 200 and 404; the realism block equals the lab's computation |
| regression set | **PASSED**: run A hash reproduced; 42 metric checks inside the stored [p10, p90] (1 min 22 s) |
| `npm run build` | passes |

## Acceptance (spec §11.3)

| | Criterion | Result |
|---|---|---|
| A1 | every run of Appendix C completed; ≥ 19 valid seeds per config | **360/360** runs, 20 valid seeds in every config. (Four c4 runs were killed by the timeout when the laptop suspended and were re-run; deviation 6.) |
| A2 | zero_sum = 0 exactly in every run | **yes, 360/360** (integer half-cents; conservation, book sanity and long-only flags also hold in all 360) |
| A3 | I1–I8 pass; T-L6 reported | **yes**; T-L6 passes |
| A4 | noise floor reported; every impact number marked resolved or not | **yes**: 0.40 bps (I_end), 0.57 bps (I_perm); 1%, 5% and the 1% sell resolved at the end of execution, 0.1% and 0.5% not; no I_perm resolved |
| A5 | BASELINE.md: scorecards, scenario tables, figures, E1–E9, heavy trader, §0.5 answer | **yes** |
| A6 | payload growth < 50 KB; npm build; screenshot | **+6.4 KB** (full day 20 + 12, seed 42: 8.41 MB total; v1.2 run A 8.40 MB); build passes; [`screenshots/realism_seed42.png`](screenshots/realism_seed42.png) |
| A7 | regression set passes | **yes** |

## Run times

One full day: 25 s [24–27] and 466 MB peak memory per process. c1 9.1 min, c2 9.4 min, c3 13.0 min,
c4 ≈ 11 min of running (4 workers each; the machine had 2–5 GB free, so not 6). All 360 runs:
about 45 minutes of wall time. Regression set: 1 min 22 s. Unit tests: about 85 s.

## Deviations from the spec, with reasons

1. **Seeds (§5.0).** The list "[42, 7, 1, 2, 3, ..., 18]" contains 7 twice (19 distinct). The lab
   uses 42, 7, 1–6, 8–19. The first c1 aggregation double-counted seed 7; this was found and fixed
   before any number was reported.
2. **A jump decays 0.3% over 5 hours**, not "less than 0.0003%" (§6.1): a^18000 = e^(−0.003).
   T-L2 asserts the exact formula and ≥ 99.7% at 16:00. The generator follows the spec's algorithm.
3. **T-R8 at 45 and 90 min fails as specified** (strict xfail). The spec's half-life estimator
   (de-meaned ACF of one 6.5 h day, §3.7) reads 45 min as 20.8 min (−54%) and 90 min as 27.1
   min (−70%) (median of 20 synthetic paths). This is a known bias of the estimator, not a coding
   error. The estimator was not changed, because G10 grades it (DECISIONS.md; open question for the owner).
4. **Boundaries.** All bands use closed intervals with PASS tested first, so every boundary takes
   the better grade (T-R11). This makes G13's ratio of exactly 0 a WARN although the table lists
   "≤ 0" under FAIL.
5. **Runner processes (§7.1).** One spawned `Process` per run with a scheduler instead of a
   `Pool(maxtasksperchild=1)`: a Pool cannot kill one stuck task, and the per-run 15-minute timeout
   is required. Default workers stay min(cpu − 1, 6). The campaigns used 4 because of memory.
6. **Laptop suspend during c4.** The c4 log jumps from 3.5 to 334 minutes elapsed between two
   consecutive completions. The four runs in flight (S7a seeds 12–15) hit the timeout on wake and
   were re-run normally (28–31 s).
7. **Probe arrival mid.** PROBE_SUMMARY's `arrival_mid` comes from a spread query that the probe
   sends with its first child, just before the order. The lab's shortfall uses the spec's mid_B(t0).
8. **`mm_pause_windows` are clock times** ("13:00:00"), as written in Appendix C. `oracle_events`
   and `probe.start` are offsets from 09:30, as specified.
9. **MM pause details** (§6.3, needed for "no MM order placed inside the window"): a spread answer
   that arrives inside a window, or a book-imbalance event inside it, places no orders. The extra
   window-start wake does not reschedule, so the regular wake chain is not doubled.
10. **Response curves and per-seed scenario rows are in summary.json**, so the figures and the
    dashboard need no run files. summary.json is 882 KB (compact JSON).
11. **`n_execs` and the I1 fingerprint** are stored in every metrics.json (used by the regression set).
12. **A pre-existing repository gap was fixed** (`web/src/lib/` untracked, see above).

## Open questions

1. G10: keep the estimator and its bias, change it, or move the band (BASELINE.md §8)?
2. A value jump settles at 97.6% of its size on every seed. Is the value agents' mean reversion
   toward r̄ intended for information news?
3. Negative volume–volatility correlation (−0.25; new K13): mechanism to check before R3.
4. The working tree's tracked `sim_data.pkl` was modified before R2 began (not by this work). It
   makes every `engine_version` carry "+dirty". It was left untouched and uncommitted.

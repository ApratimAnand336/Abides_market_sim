# Changelog

Sources: the git log of this repository and the specs in [`docs/specs/`](../specs/).
Upstream ABIDES history (2021–2023, J.P. Morgan) is not repeated here.

## v1.4 — R3: informed fundamentalists replace the value agents (in progress, branch `v1.4`)

Spec: [`docs/specs/spec_v1.4.txt`](../specs/spec_v1.4.txt).

| Milestone | Files | Change |
|---|---|---|
| N0 | `docs/specs/spec_v1.4.txt`, `docs/engine/DECISIONS.md`, `docs/engine/AGENTS_ABIDES.md`, doc skeletons, `docs/HANDOFF.md` | Spec v1.4 stored; D-R3-1..6; ValueAgent mechanism finding (§0.3) and κ mismatch documented; sim_data.pkl confirmed clean by the owner |
| N1 | `api/realism.py`, `api/realism_halflife_table.json`, `api/tests/test_realism.py`, `scripts/realism_lab.py`, `scripts/halflife_v13_recompute.py`, `docs/v1.4/lab/RESULTS.md` | Corrected gap half-life (no de-meaning + synthetic correction table), G10 grades it; jump-window metrics; `R3_TARGETS`, `R3_LIMITS`, `r3_scorecard`; `active_halfhours_share` (L3); T-N8 … T-N11; v1.3 C-DEF/C-V20 half-lives recomputed from stored series |
| N2 | `abides_markets/utils/budget.py`, `agents/trading_agent.py`, `configs/rmsc04_ekf.py`, `tests/test_budget.py`, `tests/test_invariants.py`, `api/lab.py`, `api/realism.py`, `scripts/realism_lab.py`, `scripts/lab_v14.py` | GrossLimit (K10) and `TradingAgent.budget` (default None); `build_config(abides_budget=...)` on Noise/Value/ABIDES Momentum (MMs exempt); T-N12, T-N13, I9; v1.4 lab plumbing (runs/_lab_v14, campaigns b/s1/s1r2, design ids, §7.4 selection, `r3_scorecard(screening=True)`); Campaign b |
| N3 | `agents/fundamental.py`, `configs/param_ranges.py`, `configs/rmsc04_ekf.py`, `tests/test_fundamental_informed.py`, `tests/test_invariants.py` | FundamentalistAgent informed mode (§4.1–4.6): research channel, price distrust ρ, leverage-bounded target, belief-anchored target orders and quote layer, worst-case budget, Poisson wakes; `INFORMED_RANGES`; `build_config(fund_mode, informed_design)` (inert at defaults, I8 unchanged); T-N1 … T-N7; I4 split |
| N4 | `scripts/lab_v14.py`, `api/realism.py`, `docs/v1.4/lab/RESULTS_s1.md`, `selection_s1.json`, `summary_s1.json` | Campaign s1 (160 runs) and the mechanical §7.4 selection: every design fails L1 and/or L2, so there is no winner (stopped for the owner); lab `long_only` flag split (I4) with new `informed_bounds` |
| N4a (spec v1.4.1) | `docs/specs/spec_v1.4.1.txt`, `.gitignore`, `api/realism.py`, `api/tests/test_realism.py`, `scripts/lab_v14.py`, `web/src/tabs/Realism.tsx`, `docs/v1.4/lab/RESULTS_s2.md` | Amendment stored; two files committed by accident in 9e6b063 untracked and ignored; spreads in bps (G8, L1), T6 = spread_jump_ratio, new limit L6 (max \|gap\|), diagnostics (vol ratio by horizon, informed_share_updated); T-N14, T-N15; round 1 re-evaluated from stored series |
| N4b (spec v1.4.1) | `agents/fundamental.py`, `configs/param_ranges.py`, `configs/rmsc04_ekf.py`, `tests/test_fundamental_informed.py`, `api/lab.py`, `scripts/lab_v14.py`, `scripts/realism_lab.py` | Learning from prices (`price_learning` off/mod/strong; gated covariance matching); `PRICE_LEARNING_LEVELS`; T-N16 … T-N18; lab plumbing for campaigns s2 and s2r (level suffix in design ids, S2n configs, refinement designs) |
| N4c (spec v1.4.1) | `scripts/lab_v14.py`, `scripts/diag_learning_jump.py`, `docs/v1.4/lab/RESULTS_s2.md`, `S2_FINDINGS.md`, `selection_s2.json`, `summary_s2.json` | Campaign s2 (240 runs) and s2r (50 runs); 32-candidate selection: D-60fl2M, which fails T3 and T6, so STOP (§3.5); finding: learning from prices slows jump pricing (moves toward the stale price) |
| N4d (spec v1.4.2) | `docs/specs/spec_v1.4.2.txt`, `abides_markets/order_book.py`, `tests/test_orderbook_totals.py`, `tests/orderbook/conftest.py`, `scripts/fingerprint_run.py`, `docs/v1.4/lab/reference_hashes.json` | D-R3-7 … D-R3-11; OrderBook running visible totals (get_imbalance no longer sums every order; bit-identical, about −23% wall time); T-S1, T-S2, T-S3; learning from prices documented as a negative result |

## v1.3 — R2: the realism lab, measurement only (2026-10-12, branch `v1.3`)

Spec: [`docs/specs/spec_v1.3.txt`](../specs/spec_v1.3.txt). Reports: [`docs/v1.3/REPORT.md`](../v1.3/REPORT.md),
[`docs/v1.3/lab/BASELINE.md`](../v1.3/lab/BASELINE.md). Every change is measurement or
scenario tooling whose default is inert; invariant I8 checks that default runs are
bit-identical to v1.2 (aa5f606).

| Milestone | Files | Change |
|---|---|---|
| L0 | `docs/specs/`, `docs/engine/REALISM_LAB.md`, `docs/engine/DECISIONS.md`, `docs/engine/TESTING.md`, `abides-markets/tests/test_invariants.py`, `docs/v1.3/lab/reference_hashes.json` | Spec v1.3 stored; **owner correction (2026-10-11): the "Owner:" line of `spec_v1.1.txt` and `spec_v1.2.txt` now reads "Owner: Apratim Anand, IIT Bombay."** (nothing else changed in those files); invariant I8 "no drift" with the hash recorded from aa5f606; run A reference hash; decision entries D-R2-1 … D-R2-5; REALISM_LAB.md skeleton |
| L1 | `api/realism.py` (new), `api/tests/test_realism.py` (new), `docs/engine/REALISM_LAB.md` | Every Part 3 metric, the bands (`BANDS`) and grading, aggregation over seeds, the §7.3 scenario analysis functions, zero_sum in exact integer half-cents; tests T-R1 … T-R12. No simulation code touched |
| L2 | `api/lab.py` (new), `api/jobs.py` (`run_config_kwargs`, no behaviour change), `scripts/realism_lab.py` (new), `requirements-dev.txt` (matplotlib), `docs/v1.3/lab/` (summary.json, BASELINE_c1.md, figures) | The run matrix (Appendix C) and the lab runner: resumable, one process per run, metrics.json + series.npz per run, aggregation, scenario analysis, figures, regression set. Campaign c1 run on 20 seeds (80 runs) |
| L3 | `oracles/pregenerated_oracle.py`, `configs/rmsc04_ekf.py` (`oracle_events`), `tests/test_scenarios.py` (new), `docs/engine/ORACLE.md` | Oracle path source `"scenario"` (value jumps and volatility windows, no extra draws; the shared `_ou_draws` helper keeps `synthetic_ou` bit-identical) and `oracle.events`; T-L1 … T-L4; Campaign c2 (S2, S2n, S3, S5, 80 runs) |
| L4 | `agents/impact_probe_agent.py` (new), `configs/rmsc04_ekf.py` (`probe`), `api/export.py` (probe row label "Impact probe (test)", probe start position), `tests/test_scenarios.py`, `docs/engine/ARCHITECTURE.md` | `ImpactProbeAgent` (a parent order as 30 market orders over 5 minutes; constant RNG, appended last); T-L5 … T-L7 (the null probe is neutral, so no C-NULL); Campaign c3 (IMP-0 … IMP-1s, 120 runs); impact figures |
| L5 | `agents/market_makers/adaptive_market_maker_agent.py` (`pause_windows`), `configs/rmsc04_ekf.py` (`mm_pause_windows`, `mom_capital_mult`), `tests/test_scenarios.py`, `docs/engine/AGENTS_ABIDES.md` | Market-maker pause windows and the momentum capital multiplier (both inert by default); T-L8, T-L9; Campaign c4 (S6, S7a, S7b, S7c, 80 runs). All 360 runs of Appendix C complete |
| L6 | `api/__init__.py` (SCHEMA_VERSION 1.2, ENGINE_VERSION 1.3), `api/export.py`, `api/schema.py`, `api/server.py` (`GET /api/lab/summary`), `api/tests/`, `web/src/tabs/Realism.tsx` (new), `web/src/App.tsx`, `web/src/types/payload.ts`, `web/src/lib/` (api.ts, urlState.ts), `.gitignore` | Payload `realism` (bands, single-run Part 3 metrics, grades G1, G3–G11; +6.4 KB on a full 20 + 12 day) and `oracle_events`; fifth dashboard tab "Realism" (this run, lab baseline, diagnostics); the lab summary endpoint. **`web/src/lib/` was never committed** (the root `.gitignore` rule `lib/` matched it); an exception `!web/src/lib/` adds the five files so a fresh clone can build the dashboard |
| L7 | `scripts/realism_lab.py` (compact summary.json), `api/tests/conftest.py` (`slow` marker), `api/tests/test_lab_regression.py`, `docs/v1.3/lab/BASELINE.md`, `docs/v1.3/REPORT.md`, `docs/engine/*` | Regression set passes; final findings report and implementation report; KNOWN_ISSUES on 20-seed medians (K11 measured, K13 new), REALISM_LAB, TESTING, README glossary synced |

## v1.2 — R1: foundation fixes and living documentation (2026-10-09, branch `v1.2`)

Spec: [`docs/specs/spec_v1.2.txt`](../specs/spec_v1.2.txt). Report and acceptance numbers:
[`docs/v1.2/REPORT.md`](../v1.2/REPORT.md).

| Milestone | Files | Change |
|---|---|---|
| W0 | `docs/engine/`, `docs/specs/` | Living documentation skeleton; specs stored with the code |
| W1 | `agents/fundamental.py`, `tests/test_fundamental.py` | Edge z = (x̂ − mid)/√(P + R_last) (`R_last` stored each update); `z_den` in FUND_DECISION; T-F8 … T-F10 |
| W2 | `oracles/pregenerated_oracle.py` (new), `oracles/__init__.py`, `configs/rmsc04_ekf.py`, `api/export.py`, `tests/test_oracle.py` | `PregeneratedOracle`: the whole true-value path generated at construction from one dedicated RNG (`generate_path` / `PATH_SOURCES`, source `synthetic_ou`); `rmsc04_ekf` uses it for 09:30–16:00 on a 1 s grid; T-O1 … T-O4. Export: market statistics rounded to 8 significant figures instead of 6 (half-cent closes were rounded away) |
| W3 | `agents/market_makers/adaptive_market_maker_agent.py`, `configs/rmsc04_ekf.py`, `order_book.py`, `agents/utils.py`, `agents/fundamental.py`, `agents/momentum_ekf.py`, `tests/test_market_maker.py`, `tests/sim_helpers.py` | MM `cold_start_price` (= r̄) and always rescheduling the next wake (fixes MM death and the market not starting without value agents); MM `max_spread` cap (100¢) against the self-referential spread runaway; no quotes ≤ 0; EXEC history records the fill price; numerically stable caution sigmoid in both of our agents; T-M6, T-M7 |
| W4 | `tests/test_invariants.py` | Invariants I1–I7: cross-process determinism (with different hash seeds), oracle stability, conservation of cash and shares, long-only safety, book sanity, market without value agents, MM liveness. No non-determinism found |
| W5 | `api/__init__.py`, `web/src/components/health/PriceVsValue.tsx`, `web/src/components/health/PopulationCard.tsx`, `web/src/components/ui/DataTable.tsx`, `docs/engine/AGENT_MOMENTUM.md` | `ENGINE_VERSION` 1.2 (cached v1.1 runs are not reused or listed); U1 the price-vs-value caption shows no hard-coded seed-42 reference; U2 a compact DataTable mode (tighter cells, wrapping headers) so the population table fits its card; payload schema unchanged (1.1). AGENT_MOMENTUM.md written (documentation only) |
| W6 | `scripts/acceptance_v1_2.py`, `docs/v1.2/`, `web/src/components/health/PopulationCard.tsx`, `web/src/components/ui/DataTable.tsx`, `docs/engine/*` | Acceptance runs A, B, C, Z (all targets met); report and screenshots; the population table uses compact dollars and a 12 px compact mode so it fits at 1280 px; KNOWN_ISSUES synced with the measured numbers |

## v1.1 — fundamentalist and momentum fixes, dashboard additions (2026-10-08)

Spec: [`docs/specs/spec_v1.1.txt`](../specs/spec_v1.1.txt). Report and acceptance numbers:
[`docs/v1.1/REPORT.md`](../v1.1/REPORT.md). Commits e40df56 … 3c0b859.

| Milestone | Commit | Files | Change |
|---|---|---|---|
| V1 | e40df56 | `agents/fundamental.py`, `configs/param_ranges.py`, `configs/rmsc04_ekf.py`, `tests/test_fundamental.py` | Removed the ±1% nudge; process noise Q from a 300 s value-speed estimate; smaller R ranges; target-position sizing (`target_position`, FUND_DECISION); volatility-scaled news (`apply_news`); `beta` and `news_sensitivity` removed |
| V2 | 2ddee51 | `agents/momentum_ekf.py`, `configs/param_ranges.py`, `configs/rmsc04_ekf.py`, `tests/test_momentum_ekf.py`, `.gitignore` | M1 κ ranges; M2 `detrended_var`; M3 `tau_ratio` (τ = ratio × wake_mean); M4 ratchet follows down; M5 re-entry needs T ≥ θ_out; M6 `exit_pending`; M7 log keys; `log/` and `*.pkl` ignored |
| V3 | 2caaed7 | `api/__init__.py`, `api/export.py`, `api/jobs.py`, `api/schema.py`, `web/src/…` | Payload schema 1.1; `ENGINE_VERSION` in the cache key; new fundamental export fields; D2 "P&L vs holding" (leaderboard column, KPI) |
| V4 | e2a6e02 | `web/src/charts/series.ts`, `tabs/MarketOverview.tsx`, `agents/FundamentalDetail.tsx` | D1 off-scale overlays break with edge markers; D3 overlay agent chips |
| V5 | 49c46bc | `api/export.py`, `api/stats.py`, `api/schema.py`, `api/jobs.py`, `configs/rmsc04_ekf.py` (`num_mm`), `web/src/components/health/…`, `Sidebar.tsx` | D4 market population table and count controls (`num_value`, `num_noise`, `num_mm`); D5 price vs true value panel (gap std, half-life) |
| V6 | 3c0b859 | `scripts/acceptance_v1_1.py`, `docs/v1.1/` | Full-day acceptance (all targets met), report, screenshots |

## v1.0 — our agents and the dashboard (2026-09-25 … 2026-10-06)

There was no single written spec for the fundamentalist v1.0. The momentum agent follows
"momentum_agent_spec v1.0" and the dashboard follows "dashboard_spec v1.0" (both in the
owner's project notes, not in this repository).

| Date | Commit | Files | Change |
|---|---|---|---|
| 2026-09-25 | 9a8fb8c | `agents/fundamental.py`, `agents/news_oracle_agent.py`, `messages/news.py`, `models/finbert_sentiment.py`, `models/order_size_model.py`, `configs/rmsc04_ekf.py`, `dashboard.py`, `run_dashboard_sim.py`, `run_simulation.py` | First version of our FundamentalistAgent (scalar Kalman filter, ER-based R, caution modulator), the NewsOracleAgent and news messages, FinBERT headline scoring, the `rmsc04_ekf` market, and a Streamlit dashboard |
| 2026-09-25 | ea3ecf7 | `agents/fundamental.py`, `configs/rmsc04_ekf.py`, `run_dashboard_sim.py` | Bug fixes |
| 2026-10-05 | 539ec6b | `agents/momentum_ekf.py`, `tests/test_momentum_ekf.py`, `configs/rmsc04_ekf.py`, `abides_core/utils.py`, `agents/fundamental.py` | MomentumEKFAgent; endowments for our agents; pandas ≥ 2 fix in `str_to_ns` |
| 2026-10-06 | 826ab70 … aa38353 | `api/`, `web/`, `configs/param_ranges.py` | Dashboard M1–M8: payload export, HTTP API, React frontend with four tabs, and the hyperparameter ranges as a single source of truth |

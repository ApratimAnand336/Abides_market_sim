# Changelog

Sources: the git log of this repository and the specs in [`docs/specs/`](../specs/).
Upstream ABIDES history (2021–2023, J.P. Morgan) is not repeated here.

## v1.3 — R2: the realism lab, measurement only (in progress, branch `v1.3`)

Spec: [`docs/specs/spec_v1.3.txt`](../specs/spec_v1.3.txt). Every change is measurement or
scenario tooling whose default is inert; invariant I8 checks that default runs are
bit-identical to v1.2 (aa5f606).

| Milestone | Files | Change |
|---|---|---|
| L0 | `docs/specs/`, `docs/engine/REALISM_LAB.md`, `docs/engine/DECISIONS.md`, `docs/engine/TESTING.md`, `abides-markets/tests/test_invariants.py`, `docs/v1.3/lab/reference_hashes.json` | Spec v1.3 stored; **owner correction (2026-10-11): the "Owner:" line of `spec_v1.1.txt` and `spec_v1.2.txt` now reads "Owner: Apratim Anand, IIT Bombay."** (nothing else changed in those files); invariant I8 "no drift" with the hash recorded from aa5f606; run A reference hash; decision entries D-R2-1 … D-R2-5; REALISM_LAB.md skeleton |
| L1 | `api/realism.py` (new), `api/tests/test_realism.py` (new), `docs/engine/REALISM_LAB.md` | Every Part 3 metric, the bands (`BANDS`) and grading, aggregation over seeds, the §7.3 scenario analysis functions, zero_sum in exact integer half-cents; tests T-R1 … T-R12. No simulation code touched |
| L2 | `api/lab.py` (new), `api/jobs.py` (`run_config_kwargs`, no behaviour change), `scripts/realism_lab.py` (new), `requirements-dev.txt` (matplotlib), `docs/v1.3/lab/` (summary.json, BASELINE_c1.md, figures) | The run matrix (Appendix C) and the lab runner: resumable, one process per run, metrics.json + series.npz per run, aggregation, scenario analysis, figures, regression set. Campaign c1 run on 20 seeds (80 runs) |

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

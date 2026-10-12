# Decision log

One entry per decision, newest last. Dates are when the owner approved. Fields left as "—"
were not recorded at the time; they are not reconstructed. Entries up to 2026-10-09 are
seeded from spec v1.2, Appendix A. New decisions made while implementing are added below
them, with the evidence that led to them.

---

### 2026-10 (momentum spec v1.0) — MomentumEKFAgent design
- **Decision:** a log-price damped-trend Kalman filter, a warm-up fit, Kaufman-ER observation noise, a regime monitor, a state machine (NEUTRAL/BULL/BEAR/WATCH) with hysteresis, target-exposure sizing with a staircase ratchet, primed news handling, long-only, endowment 0.5.
- **Reason:** a trend follower that reasons about the speed and its uncertainty instead of fixed moving averages.
- **Alternatives:** the stock ABIDES 20/50 moving-average crossover (still present as `MomentumAgent`).
- **Evidence:** —

### 2026-10 (v1.0) — Endowment: our agents start 50% in stock
- **Decision:** our agents start with 50% of wealth in stock (50 shares at $1000).
- **Reason:** without shares, long-only fundamentalists could never act on "overvalued".
- **Alternatives:** —  **Evidence:** —

### 2026-10-08 (v1.1) — Delete the fundamentalist's ±1% nudge after each order
- **Decision:** remove the "step 9" rule that multiplied x̂ by 1.01 or 0.99 after every order.
- **Reason:** it made a $10 jump per order, equivalent to a phantom price thousands of dollars away; beliefs drifted to about $949.
- **Alternatives:** a herding tilt used only in decisions (deferred).
- **Evidence:** spec v1.1 §0.5(a), seed 42.

### 2026-10-08 (v1.1) — Process noise for the fundamentalist
- **Decision:** Q = q · σ̂_f² · dt, with σ̂_f² estimated from 300 s price changes (prior 3 cents²/s).
- **Reason:** without Q the gain fell like 1/n and the belief froze into an all-day average.
- **Alternatives:** a constant Q (rejected: it would not adapt to other oracle settings).
- **Evidence:** spec v1.1 §0.5(b), Appendix A1.

### 2026-10-08 (v1.1) — Smaller observation noise
- **Decision:** δ ∈ [0.0005, 0.003], λ_ER ∈ [0.5, 2].
- **Reason:** the old R said prices were $2.6–70 off when the real noise is cents to tens of cents.
- **Alternatives:** a self-calibrating R from innovations (deferred until the value agents are replaced).
- **Evidence:** spec v1.1 §0.5(c).

### 2026-10-08 (v1.1) — Target-position sizing
- **Decision:** a holding target from the edge, a step cap and a dead band replace flow sizing.
- **Reason:** the flow rule plus a 1-share minimum sold the whole endowment within 7–19 minutes.
- **Alternatives:** —  **Evidence:** spec v1.1 §0.5(d): 19 of 20 agents sold all 50 shares.

### 2026-10-08 (v1.1) — Volatility-scaled news
- **Decision:** news shift = sentiment · k_news · √(σ̂_f² · 1800 s), additive, with P += shift².
- **Reason (owner's idea):** scale news by how much the stock usually moves, not by a % of price; the added P makes the market confirm or fade the news.
- **Alternatives:** the spread as the scale (rejected: it measures liquidity, not movement).
- **Evidence:** spec v1.1 §0.5(e): the old rule moved beliefs by +$33.

### 2026-10-08 (v1.1) — Momentum M1–M7
- **Decision:** κ_l ∈ [0.02, 0.15], κ_v ∈ [1, 2]; detrended volatility; τ = tau_ratio · wake_mean with tau_ratio log-U[15, 40]; the ratchet cap follows down; re-entry needs T ≥ θ_out; a persistent stop exit.
- **Reason:** the filter saw only 26–28% of trend speed in the worst parameter corner; the trend counted as volatility; agents with τ/wake ≤ 5 could never enter; noisy re-entries.
- **Alternatives:** —  **Evidence:** spec v1.1 §0.5(f)–(k); docs/v1.1/REPORT.md.

### 2026-10-08 (v1.1) — Dashboard D1–D5
- **Decision:** off-scale line breaks, P&L vs holding, overlay agent selection, a market population panel with count controls, a price vs true value panel.
- **Alternatives:** —  **Evidence:** —

### 2026-10-08 (v1.1) — Deferred items
- Skewed initial noise; a self-calibrating R; the safety margin in uncertainty units; replacing value agents; two news types; the herding tilt.

### 2026-10-09 (v1.2) — Fundamentalist edge as a t-statistic
- **Decision:** z = gap / √(P + R) instead of gap / √P.
- **Reason:** overtrading and synchronised herding.
- **Alternatives:** —
- **Evidence:** spec v1.2 §0.4 P1: about 1,900 shares/day per agent on a 50-share endowment, all 20 in sync. With the fix: 168–231 shares/day, holdings 46–57 (10th–90th percentile), loss vs holding $5–13 instead of $80–110.

### 2026-10-09 (v1.2) — Pre-generated, seed-stable true-value path
- **Decision:** generate the whole true-value path at construction from one dedicated RNG.
- **Reason:** the lazy oracle made the true value depend on agent activity, which breaks counterfactuals and future user trading.
- **Alternatives:** historical data as the fundamental (rejected: it is a market price, not a value; kept as a future optional path source).
- **Evidence:** spec v1.2 §0.4 P2: same seed with vs without news, about $2 apart after 2 h.

### 2026-10-09 (v1.2) — Market-maker cold start and guaranteed rescheduling
- **Decision:** market makers anchor to a reference price when no book exists, and always reschedule their next wake.
- **Reason:** MMs died when the book was empty at their first wake; the market could not start without value agents.
- **Alternatives:** —
- **Evidence:** spec v1.2 §0.4 P3–P4. Reproduced 2026-10-09 (seed 42, 09:30–11:00, 5 + 4 of our agents): with 0 or 3 value agents each MM woke twice and placed 0 orders; with 0 value agents there were 0 trades. With 97 value agents each MM woke about 92 times and placed about 2,000 orders.

### 2026-10-09 (v1.2) — ValueAgents stay as scaffolding
- **Decision:** keep the 97 ValueAgents for now; replace them in R3 with fundamentalists that have a research channel.
- **Reason:** they currently provide information, about 83% of volume and the market's first prices.
- **Alternatives:** removing them directly (tested with 20, 3 and 0 value agents): either the same pinned market or a broken, illiquid one.
- **Evidence:** spec v1.2 §1.2 and Appendix A.

### 2026-10-09 — Roadmap
- R1 (spec v1.2) → R2 realism lab → R3 informed fundamentalists and value-agent replacement → R4 value dynamics and news types, MM inventory management → R5 calibration → R6 user trading.

---

## Decisions made while implementing v1.2

(Added by milestone; each with its evidence.)

### 2026-10-09 (W2) — Megashocks enter the OU state
- **Decision:** a megashock is added to the OU *state* at the first grid point at or after its time, and then decays with the OU dynamics (factor e^(−κd) per step), rather than being added as a permanent constant to all later points.
- **Reason:** it is what the sparse oracle does (`v_adj` is added to the state before the next OU step). With κ = 1.67e-16/ns the two readings differ by at most 0.39% of the shock size over a full 6.5 h day.
- **Alternatives:** a permanent additive offset (the literal reading of spec §3.1). **Evidence:** `test_megashocks_jump_the_state`.

### 2026-10-09 (W2) — The path always covers 09:30–16:00
- **Decision:** `rmsc04_ekf` builds the oracle for the full trading day (`NOISE_MKT_CLOSE`, as the sparse oracle was), not up to `end_time`.
- **Reason:** a 10:00 run then sees exactly the first 30 minutes of the 16:00 run's true value, so sessions of different lengths are comparable. Cost: 23,401 grid points (≈0.8 s to build).
- **Alternatives:** generate only up to `end_time`. **Evidence:** —

### 2026-10-09 (W2) — Market statistics keep 8 significant figures
- **Decision:** `api/export._round_tree` rounds statistics to 8 significant figures (was 6).
- **Reason:** at $1000, 6 figures cannot hold a half-cent mid: a close of $1000.705 was exported as $1000.71, so `stats.close` (and P&L vs holding computed from it) disagreed with the quotes. The new seed-42 path produced such a close and three export tests caught it.
- **Alternatives:** —  **Evidence:** `test_close_is_last_mid`, `test_payload_v1_1_fields`, `test_population_volume_shares`.

### 2026-10-09 (W3) — Cap on the market maker's adaptive spread
- **Decision:** `AdaptiveMarketMakerAgent(max_spread=…)`, set to 100 cents in `rmsc04_ekf`; the spread estimate is clamped and `MM_SPREAD_CAP` is logged the first time it binds.
- **Reason:** without value agents the market maker mostly observes its own ladder, so its spread estimate fed on itself: 1.6¢ at 10:05 → $46.50 at 10:15 (seed 42, 0 value agents, 5 + 4 of our agents). The ladder spread to levels $15–$232 apart, the price fell through the gaps toward 0 and the simulation stalled. Run Z (spec v1.2 §7.2) could not complete.
- **Alternatives:** inventory limits or skew for the market maker (that is R4, out of scope); leaving Run Z unrun.
- **Evidence:** with the cap a 1-hour run without value agents finishes in 2.5 s. With value agents the cap never binds (test `test_spread_cap_does_not_bind_in_default_market`); observed spreads there have a median of 1¢ and a maximum of 53¢ (v1.1 report).

### 2026-10-09 (W3) — Only the first market maker cold-starts
- **Decision:** keep spec §4.1's rule (cold start only without any mid). Test T-M6 checks "at most one MM_COLD_START per MM and at least one in the market" instead of "one per MM".
- **Reason:** the second market maker to wake already sees the first one's ladder, so it has a mid.
- **Evidence:** probe 2026-10-09: one cold start per run with 0 or 3 value agents.

### 2026-10-09 (W3) — Numerically stable caution sigmoid
- **Decision:** both of our agents compute C = 1/(1 + e^(−k·E)) with `agents.utils.stable_sigmoid` (identical values).
- **Reason:** in a market without value agents, −k·E exceeded 709 and `math.exp` raised OverflowError, crashing the simulation.
- **Alternatives:** clipping E. **Evidence:** crash reproduced with 0 and 3 value agents before the fix.

### 2026-10-09 (W3) — Exchange history records every fill price
- **Decision:** `OrderBook` EXEC history entries carry `price` = the resting order's limit price (upstream set it only for price-to-comply fills, else `None`).
- **Reason:** invariants I1 (hash of every execution) and I5 (every EXEC price > 0) need the price; nothing read the field before.
- **Alternatives:** reconstructing prices from agents' ORDER_EXECUTED logs (not all agents log orders).

### 2026-10-09 (W3) — Market makers never quote at or below zero
- **Decision:** buy levels below 1 cent are dropped from the ladder.
- **Reason:** a safety guard for crashing markets; it never matters with value agents present.

### 2026-10-09 (W4) — Determinism test with different hash seeds
- **Decision:** I1 runs the two processes with `PYTHONHASHSEED` 1 and 2.
- **Reason:** the most likely hidden source of non-determinism is iteration over sets or dicts of strings, which Python randomises per process; equal hash seeds would hide it.
- **Evidence:** I1 passes: the same sha256 of all executions and final holdings (seed 42, 09:30–10:30). No fix was needed.

---

## v1.3 (R2): the realism lab (spec v1.3, approved 2026-10-11)

Entries D-R2-1 … D-R2-5 are the owner's decisions recorded in spec v1.3 Part 1 and
Appendix B. Implementation decisions follow under "Decisions made while implementing v1.3".

### 2026-10-11 (v1.3, R2) — Realism lab, measurement only
- **Decision:** R2 changes no agent decision and no market default. New code is scenario tooling only (a scripted true-value path, a test order agent, switches whose defaults are inert). Enforced by invariant I8: with defaults the market is bit-identical to v1.2 (aa5f606).
- **Reason:** the owner wants information first, then changes; every later change is then judged against a 20-seed baseline (D-R2-2).
- **Alternatives:** fixing the known issues while measuring them (rejected: no clean "before" picture).
- **Evidence:** I8 hash recorded 2026-10-12 from aa5f606 (`docs/v1.3/lab/reference_hashes.json`).

### 2026-10-11 (v1.3) — D-R2-1: provisional bands from a large-cap reference
- **Decision:** a liquid large-cap moving about 1–2% a day: 5–10 bps per minute, |ac1| ≤ 0.10, kurtosis ≥ 3, gap std $1–3, gap half-life 30–90 min, regime contrast ≥ 5, spread median 1 tick / p95 ≤ 5, impact exponent 0.4–0.7. Provisional: revisited before R5.
- **Reason:** owner decision D-R2-1.
- **Alternatives:** a volatile mid-cap (2–4% a day); not chosen.  **Evidence:** —

### 2026-10-11 (v1.3) — D-R2-3: scenarios S1–S8 in scope; S3 = value jump + ordinary headline
- **Decision:** every scenario the tooling allows is run. S3 is a true-value jump plus an ordinary headline at the same second; agents do not distinguish news types until R4. S4 is today's news (beliefs only, "hype").
- **Reason:** owner decision D-R2-3.  **Alternatives:** —  **Evidence:** —

### 2026-10-11 (v1.3) — D-R2-4: the heavy-trader fundamentalist stays
- **Decision:** keep it; fundamentalist group statistics are medians and quantiles, never means; the lab watches the largest fundamentalist's volume share (flag if > 1% on any seed).
- **Reason:** 1,433 shares, 0.12% of volume (seed 42, measured 2026-10-11); its draw is the aggressive corner of most ranges, a personality, not a bug.
- **Alternatives:** a floor on R (v1.2 open question 2); deferred.  **Evidence:** spec v1.3 §0.4.

### 2026-10-11 (v1.3) — D-R2-5: budget limits for the ABIDES agents stay in R3
- **Decision:** R2 measures price impact while value agents can short without limit; the numbers are the "before" picture and are re-measured after R3.
- **Reason:** owner decision D-R2-5.  **Alternatives:** —  **Evidence:** —

### 2026-10-11 — Owner correction of the spec owner line
- **Decision:** the owner line of the specs is "Owner: Apratim Anand, IIT Bombay."; `docs/specs/spec_v1.1.txt` and `spec_v1.2.txt` corrected (that line only).
- **Reason:** owner correction.  **Evidence:** —

---

## Decisions made while implementing v1.3

(Added by milestone; each with its evidence.)

### 2026-10-12 (L3) — A value jump decays 0.3% over 5 hours, not 0.0003%
- **Decision:** T-L2 checks the exact decay J · a^(k − k0) (to 1e-6 ¢) and that the 16:00 value is ≥ 99.7% of the jump, instead of spec §6.1's "less than 0.0003% over 5 hours".
- **Reason:** a = e^(−κ · 1 s) = e^(−1.67e-7); over 18,000 s that is e^(−0.003), a 0.30% decay ($20.00 → $19.94; measured 1993.997 ¢ of 2,000). The spec's number is a factor-1000 slip; "permanent in practice" stays true. Nothing in the generator changes.
- **Evidence:** `test_scenarios.py::test_l2_jump_adds_a_decaying_step`.

### 2026-10-12 (L2) — 20 distinct seeds: 42, 7, 1–6, 8–19
- **Decision:** `api.lab.SEEDS = [42, 7, 1, 2, 3, 4, 5, 6, 8, …, 19]`.
- **Reason:** spec §5.0 writes "[42, 7, 1, 2, 3, ..., 18] (20 seeds)", which contains 7 twice (19 distinct seeds). The first c1 report counted seed 7 twice; found and fixed before the c1 numbers were used. 42 and 7 keep continuity with v1.1/v1.2.
- **Alternatives:** 19 seeds (literal list).  **Evidence:** c1 heavy-trader table listed seed 7 twice.

### 2026-10-12 (L2) — The lab schedules its own processes instead of a multiprocessing Pool
- **Decision:** `scripts/realism_lab.py` starts one spawned `Process` per simulation, at most `--workers` at once, and terminates one that runs over 15 minutes.
- **Reason:** spec §7.1 asks for one simulation per process (Pool with maxtasksperchild = 1) **and** a per-run timeout. A Pool cannot kill one stuck task: its AsyncResult never completes when a worker is killed. The manual scheduler gives the same one-run-per-process isolation with a working timeout.

### 2026-10-12 (L2) — Workers sized by memory
- **Decision:** c1 ran with 4 workers, not the default 6.
- **Reason:** a full day uses ≈ 470 MB per process; the development laptop had 2.1–2.9 GB free with 16 cores.

### 2026-10-12 (L1) — The half-life estimator is kept as specified; its bias is reported
- **Decision:** `gap_half_life_min` is `api.stats.gap_half_life(gap, LAB_GAP_LAGS)` exactly as spec v1.3 §3.7 defines it. T-R8's 45-min and 90-min cases are strict xfails with the measured bias in the reason.
- **Reason:** on one 6.5 h day the de-meaned sample ACF is biased low for long half-lives: a true 45 min reads as 20.8 min (−54%), 90 min as 27.1 min (−70%) (median of 20 synthetic AR(1) paths). This is the estimator's mean-removal bias, not a coding error. Changing the estimator would change what G10 grades, which is the owner's call (bands are revisited before R5).
- **Alternatives:** not de-meaning (tested: 45 min → 31.5 min, 90 min → 51 min, but p10–p90 widens to 26–128 min); pooling seeds. Not adopted in R2.
- **Evidence:** `api/tests/test_realism.py::test_r8_gap_half_life` (run with `-s`).

### 2026-10-12 (L1) — Boundaries: one rule for every band
- **Decision:** every band interval is closed and PASS is tested first, so every boundary takes the better grade (§4.2). This makes G5's "PS > 0.03" pass at exactly 0.03 and G13's ratio of exactly 0 a WARN although the table writes "≤ 0" under FAIL.
- **Reason:** T-R11 requires every boundary of every band to take the better grade; a ratio of exactly 0 has probability zero with real data.

### 2026-10-12 (L0) — I8 recorded from aa5f606 with PYTHONHASHSEED=0
- **Decision:** I8 reuses I1's fingerprint script (same EXEC and holdings hashes) in a fresh process with `PYTHONHASHSEED=0`; the expected values are constants in `test_invariants.py`. The full-day run A hash is stored in `docs/v1.3/lab/reference_hashes.json`.
- **Evidence:** I8: 2,448 executions, 121,622 shares. Run A: 13,759 executions, 608,106 shares (equal to spec §0.4's independent measurement).

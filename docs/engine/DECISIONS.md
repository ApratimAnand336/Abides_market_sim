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

### 2026-10-12 (L5) — Four c4 runs re-run after the laptop suspended
- **Decision:** S7a seeds 12–15 were re-run; their first attempts are not used.
- **Reason:** the c4 log jumps from 3.5 to 334 minutes elapsed between two consecutive completions while every other run took 21–32 s: the machine was suspended with those four runs in flight, and on wake the 15-minute watchdog killed them. Re-run normally (28–31 s each). Nothing else in the campaign was affected (a run's result does not depend on wall-clock time).
- **Evidence:** `runs/_lab/c4.log`.

### 2026-10-12 (L4) — C-NULL baselines are not needed
- **Decision:** the impact runs use C-DEF on the same seed as their baseline (spec §5.4). C-NULL (probe with quantity 0) was not run.
- **Reason:** T-L6 passes: the 1-hour I8 market with a null probe gives the I8 EXEC and holdings hashes exactly. The latency model is deterministic (no per-message random draws), the probe's coordinate is drawn after every existing agent's, its RandomState is a constant, and the exchange has zero computation delay, so the probe's start-up messages change nothing for the other agents. T-L7 adds that a 600-share probe leaves every other agent's parameters and RNG state, and every execution before its start, unchanged.
- **Evidence:** `test_scenarios.py::test_l6_null_probe_is_neutral`, `test_l7_probe_uses_no_global_rng`.

### 2026-10-12 (L4) — The probe records its own arrival mid
- **Decision:** with its first child the probe sends a spread query just before the market order and logs PROBE_ARRIVAL_MID; PROBE_SUMMARY carries it. The lab's shortfall uses the spec's arrival mid, mid_B(t0) from the baseline series.
- **Reason:** spec §6.2 asks PROBE_SUMMARY to include arrival_mid, but a probe that sends nothing cannot know the mid. The query is answered before the order (messages are delivered in send order) and only touches the treated run after t0.

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

---

## v1.4 (R3): informed fundamentalists replace the value agents

Spec: [`docs/specs/spec_v1.4.txt`](../specs/spec_v1.4.txt) (Part 1, Appendix B).

### 2026-10-12 (v1.4, R3) D-R3-1: replace the ValueAgents with informed fundamentalists (ours)
- **Decision:** the FundamentalistAgent gains an "informed" mode (research channel, belief-anchored pricing, quotes into an empty book, budget limits). It replaces the 97 ABIDES ValueAgents in the default market from N6. The ValueAgent code is not modified.
- **Reason:** we should not depend on stock agents we do not control. R2 showed that their book-anchored pricing (buy at ask − U[0, 2·spread], whatever the mispricing) causes most failures (spec v1.4 §0.3).
- **Alternatives:** patch the ValueAgent's pricing (rejected by the owner).

### 2026-10-13 D-R3-2: R3 stays focused
- **Decision:** no oracle changes, no market-maker inventory management and no new news types until R4. Volatility, clustering and regimes are not judged in R3.

### 2026-10-13 D-R3-3: R3 graded on real-world-checkable measures
- **Decision:** T1–T7 and L1–L5 (spec v1.4 Part 2). Gap size and gap half-life are simulator-only diagnostics.
- **Reason:** no real market has an oracle. Real mispricing is measured indirectly, through autocorrelation, variance ratios and event studies.

### 2026-10-13 D-R3-4: corrected half-life
- **Decision:** no de-meaning, plus a synthetic correction table (spec v1.4 §3.1). G10 grades the corrected value, and the v1.3 estimator is still reported.
- **Reason:** on one day, the v1.3 estimator reads a true 45 min as about 25 min and a true 90 min as about 29 min.

### 2026-10-13 D-R3-5: ABIDES budget limits
- **Decision:** gross limit 2× wealth on NoiseAgent, ValueAgent and the ABIDES MomentumAgent. Market makers are exempt until R4. The effect is measured alone first (config C-BL).

### 2026-10-13 D-R3-6: multi-day sessions after R6.

### 2026-10-12 (N0) sim_data.pkl: clean
- **Decision:** the owner confirmed that the tracked `sim_data.pkl` is restored (`git status` shows it unmodified). v1.4 runs therefore carry no "+dirty" engine_version label. The spec's owner action before N0 is done.

### 2026-10-12 (N1) T-N9 coverage: the spec's "≥ 80%" is not met by the §3.1 h_range — reported, not changed
- **Decision:** h_range is implemented exactly as §3.1 defines it: [min, max] of the table H whose p10..p90 interval contains h_read. T-N9's coverage assertion is a strict xfail with the measured value. Reproducibility, monotonicity and the bracketing property of h_range are tested normally.
- **Evidence:** on the T-N8 paths (default_rng(1), 40 per H), h_range contains H for 59% of paths (H 1.5: 0/40, 10: 29/40, 45: 36/40, 90: 29/40).
- **Reason:** H = 1.5 is not a table point. Its readings (1.4–1.7 min) fall in the gap between the p10–p90 intervals of H = 1 (0.87–1.42) and H = 2 (1.66–2.71). At table points, coverage is about 80% by construction, so "at least 80%" is a coin flip. The spec is inconsistent here; how to fix it (for example a finer H grid or interpolated p10/p90 bands) is the owner's call. G10 and every graded number use h_corrected, not h_range.

### 2026-10-12 (N1) G10 switched to the corrected half-life; encodings
- **Decision:** G10's key becomes `gap_half_life_corr_min` (band unchanged), as §3.1 requires. T-R11's G10 boundary cases now name that key.
- A reading above the table's last median is stored as None with `gap_half_life_corr_above = true` and reported as ">240 min". G10 grades it FAIL (above 180 min it would be a FAIL either way). For the median across seeds, the lab uses the §3.1 "correction of the median h_read", which has no such gap.
- T1 uses |median ac1| (G3's convention). L3 is graded as "every half-hour has a trade" (`active_halfhours_share` = 1).

### 2026-10-12 (N1) Half-life table: no isotonic fit needed; the slow end is flat
- The 16 medians are strictly increasing (`monotone_raw: true`). Above H = 90 min they are nearly flat (59.3, 63.1, 67.8, 92.5 min for 90, 120, 180, 240), so the correction is poorly determined there. This is reported in REALISM_LAB.md; nothing is tuned.

### 2026-10-12 (N2) Budget: open orders in flight count as open
- **Decision:** `GrossLimit` counts every order still in `TradingAgent.orders`, including orders whose cancellation has been sent but not yet confirmed.
- **Reason:** §5.1 is a worst-case rule ("open same-side quantity"). An order whose cancellation is in flight can still fill. For ValueAgents, which cancel and re-order at each wake, this makes the limit bind a little earlier. It is reported with the block counts.

### 2026-10-12 (N2) Campaign runs use a committed engine: N2 is two commits
- **Decision:** the N2 code (budget, tests, lab plumbing) is committed first. Campaign b then runs on that clean engine label, and its report is committed as a second N2 commit.
- **Reason:** a campaign needs the code committed before it runs, or every run is labelled "+dirty" (the owner restored `sim_data.pkl` so that labels would be clean). From N3 on, a milestone's campaign runs on the previous milestone's commit, so N4 is again a single commit.

### 2026-10-12 (N3) Informed mode: readings of the spec where it leaves a choice
- **First cycle.** Step 0 goes straight to step 6, so the first cycle makes no market reading, no caution update and no target order, even with a two-sided book. It posts the two quotes only. W_ref = cash + shares·x̂ ("W if mid exists" refers to step 5's W, which is not computed). FUND_DECISION is logged with z…w_now = None and skipped_reason "first_cycle" (or "no_mid" for a later cycle with an empty book).
- **EKF_UPDATE keys.** "R" is R_noise (the v1.2 R) and "K" is K_m; R_m, rho and K_m are added as §4.3 lists. The target uses R_noise in z (§4.3 step 5), and the agent's `R_last` stores R_noise.
- **Draw order.** The informed draws (wake_mean, rho, m0, kappa_m, h0, theta_q, T_r, sigma_r) come right after the agent's FUNDAMENTAL_RANGES draws and before its RandomState seed (§4.6 "after the existing FUNDAMENTAL_RANGES draws"). In a price_only market nothing new is drawn (I8 holds; T-N6).
- **Unchanged type.** The agent type string stays "EKF_Fundamentalist" and the class is unchanged, so the lab and the payload classify informed agents as FundamentalistAgent. The label "Fundamentalist (informed)" is a dashboard change (N6).
- **Payload export deferred.** `INFORMED_RANGES` is defined but not yet in `ranges_for_export()`: the payload schema only accepts "fundamental" and "momentum" (13 export tests failed when it was added). Spec Part 6 changes the payload, schema and dashboard together in N6.
- **Budget arithmetic is shared** with the ABIDES gross limit (`utils/budget.allowed_qty_wealth`); B and S count only this cycle's orders, as §4.5 says.

### 2026-10-12 (N4) Campaign s1: no design passes L1/L2/L4/L5 — §7.4 names no winner; stopped for the owner
- **Finding:** step 1 of the pre-registered rule rejects all 16 round-1 designs: L1 (median spread ≤ 2 ticks) fails in 14 and L2 (volume ≥ 295,500) in 7. Round 2 is defined from a round-1 winner, so it cannot start. No parameter was tuned, and the selection code was not changed to produce a winner. The full printout and table are in `docs/v1.4/lab/RESULTS_s1.md`.
- **Gap in the spec:** §7.4 and §2.4 have no rule for "no design passes the limits". Possible ways forward include choosing among the closest designs (D-60fl2M misses only the L1 median by 1 tick; D-120fl500k misses only L2 by 10%), running round 2 around one of them, or revisiting L1 for a market without ValueAgents. Any of these is the owner's decision.

### 2026-10-12 (N4) Lab flag `long_only` split like I4
- **Decision:** `series_from_end_state`'s `long_only` flag now covers only price-only fundamentalists and momentum EKF agents. A new `informed_bounds` flag checks informed agents within [−0.5, 1.5] × wealth at each fill price (one-share tolerance), from ORDER_EXECUTED + HOLDINGS_UPDATED.
- **Reason:** I4 was split in N3 (spec §10.4), but the lab flag still applied the long-only rule to informed agents, which short and borrow by design. Every s1 run therefore recorded `long_only: false`.
- **Evidence:** D-60fl2M seed 42 was re-run with the fixed flag: book_sanity, long_only, informed_bounds and conservation are all true, and the executions are bit-identical to the campaign run. The stored s1 metrics keep the old flag values; the momentum agents' long-only property in those runs is covered by this re-run and by the tests (I4, T-N5).

### 2026-10-12 (N4) L5 timing: probe vs campaign
- The single-run probe of D-120fl2M took 101 s (seed 42). Its 5-seed campaign median under 2 workers is 74 s, and every design's median is ≤ 76 s, so L5 passes everywhere. The variation is machine load (the probe ran while other applications were using memory: 2.5 GB free).
- Profile (1.5 h of D-120fl2M): 40% of the time is in `OrderBook.get_imbalance`, which sums every price level on each book event for the market makers' imbalance subscriptions. An exactly equivalent faster version is possible, but it would change ABIDES core code, so it is left for the owner to decide (not needed for L5 now).

---

## v1.4.1 (amendment to R3): learning from prices and corrected limits

Spec: [`docs/specs/spec_v1.4.1.txt`](../specs/spec_v1.4.1.txt), approved by the owner on 2026-10-13.

### 2026-10-13 (N4a) Spec error: L1 and G8 were written in absolute ticks
- **Decision:** spreads are judged in bps of the mid: spread_bps = 1e4·(ask − bid)/mid. L1 passes when spread_med_bps ≤ 2.5 and spread_p95_bps ≤ 10. G8 passes when the median is ≤ 2.5 bps and the p95 ≤ 10 bps, and warns when the p95 is ≤ 25 bps. The tick metrics are still reported.
- **Reason:** for a $1000 stock, 1 tick = 0.1 bp. "Median ≤ 2 ticks" demanded 0.2 bp, which is tighter than AAPL. Real liquid large caps trade at about 1 bp (AAPL, MSFT); the 10 largest S&P 500 stocks trade at about 2.5 bps and the index at about 4.5 bps (Nasdaq, "Sampling the S&P 500 to minimize spreads", https://www.nasdaq.com/articles/sampling-sp-500-minimize-spreads). The correction rests on that external reference, not on the round-1 numbers.
- **Evidence:** the re-graded G8 of the v1.3 markets is unchanged: PASS (C-DEF median/p95 0.1/0.3 bps; C-V20 0.1/0.4). T-R11's G8 boundary cases now use the bps keys. The dashboard's Realism tab renders G8 from the band's own metric keys and unit.

### 2026-10-13 (N4a) Spec error: T6 used an absolute tick spread
- **Decision:** T6 = one_sided_share_jump ≤ 1% AND spread_jump_ratio ≤ 3.0, in both S2 and S2n. spread_jump_ratio is the p95 spread_bps of the treated run in [t0, t0 + 30 min] divided by the same seed's baseline in the same window, as a median over seeds. New limit L6: the median over seeds of the day's max |mid − value| must be ≤ $10 in run C.

### 2026-10-13 (N4a) Round 1 re-evaluated under the corrected rules (§3.1, record only)
- No new runs; the new metrics are recomputed from the stored s1 `series.npz` by the same functions as `run_metrics` (`scripts/lab_v14._augment_from_series`).
- **Result:** L1 and L6 now pass in all 16 designs. The 8 designs at $500k still fail L2. Among the 8 at $2M, the v1.4 §7.4 rule (T5/T6 on S2 only, as round 1 has no S2n runs) picks D-60fl2M with 5/7 targets: T3 and T6 fail.
- T6 fails everywhere: spread_jump_ratio 8.7–49. T3 (1-min vol ratio, 0.45–0.74) fails everywhere. Tables: `docs/v1.4/lab/RESULTS_s2.md` §1.

### 2026-10-13 (N4b) Learning from prices: implementation notes
- The mechanism is implemented exactly as §2.2 (`FundamentalistAgent.price_learning_step`). The levels mod/strong follow §2.3: `eps_thr` and `a_pl` are drawn after the agent's T_r and σ_r draws and before its RandomState seed, and nothing is drawn for "off". "off" keeps the v1.4 code path and the v1.4 EKF_UPDATE keys (T-N16: identical agents and fingerprint).
- `P_inflated` is logged as true when the covariance matching actually raised P (g > 1 and (ε̄ − ε_thr)(P + R_noise) > P).
- The T-N18 numbers agree with the spec's hand simulation. A persistent 2,000¢ gap is adopted 59–96% at look 3 and 95–100% at look 4 (mod); 76–96% at look 2 (strong). A two-look 800¢ blip moves the belief by less than 20¢ (mod). N(0, 40¢) noise never triggers g > 1 in 3,000 looks.
- Lab: design ids gain an optional level suffix (`D-60fl2M-mod`). Designs without a suffix keep their v1.4 build arguments and config hashes, so the stored s1 runs stay valid. S2n configs are registered for every s2, refinement and round-1 design. Refinement candidates (§3.4) are registered at import so that spawned workers know them.

### 2026-10-13 (N4c) Campaign s2, the 32-candidate selection, refinement: STOP per §3.5
- **W fixed at $2M in s2** (§3.2): in round 1, 7 of the 8 designs at $500k failed L2 (liquidity).
- **Round-1 designs in the §3.3 selection** enter as re-evaluated by §3.1, with T5/T6 on S2 only (they have no S2n runs). This favours them by at most one target (T5); they fail T6 on S2 in any case. The printout says so.
- **Result.** The selection over 32 candidates picks D-60fl2M (no learning; 5/7 targets). It ties on targets with D-60fl2M-mod and -strong and wins the tie-break on the T3 miss (0.452 vs 0.455). It fails T3 and T6, so the refinement round runs. N = 30 fails L2 (279k), N = 240 fails L5 (186 s), and D-60fl5M ties on 5/7 but loses the tie-break by 0.002, so D-60fl2M stays. It still fails T3 (vol ratio 0.49) and T6 (spread_jump_ratio 8.7 / 16.7), so §3.5 requires a STOP and a report to the owner. N5 is not started.
- **Finding: learning from prices slows jump pricing.** Off → mod / strong: t90 +5.8 / +16.1 min. A diagnostic run (seed 42) shows that 55–70% of learning-driven belief moves after a jump go toward the stale price, and they are 2–3× larger. Researched agents doubt their new information because the price lags. The mechanism was implemented exactly as specified; whether and how to change it (for example, suspending learning for agents with fresh research, or using an asymmetric gate) is the owner's decision. Details: `docs/v1.4/lab/RESULTS_s2.md` §6.
- **Run conditions (L5 is a wall-time limit, so run conditions matter):**
  - s2 was interrupted after 142/240 runs when Claude Code's memory reaper stopped the job. It resumed on the same clean engine (v1.3-0d20335); the runner skips finished runs.
  - A resume with 3 workers slowed the 120-agent runs to 89–95 s (about 75–82 s with 2). Those 3 runs were set aside (`metrics_3workers.json.bak`) and re-run with 2 workers, so every s1/s2 design is timed under the same condition.
  - D-240fl2M (about 2 GB per run) ran one at a time for memory safety; its L5 failure (186 s) is under the most favourable condition.
  - Late s2 runs became slower (82 → about 100 s) under unchanged settings; this decides only D-120sh2M-strong's L5 rejection (99.7 s), and that design ranks below the winner anyway.
  - To keep the engine label clean while the report code was still uncommitted, `scripts/lab_v14.py` and the generated reports were set aside with `git stash` during the runs. Two stash entries hold only stale generated reports (safe to drop).

---

## v1.4.2 (amendment 2 to R3): close R3, faster engine, trimmed runs

Spec: [`docs/specs/spec_v1.4.2.txt`](../specs/spec_v1.4.2.txt), approved by the owner on 2026-10-13.

### 2026-10-13 D-R3-7: the R3 design is D-60fl2M, price learning off
- 60 informed fundamentalists. Research interval log-U[60, 300] s, research noise log-U[10, 50]¢, $2M each.
- In screening it passes T1, T2, T4, T5, T7 and every limit L1–L6.

### 2026-10-13 D-R3-8: R3 closes with T3 and T6 open (carried into R4)
- **T3:** the price/value volatility ratio is 0.49 at 1 min, 0.73 at 15 min and 0.93 at 60 min.
- **T6:** the spread p95 after a ±2% jump is 8.7× / 16.7× the baseline. The book never empties.
- **Why R4:** both need liquidity that stays tight while informed traders disagree, and short-horizon price variation that does not come from research arrivals. That is R4's market-maker and endogenous-volatility work. Recorded as K14 and K15 in N7. No further R3 design sweeps.

### 2026-10-13 D-R3-9: learning from prices is a documented negative result
- The rule is symmetric, so an agent that has just researched the new value is pulled back toward the stale price.
- The spec's hand simulation tested only an un-updated agent; that was a spec error.
- The code and its tests stay, with default "off".
- R4 candidate (not implemented): a one-directional variant, with no learning for an agent whose last research reading is younger than its research interval.

### 2026-10-13 D-R3-10: bit-identical engine speed-up before the remaining campaigns (N4d, below)

### 2026-10-13 D-R3-11: trimmed campaigns
- step: P97/50/20 on 10 seeds (C + S2); P0 on 20 seeds (C, S2, S2n).
- final on P0, 20 seeds: IMP-0, IMP-0.5, IMP-1, IMP-5, IMP-1s, S4; plus P0-MM0 on 5 seeds.
- 245 runs; S5 dropped. The 10-seed steps show the trend and decide nothing.

### 2026-10-13 (N4d) OrderBook running visible totals (ABIDES core, bit-identical)
- **Change.** `OrderBook._vis_bid_qty` / `_vis_ask_qty` are adjusted at every site that changes visible resting quantity, and `get_imbalance` reads them instead of summing every order. Its formula and return values are unchanged: the same integers.
  - Sites: enter_order; execute_order (full pop, partial fill, price-to-comply other half, removed or decremented); cancel_order; modify_order and partial_cancel_order (delta of the visible quantity); replace_order (through cancel + enter).
  - Hidden orders are excluded, as in `PriceLevel.total_quantity`.
- **Guard.** `OrderBook.DEBUG_TOTALS` (default False) asserts totals == full recomputation after every public handler and in get_imbalance.
  - T-S1: every upstream orderbook/ unit test runs with the flag on (orderbook/conftest.py); a hand-built book covers hidden orders, partial cancel, modify up/down, replace and fills; a 1-hour default market and a 1-hour D-60fl2M market also run with the check on.
  - T-S2: the full-day D-60fl2M-S2 seed-42 fingerprint recorded before the change (`docs/v1.4/lab/reference_hashes.json`, equal to the stored s1 run) is reproduced, and I8 holds.
- **T-S3 (one full D-60fl2M day, seed 42, 1 worker, same machine, alternating old/new engine):** before 63.6 and 62.7 s; after 48.9 and 48.0 s, about **−23%**.
  - The profile had attributed about 40% to get_imbalance, but the old per-event summing also overlapped with other work.
  - After the change, no single hotspot remains: deepcopy of orders (about 15%) and `fmt_ts` in debug log calls that are formatted even when debug logging is off (about 8%) lead. Those are left for R4 (they touch ABIDES core logging/messaging).

### 2026-10-14 (N6) The default switch: where the default lives, budget auto, I8 re-recorded
- **Where.** "The default market" is the RunParams / `api.jobs.run_config_kwargs` path (dashboard, CLI, tests through `build_run_config`). RunParams defaults: num_fund 60 (0..200), num_mom 12, fund_mode "informed", num_value 0, budget None. run_config_kwargs passes `param_ranges.DEFAULT_INFORMED_DESIGN` (D-60fl2M, learning off).
  - `rmsc04_ekf.build_config`'s own keyword defaults are unchanged: it is the low-level, legacy-compatible API, and every inert v1.3/v1.4 switch default keeps its meaning.
  - Check: a full default day (seed 42) has the same fingerprint as the lab's P0-C seed-42 run (20,518 executions).
- **budget = None (auto)** means on for informed and off for price-only. RunParams needs a budget field to express the legacy market (num_value=97, num_fund=20, fund_mode="price_only"); with "auto", those three parameters alone reproduce v1.3.
- **The lab pins the v1.3 base for every config** (num_fund 20, num_mom 12, num_value 97, price_only, budget off), exactly as before the switch. v1.4 configs set their population through `params` / `extra`, so the lab's markets are unchanged; regression and regression-legacy both pass.
- **I8 re-recorded** on the new invariant market (spec v1.4 §10.4: the default market, 09:30–10:30, seed 42, num_fund = 30): execs `bf455dc7…1579`, holdings `39be7b70…0b90`, 1,925 executions. **I8-legacy** keeps the v1.2/v1.3 hash (execs `5cfff6b2…c1f5`, 2,448 executions) for the legacy test market (5 price-only fundamentalists, 4 momentum, 97 value agents, no budget). The explicit-default tests (T-L4/L6/L8/L9) now run on the invariant market. T-N6 (price_only) and T-N13 (budget None) compare the legacy market with I8-legacy.
- **T-M6 (cold start) gets its own market** (no value agents AND no fundamentalists). In the default market, informed agents quote into the empty book before the market makers wake, so the cold start is never needed; T-M6 tests the market makers' cold start. Liveness (T-M7) keeps "no value agents" (now the default).
  - Measured on the way: in the no-fundamentalist market one MM woke 52 times in the hour (90% floor: 54). That is about one sd below Poisson(60) with reshuffled seeds; the test was not loosened.
- **Payload (spec §6.3).** Detailed series are stored for ≤ 20 fundamentalists (evenly spaced over the sorted ids). The others keep their start/end holdings and every summary field; their value_1m and fills series are dropped.
  - Without that trim, 200 fundamentalists gave 11.45 MB, of which 7 MB was those series.
  - Sizes (full day, seed 42): the default day 4.60 MB; 200 fundamentalists 4.46 MB (limit 9 MB).
- **Regression (spec §10.5).** P0-C / P0-S2 / P0-IMP-1 on seeds 42, 7, 1 against `docs/v1.4/lab/summary.json`; the old set is kept as `regression-legacy`.
  - G11 regime contrast is not compared for P0-S2: in a jump run it is dominated by the jump window (median 45 vs 2.5 quiet), and seeds 42 and 1 are the 20-seed maximum and runner-up, so the fixed 3-seed median (64.5) always fell outside [34.4, 57.5]. The regression values equal the lab's per-seed values exactly.
- **CLI.** `python -m api.cli export` defaults follow RunParams (60/12, informed); `--num-value` and `--fund-mode` reach the legacy market.

## v1.5 (R4): a living market, realistic crashes, circuit breakers

Spec: [`docs/specs/spec_v1.5.txt`](../specs/spec_v1.5.txt), approved by the owner on 2026-10-15/16. Branch `v1.5` from 20465e2.

### 2026-10-16 D-R4-1: default days are a random mix of day types
- 30% calm, 50% normal, 20% volatile; no crash days in the default. Target stays a liquid large cap, 1–2% a day.

### 2026-10-16 D-R4-2: automatic information news by default
- Rate by day type; template headlines with stored FinBERT scores (runs never call FinBERT). Scripted news stays available.

### 2026-10-16 D-R4-3: our own RetailTraderAgent crowd replaces the ABIDES NoiseAgents
- Fixes gaps G-a … G-e of spec §0.4 (no reaction, one order a day, no positions/stops, no types, stock agent).

### 2026-10-16 D-R4-4: 2–4 market makers of our own with realistic capital
- Count and capital chosen by the pre-registered sweep (spec A7).

### 2026-10-16 D-R4-5: fix K16 (informed budget exceeded after jumps)

### 2026-10-16 D-R4-6: crashes exist only on demand, never scripted
- Three kinds (flash/liquidity, information, rumour) × two severities, selected explicitly. A scenario sets only the trigger and the fragility; the path comes from the agents.

### 2026-10-16 D-R4-7: circuit breaker after Parts A and B, optional, off by default

### 2026-10-16 D-R4-8: engine run time down further, bit-identical results

### 2026-10-16 D-R4-9: owner standing rule
- Never compromise accuracy or quality; shortcuts only if they give as good or almost as good results.

### 2026-10-16 (A0) Pre-run check of the A3.3 value statistics (record only, no change)
- An independent numpy simulation of A3.1 (written from the spec text, not from the spec's own check) gives, over 1,500 days per type: 1-min sd median 3.76 / 6.37 / 11.02 bps and daily move sd 0.80% / 1.32% / 2.39% (calm / normal / volatile).
- Over 200-day samples (seeds 1–4) the daily sd varies by about ±8% (normal: 1.23–1.43%).
- The 1-min values agree with A3.3 within 4%. The normal-day daily sd (spec 1.49%) is about 11% above the long-run value, so T-O5's ±10% band on that one statistic may be met or missed on sampling noise alone. T-O5 is implemented as written in A3; its result is reported as measured.

### 2026-10-16 (A1) Bit-identical engine speed-up: what changed in ABIDES core and why it is safe
- Spec A1.2 names the targets (order deepcopies, eager log formatting, depth logging, other hotspots). The profile (`docs/v1.5/PROFILE.md`) showed different weights from the v1.4 estimate: the agent-side order deepcopy was only ~0.4 s of a 59 s profiled day, while logEvent's deepcopy of every event (5.6 s), eager debug formatting (~4.5 s), the locked PriorityQueue (~4 s), `fmt_ts` via pandas (~4 s) and the end-of-day `iterrows` scan of `book_log2` (8.7 s) led.
- Seven changes, each identical by construction and by a unit test (table in PROFILE.md): kernel heap without lock; exact `deepcopy` replacement for plain events; `isEnabledFor` guards on 68 eager log statements; pandas-free `fmt_ts`; `get_time_dropout` without `iterrows`; no agent-side order copy (A1.2a); `book_log_depth_interval_s` (A1.2c).
- **Result:** 22.69 → 12.13 s per full P0 day (−47%, 1 worker, median of 3); 24/24 runs share the v1.4 fingerprint (T-S4); T-S5 lab metrics identical with sparse depth.
- **Sparse depth is a lab-only setting:** `api.lab.lab_config` sets `book_log_depth_interval_s = 1.0` (LAB_BOOK_LOG_DEPTH_INTERVAL_S) unless a config overrides it; `build_config`'s default stays None (every event), so the dashboard's depth chart and I8 are untouched. Lab code reads only L1 from `book_log2`.
- The ABIDES stock agents (noise, value, market maker) needed no change: none of their log calls formats eagerly.

### 2026-10-16 (A3) living_v1: implementation choices and one spec-number finding
- **Day-type draw always made.** A3.2 lists "1 day type (if auto: u ~ U(0,1) ...)". The uniform is drawn in every case and used only for "auto", so a requested type equal to the drawn one gives the identical path (T-O6) and a seed's later draws do not shift with the request. With a fixed day type the request simply replaces the drawn type.
- **U normalisation over the oracle grid**, which build_config always generates for the full 09:30–16:00 session (whatever end_time), so c_U and the path do not depend on session length (T-O7).
- **Stress chain convention:** S_0 = 1 (start in state 1); u_k decides the transition after step k; computed episode by episode (identical to the loop, test). p_in and p_out are per grid step, i.e. per second on the 1 s grid.
- **Signs and templates:** sign = + if a uniform < 0.5; template index = randint(bucket size), the last draws, so the path never depends on the templates (the oracle can be built without them).
- **Agents unchanged** (A3.7 "everything else v1.4"): informed agents learn the value speed sigma_f2_hat online from the market, so no parameter follows the faster value.
- **Spec-number finding (T-O5).**
  - Measured vs A3.3: the 1-min sd matches for every type and the mix (within 5%); daily sd matches for calm, volatile and the mix (within 9%).
  - Normal-day daily sd measures 1.28% (seeds 0–199; 1.32% over 1,500 days) vs 1.49% in A3.3 (−14%). That one case is `xfail(strict=True)` with this reason.
  - The model is not changed (nothing is tuned outside a pre-registered sweep). The default mix still gives 1.43%/day, inside the 1–2% target.
- **Component campaigns run C + S2.**
  - A3.7/A4.5/A5.5 count 10 runs each (C only), but "T-measures vs P0" includes T5/T6, and E-A3 is a post-jump spread ratio; both need the +2% jump run.
  - So each component runs C and S2 on the first 10 lab seeds, plus the same-seed P0-C/P0-S2 rerun on the current engine as the reference: 40 runs per component instead of 10.
- **Two commits for A3** (code, then campaign results), as N5 did: lab runs record the engine label, which must be a clean commit.

### 2026-10-16 (A4) Retail crowd: implementation choices
- **Trader wakes:** traders keep the standard TradingAgent start wake (market hours and the close-price request that end-of-day mark-to-market needs) and one wake at the open, then act only on crowd messages.
  - `RetailTraderAgent.wakeup` must return None. The first smoke run stopped the kernel at 09:30 because `TradingAgent.wakeup` returns a bool, which the kernel treats as a gym interruption. Found and fixed before any test or campaign.
- **Clipping counts in-flight orders.** The spec clips by cash or shares held. Because an order whose cancel is still in flight can fill, the clip uses cash and shares minus the worst-case commitment of the trader's own open orders. This is what makes T-RT4 ("never negative at any fill") hold.
- **σ_ref EWMA** starts at the first 5-s sample (the spec gives no start value). The 10-min warm-up (V = 1) covers the start. With less than 30 (5) minutes of history, r_30 (r_5) is measured against the oldest mid kept.
- **One stop per trader**, replaced by every new buy fill. The stop is cleared when a sell leaves the trader flat, so a stop never fires for a trader with nothing to sell (keeps E-A9's trigger counts meaningful).
- **Ordering and RNG:** the crowd and traders are appended after every existing agent. Their RNGs come from one global draw made after the latency model (the last existing draw), per rule 2.3. `num_retail=0` builds and draws nothing (I8 unchanged).

### 2026-10-16 (A5) Liquidity providers: implementation choices
- **Prices to whole cents:** bids are floored and asks ceiled, so the quoted half-spread is never below h; prices are clamped to >= 1.
- **"A side is missing"** = a side the rules say to quote (not blocked by the inventory limit) has no open order of this LP (its quotes were filled or cancelled).
- **Overshoot:** cancel, send one marketable order to q_max, then requote at the next wake from the new inventory.
- **Wake offset:** LP k first wakes at the open + k·5 s / n_lp (evenly spread), then every 5 s; always rescheduled while the market is open.
- **Budget:** GrossLimit(L = 2), the same worst-case rule as the stock agents (open same-side orders counted).
- **Inventory check (T-LP6):** with log_orders off, the LP's fills are replayed from the exchange's EXEC history. This is also how I4-for-LPs is checked in a market.
- **E-A9 measurement added:** `retail_stop_trigger_pct` (share of stop users whose stop fired that day) and the stop counts in `metrics.json["diagnostics"]["retail_stops"]`.

### 2026-10-16 (A6) K16 fix, impact set, G11 to reported
- **K16 diagnosis (A6.1, targeted first).** `scripts/diag_k16.py` on the failing P0-S2 runs (seeds 7, 13, 14, 18, 19; v1 check):
  - 7 breach fills, all increased |position|, all marketable buys of a borrowing long (w ≈ 1.5, cash < 0) that filled at once BELOW the limit (e.g. seed 14: limit 1019.63, fill 1016.02, 1.5024×; at the limit price it would have been 1.4997×).
  - P0-S2n seeds 3, 8 (−2% jump): the mirror case, shorts selling at once ABOVE the limit (−0.5058× at worst).
  - In-flight cancels: 0 of ~125k decision cycles had an own open order left at the cycle (the cancel confirmation arrives before the spread reply). Counted anyway, as the spec says.
- **The spec's premise is wrong for the binding cases (spec question for the owner).** A6.1 says the worst-case fill price is the limit price. The post-fill ratio n·p / (cash + n·p) falls with p when cash < 0 (borrowing long) and grows in size with p when n < 0 (short). So the limit is the BEST end exactly where the ±bounds bind (w > 1 or w < 0). Checking at the limit price alone (= the v1.4 check) cannot close K16.
- **Decision: `informed_budget_v2` checks both ends of the fill range**, which follows the spec's own principle ("the worst-case price at which the order can fill"):
  - the limit price (resting fills happen there), and the best opposite quote seen in this cycle when it is better than the limit (the immediate fill of a marketable order); the smaller allowed quantity wins. The ratio is monotone in the fill price, so both ends cover the range in between.
  - B/S start from every own order still in `self.orders` (resting, or cancel sent but not confirmed).
  - With cash ≥ 0 and n ≥ 0 the limit price is the worst end and v2 = v1 (T-K16-1).
  - Default False (build_config `informed_budget_v2`, agent `budget_v2`), no RNG draw, I8 unchanged until A9.
- **Result.** v2 on all 15 previously failing jump runs (P0-S2 ×5, P0-S2n ×4, A-ENV-S2 ×2, A-RET-S2 ×2, A-LP-S2 ×1, plus seed 14 targeted): 0 fills that increase |position| end outside the bounds.
- **What v2 cannot do: "every fill" is unreachable by any order rule.** Two fills remain outside the bounds: P0-S2n seed 11 1.5069× and A-RET-S2 seed 5 −0.5089×. Both REDUCED |position|. The jump had already pushed the position past the bound by mark-to-market (the agent sat at the bound; the price moved); the fill moved it back toward the bound.
  - Tightened I4 (informed) therefore means: every fill that increases |position| stays within [−0.5, 1.5] × wealth at the fill price, one share tolerance (T-K16-3 on the jump market). The lab now reports both `informed_bounds` (every fill, unchanged) and `informed_budget` (increasing fills only).
  - The owner decides whether "every fill" in A6.1 should read "every fill that increases exposure" (recommended), or whether the agent should actively de-lever after a jump (new behaviour, not in the spec).
- **A6.2 impact set:** `lab_v15.IMPACT_SET` = IMP-0, IMP-0.1, IMP-0.5, IMP-1, IMP-5, IMP-1s. β is fitted on the four sizes (0.1, 0.5, 1, 5) by `realism_lab.impact_summary`. The configs are registered for N (normal day) in A8.
- **A6.3:** no action. VR(5) is reported (below and in RESULTS_A).
- **A6.4 G11 → REPORTED.** The band is kept in `BANDS` with `"reported": True`. `grade_value` returns None (shown "n/a"), the metric is still computed and shown, and regimes are graded across days (RS, A8).
  - Reason (spec A6.4, from the model's own maths, before any R4 sweep run): even the true value gives a median per-day 30-min contrast of 2.4–2.9 under realistic day types, so ≥ 5 per day is unreachable by construction.

### 2026-10-16 (A7) Design sweep: implementation choices
- **Population per design** (`api/lab.py` `sweep_extra`): P0 base (0 value agents, D-60fl2M, 12 momentum, budget L = 2) + `informed_budget_v2=True`, living_v1 (day type "normal", auto news), `num_noise_agents=0`, retail crowd (`num_retail` = N_r, `retail_kappa_v` = κ_v, every other retail parameter at its A4 default), `mm_kind="lp"` with `num_lp` = n_lp LPs of W each (LP l_max at its A5 default).
- **Design id** exactly as A7 writes it, R-<n_lp><W><N_r><κ_v> (e.g. R-25M5001, R-420M15003); n_lp and κ_v are one digit, so the id parses unambiguously (`lab.parse_sweep`). Reports also print the dials in separate columns.
- **R4a scorecard** (`realism.r4a_scorecard`, A8.1/A8.2 thresholds as written). In screening (`screening=True`): A-T3 and A-T11 are NOT_SCREENED (day mix), A-T9 uses S2 only (A7 runs the +2% jump only), L1 is judged on the normal day only.
- **L4 in the sweep** = zero_sum 0 in every run AND every invariant flag passes, except `informed_bounds`. That flag keeps the A6 "every fill" reading, which no order rule can meet after a jump (A6). The budget rule itself is judged by `informed_budget` (fills that increase exposure), the reading recommended to the owner in A6. `informed_bounds` failures are counted and reported per design. If the owner keeps "every fill", L4 is re-read from the stored flags without new runs.
- **L5** is measured at 2 workers (the campaign runs at 2 workers), median over the design's C and S2 runs. The A7 tie-break also uses this median.
- **Jump response minimum seeds** = 1 per design, as in the v1.4 screening (`design_summary`). The completeness table shows each config's valid seeds.
- **No winner case:** if every design fails a limit, step 1 keeps none. A7 does not cover this, so the printout says so and the owner decides. The rule is not relaxed.
- **Outcome (recorded, not acted on):** 13 of 16 designs fail L7. Retail volume share is 1.2–4.8%, below the 5% floor; only the N_r 1500 designs with 2 LPs of $5M, or 4 LPs with κ_v 3, reach it. The selection keeps 3 designs and picks R-25M15003 (5/10 screened targets).
  - The refinement round (40 runs) keeps it: R-25M30003 passes 7/10 targets but fails L6 (max gap $20.7), and R-250M15003 fails L7.
  - Larger LP capital lowers σ1m and the vol ratio and raises VR(5), kurtosis and the LP losses (main effects in RESULTS_a-sweep.md).
  - A7 continues with R-25M15003 as written. It fails A-T1 (4.9 bps), A-T5 (0.81), A-T7 (CS 0.026, PS < 0), A-T10 (LP group −$6.0k) and A-T12 (u 1.2).

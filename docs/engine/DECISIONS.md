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

# FundamentalistAgent (ours)

Code: `abides-markets/abides_markets/agents/fundamental.py`.
Ranges: `abides-markets/abides_markets/configs/param_ranges.py` (`FUNDAMENTAL_RANGES`).
Tests: `abides-markets/tests/test_fundamental.py`.

## In plain language

A value investor who cannot see the company's true value. Every 10 seconds it looks at the
market price and updates a belief, x̂, about what the stock is worth, using a **Kalman
filter**: it moves its belief a small fraction K of the way toward each new price, and that
fraction depends on how noisy it thinks prices are (R) and how fast it thinks value can move
(Q). It then compares its belief with the price. If the price is below its belief by much
more than the normal wiggle of prices, it holds more stock; if above, less. It trades only
the difference between what it holds and what it wants to hold, in limited steps, and
ignores differences too small to be worth a trade. A headline nudges its belief by a few
"typical half-hour moves" and makes it more open-minded for a while.

It starts with $50,000 cash and 50 shares (bought at $1000 before the open), never borrows
and never short-sells.

## One decision cycle

`wakeup` (every `wake_up_freq` = 10 s) → cancel open orders → ask for the spread →
`receive_message` → `execute_strategy`:

1. **Observe**: mid = (bid + ask) / 2 (cents). Skip the cycle if one side is empty.
2. **Initialise** (first observation only): x̂ = one noisy look at the oracle,
   `observe_price(sigma_n = σ_n)`, where σ_n is a **variance** (300–3000 cents², sd 17–55¢).
   P starts at `initial_uncertainty`.
3. **Value-speed estimate** σ̂_f² (cents²/s), from the mid change over the last 300 s:
   - find the latest logged time ≤ now − 300 s (bisect);
   - sample = (mid − mid_then)² / lag_s;
   - σ̂_f² ← max(0.1, (1 − 1/60) σ̂_f² + (1/60) sample); prior 3.0.

   Long lags are used because short-lag changes are mostly microstructure noise.
4. **Predict** (random walk), with dt = seconds since the previous update:

   x_pred = x̂,  P_pred = P + Q,  **Q = q · σ̂_f² · dt**

5. **Observation noise** from the Kaufman efficiency ratio (ER over the last `er_window` mids):

   **R = (δ · mid)² · exp(λ_ER · (1 − ER))**

   Clean, trending prices (ER → 1) are trusted more; choppy prices (ER → 0) less.
6. **Correct** (standard scalar Kalman update):

   y = mid − x_pred,  K = P_pred / (P_pred + R),  x̂ = x_pred + K·y,  P = (1 − K)·P_pred

   With Q the gain settles at K_ss ≈ √(Q/R) instead of decaying like 1/n.
7. **Caution** C_t ∈ [0, 1]: the virtual score W = D_prev · (mid − previous mid), where
   D_prev = sign(x̂ − mid) at the previous cycle; E ← γ·E + (1 − γ)·W;
   C = 1 / (1 + exp(−k·E)). C = 0.5 is neutral.
8. **Target position** (v1.1, edge redefined in v1.2):

   | | |
   |---|---|
   | edge | **z = (x̂ − mid) / √(P + R)** (0 if P + R ≤ 0) |
   | target stock fraction | w* = clip(w₀ + a_max · C · tanh(z / z₀), 0, 1), w₀ = 0.5 |
   | wealth | W = cash + shares · mid |
   | wanted change | d* = round((w*·W − shares·mid) / mid) shares |
   | step cap | \|d\| ≤ floor(s_max · W / mid) |
   | dead band | trade only if \|d\| ≥ 1 and \|d\|·mid ≥ b_f · W |
   | long-only, no leverage | sells ≤ shares held; buys ≤ floor(cash / limit price) |

   The side comes from d, not from the sign of z. After buying to 90%, a small positive z
   that targets 60% is a SELL (taking profit).
9. **Limit price** for the chosen side: buy at bid + C·spread, capped at x̂·(1 + μ) and floored
   at the bid; sell at ask − C·spread, floored at x̂·(1 − μ) and capped at the ask.

### Why z = gap / √(P + R) (v1.2)

P + R is the variance of (belief − price) when nothing is mispriced: the agent's own
uncertainty plus the normal noise of the price. z is therefore a t-statistic,
signal ÷ noise. z = 1 is one normal wiggle; z = 3 is a real mispricing.

Worked example (seed 42 medians, spec v1.2 §2.2): gap 13¢, √P = 30¢, √R = $2.09.

- v1.1, z = 0.13 / 0.30 = 0.43 → about 9 shares of target change, every few cycles;
- v1.2, z = 0.13 / 2.11 = 0.06 → about 1.3 shares, inside the dead band → hold.

Side effect: R rises in choppy markets (low ER), so the agent trades less in chop and more
when prices move cleanly.

**Why the old version herded:** all agents watch the same price through similar lagging
filters, so their gaps share sign and timing. Every dip looked like a strong buy signal to
all of them at once.

Measured (2026-10-09, seed 42, full day, 20 fundamentalists + 12 momentum, 97 value agents,
v1.2 code): shares traded per agent per day median **168.5** (range 4–1216; v1.1: ≈1,900),
holdings 46–54 shares at the 10th/90th percentile of fill events, median √(P + R) = $2.12.

### News

On a `NewsSentimentMsg` for its symbol (`apply_news`):

σ_move = √(σ̂_f² · 1800 s),  shift = sentiment · k_news · σ_move,  x̂ += shift,  P += shift²

News is worth k_news "typical 30-minute moves". The added P makes the next market readings
count more, so the market confirms or fades the news. The agent then runs one immediate
trading cycle. Example: σ̂_f² = 3 gives σ_move = 73¢; sentiment 0.9 and k_news 2 give
+$1.32 (v1.0 gave +$33).

## Parameters

Drawn per agent in `rmsc04_ekf.build_config` with `param_ranges.draw` ("linear" = uniform,
"log" = log-uniform, "floor" = integer).

| Name | Range | Meaning |
|---|---|---|
| `er_window` | 5–24 (integer) | Prices used for the efficiency ratio |
| `delta` (δ) | 0.0005–0.003 | Base observation noise as a fraction of price (δ·mid = $0.50–$3) |
| `lambda_er` (λ_ER) | 0.5–2.0 | Extra distrust of choppy prices |
| `sigma_n` (σ_n) | 300–3000 cents² | Noise **variance** of the one private oracle look at start-up |
| `initial_uncertainty` (P₀) | 50,000–500,000 cents² | Initial belief variance |
| `q` | 0.3–3.0 (log) | Process-noise multiplier: how flexible the belief is |
| `gamma` (γ) | 0.4–0.95 | Caution memory |
| `k` | 0.3–2.5 | Caution sensitivity |
| `mu` (μ) | 0.02–0.2 | Limit price safety margin around x̂ |
| `a_max` | 0.6–1.0 | Largest tilt of the stock fraction away from 50% |
| `z0` (z₀) | 1.0–3.0 | Edge (in normal wiggles) that earns most of the tilt |
| `s_max` | 0.10–0.25 | Largest trade per cycle, as a fraction of wealth |
| `b_f` | 0.01–0.03 | Dead band, as a fraction of wealth |
| `k_news` | 0.5–3.0 | News shift in typical 30-minute moves |

Fixed: `wake_up_freq` = 10 s, `initial_exposure` = 0.5, `reference_price` = r̄ = 100,000¢.
Module constants (not randomised): `SIGMA_F_LAG_S` = 300 s, `SIGMA_F_PRIOR` = 3 cents²/s,
`SIGMA_F_FLOOR` = 0.1 cents²/s, `SIGMA_F_EWMA_N` = 60, `NEWS_HORIZON_S` = 1800 s.

## Log events

| Event | When | Keys |
|---|---|---|
| `EKF_UPDATE` | each cycle after initialisation | mid, x_hat, P, R, K, ER, Q, dt, sigma_f2 |
| `CAUTION_UPDATE` | each cycle | D_prev, E_t, C_t |
| `FUND_DECISION` | each cycle | z, z_den (= √(P + R), cents; v1.2), w_star, w_now, d_star, d, skipped_reason (`dead_band` / `no_cash` / `no_shares` / null), side, limit_price |
| `NEWS_RECEIVED` | on a headline | headline, sentiment, shift (cents, signed), sigma_move, x_hat_before, x_hat_after, P_before, P_after |
| `EKF_FINAL_ESTIMATE` | kernel stop | x_hat, P, num_observations |

Plus the standard TradingAgent events (`HOLDINGS_UPDATED`, `ORDER_SUBMITTED`, `ORDER_EXECUTED`, …).

## Informed mode (v1.4, R3)

Spec v1.4 Part 4. Filled in at milestone N3.

## History

| Version | Change | Why |
|---|---|---|
| v1.0 (2026-09-25) | Scalar Kalman filter on the mid, no process noise; R = (δ·mid)²·exp(λ(1−ER)) with δ ∈ [0.002, 0.015], λ ∈ [1, 6]; flow sizing (buy a fraction of cash or sell a fraction of holdings, at least 1 share); after each order x̂ ×= 1.01 or 0.99; news x̂ ×= (1 + η·sentiment) | first version |
| v1.1 (2026-10-08) | nudge removed; Q = q·σ̂_f²·dt; smaller δ, λ ranges; target-position sizing with z = gap/√P; volatility-scaled additive news with P += shift² | x̂ drifted to ≈$949; the gain fell to ≈0.0004; R claimed $2.6–70 of noise; 19 of 20 agents sold all 50 shares in 7–19 min; news moved beliefs by +$33 (spec v1.1 §0.5) |
| v1.2 (2026-10-09) | **z = gap / √(P + R)** (`R_last` kept from the update); `z_den` logged | ≈1,900 shares/day per agent, holdings swinging 0 ↔ 100, all 20 in sync (spec v1.2 §0.4 P1) |

Decisions and alternatives: [DECISIONS.md](DECISIONS.md).

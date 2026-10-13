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

Spec v1.4 Part 4. Switch: `mode="informed"` (constructor), or `build_config(fund_mode="informed",
informed_design={...})`. `mode="price_only"` (the default) is the v1.3 agent byte for byte; its
code paths are untouched (I8, T-N6). The informed code lives in new methods: `informed_cycle`,
`research_update`, `belief_prices`, `informed_target`, `budget_qty`, and the informed branch of
`get_wake_frequency`.

### In plain language (§4.1)

A fundamental investor with its own research. Every few minutes it gets a noisy reading of the
company's true value (its *research*). It also learns from the market price, with less trust.
It decides how much stock to HOLD from how mispriced the stock looks. The key change is that it
prices every order from **what it believes the stock is worth**, not from the current quotes.
It also keeps a small two-sided quote around its belief (the *quote layer*), so the market has
liquidity at a price that reflects information, even when the book is empty. It may sell short
and borrow, within limits.

### Scheduling (§4.2)

- **Wakes:** Poisson. The gap is max(1 s, Exp(wake_mean)), drawn from the agent's own
  RandomState. The first wake is at the open + one such gap, through ABIDES' market-hours
  handshake. At each wake the agent cancels its open orders and requests the spread.
- **Research clock:** next_research = the time of the last reading + Exp(T_r), drawn from the
  agent's RandomState. The first research time is the first wake + Exp(T_r). A reading is taken
  at the first **wake** at or after next_research, not at next_research itself, and at most one
  is taken per wake. The mean interval is therefore T_r plus about half a wake gap.

### One decision cycle (§4.3), on the spread response at time t

| step | what | formula |
|---|---|---|
| 0 (first cycle only) | initial belief | x̂ = oracle reading with variance σ_n; P = initial_uncertainty; t_last = t; next_research = t + Exp(T_r); go to step 6 (quotes only, even on an empty book) |
| 1 | predict | dt = (t − t_last)/1e9; Q = q·σ̂_f²·dt; P ← P + Q |
| 2 | research (if next_research ≤ t) | y_r = oracle reading with variance σ_r²; K_r = P/(P + σ_r²); x̂ ← x̂ + K_r(y_r − x̂); P ← (1 − K_r)P; next_research = t + Exp(T_r); log RESEARCH_READING |
| 3 | market reading (two-sided book only) | mid = (bid + ask)/2; σ̂_f² update (unchanged); R_noise = (δ·mid)²·exp(λ(1 − ER)) (the v1.2 R); R_m = ρ·R_noise; K_m = P/(P + R_m); x̂ ← x̂ + K_m(mid − x̂); P ← (1 − K_m)P; log EKF_UPDATE |
| 4 | clock, caution | t_last = t; C = update_caution(mid) (unchanged), only with a mid |
| 5 | target position (only with a mid) | z = (x̂ − mid)/√(P + R_noise); w* = clip(0.5 + a_max·C·tanh(z/z0), −0.5, 1.5); W = cash + shares·mid; d* = round((w*·W − shares·mid)/mid); step cap ⌊s_max·W/mid⌋; dead band \|d\|·mid < b_f·W or \|d\| < 1 → 0 |
| 6 | **prices from the belief** (no bid/ask) | m = m0 + κ_m·√P (required edge); h = m + h0 (quote half-width); target BUY at ⌊x̂ − m⌋, SELL at ⌈x̂ + m⌉; quotes: bid at ⌊x̂ − h⌋, ask at ⌈x̂ + h⌉, each of q_q = max(1, ⌊θ_q·W_ref/x̂⌋) shares (W_ref = W with a mid, else cash + shares·x̂); every price ≥ 1¢ |
| 7 | budget, send | each order passes the §4.5 check (below); the target order is sent first, then the bid quote, then the ask quote; log FUND_DECISION and FUND_QUOTES |

The order is predict → research → market: two standard scalar Kalman updates of the same state.
A large ρ (price distrust) means the agent learns mainly from research; ρ near 1 makes it follow
the price, like v1.3. A price that crosses the book executes against resting orders up to that
price, and the remainder rests there. An agent that sees a large mispricing therefore buys
aggressively up to its *reservation price* (x̂ − m) and then becomes the best bid: liquidity at
the new, informed price. News is unchanged: `apply_news` shifts the belief, and the forced
immediate cycle follows.

### Why this fixes the R2 mechanism (§4.4)

The ValueAgents knew the value but quoted near the book, so the price moved only when one side
of the book ran out (book-creep; see AGENTS_ABIDES.md, "v1.4 finding"). Informed agents quote
around their beliefs, so the book itself sits around the market's consensus belief. When
research moves beliefs, the quotes move and orders cross at once. Disagreement between the
agents' beliefs (different research noise, timing and trust in the price) makes them trade
with each other. Volume then comes from information and disagreement, so it should rise when
information arrives. For an optimal filter the belief is a martingale (its changes cannot be
predicted), so belief-driven price changes should not be autocorrelated the way book-creep
was. Whether the *consensus* of many partially informed agents keeps that property is exactly
what targets T1/T2 test.

### Budget (§4.5)

Position limits are fractions of current wealth: `INFORMED_W_MIN = −0.5` (it may short up to
half its wealth) and `INFORMED_W_MAX = 1.5` (it may hold up to 150% of its wealth in stock,
borrowing the rest). Each order is checked for the worst case. Let n = shares held,
B/S = this cycle's own BUY/SELL orders already sent (older orders were cancelled at the wake),
p = the order's limit price, and W_p = cash + n·p:
- a BUY of q is allowed only if (n + B + q)·p ≤ 1.5·W_p;
- a SELL of q is allowed only if (n − S − q)·p ≥ −0.5·W_p;
- otherwise q is reduced to the largest allowed integer; at 0 the order is skipped
  (target: `skipped_reason = "budget"`; quote: the side is listed in `blocked_sides`);
- if W_p ≤ 0, only orders that reduce |n| are allowed.

The arithmetic is shared with the ABIDES gross limit (`utils/budget.allowed_qty_wealth`).

### Parameters (§4.6, `param_ranges.INFORMED_RANGES`)

They are drawn per agent with the global RNG of `build_config`, after the agent's
FUNDAMENTAL_RANGES draws and before its RandomState seed, in this order:

| name | range | meaning |
|---|---|---|
| wake_mean | 30–120 s, log | mean Poisson wake gap |
| rho | 3–100, log | price distrust: R_m = ρ·R_noise |
| m0 | 1–3¢ | base required edge |
| kappa_m | 0–0.5 | extra edge per sd of the belief |
| h0 | 1–5¢ | quote half-width beyond the edge |
| theta_q | 0.005–0.02 | quote size, fraction of wealth per side |
| T_r | design level, log-uniform | mean research interval (s) |
| sigma_r | design level, log-uniform | research noise sd (¢) |

The FUNDAMENTAL_RANGES (er_window, delta, lambda_er, sigma_n, initial_uncertainty, q, gamma, k,
a_max, z0, s_max, b_f, k_news) are used as in price_only mode. `mu` is drawn, which keeps the
draw order, but is unused. Starting wealth per agent is `informed_design["wealth_c"]`; the
endowment is ⌊0.5·wealth/r̄⌋ shares as before.

### Log events (informed mode)

| event | keys |
|---|---|
| RESEARCH_READING | y_r, sigma_r, K_r, x_hat_before, x_hat_after, P_after |
| EKF_UPDATE | the v1.3 keys (mid, x_hat, P, R = R_noise, K = K_m, ER, Q, dt, sigma_f2) + R_m, rho, K_m |
| CAUTION_UPDATE | unchanged |
| FUND_DECISION | the v1.3 keys (z, z_den, w_star, w_now, d_star, d, skipped_reason, side, limit_price) + mode, m, h, x_hat. z…w_now are None when there is no decision (skipped_reason first_cycle or no_mid) |
| FUND_QUOTES | bid_price, bid_qty, ask_price, ask_qty, blocked_sides |

### Learning from prices (v1.4.1, `price_learning`)

Spec v1.4.1 Part 2. Informed mode only. With `"off"` (the default) the behaviour is exactly v1.4.

**Plain language.** An informed agent normally trusts its own research much more than the
market price. But if the price keeps sitting far from its belief (farther than normal price
noise can explain, on several looks in a row), the agent concludes that other traders probably
know something it does not. It then trusts the price more until the disagreement is gone. One
odd print does nothing; a persistent move does. Research keeps every agent anchored to the true
value, so prices cannot drift away for long. Economically this is learning from prices
(Grossman–Stiglitz); technically it is innovation-based adaptive Kalman filtering (covariance
matching).

**Maths** (`price_learning_step`). It runs in step 3 before the market update, with x̂ and P as
they are after the predict and research steps:

| quantity | formula |
|---|---|
| innovation | y = mid − x̂ |
| surprise | ε = y² / (P + R_noise), measured against normal price noise, not against R_m |
| persistence gate | e_pers = min of the last n_pl ε once n_pl looks exist, else 0 (the price must disagree n_pl looks in a row) |
| memory | ε̄ ← (1 − a_pl)·ε̄ + a_pl·e_pers |
| trust boost | g = clip(ε̄ / ε_thr, 1, ρ) |
| covariance matching (if g > 1) | P ← max(P, (ε̄ − ε_thr)·(P + R_noise)) |
| market noise | ρ_eff = ρ / g ≥ 1; R_m = ρ_eff·R_noise (replaces ρ·R_noise) |

The v1.4 update K_m = P/(P + R_m) then follows. Both parts are needed. Lowering R_m alone
barely moves a belief with a small P. The P inflation is what lets a persistent gap be
adopted: in T-N18, "mod" adopts 59–96% of the gap at the first gated look and ≥ 95% one look
later.

**Levels** (`param_ranges.PRICE_LEARNING_LEVELS`). Set through `informed_design["price_learning"]`.
`eps_thr` and `a_pl` are drawn per agent after all its other informed draws; nothing is drawn
for "off".

| level | n_pl | ε_thr | a_pl | note |
|---|---|---|---|---|
| off | — | — | — | v1.4 behaviour |
| mod | 3 | 1–4, log | 0.2–0.4 | ignores a two-look blip |
| strong | 2 | 0.5–2, log | 0.2–0.4 | reacts one look earlier and follows two-look blips (herding-prone; judged by L6) |

**Result: a negative result (spec v1.4.2, D-R3-9). Default "off"; the code and tests stay.**

Campaign s2 (16 designs × C/S2/S2n × 5 seeds) and its refinement round found that learning
from prices *slows* the pricing of value jumps. Off → mod / strong: t90 +5.8 / +16.1 min, with
no more agents updated at +5 min.

The rule is symmetric. An agent that has just researched the new value sees a price that has
not moved yet. Its gate opens, it inflates P, and it pulls its belief back toward the stale
price. Diagnostic (`scripts/diag_learning_jump.py`, seed 42, 11:00–11:30, +2% jump):

| design | learning moves toward the new value / toward the stale price | median move ($) |
|---|---|---|
| D-60fl2M-mod | 81 / 99 | 0.34 / 1.12 |
| D-60fl2M-strong | 183 / 216 | 0.30 / 0.89 |
| D-60sl2M-mod | 150 / 354 | 0.52 / 1.05 |

The spec's hand simulation tested only an agent that had not yet researched; that was a spec
error. On quiet days the gate never opens in the fast, precise designs.

R4 candidate (not implemented): a one-directional variant, with no learning for an agent whose
last research reading is younger than its research interval.

**Log.** With learning on, EKF_UPDATE also carries eps, e_pers, epsbar, g, rho_eff and
P_inflated (true when the covariance matching raised P). With "off" the event is unchanged.

## History

| Version | Change | Why |
|---|---|---|
| v1.0 (2026-09-25) | Scalar Kalman filter on the mid, no process noise; R = (δ·mid)²·exp(λ(1−ER)) with δ ∈ [0.002, 0.015], λ ∈ [1, 6]; flow sizing (buy a fraction of cash or sell a fraction of holdings, at least 1 share); after each order x̂ ×= 1.01 or 0.99; news x̂ ×= (1 + η·sentiment) | first version |
| v1.1 (2026-10-08) | nudge removed; Q = q·σ̂_f²·dt; smaller δ, λ ranges; target-position sizing with z = gap/√P; volatility-scaled additive news with P += shift² | x̂ drifted to ≈$949; the gain fell to ≈0.0004; R claimed $2.6–70 of noise; 19 of 20 agents sold all 50 shares in 7–19 min; news moved beliefs by +$33 (spec v1.1 §0.5) |
| v1.2 (2026-10-09) | **z = gap / √(P + R)** (`R_last` kept from the update); `z_den` logged | ≈1,900 shares/day per agent, holdings swinging 0 ↔ 100, all 20 in sync (spec v1.2 §0.4 P1) |
| v1.4 (2026-10-12) | **informed mode** (`mode="informed"`): research readings every Exp(T_r), market readings down-weighted by ρ, leverage-bounded target w* ∈ [−0.5, 1.5], every order priced from the belief (x̂ ∓ m), a two-sided quote layer at x̂ ∓ h, worst-case budget, Poisson wakes. price_only unchanged | R2: the ValueAgents (87% of volume) priced from the book, so the price moved by book exhaustion; R3 replaces them with agents whose quotes carry information (spec v1.4 §0.3, D-R3-1) |
| v1.4.1 (2026-10-13) | **learning from prices** (`price_learning` mod/strong): a persistent, gated disagreement between the price and the belief lowers the price distrust (ρ_eff = ρ/g) and inflates P (covariance matching) | N4 (D-60fl2M, seed 42): after a +2% jump only 15% of agents had updated at +5 min; the book split into old-belief and new-belief clusters, and the price lagged value by tens of minutes (spec v1.4.1 §0.2) |

Decisions and alternatives: [DECISIONS.md](DECISIONS.md).

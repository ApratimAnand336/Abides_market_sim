# MomentumEKFAgent (ours)

Code: `abides-markets/abides_markets/agents/momentum_ekf.py`. The maths lives in small pure
functions at the top of the file so it can be tested without a kernel.
Ranges: `configs/param_ranges.py` (`MOMENTUM_RANGES`). Tests: `abides-markets/tests/test_momentum_ekf.py`.
Design: momentum agent spec v1.0 (owner's notes) and spec v1.1 Part 3 (M1–M7,
[`docs/specs/spec_v1.1.txt`](../specs/spec_v1.1.txt)).

## In plain language

A trend follower that never looks at the true value. It watches the market price and keeps a
Kalman-filter estimate of two things: where the price "really" is (the level l̂) and how fast
it is moving (the speed v̂), each with its uncertainty. Trend strength T = v̂ / (its standard
deviation) says whether the speed is clearly different from zero. When T is high, the
efficiency ratio says the move is clean, and the price breaks out of its recent range, the
agent turns BULL (or BEAR) and leans its holdings toward stock (or cash). It only adds at
fresh highs, cuts back when conviction drops, and exits through a trailing stop or when the
trend fades. Like the fundamentalist it starts with $50,000 + 50 shares and is long-only.

## One decision cycle

Wakes are Poisson with mean `wake_mean` (gap = max(1 s, Exponential(wake_mean))). Each wake:
cancel open orders → ask for the spread → `process_observation(t, bid, ask)`:

### Layer 1 — damped-trend Kalman filter on z = ln(mid)

State x = [l, v]: log-price level and velocity (log-return per second). The model is linear in
log-price, so the "EKF" is a standard Kalman filter.

**Warm-up** (first `N_w` observations, no trading): an OLS fit of z on [1, t − t_last] gives
x₀ and P₀ = c_P · s²_res · (XᵀX)⁻¹, with s²_res = max(residual variance, σ_q²) and the tick
floor σ_q² = 1 / (12 · mid²). Noise scales are self-calibrated from the warm-up:

- σ²_ref = detrended return variance per second (below), floored at σ_q² / mean(dt);
- R_base = κ_R · s²_res;  σ_l² = κ_l · σ²_ref;  σ_v∞ = κ_v · σ_ref / √τ.

**Predict** over the gap dt with φ = e^(−dt/τ):

F = [[1, τ(1 − φ)], [0, φ]],  Q = diag(σ_l² · dt,  g_Q · σ_v∞² · (1 − φ²))

The velocity decays toward 0 with time constant τ ("damped trend"); a trend must keep proving itself.

**Observe**: R = R_base · exp(λ_ER · (1 − ER)), with ER over the last `n_er` log-prices.

**Correct**: H = [1, 0], Joseph-form covariance update.

**Regime monitor**: ε = y²/S (normalised surprise), ε̄ ← (1 − a_ε) ε̄ + a_ε ε, and
g_Q = clip(ε̄ / ε_thr, 1, g_max) inflates the velocity noise for the next step when
surprises are persistently large (a regime change).

**Derived quantities**: T = v̂ / √P_vv; σ̂² = detrended realised variance of the last `n_er`
returns (floored as above); σ_τ = mid · σ̂ · √τ, a "typical move over one trend lifetime" in cents.

**Detrended variance** (v1.1 M2): r_i = z_i − z_{i−1}, v̄ = Σr_i / Σdt_i,
e_i = r_i − v̄ · dt_i, variance = mean(e_i² / dt_i). Raw returns would count the trend as
volatility (E[r²/dt] = σ² + v² dt).

**Trend bias.** At steady state on a ramp of speed v, the filter sees only part of the speed:

v̂ / v = dt / ((1 − φ)(τ + K_l / K_v)) ≈ τ / (τ + K_l / K_v)

where K_l, K_v are the steady-state gains (spec v1.1 Appendix A3). With v1.0's κ ranges the
worst corner saw 26–28% of the speed; the v1.1 ranges give 83–88% (test T-M1: 0.854, 0.879,
0.833, 0.866 at the four corners with tau_ratio = 15 and a 30 s wake; the formula agrees to
< 0.01%).

### Layer 2 — caution

As for the fundamentalist, with the view D = sign(v̂): W = D_prev · (mid − previous mid),
E ← γE + (1 − γ)W, C = sigmoid(k_c · E) (computed with a numerically stable sigmoid since v1.2).

### Decision — state machine

| From | To | Condition |
|---|---|---|
| NEUTRAL | BULL (BEAR) | breakout: price above (below) the highest (lowest) mid of the last τ seconds, **and** T ≥ θ_in (≤ −θ_in), **and** ER ≥ ER_min |
| BULL | WATCH | **STOP**: price ≤ peak − k_stop · σ_τ; or **FADE**: T < θ_out |
| BEAR | WATCH | mirror (price ≥ trough + k_stop · σ_τ, or T > −θ_out) |
| WATCH | BULL (BEAR) | **re-entry**: price ≥ L + k_re · σ_τ (≤ L − k_re · σ_τ) and v̂ > 0 (< 0) and **T ≥ θ_out (≤ −θ_out)** (v1.1 M5); L = the exit's peak (trough) |
| WATCH | opposite trend | a breakout the other way |
| WATCH | NEUTRAL | τ seconds without re-entry (TIMEOUT) |

θ_in > θ_out gives hysteresis: no flip-flopping around a single threshold.

### Layer 3 — target exposure, ratchet, order

- Conviction a = C · s · m · g with s = tanh(|T| / T₀), m = exp(−λ_v (1 − ER)) and
  g = min(1, √(σ²_ref / σ̂²)) (less size when volatility is above its warm-up level).
- Target fraction of wealth in stock: BULL e* = e₀ + a (e_max − e₀); BEAR e* = e₀ − a (e₀ − e_min);
  otherwise e₀ = 0.5.
- **Ratchet** (v1.1 M4): in BULL the cap first follows e* down (e_cap = min(e_cap, e*)); it rises
  to e* only at a fresh high p ≥ p_add + k_add · σ_τ. Exposure can always be cut, and is rebuilt
  only at new highs. BEAR mirrors this with a floor.
- Shares: n* = floor(e_target · W / mid), Δn = n* − n; skip if |Δn| < max(n_min, b · n*) (dead band).
- **Limit price**: urgency u within the spread. A STOP exit uses u = 1 (cross the spread); a
  TREND order uses u = C · ρ / (1 + ρ) with ρ = |v̂| · h / (relative half-spread); other orders
  use u = 0. TREND orders are also bounded by an anti-chase band exp(z_fc ± μ_m · σ_fc) around
  the filter's forecast for the next decision; an order the band rules out is skipped.
- **Persistent stop** (v1.1 M6): after a STOP, `exit_pending` keeps STOP pricing and ignores
  the dead band until the position is back at target (|n − n*| < n_min); it clears on any entry.

### News

On a headline (`apply_news`, after warm-up only): v̂ += η_news · sentiment · σ_v∞;
P_vv ×= f and P_lv ×= √f with f = 1 + ρ_news · |sentiment| (keeps P positive semi-definite).
The level is never moved and no immediate trade is made; the effect shows at the next wake.

## Parameters

Drawn per agent in `rmsc04_ekf.build_config`: `wake_mean` first, then the rest
(`tau = tau_ratio × wake_mean`).

| Name | Range | Meaning |
|---|---|---|
| `wake_mean` | 10–60 s | Average time between decisions |
| `tau_ratio` | 15–40 (log) | Trend lifetime in decisions; τ = tau_ratio · wake_mean spans 2.5–40 min |
| `N_w` | max(n_er + 1, 15)–30 | Warm-up length (observations) |
| `n_er` | 10–25 | Efficiency-ratio and realised-variance window |
| `lambda_er` | 1.0–6.0 | Distrust of choppy prices |
| `kappa_R` | 0.5–2.0 | Observation-noise scale |
| `c_P` | 1.0–5.0 | Initial self-doubt after warm-up |
| `kappa_l` | 0.02–0.15 | Share of the noise treated as real level moves (v1.1 M1) |
| `kappa_v` | 1.0–2.0 | Expected trend size relative to the noise (v1.1 M1) |
| `a_eps`, `eps_thr`, `g_max` | 0.1–0.3, 2.0–4.0, 10 | Regime monitor: memory, threshold, maximum Q boost |
| `gamma`, `k_c` | 0.4–0.95, 0.3–2.5 | Caution memory and sensitivity |
| `theta_in`, `theta_out` | 1.5–2.5, 0.5–1.0 | Entry and stay thresholds on T |
| `ER_min` | 0.2–0.4 | Choppiness gate for entries |
| `k_stop`, `k_re`, `k_add` | 2.0–4.0, 0.25–0.5, 0.25–0.75 | Trailing stop, re-entry margin, add spacing (in σ_τ) |
| `T_0`, `lambda_v` | 1.0–3.0, 0.5–2.0 | Evidence for full size; murkiness penalty |
| `e_max`, `e_min`, `b`, `n_min` | 0.7–0.95, 0, 0.1, 1 | Exposure bounds, dead band, minimum order |
| `mu_m` | 0.5–2.0 | Anti-chase band width |
| `eta_news`, `rho_news` | 0.0–0.5, 1.0–5.0 | News lean on v̂; open-mindedness after news |

## Log events

| Event | Keys |
|---|---|
| `MOM_WARMUP_DONE` | l0, v0, P0, s2_res, sigma_ref2, R_base, sigma_l2, sigma_vinf |
| `MOM_KF_UPDATE` | mid, l_hat, v_hat, P00, P01, P11, R, S, K0, K1, ER, eps, epsbar, g_Q, T |
| `CAUTION_UPDATE` | D_prev, E_t, C_t |
| `MOM_STATE` | from, to, reason (BREAKOUT / REENTRY / STOP / FADE / TIMEOUT), L, peak_or_trough |
| `MOM_DECISION` | state, a, s, m, g, e_star, e_target, n_star, n, dn, order_class, u, P_L, skipped_reason, added, exit_pending, sigma_hat2, sigma_tau, qty |
| `NEWS_RECEIVED` | headline, sentiment, v_hat_new, P11_new |
| `MOM_FINAL` | state, l_hat, v_hat, P, holdings |

## History

| Version | Change | Why |
|---|---|---|
| v1.0 (2026-10-05, 539ec6b) | First version as described above, with κ_l ∈ [0.05, 0.5], κ_v ∈ [0.5, 2], τ drawn independently (120–1800 s), raw (not detrended) variance, a ratchet cap that only rises, re-entry on v̂ > 0 alone, STOP urgency on the exit wake only | spec v1.0 |
| v1.1 (2026-10-08, 2ddee51) | M1 narrower κ ranges; M2 detrended variance; M3 τ = tau_ratio · wake_mean; M4 ratchet follows down; M5 re-entry needs T ≥ θ_out; M6 persistent stop; M7 more log keys | only 26–28% of trend speed seen; trend counted as volatility (g fell to 0.43); agents with τ/wake ≤ 5 never entered; 6 of 9 re-entries reversed within 3 looks (spec v1.1 §0.5 f–k) |
| v1.2 (2026-10-09) | No behaviour change. The caution sigmoid is computed in a numerically stable way (it overflowed in markets without value agents) | crash fix |

v1.1 acceptance (seed 42, full day, 20 + 12): 12 of 12 agents reached |T| ≥ θ_in; 19–21% of
re-entries reversed within 3 looks; median g in trends 0.91–0.98 ([`docs/v1.1/REPORT.md`](../v1.1/REPORT.md)).

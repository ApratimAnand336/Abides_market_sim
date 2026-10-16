# Liquidity providers (our market makers)

Spec v1.5 A5 (D-R4-4). Code: `abides_markets/agents/liquidity_provider.py` (quote maths in
the pure functions `lp_quotes`, `lp_sigma_update`, `lp_needs_requote`), constants `LP` in
`configs/param_ranges.py`, tests `tests/test_liquidity_provider.py`. Built by
`build_config(mm_kind="lp", num_lp=n, lp_wealth=W_cents, lp_l_max=None)`; the default
`mm_kind="abides"` keeps the two ABIDES AdaptiveMarketMakers (I8).

## Why our own

The ABIDES AdaptiveMarketMakerAgent has three problems:
- It quotes a 10-level ladder every ~60 s, with spacing tied to its own spread estimate (this needed a cap in v1.2 because of a runaway feedback loop).
- It has no inventory management (skew off).
- Its inventory is unlimited (exempt from the budget).

K15 needs liquidity that stays tight while informed traders disagree after a jump, and that widens and withdraws sensibly under stress, which is also a crash ingredient (Part B). In campaign a-env the ABIDES market makers lost a median $28.8k a day on the faster living value.

## Rules (every 5 s; first wake offset by k·5 s/n_lp for LP k)

| step | rule |
|---|---|
| reference | ref = mid if both sides exist, else the last trade, else r_bar (cold start). The exchange initialises the last trade to the oracle's open value, so a cold start quotes around it. |
| volatility | σ̂² = EWMA, half-life 5 min, of (ln ref_t − ln ref_{t−5 s})² / 5 s (per-second variance), prior (5.5 bps/min)²/60 s |
| half-spread | σ_10 = ref·sqrt(σ̂²·10 s); h = max(1¢, 0.5·σ_10) |
| inventory limit | q_max = floor(l_max·W/ref), l_max = 0.5 (0.25 in the crash fragility profile); W = cash + q·ref |
| skew | skew = ψ·(q/q_max)·h, ψ = 1; reservation r = ref − skew (long inventory lowers both sides) |
| ladder | 3 levels per side at r ∓ h·(1, 2, 3) (bids floored, asks ceiled to whole cents), each max(1, floor(0.02·W/ref/3)) shares (2% of wealth per side) |
| limits | no bids if q ≥ q_max; no asks if q ≤ −q_max; if \|q\| > 1.2·q_max (overshoot by fills), cancel and send one marketable order (2% collar) back to q_max (LP_UNWIND) |
| lazy requote | cancel and requote only if \|ref − ref_quoted\| > h/2, \|q − q_quoted\| > 0.1·q_max, 30 s have passed, or a side that should be quoted has no open order; otherwise send nothing |
| budget | GrossLimit(2): gross position value ≤ 2W in the worst case, as for the stock agents. The LP may short within q_max. |

Deterministic: an LP makes no random draws (it still gets a RandomState, from the v1.5 RNG
draw made after the latency model, like every v1.5 agent).

For $5M at $1000: q_max = 2,500 shares; 33 shares per level, i.e. 99 shares per side. With
the prior volatility, σ_10 = 22¢ and h = 11¢, a 2.2 bps quoted spread at the first level. On
the calm synthetic_ou value, σ̂ falls and h sits at the 1–2¢ floor.

## Log events

| event | fields |
|---|---|
| `LP_QUOTE` (each requote) | ref, h, sigma2, q, q_max, skew, r, bids, asks, size, reason ∈ {first, ref, inventory, age, side} |
| `LP_UNWIND` | q, q_max, side, qty, limit |

## Tests

| test | what it checks |
|---|---|
| T-LP1 | exact quotes (prior, skewed, 1¢ floor) |
| T-LP2 | no bid at q_max, no ask at −q_max; overshoot unwinds to q_max |
| T-LP3 | requote rules; an agent with an unchanged book sends nothing; a move > h/2 requotes |
| T-LP4 | empty book → quotes around r_bar; one-sided book → around the last trade |
| T-LP5 | σ̂ and h widen monotonically after a fast move (exact EWMA) |
| T-LP6 | 1-hour market with 2 LPs of $5M: ≥ 90% of 5-s wakes; lazy (requotes < wakes); \|q\| ≤ 1.2·q_max and gross ≤ 2W after every fill (replayed from the exchange's EXEC history); zero_sum 0; conservation |

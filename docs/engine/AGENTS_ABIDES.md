# The stock ABIDES agents

These agents come with ABIDES (J.P. Morgan). We use them as the background population of
`rmsc04_ekf`. Counts and wake patterns are summarised in [ARCHITECTURE.md](ARCHITECTURE.md);
the details are here. Code under `abides-markets/abides_markets/agents/`.

All stock agents trade with `ignore_risk = True`: they have **no budget limits**, so they can
short-sell and borrow without bound ([KNOWN_ISSUES.md](KNOWN_ISSUES.md), K10).

**Order sizes** (noise, value and ABIDES momentum agents) come from `models/order_size_model.py`,
a mixture: about 20% lognormal(2.9, 1.2) (median ≈ 18 shares), about 70% ≈100 shares, and the rest
≈200–1000 shares in round lots. The typical order is therefore about 100 shares.

## NoiseAgent (`noise_agent.py`) — 1000 by default

- **Does:** wakes **once per day** and places one order in a random direction (50/50) at the
  opposite best price (a buy at the ask, a sell at the bid). It takes liquidity immediately if
  the book has that side; with an empty side it places nothing.
- **Knows:** the best bid and ask only.
- **Wakes:** one time drawn from a U-quadratic distribution over 09:00–16:00
  (`abides_core.utils.get_wake_time`): more agents near the open and the close.
- **Role:** uninformed order flow, the "random traders" that informed traders profit from.

## ValueAgent (`value_agent.py`) — 97 by default

- **Does:** at each wake, takes a noisy look at the true value, updates a Bayesian estimate of the
  value at the close (its own mean-reverting model with `kappa = 1.67e-15`/ns and r̄), and compares
  it with the mid. If its estimate is below the mid it sells, otherwise it buys. 10% of its orders
  (`percent_aggr`) are placed at the opposite best (aggressive). The rest go up to
  `depth_spread · spread` = 2 spreads inside its own side of the book. **With an empty book it
  places an order at its value estimate, on a random side.**
- **Knows:** the true value with noise of variance `r̄ / 100` = 1000 cents² (sd ≈ 32¢), and the best bid and ask.
- **Wakes:** Poisson, mean 1/`lambda_a` = 1 / 5.7e-12 ns ≈ 175 s.

### Why the market currently depends on ValueAgents

ValueAgents do three jobs at once:

1. **Information.** They observe the true value with small noise about every 175 s, so they pull
   the price toward value and are the only consistently profitable group.
2. **Liquidity and volume.** About 13,000 orders of about 100 shares per day, about 83% of
   traded volume (spec v1.2 §1.2; the v1.1 report measured 82.5% on seed 42, run B).
3. **Starting the market.** They are the only stock agents that will place an order into an
   empty book (at their value estimate).

v1.2 removes dependency (3) for market makers (the cold start below). R3 builds our
fundamentalist to take over (1) and, with enough agents and capital, (2). After that the
ValueAgents can be phased out. Until then they stay as scaffolding
([DECISIONS.md](DECISIONS.md), 2026-10-09).

### v1.4 finding: the ValueAgent prices from the book, not from its estimate (spec v1.4 §0.3)

On S2 seed 42, one minute after a +2% value jump, the ValueAgents know the value is $1020.90
and 89% of their orders are buys, but they bid $1000.86. `ValueAgent.placeOrder` sets the
limit price from the **book**: a buy goes at ask − U[0, 2·spread], and 10% of orders go at the
ask. Its estimate decides only the side, so a $20 mispricing produces the same order as a
1-cent one. These agents supply 87% of the volume, yet they never push the price toward
value; the price moves only when one side of the book runs out. This one rule explains:
- the smooth, positively autocorrelated price (ac1 +0.37, VR(5) 1.90);
- the stall-then-gap pricing of jumps;
- the negative volume-volatility correlation (−0.25);
- the linear, transient impact.

**κ mismatch.** The ValueAgent's own model uses κ = 1.67e-15/ns, ten times the oracle's
1.67e-16. The agent therefore expects any deviation from r̄ to shrink by the close: 97.0% of
it is kept at 11:00 and 97.6% at 12:00. This is why a jump settles at 97.6%.

R3 (spec v1.4, D-R3-1) replaces these agents with informed fundamentalists. The ValueAgent
code is not modified; the legacy market keeps them.

### v1.4: gross budget limits (spec v1.4 Part 5)
Documented in N2.

## AdaptiveMarketMakerAgent (`market_makers/adaptive_market_maker_agent.py`) — 2 by default

- **Does:** at each wake, cancels its orders, asks for the spread and the recent traded volume,
  and places a **ladder** of `num_ticks` = 10 buy levels below and 10 sell levels above the mid. The
  window and the level spacing adapt to an EWMA of the observed spread (`window_size = "adaptive"`,
  `spread_alpha` = 0.75, `level_spacing` = 5 × the spread). The size per level is `pov` = 2.5% of
  the recent traded volume (at least `min_order_size` = 1). Inventory skew is off (`skew_beta = 0`).
- **Knows:** the best bid and ask and the recent traded volume. It never sees the true value.
- **Wakes:** Poisson, mean 60 s, in polling mode (`subscribe = False`).

### v1.2 fixes

**Cold start** (`cold_start_price`, spec v1.2 Part 4). The price the market maker anchors to
before any two-sided book exists, like "yesterday's close" that every real trader knows.
`rmsc04_ekf` passes r̄ = $1000. When both requests of a wake have been answered, the polling
branch now does:

```
mid = current mid, else last mid, else cold_start_price   (MM_COLD_START logged the first time)
if mid is known: place the ladder
ALWAYS: reset the request flags and schedule the next wake
```

**Upstream bug fixed:** ABIDES scheduled the next wake *only* when a mid existed. One wake on an
empty book stopped the market maker for the rest of the day. Reproduced 2026-10-09 (seed 42,
09:30–11:00, 5 + 4 of our agents): with 0 or 3 value agents each MM woke twice and placed **0
orders**; with 0 value agents there were **0 trades** all session. After the fix: 86–96 wakes per MM,
about 2,000 orders each, and 1,594 / 1,689 trades with 3 / 0 value agents. Only the first MM to
wake uses the cold start; the second already sees the first one's quotes.

**Spread cap** (`max_spread`, `rmsc04_ekf`: 100 cents). The adaptive spread has a feedback loop:
when the market maker is the main source of quotes, the spread it observes is the spread of its
own ladder, which is set from the spread it observed. Without value agents this grew
geometrically: one MM's estimate went from 1.6¢ at 10:05 to $46.50 by 10:15 (seed 42, 0 value agents),
with ladder levels $15–$232 apart. The price fell through the gaps toward zero, and the simulation then ground to a
halt. The cap stops the runaway; `MM_SPREAD_CAP` is logged the first time it binds and
`MM_SPREAD_CAP_SUMMARY` gives the count at the close. With value agents the spread has a median of 1¢
and a maximum of 53¢ (v1.1 report, seed 42, run B), so the cap does not bind there (tested).

**No quotes at or below zero.** Buy levels below 1 cent are dropped from the ladder (a safety guard
for crashing markets).

### v1.3: pause windows (realism lab scenario S6; default inert)

`AdaptiveMarketMakerAgent(pause_windows=[(start_ns, end_ns), ...])`, set through
`rmsc04_ekf.build_config(mm_pause_windows=[("13:00:00", "13:30:00")])` (clock times) and passed to
both market makers. Spec v1.3 §6.3. **Default `None`: no code path changes** (invariant I8).

When given:

- `kernel_starting` schedules one extra wake at each window start;
- at any wake inside a window [start, end) the agent cancels all its orders, logs `MM_PAUSED`
  (once per window) and does not ask for the spread. The extra window-start wake does not
  reschedule (the regular Poisson wake chain continues); a regular wake schedules its next wake as
  usual, so the chain survives the pause;
- a spread answer that arrives inside a window (asked for just before it began) and a book-imbalance
  event inside a window place no orders;
- at the first wake at or after the window end it quotes normally again and logs `MM_RESUMED`.

Tested by T-L8 (`tests/test_scenarios.py`): in a 1-hour market paused 10:00–10:15, no market-maker
order is placed in the window, none rests in the book once the cancels have arrived (1 s), each
MM logs one `MM_PAUSED` and one `MM_RESUMED`, and every execution before 10:00 equals the baseline's.

## MomentumAgent, "ABIDES MA" (`examples/momentum_agent.py`) — 12 minus our momentum count

- **Does:** after 50 observations of the mid, compares the 20- and 50-observation moving averages
  at every wake. If MA20 ≥ MA50 it **buys at the ask**, otherwise it **sells at the bid**: a
  liquidity-taking order of the mixture size every wake, with no position limit.
- **Knows:** its own history of mids.
- **Wakes:** Poisson, mean 37 s.

## Known limitations

- **No market without value agents and market makers.** With `num_mm = 0` and `num_value = 0`
  the market still cannot start: no agent will quote into an empty book. R3 gives our
  fundamentalist that ability.
- **Without value agents the price has no anchor.** With market makers it now trades all day,
  but nothing pulls it back to value. On seed 42 with 5 + 4 of our agents it slid from $999.75 to
  about $589 in the first hour (2026-10-09). The market makers absorb the selling with unlimited
  inventory (K10), and the ABIDES momentum agents sell at the bid on every wake once MA20 < MA50.
  This is the baseline that R3 starts from; see Run Z in `docs/v1.2/REPORT.md`.
- Market makers lose money every day to adverse selection by value agents (K8).

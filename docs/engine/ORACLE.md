# The oracle: the company's true value

Code: `abides-markets/abides_markets/oracles/pregenerated_oracle.py` (v1.2, used by
`rmsc04_ekf`); the stock ABIDES `sparse_mean_reverting_oracle.py` is kept, unchanged, for the
stock configs. Tests: `abides-markets/tests/test_oracle.py`.

## What the oracle is (and is not)

Two different things exist in the simulator:

- the **market price**, produced by agents' orders meeting in the order book. Market
  dynamics (volatility, trends, crashes, clustering) must come from here;
- the **true value** ("fundamental"): what the company is really worth. In real life nobody
  observes it directly; it changes when information arrives (earnings, news). Informed
  traders estimate it with noise.

The oracle is the simulator's source of the true value. **It is not historical market data.**
ABIDES' `SparseMeanRevertingOracle` invents the value with a random process: an
Ornstein-Uhlenbeck random walk with a very weak pull toward r̄, plus rare "megashocks". Its
docstring says: *"Historical dates are effectively meaningless to this oracle. It is driven
by the numpy random number seed."* The v1.2 oracle uses the same process.

Who looks at it: the 97 ValueAgents (every ≈175 s, with noise of variance 1000 cents²), our
FundamentalistAgent (once, at start-up), and the exchange (the opening price). Our momentum
agents never look at it. The dashboard draws it as the dashed "Oracle fundamental" line.

**Why synthetic and not historical.** A historical price series is itself a market price,
made by real traders, not a true value. Using it as the fundamental would make our agents
replay history instead of producing their own dynamics. A synthetic value lets us control
the information environment (calm days, shocks, news) and measure how the market reacts.
Historical data still has a place later, as an optional *path source* ("replay the
true-value shape of a real stock or event"); the v1.2 design makes that a drop-in.

## The maths

Units: value v in cents, time in nanoseconds.

**Ornstein-Uhlenbeck** (mean r̄, pull κ per ns, volatility `fund_vol` in cents/√ns):

dv = κ (r̄ − v) dt + fund_vol dW

Its exact transition over a step of d ns is

v(t + d) = r̄ + (v(t) − r̄) a + √(fund_vol² / (2κ) · (1 − a²)) · ε,  a = e^(−κd),  ε ~ N(0, 1)

For κd → 0 this is a random walk with standard deviation fund_vol · √d.

**Megashocks** arrive as a Poisson process (rate `megashock_lambda_a` per ns). Each has a size
drawn from N(`megashock_mean`, `megashock_var`) and a random sign (50/50): a bimodal jump
of about ±$10.

Parameters of `rmsc04_ekf` (unchanged in v1.2):

| Parameter | Value | In everyday units |
|---|---|---|
| r̄ (`r_bar`) | 100,000 | $1000 |
| κ (`kappa_oracle`) | 1.67e-16 /ns | a half-life of ln 2/κ ≈ 48 days: negligible pull within a day |
| `fund_vol` | 5e-5 cents/√ns | 1.58¢ per √second, 12.2¢ per √minute, $2.42 over a 6.5 h day (one standard deviation) |
| `megashock_lambda_a` | 2.77778e-18 /ns | one shock every ≈11.4 years on average: essentially never within a session |
| `megashock_mean`, `megashock_var` | 1000, 50,000 | ±$10, sd $2.24 |

**Measured** (2026-10-09, v1.2 path, seed 42, 09:30–16:00): the standard deviation of value
changes is 4.96¢ over 10 s, 11.2¢ over 60 s and 23.2¢ over 300 s (theory 5.0, 12.2, 27.4; one
day holds only 78 non-overlapping 300 s steps). The day spans $999.52–$1003.12. Over 200
seeds the 10/60/300 s standard deviations are within ±10% of the theory (test T-O2). The spec
quotes 1.6–1.9¢/√s and a $2–4 daily span on the v1.1 oracle.

That calmness is one root cause of the market's low volatility ([KNOWN_ISSUES.md](KNOWN_ISSUES.md),
K1 and K5), to be addressed in R4 (calm/stressed periods, information jumps).

## Why v1.2 pre-generates the path

`SparseMeanRevertingOracle` generates the value **lazily**: each query draws one random number
from the oracle's RNG, conditioned on the time since the previous query. The realised path
therefore depends on how many queries happen and when. On seed 42, with vs without one news
item, the true value was identical for 10 minutes, $0.10 apart at 30 minutes and about $2
apart after 2 hours (spec v1.2 §0.4 P2). Megashock times also came from numpy's *global* RNG.
Consequences: no clean counterfactuals ("what if this news had not happened?"), and in future
a user's trade would change the company's true value.

### Design

`PregeneratedOracle(mkt_open, mkt_close, symbols, grid_s=1.0)`:

1. At construction, for each symbol, build the grid t_k = mkt_open + k · grid_s, k = 0 … N,
   N = ⌈(mkt_close − mkt_open) / grid_s⌉, and call `generate_path(params, times, rng)`.
2. `generate_synthetic_ou` draws, from the symbol's dedicated `random_state` only and in this
   fixed order: the full vector ε₁ … ε_N; then the number of megashocks
   (Poisson(λ · span)), their times (uniform over the session), sizes and signs. It applies
   the exact transition above at every step, computing 1 − a² as `-expm1(-2κd)` for precision
   (κd ≈ 1.7e-7 at 1 s). A shock enters the OU state at the first grid point at or after its
   time and then evolves with the OU dynamics (as `v_adj` did in the sparse oracle). Values
   are stored as floats in cents.
3. `f_log[symbol]` holds every grid point as `{"FundamentalTime", "FundamentalValue"}` (integer
   cents), so the exchange and the export keep working unchanged. The export downsamples it
   (LTTB, ≤ 2000 points).

`rmsc04_ekf` builds the path from 09:30 to **16:00 whatever the session length**, from the
symbol's RandomState whose seed is the first draw after `np.random.seed(seed)`, before any
agent. The path is therefore identical across agent counts, news items and end times.

### Interface

| Method | Returns |
|---|---|
| `observe_price(symbol, t, random_state, sigma_n=1000)` | the value at the last grid point ≤ t, rounded to integer cents and floored at 0. With `sigma_n = 0` this is exact; otherwise `round(N(value, √sigma_n))` drawn from the **caller's** RNG. `sigma_n` is a variance. Before the open: v₀; at or after the close: the last value. |
| `get_daily_open_price(symbol, mkt_open)` | v₀ = r̄, in integer cents |
| `value_at(symbol, t)` | the exact float value in force at t |
| `path(symbol)` | `(times_ns, values)` copies of the whole path |
| `f_log[symbol]` | list of `{"FundamentalTime": t_k, "FundamentalValue": int}` |

**Why a step function.** Between two grid points the value is held at the earlier point, so an
agent at time t never sees a value from after t (no look-ahead). With a 1 s grid the step is
about 1.6¢, far below the observation noise of any agent.

### The reproducibility guarantee

The true-value path is a pure function of (seed, oracle parameters, grid, session window). It
does not depend on agent counts, news, the session end time, the order or number of
observations, or the global numpy RNG. Tested by T-O1 (also invariant I2: three different
markets on one seed give bit-identical paths) and by `test_path_is_pure_function_of_seed`.

Note: seed 42 in v1.2 gives a different true-value path from seed 42 in v1.1, because the
path is now drawn in one block instead of query by query.

## Path source "scenario" (v1.3, realism lab)

Spec v1.3 §6.1. `generate_scenario_ou` is the `synthetic_ou` path plus scripted **events**,
used only by the realism lab's scenarios ([REALISM_LAB.md](REALISM_LAB.md)):

| Event | Form (oracle) | Effect |
|---|---|---|
| value jump | `{"type": "jump", "t_ns": int, "cents": float}` | adds J to the OU innovation at the first grid point at or after `t_ns`, so the value steps by J and then decays like any OU deviation: J · a^(k − k0) with a = e^(−κ · 1 s). Over 5 hours the jump loses less than 0.0003%: permanent in practice |
| volatility window | `{"type": "vol", "t0_ns": int, "t1_ns": int, "mult": float}` | multiplies the innovations of every grid step with t0_ns ≤ t_k < t1_ns by `mult`; the path before t0_ns is unchanged |

**No extra random draws.** Both sources call the same helper `_ou_draws` (the ε vector, then
the megashock count, times, sizes and signs, from the symbol's RandomState), so they cannot
diverge: with `events = []` the scenario path is bit-identical to `synthetic_ou` (test T-L1,
20 seeds). Algorithm: (1) the draws; (2) innov[1:] = sd · ε, scaled inside volatility windows;
(3) megashocks as before; (4) jumps; (5) x = lfilter([1], [1, −a], innov), value = r̄ + x.

**What the oracle records.** `oracle.events[symbol]` holds the events as applied to the grid
(for a jump the grid time `t_grid_ns` it landed on; for a window its first step and number of
steps), and each one is logged at INFO level. The dashboard payload carries them as
`oracle_events` (empty in normal runs).

**How the lab asks for it.** `rmsc04_ekf.build_config(oracle_events=[...])` takes offsets from
the 09:30 open and jumps in % of r̄: `{"type": "jump", "at": "01:30:00", "pct": 2.0}` (= +$20.00
at 11:00) or `{"type": "vol", "start": "01:30:00", "end": "02:30:00", "mult": 3.0}`. With
`oracle_events=None` (the default) the path source stays `synthetic_ou` and the market is
bit-identical to v1.2 (invariant I8). Because the symbol's RandomState is drawn exactly as
before, a scenario and its baseline share every agent's parameters and random stream
(test T-L4): only the true value differs, and only from the event on.

## Path source "living_v1" (v1.5, spec A3): day types, stress, information news

`build_config(value_process="living_v1", day_type="auto"|"calm"|"normal"|"volatile",
auto_news=True)`. The v1.4 default stays `"synthetic_ou"` until milestone A9 (I8). Code:
`living_v1_day` in `oracles/pregenerated_oracle.py`; constants `LIVING_V1` in
`configs/param_ranges.py`.

**Model** (cents, seconds; the 1 s grid 09:30–16:00, N = 23,401 points):

    v_{k+1} = r_bar + (v_k − r_bar)·a + sd0 · m_day · U(t_k) · S_k · eps_k + J_{k+1}

| piece | value |
|---|---|
| sd0 | the synthetic_ou step sd with fund_vol = 7.1 / sqrt(1e9) c/sqrt(ns), i.e. sigma_base = 7.1 c per sqrt(s) = 5.5 bps per minute at $1000; a = exp(−kappa_oracle·d) (a jump decays by 0.3% over a day) |
| m_day | calm 0.6, normal 1.0, volatile 1.6 |
| U(t) | (1 + 0.6·e^(−t/0.5) + 0.4·e^(−(6.5−t)/0.5)) / c_U, t in hours since 09:30, c_U = mean over the oracle grid (the full session, whatever end_time is), so mean U = 1 |
| S_k | stress chain, S in {1, 2.5}, S_0 = 1; from 1, u_k < p_in = e_day/(6.5·3600) enters (e_day calm 0.2, normal 0.7, volatile 1.5 episodes a day); from 2.5, u_k < 1/2700 leaves (mean 45 min) |
| J | information jumps: count ~ Poisson(2 / 3 / 4); times ~ U(09:35, 15:55), sorted; size r_bar·min(LogNormal(ln 0.002, 0.6), 0.02) (median 0.20%, cap 2%); sign 50/50. A jump enters at the first grid point >= its time |
| megashocks | none |

Scripted `oracle_events` (jump / vol windows, the lab's S2 etc.) are applied on top, as in
"scenario", without extra draws.

**Draw order** (the symbol's own RandomState; fixed):
1. one uniform for the day type: always drawn, used only when `day_type="auto"` (calm if
   u < 0.30, normal if u < 0.80, else volatile), so a seed's path is the same whether its type
   was drawn or requested (DECISIONS A3);
2. N uniforms for the stress chain;
3. N − 1 normals eps;
4. news count, times, sizes, signs (uniform < 0.5 gives +), then one template index per jump,
   uniform within the jump's bucket. The template draws are last, so the path never depends
   on the templates.

**Day info:** `oracle.day_info(symbol=None)` returns `{"day_type", "stress_episodes": [(start_ns,
end_ns)], "news": [(t_ns, J_cents, headline, sentiment, bucket)]}` (None for other sources).
With `auto_news`, build_config enqueues each news item on the NewsOracleAgent at `t_ns`
(the jump's grid time): public news AT the jump (NEWS.md).

**Verified statistics of the value** (T-O5, seeds 0–199 per type; spec A3.3 in brackets):

| day type | 1-min sd median (bps) | daily move sd (%) | per-day 30-min regime contrast, median / p90 |
|---|---|---|---|
| calm | 3.76 (3.8) | 0.75 (0.78) | 2.51 / 4.29 |
| normal | 6.24 (6.3) | **1.28 (1.49)**, outside ±10%, strict xfail | 2.42 / 3.63 |
| volatile | 10.77 (11.3) | 2.21 (2.42) | 2.73 / 3.98 |
| default mix 30/50/20 | 6.13 (6.2) | 1.43 (1.53) | 2.43 / 4.02 |

The model is implemented exactly as A3.1; the normal-day daily sd in A3.3 is about 11–14% above
what this model gives (1,500 days: 1.32%), see DECISIONS (A0, A3). The value's own regime
contrast (2.4–2.7 median) is why G11 per day is moved to "reported" (A6.4).

**Guarantees (tests/test_living_oracle.py):**
- T-O6: day-type override (requesting the type that was drawn gives the same path), and the auto mix over 2000 seeds (31.8 / 48.7 / 19.5%).
- T-O7: the path and day info are identical across agent mixes, news on/off, informed mode and session length (I2 extended).
- T-O8: headline bucket and sign; T-O9: synthetic_ou unchanged (seed-42 path hash).
- The stress chain equals the per-step loop, and the draw order is re-implemented independently.
- A scripted +2% jump adds exactly J·a^(k−k0).

## Future path sources (designed for, not built)

New sources are one function `generate(params, times_ns, rng) -> values`, registered in
`PATH_SOURCES` and selected by `params["path_source"]`:

- `"csv"`: read a (time, value) series and rescale it to r̄ (replay the true-value shape of a real stock or event).

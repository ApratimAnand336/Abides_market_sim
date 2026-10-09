# Testing

Three layers, from fast to slow:

1. **Unit tests**: the maths of each agent and helper, with no simulation kernel (seconds).
2. **Invariant tests**: short real simulations that check properties which must *always* hold: determinism, conservation of cash and shares, book sanity, liveness (added in v1.2, milestone W4).
3. **Acceptance runs**: full trading days with the release's targets, reported in `docs/v<version>/REPORT.md` (about 25 s per simulated day).

## How to run

```bash
# everything except the gym runner (needs the optional `gym` package)
python -m pytest abides-markets/tests api/tests -q --ignore=abides-markets/tests/test_gym_runner.py

# one area
python -m pytest abides-markets/tests/test_fundamental.py -q
python -m pytest api/tests -q

# acceptance (v1.1 targets)
python scripts/acceptance_v1_1.py                # runs A and B, full day
python scripts/acceptance_v1_1.py --end 11:00:00 --runs A   # quick smoke run
```

`api/tests/test_export.py` builds one real 30-minute simulation (seed 42, 3 + 3 of our
agents, three news items) once per session and checks the payload against it.

## What is covered

| File | Tests | Covers |
|---|---|---|
| `abides-markets/tests/test_fundamental.py` | 16 | FundamentalistAgent: no nudge (T-F1), gain does not decay (T-F2), step tracking (T-F3), value-speed estimate (T-F4), target-position sizing and dead band (T-F5), side from d (T-F6), news shift (T-F7), log keys, long-only orders; v1.2 edge z = gap/√(P+R) (T-F8), a typical 13¢ gap holds (T-F9), a $6 gap buys within the step cap (T-F10) |
| `abides-markets/tests/test_momentum_ekf.py` | 43 | MomentumEKFAgent: trend detection, noise rejection, numerical stability, news priming, state machine, ratchet, sizing, endowment; v1.1 T-M1 … T-M5 (ramp bias, detrended variance, ratchet follows down, re-entry, persistent stop) |
| `abides-markets/tests/test_oracle.py` | 7 | PregeneratedOracle: the same seed gives the same path in three different markets (T-O1, also invariant I2; three 1-hour simulations), increment std matches OU theory over 200 seeds (T-O2), exact observations are the step function with clamped ends (T-O3), the noise comes from the caller's RNG (T-O4), the path ignores the global RNG, megashocks, unknown sources |
| `abides-markets/tests/test_market_maker.py` | 4 | Market maker cold start and liveness: without value agents the market trades and each MM quotes in every 10-minute window (T-M6, invariant I6); each MM wakes ≥ 90% of duration/mean wake and is never silent for 10 minutes, with and without value agents (T-M7, invariant I7); the spread cap does not bind in the default market. Two 1-hour simulations, ≈8 s |
| `api/tests/test_export.py` | 22 | payload validity (schema, no NaN), trade counts, close, mark-to-market, equal-length series, size budget, news records, candles, P&L vs holding, population (volume shares sum to 100), gap half-life on a synthetic AR(1) |
| `api/tests/test_server.py` | 18 | HTTP validation (readable 400s, including population bounds), presets, 404s, run listing |
| `abides-markets/tests/orderbook/*`, `test_orders.py`, `test_generators.py`, `test_sim.py`, `agent_utils_test.py` | 48 | upstream ABIDES order book and utilities |

## Latest results

| Date | Branch / commit | Result |
|---|---|---|
| 2026-10-09 | `v1.2` at 3c0b859 (v1.1 code) | 147 passed, 1 failed (`test_ou_process`, pre-existing, see below) |

### Pre-existing failures (not caused by our code)

- `test_gym_runner.py`: needs the `gym` package, which is not installed. Excluded with `--ignore`.
- `test_ou_process.py::test_ou_process`: a pandas/`datetime` incompatibility inside the upstream
  `MeanRevertingOracle` (not used by our market). It fails identically on `origin/dashboard`.

## Invariants

Added in milestone W4 (`abides-markets/tests/test_invariants.py`). This section lists each
invariant, what it guarantees and its run time once they exist.

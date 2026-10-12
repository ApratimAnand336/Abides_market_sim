# FinVerse engine documentation

FinVerse is a simulated stock market where students trade against AI investors and learn
the theory as they go. The engine is a fork of [ABIDES](https://arxiv.org/abs/1904.12066)
(J.P. Morgan's discrete-event market simulator). We add our own investors, a news system and
a web dashboard.

These pages are written for a newcomer: a new teammate, a judge or a mentor. Each page
starts in plain language, then gives the maths, then points to the code. Every number names
its source (run configuration, seed, date). The documents are **living**: each milestone
updates them in the same commit as the code (spec v1.2, Part 1).

## Index

| Page | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, the agent population, units, every source of randomness |
| [ORACLE.md](ORACLE.md) | The hidden "true value" of the company: what it is, its maths, the v1.2 reproducible design |
| [AGENT_FUNDAMENTALIST.md](AGENT_FUNDAMENTALIST.md) | Our Kalman-filter value investor: maths, parameters, logs, history |
| [AGENT_MOMENTUM.md](AGENT_MOMENTUM.md) | Our Kalman-filter trend follower: maths, parameters, logs, history |
| [AGENTS_ABIDES.md](AGENTS_ABIDES.md) | The stock ABIDES agents (noise, value, market makers, MA momentum) and their limits |
| [DECISIONS.md](DECISIONS.md) | Decision log: what was decided, when, why, and what was rejected |
| [CHANGELOG.md](CHANGELOG.md) | What changed in v1.0, v1.1 and v1.2, by file |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Where the simulated market is still unrealistic, with status and plan |
| [TESTING.md](TESTING.md) | Unit, invariant and acceptance tests: how to run them, what they guarantee |
| [REALISM_LAB.md](REALISM_LAB.md) | The realism lab (v1.3): metrics, bands, scenarios, the 20-seed runner and how to read its reports |

The specifications live in [`docs/specs/`](../specs/) (`spec_v1.1.txt`, `spec_v1.2.txt`, `spec_v1.3.txt`).
Per-release reports with acceptance numbers and screenshots are in `docs/v1.1/` and `docs/v1.2/`.

## Running things

All commands run from the repository root. Python 3.13 with the packages in
`requirements.txt`, and `abides-core` and `abides-markets` installed in editable mode
(`install.sh`).

**One simulation from the command line** (writes the dashboard payload to `runs/<run_id>.json`):

```bash
python -m api.cli export --seed 42 --end-time 16:00:00 --num-fund 20 --num-mom 12 \
    --news "00:10:00|0.9|Company announces record quarterly earnings"
```

A full day (09:30–16:00) with 20 + 12 of our agents takes about 25 s on the development
laptop (measured 2026-10-08).

**The dashboard** (FastAPI backend on :8000, React frontend on :5173):

```bash
scripts/dev.sh                      # both together
# or separately:
python -m uvicorn api.server:app --port 8000
cd web && npm install && npm run dev
```

Open http://localhost:5173, choose the parameters in the sidebar and press *Run Simulation*.
Runs are cached by their parameters and the engine version, so asking for the same run
twice loads it instantly.

**Tests** (see [TESTING.md](TESTING.md)):

```bash
python -m pytest abides-markets/tests api/tests -q --ignore=abides-markets/tests/test_gym_runner.py
python scripts/acceptance_v1_2.py --run A  # one full-day acceptance run (~25 s); also B, C, Z
python scripts/acceptance_v1_2.py --report # the acceptance table
```

## Glossary

| Term | Meaning |
|---|---|
| **bid / ask** | The best (highest) price someone is willing to buy at, and the best (lowest) price someone is willing to sell at. |
| **mid** | (bid + ask) / 2: the usual "current price" of the stock. |
| **spread** | ask − bid. A measure of liquidity: how much it costs to trade immediately. One cent is the minimum (one tick). |
| **cents** | All prices inside the engine are integer cents ($1000.00 = 100,000). Variances are in cents². The dashboard shows dollars. |
| **ns** | All times inside the engine are integer nanoseconds since the epoch. The dashboard shows clock time or seconds since the 09:30 open. |
| **oracle / true value / fundamental** | The simulator's hidden "what the company is really worth" at each moment. Agents never see it exactly. See [ORACLE.md](ORACLE.md). Not to be confused with the *news oracle* (an agent that broadcasts headlines). |
| **belief x̂ (x_hat)** | A Kalman-filter agent's current best estimate. For the fundamentalist it is the estimated value (cents); for the momentum agent it is the estimated log-price level and trend speed. |
| **P** | The variance of the belief: how unsure the agent is about x̂ (cents²). |
| **R** | Observation noise variance: how noisy the agent thinks one price reading is (cents²). |
| **Q** | Process noise: how much the agent thinks the value can move between two looks (cents²). Without Q the agent stops learning. |
| **K** | Kalman gain, P_pred / (P_pred + R): the fraction of a surprise the agent believes. K = 0.03 means it moves 3% of the way toward each new price. |
| **z (edge)** | The fundamentalist's signal-to-noise ratio, (x̂ − mid) / √(P + R) (v1.2): how many "normal wiggles" the price is away from its belief. |
| **endowment** | Our agents start with half of their $100,000 in stock (50 shares at $1000), so they can sell as well as buy. |
| **P&L** | Final value − starting value, with everything valued at the close. |
| **P&L vs holding** | Final value − what the starting cash and shares would be worth at the close. It removes the endowment's price move, so it measures trading skill only. Summed over every agent in the market it is exactly $0 (every trade has two sides). |
| **ER (Kaufman efficiency ratio)** | \|net price change\| / sum of \|individual changes\| over a window: 1 = a clean straight move, 0 = pure back-and-forth chop. |
| **tick** | The smallest price step, one cent. |

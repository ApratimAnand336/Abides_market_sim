# Known issues: where the simulated market is still unrealistic

Each issue has a status and the roadmap stage that addresses it (R1 = spec v1.2 … R6;
see [DECISIONS.md](DECISIONS.md), "Roadmap"). Real-market references are approximate
stylized facts (R. Cont, *Empirical properties of asset returns: stylized facts and
statistical issues*, Quantitative Finance, 2001).

**Source of the numbers (v1.4, R3 closed 2026-10-14):** the final market P0 (the default since
v1.4: 0 value agents, 60 informed fundamentalists of design D-60fl2M, 12 momentum EKF, 1000
noise, 2 market makers, budget on; full day). The values are 20-seed medians [p10–p90], seeds
42, 7, 1–6, 8–19, engine v1.3-c1dfa51 (2026-10-13/14), from
[`docs/v1.4/lab/RESULTS.md`](../v1.4/lab/RESULTS.md). The v1.3 numbers (C-DEF, 97 value agents)
are kept in brackets "v1.3:" and in [`docs/v1.3/lab/BASELINE.md`](../v1.3/lab/BASELINE.md).

## Open

| # | Issue | Measured (P0, 20 seeds) | Real markets / band | Root cause | Plan |
|---|---|---|---|---|---|
| K1 | Volatility too low | 1-min σ **0.62 bps** [0.55–0.71] (v1.3: 0.71); a day moves 0.20% (std over seeds) (G1, G2 FAIL) | 5–10 bps; 1–2% a day | calm synthetic value (≈ 1.2 bps a minute) and a price that is smoother than the value minute by minute (K14) | R4 (value dynamics) + endogenous volatility |
| K3 | Weak volatility clustering | CS **0.087** [0.05–0.16], PS 0.032 (G5 **WARN**; v1.3: FAIL) | CS ≥ 0.10 | constant information flow; jumps and research arrivals give some clustering | R4 |
| K4 | Price pinned to value | gap std **$0.197** [0.18–0.22], corrected half-life **3.6 min** [3.0–5.6] (G9, G10 FAIL), corr(mid, value) 0.963 (v1.3: $0.145, 1.5 min, 0.979) | $1–3; 30–90 min | 60 informed agents research every 1–5 min with 10–50¢ noise; slower or noisier research gives larger and slower gaps (D-60sh2M: $0.53, 38 min) but fails T1/T2 | R4 / R5 calibration |
| K5 | No regimes | regime contrast **2.47** [1.9–4.0] (G11 FAIL; G11 per day is REPORTED since v1.5 A6.4, regimes graded across days) | ≥ 5 | constant-volatility value process | R4 |
| K6 | News: fast overreaction | a +0.9 headline moves the price +5.5 bps within 0.27 min and half of it reverses within 1.1 min (v1.3: +0.9 bps at 22 min); beliefs move +$0.82 | news moves prices persistently when it carries information | headlines move beliefs only; the true value does not change on news (R4 "information news") | R4 |
| K7 | Flat intraday activity | u_ratio **1.14** [1.06–1.23] | U-shaped volume, well above 1 | agents wake at constant rates | R4/R5 |
| K8 | Market makers' P&L | total vs holding −$107 [−2,582 – +1,977] per run: about even, volatile | MMs earn the spread on average | adverse selection by informed agents; no inventory management (R4) | R4 |
| K11 | Price impact | β = **0.94** [0.81–1.12] (sizes 0.5/1/5% of volume; G12 FAIL); recovery I_perm/I_peak **0.23** (G13 PASS; v1.3: −0.02); a 1% buy moves the price 0.56 bps at the end, 0.29 bps permanently; selling costs more than buying (shortfall 1.14 vs 0.72 bps) | β ≈ 0.5, partly permanent | informed agents absorb the flow (5,498 of 6,000 shares) and update beliefs from it | R4/R5 |
| K14 | **Price too smooth at 1–5 min** (T3 FAIL) | price/value volatility ratio **0.49** at 1 min, 0.57 / 0.75 / 0.84 / 0.90 at 5 / 15 / 30 / 60 min | ≥ 0.90 at 1 min | value news reaches the price only through research readings (every 1–5 min per agent), and nothing else moves the price at short horizons | R4: short-horizon variation not driven by research arrivals (endogenous volatility, livelier value process) — D-R3-8 |
| K15 | **The spread widens 15–16× after a value jump while informed agents disagree** (T6 FAIL) | spread_jump_ratio **14.8 / 16.0** (±2% jump, p95 spread in the 30 min after vs the same seed's baseline; 148 ticks); the book never empties (one-sided share 0); 33% of informed agents updated at +5 min, 86% at +10 | ≤ 3× | informed quotes split into an "old belief" and a "new belief" cluster with a hole between them; MMs do not fill it | R4: market makers with inventory, quoting around the last trade under stress — D-R3-8 |
| K16 | **Informed budget slightly exceeded right after jumps** (new in N5) | in 13 of 100 jump runs, 1–3 fills by 1–2 informed agents end beyond [−0.5, 1.5] × wealth, at most 1.507× / −0.509× (`scripts/diag_informed_bounds.py`); quiet markets within ±1 share (T-N5, I4) | the bounds of spec v1.4 §4.5 | §4.5 checks at the order's limit price (a borrowing or short agent then fills at a better price) and does not count orders whose cancellation is still in flight | **A6 (v1.5): fixed behind `informed_budget_v2`** (default off until A9). The diagnosis: marketable orders of borrowing longs and shorts fill at once at a better price than the limit, which is the worse end for them. v2 checks both ends of the fill range and counts own open orders. Result: 0 exposure-increasing breaches on 15 failing jump runs. Left over: mark-to-market drift alone (a reducing fill after a jump, ≤ 0.7 pp), which no order rule can stop; owner question in DECISIONS A6 |

What passes on P0: T1/G3 (ac1 −0.005), T2/G4 (VR(5) 1.2488), T4/G7 (vv_corr +0.53), T5 (volume
×2.5 after jumps), T7 (informed agents profit), spreads (0.30 / 1.0 bps; G8), G13. See
[`docs/v1.4/lab/RESULTS.md`](../v1.4/lab/RESULTS.md).

## R4a candidate R-25M15003 (a-confirm, N-C normal day, 20 seeds, engine v1.4-d498ee4, 2026-10-17)

These are the open issues measured on the design that becomes the default in A9 (`docs/v1.5/lab/RESULTS_A.md`). The table above stays the P0 record until the switch.

| # | R4a measured | Status vs band |
|---|---|---|
| K1 | σ1m **4.86 bps**; daily sd across seeds (D-mix) **0.99%** | both just below the band (A-T1, A-T3 FAIL) |
| K3 | CS **0.065**, PS 0.0008 | worse than P0 (A-T7 FAIL) |
| K4 | gap std **$0.54**, half-life read 1 min | larger gaps, still fast |
| K5 | RS across days (D-mix) **2.40**; per-day contrast 3.8 (reported) | A-T11 FAIL by 0.1 |
| K6 | hype +0.9 headline: R_peak **+21.6 bps** at 0.27 min, half reverts in 0.77 min; beliefs +$1.11 | stronger overreaction than P0 |
| K7 | u_ratio **1.19** | A-T12 FAIL |
| K8 | MM (2 LPs) group P&L vs hold **−$3,572** median; +$1,325 on volatile days | A-T10 FAIL |
| K11 | β **1.1** [0.94–1.86], recovery 0.36 | G12 FAIL, G13 PASS |
| K14 | price/value vol ratio **0.81** at 1 min | improved from 0.49, A-T5 FAIL |
| K15 | spread_jump_ratio **2.49 / 2.98** | **fixed on R4a** (A-T9 PASS) |
| K16 | 0 fills that increase exposure out of bounds in 240 runs (informed_budget_v2) | fixed behind the A9 switch |

## Closed in v1.4 (R3, measured on P0, 20 seeds, 2026-10-14)

| # | Issue | Fix | Status |
|---|---|---|---|
| K2 | Predictable returns (ac1 +0.37, VR(5) 1.90) | informed fundamentalists price from their beliefs (spec v1.4 Part 4); no ValueAgents | **closed**: ac1 −0.005, VR(5) 1.25 (T1, T2 PASS; T2 by 0.001) |
| K9 | Fundamentalists have no information edge (−$112 for all 20) | research channel (informed mode) | **closed**: +$1,023 total, +$112 median per agent (T7) |
| K10 | Stock ABIDES agents have no budget limits | GrossLimit L = 2 on Noise/Value/ABIDES-Momentum (spec v1.4 Part 5); MMs exempt until R4 | **closed** (I9); effect alone: volume −28% in the v1.3 market |
| K12 | Dashboard payload large (8.41 MB) | detailed series for ≤ 20 fundamentalists, summaries for the rest (spec v1.4 §6.3) | **closed**: 4.60 MB for a full default day; 4.46 MB with 200 fundamentalists |
| K13 | Volume falls when prices move (vv_corr −0.25; −25% after a jump) | volume now comes from informed disagreement | **closed**: vv_corr +0.53 (T4), volume ×2.5 after a ±2% jump (T5) |
| — | v1.3 limitation "with num_mm = 0 and num_value = 0 the market cannot start" | informed agents quote into an empty book | **closed**: P0 without market makers trades all day (19.6–23.3k executions, 5 seeds; L3) |

## Closed in v1.2 (verified 2026-10-09, acceptance runs A, B, C, Z)

| # | Issue | Fix | Status |
|---|---|---|---|
| P2 | True value not reproducible (lazy oracle; global RNG for megashocks) | pre-generated, seed-stable path ([ORACLE.md](ORACLE.md)) | **closed**: A and B paths bit-identical; T-O1/I2 |
| P3 | Market makers die when the book is empty at their first wake | cold start + guaranteed rescheduling ([AGENTS_ABIDES.md](AGENTS_ABIDES.md)) | **closed**: full-day runs A–Z, both MMs alive (353–397 wakes of 390, longest silence ≤ 439 s) |
| P4 | The market cannot start without value agents (when at least one MM exists) | follows from P3, plus the MM spread cap | **closed**: Run Z trades all day (2,539 trades) |
| P1 | Fundamentalist overtrading and herding | z = gap / √(P + R) ([AGENT_FUNDAMENTALIST.md](AGENT_FUNDAMENTALIST.md)) | **closed**: median 166–192 shares/day per agent, holdings 48–53 (p10–p90) |

## Known limitation kept on purpose

- (v1.3) With `num_mm = 0` **and** `num_value = 0` the market could not start: closed in v1.4
  (informed agents quote into an empty book).
- Without value agents nothing anchors the price. With market makers the market now runs, but
  on seed 42 (5 + 4 of our agents) the price slid from $999.75 to about $589 within the first hour
  (2026-10-09). This is the baseline R3 starts from, not a v1.2 target.
- One fundamentalist per run trades heavily: 790 [552–1,430] shares a day vs a median of 160, i.e.
  0.067% of volume (at most 0.13%; never above 1% in any of the 360 lab runs). Kept on purpose
  (owner decision D-R2-4): a personality, not a bug.
- The realism lab's half-life estimator reads a true 45–90 min half-life as 21–27 min on one day
  ([REALISM_LAB.md](REALISM_LAB.md)).
- Without value agents (Run Z) the market runs but decouples from value: corr(mid, value) −0.18,
  mean gap $9.60, 1-min excess kurtosis 219, spreads up to $22.50 (seed 42, 20 + 12, full day).

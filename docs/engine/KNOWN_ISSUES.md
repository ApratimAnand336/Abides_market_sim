# Known issues: where the simulated market is still unrealistic

Each issue has a status and the roadmap stage that addresses it (R1 = spec v1.2 … R6;
see [DECISIONS.md](DECISIONS.md), "Roadmap"). Real-market references are approximate
stylized facts (R. Cont, *Empirical properties of asset returns: stylized facts and
statistical issues*, Quantitative Finance, 2001).

**Source of the numbers (v1.3):** the realism lab's 20-seed baseline, configuration C-DEF (full
day, 20 fundamentalists + 12 momentum, 97 value agents; seeds 42, 7, 1–6, 8–19), measured
2026-10-12: median [p10–p90] ([`docs/v1.3/lab/BASELINE.md`](../v1.3/lab/BASELINE.md)). Grades are
those of the provisional large-cap bands ([REALISM_LAB.md](REALISM_LAB.md)). The v1.2 single-run
numbers are kept in [`docs/v1.2/REPORT.md`](../v1.2/REPORT.md).

## Open

| # | Issue | Measured (20 seeds) | Real markets / band | Root cause | Plan |
|---|---|---|---|---|---|
| K1 | Volatility too low | 1-min σ **0.71 bps** [0.63–0.77]; a day moves 0.19% (std over seeds); the price has only **58%** of the true value's own 1-min volatility [0.54–0.63] (G1, G2 FAIL) | 5–10 bps; 1–2% a day | calm synthetic value (≈ 1.2 bps a minute) **and** a price that trails it (spec v1.3 §0.5, confirmed) | R4 (value dynamics) + endogenous volatility |
| K2 | Predictable returns | lag-1 autocorrelation **+0.37** [0.31–0.43]; VR(5) **1.90** [1.74–2.15] (G3, G4 FAIL) | ≈ 0; VR ≈ 1 | the price trails the value step by step | R3/R4 |
| K3 | Weak volatility clustering | CS **0.038** [0.014–0.079], PS ≈ 0 (G5 FAIL); \|r\| lag-1 0.20 | CS ≥ 0.10, slowly decaying | constant information flow | R4 |
| K4 | Price pinned to value | gap std **$0.145** [0.132–0.156], half-life **1.5 min** [1.3–2.0], corr(mid, value) 0.979 (G9, G10 FAIL). With 20 value agents: $0.26 / 3.9 min | $1–3; 30–90 min | 97 value agents see the value every ≈ 175 s | R3 |
| K5 | No regimes | regime contrast **2.39** [1.81–3.09] (chance alone ≈ 1.55; G11 FAIL) | ≥ 5 | constant-volatility value process | R4 |
| K6 | News barely moves the price | a ±0.9 headline: beliefs move ±$0.69 (median), the price does not move measurably (R_peak 0.8–0.9 bps = divergence noise); a +2% value jump is priced only after ≈ 12 min, through a liquidity gap | news moves prices, with more volume | value agents pull the price back; the true value never changes on news; nobody supplies liquidity at a new price | R3/R4 |
| K7 | Flat intraday activity | u_ratio **1.16** [1.11–1.18] | U-shaped volume, well above 1 | value agents (87% of volume) wake at a constant rate; noise agents' single wake is U-shaped but small | R4/R5 |
| K8 | Market makers' P&L | total vs holding +$1,110 [−16,100 – +6,090] over 20 seeds: not a loss every day (v1.2's three runs all lost), but very volatile | MMs earn the spread on average | adverse selection by value agents; inventory skew disabled (`mm_skew_beta = 0`) | R4 |
| K9 | Fundamentalists have no information edge | median −$2.92 per agent vs holding [−7.4 – +0.3]; −$112 for all 20 | — | they only see the price | R3 (research channel) |
| K10 | Stock ABIDES agents have no budget limits | — | margin and short-sale limits | `ignore_risk = True`: unlimited shorting and leverage | R3 |
| K11 | Price impact | **measured (v1.3):** a 1% order over 5 min moves the price 1.4 bps [0.9–2.6] (shortfall 1.2 bps); 5%: 4.9 bps at the end, 23 bps peak, 20 bps shortfall, up to 171 bps; exponent β = **0.90** (CI 0.77–1.25; G12 FAIL); fully transient (I_perm/I_peak ≈ 0; G13 FAIL); noise floor 0.40 bps | β ≈ 0.5, partly permanent | value agents (unlimited shorting) absorb small orders, MMs large ones; the value never changes | re-measure after R3 (D-R2-5) |
| K12 | Dashboard payload large | 8.41 MB for a full day with 20 + 12 agents (v1.3; the realism block adds 6.4 KB) | budget 8 MB | per-agent series | open |
| K13 | Volume falls when prices move | volume–volatility correlation **−0.25** [−0.35 – −0.09] (G7 FAIL); −25% volume after a value jump, −12% in a volatility burst | ≥ 0.30 | — (to investigate; see BASELINE.md §7) | R3/R4 |

What passes: spreads (median 1 tick, p95 3; G8) and fat tails on the median (kurtosis 3.02, on the
boundary; G6, pass share 50%).

## Closed in v1.2 (verified 2026-10-09, acceptance runs A, B, C, Z)

| # | Issue | Fix | Status |
|---|---|---|---|
| P2 | True value not reproducible (lazy oracle; global RNG for megashocks) | pre-generated, seed-stable path ([ORACLE.md](ORACLE.md)) | **closed**: A and B paths bit-identical; T-O1/I2 |
| P3 | Market makers die when the book is empty at their first wake | cold start + guaranteed rescheduling ([AGENTS_ABIDES.md](AGENTS_ABIDES.md)) | **closed**: full-day runs A–Z, both MMs alive (353–397 wakes of 390, longest silence ≤ 439 s) |
| P4 | The market cannot start without value agents (when at least one MM exists) | follows from P3, plus the MM spread cap | **closed**: Run Z trades all day (2,539 trades) |
| P1 | Fundamentalist overtrading and herding | z = gap / √(P + R) ([AGENT_FUNDAMENTALIST.md](AGENT_FUNDAMENTALIST.md)) | **closed**: median 166–192 shares/day per agent, holdings 48–53 (p10–p90) |

## Known limitation kept on purpose

- With `num_mm = 0` **and** `num_value = 0` the market still cannot start: no agent is
  willing to quote into an empty book. R3 gives our fundamentalist that ability.
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

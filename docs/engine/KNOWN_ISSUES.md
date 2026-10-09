# Known issues: where the simulated market is still unrealistic

Each issue has a status and the roadmap stage that addresses it (R1 = spec v1.2 … R6;
see [DECISIONS.md](DECISIONS.md), "Roadmap"). Real-market references are approximate
stylized facts (R. Cont, *Empirical properties of asset returns: stylized facts and
statistical issues*, Quantitative Finance, 2001).

**Source of the numbers:** the v1.2 acceptance runs A, B (seed 42, with/without one news item) and
C (seed 7), measured 2026-10-09: a full day, 20 fundamentalists + 12 momentum agents, 97 value
agents, v1.2 code ([`docs/v1.2/REPORT.md`](../v1.2/REPORT.md)). Where a number is still the spec's
pre-implementation measurement (spec v1.2 Appendix B) it says so.

## Open

| # | Issue | Measured | Real markets | Root cause | Plan |
|---|---|---|---|---|---|
| K1 | Volatility too low | 1-min return std 0.62–0.70 bps (≈ 2 %/year; spec App. B: 0.8–0.9 bps) | ≈ 15–40 %/year | calm synthetic value ([ORACLE.md](ORACLE.md)) + tight pinning by value agents | R4 |
| K2 | Predictable returns | 1-min lag-1 autocorrelation +0.33 … +0.40 | ≈ 0 | — (also present with none of our agents; see the v1.1 report) | R3/R4 |
| K3 | Weak volatility clustering | \|r\| lag-1 autocorrelation 0.05–0.20 | clearly positive, slowly decaying | constant information flow | R4 |
| K4 | Price pinned to value | gap half-life 1.3–1.4 min; corr(mid, value) 0.981–0.989 | mispricings last much longer | 97 value agents see the value every ≈175 s | R3 |
| K5 | No regimes | wildest 30-min volatility only 2–3× the quietest (spec App. B; not re-measured) | calm/stressed periods | constant-volatility value process | R4 |
| K6 | News barely moves the price | — | news moves prices | value agents pull the price back; the true value never changes on news | R3/R4 |
| K7 | Flat intraday activity | — | U-shaped volume (busy open and close) | value agents wake at a constant rate. *Note from the code:* noise agents' single wake is drawn from a U-quadratic distribution over 09:00–16:00 (`abides_core.utils.get_wake_time`), so their activity is already somewhat U-shaped; the value agents dominate volume (≈83%) and are flat | R4/R5 |
| K8 | Market makers lose money every day | $1.1k–9.5k each per day; −$3.0k to −$16.5k for the pair | MMs earn the spread on average | adverse selection by value agents; inventory skew disabled (`mm_skew_beta = 0`) | R4 |
| K9 | Fundamentalists have no information edge | median −$3 to −$5 per agent vs holding (−$112 to −$134 for all 20) | — | they only see the price | R3 (research channel) |
| K10 | Stock ABIDES agents have no budget limits | — | margin and short-sale limits | `ignore_risk = True`: unlimited shorting and leverage | R3 |
| K11 | Price impact of large orders not measured | — | needed before user trading | — | R2 |
| K12 | Dashboard payload large | 8.32–8.41 MB for a full day with 20 + 12 agents (v1.2; v1.1 was 8.98 MB) | budget 8 MB | per-agent series | R2 |

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
- One fundamentalist per run still trades heavily (1,433 / 1,456 / 687 shares in A / B / C vs a
  median of about 190). Not yet investigated.
- Without value agents (Run Z) the market runs but decouples from value: corr(mid, value) −0.18,
  mean gap $9.60, 1-min excess kurtosis 219, spreads up to $22.50 (seed 42, 20 + 12, full day).

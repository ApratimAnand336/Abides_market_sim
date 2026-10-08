# Known issues: where the simulated market is still unrealistic

Each issue has a status and the roadmap stage that addresses it (R1 = spec v1.2 … R6;
see [DECISIONS.md](DECISIONS.md), "Roadmap"). Real-market references are approximate
stylized facts (R. Cont, *Empirical properties of asset returns: stylized facts and
statistical issues*, Quantitative Finance, 2001).

**Source of the numbers:** spec v1.2, Appendix B, measured 2026-10-09 on seed 42 and seed 7,
a full day, 20 fundamentalists + 12 momentum agents, 97 value agents, with v1.2 sizing.
They are refreshed from the v1.2 acceptance runs in milestone W6.

## Open

| # | Issue | Measured | Real markets | Root cause | Plan |
|---|---|---|---|---|---|
| K1 | Volatility too low | 1-min return std ≈ 0.8–0.9 bps (≈ 2.6 %/year) | ≈ 15–40 %/year | calm synthetic value ([ORACLE.md](ORACLE.md)) + tight pinning by value agents | R4 |
| K2 | Predictable returns | 1-min lag-1 autocorrelation +0.14 … +0.37 | ≈ 0 | — (also present with none of our agents; see the v1.1 report) | R3/R4 |
| K3 | Weak volatility clustering | \|r\| autocorrelation ≈ 0.06–0.07 | clearly positive, slowly decaying | constant information flow | R4 |
| K4 | Price pinned to value | gap half-life 1–2 min; corr(mid, value) 0.95–0.99 | mispricings last much longer | 97 value agents see the value every ≈175 s | R3 |
| K5 | No regimes | wildest 30-min volatility only 2–3× the quietest | calm/stressed periods | constant-volatility value process | R4 |
| K6 | News barely moves the price | — | news moves prices | value agents pull the price back; the true value never changes on news | R3/R4 |
| K7 | Flat intraday activity | — | U-shaped volume (busy open and close) | value agents wake at a constant rate. *Note from the code:* noise agents' single wake is drawn from a U-quadratic distribution over 09:00–16:00 (`abides_core.utils.get_wake_time`), so their activity is already somewhat U-shaped; the value agents dominate volume (≈83%) and are flat | R4/R5 |
| K8 | Market makers lose money every day | $1.3k–12k each | MMs earn the spread on average | adverse selection by value agents; inventory skew disabled (`mm_skew_beta = 0`) | R4 |
| K9 | Fundamentalists have no information edge | lose slightly vs holding | — | they only see the price | R3 (research channel) |
| K10 | Stock ABIDES agents have no budget limits | — | margin and short-sale limits | `ignore_risk = True`: unlimited shorting and leverage | R3 |
| K11 | Price impact of large orders not measured | — | needed before user trading | — | R2 |
| K12 | Dashboard payload large | ≈ 9 MB for a full day with 20 + 12 agents (8.98 MB, v1.1 report, seed 42, run B) | budget 8 MB | per-agent series | R2 |

## Closing in v1.2 (verified in W6)

| # | Issue | Fix | Status |
|---|---|---|---|
| P2 | True value not reproducible (lazy oracle; global RNG for megashocks) | pre-generated, seed-stable path ([ORACLE.md](ORACLE.md)) | to verify |
| P3 | Market makers die when the book is empty at their first wake | cold start + guaranteed rescheduling ([AGENTS_ABIDES.md](AGENTS_ABIDES.md)) | to verify |
| P4 | The market cannot start without value agents (when at least one MM exists) | follows from P3 | to verify |
| P1 | Fundamentalist overtrading and herding | z = gap / √(P + R) ([AGENT_FUNDAMENTALIST.md](AGENT_FUNDAMENTALIST.md)) | to verify |

## Known limitation kept on purpose

- With `num_mm = 0` **and** `num_value = 0` the market still cannot start: no agent is
  willing to quote into an empty book. R3 gives our fundamentalist that ability.

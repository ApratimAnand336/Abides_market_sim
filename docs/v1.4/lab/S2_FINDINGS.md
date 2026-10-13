## 6. Findings and E11–E15 verdicts (spec v1.4.1 Part 4)

All numbers are 5-seed medians (seeds 42, 7, 1, 2, 3), engine v1.3-0d20335 (s2, s2r) and
v1.3-344fcbf (s1), 2026-10-13.

**Learning from prices did not spread information faster; it slowed the pricing of jumps.**
- Matched pairs, off → mod / off → strong (same N, T, S at $2M):
  - t90 after the +2% jump: +5.8 / +16.1 min;
  - informed share updated at +5 min: −0.01 / −0.03;
  - spread_jump_ratio: −6.3 / −10.8. The spread widens less after the jump, but the ratio
    is still 6.7–19, against a limit of 3.
- **Mechanism (diagnostic `scripts/diag_learning_jump.py`, seed 42, 11:00–11:30).** Most
  learning-driven belief moves go *away* from the new value, and they are 2–3× larger
  (toward value / toward stale):

  | design | moves | median move ($) |
  |---|---|---|
  | D-60fl2M-mod | 81 / 99 | 0.34 / 1.12 |
  | D-60fl2M-strong | 183 / 216 | 0.30 / 0.89 |
  | D-60sl2M-mod | 150 / 354 | 0.52 / 1.05 |

  The rule is symmetric. An agent that has just researched the new value sees a price that
  has not moved yet, so its gate opens. It inflates P, trusts the stale price and pulls its
  belief back. The agents who carry the information are talked out of it by the price they
  should be moving.
- **On quiet days the gate never opens** in the fast, precise designs. D-60fl2M-mod and
  D-60fl2M-strong are bit-identical there: both draw two values per agent, so every seed
  matches. Quiet-day differences between "off" and a learning design therefore come from the
  two extra draws per agent, which reseed the agents built later, not from learning.

| | verdict | evidence |
|---|---|---|
| E11 informed_share_updated ≥ 50% within 2–3 min | **not met** | updated at +2 min: 0–2% in every learning design (round 1: 0–2%); at +5 min, D-60fl2M: 33% off, 23% mod, 2% strong |
| E12 T6 passes for most learning designs | **not met** | T6 passes in 0 of 16 designs; spread_jump_ratio 6.7–19 (round-1 designs 8.7–49); never one-sided |
| E13 vol ratio at 15/30 min rises toward 1; T3 rises | **not met** | off → mod: 15 min −0.01, 30 min −0.01, 1 min −0.01; T3 stays 0.44–0.70 |
| E14 "strong" herds (higher ac1/VR(30), larger max gap); L6 catches it | **not observed** | quiet days identical to mod; max gap ≤ $1.7 in every design, so L6 never binds; after jumps strong is slower than mod (t90 +8.6 min) |
| E15 slow/noisy designs improve most | **not met; they worsen after jumps** | ac1 unchanged (−0.30 to −0.43); D-60sl2M t90 S2: 19.7 min off, 54 mod, 77 strong |

**Why T3 and T6 fail in the selected design (D-60fl2M, evidence).**
- **T3.** The price/value volatility ratio rises with the horizon: 0.49 (1 min), 0.57 (5),
  0.73 (15), 0.85 (30) and 0.93 (60 min). The price tracks value over an hour but is too
  smooth minute by minute. Value news reaches the price only through research readings every
  1–5 min per agent, so 1-minute value moves are mostly not traded on.
- **T6.** In the 30 minutes after a ±2% jump, the p95 spread is 8.7× (S2) and 16.7× (S2n) the
  same seed's baseline. The book never empties (one-sided share 0). It widens while beliefs
  are split between agents who have and have not researched the jump; 33% have updated at
  +5 min, 87% at +10 min.

**Other notes**
- **Close second.** D-60fl5M ties with the winner on 5/7 targets and loses the tie-break by
  0.002 in normalised miss.
- **N.** N = 30 fails L2 (279k shares) and N = 240 fails L5 (186 s, run one at a time to stay
  within memory).
- **A borderline L5 rejection.** D-120sh2M-strong was rejected on L5 (median 99.7 s). Its
  runs came late in the campaign, when per-run times rose from about 82 s to about 100 s
  under unchanged settings (machine load). It ranks below the winner anyway (3/7 targets).

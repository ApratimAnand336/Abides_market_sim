# News (information and hype)

Two kinds of news reach the agents, both through the NewsOracleAgent, which broadcasts a
`NewsSentimentMsg(symbol, sentiment, headline)` to every agent at its time.

| kind | where it comes from | changes the true value? | default |
|---|---|---|---|
| **information news** (spec v1.5 A3.4) | one headline AT each information jump of the "living_v1" value process (`auto_news=True`) | yes: the jump J is in the oracle path | from A9 (living_v1 default) |
| **hype / scripted news** (v1.0) | `build_config(news_events=[(offset, symbol, sentiment, headline)])`, dashboard news editor, lab S4 | no | none |

## Automatic information news (living_v1)

- **When:** at the grid time of each value jump (`oracle.day_info()["news"]`), so the
  headline and the value change are simultaneous. Count per day Poisson(2 / 3 / 4) by day type
  (calm / normal / volatile), times U(09:35, 15:55).
- **Which headline:** drawn uniformly (from the oracle's RandomState, after every path draw)
  within the bucket matching the jump: {positive, negative} x {small (|J| < 0.3% of price),
  medium (0.3–1%), large (> 1%)}.
- **Sentiment:** the template's STORED FinBERT score. Runs never call FinBERT.
- **What agents learn:** the headline's sentiment only.
  - Informed fundamentalists shift their belief by k_news × sentiment × a typical 30-minute move, as for hype news. They learn the jump's SIZE through research, every log-U[60, 300] s.
  - Momentum agents prime their velocity estimate; news is ignored during their warm-up.
  - From A4, the retail crowd's activity rises (Nn).

## Templates: `docs/engine/news_templates.json`

- 66 templates, 11 per bucket (balanced), ticker "ABM".
- Written once by `scripts/score_templates.py` with ProsusAI/finbert (sentiment = P(positive) − P(negative), 4 decimals).
- A template whose stored sentiment sign disagrees with its bucket is a build error: the script refuses to write, and T-O8 checks the committed file.
  - Three first-draft headlines failed that check and were reworded. For example, "ABM input costs rise modestly" scored +0.91.
- Small-news sentiments are weak by nature: positive_small min +0.026, negative_small max −0.008. Medium and large are mostly |s| > 0.6.
- Loaded by `abides_markets/configs/news_templates.py` (`load_news_templates`).

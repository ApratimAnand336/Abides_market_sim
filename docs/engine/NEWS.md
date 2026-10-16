# News (information and hype)

Status: skeleton (spec v1.5 A0). Filled in A3.

- Automatic information news (living_v1): one public headline at each value jump, from
  `docs/engine/news_templates.json` (>= 60 templates, {positive, negative} x {small, medium,
  large}, stored FinBERT sentiment; computed once by `scripts/score_templates.py`).
- Scripted news (hype, S4) stays available.

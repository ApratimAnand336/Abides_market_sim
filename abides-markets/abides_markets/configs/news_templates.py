"""Automatic-news headline templates (FinVerse spec v1.5 A3.4).

The templates and their stored FinBERT sentiments live in
docs/engine/news_templates.json (written once by scripts/score_templates.py); runs
never call FinBERT. Buckets: {positive, negative} x {small, medium, large}.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

TEMPLATES_PATH = Path(__file__).resolve().parents[3] / "docs" / "engine" / "news_templates.json"
BUCKETS = tuple(f"{s}_{z}" for s in ("positive", "negative") for z in ("small", "medium", "large"))


@lru_cache(maxsize=1)
def load_news_templates() -> Dict[str, Any]:
    """The template file as a dict ({"buckets": {bucket: [{"headline", "sentiment"}]}, ...})."""
    doc = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))
    missing = [b for b in BUCKETS if not doc.get("buckets", {}).get(b)]
    if missing:
        raise ValueError(f"{TEMPLATES_PATH}: empty or missing buckets {missing}")
    return doc

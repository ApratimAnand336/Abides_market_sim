"""FinBERT scoring for the dashboard (optional dependency).

transformers and torch are optional: when they are missing, available() is
False and the API answers 503 so the UI can degrade gracefully. The model is
loaded lazily on the first request and kept in memory.
"""

import importlib.util
import threading
from typing import Dict, Optional


class SentimentUnavailable(Exception):
    pass


_lock = threading.Lock()
_model = None
_load_error: Optional[str] = None


def available() -> bool:
    if _load_error is not None:
        return False
    return all(importlib.util.find_spec(m) is not None for m in ("transformers", "torch"))


def score(headline: str) -> Dict[str, float]:
    """{positive, negative, neutral, compound} with compound = positive - negative."""
    global _model, _load_error
    if not available():
        raise SentimentUnavailable(_load_error or "FinBERT not installed on the server")
    with _lock:
        if _model is None:
            try:
                from abides_markets.models.finbert_sentiment import FinBERTSentiment

                m = FinBERTSentiment()
                m.score("warm-up")  # forces the (possibly downloading) model load
                _model = m
            except Exception as e:  # missing weights, no network, ...
                _load_error = f"FinBERT failed to load: {e}"
                raise SentimentUnavailable(_load_error) from e
        out = _model.score(headline)
    pos, neg, neu = float(out["positive"]), float(out["negative"]), float(out["neutral"])
    return {"positive": pos, "negative": neg, "neutral": neu, "compound": round(pos - neg, 4)}

"""
FinBERT Sentiment Analyzer
──────────────────────────
Loads the pretrained FinBERT model (ProsusAI/finbert) for financial
sentiment analysis. Provides a simple interface to score news headlines
as positive, negative, or neutral.

Usage:
    from abides_markets.models.finbert_sentiment import FinBERTSentiment

    model = FinBERTSentiment()
    score = model.score("Company X beats Q3 earnings expectations")
    # score => {"positive": 0.92, "negative": 0.03, "neutral": 0.05, "sentiment": 0.89}
"""

import logging
from typing import Dict, List, Union

logger = logging.getLogger(__name__)


class FinBERTSentiment:
    """
    Wraps the ProsusAI/finbert model behind a clean API.

    The model is loaded lazily on first call to avoid blocking import time.
    """

    MODEL_NAME = "ProsusAI/finbert"

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._pipeline = None

    def _load(self) -> None:
        """Lazy-load the model and tokenizer on first use."""
        if self._pipeline is not None:
            return

        logger.info(f"Loading FinBERT model ({self.MODEL_NAME}) ...")
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

        tokenizer = AutoTokenizer.from_pretrained(self.MODEL_NAME)
        model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_NAME)
        model.to(self.device)

        self._pipeline = pipeline(
            "sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
            device=self.device,
            top_k=None,  # return all class scores
        )
        logger.info("FinBERT model loaded successfully.")

    def score(self, headline: str) -> Dict[str, float]:
        """
        Score a single headline.

        Returns:
            Dict with keys: "positive", "negative", "neutral", "sentiment".
            "sentiment" is a single float in [-1, 1]:
                +1 = maximally positive
                -1 = maximally negative
                 0 = perfectly neutral
        """
        self._load()
        results = self._pipeline(headline)[0]

        # results is a list of dicts like [{"label": "positive", "score": 0.92}, ...]
        scores = {r["label"]: r["score"] for r in results}

        # Compute a single directional sentiment value in [-1, 1]
        pos = scores.get("positive", 0.0)
        neg = scores.get("negative", 0.0)
        sentiment = pos - neg

        return {
            "positive": round(pos, 4),
            "negative": round(neg, 4),
            "neutral": round(scores.get("neutral", 0.0), 4),
            "sentiment": round(sentiment, 4),
        }

    def score_batch(self, headlines: List[str]) -> List[Dict[str, float]]:
        """Score multiple headlines at once (more efficient than looping)."""
        self._load()
        batch_results = self._pipeline(headlines)

        out = []
        for results in batch_results:
            scores = {r["label"]: r["score"] for r in results}
            pos = scores.get("positive", 0.0)
            neg = scores.get("negative", 0.0)
            out.append({
                "positive": round(pos, 4),
                "negative": round(neg, 4),
                "neutral": round(scores.get("neutral", 0.0), 4),
                "sentiment": round(pos - neg, 4),
            })
        return out


# ── Quick test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    analyzer = FinBERTSentiment()

    test_headlines = [
        "Company X beats Q3 earnings expectations by 15%",
        "Federal Reserve signals aggressive rate hikes amid inflation concerns",
        "Markets close flat as investors await jobs report",
    ]

    print("FinBERT Sentiment Analysis")
    print("=" * 60)
    for h in test_headlines:
        result = analyzer.score(h)
        print(f"\n  Headline: {h}")
        print(f"  Positive: {result['positive']:.4f}")
        print(f"  Negative: {result['negative']:.4f}")
        print(f"  Neutral:  {result['neutral']:.4f}")
        print(f"  Sentiment: {result['sentiment']:+.4f}")
    print("\n" + "=" * 60)

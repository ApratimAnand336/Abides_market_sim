"""Score the automatic-news headline templates with FinBERT once and store the scores
(FinVerse spec v1.5 A3.4).

    python scripts/score_templates.py            # writes docs/engine/news_templates.json

Runs never call FinBERT: the living_v1 oracle draws a template from the bucket matching a
value jump's sign and size and publishes its STORED sentiment. Buckets:
{positive, negative} x {small (|J| < 0.3% of price), medium (0.3-1%), large (> 1%)}.
sentiment = P(positive) - P(negative) from ProsusAI/finbert (as api/sentiment.py), rounded
to 4 decimals. A template whose stored sentiment sign disagrees with its bucket is a build
error: the script stops without writing (rewrite the headline), and
tests/test_living_oracle.py (T-O8) checks the committed file.
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "engine" / "news_templates.json"
SIZE_EDGES_PCT = (0.3, 1.0)  # small < 0.3% <= medium <= 1% < large

TEMPLATES = {
    "positive_small": [
        "ABM wins a small supply contract with a regional distributor",
        "Analyst raises ABM price target slightly on solid demand",
        "ABM reports slightly better than expected monthly sales",
        "ABM announces modest expansion of its share buyback program",
        "ABM receives regulatory approval for a new product line",
        "ABM customer satisfaction scores improve modestly in survey",
        "ABM opens a new regional office to support growth",
        "ABM signs a small partnership agreement with a technology firm",
        "ABM web traffic data points to steady demand growth",
        "ABM director buys a small block of shares",
        "ABM reports a small rise in weekly bookings",
    ],
    "positive_medium": [
        "ABM quarterly earnings beat consensus estimates",
        "ABM raises full-year revenue guidance",
        "ABM secures a multi-year contract with a major retailer",
        "Major broker upgrades ABM to buy",
        "ABM margins improve as cost cuts take hold",
        "ABM raises its dividend by more than expected",
        "ABM wins approval for its flagship product in a key market",
        "ABM reports strong growth in new customer orders",
        "ABM unveils new product with strong early demand",
        "ABM settles legal dispute on favourable terms",
        "ABM credit rating upgraded by a major agency",
    ],
    "positive_large": [
        "ABM profit surges far above expectations, guidance raised sharply",
        "ABM agrees to be acquired at a substantial premium",
        "ABM announces breakthrough product, analysts see major revenue boost",
        "ABM wins landmark government contract worth billions",
        "ABM record quarterly revenue smashes all estimates",
        "ABM receives full regulatory approval for blockbuster drug",
        "ABM doubles its earnings forecast for the year",
        "ABM announces massive share buyback after record profits",
        "ABM strikes transformational partnership with industry leader",
        "ABM sales soar as new product becomes a market hit",
        "ABM swings to a large profit, beating every analyst estimate",
    ],
    "negative_small": [
        "ABM misses monthly sales estimate by a small margin",
        "Analyst trims ABM price target slightly",
        "ABM reports a minor delay in a product shipment",
        "ABM faces a small product recall in one region",
        "ABM profit squeezed slightly by higher input costs",
        "ABM loses a small contract to a competitor",
        "ABM director sells a small block of shares",
        "ABM web traffic data points to softer demand",
        "ABM warns of slightly higher operating expenses",
        "ABM customer complaints tick up in latest survey",
        "ABM reports a small drop in weekly bookings",
    ],
    "negative_medium": [
        "ABM quarterly earnings miss consensus estimates",
        "ABM cuts full-year revenue guidance",
        "Major broker downgrades ABM to sell",
        "ABM loses a key contract with a major retailer",
        "ABM margins shrink as costs rise",
        "ABM faces regulatory investigation into sales practices",
        "ABM product launch delayed by several months",
        "ABM reports weak growth in new orders",
        "ABM credit rating downgraded by a major agency",
        "ABM cuts its dividend",
        "ABM hit by lawsuit over product defects",
    ],
    "negative_large": [
        "ABM profit collapses, guidance slashed",
        "ABM chief executive resigns amid accounting probe",
        "ABM loses patent case, key product faces ban",
        "Regulator rejects ABM flagship product",
        "ABM issues profit warning, sees steep revenue decline",
        "ABM swings to a large loss, missing every estimate",
        "ABM major customer cancels multi-year contract",
        "ABM faces fraud allegations in short seller report",
        "ABM suspends dividend after sharp fall in earnings",
        "ABM recalls flagship product nationwide over safety concerns",
        "ABM plant shutdown halts most production",
    ],
}


def bucket_sign(bucket: str) -> int:
    return 1 if bucket.startswith("positive") else -1


def main() -> int:
    from abides_markets.models.finbert_sentiment import FinBERTSentiment

    model = FinBERTSentiment()
    buckets, bad = {}, []
    for name, heads in TEMPLATES.items():
        scored = model.score_batch(heads)
        buckets[name] = []
        for h, sc in zip(heads, scored):
            s = round(float(sc["sentiment"]), 4)
            buckets[name].append({"headline": h, "sentiment": s})
            if s == 0 or (s > 0) != (bucket_sign(name) > 0):
                bad.append((name, h, s))
    for name, items in buckets.items():
        ss = [x["sentiment"] for x in items]
        print(f"{name:16s} n={len(ss):2d}  sentiment min {min(ss):+.3f} median {sorted(ss)[len(ss) // 2]:+.3f} max {max(ss):+.3f}")
    if bad:
        print("BUILD ERROR: stored sentiment sign disagrees with the bucket:")
        for b in bad:
            print("  ", b)
        return 1
    doc = {
        "spec": "v1.5 A3.4",
        "model": FinBERTSentiment.MODEL_NAME,
        "score": "P(positive) - P(negative), rounded to 4 decimals",
        "computed": date.today().isoformat(),
        "size_edges_pct": list(SIZE_EDGES_PCT),
        "buckets": buckets,
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({sum(len(v) for v in buckets.values())} templates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

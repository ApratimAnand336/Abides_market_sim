"""Measurement additions of FinVerse spec v1.5 A2 (synthetic data, answers known by
construction).

T-R4-1  regime spread RS = p90/p10 of daily realised vols, on synthetic days whose
        realised vols are known exactly.
T-R4-2  information-news response (f_10, volume uplift) on a hand-built series.
Also: day_rv_pct, class volumes and volume shares (both sides counted), market-maker
inventory statistics.
"""

import math

import numpy as np
import pytest

from api import realism as R


def _day_with_rv(sigma_pct: float, n: int = 389, seed: int = 0) -> np.ndarray:
    """1-min returns of equal size and random sign: sum r^2 = (sigma/100)^2 exactly."""
    signs = np.where(np.random.RandomState(seed).rand(n) < 0.5, -1.0, 1.0)
    return signs * (sigma_pct / 100.0) / math.sqrt(n)


def test_day_rv_pct_known():
    for s in (0.5, 1.0, 2.37):
        assert R.day_rv_pct(_day_with_rv(s)) == pytest.approx(s, rel=1e-12)
    assert R.day_rv_pct(np.array([])) is None


def test_r4_1_regime_spread_known_daily_vols():
    sigmas = [0.5 + 0.1 * i for i in range(20)]  # 0.5 ... 2.4 % a day
    rvs = [R.day_rv_pct(_day_with_rv(s, seed=i)) for i, s in enumerate(reversed(sigmas))]
    # numpy linear percentiles of 0.5 + 0.1 i: p10 at index 1.9 -> 0.69, p90 at 17.1 -> 2.21
    assert R.regime_spread(rvs) == pytest.approx(2.21 / 0.69, rel=1e-12)
    assert R.regime_spread([1.0, 1.0, 1.0]) == pytest.approx(1.0)
    assert R.regime_spread([1.0]) is None
    assert R.regime_spread([None, 1.0, float("nan")]) is None
    assert R.regime_spread([0.0, 0.0, 2.0]) is None  # p10 = 0


def test_r4_2_info_news_response_hand_built():
    dur = 3600
    mid = np.full(dur + 1, 1000.0)
    t0 = 1000
    mid[t0:t0 + 301] = np.linspace(1000.0, 1010.0, 301)  # moves $10 in 5 min, then stays
    mid[t0 + 301:] = 1010.0
    # volume: 10 x 100 shares in (t0 - 600, t0], 25 x 100 in (t0, t0 + 600]
    et = np.concatenate([np.linspace(t0 - 590, t0, 10), np.linspace(t0 + 1, t0 + 600, 25)])
    eq = np.full(len(et), 100.0)
    events = [(float(t0), 20.0),        # J = +$20: f_10 = 10 / 20 = 0.5, uplift 2.5
              (3300.0, 5.0),            # no full 10-min window after: skipped
              (2000.0, 0.0)]            # J = 0: skipped
    out = R.info_news_response(mid, et, eq, events)
    assert out["n"] == 1 and out["n_events"] == 3
    assert out["f10_median"] == pytest.approx(0.5, abs=1e-12)
    assert out["uplift_median"] == pytest.approx(2.5, abs=1e-12)
    # a negative jump priced in fully: f_10 = 1
    mid2 = np.full(dur + 1, 1000.0)
    mid2[t0 + 1:] = 990.0
    out2 = R.info_news_response(mid2, et, eq, [(float(t0), -10.0)])
    assert out2["f10_median"] == pytest.approx(1.0, abs=1e-12)
    # no volume before: uplift undefined
    out3 = R.info_news_response(mid, et[10:], eq[10:], [(float(t0), 20.0)])
    assert out3["uplift_median"] is None and out3["f10_median"] == pytest.approx(0.5)


def test_class_volumes_and_shares():
    cls_of = {1: "RetailTraderAgent", 2: "LiquidityProviderAgent", 3: "FundamentalistAgent"}
    buyer = np.array([1, 2, 3, 1])
    seller = np.array([2, 3, 1, 1])
    q = np.array([10.0, 20.0, 30.0, 40.0])  # 100 shares executed
    cv = R.class_volumes(buyer, seller, q, cls_of)
    assert cv == {"RetailTraderAgent": 10 + 30 + 80, "LiquidityProviderAgent": 30, "FundamentalistAgent": 50}
    assert sum(cv.values()) == 2 * q.sum()
    assert R.volume_share(cv, R.RETAIL_CLASSES, 100) == pytest.approx(60.0)
    assert R.volume_share(cv, R.MM_CLASSES, 100) == pytest.approx(15.0)
    assert R.volume_share(cv, R.MM_CLASSES, 0) is None


def test_inventory_stats():
    buyer = np.array([5, 1, 5, 2, 1])
    seller = np.array([1, 5, 2, 5, 5])
    q = np.array([10.0, 4.0, 7.0, 30.0, 1.0])
    # agent 5: +10, -4, +7, -30, -1 -> path 10, 6, 13, -17, -18
    assert R.inventory_stats(buyer, seller, q, 5) == {"max_abs": 18, "end": -18}
    assert R.inventory_stats(buyer, seller, q, 9) == {"max_abs": 0, "end": 0}
    assert R.inventory_stats(np.array([]), np.array([]), np.array([]), 5) == {"max_abs": 0, "end": 0}


def test_run_metrics_v15_keys_are_payload_scalars():
    """The payload schema accepts scalar (or list-of-number) metrics only: the A2 keys
    are scalars; the per-agent / per-event detail goes to run_diagnostics."""
    rs = np.random.RandomState(1)
    dur = 23400
    mid = 1000.0 * np.exp(np.cumsum(rs.normal(0, 2e-5, dur + 1)))
    val = mid + rs.normal(0, 0.05, dur + 1)
    s = {
        "duration": dur, "mid_1s": mid, "val_1s": val,
        "close_1m": R.bar_closes(mid, dur), "vol_1m": rs.randint(100, 1000, 390).astype(float),
        "spr_1s": np.full(dur + 1, 0.02), "shares_executed": 200_000,
        "exec_t": np.sort(rs.uniform(0, dur, 5000)), "exec_q": np.full(5000, 40.0),
        "class_volume": {"RetailTraderAgent": 80_000.0, "LiquidityProviderAgent": 120_000.0},
        "mm_inventory": [{"id": 3, "cls": "LiquidityProviderAgent", "max_abs": 900, "end": -40},
                         {"id": 4, "cls": "LiquidityProviderAgent", "max_abs": 1200, "end": 15}],
        "info_news": [(3600.0, 2.0), (12000.0, -1.5)],
        "day_info": {"day_type": "normal", "stress_episodes": [], "news": []},
    }
    m = R.run_metrics(s)
    assert m["retail_share"] == pytest.approx(20.0) and m["mm_share"] == pytest.approx(30.0)
    assert m["mm_inv_max_abs"] == 1200 and m["mm_inv_end_max_abs"] == 40
    assert m["info_news_n"] == 2 and m["day_rv_pct"] > 0
    for k, v in m.items():
        ok = v is None or isinstance(v, (int, float, bool)) or (
            isinstance(v, list) and all(isinstance(x, (int, float)) for x in v))
        assert ok, k
    d = R.run_diagnostics(s)
    assert len(d["mm_inventory"]) == 2 and d["info_news"]["n"] == 2 and d["day_info"]["day_type"] == "normal"

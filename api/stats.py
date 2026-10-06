"""Market statistics for the dashboard (spec Section 4, items 3-5).

All statistics are computed here, once, from full-resolution series. Inputs are
plain numpy arrays; prices in dollars, times in seconds since market open.
"""

from typing import Dict, Optional, Sequence

import numpy as np
from scipy import stats as sps

N_ACF_LAGS = 20
N_HIST_BINS = 41
N_NORMAL_POINTS = 200
MAX_TICK_BUCKET = 11  # spread buckets 1..10 cents, 11 = ">= 11"


def spread_stats(spread_dollars: np.ndarray) -> Dict:
    if len(spread_dollars) == 0:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "mean": float(np.mean(spread_dollars)),
        "median": float(np.median(spread_dollars)),
        "p95": float(np.percentile(spread_dollars, 95)),
        "max": float(np.max(spread_dollars)),
    }


def spread_ticks(spread_cents: np.ndarray) -> Dict:
    """Histogram of round(spread in cents). Buckets 1..10 and a final '>= 11'
    bucket. A locked book (0 cents, which should not occur) counts as 1."""
    ticks = list(range(1, MAX_TICK_BUCKET + 1))
    if len(spread_cents) == 0:
        return {"ticks": ticks, "share": [0.0] * len(ticks)}
    r = np.clip(np.round(spread_cents).astype(int), 1, MAX_TICK_BUCKET)
    counts = np.bincount(r, minlength=MAX_TICK_BUCKET + 1)[1:]
    return {"ticks": ticks, "share": (counts / counts.sum()).tolist()}


def acf(x: np.ndarray, n_lags: int = N_ACF_LAGS) -> list:
    """Sample autocorrelation for lags 1..n_lags (biased estimator, as in
    standard ACF plots). Lags beyond the sample length are 0."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    out = []
    if n < 2:
        return [0.0] * n_lags
    d = x - x.mean()
    denom = float(d @ d)
    for lag in range(1, n_lags + 1):
        if lag >= n or denom == 0:
            out.append(0.0)
        else:
            out.append(float(d[:-lag] @ d[lag:]) / denom)
    return out


def returns_1m(close: np.ndarray) -> Dict:
    """Statistics of 1-minute log returns from candle closes."""
    r = np.diff(np.log(np.asarray(close, dtype=float)))
    n = len(r)
    if n < 3:
        empty_hist = {"edges": [], "counts": []}
        return {
            "n": n, "mean": 0.0, "std": 0.0, "skew": 0.0, "excess_kurtosis": 0.0,
            "hist": empty_hist, "normal": {"x": [], "y": []},
            "acf": [0.0] * N_ACF_LAGS, "acf_abs": [0.0] * N_ACF_LAGS,
            "acf_band": 0.0,
        }
    mean, std = float(np.mean(r)), float(np.std(r, ddof=1))
    if std > 0:
        skew = float(sps.skew(r))
        kurt = float(sps.kurtosis(r, fisher=True))
        lo, hi = mean - 4 * std, mean + 4 * std
    else:  # a perfectly flat market
        skew, kurt = 0.0, 0.0
        lo, hi = mean - 1e-6, mean + 1e-6
    edges = np.linspace(lo, hi, N_HIST_BINS + 1)
    # values outside +-4 std go into the edge bins
    counts, _ = np.histogram(np.clip(r, lo, hi), bins=edges)
    width = edges[1] - edges[0]
    xs = np.linspace(lo, hi, N_NORMAL_POINTS)
    ys = (
        sps.norm.pdf(xs, mean, std) * n * width
        if std > 0
        else np.zeros_like(xs)
    )
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "skew": skew,
        "excess_kurtosis": kurt,
        "hist": {"edges": edges.tolist(), "counts": counts.astype(int).tolist()},
        "normal": {"x": xs.tolist(), "y": ys.tolist()},
        "acf": acf(r),
        "acf_abs": acf(np.abs(r)),
        "acf_band": 1.96 / np.sqrt(n),
    }


def returns_tick(mid: np.ndarray) -> Dict:
    """Tick-to-tick log-return std and excess kurtosis (reference only: these
    are dominated by zero changes and microstructure noise)."""
    r = np.diff(np.log(np.asarray(mid, dtype=float)))
    if len(r) < 4 or np.std(r) == 0:
        return {"std": 0.0, "excess_kurtosis": 0.0}
    return {"std": float(np.std(r, ddof=1)), "excess_kurtosis": float(sps.kurtosis(r, fisher=True))}


def tracking(t: np.ndarray, mid: np.ndarray, oracle_t: np.ndarray, oracle_v: np.ndarray) -> Dict:
    """Mid vs oracle fundamental, with the oracle interpolated onto quote times."""
    if len(t) < 2 or len(oracle_t) < 2:
        return {"rms": 0.0, "mean_abs": 0.0, "corr": 0.0}
    o = np.interp(t, oracle_t, oracle_v)
    err = mid - o
    corr = float(np.corrcoef(mid, o)[0, 1]) if np.std(mid) > 0 and np.std(o) > 0 else 0.0
    return {
        "rms": float(np.sqrt(np.mean(err ** 2))),
        "mean_abs": float(np.mean(np.abs(err))),
        "corr": corr,
    }


def market_stats(
    t: np.ndarray,
    bid: np.ndarray,
    ask: np.ndarray,
    mid: np.ndarray,
    candle_close: np.ndarray,
    oracle_t: np.ndarray,
    oracle_v: np.ndarray,
    trades: int,
    volume_shares: int,
) -> Dict:
    """Everything in MarketStats. Prices in dollars."""
    spread = ask - bid
    open_, close = (float(mid[0]), float(mid[-1])) if len(mid) else (0.0, 0.0)
    change = close - open_
    return {
        "open": open_,
        "close": close,
        "change": change,
        "change_pct": 100.0 * change / open_ if open_ else 0.0,
        "low": float(np.min(mid)) if len(mid) else 0.0,
        "high": float(np.max(mid)) if len(mid) else 0.0,
        "spread": spread_stats(spread),
        "spread_ticks": spread_ticks(spread * 100.0),
        "returns_1m": returns_1m(candle_close),
        "returns_tick": returns_tick(mid),
        "tracking": tracking(t, mid, oracle_t, oracle_v),
        "trades": int(trades),
        "volume_shares": int(volume_shares),
    }


def value_at(t_query: float, t: np.ndarray, v: np.ndarray) -> Optional[float]:
    """Last value at or before t_query (None if t_query precedes the series)."""
    i = int(np.searchsorted(t, t_query, side="right")) - 1
    return float(v[i]) if i >= 0 else None

"""Realism metrics, bands and scenario analysis (FinVerse spec v1.3, Parts 3, 4, 7.3).

The single source of every realism number: the lab (scripts/realism_lab.py) and
the dashboard payload (api/export.py) both call this module. Metrics are pure
functions of numpy arrays; only the series builder (series_from_end_state)
reads a simulation's end state.

Conventions: prices in dollars, spreads in cents (1 tick = 1 cent), times in
seconds since the 09:30 open on a 1 s grid, returns as log returns. Reuses
api.stats.acf and api.stats.gap_half_life without changing them.
"""

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sps

from .stats import GAP_LAGS_S, GAP_RHO_RANGE, acf, gap_half_life

# ── constants ─────────────────────────────────────────────────────────────

LAB_GAP_LAGS = (60, 120, 300, 600, 1200, 1800, 3600)  # spec v1.3 §3.7
N_DAY_RETURNS = 389  # 1-min returns in a full 09:30-16:00 day (390 bars)
FULL_DAY_S = 23400
MIN_VALID_SEEDS = 15  # spec v1.3 §4.3: fewer valid seeds -> INCOMPLETE
SMOOTH_S = 30  # centred rolling mean used by the scenario analysis
GRID_10S = 10  # agent series are stored on a 10 s grid
SOURCE = "owner D-R2-1, 2026-10-11, large-cap reference"

# agent classes, in table order; the probe is listed separately
CLASSES = [
    "NoiseAgent", "ValueAgent", "AdaptiveMarketMakerAgent", "MomentumAgent",
    "FundamentalistAgent", "MomentumEKFAgent",
]
PROBE_CLASS = "ImpactProbeAgent"
FLOW_CLASSES = CLASSES + [PROBE_CLASS]
EXCLUDED_CLASSES = {"ExchangeAgent", "NewsOracleAgent"}
MOM_STATES = ["NEUTRAL", "BULL", "BEAR", "WATCH"]
MOM_REASONS = ["BREAKOUT", "REENTRY", "STOP", "FADE", "TIMEOUT", "OTHER"]


# ── bands (spec v1.3 Part 4; one table, one place) ───────────────────────
#
# pass / warn: lists of closed intervals [lo, hi] (None = open end). A value
# exactly on a boundary takes the better grade, so PASS is tested first and
# every interval is closed. G5 and G8 combine two metrics ("rule").

BANDS: List[Dict[str, Any]] = [
    {
        "id": "G1", "key": "sigma_1m_bps", "label": "1-min volatility", "unit": "bps",
        "pass": [[5.0, 10.0]], "warn": [[2.5, 5.0], [10.0, 20.0]],
        "text": "PASS 5–10 · WARN 2.5–5 or 10–20",
        "note": "Std of 1-minute log returns. 1–2% a day over 389 minutes is 5.1–10.1 bps per minute.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G2", "key": "sigma_day_xseed", "label": "Daily volatility (across seeds)", "unit": "%",
        "pass": [[1.0, 2.0]], "warn": [[0.5, 1.0], [2.0, 4.0]],
        "text": "PASS 1–2% · WARN 0.5–1% or 2–4%",
        "note": "Std over seeds of the 09:30→16:00 log return. A large-cap moves about 1–2% a day.",
        "scope": "lab", "source": SOURCE,
    },
    {
        "id": "G3", "key": "ac1", "transform": "abs", "label": "Return predictability |ac1|", "unit": "",
        "pass": [[None, 0.10]], "warn": [[0.10, 0.20]],
        "text": "PASS |ac1| ≤ 0.10 · WARN 0.10–0.20",
        "note": "Lag-1 autocorrelation of 1-minute returns. Real prices are close to unpredictable (≈0).",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G4", "key": "vr5", "label": "Variance ratio VR(5)", "unit": "",
        "pass": [[0.80, 1.25]], "warn": [[0.60, 0.80], [1.25, 1.60]],
        "text": "PASS 0.80–1.25 · WARN 0.60–0.80 or 1.25–1.60",
        "note": "Var of 5-min returns / (5 × var of 1-min returns). 1 = random walk; > 1 = the price trails a target.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G5", "key": "clustering", "rule": "clustering", "metrics": ["cs", "ps"],
        "label": "Volatility clustering (CS, PS)", "unit": "",
        "pass": [[0.10, None]], "warn": [[0.05, 0.10]],
        "text": "PASS CS ≥ 0.10 and PS > 0.03 · WARN CS 0.05–0.10, or CS ≥ 0.10 with PS ≤ 0.03",
        "note": "CS = mean autocorrelation of |r| at lags 1–5, PS = at lags 10–30. Real markets: calm and wild periods cluster.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G6", "key": "kurt", "label": "Fat tails (excess kurtosis)", "unit": "",
        "pass": [[3.0, None]], "warn": [[1.0, 3.0]],
        "text": "PASS ≥ 3 · WARN 1–3",
        "note": "Excess kurtosis of 1-minute returns. 0 for a normal distribution; real returns have fat tails.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G7", "key": "vv_corr", "label": "Volume–volatility correlation", "unit": "",
        "pass": [[0.30, None]], "warn": [[0.10, 0.30]],
        "text": "PASS ≥ 0.30 · WARN 0.10–0.30",
        "note": "Spearman correlation of 5-minute realised volatility and volume. Real markets trade more when prices move.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G8", "key": "spread", "rule": "spread", "metrics": ["spread_med_ticks", "spread_p95_ticks"],
        "label": "Spread (median, p95)", "unit": "ticks",
        "pass": [[None, 5.0]], "warn": [[None, 10.0]],
        "text": "PASS median ≤ 1 and p95 ≤ 5 ticks · WARN p95 ≤ 10 ticks",
        "note": "Bid-ask spread in cents, two-sided seconds only. A liquid large-cap trades at a one-tick spread.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G9", "key": "gap_std", "label": "Mispricing size (gap std)", "unit": "$",
        "pass": [[1.0, 3.0]], "warn": [[0.5, 1.0], [3.0, 5.0]],
        "text": "PASS $1–3 · WARN $0.50–1 or $3–5",
        "note": "Std of price − true value. Real prices wander around value by dollars, not cents.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G10", "key": "gap_half_life_corr_min", "label": "Mispricing half-life", "unit": "min",
        "pass": [[30.0, 90.0]], "warn": [[10.0, 30.0], [90.0, 180.0]],
        "text": "PASS 30–90 min · WARN 10–30 or 90–180 min · FAIL otherwise or none",
        "note": "How long a mispricing takes to halve (spring model, lags 1–60 min, corrected reading, spec v1.4 §3.1). Real mispricings last much longer than minutes.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G11", "key": "regime_contrast", "label": "Regime contrast", "unit": "×",
        "pass": [[5.0, None]], "warn": [[3.0, 5.0]],
        "text": "PASS ≥ 5 · WARN 3–5",
        "note": "Wildest / calmest 30-min volatility. Sampling noise alone gives about 1.55; real days have calm and stressed hours.",
        "scope": "run", "source": SOURCE,
    },
    {
        "id": "G12", "key": "impact_beta", "label": "Impact exponent β", "unit": "",
        "pass": [[0.40, 0.70]], "warn": [[0.25, 0.40], [0.70, 0.90]],
        "text": "PASS 0.40–0.70 · WARN 0.25–0.40 or 0.70–0.90",
        "note": "Slope of log impact on log order size (share of daily volume). The square-root law gives 0.5.",
        "scope": "lab", "source": SOURCE,
    },
    {
        "id": "G13", "key": "impact_recovery", "label": "Impact recovery I_perm / I_peak", "unit": "",
        "pass": [[0.10, 0.80]], "warn": [[0.0, 0.10], [0.80, 1.0]],
        "text": "PASS 0.1–0.8 · WARN 0–0.1 or 0.8–1",
        "note": "Share of the peak impact still present 25–35 min after the order ends. Real impact partly decays.",
        "scope": "lab", "source": SOURCE,
    },
]
BANDS_BY_ID = {b["id"]: b for b in BANDS}
RUN_GRADES = [b["id"] for b in BANDS if b["scope"] == "run"]  # G1, G3-G11


# ── small helpers ─────────────────────────────────────────────────────────


def _f(x) -> Optional[float]:
    """float, or None for None/NaN/inf."""
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _std(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.std(x, ddof=1)) if len(x) >= 2 else None


def _ratio(a, b) -> Optional[float]:
    a, b = _f(a), _f(b)
    if a is None or b is None or b == 0:
        return None
    return a / b


def smooth(x: np.ndarray, window: int = SMOOTH_S) -> np.ndarray:
    """Centred rolling mean over `window` samples (1 s grid: seconds)."""
    return pd.Series(np.asarray(x, dtype=float)).rolling(window, center=True, min_periods=1).mean().to_numpy()


def _ffill_sample(ts: np.ndarray, vals: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Last value at or before each grid time (NaN before the first)."""
    out = np.full(len(grid), np.nan)
    if len(ts) == 0:
        return out
    idx = np.searchsorted(ts, grid, side="right") - 1
    ok = idx >= 0
    out[ok] = vals[idx[ok]]
    return out


# ── series (spec v1.3 Part 3, common inputs) ─────────────────────────────


def bar_closes(mid_1s: np.ndarray, duration: int) -> np.ndarray:
    """close_1m: the mid at the end of each 1-minute bar (t = 60, 120, ...)."""
    ends = np.arange(60, int(duration) + 1, 60)
    return np.asarray(mid_1s, dtype=float)[ends]


def returns_from_closes(close_1m: np.ndarray) -> np.ndarray:
    """r1: 1-minute log returns of close_1m (389 for a full day)."""
    c = np.asarray(close_1m, dtype=float)
    return np.diff(np.log(c)) if len(c) >= 2 else np.array([])


def class_of(agent) -> str:
    return type(agent).__name__


def start_position(agent, ticker: str = "ABM") -> Tuple[int, int]:
    """(cash, shares) at the start, in cents. Our agents hold an endowment of
    floor(e0 * W0 / p_ref) shares; the probe may start with shares; ABIDES
    agents start with cash only."""
    w0 = int(agent.starting_cash)
    if hasattr(agent, "initial_exposure") and hasattr(agent, "reference_price"):
        n0 = int(math.floor(agent.initial_exposure * w0 / agent.reference_price))
        return w0 - n0 * int(agent.reference_price), n0
    if hasattr(agent, "starting_shares"):
        return w0, int(agent.starting_shares)
    return w0, 0


def series_from_end_state(
    end_state: Dict[str, Any],
    config: Dict[str, Any],
    ticker: str = "ABM",
    start_holdings: Optional[Dict[int, Tuple[int, int]]] = None,
) -> Dict[str, Any]:
    """Build every per-run input of Part 3 from a finished simulation.

    start_holdings: {agent_id: (cash, shares)} snapshot taken before
    abides.run (the lab passes it); otherwise reconstructed by start_position.

    Returns a dict of numpy arrays (the series) plus "agents" (per-agent
    records for the sanity tables) and "events" (news and probe logs)."""
    agents = end_state["agents"]
    exchange = agents[0]
    ob = exchange.order_books[ticker]
    open_ns, close_ns = int(config["_mkt_open_ns"]), int(config["_mkt_close_ns"])
    duration = int(round((close_ns - open_ns) / 1e9))
    grid = np.arange(0, duration + 1, dtype=float)

    # ── L1 book on the grid ──
    snap_t, snap_bid, snap_ask = [], [], []
    for row in ob.book_log2:
        b, a = row["bids"], row["asks"]
        snap_t.append((int(row["QuoteTime"]) - open_ns) / 1e9)
        snap_bid.append(float(b[0][0]) if len(b) and float(b[0][0]) > 0 else np.nan)
        snap_ask.append(float(a[0][0]) if len(a) and float(a[0][0]) > 0 else np.nan)
    snap_t = np.array(snap_t)
    snap_bid = np.array(snap_bid)
    snap_ask = np.array(snap_ask)
    two = np.isfinite(snap_bid) & np.isfinite(snap_ask)
    mid_c = (snap_bid + snap_ask) / 2.0
    # mid: last TWO-SIDED mid at or before t (forward-filled through one-sided books)
    mid_1s = _ffill_sample(snap_t[two], mid_c[two], grid) / 100.0
    first = np.flatnonzero(np.isfinite(mid_1s))
    if len(first) == 0:
        raise RuntimeError("no two-sided book in the session")
    mid_1s[: first[0]] = mid_1s[first[0]]  # mid at 09:30 = first two-sided mid
    # spread: state of the LAST snapshot; one-sided (or no book yet) -> NaN
    spr_1s = _ffill_sample(snap_t, snap_ask - snap_bid, grid)

    # ── true value on the grid (oracle.value_at: last grid point <= t) ──
    oracle = config["custom_properties"]["oracle"]
    o_t, o_v = oracle.path(ticker)
    idx = np.clip(np.searchsorted(o_t, open_ns + (grid * 1e9).astype(np.int64), side="right") - 1, 0, len(o_t) - 1)
    val_1s = o_v[idx] / 100.0

    # ── executions ──
    cls_of = {a.id: class_of(a) for a in agents}
    execs = [h for h in ob.history if h.get("type") == "EXEC"]
    ex_t = np.array([(int(h["time"]) - open_ns) / 1e9 for h in execs], dtype=float)
    ex_p = np.array([h["price"] for h in execs], dtype=float)
    ex_q = np.array([h["quantity"] for h in execs], dtype=float)
    ex_a = np.array([h["agent_id"] for h in execs], dtype=np.int64)
    ex_o = np.array([h["oppos_agent_id"] for h in execs], dtype=np.int64)
    # side is the PASSIVE order's side (order_book.py); buyer gets +q
    ex_buyer = np.array([h["agent_id"] if h["side"] == "BUY" else h["oppos_agent_id"] for h in execs], dtype=np.int64)
    ex_seller = np.where(ex_buyer == ex_a, ex_o, ex_a)

    n_min = max(1, int(math.ceil(duration / 60.0)))
    in_sess = (ex_t >= 0) & (ex_t <= duration)
    bucket = np.clip((ex_t // 60).astype(int), 0, n_min - 1) if len(ex_t) else np.array([], int)
    vol_1m = np.bincount(bucket[in_sess], weights=ex_q[in_sess], minlength=n_min) if len(ex_t) else np.zeros(n_min)

    # per-class signed net shares bought per 1-min bar
    net = np.zeros((len(FLOW_CLASSES), n_min))
    ci = {c: i for i, c in enumerate(FLOW_CLASSES)}
    for k in np.flatnonzero(in_sess):
        b, s = cls_of.get(int(ex_buyer[k])), cls_of.get(int(ex_seller[k]))
        if b in ci:
            net[ci[b], bucket[k]] += ex_q[k]
        if s in ci:
            net[ci[s], bucket[k]] -= ex_q[k]

    # ── our agents' beliefs and states ──
    g10 = np.arange(0, duration + 1, GRID_10S, dtype=float)
    fund_ids = list(config.get("_ekf_agent_ids", []))
    mom_ids = list(config.get("_mom_ekf_agent_ids", []))
    fund_xhat = np.zeros((len(fund_ids), len(g10)))
    for r, i in enumerate(fund_ids):
        tt, xx = [], []
        for t_ns, typ, ev in agents[i].log:
            if typ == "EKF_UPDATE":
                tt.append((int(t_ns) - open_ns) / 1e9)
                xx.append(ev["x_hat"] / 100.0)
        fund_xhat[r] = _ffill_sample(np.array(tt), np.array(xx), g10)
    mom_states = []  # rows: agent index, t, to code, reason code
    for r, i in enumerate(mom_ids):
        for t_ns, typ, ev in agents[i].log:
            if typ == "MOM_STATE":
                reason = ev.get("reason")
                mom_states.append((
                    r, (int(t_ns) - open_ns) / 1e9, MOM_STATES.index(ev["to"]),
                    MOM_REASONS.index(reason) if reason in MOM_REASONS else MOM_REASONS.index("OTHER"),
                ))
    mom_states = np.array(mom_states, dtype=float).reshape(-1, 4)

    # ── news reactions and probe log ──
    news = {"fund_shift": [], "mom_dv": []}
    for i in fund_ids:
        for _, typ, ev in agents[i].log:
            if typ == "NEWS_RECEIVED":
                news["fund_shift"].append(ev["shift"] / 100.0)
    for i in mom_ids:
        last_v = None
        for _, typ, ev in agents[i].log:
            if typ == "MOM_KF_UPDATE":
                last_v = ev["v_hat"]
            elif typ == "NEWS_RECEIVED" and last_v is not None:
                news["mom_dv"].append(ev["v_hat_new"] - last_v)
    probe = None
    for a in agents:
        if class_of(a) == PROBE_CLASS:
            summ = [ev for _, typ, ev in a.log if typ == "PROBE_SUMMARY"]
            children = [ev for _, typ, ev in a.log if typ == "PROBE_CHILD"]
            absorbed = defaultdict(int)
            for k in range(len(execs)):
                if ex_a[k] == a.id or ex_o[k] == a.id:
                    other = int(ex_o[k] if ex_a[k] == a.id else ex_a[k])
                    absorbed[cls_of.get(other, "?")] += int(ex_q[k])
            probe = {
                "id": int(a.id), "side": a.side, "quantity": int(a.quantity),
                "summary": summ[-1] if summ else None, "n_children": len(children),
                "absorbed": dict(absorbed),
            }

    # ── agent records (sanity tables, zero_sum) ──
    close_c = float(mid_1s[-1]) * 100.0
    traded = defaultdict(int)
    for k in range(len(execs)):
        traded[int(ex_a[k])] += int(ex_q[k])
        traded[int(ex_o[k])] += int(ex_q[k])
    order_ids = defaultdict(set)
    for h in ob.history:
        if h.get("type") == "LIMIT":
            order_ids[h["agent_id"]].add(h["order_id"])
        elif h.get("type") == "EXEC":
            order_ids[h["oppos_agent_id"]].add(h["oppos_order_id"])
    records = []
    for a in agents:
        if class_of(a) in EXCLUDED_CLASSES or not hasattr(a, "holdings"):
            continue
        c0, n0 = (start_holdings or {}).get(a.id, start_position(a, ticker))
        rec = {
            "id": int(a.id), "cls": class_of(a),
            "cash0": int(c0), "sh0": int(n0),
            "cash1": int(a.holdings.get("CASH", 0)), "sh1": int(a.holdings.get(ticker, 0)),
            "traded": int(traded.get(a.id, 0)), "orders": len(order_ids.get(a.id, ())),
        }
        if rec["cls"] in ("FundamentalistAgent", "MomentumEKFAgent"):
            ht, hs = [], []
            for t_ns, typ, ev in a.log:
                if typ == "HOLDINGS_UPDATED":
                    ht.append(max((int(t_ns) - open_ns) / 1e9, 0.0))
                    hs.append(int(ev.get(ticker, 0)))
            rec["holdings_10s"] = _ffill_sample(np.array(ht), np.array(hs, dtype=float), g10)
        records.append(rec)

    # ── invariant flags ──
    book_ok = bool(np.all(snap_bid[two] < snap_ask[two])) and bool(np.all(ex_p > 0)) if len(ex_p) else True
    long_only_ok = True
    for i in fund_ids + mom_ids:
        for _, typ, ev in agents[i].log:
            if typ == "HOLDINGS_UPDATED" and (ev.get(ticker, 0) < 0 or ev.get("CASH", 0) < 0):
                long_only_ok = False
    flags = {"book_sanity": book_ok, "long_only": long_only_ok}
    if start_holdings is not None:
        flags["conservation"] = (
            sum(r["cash1"] for r in records) == sum(r["cash0"] for r in records)
            and sum(r["sh1"] for r in records) == sum(r["sh0"] for r in records)
        )

    return {
        "duration": duration,
        "grid": grid,
        "mid_1s": mid_1s,
        "val_1s": val_1s,
        "spr_1s": spr_1s,
        "close_1m": bar_closes(mid_1s, duration),
        "vol_1m": vol_1m,
        "net_1m": net,
        "fund_xhat_10s": fund_xhat,
        "mom_states": mom_states,
        "exec_t": ex_t, "exec_p": ex_p, "exec_q": ex_q,
        "close_cents": close_c,
        "n_execs": int(len(execs)),
        "shares_executed": int(ex_q[in_sess].sum()) if len(ex_q) else 0,
        "agents": records,
        "news": news,
        "probe": probe,
        "flags": flags,
        "oracle_events": list((getattr(oracle, "events", None) or {}).get(ticker, [])),
    }


# ── Part 3 metrics ────────────────────────────────────────────────────────


def sigma_1m_bps(r1: np.ndarray) -> Optional[float]:
    """3.1: 1e4 * std(r1, ddof=1)."""
    s = _std(r1)
    return None if s is None else 1e4 * s


def variance_ratio(close: np.ndarray, k: int) -> Optional[float]:
    """3.2: Var(ln p(t+k) - ln p(t)) / (k Var(r1)), overlapping k-step returns
    from the closes. 1 for a random walk; > 1 when returns are positively
    autocorrelated."""
    lp = np.log(np.asarray(close, dtype=float))
    if len(lp) < k + 3:
        return None
    r1 = np.diff(lp)
    rk = lp[k:] - lp[:-k]
    v1 = np.var(r1, ddof=1)
    if v1 == 0:
        return None
    return float(np.var(rk, ddof=1) / (k * v1))


def clustering(r1: np.ndarray, n_lags: int = 30) -> Dict[str, Any]:
    """3.3: acf of |r1| at lags 1..30; CS = mean lags 1-5, PS = mean lags 10-30."""
    a = acf(np.abs(np.asarray(r1, dtype=float)), n_lags=n_lags)
    return {"acf_abs": a, "cs": float(np.mean(a[0:5])), "ps": float(np.mean(a[9:30]))}


def minute_of_return(n_returns: int) -> np.ndarray:
    """r1[i] is the return over minute i + 1 (from the close of bar i to the
    close of bar i + 1); minute m spans [60 m, 60 (m + 1)] seconds."""
    return np.arange(n_returns) + 1


def vv_buckets(r1: np.ndarray, vol_1m: np.ndarray, bucket_min: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """3.5: per 5-min bucket, RV_b = sqrt(sum r1^2) and V_b = shares executed."""
    r1 = np.asarray(r1, dtype=float)
    vol_1m = np.asarray(vol_1m, dtype=float)
    n_b = int(math.ceil(len(vol_1m) / bucket_min))
    m = minute_of_return(len(r1)) // bucket_min
    rv = np.sqrt(np.bincount(m, weights=r1 ** 2, minlength=n_b)[:n_b])
    v = np.bincount(np.arange(len(vol_1m)) // bucket_min, weights=vol_1m, minlength=n_b)[:n_b]
    return rv, v


def vv_corr_buckets(rv: np.ndarray, v: np.ndarray) -> Optional[float]:
    """Spearman rank correlation of (RV_b, V_b)."""
    rv, v = np.asarray(rv, float), np.asarray(v, float)
    if len(rv) < 3 or np.all(rv == rv[0]) or np.all(v == v[0]):
        return None
    return _f(sps.spearmanr(rv, v)[0])


def u_ratio(vol_1m: np.ndarray) -> Optional[float]:
    """3.5: (volume 09:30-10:00 + 15:30-16:00) / (2 x mean 30-min volume
    10:00-15:30). Full day only."""
    v = np.asarray(vol_1m, dtype=float)
    if len(v) != 390:
        return None
    mid = v[30:360].sum() / 11.0
    return _ratio(v[:30].sum() + v[360:].sum(), 2.0 * mid)


def spread_metrics(spr_1s: np.ndarray) -> Dict[str, Optional[float]]:
    """3.6: spread in ticks (cents) over two-sided grid seconds."""
    s = np.asarray(spr_1s, dtype=float)
    ok = np.isfinite(s)
    two = s[ok]
    return {
        "spread_med_ticks": float(np.median(two)) if len(two) else None,
        "spread_p95_ticks": float(np.percentile(two, 95)) if len(two) else None,
        "spread_max_ticks": float(np.max(two)) if len(two) else None,
        "spread_mean_ticks": float(np.mean(two)) if len(two) else None,
        "one_sided_share": float(1.0 - ok.mean()) if len(s) else None,
    }


def window_returns(r1: np.ndarray, window_min: int = 30) -> List[np.ndarray]:
    """1-min returns grouped into non-overlapping windows of the day (by the
    minute each return covers); only complete windows of the session."""
    r1 = np.asarray(r1, dtype=float)
    m = minute_of_return(len(r1))
    n_w = (len(r1) + 1) // window_min
    return [r1[(m >= w * window_min) & (m < (w + 1) * window_min)] for w in range(n_w)]


def regime_contrast(r1: np.ndarray) -> Optional[float]:
    """3.8: max / min over the 30-min windows of the std of the 1-min returns
    inside each window (13 windows in a full day; window 1 holds 29 returns)."""
    sds = [np.std(w, ddof=1) for w in window_returns(r1) if len(w) >= 2]
    if len(sds) < 2 or min(sds) == 0:
        return None
    return float(max(sds) / min(sds))


def trend_share(close_1m: np.ndarray, window_min: int = 30) -> Optional[float]:
    """3.8: share of 1-min-stepped rolling 30-min windows whose |30-min
    return| exceeds 2x the day's median |30-min return|."""
    lp = np.log(np.asarray(close_1m, dtype=float))
    if len(lp) <= window_min:
        return None
    r = np.abs(lp[window_min:] - lp[:-window_min])
    med = np.median(r)
    if med == 0:
        return None
    return float(np.mean(r > 2.0 * med))


def run_metrics(s: Dict[str, Any]) -> Dict[str, Any]:
    """Every Part 3 market metric of one run, from its series."""
    mid, val, close = s["mid_1s"], s["val_1s"], s["close_1m"]
    r1 = returns_from_closes(close)
    n = len(r1)
    out: Dict[str, Any] = {"n_returns": n}

    # 3.1 volatility
    out["sigma_1m_bps"] = sigma_1m_bps(r1)
    out["sigma_day_implied"] = None if out["sigma_1m_bps"] is None else out["sigma_1m_bps"] * math.sqrt(N_DAY_RETURNS) / 100.0
    out["day_return"] = float(math.log(mid[-1] / mid[0]))
    out["day_return_pct"] = 100.0 * out["day_return"]

    # 3.2 predictability
    a = acf(r1, n_lags=5)
    band = 2.0 / math.sqrt(n) if n > 0 else None
    out["ac1"] = a[0] if n >= 3 else None
    out["ac_1_5"] = a
    out["ac_band"] = band
    out["n_out"] = int(sum(abs(x) > band for x in a)) if band else None
    out["vr5"] = variance_ratio(close, 5)
    out["vr30"] = variance_ratio(close, 30)

    # 3.3 clustering
    c = clustering(r1) if n >= 3 else {"acf_abs": [0.0] * 30, "cs": None, "ps": None}
    out.update(acf_abs=c["acf_abs"], cs=c["cs"], ps=c["ps"])

    # 3.4 tails
    ok = n >= 4 and np.std(r1) > 0
    out["kurt"] = float(sps.kurtosis(r1, fisher=True)) if ok else None
    out["skew"] = float(sps.skew(r1)) if ok else None

    # 3.5 volume and volatility
    rv, v = vv_buckets(r1, s["vol_1m"])
    out["vv_corr"] = vv_corr_buckets(rv, v)
    out["u_ratio"] = u_ratio(s["vol_1m"])

    # 3.6 spread
    out.update(spread_metrics(s["spr_1s"]))

    # 3.7 price vs value
    gap = np.asarray(mid, float) - np.asarray(val, float)
    lab = gap_half_life(gap, lags_s=LAB_GAP_LAGS)
    dash = gap_half_life(gap, lags_s=GAP_LAGS_S)
    out["gap_std"] = lab["std"]
    out["gap_mean_abs"] = lab["mean_abs"]
    out["gap_half_life_min"] = _f(lab["half_life_min"])
    out["gap_rho"] = lab["rho"]
    out["gap_half_life_min_dash"] = _f(dash["half_life_min"])
    # spec v1.4 §3.1: corrected reading (G10); gap_half_life_min above is the
    # "v1.3 estimator (biased for slow mispricing)", kept for continuity
    corr = gap_half_life_corrected(gap)
    out["gap_half_life_read_min"] = _f(corr["h_read"])
    out["gap_half_life_corr_min"] = _f(corr["h_corrected"])
    out["gap_half_life_corr_above"] = bool(corr["above_table"])
    out["gap_half_life_range"] = corr["h_range"]
    out["gap_mean"] = _f(corr["gap_mean"])
    out["gap_rho0"] = corr["rho0"]
    out["corr_mid_value"] = float(np.corrcoef(mid, val)[0, 1]) if np.std(mid) > 0 and np.std(val) > 0 else None
    val_close = bar_closes(val, s["duration"])
    out["vol_ratio_price_value"] = _ratio(_std(r1), _std(returns_from_closes(val_close)))

    # 3.8 regimes
    out["regime_contrast"] = regime_contrast(r1)
    out["trend_share"] = trend_share(close)

    out["shares_executed"] = int(s.get("shares_executed", int(np.sum(s["vol_1m"]))))
    # spec v1.4 L3: share of the 13 half-hour windows with at least one trade
    v = np.asarray(s["vol_1m"], dtype=float)
    win = [v[i:i + 30].sum() for i in range(0, len(v), 30)]
    out["active_halfhours_share"] = float(np.mean([w > 0 for w in win])) if win else None
    return out


# ── corrected gap half-life (spec v1.4 §3.1, D-R3-4) ──────────────────────

HL_TABLE_H_MIN = (0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240)
HL_TABLE_PATHS = 200
HL_TABLE_N = 23_401  # 1 s grid of a 6.5 h session
HL_TABLE_PATH = Path(__file__).with_name("realism_halflife_table.json")
_HL_TABLE: Optional[Dict[str, Any]] = None


def gap_half_life_read(gap: np.ndarray, dt: float = 1.0, lags_s: Sequence[int] = LAB_GAP_LAGS) -> Dict[str, Any]:
    """Steps 1-2 of §3.1: rho0(L) = sum g_t g_{t+L} / sum g_t^2 WITHOUT
    de-meaning; k = median(-ln rho0(L) / L) over 0.05 < rho0 < 0.98;
    h_read = ln 2 / k / 60 minutes (None if no lag qualifies)."""
    g = np.asarray(gap, dtype=float)
    denom = float(g @ g) if len(g) else 0.0
    rho, ks = [], []
    for L in lags_s:
        n = int(round(L / dt))
        if n <= 0 or n >= len(g) or denom == 0:
            rho.append(0.0)
            continue
        r = float(g[:-n] @ g[n:]) / denom
        rho.append(r)
        if GAP_RHO_RANGE[0] < r < GAP_RHO_RANGE[1]:
            ks.append(-math.log(r) / L)
    k = float(np.median(ks)) if ks else None
    return {
        "h_read": (math.log(2.0) / k / 60.0) if k and k > 0 else None,
        "gap_mean": float(np.mean(g)) if len(g) else None,
        "rho0": rho,
        "lags_s": [int(L) for L in lags_s],
    }


def _isotonic(y: Sequence[float]) -> List[float]:
    """Pool-adjacent-violators fit of a non-decreasing sequence (equal weights)."""
    blocks: List[List[float]] = []  # [sum, count]
    for v in y:
        blocks.append([float(v), 1.0])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
    out: List[float] = []
    for s, c in blocks:
        out.extend([s / c] * int(c))
    return out


def build_halflife_table(paths: int = HL_TABLE_PATHS, n: int = HL_TABLE_N) -> Dict[str, Any]:
    """Step 3 of §3.1: for each true half-life H (ascending), `paths` AR(1)
    gaps on the 1 s grid from the stationary distribution, drawn path by path
    from one numpy default_rng(seed=0); median and p10/p90 of h_read."""
    from scipy.signal import lfilter

    rng = np.random.default_rng(seed=0)
    rows = []
    for H in HL_TABLE_H_MIN:
        phi = math.exp(-math.log(2.0) / (H * 60.0))
        reads = []
        for _ in range(paths):
            e = rng.standard_normal(n)
            e[0] /= math.sqrt(1.0 - phi * phi)  # stationary start, unit innovations
            g = lfilter([1.0], [1.0, -phi], e)
            h = gap_half_life_read(g)["h_read"]
            reads.append(np.nan if h is None else h)
        x = np.array(reads)
        rows.append({
            "H": float(H), "median": float(np.nanmedian(x)), "p10": float(np.nanpercentile(x, 10)),
            "p90": float(np.nanpercentile(x, 90)), "n_none": int(np.isnan(x).sum()),
        })
    med = [r["median"] for r in rows]
    monotone = all(b > a for a, b in zip(med, med[1:]))
    if not monotone:  # §3.1 step 3: isotonic fit, recorded in DECISIONS.md
        for r, v in zip(rows, _isotonic(med)):
            r["median_raw"], r["median"] = r["median"], v
    return {"spec": "v1.4 §3.1", "rng": "numpy default_rng(seed=0)", "paths": paths, "n": n,
            "lags_s": list(LAB_GAP_LAGS), "monotone_raw": monotone, "rows": rows}


def halflife_table() -> Dict[str, Any]:
    """The committed table (api/realism_halflife_table.json), cached."""
    global _HL_TABLE
    if _HL_TABLE is None:
        _HL_TABLE = json.loads(HL_TABLE_PATH.read_text(encoding="utf-8"))
    return _HL_TABLE


def correct_half_life(h_read: Optional[float]) -> Dict[str, Any]:
    """Step 4 of §3.1. h_corrected: log-log linear interpolation of the inverse
    of median(h_read | H); below the first reading h_corrected = h_read; above
    the last None with above_table = True (">240 min"). h_range: [min, max] of
    the H whose p10..p90 reading interval contains h_read (None if none)."""
    if _f(h_read) is None:
        return {"h_corrected": None, "above_table": False, "h_range": None, "text": "none"}
    rows = halflife_table()["rows"]
    med = np.array([r["median"] for r in rows])
    Hs = np.array([r["H"] for r in rows])
    above = False
    if h_read < med[0]:
        hc = float(h_read)
    elif h_read > med[-1]:
        hc, above = None, True
    else:
        hc = float(np.exp(np.interp(math.log(h_read), np.log(med), np.log(Hs))))
    inside = [r["H"] for r in rows if r["p10"] <= h_read <= r["p90"]]
    return {
        "h_corrected": hc, "above_table": above,
        "h_range": [min(inside), max(inside)] if inside else None,
        "text": f">{Hs[-1]:g} min" if above else f"{hc:.1f} min",
    }


def gap_half_life_corrected(gap: np.ndarray, dt: float = 1.0, lags_s: Sequence[int] = LAB_GAP_LAGS) -> Dict[str, Any]:
    """§3.1: {"h_read", "h_corrected", "h_range", "gap_mean", "rho0", "lags_s"}
    (+ "above_table" when h_read is above the table: report ">240 min")."""
    r = gap_half_life_read(gap, dt, lags_s)
    c = correct_half_life(r["h_read"])
    return {"h_read": r["h_read"], "h_corrected": c["h_corrected"], "h_range": c["h_range"],
            "above_table": c["above_table"], "gap_mean": r["gap_mean"], "rho0": r["rho0"], "lags_s": r["lags_s"]}


# ── 3.9 accounting and 3.10 heavy-trader watch ───────────────────────────


def zero_sum(records: Sequence[Dict[str, int]], close_cents: float) -> Dict[str, Any]:
    """Sum of P&L vs holding over every agent, exactly, in cents.

    pnl_vs_hold = (cash1 + sh1 * close) - (cash0 + sh0 * close)
                = (cash1 - cash0) + (sh1 - sh0) * close.
    The close is a mid, so at most a half cent: it is held as an integer
    number of half cents and the sum is computed in integers."""
    close2 = int(round(2.0 * float(close_cents)))
    if abs(close2 - 2.0 * float(close_cents)) > 1e-6:
        raise ValueError(f"close {close_cents} is not a multiple of half a cent")
    tot2 = sum(2 * (r["cash1"] - r["cash0"]) + (r["sh1"] - r["sh0"]) * close2 for r in records)
    return {"zero_sum_cents": tot2 / 2.0, "ok": tot2 == 0}


def _q(x: Sequence[float], p: float) -> Optional[float]:
    x = [v for v in x if v is not None and math.isfinite(v)]
    return float(np.percentile(x, p)) if x else None


def agent_sanity(s: Dict[str, Any]) -> Dict[str, Any]:
    """3.9 / 3.10 from the series' agent records."""
    from .export import pnl_vs_hold  # spec: reuse api.export.pnl_vs_hold

    recs = s["agents"]
    close_c = s["close_cents"]
    total_traded = sum(r["traded"] for r in recs)  # both sides
    by_cls: Dict[str, List[Dict]] = defaultdict(list)
    for r in recs:
        r["pnl_vs_hold"] = pnl_vs_hold(r["cash1"] + r["sh1"] * close_c, r["cash0"], r["sh0"], close_c)
        by_cls[r["cls"]].append(r)
    classes = {}
    for cls in CLASSES + sorted(c for c in by_cls if c not in CLASSES and c != PROBE_CLASS):
        rs = by_cls.get(cls)
        if not rs:
            continue
        p = [r["pnl_vs_hold"] / 100.0 for r in rs]
        row = {
            "count": len(rs),
            "orders_sent": sum(r["orders"] for r in rs),
            "shares_traded": sum(r["traded"] for r in rs),
            "volume_share_pct": 100.0 * sum(r["traded"] for r in rs) / total_traded if total_traded else 0.0,
            "pnl_vs_hold_total": float(sum(p)),
            "pnl_vs_hold_median": _q(p, 50), "pnl_vs_hold_p10": _q(p, 10), "pnl_vs_hold_p90": _q(p, 90),
        }
        if cls in ("FundamentalistAgent", "MomentumEKFAgent"):
            turn = [r["traded"] for r in rs]
            pooled = np.concatenate([r["holdings_10s"] for r in rs]) if rs else np.array([])
            row.update(
                turnover_median=_q(turn, 50), turnover_p90=_q(turn, 90), turnover_max=float(max(turn)),
                holdings_p10=_q(pooled[np.isfinite(pooled)], 10), holdings_p90=_q(pooled[np.isfinite(pooled)], 90),
            )
        classes[cls] = row
    probe = [r for r in recs if r["cls"] == PROBE_CLASS]
    out = {
        "classes": classes,
        "probe_pnl_vs_hold": probe[0]["pnl_vs_hold"] / 100.0 if probe else None,
        "probe_volume_share_pct": 100.0 * probe[0]["traded"] / total_traded if probe and total_traded else None,
        **zero_sum(recs, close_c),
    }
    funds = by_cls.get("FundamentalistAgent", [])
    if funds:
        top = max(funds, key=lambda r: r["traded"])
        out["top_fund_id"] = top["id"]
        out["top_fund_turnover"] = top["traded"]
        out["top_fund_volume_share"] = 100.0 * top["traded"] / total_traded if total_traded else 0.0
    return out


# ── Part 4 grading ────────────────────────────────────────────────────────


def _in(x: float, intervals) -> bool:
    for lo, hi in intervals:
        if (lo is None or x >= lo) and (hi is None or x <= hi):
            return True
    return False


def grade_value(band: Dict[str, Any], values: Dict[str, Any]) -> Optional[str]:
    """PASS / WARN / FAIL for one band, given the metric values it needs.
    Boundaries take the better grade (closed intervals, PASS tested first).
    Returns None when the metric is missing, except G10 (None -> FAIL)."""
    rule = band.get("rule")
    if rule == "clustering":
        cs, ps = _f(values.get("cs")), _f(values.get("ps"))
        if cs is None or ps is None:
            return None
        if cs >= 0.10 and ps >= 0.03:  # "PS > 0.03": the boundary takes the better grade
            return "PASS"
        if cs >= 0.05:
            return "WARN"
        return "FAIL"
    if rule == "spread":
        med, p95 = _f(values.get("spread_med_ticks")), _f(values.get("spread_p95_ticks"))
        if med is None or p95 is None:
            return None
        if med <= 1.0 and p95 <= 5.0:
            return "PASS"
        if p95 <= 10.0:
            return "WARN"
        return "FAIL"
    x = _f(values.get(band["key"]))
    if x is None:
        return "FAIL" if band["id"] == "G10" and band["key"] in values else None
    if band.get("transform") == "abs":
        x = abs(x)
    if _in(x, band["pass"]):
        return "PASS"
    if _in(x, band["warn"]):
        return "WARN"
    return "FAIL"


def grade_run(metrics: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Single-run grades G1, G3-G11 (spec v1.3 §4.4)."""
    return {g: grade_value(BANDS_BY_ID[g], metrics) for g in RUN_GRADES}


def aggregate(values: Sequence[Any], min_seeds: int = MIN_VALID_SEEDS) -> Dict[str, Any]:
    """median, p10, p90, min, max over the valid (finite) values, n_seeds;
    status INCOMPLETE with fewer than min_seeds valid values (spec §4.3).
    Percentiles are numpy.percentile with linear interpolation."""
    x = np.array([v for v in values if _f(v) is not None], dtype=float)
    out = {"n_seeds": int(len(x)), "n_total": int(len(values))}
    if len(x):
        out.update(
            median=float(np.percentile(x, 50)), p10=float(np.percentile(x, 10)),
            p90=float(np.percentile(x, 90)), min=float(x.min()), max=float(x.max()),
        )
    else:
        out.update(median=None, p10=None, p90=None, min=None, max=None)
    out["status"] = "OK" if len(x) >= min_seeds else "INCOMPLETE"
    return out


def scorecard(per_seed: Sequence[Dict[str, Any]], min_seeds: int = MIN_VALID_SEEDS) -> Dict[str, Any]:
    """Lab scorecard of one configuration: G1, G3-G11 graded on the median
    over seeds, with pass_share; G2 from the cross-seed std of day returns."""
    out: Dict[str, Any] = {}
    for gid in RUN_GRADES:
        band = BANDS_BY_ID[gid]
        keys = band.get("metrics", [band["key"]])
        agg = {k: aggregate([m.get(k) for m in per_seed], min_seeds) for k in keys}
        med = {k: agg[k]["median"] for k in keys}
        if gid == "G10":  # None is a FAIL for a seed, but not a value for the median
            med = {band["key"]: med[band["key"]]}
        seed_grades = [grade_value(band, m) for m in per_seed]
        valid = [g for g in seed_grades if g is not None]
        incomplete = any(a["status"] == "INCOMPLETE" for a in agg.values())
        out[gid] = {
            "id": gid, "label": band["label"], "unit": band["unit"], "band": band["text"],
            "stats": agg,
            "grade": "INCOMPLETE" if incomplete else grade_value(band, med),
            "pass_share": (sum(g == "PASS" for g in valid) / len(valid)) if valid else None,
            "n_none": sum(1 for m in per_seed if _f(m.get(band["key"])) is None) if not band.get("rule") else 0,
        }
    day = [m.get("day_return_pct") for m in per_seed if _f(m.get("day_return_pct")) is not None]
    sd = float(np.std(day, ddof=1)) if len(day) >= 2 else None
    out["G2"] = {
        "id": "G2", "label": BANDS_BY_ID["G2"]["label"], "unit": "%", "band": BANDS_BY_ID["G2"]["text"],
        "stats": {"value": sd, "n_seeds": len(day), "status": "OK" if len(day) >= min_seeds else "INCOMPLETE"},
        "grade": ("INCOMPLETE" if len(day) < min_seeds else grade_value(BANDS_BY_ID["G2"], {"sigma_day_xseed": sd})),
        "pass_share": None,
    }
    return out


# ── 7.3 scenario analysis (treated vs baseline on the same seed) ─────────


def _win(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """x[a..b] on the 1 s grid, inclusive, clipped to the series."""
    a, b = max(0, int(round(a))), min(len(x) - 1, int(round(b)))
    return np.asarray(x[a:b + 1], dtype=float)


def sigma_window_bps(mid_1s: np.ndarray, a: float, b: float) -> Optional[float]:
    """Std (bps) of the 1-min log returns of the mid sampled every 60 s from a to b."""
    pts = np.asarray(mid_1s, dtype=float)[np.arange(int(a), int(b) + 1, 60)]
    return sigma_1m_bps(np.diff(np.log(pts)))


def first_crossing(xs: np.ndarray, start: int, end: int, level: float, above: bool = True) -> Optional[int]:
    seg = _win(xs, start, end)
    hit = np.flatnonzero(seg >= level if above else seg <= level)
    return int(start + hit[0]) if len(hit) else None


def jump_response(T: Dict[str, Any], B: Dict[str, Any], t0: int, jump_dollars: float) -> Dict[str, Any]:
    """Value-jump scenarios (S2, S2n, S3, S7c). Times in minutes after t0."""
    J = float(jump_dollars)
    f = (np.asarray(T["mid_1s"], float) - np.asarray(B["mid_1s"], float)) / J
    fs = smooth(f)
    end90, end60 = t0 + 5400, t0 + 3600
    out: Dict[str, Any] = {}
    for name, lvl in (("t50", 0.5), ("t90", 0.9)):
        k = first_crossing(fs, t0, end90, lvl)
        out[name] = None if k is None else (k - t0) / 60.0
    out["overshoot"] = float(max(0.0, np.max(_win(fs, t0, end60)) - 1.0))
    out["settle"] = float(np.mean(_win(f, end60, end90)))
    if "fund_xhat_10s" in T and len(T["fund_xhat_10s"]):
        for name, dt in (("belief_5", 300), ("belief_30", 1800)):
            j = (t0 + dt) // GRID_10S
            d = (np.asarray(T["fund_xhat_10s"])[:, j] - np.asarray(B["fund_xhat_10s"])[:, j]) / J
            out[name] = _f(np.nanmedian(d))
    want = MOM_STATES.index("BULL" if J > 0 else "BEAR")
    entries = [MOM_REASONS.index("BREAKOUT"), MOM_REASONS.index("REENTRY")]

    def n_entries(S):
        m = np.asarray(S.get("mom_states", np.zeros((0, 4))))
        if not len(m):
            return 0
        sel = (m[:, 1] >= t0) & (m[:, 1] <= t0 + 1800) & (m[:, 2] == want) & np.isin(m[:, 3], entries)
        return int(sel.sum())

    out["mom_entries"] = n_entries(T) - n_entries(B)
    out["net_flow"] = net_flow(T, B, t0, t0 + 3600)
    out["vol_uplift"] = _ratio(sigma_window_bps(T["mid_1s"], t0, t0 + 1800), sigma_window_bps(B["mid_1s"], t0, t0 + 1800))
    out["volume_uplift"] = _ratio(window_volume(T, t0, t0 + 1800), window_volume(B, t0, t0 + 1800))
    out.update(jump_window_metrics(T, t0, J))
    return out


def jump_window_metrics(T: Dict[str, Any], t0: int, jump_dollars: float, window_s: int = 1800) -> Dict[str, Any]:
    """spec v1.4 §3.2, treated run only, window [t0, t0 + 30 min]:
    one_sided_share_jump (share of 1 s points with an empty side),
    spread_p95_jump_ticks / spread_max_jump_ticks (two-sided points),
    price_path_steps (1-min bars in the window with |return| > 25% of J,
    the return being the change of the mid sampled every 60 s, in dollars)."""
    spr = _win(T["spr_1s"], t0, t0 + window_s) if "spr_1s" in T else np.array([])
    ok = np.isfinite(spr)
    two = spr[ok]
    pts = _win(T["mid_1s"], t0, t0 + window_s)[::60]
    steps = int(np.sum(np.abs(np.diff(pts)) > 0.25 * abs(float(jump_dollars)))) if len(pts) > 1 else 0
    return {
        "one_sided_share_jump": float(1.0 - ok.mean()) if len(spr) else None,
        "spread_p95_jump_ticks": float(np.percentile(two, 95)) if len(two) else None,
        "spread_max_jump_ticks": float(np.max(two)) if len(two) else None,
        "price_path_steps": steps,
    }


def window_volume(S: Dict[str, Any], a: int, b: int) -> float:
    """Shares executed in the 1-min bars covering [a, b) seconds."""
    return float(np.sum(np.asarray(S["vol_1m"], float)[a // 60: b // 60]))


def net_flow(T: Dict[str, Any], B: Dict[str, Any], a: int, b: int) -> Dict[str, float]:
    """Net shares bought by each class in the bars covering [a, b), treated minus baseline."""
    nt = np.asarray(T["net_1m"], float)[:, a // 60: b // 60].sum(axis=1)
    nb = np.asarray(B["net_1m"], float)[:, a // 60: b // 60].sum(axis=1)
    return {c: float(nt[i] - nb[i]) for i, c in enumerate(FLOW_CLASSES)}


def news_response(T: Dict[str, Any], B: Dict[str, Any], t0: int, sentiment: float) -> Dict[str, Any]:
    """News-only scenarios (S4, S4n). R in bps, positive = the expected direction."""
    s = 1.0 if sentiment > 0 else -1.0
    R = s * 1e4 * np.log(np.asarray(T["mid_1s"], float) / np.asarray(B["mid_1s"], float))
    Rs = smooth(R)
    seg = _win(Rs, t0, t0 + 1800)
    k = int(np.argmax(seg))
    peak, t_peak = float(seg[k]), t0 + k
    rev = first_crossing(Rs, t_peak + 1, t0 + 5400, peak / 2.0, above=False) if peak > 0 else None
    return {
        "R_peak": peak,
        "t_peak": k / 60.0,
        "t_half_rev": None if rev is None else (rev - t0) / 60.0,
        "R_60": float(np.mean(_win(R, t0 + 3300, t0 + 3900))),
    }


def vol_burst(T: Dict[str, Any], B: Dict[str, Any], t0: int, t1: int) -> Dict[str, Any]:
    """Volatility burst (S5): treated / baseline in [t0, t1] and the hour after."""
    t2 = t1 + (t1 - t0)

    def spread_mean(S, a, b):
        x = _win(S["spr_1s"], a, b)
        x = x[np.isfinite(x)]
        return float(np.mean(x)) if len(x) else None

    def gap_std(S, a, b):
        return float(np.std(_win(S["mid_1s"], a, b) - _win(S["val_1s"], a, b)))

    return {
        "in_ratio": _ratio(sigma_window_bps(T["mid_1s"], t0, t1), sigma_window_bps(B["mid_1s"], t0, t1)),
        "after_ratio": _ratio(sigma_window_bps(T["mid_1s"], t1, t2), sigma_window_bps(B["mid_1s"], t1, t2)),
        "value_in_ratio": _ratio(sigma_window_bps(T["val_1s"], t0, t1), sigma_window_bps(B["val_1s"], t0, t1)),
        "spread_ratio": _ratio(spread_mean(T, t0, t1), spread_mean(B, t0, t1)),
        "volume_ratio": _ratio(window_volume(T, t0, t1), window_volume(B, t0, t1)),
        "gap_std_ratio": _ratio(gap_std(T, t0, t1), gap_std(B, t0, t1)),
        "gap_std_T": gap_std(T, t0, t1),
        "gap_std_B": gap_std(B, t0, t1),
    }


def mm_pause(T: Dict[str, Any], B: Dict[str, Any], w0: int, w1: int) -> Dict[str, Any]:
    """Market-maker pause (S6), window W = [w0, w1)."""
    out: Dict[str, Any] = {}
    for tag, S in (("T", T), ("B", B)):
        sm = spread_metrics(_win(S["spr_1s"], w0, w1 - 1))
        out[f"spread_mean_{tag}"] = sm["spread_mean_ticks"]
        out[f"spread_p95_{tag}"] = sm["spread_p95_ticks"]
        out[f"spread_max_{tag}"] = sm["spread_max_ticks"]
        out[f"one_sided_{tag}"] = sm["one_sided_share"]
    out["sigma_ratio"] = _ratio(sigma_window_bps(T["mid_1s"], w0, w1), sigma_window_bps(B["mid_1s"], w0, w1))
    out["volume_ratio"] = _ratio(window_volume(T, w0, w1), window_volume(B, w0, w1))
    out["max_abs_mid_diff"] = float(np.max(np.abs(_win(T["mid_1s"], w0, w1 - 1) - _win(B["mid_1s"], w0, w1 - 1))))

    # recovery: first t >= w1 where the mean spread over [t, t + 5 min) is
    # <= 1.2x the baseline's over the same 5 minutes
    def fwd5(S):
        x = pd.Series(np.asarray(S["spr_1s"], float))
        return x[::-1].rolling(300, min_periods=1).mean()[::-1].to_numpy()  # mean over [t, t+300)

    rT, rB = fwd5(T), fwd5(B)
    n = len(rT)
    hit = None
    for t in range(w1, n - 300):
        if np.isfinite(rT[t]) and np.isfinite(rB[t]) and rT[t] <= 1.2 * rB[t]:
            hit = t
            break
    out["recovery_min"] = None if hit is None else (hit - w1) / 60.0
    return out


def impact_run(T: Dict[str, Any], B: Dict[str, Any], t0: int, duration_s: int, side: str,
               quantity: int, baseline_shares: float, probe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One price-impact run (IMP-*). I in bps, positive = against the trader."""
    s = 1.0 if side == "BUY" else -1.0
    D = int(duration_s)
    I = s * 1e4 * np.log(np.asarray(T["mid_1s"], float) / np.asarray(B["mid_1s"], float))
    roll = smooth(I)
    arrival = float(B["mid_1s"][t0])
    out = {
        "q": quantity / baseline_shares if baseline_shares else None,
        "I_end": float(np.mean(_win(I, t0 + D - 10, t0 + D))),
        "I_peak": float(np.max(_win(roll, t0, t0 + D + 120))),
        "I_perm": float(np.mean(_win(I, t0 + D + 1500, t0 + D + 2100))),
        "arrival_mid": arrival,
    }
    summ = (probe or {}).get("summary") or {}
    filled = summ.get("filled")
    vwap = summ.get("vwap_cents")
    out["fill_rate"] = (filled / quantity) if (filled is not None and quantity) else None
    out["shortfall_bps"] = (s * 1e4 * (vwap / 100.0 / arrival - 1.0)) if vwap else None
    out["absorbed"] = dict((probe or {}).get("absorbed") or {})
    out["recovery"] = _ratio(out["I_perm"], out["I_peak"])
    return out


def impact_beta(q_by_size: Dict[str, Sequence[float]], I_by_size: Dict[str, Sequence[float]],
                n_boot: int = 2000, seed: int = 0, ci: float = 0.90) -> Dict[str, Any]:
    """Exponent beta = OLS slope of ln(median I) on ln(median q) over the sizes,
    with a bootstrap over seeds (the same resampled seeds for every size,
    since the sizes share their baselines). Sizes whose median I <= 0 make
    the log undefined: such resamples are dropped and counted."""
    sizes = list(q_by_size)
    Q = np.array([np.asarray(q_by_size[k], float) for k in sizes])  # sizes x seeds
    I = np.array([np.asarray(I_by_size[k], float) for k in sizes])

    def slope(qm, im):
        if np.any(im <= 0) or np.any(qm <= 0):
            return None
        return float(np.polyfit(np.log(qm), np.log(im), 1)[0])

    beta = slope(np.median(Q, axis=1), np.median(I, axis=1))
    rng = np.random.RandomState(seed)
    n = Q.shape[1]
    boots, dropped = [], 0
    for _ in range(n_boot):
        idx = rng.randint(0, n, size=n)
        b = slope(np.median(Q[:, idx], axis=1), np.median(I[:, idx], axis=1))
        if b is None:
            dropped += 1
        else:
            boots.append(b)
    lo_p, hi_p = 50.0 * (1.0 - ci), 50.0 * (1.0 + ci)
    return {
        "beta": beta,
        "ci": [float(np.percentile(boots, lo_p)), float(np.percentile(boots, hi_p))] if boots else None,
        "n_boot": n_boot, "n_boot_dropped": dropped, "sizes": sizes,
    }


def noise_floor(I_end_placebo: Sequence[float], I_perm_placebo: Sequence[float]) -> Dict[str, Optional[float]]:
    """p90 over seeds of |I_end| and |I_perm| for the placebo IMP-0."""
    return {
        "I_end": _q([abs(x) for x in I_end_placebo], 90),
        "I_perm": _q([abs(x) for x in I_perm_placebo], 90),
    }


def resolved(median_abs_I: Optional[float], floor: Optional[float]) -> Optional[bool]:
    """A size is resolved when its median |I| is at least 2x the noise floor."""
    if median_abs_I is None or floor is None:
        return None
    return bool(abs(median_abs_I) >= 2.0 * floor)


# ── R3 scorecard (spec v1.4 Part 2, §3.3; pre-registered) ────────────────
# Inputs are medians over seeds: "C" = the no-trigger config, "S2"/"S2n" =
# the jump configs (jump_response of treated vs baseline). Operators are
# exactly as Part 2 writes them; "abs" applies |.| to the median (as G3).
# One check per (scope, key); a target passes when all its checks pass.

R3_TARGETS: List[Dict[str, Any]] = [
    {"id": "T1", "label": "|ac1| of 1-min returns", "checks": [("C", "ac1", "abs<=", 0.10)]},
    {"id": "T2", "label": "VR(5)", "checks": [("C", "vr5", ">=", 0.80), ("C", "vr5", "<=", 1.25)]},
    {"id": "T3", "label": "price vol / value vol", "checks": [("C", "vol_ratio_price_value", ">=", 0.90)]},
    {"id": "T4", "label": "volume-volatility Spearman", "checks": [("C", "vv_corr", ">", 0.0)]},
    {"id": "T5", "label": "volume uplift after a ±2% jump",
     "checks": [("S2", "volume_uplift", ">", 1.0), ("S2n", "volume_uplift", ">", 1.0)]},
    {"id": "T6", "label": "no emptied book during a jump",
     "checks": [("S2", "one_sided_share_jump", "<=", 0.01), ("S2", "spread_p95_jump_ticks", "<=", 10.0),
                ("S2n", "one_sided_share_jump", "<=", 0.01), ("S2n", "spread_p95_jump_ticks", "<=", 10.0)]},
    {"id": "T7", "label": "informed fundamentalists earn their information ($)",
     "checks": [("C", "fund_pnl_total", ">", 0.0), ("C", "fund_pnl_median", ">", 0.0)]},
]
R3_LIMITS: List[Dict[str, Any]] = [
    {"id": "L1", "label": "spread (ticks)",
     "checks": [("C", "spread_med_ticks", "<=", 2.0), ("C", "spread_p95_ticks", "<=", 10.0)]},
    {"id": "L2", "label": "shares executed per day", "checks": [("C", "shares_executed", ">=", 295_500)]},
    {"id": "L3", "label": "trades all day with num_value = 0 (share of half-hours with trades)",
     "checks": [("C", "active_halfhours_share", ">=", 1.0)]},
    {"id": "L4", "label": "zero_sum = 0 in every run (1 = yes)", "checks": [("C", "zero_sum_all_zero", ">=", 1.0)]},
    {"id": "L5", "label": "median wall time of a full day (s)", "checks": [("C", "wall_time_s", "<=", 90.0)]},
]
R3_MISS_SCALE = {"T1": 0.10, "T2": 0.45, "T3": 0.90, "T4": 0.30}  # §7.4 tie-break


def _check(value: Optional[float], op: str, thr: float) -> Optional[bool]:
    x = _f(value)
    if x is None:
        return None
    if op == "abs<=":
        return abs(x) <= thr
    return {">": x > thr, ">=": x >= thr, "<=": x <= thr, "<": x < thr}[op]


def _miss(value: Optional[float], op: str, thr: float) -> Optional[float]:
    """Distance outside the target (0 when inside)."""
    x = _f(value)
    if x is None:
        return None
    if op == "abs<=":
        return max(0.0, abs(x) - thr)
    if op in (">", ">="):
        return max(0.0, thr - x)
    return max(0.0, x - thr)


def _r3_item(item: Dict[str, Any], summaries: Dict[str, Dict[str, Any]], screening: bool = False) -> Dict[str, Any]:
    checks, oks, misses = [], [], []
    for scope, key, op, thr in item["checks"]:
        if screening and scope == "S2n":  # §7.4: T5, T6 on S2 only in screening
            continue
        v = summaries.get(scope, {}).get(key)
        ok = _check(v, op, thr)
        checks.append({"scope": scope, "key": key, "op": op, "threshold": thr, "value": _f(v),
                       "result": None if ok is None else ("PASS" if ok else "FAIL")})
        oks.append(ok)
        m = _miss(v, op, thr)
        if m is not None:
            misses.append(m)
    if any(o is None for o in oks):
        status = "MISSING"
    else:
        status = "PASS" if all(oks) else "FAIL"
    out = {"id": item["id"], "label": item["label"], "checks": checks, "status": status}
    if item["id"] in R3_MISS_SCALE:
        out["norm_miss"] = (sum(misses) / R3_MISS_SCALE[item["id"]]) if len(misses) == len(checks) else None
    return out


def r3_scorecard(per_config_summaries: Dict[str, Dict[str, Any]], screening: bool = False) -> Dict[str, Any]:
    """T1-T7 and L1-L5 of spec v1.4 Part 2 with value, threshold, PASS/FAIL.
    per_config_summaries: {"C": {...}, "S2": {...}, "S2n": {...}} of medians
    (a scope that is absent makes the items that need it MISSING).
    screening=True drops the S2n checks (§7.4: T5, T6 on S2 only)."""
    targets = {t["id"]: _r3_item(t, per_config_summaries, screening) for t in R3_TARGETS}
    limits = {x["id"]: _r3_item(x, per_config_summaries, screening) for x in R3_LIMITS}
    return {
        "targets": targets, "limits": limits,
        "n_targets_passed": sum(t["status"] == "PASS" for t in targets.values()),
        "all_pass": all(x["status"] == "PASS" for x in list(targets.values()) + list(limits.values())),
    }

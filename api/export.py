"""ABIDES end_state -> dashboard payload (spec Sections 3 and 4).

Conventions in the payload: times are seconds since market open (09:30),
prices are dollars, shares are integers, series are columnar. Everything the
dashboard shows is derived here from the simulation's own logs; nothing is
estimated or invented. Events before 09:30 are dropped from displayed series.
"""

import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from abides_markets.configs.param_ranges import ranges_for_export

from . import SCHEMA_VERSION
from . import realism
from .downsample import change_points, downsample_columns, lttb_indices
from .schema import RunParams, SimPayload
from .stats import gap_series, market_stats, value_at

MAX_QUOTES = 6000
MAX_ORACLE = 2000
MAX_GAP = 2000
MAX_AGENT_POINTS = 3000
DEPTH_STEP_S = 30
DEPTH_LEVELS = 10
ER_SMOOTH_WINDOW = 20
EVENT_WINDOW = (-300, 1800, 10)  # seconds relative to the news, step

FUND_HYPERPARAMS = [
    "er_window", "delta", "lambda_er", "sigma_n", "gamma", "k", "mu",
    "q", "a_max", "z0", "s_max", "b_f", "k_news", "initial_exposure",
]
# spec v1.4 Part 4 / v1.4.1 Part 2: informed-mode and learning hyperparameters
INFORMED_HYPERPARAMS = ["wake_mean", "rho", "m0", "kappa_m", "h0", "theta_q", "T_r", "sigma_r"]
LEARNING_HYPERPARAMS = ["n_pl", "eps_thr", "a_pl"]
MAX_FUND_DETAIL = 20  # spec v1.4 §6.3
# tau is realised as tau_ratio * wake_mean (spec v1.1 M3); both are exported
MOM_HYPERPARAMS = [
    "initial_exposure", "N_w", "n_er", "lambda_er", "kappa_R", "c_P", "tau_ratio", "tau",
    "kappa_l", "kappa_v", "a_eps", "eps_thr", "g_max", "gamma", "k_c",
    "theta_in", "theta_out", "ER_min", "k_stop", "k_re", "T_0", "lambda_v",
    "e_max", "e_min", "b", "n_min", "k_add", "mu_m", "eta_news", "rho_news",
    "wake_mean",
]
OPTIONAL_DECISION_FIELDS = ["added", "exit_pending", "sigma_hat2", "sigma_tau"]
SKIP_REASONS = ["dead_band", "anti_chase", "no_cash", "no_shares"]


# ── small helpers ─────────────────────────────────────────────────────────


def _sig(x: Optional[float], digits: int = 6) -> Optional[float]:
    """Round to `digits` significant figures (keeps tiny values like v_hat)."""
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        return None
    if x == 0:
        return 0.0
    return float(f"{x:.{digits}g}")


def _price(x: Optional[float]) -> Optional[float]:
    """Cents -> dollars, 4 decimals (sub-cent mids exist: (bid+ask)/2)."""
    if x is None:
        return None
    return round(float(x) / 100.0, 4)


def _t(x: float) -> float:
    return round(float(x), 3)


def _events(agent, *types: str):
    """(t_ns, type, event) for the requested event types, in log order."""
    wanted = set(types)
    for t_ns, typ, ev in agent.log:
        if typ in wanted:
            yield t_ns, typ, ev


def _rolling_mean(v: List[float], window: int) -> List[float]:
    if not v:
        return []
    return pd.Series(v, dtype=float).rolling(window, min_periods=1).mean().tolist()


def _side_is_buy(side) -> bool:
    if hasattr(side, "is_bid"):
        return side.is_bid()
    return str(side).upper() in ("BID", "SIDE.BID", "BUY")


# ── market ────────────────────────────────────────────────────────────────


class _Clock:
    def __init__(self, open_ns: int, close_ns: int):
        self.open_ns = open_ns
        self.duration = (close_ns - open_ns) / 1e9

    def s(self, t_ns) -> float:
        return (int(t_ns) - self.open_ns) / 1e9

    def in_session(self, t: float) -> bool:
        return 0.0 <= t <= self.duration


def _book_snapshots(ob, clock: _Clock):
    """Full-resolution (t, bid, ask) in cents plus the raw snapshots used for
    depth, restricted to the session and to two-sided books."""
    ts, bids, asks, snaps = [], [], [], []
    for row in ob.book_log2:
        b, a = row["bids"], row["asks"]
        if len(b) == 0 or len(a) == 0:
            continue
        t = clock.s(row["QuoteTime"])
        if not clock.in_session(t):
            continue
        bb, ba = float(b[0][0]), float(a[0][0])
        if bb <= 0 or ba <= 0:
            continue
        ts.append(t)
        bids.append(bb)
        asks.append(ba)
        snaps.append(row)
    return np.array(ts), np.array(bids), np.array(asks), snaps


def _candles(t: np.ndarray, mid: np.ndarray, exec_t: np.ndarray, exec_q: np.ndarray, duration: float) -> Dict:
    """1-minute OHLC from the full-resolution mid; volume and trade counts from
    the exchange's EXEC history. Minutes without quote changes carry the
    previous close forward (O = H = L = C)."""
    n_buckets = max(1, int(math.ceil(duration / 60.0)))
    edges = np.arange(n_buckets + 1) * 60.0
    lo_idx = np.searchsorted(t, edges[:-1], side="left")
    hi_idx = np.searchsorted(t, edges[1:], side="left")
    hi_idx[-1] = len(t)  # last bucket includes the closing instant
    vol_bucket = np.clip((exec_t // 60).astype(int), 0, n_buckets - 1) if len(exec_t) else np.array([], int)
    volume = np.bincount(vol_bucket, weights=exec_q, minlength=n_buckets).astype(int) if len(exec_t) else np.zeros(n_buckets, int)
    trades = np.bincount(vol_bucket, minlength=n_buckets).astype(int) if len(exec_t) else np.zeros(n_buckets, int)

    o, h, l, c = [], [], [], []
    prev = float(mid[0]) if len(mid) else 0.0
    for i in range(n_buckets):
        seg = mid[lo_idx[i]:hi_idx[i]]
        if len(seg) == 0:
            o.append(prev); h.append(prev); l.append(prev); c.append(prev)
        else:
            o.append(float(seg[0])); h.append(float(seg.max()))
            l.append(float(seg.min())); c.append(float(seg[-1]))
            prev = float(seg[-1])
    return {
        "t": [float(x) for x in edges[:-1]],
        "o": o, "h": h, "l": l, "c": c,
        "volume": volume.tolist(), "trades": trades.tolist(),
    }


def _depth(snaps, snap_t: np.ndarray, duration: float) -> Dict:
    """One book snapshot per DEPTH_STEP_S: the last at or before each grid
    time, top DEPTH_LEVELS levels, [price $, shares]."""
    out = {"t": [], "bids": [], "asks": []}
    for g in np.arange(0.0, duration + 1e-9, DEPTH_STEP_S):
        i = int(np.searchsorted(snap_t, g, side="right")) - 1
        if i < 0:
            continue
        row = snaps[i]
        out["t"].append(float(g))
        out["bids"].append([[_price(p), int(q)] for p, q in row["bids"][:DEPTH_LEVELS]])
        out["asks"].append([[_price(p), int(q)] for p, q in row["asks"][:DEPTH_LEVELS]])
    return out


# ── agents ────────────────────────────────────────────────────────────────


def pnl_vs_hold(final_value: float, start_cash: float, start_shares: int, close: float) -> float:
    """Spec v1.1 D2: final value minus the value of simply holding the
    starting portfolio to the close (removes the endowment's mark-to-market)."""
    return final_value - (start_cash + start_shares * close)


def _agent_common(agent, clock: _Clock, ticker: str, candles: Dict, close: float, hyper_keys: List[str]) -> Dict:
    """AgentBase fields shared by both EKF agent kinds."""
    hold_t, hold_cash, hold_sh = [], [], []
    for t_ns, _, ev in _events(agent, "HOLDINGS_UPDATED"):
        t = clock.s(t_ns)
        if t > clock.duration:
            continue
        # the first event is the endowment logged at the first (pre-open)
        # wake; it becomes the t = 0 start point
        hold_t.append(max(t, 0.0))
        hold_cash.append(ev.get("CASH", 0) / 100.0)
        hold_sh.append(int(ev.get(ticker, 0)))
    if not hold_t:
        hold_t, hold_cash, hold_sh = [0.0], [agent.holdings.get("CASH", 0) / 100.0], [int(agent.holdings.get(ticker, 0))]
    # keep the last state per timestamp, then change points only
    keep = change_points(hold_t, hold_cash, hold_sh)
    holdings = {
        "t": [_t(hold_t[i]) for i in keep],
        "cash": [round(hold_cash[i], 2) for i in keep],
        "shares": [hold_sh[i] for i in keep],
    }

    fills = {"t": [], "side": [], "qty": [], "price": []}
    for t_ns, _, ev in _events(agent, "ORDER_EXECUTED"):
        if ev.get("fill_price") is None:
            continue
        fills["t"].append(_t(clock.s(t_ns)))
        fills["side"].append("BUY" if _side_is_buy(ev.get("side")) else "SELL")
        fills["qty"].append(int(ev.get("quantity", 0)))
        fills["price"].append(_price(ev["fill_price"]))
    n_orders = sum(1 for _ in _events(agent, "ORDER_SUBMITTED"))

    # value each minute: holdings as-of the minute's end x the candle close
    ht = np.array(holdings["t"])
    v_t, v_v = [], []
    for i, (t0, c) in enumerate(zip(candles["t"], candles["c"])):
        t_end = min(t0 + 60.0, clock.duration)
        j = max(0, int(np.searchsorted(ht, t_end, side="right")) - 1)
        v_t.append(_t(t_end))
        v_v.append(round(holdings["cash"][j] + holdings["shares"][j] * c, 2))

    start_value = agent.starting_cash / 100.0
    ending = [ev for _, _, ev in _events(agent, "ENDING_CASH")]
    # final.value is the agent's own mark_to_market at kernel stop (ENDING_CASH)
    final_value = (ending[-1] / 100.0) if ending else holdings["cash"][-1] + holdings["shares"][-1] * close
    final_cash = agent.holdings.get("CASH", 0) / 100.0
    final_sh = int(agent.holdings.get(ticker, 0))
    pnl = final_value - start_value
    vs_hold = pnl_vs_hold(final_value, holdings["cash"][0], holdings["shares"][0], close)
    return {
        "id": int(agent.id),
        "name": agent.name,
        "hyperparams": {k: float(getattr(agent, k)) for k in hyper_keys if hasattr(agent, k)},
        "start": {"cash": holdings["cash"][0], "shares": holdings["shares"][0], "value": round(start_value, 2)},
        "final": {
            "cash": round(final_cash, 2),
            "shares": final_sh,
            "value": round(final_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": _sig(100.0 * pnl / start_value if start_value else 0.0),
            "pnl_vs_hold": round(vs_hold, 2),
            "pnl_vs_hold_pct": _sig(100.0 * vs_hold / start_value if start_value else 0.0),
            "exposure_pct": _sig(100.0 * final_sh * close / final_value if final_value else 0.0),
            "n_orders": n_orders,
            "n_fills": len(fills["t"]),
        },
        "holdings": holdings,
        "value_1m": {"t": v_t, "v": v_v},
        "fills": fills,
    }


def fund_detail_ids(ids: List[int], n_max: int = MAX_FUND_DETAIL) -> List[int]:
    """spec v1.4 §6.3: at most n_max fundamentalists keep detailed series,
    chosen as evenly spaced indices over the sorted ids (deterministic)."""
    ids = sorted(ids)
    if len(ids) <= n_max:
        return ids
    return sorted({ids[int(round(x))] for x in np.linspace(0, len(ids) - 1, n_max)})


def _fundamental(agent, clock, ticker, candles, close, detail: bool = True) -> Dict:
    mode = getattr(agent, "mode", "price_only")
    learning = mode == "informed" and getattr(agent, "price_learning", "off") != "off"
    keys = FUND_HYPERPARAMS + (INFORMED_HYPERPARAMS if mode == "informed" else []) + (LEARNING_HYPERPARAMS if learning else [])
    d = _agent_common(agent, clock, ticker, candles, close, keys)
    if mode == "informed":
        from abides_markets.agents.fundamental import INFORMED_W_MAX, INFORMED_W_MIN

        d["hyperparams"].update(w_min=float(INFORMED_W_MIN), w_max=float(INFORMED_W_MAX))
    d.update(kind="fundamental", mode=mode, detail=bool(detail))
    if not detail:
        d.update(research={"t": [], "y_r": []},
                 ekf={k: [] for k in ["t", "mid", "x_hat", "P", "R", "K", "ER", "ER_smooth", "Q", "sigma_f2"]},
                 caution={"t": [], "D": [], "E": [], "C": []}, news=[])
        return d
    research = {"t": [], "y_r": []}
    for t_ns, _, ev in _events(agent, "RESEARCH_READING"):
        t = clock.s(t_ns)
        if clock.in_session(t):
            research["t"].append(_t(t))
            research["y_r"].append(_price(ev["y_r"] / 100.0))
    ekf = defaultdict(list)
    for t_ns, _, ev in _events(agent, "EKF_UPDATE"):
        t = clock.s(t_ns)
        if not clock.in_session(t):
            continue
        ekf["t"].append(t)
        ekf["mid"].append(ev["mid"] / 100.0)
        ekf["x_hat"].append(ev["x_hat"] / 100.0)
        ekf["P"].append(ev["P"] / 1e4)  # cents^2 -> $^2
        ekf["R"].append(ev["R"] / 1e4)
        ekf["K"].append(ev["K"])
        ekf["ER"].append(ev["ER"])
        ekf["Q"].append(ev["Q"] / 1e4)  # cents^2 -> $^2
        ekf["sigma_f2"].append(ev["sigma_f2"] / 1e4)  # cents^2/s -> $^2/s
        if learning:
            ekf["eps"].append(ev.get("eps", 0.0))
            ekf["g"].append(ev.get("g", 1.0))
            ekf["rho_eff"].append(ev.get("rho_eff", getattr(agent, "rho", 1.0)))
    ekf["ER_smooth"] = _rolling_mean(ekf["ER"], ER_SMOOTH_WINDOW)
    keys = ["t", "mid", "x_hat", "P", "R", "K", "ER", "ER_smooth", "Q", "sigma_f2"] + (["eps", "g", "rho_eff"] if learning else [])
    ekf = downsample_columns({k: ekf[k] for k in keys}, "x_hat", MAX_AGENT_POINTS)

    caution = defaultdict(list)
    for t_ns, _, ev in _events(agent, "CAUTION_UPDATE"):
        t = clock.s(t_ns)
        if not clock.in_session(t):
            continue
        caution["t"].append(t)
        caution["D"].append(float(ev["D_prev"]))
        caution["E"].append(ev["E_t"] / 100.0)  # virtual P&L memory, cents -> $
        caution["C"].append(ev["C_t"])
    caution = downsample_columns({k: caution[k] for k in ["t", "D", "E", "C"]}, "C", MAX_AGENT_POINTS)

    news = []
    for t_ns, _, ev in _events(agent, "NEWS_RECEIVED"):
        news.append({
            "t": _t(clock.s(t_ns)),
            "headline": ev["headline"],
            "sentiment": float(ev["sentiment"]),
            "shift": _sig(ev["shift"] / 100.0),  # signed $
            "sigma_move": _sig(ev["sigma_move"] / 100.0),
            "x_hat_before": _price(ev["x_hat_before"]),
            "x_hat_after": _price(ev["x_hat_after"]),
            "P_before": _sig(ev["P_before"] / 1e4),  # cents^2 -> $^2
            "P_after": _sig(ev["P_after"] / 1e4),
        })

    d.update(
        research=research,
        ekf={
            "t": [_t(x) for x in ekf["t"]],
            "mid": [round(x, 4) for x in ekf["mid"]],
            "x_hat": [round(x, 4) for x in ekf["x_hat"]],
            **{k: [_sig(x) for x in ekf[k]] for k in ["P", "R", "K", "ER", "ER_smooth", "Q", "sigma_f2"]},
            **({k: [_sig(x) for x in ekf[k]] for k in ["eps", "g", "rho_eff"]} if learning else {}),
        },
        caution={
            "t": [_t(x) for x in caution["t"]],
            **{k: [_sig(x) for x in caution[k]] for k in ["D", "E", "C"]},
        },
        news=news,
    )
    return d


def _momentum(agent, clock, ticker, candles, close) -> Dict:
    d = _agent_common(agent, clock, ticker, candles, close, MOM_HYPERPARAMS)

    warm = [t_ns for t_ns, _, _ in _events(agent, "MOM_WARMUP_DONE")]
    warmup_end_t = _t(clock.s(warm[0])) if warm else None

    kf = defaultdict(list)
    for t_ns, _, ev in _events(agent, "MOM_KF_UPDATE"):
        t = clock.s(t_ns)
        if not clock.in_session(t):
            continue
        l, sd = ev["l_hat"], math.sqrt(max(ev["P00"], 0.0))
        kf["t"].append(t)
        kf["mid"].append(ev["mid"] / 100.0)
        kf["level"].append(math.exp(l) / 100.0)
        kf["band_lo"].append(math.exp(l - 2 * sd) / 100.0)
        kf["band_hi"].append(math.exp(l + 2 * sd) / 100.0)
        for k in ["v_hat", "T", "K0", "K1", "ER", "epsbar", "g_Q"]:
            kf[k].append(ev[k])
    kf["ER_smooth"] = _rolling_mean(kf["ER"], ER_SMOOTH_WINDOW)
    full_kf_t = np.array(kf["t"])
    full_kf_v = np.array(kf["v_hat"])
    full_kf_mid = list(kf["mid"])
    kf_keys = ["t", "mid", "level", "band_lo", "band_hi", "v_hat", "T", "K0", "K1",
               "ER", "ER_smooth", "epsbar", "g_Q"]
    kf_ds = downsample_columns({k: kf[k] for k in kf_keys}, "level", MAX_AGENT_POINTS)

    caution = defaultdict(list)
    for t_ns, _, ev in _events(agent, "CAUTION_UPDATE"):
        t = clock.s(t_ns)
        if not clock.in_session(t):
            continue
        caution["t"].append(t)
        caution["C"].append(ev["C_t"])
        caution["E"].append(ev["E_t"] / 100.0)
    caution = downsample_columns({k: caution[k] for k in ["t", "C", "E"]}, "C", MAX_AGENT_POINTS)

    states = []
    for t_ns, _, ev in _events(agent, "MOM_STATE"):
        states.append({
            "t": _t(clock.s(t_ns)),
            "from": ev.get("from"),
            "to": ev["to"],
            "reason": ev["reason"],
            "L": _price(ev.get("L")),
            "extreme": _price(ev.get("peak_or_trough")),
        })

    # decisions: counts over every cycle, series downsampled
    counts = {"order": 0, **{r: 0 for r in SKIP_REASONS}}
    dec = defaultdict(list)
    ht = np.array(d["holdings"]["t"])
    present_optional = set()
    for i, (t_ns, _, ev) in enumerate(_events(agent, "MOM_DECISION")):
        t = clock.s(t_ns)
        if ev.get("qty") is not None:
            counts["order"] += 1
        elif ev.get("skipped_reason") in counts:
            counts[ev["skipped_reason"]] += 1
        if not clock.in_session(t):
            continue
        # MOM_DECISION and MOM_KF_UPDATE are logged in pairs at the same time
        mid = full_kf_mid[i] if i < len(full_kf_mid) else value_at(t, full_kf_t, np.array(full_kf_mid))
        j = max(0, int(np.searchsorted(ht, t, side="right")) - 1)
        n = int(ev["n"])
        wealth = d["holdings"]["cash"][j] + n * mid
        dec["t"].append(t)
        for k in ["a", "s", "m", "g", "e_target"]:
            dec[k].append(ev[k])
        dec["exposure"].append(n * mid / wealth if wealth > 0 else 0.0)
        for k in OPTIONAL_DECISION_FIELDS:
            if k in ev:
                present_optional.add(k)
            dec[k].append(ev.get(k))
    dec_keys = ["t", "a", "s", "m", "g", "e_target", "exposure"] + sorted(present_optional)
    dec_ds = downsample_columns({k: dec[k] for k in dec_keys}, "e_target", MAX_AGENT_POINTS)
    series = {"t": [_t(x) for x in dec_ds["t"]]}
    for k in dec_keys[1:]:
        series[k] = [_sig(None if x is None else float(x)) for x in dec_ds[k]]

    news = []
    for t_ns, _, ev in _events(agent, "NEWS_RECEIVED"):
        news.append({
            "t": _t(clock.s(t_ns)),
            "headline": ev["headline"],
            "sentiment": float(ev["sentiment"]),
            "v_hat_after": _sig(ev["v_hat_new"]),
        })

    d.update(
        kind="momentum",
        warmup_end_t=warmup_end_t,
        thresholds={"theta_in": float(agent.theta_in), "theta_out": float(agent.theta_out)},
        kf={
            "t": [_t(x) for x in kf_ds["t"]],
            **{k: [round(x, 4) for x in kf_ds[k]] for k in ["mid", "level", "band_lo", "band_hi"]},
            **{k: [_sig(x) for x in kf_ds[k]] for k in ["v_hat", "T", "K0", "K1", "ER", "ER_smooth", "epsbar", "g_Q"]},
        },
        caution={"t": [_t(x) for x in caution["t"]], "C": [_sig(x) for x in caution["C"]],
                 "E": [_sig(x) for x in caution["E"]]},
        states=states,
        decisions={"counts": counts, "series": series},
        news=news,
    )
    # kept for news reactions (removed before validation)
    d["_kf_full"] = (full_kf_t, full_kf_v)
    return d


# ── news ──────────────────────────────────────────────────────────────────


def _news(news_agent, clock: _Clock, q_t: np.ndarray, q_mid: np.ndarray, fund: List, mom: List, agents_by_id) -> List[Dict]:
    broadcasts = [(clock.s(t_ns), ev) for t_ns, _, ev in _events(news_agent, "NEWS_BROADCAST")] if news_agent else []
    records = []
    for k, (t, ev) in enumerate(broadcasts):
        t_next = broadcasts[k + 1][0] if k + 1 < len(broadcasts) else float("inf")
        p0 = value_at(t, q_t, q_mid)

        def after(h):
            return round(value_at(t + h, q_t, q_mid), 4) if t + h <= clock.duration and p0 is not None else None

        reactions = []
        for a in fund:
            for nev in a["news"]:
                if t <= nev["t"] < t_next and nev["headline"] == ev["headline"]:
                    before, aft = nev["x_hat_before"], nev["x_hat_after"]
                    reactions.append({
                        "agent_id": a["id"], "kind": "fundamental", "before": before, "after": aft,
                        "change_pct": _sig(100.0 * (aft / before - 1.0)) if before else None,
                    })
        for a in mom:
            kf_t, kf_v = a["_kf_full"]
            for nev in a["news"]:
                if t <= nev["t"] < t_next and nev["headline"] == ev["headline"]:
                    before = value_at(nev["t"] - 1e-9, kf_t, kf_v)
                    # percent change of a velocity is meaningless (it can
                    # change sign), so change_pct is null for momentum agents
                    reactions.append({
                        "agent_id": a["id"], "kind": "momentum",
                        "before": _sig(before), "after": nev["v_hat_after"], "change_pct": None,
                    })

        lo, hi, step = EVENT_WINDOW
        rel_t, rel_bps = [], []
        if p0:
            for r in range(lo, hi + 1, step):
                tt = t + r
                if 0.0 <= tt <= clock.duration:
                    m = value_at(tt, q_t, q_mid)
                    if m is not None:
                        rel_t.append(float(r))
                        rel_bps.append(round((m / p0 - 1.0) * 1e4, 3))

        records.append({
            "t": _t(t),
            "headline": ev["headline"],
            "sentiment": float(ev["sentiment"]),
            "price_before": None if p0 is None else round(p0, 4),
            "price_after": {"1m": after(60), "5m": after(300), "30m": after(1800)},
            "reactions": reactions,
            "event_window": {"t_rel": rel_t, "mid_rel_bps": rel_bps},
        })
    return records


# ── market population (spec v1.1 D4) ──────────────────────────────────────

# class name -> display label, in display order
POPULATION_LABELS = {
    "NoiseAgent": "Noise",
    "ValueAgent": "Value",
    "AdaptiveMarketMakerAgent": "Market maker",
    "MomentumAgent": "Momentum (ABIDES MA)",
    "FundamentalistAgent": "Fundamentalist (ours)",
    "MomentumEKFAgent": "Momentum EKF (ours)",
    # spec v1.3 §6.2: a test instrument of the realism lab, listed separately
    "ImpactProbeAgent": "Impact probe (test)",
}
POPULATION_EXCLUDE = {"ExchangeAgent", "NewsOracleAgent"}


def _wake_desc(cls: str, members: List) -> str:
    a = members[0]

    def periodic(freq_ns, poisson) -> str:
        return f"{'Poisson, mean' if poisson else 'every'} {int(freq_ns) / 1e9:.0f} s"

    if cls == "NoiseAgent":
        return "once per day"
    if cls == "ValueAgent":
        return f"Poisson, mean ~{1.0 / a.lambda_a / 1e9:.0f} s"
    if cls == "MomentumEKFAgent":
        lo, hi = min(m.wake_mean for m in members), max(m.wake_mean for m in members)
        return f"Poisson, mean {lo:.0f}–{hi:.0f} s" if round(lo) != round(hi) else f"Poisson, mean {lo:.0f} s"
    if hasattr(a, "wake_up_freq"):
        return periodic(a.wake_up_freq, getattr(a, "poisson_arrival", False))
    return "—"


def _start_position(agent):
    """(cash, shares) at the start in cents. Our agents hold an endowment of
    floor(e0 * W0 / p_ref) shares bought at p_ref; ABIDES agents hold cash."""
    w0 = int(agent.starting_cash)
    if hasattr(agent, "initial_exposure") and hasattr(agent, "reference_price"):
        n0 = int(math.floor(agent.initial_exposure * w0 / agent.reference_price))
        return w0 - n0 * agent.reference_price, n0
    if hasattr(agent, "starting_shares"):  # the impact probe (spec v1.3 §6.2)
        return w0, int(agent.starting_shares)
    return w0, 0


def _fund_label(members) -> str:
    """spec v1.4 §6.4: "Fundamentalist (informed)" when the run uses informed mode."""
    modes = {getattr(a, "mode", "price_only") for a in members}
    if modes == {"informed"}:
        return "Fundamentalist (informed)"
    if modes == {"price_only"}:
        return "Fundamentalist (price-only)"
    return "Fundamentalist (ours)"


def population(agents, history, close: float, ticker: str = "ABM") -> List[Dict]:
    """One row per agent class present. close in $.

    orders_sent counts distinct order ids per class: LIMIT entries (orders
    that rested in the book) plus the aggressor order of EXEC entries
    (marketable orders that filled on arrival never produce a LIMIT entry).
    shares_traded counts both sides of every EXEC."""
    groups: Dict[str, List] = defaultdict(list)
    for a in agents:
        cls = type(a).__name__
        if cls not in POPULATION_EXCLUDE:
            groups[cls].append(a)
    cls_of = {a.id: type(a).__name__ for a in agents}

    order_ids: Dict[str, set] = defaultdict(set)
    traded: Dict[str, int] = defaultdict(int)
    total_exec = 0
    for h in history:
        typ = h.get("type")
        if typ == "LIMIT":
            order_ids[cls_of.get(h["agent_id"], "")].add(h["order_id"])
        elif typ == "EXEC":
            q = int(h["quantity"])
            total_exec += q
            traded[cls_of.get(h["agent_id"], "")] += q
            traded[cls_of.get(h["oppos_agent_id"], "")] += q
            order_ids[cls_of.get(h["oppos_agent_id"], "")].add(h["oppos_order_id"])

    close_c = close * 100.0
    order = list(POPULATION_LABELS) + sorted(c for c in groups if c not in POPULATION_LABELS)
    rows = []
    for cls in order:
        members = groups.get(cls)
        if not members:
            continue
        starts = [_start_position(a) for a in members]
        final_value = sum(a.holdings.get("CASH", 0) + a.holdings.get(ticker, 0) * close_c for a in members)
        start_wealth = sum(a.starting_cash for a in members)
        hold_value = sum(c + n * close_c for c, n in starts)
        cash_each = [c / 100.0 for c, _ in starts]
        rows.append({
            "label": _fund_label(members) if cls == "FundamentalistAgent" else POPULATION_LABELS.get(cls, cls),
            "class_name": cls,
            "count": len(members),
            "starting_cash_each": {"min": round(min(cash_each), 2), "max": round(max(cash_each), 2)},
            "starting_shares_total": int(sum(n for _, n in starts)),
            "wake_desc": _wake_desc(cls, members),
            "orders_sent": len(order_ids.get(cls, ())),
            "shares_traded": int(traded.get(cls, 0)),
            "volume_share_pct": round(100.0 * traded.get(cls, 0) / (2 * total_exec), 4) if total_exec else 0.0,
            "final_value_total": round(final_value / 100.0, 2),
            "pnl_total": round((final_value - start_wealth) / 100.0, 2),
            "pnl_vs_hold_total": round((final_value - hold_value) / 100.0, 2),
        })
    return rows


# ── entry point ───────────────────────────────────────────────────────────


def build_payload(
    end_state: Dict[str, Any],
    config: Dict[str, Any],
    params: RunParams,
    run_id: str,
    engine_version: str,
    wall_time_s: float,
    ticker: str = "ABM",
    created_at: Optional[str] = None,
) -> Dict:
    agents = end_state["agents"]
    exchange = agents[0]
    ob = exchange.order_books[ticker]
    clock = _Clock(config["_mkt_open_ns"], config["_mkt_close_ns"])

    # ── quotes (full resolution) ──────────────────────────────────────────
    q_t, q_bid_c, q_ask_c, snaps = _book_snapshots(ob, clock)
    if len(q_t) == 0:
        raise RuntimeError("order book log is empty: was book_logging enabled?")
    q_bid, q_ask = q_bid_c / 100.0, q_ask_c / 100.0
    q_mid = (q_bid + q_ask) / 2.0

    execs = [h for h in ob.history if h.get("type") == "EXEC"]
    exec_t = np.array([clock.s(h["time"]) for h in execs], dtype=float)
    exec_q = np.array([h["quantity"] for h in execs], dtype=float)
    in_sess = (exec_t >= 0) & (exec_t <= clock.duration)
    candles = _candles(q_t, q_mid, exec_t[in_sess], exec_q[in_sess], clock.duration)

    oracle = exchange.kernel.oracle
    f_log = oracle.f_log.get(ticker, [])
    o_t = np.array([clock.s(e["FundamentalTime"]) for e in f_log], dtype=float)
    o_v = np.array([e["FundamentalValue"] / 100.0 for e in f_log], dtype=float)
    o_mask = (o_t >= 0) & (o_t <= clock.duration)
    o_t, o_v = o_t[o_mask], o_v[o_mask]

    g_t, g_v = gap_series(q_t, q_mid, o_t, o_v, clock.duration)
    stats = market_stats(
        q_t, q_bid, q_ask, q_mid, np.array(candles["c"]), o_t, o_v,
        trades=len(execs), volume_shares=int(exec_q.sum()), gap=g_v,
    )
    close = stats["close"]
    g_idx = lttb_indices(g_t, g_v, MAX_GAP) if len(g_t) else []

    q_idx = lttb_indices(q_t, q_mid, MAX_QUOTES)
    o_idx = lttb_indices(o_t, o_v, MAX_ORACLE)

    market = {
        "quotes": {
            "t": [_t(q_t[i]) for i in q_idx],
            "bid": [round(float(q_bid[i]), 4) for i in q_idx],
            "ask": [round(float(q_ask[i]), 4) for i in q_idx],
            "mid": [round(float(q_mid[i]), 4) for i in q_idx],
        },
        "candles_1m": {
            **{k: candles[k] for k in ["t", "volume", "trades"]},
            **{k: [round(x, 4) for x in candles[k]] for k in ["o", "h", "l", "c"]},
        },
        "oracle": {"t": [_t(o_t[i]) for i in o_idx], "v": [round(float(o_v[i]), 4) for i in o_idx]},
        "depth": _depth(snaps, q_t, clock.duration),
        "totals": {"price_points": int(len(q_t)), "trades": len(execs), "volume_shares": int(exec_q.sum())},
        "gap": {"t": [_t(g_t[i]) for i in g_idx], "v": [round(float(g_v[i]), 4) for i in g_idx]},
    }

    # ── agents ────────────────────────────────────────────────────────────
    fund_ids = list(config.get("_ekf_agent_ids", []))
    detail_ids = set(fund_detail_ids(fund_ids))
    fund = [_fundamental(agents[i], clock, ticker, candles, close, detail=i in detail_ids) for i in fund_ids]
    detail_note = (None if len(detail_ids) == len(fund_ids) else
                   f"Detailed series are stored for {len(detail_ids)} of {len(fund_ids)} fundamentalists "
                   f"(evenly spaced ids); every agent is in the leaderboard and the population table.")
    mom = [_momentum(agents[i], clock, ticker, candles, close) for i in config.get("_mom_ekf_agent_ids", [])]
    news_agent = agents[config["_news_oracle_id"]] if "_news_oracle_id" in config else None
    news = _news(news_agent, clock, q_t, q_mid, fund, mom, None)
    for a in mom:
        del a["_kf_full"]

    stats_rounded = _round_tree(stats)

    # ── realism (spec v1.3 §9.1): the lab's metrics on this single run ────
    r_series = realism.series_from_end_state(end_state, config, ticker)
    r_metrics = realism.run_metrics(r_series)
    realism_block = {
        "bands": realism.BANDS,
        "metrics": _round_tree(r_metrics),
        "grades": realism.grade_run(r_metrics),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "run_id": run_id,
            "params": params.model_dump(),
            "engine_version": engine_version,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "wall_time_s": round(float(wall_time_s), 2),
            "ticker": ticker,
            "session": {"open": "09:30:00", "close": params.end_time, "duration_s": clock.duration},
            "agent_counts": dict(Counter(a.type for a in agents)),
        },
        "market": market,
        "stats": stats_rounded,
        "news": news,
        "agents": {"fundamental": fund, "momentum": mom},
        "population": population(agents, ob.history, close),
        "hyperparam_ranges": ranges_for_export(config.get("_informed_design")),
        "agents_detail_note": detail_note,
        "realism": realism_block,
        "oracle_events": _round_tree(r_series["oracle_events"]),
    }
    SimPayload.model_validate(payload)
    return payload


def _round_tree(x):
    """Round every float in a nested structure to 8 significant figures.

    8, not 6: prices near $1000 need 7 digits to keep half-cent mids
    ($1000.705 rounded to 6 figures is $1000.71)."""
    if isinstance(x, dict):
        return {k: _round_tree(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round_tree(v) for v in x]
    if isinstance(x, float):
        return _sig(x, 8)
    return x

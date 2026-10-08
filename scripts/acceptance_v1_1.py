"""Full-run acceptance for FinVerse spec v1.1 (section 6.3).

    python scripts/acceptance_v1_1.py                 # runs A and B, 16:00
    python scripts/acceptance_v1_1.py --end 11:00:00  # shorter smoke run
    python scripts/acceptance_v1_1.py --runs A

Run A: seed 42, 20 fundamentalists, 12 momentum EKF, no news.
Run B: as A plus "Company announces record quarterly earnings" (+0.9) at 00:10:00.

Prints every acceptance number with its target and PASS/MISS. Numbers are
reported as measured; nothing is tuned here. Writes a JSON summary next to
the kernel log directory (runs/_acceptance/).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api.jobs import build_run_config  # noqa: E402
from api.schema import RunParams  # noqa: E402

NEWS = {"offset": "00:10:00", "headline": "Company announces record quarterly earnings", "sentiment": 0.9}
NEWS_EXCLUDE_S = 300.0
REVERSAL_LOOKS = 3


def run(name: str, end: str, seed: int):
    from abides_core import abides

    params = RunParams(seed=seed, end_time=end, num_fund=20, num_mom=12,
                       news=[NEWS] if name == "B" else [])
    out_dir = REPO / "runs" / "_acceptance"
    out_dir.mkdir(parents=True, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(out_dir)
    try:
        config = build_run_config(params)
        t0 = time.time()
        end_state = abides.run(config)
        wall = time.time() - t0
    finally:
        os.chdir(cwd)
    return params, config, end_state, wall


def _events(agent, typ):
    return [(t, ev) for t, ty, ev in agent.log if ty == typ]


def _check(label, value, ok, target):
    flag = "PASS" if ok else "MISS"
    print(f"  [{flag}] {label}: {value}   (target {target})")
    return {"label": label, "value": value, "target": target, "pass": bool(ok)}


def fundamentalist_report(config, agents, open_ns, close_ns, news_ns):
    ids = config["_ekf_agent_ids"]
    rows, checks = [], []
    close_mid = None
    for i in ids:
        a = agents[i]
        upd = _events(a, "EKF_UPDATE")
        t = np.array([u[0] for u in upd], dtype=float)
        mid = np.array([u[1]["mid"] for u in upd])
        xh = np.array([u[1]["x_hat"] for u in upd])
        K = np.array([u[1]["K"] for u in upd])
        gap = np.abs(xh - mid) / 100.0
        keep = np.ones_like(t, dtype=bool)
        for tn in news_ns:
            keep &= ~((t >= tn) & (t < tn + NEWS_EXCLUDE_S * 1e9))
        last_hour = t >= close_ns - 3600e9
        close_mid = mid[-1]
        cash, sh = a.holdings.get("CASH", 0), a.holdings.get("ABM", 0)
        W = cash + sh * mid[-1]
        shifts = [ev["shift"] / 100.0 for _, ev in _events(a, "NEWS_RECEIVED")]
        dec = [ev for _, ev in _events(a, "FUND_DECISION")]
        rows.append({
            "id": i,
            "median_abs_gap": float(np.median(gap)),
            "max_abs_gap_ex_news": float(np.max(gap[keep])),
            "median_K_last_hour": float(np.median(K[last_hour])) if last_hour.any() else None,
            "K_close": float(K[-1]),
            "sqrtP_close": float(np.sqrt(upd[-1][1]["P"])) / 100.0,
            "sigma_f2_close": float(upd[-1][1]["sigma_f2"]),
            "x_hat_close": float(xh[-1]) / 100.0,
            "x_hat_min": float(xh.min()) / 100.0,
            "x_hat_max": float(xh.max()) / 100.0,
            "shares_close": int(sh),
            "stock_frac_close": float(sh * mid[-1] / W),
            "orders": sum(1 for d in dec if d["d"] != 0),
            "news_shift": shifts,
            "q": a.q, "delta": a.delta, "lambda_er": a.lambda_er,
        })

    print(f"\nFundamentalists ({len(ids)})")
    print(f"  {'id':>5} {'med|gap|$':>9} {'max|gap|$':>9} {'K_last_h':>8} {'K_close':>8} "
          f"{'sqrtP$':>7} {'sf2':>6} {'xhat_lo':>8} {'xhat_hi':>8} {'shares':>6} {'stock%':>6} {'orders':>6}")
    for r in rows:
        print(f"  {r['id']:>5} {r['median_abs_gap']:>9.3f} {r['max_abs_gap_ex_news']:>9.3f} "
              f"{(r['median_K_last_hour'] or 0):>8.4f} {r['K_close']:>8.4f} {r['sqrtP_close']:>7.3f} "
              f"{r['sigma_f2_close']:>6.2f} {r['x_hat_min']:>8.2f} {r['x_hat_max']:>8.2f} "
              f"{r['shares_close']:>6} {100 * r['stock_frac_close']:>6.1f} {r['orders']:>6}")

    med_gap = float(np.median([r["median_abs_gap"] for r in rows]))
    max_gap = float(max(r["max_abs_gap_ex_news"] for r in rows))
    k_last = [r["median_K_last_hour"] for r in rows if r["median_K_last_hour"] is not None]
    med_K = float(np.median(k_last)) if k_last else float("nan")
    n_zero = sum(1 for r in rows if r["shares_close"] == 0)
    n_high = sum(1 for r in rows if r["stock_frac_close"] > 0.95)
    checks.append(_check("median over agents of median |x_hat - mid| ($)", round(med_gap, 3), med_gap < 1.0, "< 1.00"))
    checks.append(_check("max |x_hat - mid| excl. 5 min after news ($)", round(max_gap, 3), max_gap < 5.0, "< 5"))
    checks.append(_check("median K over the last hour", round(med_K, 4), med_K > 0.003, "> 0.003"))
    checks.append(_check("agents ending at 0 shares", n_zero, n_zero <= 2, "<= 2 of 20"))
    checks.append(_check("agents ending above 95% stock", n_high, n_high <= 2, "<= 2 of 20"))
    if news_ns:
        shifts = [abs(s) for r in rows for s in r["news_shift"]]
        med_shift = float(np.median(shifts)) if shifts else float("nan")
        checks.append(_check("median news shift ($)", round(med_shift, 3), 0.30 <= med_shift <= 4.0, "0.30-4.00"))
    return rows, checks


def momentum_report(config, agents):
    ids = config["_mom_ekf_agent_ids"]
    rows, checks = [], []
    g_trend = []
    n_reentry = n_reversed = 0
    for i in ids:
        a = agents[i]
        kf = [ev for _, ev in _events(a, "MOM_KF_UPDATE")]
        dec = [ev for _, ev in _events(a, "MOM_DECISION")]
        T = np.array([ev["T"] for ev in kf]) if kf else np.array([0.0])
        reached = bool(np.any(np.abs(T) >= a.theta_in))
        states = [ev["state"] for ev in dec]
        g_trend += [ev["g"] for ev in dec if ev["state"] in ("BULL", "BEAR")]
        # re-entries: a decision whose state flipped WATCH -> BULL/BEAR by REENTRY
        trans = [(t, ev) for t, ev in _events(a, "MOM_STATE")]
        dec_t = [t for t, _ in _events(a, "MOM_DECISION")]
        for t_tr, ev in trans:
            if ev["reason"] != "REENTRY":
                continue
            n_reentry += 1
            k = dec_t.index(t_tr) if t_tr in dec_t else None
            if k is None:
                continue
            window = states[k + 1:k + 1 + REVERSAL_LOOKS]
            if any(s != ev["to"] for s in window):
                n_reversed += 1
        counts = {s: states.count(s) for s in ("NEUTRAL", "BULL", "BEAR", "WATCH")}
        entries = [ev for _, ev in trans if ev["to"] in ("BULL", "BEAR")]
        rows.append({
            "id": i, "tau": a.tau, "tau_ratio": getattr(a, "tau_ratio", None), "wake_mean": a.wake_mean,
            "theta_in": a.theta_in, "max_abs_T": float(np.max(np.abs(T))), "reached_theta_in": reached,
            "entries": len(entries),
            "breakouts": sum(1 for e in entries if e["reason"] == "BREAKOUT"),
            "reentries": sum(1 for e in entries if e["reason"] == "REENTRY"),
            "stops": sum(1 for _, e in trans if e["reason"] == "STOP"),
            "state_counts": counts,
            "orders": sum(1 for d in dec if d.get("qty")),
            "shares_close": int(a.holdings.get("ABM", 0)),
        })

    print(f"\nMomentum EKF ({len(ids)})")
    print(f"  {'id':>5} {'tau_s':>7} {'ratio':>6} {'wake':>5} {'max|T|':>7} {'th_in':>5} {'entr':>4} "
          f"{'re':>3} {'stop':>4} {'orders':>6} {'shares':>6}  states(N/BU/BE/W)")
    for r in rows:
        c = r["state_counts"]
        print(f"  {r['id']:>5} {r['tau']:>7.0f} {(r['tau_ratio'] or 0):>6.1f} {r['wake_mean']:>5.0f} "
              f"{r['max_abs_T']:>7.2f} {r['theta_in']:>5.2f} {r['entries']:>4} {r['reentries']:>3} "
              f"{r['stops']:>4} {r['orders']:>6} {r['shares_close']:>6}  "
              f"{c['NEUTRAL']}/{c['BULL']}/{c['BEAR']}/{c['WATCH']}")

    n_reach = sum(r["reached_theta_in"] for r in rows)
    frac_rev = n_reversed / n_reentry if n_reentry else 0.0
    med_g = float(np.median(g_trend)) if g_trend else float("nan")
    checks.append(_check("agents reaching |T| >= theta_in", n_reach, n_reach >= 6, ">= 6 of 12"))
    checks.append(_check(f"re-entries reversed within {REVERSAL_LOOKS} looks",
                         f"{n_reversed}/{n_reentry} = {100 * frac_rev:.0f}%", frac_rev <= 0.25, "<= 25%"))
    checks.append(_check("median g during BULL/BEAR", round(med_g, 3) if g_trend else "n/a (no trend states)",
                         bool(g_trend) and med_g >= 0.7, ">= 0.7"))
    return rows, checks


def market_report(agents, open_ns, close_ns):
    ex = agents[0]
    ob = ex.order_books["ABM"]
    ts, mids = [], []
    for row in ob.book_log2:
        if len(row["bids"]) and len(row["asks"]) and open_ns <= row["QuoteTime"] <= close_ns:
            ts.append(row["QuoteTime"])
            mids.append((row["bids"][0][0] + row["asks"][0][0]) / 2.0)
    f_log = ex.kernel.oracle.f_log["ABM"]
    o_t = np.array([e["FundamentalTime"] for e in f_log], dtype=float)
    o_v = np.array([e["FundamentalValue"] for e in f_log], dtype=float)
    grid = np.arange(open_ns, close_ns, 1e9)
    m = np.interp(grid, np.array(ts, dtype=float), np.array(mids))
    o = np.interp(grid, o_t, o_v)
    gap = (m - o) / 100.0
    try:
        from api.stats import gap_half_life
        hl = gap_half_life(gap)["half_life_min"]
    except ImportError:  # before V5
        hl = None
    out = {"corr_mid_oracle": float(np.corrcoef(m, o)[0, 1]), "gap_std": float(np.std(gap)),
           "mean_abs_gap": float(np.mean(np.abs(gap))), "half_life_min": hl,
           "close": float(m[-1]) / 100.0, "low": float(m.min()) / 100.0, "high": float(m.max()) / 100.0}
    print("\nMarket sanity (no target)")
    for k, v in out.items():
        print(f"  {k}: {v if v is None else round(v, 4)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="16:00:00")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--runs", default="AB")
    args = ap.parse_args(argv)

    summary = {}
    for name in args.runs:
        params, config, end_state, wall = run(name, args.end, args.seed)
        agents = end_state["agents"]
        open_ns, close_ns = config["_mkt_open_ns"], config["_mkt_close_ns"]
        news_ns = [open_ns + 600e9] if name == "B" else []
        print(f"\n===== Run {name}: seed {args.seed}, end {args.end}, news={'yes' if news_ns else 'no'} "
              f"(simulated in {wall:.0f} s) =====")
        f_rows, f_checks = fundamentalist_report(config, agents, open_ns, close_ns, news_ns)
        m_rows, m_checks = momentum_report(config, agents)
        mk = market_report(agents, open_ns, close_ns)
        summary[name] = {"fundamental": f_rows, "momentum": m_rows, "market": mk,
                         "checks": f_checks + m_checks, "wall_s": wall}
    out = REPO / "runs" / "_acceptance" / f"summary_{args.seed}_{args.end.replace(':', '')}.json"
    out.write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    print(f"\nsummary written to {out}")


if __name__ == "__main__":
    main()

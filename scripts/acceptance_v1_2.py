"""Acceptance runs for FinVerse spec v1.2 (section 7.2).

One simulation per invocation, so a slow or stuck run can be capped from outside:

    python scripts/acceptance_v1_2.py --run A        # seed 42, 20 + 12, no news
    python scripts/acceptance_v1_2.py --run B        # A + earnings news (+0.9) at 00:10:00
    python scripts/acceptance_v1_2.py --run C        # A with seed 7
    python scripts/acceptance_v1_2.py --run Z        # A with num_value = 0
    python scripts/acceptance_v1_2.py --report       # table from the saved results

Each run writes runs/_acceptance/v1_2_<RUN>.json. Numbers are reported as measured;
nothing is tuned here.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "runs" / "_acceptance"
TICKER = "ABM"
NEWS = {"offset": "00:10:00", "headline": "Company announces record quarterly earnings", "sentiment": 0.9}
RUNS = {
    "A": dict(seed=42),
    "B": dict(seed=42, news=[NEWS]),
    "C": dict(seed=7),
    "Z": dict(seed=42, num_value=0),
}
NEWS_EXCLUDE_S = 300.0
GRID_S = 10.0


def simulate(name: str) -> dict:
    from abides_core import abides
    from api.export import build_payload
    from api.jobs import build_run_config
    from api.schema import RunParams

    params = RunParams(end_time="16:00:00", num_fund=20, num_mom=12, **RUNS[name])
    config = build_run_config(params)
    start = {
        a.id: (int(a.holdings.get("CASH", 0)), int(a.holdings.get(TICKER, 0)))
        for a in config["agents"] if hasattr(a, "holdings")
    }
    mm_wakes = {}
    for a in config["agents"]:
        if type(a).__name__ == "AdaptiveMarketMakerAgent":
            mm_wakes[a.id] = []
            orig = a.wakeup

            def counted(t, _id=a.id, _orig=orig):
                mm_wakes[_id].append(t)
                return _orig(t)

            a.wakeup = counted

    OUT.mkdir(parents=True, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(OUT)
    try:
        t0 = time.time()
        end_state = abides.run(config)
        wall = time.time() - t0
    finally:
        os.chdir(cwd)

    payload = build_payload(end_state, config, params, f"acceptance-{name}", "v1.2", wall, TICKER)
    agents = end_state["agents"]
    open_ns, close_ns = config["_mkt_open_ns"], config["_mkt_close_ns"]
    close_c = payload["stats"]["close"] * 100.0
    oracle = config["custom_properties"]["oracle"]
    _, path_v = oracle.path(TICKER)

    # ── P&L vs holding by group, at the closing mid (sums to 0 exactly) ──
    groups = {}
    for a in agents:
        if a.id not in start:
            continue
        c0, n0 = start[a.id]
        c1, n1 = int(a.holdings.get("CASH", 0)), int(a.holdings.get(TICKER, 0))
        vs_hold = (c1 + n1 * close_c) - (c0 + n0 * close_c)
        pnl = (c1 + n1 * close_c) - a.starting_cash
        g = groups.setdefault(type(a).__name__, {"n": 0, "vs_hold": [], "pnl": []})
        g["n"] += 1
        g["vs_hold"].append(vs_hold / 100.0)
        g["pnl"].append(pnl / 100.0)
    group_rows = {k: {"n": v["n"], "vs_hold_total": sum(v["vs_hold"]), "vs_hold_median": float(np.median(v["vs_hold"])),
                      "pnl_total": sum(v["pnl"]), "per_agent_vs_hold": v["vs_hold"]} for k, v in groups.items()}
    vs_hold_sum = sum(v["vs_hold_total"] for v in group_rows.values())

    # ── fundamentalists ──────────────────────────────────────────────────
    grid = np.arange(open_ns, close_ns, GRID_S * 1e9)
    news_ns = [open_ns + 600e9] if name == "B" else []
    fund = []
    pooled = []
    for i in config["_ekf_agent_ids"]:
        a = agents[i]
        traded = sum(int(e["quantity"]) for _, ty, e in a.log if ty == "ORDER_EXECUTED")
        ht, hs = [], []
        for t, ty, e in a.log:
            if ty == "HOLDINGS_UPDATED":
                ht.append(max(t, open_ns))
                hs.append(int(e.get(TICKER, 0)))
        idx = np.searchsorted(np.array(ht), grid, side="right") - 1
        held = np.array(hs)[np.clip(idx, 0, None)]
        pooled.append(held)
        upd = [(t, e) for t, ty, e in a.log if ty == "EKF_UPDATE"]
        ut = np.array([t for t, _ in upd], dtype=float)
        gap = np.array([abs(e["x_hat"] - e["mid"]) for _, e in upd]) / 100.0
        K = np.array([e["K"] for _, e in upd])
        keep = np.ones_like(ut, dtype=bool)
        for tn in news_ns:
            keep &= ~((ut >= tn) & (ut < tn + NEWS_EXCLUDE_S * 1e9))
        last_h = ut >= close_ns - 3600e9
        fund.append({
            "id": i, "traded": traded,
            "frac_at_0": float(np.mean(held == 0)), "frac_at_100": float(np.mean(held >= 100)),
            "median_abs_gap": float(np.median(gap)), "max_abs_gap_ex_news": float(np.max(gap[keep])),
            "median_K_last_hour": float(np.median(K[last_h])) if last_h.any() else None,
            "shares_close": int(a.holdings.get(TICKER, 0)),
            "news_shift": [e["shift"] / 100.0 for _, ty, e in a.log if ty == "NEWS_RECEIVED"],
        })
    pooled = np.concatenate(pooled) if pooled else np.array([0])

    # ── market makers ────────────────────────────────────────────────────
    mms = []
    for a in agents:
        if type(a).__name__ != "AdaptiveMarketMakerAgent":
            continue
        w = np.array([t for t in mm_wakes[a.id] if open_ns <= t <= close_ns])
        gaps = np.diff(np.concatenate([[open_ns], w, [close_ns]])) / 1e9
        c0, n0 = start[a.id]
        mms.append({
            "id": a.id, "wakes": int(len(w)), "expected_wakes": (close_ns - open_ns) / float(a.wake_up_freq),
            "max_silence_s": float(gaps.max()),
            "cold_starts": sum(1 for _, ty, _ in a.log if ty == "MM_COLD_START"),
            "spread_cap_hits": int(a.spread_cap_hits),
            "pnl": ((a.holdings.get("CASH", 0) + a.holdings.get(TICKER, 0) * close_c) - a.starting_cash) / 100.0,
            "final_shares": int(a.holdings.get(TICKER, 0)), "final_cash": a.holdings.get("CASH", 0) / 100.0,
        })

    st = payload["stats"]
    r = st["returns_1m"]
    size = len(json.dumps(payload, separators=(",", ":")))
    execs = [h for h in agents[0].order_books[TICKER].history if h.get("type") == "EXEC"]
    return {
        "run": name, "params": params.model_dump(), "wall_s": wall,
        "oracle_sha256": hashlib.sha256(np.ascontiguousarray(path_v).tobytes()).hexdigest(),
        "trades": len(execs),
        "market": {
            "open": st["open"], "close": st["close"], "low": st["low"], "high": st["high"],
            "spread_mean_c": st["spread"]["mean"] * 100, "spread_median_c": st["spread"]["median"] * 100,
            "spread_p95_c": st["spread"]["p95"] * 100, "spread_max_c": st["spread"]["max"] * 100,
            "ret1m_std_bps": r["std"] * 1e4, "ret1m_acf1": r["acf"][0] if r["acf"] else None,
            "ret1m_abs_acf1": r["acf_abs"][0] if r["acf_abs"] else None,
            "ret1m_excess_kurtosis": r["excess_kurtosis"],
            "gap_std": st["gap"]["std"], "gap_mean_abs": st["gap"]["mean_abs"], "gap_half_life_min": st["gap"]["half_life_min"],
            "corr_mid_oracle": st["tracking"]["corr"],
        },
        "payload_bytes": size,
        "groups": group_rows, "vs_hold_sum": vs_hold_sum,
        "fund": fund,
        "fund_holdings_p10_p90": [float(np.percentile(pooled, 10)), float(np.percentile(pooled, 90))],
        "mm": mms,
    }


def check(label, value, ok, target):
    flag = "PASS" if ok else "MISS"
    print(f"  [{flag}] {label}: {value}   (target {target})")
    return ok


def report():
    res = {n: json.loads((OUT / f"v1_2_{n}.json").read_text()) for n in RUNS if (OUT / f"v1_2_{n}.json").exists()}
    for n, d in res.items():
        m = d["market"]
        print(f"\n===== Run {n} (seed {d['params']['seed']}, value agents {d['params']['num_value']}, "
              f"news {len(d['params']['news'])}) simulated in {d['wall_s']:.0f} s =====")
        print(f"  trades {d['trades']}, close ${m['close']:.2f} (range ${m['low']:.2f}-${m['high']:.2f}), payload {d['payload_bytes'] / 1e6:.2f} MB")
        print(f"  1-min returns: std {m['ret1m_std_bps']:.2f} bps, lag-1 ACF {m['ret1m_acf1']:.3f}, |r| ACF1 {m['ret1m_abs_acf1']:.3f}, excess kurtosis {m['ret1m_excess_kurtosis']:.2f}")
        hl = m["gap_half_life_min"]
        print(f"  gap: std ${m['gap_std']:.3f}, mean |gap| ${m['gap_mean_abs']:.3f}, half-life {('%.1f min' % hl) if hl else '—'}, corr(mid, value) {m['corr_mid_oracle']:.3f}")
        print(f"  spread: mean {m['spread_mean_c']:.2f}c, median {m['spread_median_c']:.1f}c, p95 {m['spread_p95_c']:.1f}c, max {m['spread_max_c']:.0f}c")
        print("  P&L vs holding by group ($, at the closing mid):")
        for g, v in sorted(d["groups"].items(), key=lambda kv: kv[1]["vs_hold_total"]):
            print(f"    {g:28s} n={v['n']:5d}  total {v['vs_hold_total']:+12.2f}  median/agent {v['vs_hold_median']:+9.2f}")
        check("sum of P&L vs holding over every agent ($)", round(d["vs_hold_sum"], 6), abs(d["vs_hold_sum"]) < 1e-6, "= 0")
        for mm in d["mm"]:
            print(f"  MM {mm['id']}: wakes {mm['wakes']} (expected {mm['expected_wakes']:.0f}), max silence {mm['max_silence_s']:.0f} s, "
                  f"P&L ${mm['pnl']:+,.2f}, final {mm['final_shares']} sh / ${mm['final_cash']:,.0f}, cold starts {mm['cold_starts']}, spread-cap hits {mm['spread_cap_hits']}")
        if n in "ABC":
            f = d["fund"]
            traded = np.median([a["traded"] for a in f])
            p10, p90 = d["fund_holdings_p10_p90"]
            worst = max(max(a["frac_at_0"], a["frac_at_100"]) for a in f)
            med_gap = float(np.median([a["median_abs_gap"] for a in f]))
            max_gap = max(a["max_abs_gap_ex_news"] for a in f)
            med_K = float(np.median([a["median_K_last_hour"] for a in f]))
            print(f"  fundamentalists: shares traded per agent min/median/max {min(a['traded'] for a in f)}/{traded:.0f}/{max(a['traded'] for a in f)}")
            check("median shares traded per agent per day", traded, 100 <= traded <= 400, "[100, 400]")
            check("holdings 10th-90th percentile", f"{p10:.0f}-{p90:.0f}", p10 >= 35 and p90 <= 65, "within [35, 65]")
            check("worst agent's time at 0 or >=100 shares", f"{100 * worst:.2f}%", worst <= 0.01, "<= 1%")
            check("median of per-agent median |x_hat - mid| ($)", round(med_gap, 3), med_gap < 1.0, "< 1.00")
            check("max |x_hat - mid| excl. 5 min after news ($)", round(max_gap, 3), max_gap < 5.0, "< 5")
            check("median K over the last hour", round(med_K, 4), med_K > 0.003, "> 0.003")
            if n == "B":
                shifts = [abs(s) for a in f for s in a["news_shift"]]
                print(f"  news shifts ($): min {min(shifts):.2f}, median {np.median(shifts):.2f}, max {max(shifts):.2f}")
        if n == "Z":
            check("trades", d["trades"], d["trades"] > 0, "> 0")
            alive = all(mm["wakes"] >= 0.9 * mm["expected_wakes"] and mm["max_silence_s"] < 600 for mm in d["mm"])
            check("both MMs active all session (>= 90% of expected wakes, no 10-min silence)", alive, alive and len(d["mm"]) == 2, "yes")
    if "A" in res and "B" in res:
        same = res["A"]["oracle_sha256"] == res["B"]["oracle_sha256"]
        print()
        check("true-value path A == B (sha256 of the float path)", same, same, "identical")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", choices=list(RUNS))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.run:
        d = simulate(args.run)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"v1_2_{args.run}.json").write_text(json.dumps(d, indent=1, default=float))
        print(f"run {args.run}: {d['trades']} trades in {d['wall_s']:.0f} s -> {OUT / f'v1_2_{args.run}.json'}")
    if args.report:
        report()


if __name__ == "__main__":
    main()

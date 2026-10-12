"""Realism-lab campaigns of FinVerse spec v1.4 (R3), Part 7.

Called by scripts/realism_lab.py for --campaign b | s1 | s1r2 (the same
resumable runner: one process per run, 15-minute timeout). Runs go to
runs/_lab_v14/<config>/<seed>/, reports to docs/v1.4/lab/.

    python scripts/realism_lab.py --campaign b  --workers 4   # §7.2, 40 runs
    python scripts/realism_lab.py --campaign s1 --workers 4   # §7.3, 160 runs + §7.4 selection
    python scripts/realism_lab.py --campaign s1r2 --workers 4 # §7.4 round 2 (winner from selection_s1.json)

The selection (§7.4) is mechanical and printed in full (select_design).
"""

import json
import math
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

import realism_lab as RL
from api import lab, realism as R

ROOT = RL.LAB_V14
DOC = RL.DOC_V14
V13 = RL.LAB_DIR

T_MEASURES = [  # (target, label, scope, key) shown in tables and main effects
    ("T1", "ac1", "C", "ac1"),
    ("T2", "VR(5)", "C", "vr5"),
    ("T3", "vol ratio", "C", "vol_ratio_price_value"),
    ("T4", "vv_corr", "C", "vv_corr"),
    ("T5", "vol uplift S2", "S2", "volume_uplift"),
    ("T6", "one-sided S2", "S2", "one_sided_share_jump"),
    ("T6", "spread p95 S2", "S2", "spread_p95_jump_ticks"),
    ("T7", "fund P&L total $", "C", "fund_pnl_total"),
    ("T7", "fund P&L median $", "C", "fund_pnl_median"),
]


def _med(xs) -> Optional[float]:
    x = [float(v) for v in xs if v is not None and math.isfinite(float(v))]
    return float(np.median(x)) if x else None


def _fmt(x, d=3) -> str:
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.{d}g}"


# ══════════════════════════════════════════════════════════════════════════
# per-seed metrics (with v1.4 keys filled in for stored v1.3 runs)
# ══════════════════════════════════════════════════════════════════════════


def _augment_from_series(root: Path, cid: str, seed: int, m: Dict[str, Any]) -> Dict[str, Any]:
    """Runs stored before v1.4 lack the corrected half-life and L3 keys:
    recompute them from series.npz (no simulation)."""
    if "gap_half_life_corr_min" in m and "active_halfhours_share" in m:
        return m
    s = RL.load_series(root, cid, seed)
    if s is None:
        return m
    c = R.gap_half_life_corrected(s["mid_1s"] - s["val_1s"])
    m = dict(m)
    m.update(gap_half_life_read_min=R._f(c["h_read"]), gap_half_life_corr_min=R._f(c["h_corrected"]),
             gap_half_life_corr_above=bool(c["above_table"]), gap_half_life_range=c["h_range"],
             gap_mean=R._f(c["gap_mean"]))
    v = s["vol_1m"]
    win = [v[i:i + 30].sum() for i in range(0, len(v), 30)]
    m["active_halfhours_share"] = float(np.mean([w > 0 for w in win]))
    return m


def runs(root: Path, cid: str, seeds) -> List[Dict[str, Any]]:
    out = []
    for s in seeds:
        r = RL.load_metrics(root, cid, s)
        if r:
            r["metrics"] = _augment_from_series(root, cid, s, r["metrics"])
            out.append(r)
    return out


def c_summary(rows: List[Dict[str, Any]], all_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The "C" scope of the R3 scorecard: medians over seeds of a no-trigger
    config; zero_sum and wall time over every run of the design (all_rows)."""
    ms = [r["metrics"] for r in rows]
    fund = [r["sanity"]["classes"].get("FundamentalistAgent", {}) for r in rows]
    keys = ["ac1", "vr5", "vol_ratio_price_value", "vv_corr", "spread_med_ticks", "spread_p95_ticks",
            "shares_executed", "active_halfhours_share", "sigma_1m_bps", "gap_std", "gap_mean",
            "gap_half_life_read_min", "gap_half_life_corr_min", "gap_half_life_min", "one_sided_share",
            "spread_max_ticks", "cs", "kurt", "regime_contrast"]
    out = {k: _med([m.get(k) for m in ms]) for k in keys}
    out["fund_pnl_total"] = _med([f.get("pnl_vs_hold_total") for f in fund])
    out["fund_pnl_median"] = _med([f.get("pnl_vs_hold_median") for f in fund])
    out["fund_volume_share_pct"] = _med([f.get("volume_share_pct") for f in fund])
    out["zero_sum_all_zero"] = 1.0 if all(r["zero_sum_ok"] and r["zero_sum_cents"] == 0 for r in all_rows) else 0.0
    out["wall_time_s"] = _med([r["wall_time_s"] for r in all_rows])
    out["peak_mem_mb"] = _med([r.get("peak_mem_mb") for r in all_rows])
    out["n_seeds"] = len(rows)
    hr = out["gap_half_life_read_min"]
    out["gap_hl_corr_of_median_read"] = R.correct_half_life(hr)["text"] if hr is not None else None
    out["gap_hl_range_of_median_read"] = R.correct_half_life(hr)["h_range"] if hr is not None else None
    return out


def jump_summary(root: Path, cid: str, seeds, min_seeds: int) -> Optional[Dict[str, Any]]:
    sb = RL.scenario_block(root, cid, seeds, min_seeds)
    if not sb:
        return None
    st = sb["stats"]
    keys = ["t50", "t90", "settle", "overshoot", "volume_uplift", "vol_uplift", "one_sided_share_jump",
            "spread_p95_jump_ticks", "spread_max_jump_ticks", "price_path_steps", "belief_5", "belief_30"]
    out = {k: (st[k]["median"] if k in st else None) for k in keys}
    out["n_seeds"] = sb["n_seeds"]
    return out


def completeness(root: Path, configs, seeds) -> str:
    """Per config: valid seeds, zero_sum failures, flag failures, median wall time."""
    L = ["| config | valid seeds | zero_sum ≠ 0 | flags failing | wall time median (s) | errors |",
         "|---|---|---|---|---|---|"]
    for cid in configs:
        rs = [RL.load_metrics(root, cid, s) for s in seeds]
        ok = [r for r in rs if r]
        errs = [s for s in seeds if (root / cid / str(s) / "error.txt").exists()]
        zs = sum(1 for r in ok if not (r["zero_sum_ok"] and r["zero_sum_cents"] == 0))
        fl = sum(1 for r in ok if not all(r["flags"].values()))
        L.append(f"| {cid} | {len(ok)}/{len(seeds)} | {zs} | {fl} | {_fmt(_med([r['wall_time_s'] for r in ok]))} | {errs or ''} |")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════════
# Campaign b (§7.2)
# ══════════════════════════════════════════════════════════════════════════


def report_b(engine: str) -> str:
    seeds = lab.SEEDS
    ms = R.MIN_VALID_SEEDS
    rows_def = runs(V13, "C-DEF", seeds)
    rows_bl = runs(ROOT, "C-BL", seeds)
    sc_def = R.scorecard([r["metrics"] for r in rows_def], ms)
    sc_bl = R.scorecard([r["metrics"] for r in rows_bl], ms)
    j_s2 = jump_summary(V13, "S2", seeds, ms)
    j_bl = jump_summary(ROOT, "S2-BL", seeds, ms)
    cd, cb = c_summary(rows_def, rows_def), c_summary(rows_bl, rows_bl + runs(ROOT, "S2-BL", seeds))

    L = [f"# Campaign b — budget alone (spec v1.4 §7.2)", "",
         f"C-BL = C-DEF + abides_budget {{\"L\": 2}} (GrossLimit on Noise, Value and ABIDES Momentum agents; market makers exempt). "
         f"S2-BL = S2 + budget. 20 seeds (api.lab.SEEDS). C-BL/S2-BL: engine {sorted({r['engine_version'] for r in rows_bl})}, "
         f"runs {sorted({r['date'] for r in rows_bl})}. C-DEF/S2: the stored v1.3 runs (runs/_lab, engine "
         f"{sorted({r['engine_version'] for r in rows_def})}); the budget-off market is bit-identical across these engines (I8). "
         f"Report generated {date.today().isoformat()}.", "",
         "## v1.3 scorecard: C-BL vs C-DEF (20-seed median, grade)", "",
         "| band | metric | C-DEF | grade | C-BL | grade |", "|---|---|---|---|---|---|"]
    for gid in ["G1", "G2"] + [f"G{i}" for i in range(3, 12)]:
        a, b = sc_def[gid], sc_bl[gid]
        if gid == "G2":
            va, vb = a["stats"]["value"], b["stats"]["value"]
        else:
            key = R.BANDS_BY_ID[gid].get("metrics", [R.BANDS_BY_ID[gid]["key"]])
            va = "; ".join(_fmt(a["stats"][k]["median"]) for k in key)
            vb = "; ".join(_fmt(b["stats"][k]["median"]) for k in key)
        L.append(f"| {gid} | {a['label']} | {_fmt(va)} | {a['grade']} | {_fmt(vb)} | {b['grade']} |")
    L += ["", "Other medians:", "",
          "| measure | C-DEF | C-BL |", "|---|---|---|"]
    for k in ["shares_executed", "spread_max_ticks", "one_sided_share", "gap_half_life_read_min",
              "gap_half_life_min", "gap_mean", "wall_time_s"]:
        L.append(f"| {k} | {_fmt(cd.get(k))} | {_fmt(cb.get(k))} |")

    # budget counts per class (C-BL and S2-BL), medians over seeds
    L += ["", "## BUDGET_BLOCK and clipped orders per class (median over 20 seeds, per run)", "",
          "| config | class | agents | orders clipped | orders blocked | blocked per agent | blocks by half-hour (09:30 … 15:30, median) |",
          "|---|---|---|---|---|---|---|"]
    for cid in ("C-BL", "S2-BL"):
        rs = runs(ROOT, cid, seeds)
        classes = sorted({c for r in rs for c in (r.get("budget") or {})})
        for c in classes:
            b = [r["budget"].get(c, {}) for r in rs]
            n = _med([x.get("agents") for x in b])
            bl = _med([x.get("blocked") for x in b])
            hh = np.median(np.array([x.get("blocked_by_halfhour", [0] * 13) for x in b]), axis=0)
            L.append(f"| {cid} | {c} | {_fmt(n)} | {_fmt(_med([x.get('clipped') for x in b]))} | {_fmt(bl)} | "
                     f"{_fmt(bl / n if n else None)} | {' '.join(str(int(v)) for v in hh)} |")

    L += ["", "## Jump: S2-BL vs S2 (+2% value jump at 11:00; treated minus same-seed baseline; median over seeds)", "",
          "| measure | S2 (v1.3 market) | S2-BL (+ budget) |", "|---|---|---|"]
    for k in ["t50", "t90", "settle", "overshoot", "volume_uplift", "vol_uplift", "one_sided_share_jump",
              "spread_p95_jump_ticks", "spread_max_jump_ticks", "price_path_steps", "n_seeds"]:
        L.append(f"| {k} | {_fmt((j_s2 or {}).get(k))} | {_fmt((j_bl or {}).get(k))} |")
    L += ["", "## Completeness", "", completeness(ROOT, ["C-BL", "S2-BL"], seeds), ""]
    summary = {"spec": "v1.4 §7.2", "generated": date.today().isoformat(), "engine": engine,
               "C-DEF": cd, "C-BL": cb, "S2": j_s2, "S2-BL": j_bl,
               "scorecard_C-DEF": sc_def, "scorecard_C-BL": sc_bl}
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "summary_b.json").write_text(json.dumps(RL._jsonable(summary), separators=(",", ":")), encoding="utf-8")
    md = "\n".join(L)
    (DOC / "CAMPAIGN_b.md").write_text(md, encoding="utf-8")
    return md


# ══════════════════════════════════════════════════════════════════════════
# Campaign s1 / s1r2 and the selection rule (§7.3, §7.4)
# ══════════════════════════════════════════════════════════════════════════


def design_summary(did: str, seeds) -> Dict[str, Any]:
    rows_c = runs(ROOT, did, seeds)
    rows_s2 = runs(ROOT, did + "-S2", seeds)
    C = c_summary(rows_c, rows_c + rows_s2)
    S2 = jump_summary(ROOT, did + "-S2", seeds, min_seeds=1) or {}
    sc = R.r3_scorecard({"C": C, "S2": S2}, screening=True)
    return {"design": did, "dials": lab.parse_design(did), "C": C, "S2": S2, "r3": sc,
            "n_seeds_C": len(rows_c), "n_seeds_S2": len(rows_s2)}


SCREEN_TARGETS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]
SELECTION_LIMITS = ["L1", "L2", "L4", "L5"]


def select_design(summaries: List[Dict[str, Any]]):
    """§7.4, mechanically. Returns (winner id or None, printout lines)."""
    P = ["Selection rule (spec v1.4 §7.4), applied to 5-seed medians.", ""]
    P.append("Step 1 — reject designs failing any limit L1, L2, L4, L5:")
    kept = []
    for s in summaries:
        lim = s["r3"]["limits"]
        fails = [l for l in SELECTION_LIMITS if lim[l]["status"] != "PASS"]
        if fails:
            detail = "; ".join(f"{l}: " + ", ".join(f"{c['key']}={_fmt(c['value'])} {c['op']} {c['threshold']:g} {c['result']}"
                                                  for c in lim[l]["checks"]) for l in fails)
            P.append(f"  {s['design']}: REJECTED ({detail})")
        else:
            P.append(f"  {s['design']}: kept")
            kept.append(s)
    if not kept:
        P.append("No design passes the limits: no winner by the rule.")
        return None, P
    P += ["", "Step 2 — number of targets passed among T1–T4, T5 (S2 only), T6 (S2 only), T7:"]
    for s in kept:
        t = s["r3"]["targets"]
        s["_n"] = sum(t[k]["status"] == "PASS" for k in SCREEN_TARGETS)
        P.append(f"  {s['design']}: {s['_n']} ({', '.join(k for k in SCREEN_TARGETS if t[k]['status'] == 'PASS') or 'none'})")
    best = max(s["_n"] for s in kept)
    tied = [s for s in kept if s["_n"] == best]
    P.append(f"  maximum {best}: {[s['design'] for s in tied]}")
    if len(tied) > 1:
        P += ["", "Step 3 — tie-break: minimise the sum of normalised misses over T1–T4 "
              "(scales T1 0.10, T2 0.45, T3 0.90, T4 0.30), then maximise daily volume, then the lexically smallest id:"]
        for s in tied:
            nm = [s["r3"]["targets"][k].get("norm_miss") for k in ("T1", "T2", "T3", "T4")]
            s["_miss"] = math.inf if any(v is None for v in nm) else float(sum(nm))
            s["_vol"] = s["C"].get("shares_executed") or 0.0
            P.append(f"  {s['design']}: misses T1–T4 {[_fmt(v) for v in nm]} sum {_fmt(s['_miss'])}; volume {_fmt(s['_vol'])}")
        tied.sort(key=lambda s: (s["_miss"], -s["_vol"], s["design"]))
    win = tied[0]["design"]
    P += ["", f"Winner: {win}"]
    return win, P


def _all_pass(s) -> bool:
    t, l = s["r3"]["targets"], s["r3"]["limits"]
    return all(t[k]["status"] == "PASS" for k in SCREEN_TARGETS) and all(l[k]["status"] == "PASS" for k in SELECTION_LIMITS)


def design_table(summaries: List[Dict[str, Any]], winner: Optional[str]) -> str:
    H = ("| design | N | T_r | σ_r | W | T1 ac1 | T2 VR5 | T3 vol ratio | T4 vv | T5 uplift S2 | T6 one-sided / p95 S2 | "
         "T7 total / median $ | targets | L1 spread med / p95 | L2 volume | L5 wall s | L4 | gap std $ | half-life read → corr (range) min | "
         "gap mean $ | t90 S2 min | seeds C/S2 |")
    L = [H, "|" + "|".join(["---"] * (H.count("|") - 1)) + "|"]
    for s in summaries:
        C, S2, t, l = s["C"], s["S2"], s["r3"]["targets"], s["r3"]["limits"]
        d = s["dials"]

        def mark(k):
            return {"PASS": "✓", "FAIL": "✗"}.get(t[k]["status"], "?")

        rng = C.get("gap_hl_range_of_median_read")
        name = f"**{s['design']}**" if s["design"] == winner else s["design"]
        L.append(
            f"| {name} | {lab.DIAL_N[d['N']]} | {lab.DIAL_T[d['T']][0]:g}–{lab.DIAL_T[d['T']][1]:g} s | "
            f"{lab.DIAL_S[d['S']][0]:g}–{lab.DIAL_S[d['S']][1]:g} c | ${lab.DIAL_W[d['W']] / 100:,.0f} | "
            f"{_fmt(C.get('ac1'))} {mark('T1')} | {_fmt(C.get('vr5'))} {mark('T2')} | {_fmt(C.get('vol_ratio_price_value'))} {mark('T3')} | "
            f"{_fmt(C.get('vv_corr'))} {mark('T4')} | {_fmt(S2.get('volume_uplift'))} {mark('T5')} | "
            f"{_fmt(S2.get('one_sided_share_jump'))} / {_fmt(S2.get('spread_p95_jump_ticks'))} {mark('T6')} | "
            f"{_fmt(C.get('fund_pnl_total'))} / {_fmt(C.get('fund_pnl_median'))} {mark('T7')} | "
            f"{sum(t[k]['status'] == 'PASS' for k in SCREEN_TARGETS)}/7 | "
            f"{_fmt(C.get('spread_med_ticks'))} / {_fmt(C.get('spread_p95_ticks'))} {l['L1']['status']} | "
            f"{_fmt(C.get('shares_executed'))} {l['L2']['status']} | {_fmt(C.get('wall_time_s'))} {l['L5']['status']} | "
            f"{l['L4']['status']} | {_fmt(C.get('gap_std'))} | {_fmt(C.get('gap_half_life_read_min'))} → "
            f"{_fmt(C.get('gap_hl_corr_of_median_read'))} ({'—' if not rng else f'{rng[0]:g}–{rng[1]:g}'}) | "
            f"{_fmt(C.get('gap_mean'))} | {_fmt(S2.get('t90'))} | {s['n_seeds_C']}/{s['n_seeds_S2']} |")
    return "\n".join(L)


def main_effects(summaries: List[Dict[str, Any]]) -> str:
    """§12.3.3: for each dial, the median over the 8 matched pairs (other dials
    fixed) of (measure at the high level − measure at the low level)."""
    by = {s["design"]: s for s in summaries}
    L = ["| dial (low → high) | " + " | ".join(lbl for _, lbl, _, _ in T_MEASURES) + " | volume | wall s |",
         "|" + "|".join(["---"] * (len(T_MEASURES) + 3)) + "|"]
    for dial, (lo, hi), label in (("N", ("60", "120"), "N 60 → 120"), ("T", ("f", "s"), "T_r fast → slow"),
                                  ("S", ("l", "h"), "σ_r low → high"), ("W", ("500k", "2M"), "W $0.5M → $2M")):
        cols = []
        for _, _, scope, key in T_MEASURES + [("", "", "C", "shares_executed"), ("", "", "C", "wall_time_s")]:
            diffs = []
            for did in lab.ROUND1_DESIGNS:
                d = lab.parse_design(did)
                if d[dial] != lo:
                    continue
                d2 = dict(d)
                d2[dial] = hi
                a, b = by.get(did), by.get(lab.design_id(d2["N"], d2["T"], d2["S"], d2["W"]))
                if a and b:
                    va, vb = a[scope].get(key), b[scope].get(key)
                    if va is not None and vb is not None:
                        diffs.append(vb - va)
            cols.append(_fmt(_med(diffs)))
        L.append(f"| {label} | " + " | ".join(cols) + " |")
    return "\n".join(L)


def report_s1(engine: str, seeds) -> str:
    sums1 = [design_summary(d, seeds) for d in lab.ROUND1_DESIGNS]
    win1, P1 = select_design([dict(s) for s in sums1])
    sel = {"generated": date.today().isoformat(), "engine": engine, "seeds": list(seeds),
           "round1": {"winner": win1, "printout": P1}}
    L = ["# Campaign s1 — design sweep, screening (spec v1.4 §7.3, §7.4)", "",
         f"Final population: 0 ValueAgents, informed fundamentalists (design dials below), budget L=2 on Noise/ABIDES "
         f"Momentum, 1000 noise, 2 MMs, 12 momentum EKF. Seeds {list(seeds)}; full day; engine {engine}; "
         f"generated {date.today().isoformat()}. Each design: D-x (no trigger) and D-x-S2 (+2% value jump at 11:00, "
         f"baseline D-x). Values are 5-seed medians; ✓/✗ = target met/missed in screening (T5, T6 on S2 only).", "",
         "## Round 1: the 16 designs", "", design_table(sums1, win1), "",
         "## Selection printout (round 1)", "", "```", *P1, "```", ""]
    need_r2 = win1 is not None and not _all_pass(next(s for s in sums1 if s["design"] == win1))
    win_final, sums2 = win1, []
    if win1 is None:
        need_r2 = False
    if need_r2:
        r2 = lab.round2_designs(win1)
        have = [d for d in r2 if RL.load_metrics(ROOT, d, seeds[0])]
        sel["round2_designs"] = r2
        if len(have) < len(r2):
            L += [f"Round-1 winner {win1} fails at least one target or limit: **round 2 required** "
                  f"(designs {r2}). Run `python scripts/realism_lab.py --campaign s1r2`.", ""]
            sel["round2"] = {"status": "pending"}
            win_final = None
        else:
            sums2 = [design_summary(d, seeds) for d in r2]
            pool = [next(s for s in sums1 if s["design"] == win1)] + sums2
            win_final, P2 = select_design([dict(s) for s in pool])
            sel["round2"] = {"winner": win_final, "printout": P2}
            L += ["## Round 2: the round-1 winner and its 8 extensions", "", design_table(pool, win_final), "",
                  "## Selection printout (round 2)", "", "```", *P2, "```", ""]
    elif win1 is not None:
        L += [f"The round-1 winner {win1} passes every screening target and limit: no round 2 (§7.4).", ""]
    sel["selected"] = win_final
    L += ["## Selected design", "", f"**{win_final}**" if win_final else "pending (round 2)", ""]
    if win_final:
        dd = lab.design_extra(win_final)
        L += [f"N = {dd['num_ekf_agents']}, T_r ∈ {dd['informed_design']['T_r_range_s']} s, "
              f"σ_r ∈ {dd['informed_design']['sigma_r_range_c']} c, wealth ${dd['informed_design']['wealth_c'] / 100:,.0f} per agent.", ""]
    L += ["## What each dial does (main effects over the 16 designs)", "",
          "Median over the 8 matched pairs (the other three dials fixed) of the change from the low to the high level.", "",
          main_effects(sums1), "",
          "## Completeness", "", completeness(ROOT, lab.CAMPAIGNS["s1"] + [c for d in sel.get("round2_designs", []) for c in (d, d + "-S2")], seeds), ""]
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "selection_s1.json").write_text(json.dumps(RL._jsonable(sel), indent=1), encoding="utf-8")
    (DOC / "summary_s1.json").write_text(json.dumps(RL._jsonable({"round1": sums1, "round2": sums2}), separators=(",", ":")), encoding="utf-8")
    md = "\n".join(L)
    (DOC / "RESULTS_s1.md").write_text(md, encoding="utf-8")
    return md


# ══════════════════════════════════════════════════════════════════════════
# entry point
# ══════════════════════════════════════════════════════════════════════════


def main_v14(a, engine: str) -> int:
    if a.campaign == "b":
        seeds = lab.SEEDS
        configs = lab.CAMPAIGNS["b"]
    else:
        seeds = lab.SCREEN_SEEDS
        if a.campaign == "s1":
            configs = lab.CAMPAIGNS["s1"]
        else:
            winner = a.winner
            if winner is None:
                sel = json.loads((DOC / "selection_s1.json").read_text(encoding="utf-8"))
                winner = sel["round1"]["winner"]
            lab.register_round2(winner)
            configs = lab.CAMPAIGNS["s1r2"]
    if a.seeds:
        seeds = [int(x) for x in a.seeds.split(",")]
    if a.configs:
        configs = a.configs.split(",")
    print(f"engine {engine}; campaign {a.campaign} (v1.4); {len(configs)} configs; {len(seeds)} seeds; "
          f"{a.workers} workers; root {ROOT}")
    if "+dirty" in engine:
        print("note: engine_version is +dirty (tracked files have uncommitted changes)")
    failed = []
    if not a.report_only:
        tasks = [(c, s) for c in configs for s in seeds if a.force or not RL.is_done(ROOT, c, s, engine)]
        print(f"{len(tasks)} runs to do, {len(configs) * len(seeds) - len(tasks)} already done", flush=True)
        t0 = time.time()
        _, failed = RL.run_all(tasks, ROOT, a.workers, engine)
        print(f"runs finished in {(time.time() - t0) / 60:.1f} min; {len(failed)} failed")
        for key, msg in failed:
            print("  FAILED", key, msg)
    if a.campaign == "b":
        report_b(engine)
        print(f"report: {(DOC / 'CAMPAIGN_b.md').relative_to(RL.REPO)}")
    else:
        report_s1(engine, lab.SCREEN_SEEDS if not a.seeds else seeds)
        print(f"report: {(DOC / 'RESULTS_s1.md').relative_to(RL.REPO)}")
    return 1 if failed else 0

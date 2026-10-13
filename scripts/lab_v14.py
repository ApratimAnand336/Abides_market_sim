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


V141_KEYS = ["spread_med_bps", "spread_p95_bps", "max_abs_gap"] + [f"vol_ratio_{k}m" for k in R.VOL_RATIO_HORIZONS_MIN]


def _augment_from_series(root: Path, cid: str, seed: int, m: Dict[str, Any]) -> Dict[str, Any]:
    """Runs stored before v1.4 lack the corrected half-life and L3 keys:
    recompute them from series.npz (no simulation)."""
    need_v14 = not ("gap_half_life_corr_min" in m and "active_halfhours_share" in m)
    need_v141 = not all(k in m for k in V141_KEYS)
    if not (need_v14 or need_v141):
        return m
    s = RL.load_series(root, cid, seed)
    if s is None:
        return m
    m = dict(m)
    if need_v14:
        c = R.gap_half_life_corrected(s["mid_1s"] - s["val_1s"])
        m.update(gap_half_life_read_min=R._f(c["h_read"]), gap_half_life_corr_min=R._f(c["h_corrected"]),
                 gap_half_life_corr_above=bool(c["above_table"]), gap_half_life_range=c["h_range"],
                 gap_mean=R._f(c["gap_mean"]))
        v = s["vol_1m"]
        win = [v[i:i + 30].sum() for i in range(0, len(v), 30)]
        m["active_halfhours_share"] = float(np.mean([w > 0 for w in win]))
    if need_v141:  # spec v1.4.1 Part 1 / 3.1: same functions as run_metrics
        m.update(R.spread_bps_metrics(s["spr_1s"], s["mid_1s"]))
        m["max_abs_gap"] = float(np.max(np.abs(s["mid_1s"] - s["val_1s"])))
        val_close = R.bar_closes(s["val_1s"], len(s["val_1s"]) - 1)
        for k in R.VOL_RATIO_HORIZONS_MIN:
            m[f"vol_ratio_{k}m"] = R.vol_ratio_horizon(s["close_1m"], val_close, k)
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
            "spread_max_ticks", "cs", "kurt", "regime_contrast",
            "vr30"] + V141_KEYS
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
            "spread_p95_jump_ticks", "spread_max_jump_ticks", "price_path_steps", "belief_5", "belief_30",
            "spread_jump_ratio", "spread_p95_jump_bps", "spread_p95_jump_bps_base"] + \
        [f"informed_share_updated_{m}m" for m in R.SHARE_UPDATED_MIN]
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


def design_summary(did: str, seeds, screening: bool = True) -> Dict[str, Any]:
    """5-seed medians of one design. screening=True: T5/T6 on S2 only (v1.4
    §7.4); False: on S2 and S2n (v1.4.1 §3.3; missing S2n runs -> MISSING)."""
    rows_c = runs(ROOT, did, seeds)
    rows_s2 = runs(ROOT, did + "-S2", seeds)
    rows_s2n = runs(ROOT, did + "-S2n", seeds)
    C = c_summary(rows_c, rows_c + rows_s2 + rows_s2n)
    S2 = jump_summary(ROOT, did + "-S2", seeds, min_seeds=1) or {}
    S2n = (jump_summary(ROOT, did + "-S2n", seeds, min_seeds=1) or {}) if rows_s2n else {}
    sc = R.r3_scorecard({"C": C, "S2": S2, "S2n": S2n}, screening=screening)
    return {"design": did, "dials": lab.parse_design(did), "C": C, "S2": S2, "S2n": S2n, "r3": sc,
            "n_seeds_C": len(rows_c), "n_seeds_S2": len(rows_s2), "n_seeds_S2n": len(rows_s2n)}


SCREEN_TARGETS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]
SELECTION_LIMITS = ["L1", "L2", "L4", "L5"]
SELECTION_LIMITS_V141 = ["L1", "L4", "L5", "L2", "L6"]  # spec v1.4.1 §3.3


def select_design(summaries: List[Dict[str, Any]], limits=None, title=None):
    """§7.4, mechanically. Returns (winner id or None, printout lines)."""
    limits = limits or SELECTION_LIMITS
    P = [title or "Selection rule (spec v1.4 §7.4), applied to 5-seed medians.", ""]
    P.append(f"Step 1 — reject designs failing any limit {', '.join(limits)}:")
    kept = []
    for s in summaries:
        lim = s["r3"]["limits"]
        fails = [l for l in limits if lim[l]["status"] != "PASS"]
        if fails:
            detail = "; ".join(f"{l}: " + ", ".join(f"{c['key']}={_fmt(c['value'])} {c['op']} {c['threshold']:g} {c['result']}"
                                                  for c in lim[l]["checks"]) for l in fails)
            P.append(f"  {s['design']}: REJECTED ({detail})")
        else:
            P.append(f"  {s['design']}: kept")
            kept.append(s)
    if not kept:
        P.append(f"No design passes the limits {', '.join(limits)}: step 1 rejects every design, so the rule "
                 "names no winner and round 2 (defined from a round-1 winner) cannot start. "
                 "§7.4 does not cover this case: the owner decides.")
        return None, P
    scr = [all(c["scope"] != "S2n" for t in k["r3"]["targets"].values() for c in t["checks"]) for k in kept]
    on = "S2 only" if all(scr) else ("S2 AND S2n" if not any(scr) else "S2 AND S2n; designs without S2n runs: S2 only")
    P += ["", f"Step 2 — number of targets passed among T1–T7 (T5, T6 on {on}):"]
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


def _all_pass(s, limits=None) -> bool:
    t, l = s["r3"]["targets"], s["r3"]["limits"]
    return all(t[k]["status"] == "PASS" for k in SCREEN_TARGETS) and \
        all(l[k]["status"] == "PASS" for k in (limits or SELECTION_LIMITS))


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


def _mark(t, k):
    return {"PASS": "✓", "FAIL": "✗"}.get(t[k]["status"], "?")


def design_table_v141(summaries: List[Dict[str, Any]], winner: Optional[str]) -> str:
    """spec v1.4.1 table: corrected limits and targets plus the Part 1 diagnostics."""
    H = ("| design | T1 ac1 | T2 VR5 | T3 vol ratio 1m | T4 vv | T5 uplift S2 / S2n | T6 one-sided S2/S2n · ratio S2/S2n | "
         "T7 total / median $ | targets | L1 spread med / p95 bps | L2 volume | L5 wall s | L6 max gap $ | L4 | "
         "vol ratio 5/15/30/60 m | VR(30) | updated +1/2/5/10/15 m (S2) | t50 / t90 S2 min | spread p95 ticks S2 | seeds C/S2/S2n |")
    L = [H, "|" + "|".join(["---"] * (H.count("|") - 1)) + "|"]
    for s in summaries:
        C, S2, S2n, t, l = s["C"], s["S2"], s.get("S2n") or {}, s["r3"]["targets"], s["r3"]["limits"]
        name = f"**{s['design']}**" if s["design"] == winner else s["design"]
        upd = " / ".join(_fmt(S2.get(f"informed_share_updated_{m}m"), 2) for m in R.SHARE_UPDATED_MIN)
        L.append(
            f"| {name} | {_fmt(C.get('ac1'))} {_mark(t, 'T1')} | {_fmt(C.get('vr5'))} {_mark(t, 'T2')} | "
            f"{_fmt(C.get('vol_ratio_price_value'))} {_mark(t, 'T3')} | {_fmt(C.get('vv_corr'))} {_mark(t, 'T4')} | "
            f"{_fmt(S2.get('volume_uplift'))} / {_fmt(S2n.get('volume_uplift'))} {_mark(t, 'T5')} | "
            f"{_fmt(S2.get('one_sided_share_jump'))}/{_fmt(S2n.get('one_sided_share_jump'))} · "
            f"{_fmt(S2.get('spread_jump_ratio'))}/{_fmt(S2n.get('spread_jump_ratio'))} {_mark(t, 'T6')} | "
            f"{_fmt(C.get('fund_pnl_total'))} / {_fmt(C.get('fund_pnl_median'))} {_mark(t, 'T7')} | "
            f"{sum(t[k]['status'] == 'PASS' for k in SCREEN_TARGETS)}/7 | "
            f"{_fmt(C.get('spread_med_bps'))} / {_fmt(C.get('spread_p95_bps'))} {l['L1']['status']} | "
            f"{_fmt(C.get('shares_executed'))} {l['L2']['status']} | {_fmt(C.get('wall_time_s'))} {l['L5']['status']} | "
            f"{_fmt(C.get('max_abs_gap'))} {l['L6']['status']} | {l['L4']['status']} | "
            f"{' / '.join(_fmt(C.get(f'vol_ratio_{k}m'), 2) for k in R.VOL_RATIO_HORIZONS_MIN)} | {_fmt(C.get('vr30'))} | "
            f"{upd} | {_fmt(S2.get('t50'))} / {_fmt(S2.get('t90'))} | {_fmt(S2.get('spread_p95_jump_ticks'))} | "
            f"{s['n_seeds_C']}/{s['n_seeds_S2']}/{s.get('n_seeds_S2n', 0)} |")
    return "\n".join(L)


def g8_regrade() -> List[str]:
    """spec v1.4.1 Part 1: G8 re-graded in bps for the v1.3 markets (stored runs)."""
    L = ["| market (v1.3 runs, 20 seeds) | spread median / p95 (bps) | G8 (v1.4.1) | G8 as graded in v1.3 (ticks) |",
         "|---|---|---|---|"]
    for cid in ("C-DEF", "C-V20"):
        rows = runs(V13, cid, lab.SEEDS)
        if not rows:
            continue
        med = _med([r["metrics"].get("spread_med_bps") for r in rows])
        p95 = _med([r["metrics"].get("spread_p95_bps") for r in rows])
        g = R.grade_value(R.BANDS_BY_ID["G8"], {"spread_med_bps": med, "spread_p95_bps": p95})
        mt = _med([r["metrics"].get("spread_med_ticks") for r in rows])
        pt = _med([r["metrics"].get("spread_p95_ticks") for r in rows])
        L.append(f"| {cid} | {_fmt(med)} / {_fmt(p95)} | {g} | {_fmt(mt)} / {_fmt(pt)} ticks: PASS |")
    return L


def report_s2(engine: str, seeds) -> str:
    """docs/v1.4/lab/RESULTS_s2.md (spec v1.4.1): corrected round 1 (§3.1),
    then campaign s2 and the 32-candidate selection (§3.3) once its runs exist."""
    sums1 = [design_summary(d, seeds, screening=True) for d in lab.ROUND1_DESIGNS]
    win1c, P1c = select_design([dict(x) for x in sums1], SELECTION_LIMITS_V141,
                               "Round 1 under the corrected rules (spec v1.4.1 §3.1; v1.4 §7.4 rule, T5/T6 on S2 only; "
                               "for the record only).")
    run_eng = sorted({r["engine_version"] for c in lab.CAMPAIGNS["s1"] for r in runs(ROOT, c, seeds)})
    L = ["# Campaign s2 — learning from prices, and the corrected round 1 (spec v1.4.1)", "",
         f"Seeds {list(seeds)}; full day; final population (0 ValueAgents, budget L=2). Values are 5-seed medians. "
         f"Report generated {date.today().isoformat()} (report engine {engine}).", "",
         "## 1. Round 1 re-evaluated under the corrected rules (§3.1, no new runs)", "",
         f"Stored s1 runs (engine {run_eng}); L1 and G8 in bps of the mid, T6 as spread_jump_ratio, new limit L6, "
         "diagnostics of Part 1 recomputed from series.npz. Round 1 has no S2n runs, so T5/T6 are judged on S2 here.", "",
         design_table_v141(sums1, win1c), "", "```", *P1c, "```", "",
         "### G8 re-graded (v1.3 markets)", "", *g8_regrade(), ""]
    out = {"round1_corrected": {"winner": win1c, "printout": P1c, "designs": sums1}}
    s2 = getattr(lab, "S2_DESIGNS", [])
    have = [d for d in s2 if RL.load_metrics(ROOT, d, seeds[0])]
    if s2 and len(have) == len(s2):
        L += report_s2_selection(sums1, seeds, out)
    elif s2:
        L += [f"## 2. Campaign s2: {len(have)}/{len(s2)} designs have runs; selection pending.", ""]
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "summary_s2.json").write_text(json.dumps(RL._jsonable(out), separators=(",", ":")), encoding="utf-8")
    extra = DOC / "S2_FINDINGS.md"  # hand-written findings and E11-E15 verdicts (N4c)
    if extra.exists() and "s2" in out:
        L += ["", extra.read_text(encoding="utf-8")]
    md = "\n".join(L)
    (DOC / "RESULTS_s2.md").write_text(md, encoding="utf-8")
    return md


def _effects(by: Dict[str, Dict[str, Any]], pairs, rows) -> List[str]:
    """Median over matched pairs (a -> b) of the change of each measure."""
    L = ["| change | " + " | ".join(lbl for lbl, _, _ in rows) + " |", "|" + "|".join(["---"] * (len(rows) + 1)) + "|"]
    for label, plist in pairs:
        cols = []
        for _, scope, key in rows:
            d = []
            for a, b in plist:
                A, B = by.get(a), by.get(b)
                if A and B and (A.get(scope) or {}).get(key) is not None and (B.get(scope) or {}).get(key) is not None:
                    d.append(B[scope][key] - A[scope][key])
            cols.append(_fmt(_med(d)))
        L.append(f"| {label} | " + " | ".join(cols) + " |")
    return L


EFFECT_ROWS = [("ac1", "C", "ac1"), ("VR(5)", "C", "vr5"), ("VR(30)", "C", "vr30"), ("vol ratio 1m", "C", "vol_ratio_price_value"),
               ("vol ratio 15m", "C", "vol_ratio_15m"), ("vol ratio 30m", "C", "vol_ratio_30m"), ("vv_corr", "C", "vv_corr"),
               ("max gap $", "C", "max_abs_gap"), ("spread med bps", "C", "spread_med_bps"), ("spread p95 bps", "C", "spread_p95_bps"),
               ("jump ratio S2", "S2", "spread_jump_ratio"), ("updated +2m", "S2", "informed_share_updated_2m"),
               ("updated +5m", "S2", "informed_share_updated_5m"), ("t90 S2", "S2", "t90"), ("volume", "C", "shares_executed"),
               ("fund P&L total", "C", "fund_pnl_total")]


def _fails(s, limits) -> List[str]:
    t, l = s["r3"]["targets"], s["r3"]["limits"]
    return [k for k in SCREEN_TARGETS if t[k]["status"] != "PASS"] + [k for k in limits if l[k]["status"] != "PASS"]


def _why(s) -> List[str]:
    """Evidence lines for every failed target/limit of a design (check values)."""
    out = []
    for grp in ("targets", "limits"):
        for k, it in s["r3"][grp].items():
            if it["status"] != "PASS":
                out.append(f"- {k} ({it['label']}): " + "; ".join(
                    f"{c['scope']} {c['key']} = {_fmt(c['value'])} {c['op']} {c['threshold']:g} → {c['result']}" for c in it["checks"]))
    return out


def report_s2_selection(sums1, seeds, out) -> List[str]:
    """spec v1.4.1 §3.2-3.5: the s2 table, the 32-candidate selection, the
    refinement round and the continue/stop decision, all mechanical."""
    lim = SELECTION_LIMITS_V141
    sums2 = [design_summary(d, seeds, screening=False) for d in lab.S2_DESIGNS]
    run_eng = sorted({r["engine_version"] for c in lab.CAMPAIGNS["s2"] for r in runs(ROOT, c, seeds)})
    run_dates = sorted({r["date"] for c in lab.CAMPAIGNS["s2"] for r in runs(ROOT, c, seeds)})
    # §3.3: round-1 designs enter "re-evaluated by 3.1" (T5/T6 on S2: they have no S2n runs)
    pool = [dict(x) for x in sums1] + [dict(x) for x in sums2]
    win, P = select_design(pool, lim, "Selection over 32 candidates (spec v1.4.1 §3.3): limits L1, L4, L5, L2, L6; "
                                      "targets T1–T7 (s2 designs: T5, T6 on S2 AND S2n; round-1 designs: as re-evaluated by §3.1, S2 only).")
    by = {x["design"]: x for x in sums1 + sums2}
    L = ["## 2. Campaign s2: learning from prices (§3.2)", "",
         f"16 designs D-<N><T><S>2M-<L> × {{C, S2, S2n}} × seeds {list(seeds)} = 240 runs; engine {run_eng}; dates {run_dates}; "
         "W fixed at $2M (7 of 8 $500k designs failed L2 in round 1).", "",
         design_table_v141(sums2, win), "",
         "### What learning and the dials do (median change over matched pairs)", "",
         *_effects(by, [
             ("off → mod (same N, T, S at $2M)", [(d.replace("-mod", ""), d) for d in lab.S2_DESIGNS if d.endswith("-mod")]),
             ("off → strong", [(d.replace("-strong", ""), d) for d in lab.S2_DESIGNS if d.endswith("-strong")]),
             ("mod → strong", [(d, d.replace("-mod", "-strong")) for d in lab.S2_DESIGNS if d.endswith("-mod")]),
             ("N 60 → 120 (s2)", [(d, d.replace("D-60", "D-120", 1)) for d in lab.S2_DESIGNS if d.startswith("D-60")]),
             ("T_r fast → slow (s2)", [(d, lab.design_id_d({**lab.parse_design(d), "T": "s"})) for d in lab.S2_DESIGNS
                                       if lab.parse_design(d)["T"] == "f"]),
             ("σ_r low → high (s2)", [(d, lab.design_id_d({**lab.parse_design(d), "S": "h"})) for d in lab.S2_DESIGNS
                                     if lab.parse_design(d)["S"] == "l"]),
         ], EFFECT_ROWS), "",
         "## 3. Selection over 32 candidates (§3.3)", "", "```", *P, "```", ""]
    sel = {"generated": date.today().isoformat(), "seeds": list(seeds), "winner_32": win, "printout_32": P}
    final, final_sum = win, by.get(win)
    if win is None:
        L += ["No winner: every candidate fails a limit. Per §3.5: STOP and report.", ""]
        sel["decision"] = "STOP"
    else:
        fails = _fails(by[win], lim)
        if not fails:
            L += [f"The winner {win} passes every target and limit: no refinement round (§3.4).", ""]
        else:
            ref = lab.refinement_designs(win)
            sel["refinement_designs"] = ref
            have = all(RL.load_metrics(ROOT, d, seeds[0]) for d in ref) and \
                all(RL.load_metrics(ROOT, d + "-S2n", seeds[0]) for d in ref + [win])
            L += [f"Winner {win} fails {', '.join(fails)}: refinement round (§3.4) with {ref} (C + S2 + S2n, 5 seeds), "
                  f"plus S2n runs of the winner itself where missing.", ""]
            if not have:
                L += ["Refinement runs are not complete: run `python scripts/realism_lab.py --campaign s2r`.", ""]
                sel["decision"] = "PENDING_REFINEMENT"
                final, final_sum = None, None
            else:
                pool2 = [design_summary(d, seeds, screening=False) for d in [win] + ref]
                final, P2 = select_design([dict(x) for x in pool2], lim,
                                          "Refinement round (spec v1.4.1 §3.4): the winner and its three refinements, "
                                          "T5/T6 on S2 AND S2n.")
                sel["printout_refinement"] = P2
                by.update({x["design"]: x for x in pool2})
                final_sum = by.get(final)
                L += ["## 4. Refinement round (§3.4)", "", design_table_v141(pool2, final), "", "```", *P2, "```", ""]
    sel["selected"] = final
    if final_sum is not None:
        fails = _fails(final_sum, lim)
        sel["decision"] = "CONTINUE_N5" if not fails else "STOP"
        sel["selected_fails"] = fails
        S2, S2n = final_sum["S2"], final_sum.get("S2n") or {}
        L += ["## 5. Selected design and decision (§3.5)", "",
              f"**{final}** — " + ("passes every target and limit: continue to N5." if not fails
                                   else f"fails {', '.join(fails)}: STOP and report to the owner (§3.5)."), "",
              "Jump timeline of the selected design (5-seed medians; cf. spec v1.4.1 §0.2 for D-60fl2M without learning):", "",
              "| jump | updated +1 m | +2 m | +5 m | +10 m | +15 m | t50 min | t90 min | spread_jump_ratio | one-sided | volume uplift |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for nm, J in (("+2% (S2)", S2), ("−2% (S2n)", S2n)):
            L.append(f"| {nm} | " + " | ".join(_fmt(J.get(f"informed_share_updated_{m}m"), 2) for m in R.SHARE_UPDATED_MIN) +
                     f" | {_fmt(J.get('t50'))} | {_fmt(J.get('t90'))} | {_fmt(J.get('spread_jump_ratio'))} | "
                     f"{_fmt(J.get('one_sided_share_jump'))} | {_fmt(J.get('volume_uplift'))} |")
        if fails:
            L += ["", "Failed targets/limits and their evidence:", "", *_why(final_sum)]
        L.append("")
    out["s2"] = {"designs": sums2, "selection": sel}
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / "selection_s2.json").write_text(json.dumps(RL._jsonable(sel), indent=1), encoding="utf-8")
    return L


def report_s1(engine: str, seeds) -> str:
    sums1 = [design_summary(d, seeds) for d in lab.ROUND1_DESIGNS]
    run_engines = sorted({r["engine_version"] for c in lab.CAMPAIGNS["s1"] for r in runs(ROOT, c, seeds)})
    run_dates = sorted({r["date"] for c in lab.CAMPAIGNS["s1"] for r in runs(ROOT, c, seeds)})
    win1, P1 = select_design([dict(s) for s in sums1])
    sel = {"generated": date.today().isoformat(), "engine": engine, "seeds": list(seeds),
           "round1": {"winner": win1, "printout": P1}}
    L = ["# Campaign s1 — design sweep, screening (spec v1.4 §7.3, §7.4)", "",
         f"Final population: 0 ValueAgents, informed fundamentalists (design dials below), budget L=2 on Noise/ABIDES "
         f"Momentum, 1000 noise, 2 MMs, 12 momentum EKF. Seeds {list(seeds)}; full day; runs: engine {run_engines}, "
         f"dates {run_dates}, 2 workers on an i7-13620H (16 threads, 15.6 GB); report generated {date.today().isoformat()}. Each design: D-x (no trigger) and D-x-S2 (+2% value jump at 11:00, "
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
    if win_final:
        sel_txt = f"**{win_final}**"
    elif win1 is None:
        sel_txt = "**none** — every round-1 design fails at least one limit (see step 1); §7.4 has no rule for this case."
    else:
        sel_txt = "pending (round 2)"
    L += ["## Selected design", "", sel_txt, ""]
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
    elif a.campaign in ("s2", "s2r"):  # spec v1.4.1
        seeds = lab.SCREEN_SEEDS
        if a.campaign == "s2":
            configs = lab.CAMPAIGNS["s2"]
        else:
            winner = a.winner or json.loads((DOC / "selection_s2.json").read_text(encoding="utf-8"))["winner_32"]
            lab.register_refinement(winner)
            configs = lab.CAMPAIGNS["s2r"]
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
    elif a.campaign in ("s2", "s2r"):
        report_s2(engine, lab.SCREEN_SEEDS if not a.seeds else seeds)
        print(f"report: {(DOC / 'RESULTS_s2.md').relative_to(RL.REPO)}")
    else:
        report_s1(engine, lab.SCREEN_SEEDS if not a.seeds else seeds)
        print(f"report: {(DOC / 'RESULTS_s1.md').relative_to(RL.REPO)}")
    return 1 if failed else 0

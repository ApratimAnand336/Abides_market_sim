"""A8 of FinVerse spec v1.5: the confirmation campaign a-confirm (A9.1) and the R4a report
docs/v1.5/lab/RESULTS_A.md (A9.2). Judged by api.realism.r4a_scorecard on 20-seed medians:
C = N-C, S2 / S2n = N-S2 / N-S2n treated minus N-C of the same seed, MIX = D-mix.

    python scripts/realism_lab.py --campaign a-confirm --workers 2
    python scripts/realism_lab.py --campaign a-confirm --report-only
"""

import json
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np

import lab_v14 as L14
import lab_v15 as V
import realism_lab as RL
from api import lab, realism as R

ROOT, DOC = V.ROOT, V.DOC
FIG = DOC / "figures"
SEEDS = lab.SEEDS
MIN_SEEDS = R.MIN_VALID_SEEDS
DAY_CONFIGS = {"D-calm": "calm", "N-C": "normal", "D-volatile": "volatile", "D-mix": "auto (mix)"}
_fmt = L14._fmt

# v1.4 values as A8.1 writes them (reference column, not recomputed)
V14_REF = {"A-T1": "0.62", "A-T2": "0.005", "A-T3": "0.20%", "A-T4": "1.2488", "A-T5": "0.49",
           "A-T6": "+0.53", "A-T7": "0.087 / 0.032", "A-T8": "1.47", "A-T9": "2.5 / 15 / 0",
           "A-T10": "+$1,023 / −$107", "A-T11": "new", "A-T12": "1.14"}

# A9: impact set as A8 measured it (engine v1.4-d498ee4) BEFORE the probe was made the last
# agent; the N-IMP-* runs were re-run after the fix (N-C fingerprints unchanged, 20/20)
PRE_PROBE_FIX = {"noise_I_end": 1.81, "noise_I_perm": 0.392, "beta": 1.10, "ci": (0.939, 1.86), "G12": "FAIL",
                 "beta_peak": 0.529, "rec1": 0.357, "rec5": 0.289, "G13": "PASS"}


def _seeds(cid: str) -> List[int]:
    return lab.CONFIG_SEEDS.get(cid, SEEDS)


def _c_scope(cid: str) -> Dict[str, Any]:
    """20-seed (or 10-seed) medians of a no-trigger config, with the L4/L5 fields over
    every run of the campaign (zero_sum, flags, wall time are campaign-wide limits)."""
    seeds = _seeds(cid)
    C = V.config_summary(cid, seeds)
    rows = L14.runs(ROOT, cid, seeds)
    allr = [r for c in lab.CAMPAIGNS["a-confirm"] for r in L14.runs(ROOT, c, _seeds(c))]
    C["zero_sum_all_zero"] = 1.0 if allr and all(r["zero_sum_ok"] and r["zero_sum_cents"] == 0 for r in allr) else 0.0
    bad = sorted({k for r in allr for k, v in r["flags"].items() if not v})
    C["flags_failing"] = bad
    C["flags_all_ok"] = 1.0 if allr and not [k for k in bad if k not in V.L4_IGNORED_FLAGS] else 0.0
    C["informed_bounds_fail_runs"] = sum(1 for r in allr if r["flags"].get("informed_bounds") is False)
    C["wall_time_s"] = V._med([r["wall_time_s"] for r in allr])
    C["wall_time_config_s"] = V._med([r["wall_time_s"] for r in rows])
    C["peak_mem_mb_all"] = V._med([r.get("peak_mem_mb") for r in allr])
    day = [r["metrics"].get("day_return_pct") for r in rows]
    day = [x for x in day if x is not None and np.isfinite(x)]
    C["sigma_day_xseed"] = float(np.std(day, ddof=1)) if len(day) >= 2 else None
    C["retail_stop_trigger_pct"] = V._med([r["metrics"].get("retail_stop_trigger_pct") for r in rows])
    st = [r.get("diagnostics", {}).get("retail_stops") or {} for r in rows]
    C["stop_trigger_share_pct"] = V._med([100.0 * s["n_traders_triggered"] / s["n_stop_users"]
                                          for s in st if s.get("n_stop_users")])
    C["n_stress_episodes"] = V._med([len((r.get("diagnostics", {}).get("day_info") or {}).get("stress_episodes") or [])
                                     for r in rows])
    C["day_types"] = {t: sum(1 for r in rows if (r.get("diagnostics", {}).get("day_info") or {}).get("day_type") == t)
                      for t in ("calm", "normal", "volatile")}
    C["n_valid"] = len(rows)
    return C


def build() -> Dict[str, Any]:
    C = {cid: _c_scope(cid) for cid in DAY_CONFIGS}
    S2 = L14.jump_summary(ROOT, "N-S2", SEEDS, MIN_SEEDS) or {}
    S2n = L14.jump_summary(ROOT, "N-S2n", SEEDS, MIN_SEEDS) or {}
    mix = C["D-mix"]
    MIX = {k: mix.get(k) for k in ("sigma_day_xseed", "day_rv_regime_spread", "spread_med_bps", "spread_p95_bps")}
    sc = R.r4a_scorecard({"C": C["N-C"], "S2": S2, "S2n": S2n, "MIX": MIX})
    per_day = {cid: R.r4a_scorecard({"C": C[cid]}, screening=True) for cid in DAY_CONFIGS}
    scen = {c: RL.scenario_block(ROOT, c, SEEDS, MIN_SEEDS) for c in ("N-S2", "N-S2n", "N-S4")}
    imp = V.impact_summary("N", SEEDS, MIN_SEEDS)
    imp_scen = {k: RL.scenario_block(ROOT, f"N-{k}", SEEDS, MIN_SEEDS) for k in V.IMPACT_SET}
    return {"C": C, "S2": S2, "S2n": S2n, "MIX": MIX, "r4a": sc, "per_day": per_day, "scen": scen,
            "impact": imp, "imp_scen": imp_scen}


# ── report sections ──────────────────────────────────────────────────────

def _chk(c) -> str:
    return f"{c['scope']}.{c['key']} = {_fmt(c['value'])} {c['op']} {c['threshold']:g}"


def _scorecard_lines(sc) -> List[str]:
    L = ["| id | measure | value(s) (20-seed medians) | v1.4 | result |", "|---|---|---|---|---|"]
    for k, t in sc["targets"].items():
        L.append(f"| {k} | {t['label']} | " + "; ".join(_chk(c) for c in t["checks"]) +
                 f" | {V14_REF.get(k, '')} | **{t['status']}** |")
    for k, t in sc["limits"].items():
        L.append(f"| {k} | {t['label']} | " + "; ".join(_chk(c) for c in t["checks"]) + f" | | **{t['status']}** |")
    return L


DAY_ROWS = [("σ1m (bps)", "sigma_1m_bps", 2), ("day realised vol (%)", "day_rv_pct", 2),
            ("daily sd across seeds (%)", "sigma_day_xseed", 2), ("RS = p90/p10 day rv", "day_rv_regime_spread", 2),
            ("ac1", "ac1", 3), ("VR(5)", "vr5", 3), ("vol ratio 1 min", "vol_ratio_price_value", 2),
            ("vv Spearman", "vv_corr", 2), ("CS", "cs", 3), ("PS", "ps", 3), ("excess kurtosis", "kurt", 1),
            ("u_ratio", "u_ratio", 2), ("spread median (bps)", "spread_med_bps", 2),
            ("spread p95 (bps)", "spread_p95_bps", 2), ("shares/day", "shares_executed", 0),
            ("max |mid − value| ($)", "max_abs_gap", 2), ("retail share (%)", "retail_share", 1),
            ("MM share (%)", "mm_share", 1), ("MM max |inventory| (sh)", "mm_inv_max_abs", 0),
            ("informed P&L total ($)", "fund_pnl_total", 0), ("informed P&L median ($)", "fund_pnl_median", 0),
            ("MM group P&L ($)", "mm_pnl_group_median", 0), ("retail P&L total ($)", "retail_pnl_total", 0),
            ("momentum P&L total ($)", "mom_pnl_total", 0), ("info news per day", "info_news_n", 1),
            ("info news f10", "info_news_f10", 2), ("info news volume uplift", "info_news_uplift", 2),
            ("stress episodes per day", "n_stress_episodes", 1), ("stop users triggered (%)", "stop_trigger_share_pct", 2),
            ("gap std ($)", "gap_std", 2), ("gap half-life read (min)", "gap_half_life_read_min", 1),
            ("regime contrast (per day)", "regime_contrast", 2), ("wall time (s)", "wall_time_config_s", 1)]


def _day_lines(C) -> List[str]:
    cids = list(DAY_CONFIGS)
    L = ["| measure | " + " | ".join(f"{c} ({DAY_CONFIGS[c]}, {C[c]['n_valid']} seeds)" for c in cids) + " |",
         "|---|" + "---|" * len(cids)]
    for lab_, k, d in DAY_ROWS:
        L.append(f"| {lab_} | " + " | ".join(_fmt(C[c].get(k), d) for c in cids) + " |")
    L.append("| day types drawn (calm/normal/volatile) | " + " | ".join(
        "/".join(str(C[c]["day_types"][t]) for t in ("calm", "normal", "volatile")) for c in cids) + " |")
    return L


def _per_day_grid(per_day) -> List[str]:
    ids = R.R4A_SCREEN_TARGETS + [x["id"] for x in R.R4A_LIMITS]
    L = ["| config | " + " | ".join(ids) + " |", "|---|" + "---|" * len(ids)]
    for cid, sc in per_day.items():
        al = {**sc["targets"], **sc["limits"]}
        L.append(f"| {cid} | " + " | ".join({"PASS": "✓", "FAIL": "✗"}.get(al[k]["status"], "–") for k in ids) + " |")
    return L


def _scenario_lines(b) -> List[str]:
    S2, S2n = b["S2"], b["S2n"]
    s14 = json.loads((RL.DOC_V14 / "summary.json").read_text(encoding="utf-8"))["scenarios"]
    keys = ["t50", "t90", "settle", "overshoot", "volume_uplift", "vol_uplift", "spread_jump_ratio",
            "one_sided_share_jump", "spread_p95_jump_bps", "belief_5", "belief_30"]
    L = ["| measure | N-S2 (+2%) | N-S2n (−2%) | v1.4 P0-S2 | v1.4 P0-S2n |", "|---|---|---|---|---|"]
    for k in keys:
        v = [((s14.get(c) or {}).get("stats", {}).get(k) or {}).get("median") for c in ("P0-S2", "P0-S2n")]
        L.append(f"| {k} | {_fmt(S2.get(k))} | {_fmt(S2n.get(k))} | {_fmt(v[0])} | {_fmt(v[1])} |")
    n4 = (b["scen"].get("N-S4") or {}).get("stats", {})
    v4 = s14.get("P0-S4", {}).get("stats", {})
    L += ["", "Hype news +0.9 at 11:00 (N-S4 vs N-C; R in bps):", "", "| measure | N-S4 | v1.4 P0-S4 |", "|---|---|---|"]
    for k in ("R_peak", "t_peak", "t_half_rev", "R_60", "belief_shift_fund_median", "mom_dv_median"):
        L.append(f"| {k} | {_fmt((n4.get(k) or {}).get('median'))} | {_fmt((v4.get(k) or {}).get('median'))} |")
    return L


def _impact_lines(b) -> List[str]:
    imp, sc = b["impact"], b["imp_scen"]
    if not imp:
        return ["Impact set incomplete."]
    L = ["| config | q (share of daily volume) | I_end | I_peak | I_perm | recovery | fill rate | shortfall bps |",
         "|---|---|---|---|---|---|---|---|"]
    for k in V.IMPACT_SET:
        st = sc[k]["stats"]
        L.append(f"| N-{k} | {_fmt(st['q']['median'])} | {_fmt(st['I_end']['median'])} | {_fmt(st['I_peak']['median'])} | "
                 f"{_fmt(st['I_perm']['median'])} | {_fmt(st['recovery']['median'])} | {_fmt(st['fill_rate']['median'])} | "
                 f"{_fmt(st['shortfall_bps']['median'])} |")
    be = imp["beta_I_end"]
    L += ["", f"Noise floor (N-IMP-0): I_end {_fmt(imp['noise_floor']['I_end'])} bps, I_perm "
          f"{_fmt(imp['noise_floor']['I_perm'])} bps. Impact β (I_end on q, four sizes, {be['n_seeds']} seeds): "
          f"**{_fmt(be['beta'])}** [{_fmt(be['ci'][0])}–{_fmt(be['ci'][1])}] → G12 {imp['G12']['grade']}; "
          f"β on I_peak {_fmt(imp['beta_I_peak']['beta'])}. Recovery N-IMP-1: **{_fmt(imp['G13']['value'])}** → "
          f"G13 {imp['G13']['grade']} (v1.4: G12 β 0.29, recovery as in docs/v1.4/lab/RESULTS.md).", ""]
    absorbed = {}
    for k in ("IMP-1", "IMP-1s", "IMP-5"):
        rows = [r.get("absorbed") or {} for r in sc[k]["per_seed"]]
        absorbed[k] = {c: V._med([r.get(c) for r in rows]) for c in sorted({c for r in rows for c in r})}
    cls = sorted({c for v in absorbed.values() for c in v})
    L += ["Who absorbed the probe (median shares per class):", "",
          "| class | " + " | ".join(f"N-{k}" for k in absorbed) + " |", "|---|" + "---|" * len(absorbed)]
    for c in cls:
        L.append(f"| {c} | " + " | ".join(_fmt(absorbed[k].get(c), 0) for k in absorbed) + " |")
    b["absorbed"] = absorbed
    o, rec = PRE_PROBE_FIX, imp.get("recovery") or {}
    L += ["", "**Impact re-run after the probe fix (A9).** A8 ran the impact set with the probe placed before the "
          "retail crowd and the LPs, so N-IMP-* was not the N-C market plus a probe. The probe is now the last "
          "agent; N-IMP-* were re-run (N-C fingerprints unchanged on 20/20 seeds). Before → after:", "",
          "| quantity | A8 (before fix) | A9 (after fix) |", "|---|---|---|",
          f"| noise floor I_end / I_perm (bps) | {_fmt(o['noise_I_end'])} / {_fmt(o['noise_I_perm'])} | "
          f"{_fmt(imp['noise_floor']['I_end'])} / {_fmt(imp['noise_floor']['I_perm'])} |",
          f"| β on I_end [CI] | {_fmt(o['beta'])} [{_fmt(o['ci'][0])}–{_fmt(o['ci'][1])}] | "
          f"{_fmt(be['beta'])} [{_fmt(be['ci'][0])}–{_fmt(be['ci'][1])}] |",
          f"| G12 | {o['G12']} | {imp['G12']['grade']} |",
          f"| β on I_peak | {_fmt(o['beta_peak'])} | {_fmt(imp['beta_I_peak']['beta'])} |",
          f"| recovery N-IMP-1 / N-IMP-5 | {_fmt(o['rec1'])} / {_fmt(o['rec5'])} | "
          f"{_fmt((rec.get('IMP-1') or {}).get('median'))} / {_fmt((rec.get('IMP-5') or {}).get('median'))} |",
          f"| G13 | {o['G13']} | {imp['G13']['grade']} |"]
    return L


def _component_lines() -> List[str]:
    L = ["| component (10 seeds, normal day / synthetic_ou) | σ1m bps | vol ratio | CS | u_ratio | kurt | "
         "spread ratio (S2) | retail % | MM P&L $ |", "|---|---|---|---|---|---|---|---|---|"]
    for name in ("a-env", "a-retail", "a-lp"):
        p = DOC / f"summary_{name}.json"
        if not p.exists():
            continue
        s = json.loads(p.read_text(encoding="utf-8"))["summaries"]
        for lab_ in s:
            c, j = s[lab_]["C"] or {}, s[lab_]["S2"] or {}
            L.append(f"| {lab_} ({name}) | {_fmt(c.get('sigma_1m_bps'), 2)} | {_fmt(c.get('vol_ratio_price_value'), 2)} | "
                     f"{_fmt(c.get('cs'), 3)} | {_fmt(c.get('u_ratio'), 2)} | {_fmt(c.get('kurt'), 1)} | "
                     f"{_fmt(j.get('spread_jump_ratio'), 2)} | {_fmt(c.get('retail_share'), 1)} | "
                     f"{_fmt(c.get('mm_pnl_group_median'), 0)} |")
    return L


def _sweep_lines() -> List[str]:
    p = DOC / "summary_a-sweep.json"
    if not p.exists():
        return ["(summary_a-sweep.json missing)"]
    s = json.loads(p.read_text(encoding="utf-8"))
    L = [f"A7 swept 16 designs × C/S2 × 5 seeds (160 runs) and refined 4 (40 runs); full tables, the "
         f"selection printout and main effects in `RESULTS_a-sweep.md`. Sweep winner {s['winner']}; final "
         f"(after refinement) **{s['final_winner']}**.", "", "Refinement selection printout:", "", "```"]
    L += (s.get("refinement") or {}).get("selection") or s["selection"]
    return L + ["```"]


def _expectations(b) -> List[Dict[str, str]]:
    C, imp = b["C"]["N-C"], b["impact"] or {}
    comp = {}
    for name in ("a-env", "a-retail", "a-lp"):
        p = DOC / f"summary_{name}.json"
        if p.exists():
            s = json.loads(p.read_text(encoding="utf-8"))["summaries"]
            comp[name] = (s["P0 (v1.4)"], s[name])
    sw = json.loads((DOC / "summary_a-sweep.json").read_text(encoding="utf-8")) if (DOC / "summary_a-sweep.json").exists() else {}
    out = []

    def add(eid, text, measured, ok):
        out.append({"id": eid, "expectation": text, "measured": measured,
                    "verdict": "n/a" if ok is None else ("CONFIRMED" if ok else "NOT CONFIRMED")})

    if "a-env" in comp:
        e = comp["a-env"][1]["C"]
        s1, vr = e.get("sigma_1m_bps"), e.get("vol_ratio_price_value")
        add("E-A1", "living_v1 alone: σ1m ≈ 3 bps, vol ratio ≈ 0.5",
            f"a-env σ1m {_fmt(s1, 2)} bps, vol ratio {_fmt(vr, 2)}",
            None if s1 is None else (2.0 <= s1 <= 4.0 and 0.35 <= vr <= 0.65))
    if "a-retail" in comp:
        p0, e = comp["a-retail"][0]["C"], comp["a-retail"][1]["C"]
        eff = {}
        designs = sw.get("designs") or []
        for k in ("cs", "u_ratio"):
            hi = [d["C"].get(k) for d in designs if d["dials"]["k"] == 3 and d["C"].get(k) is not None]
            lo = [d["C"].get(k) for d in designs if d["dials"]["k"] == 1 and d["C"].get(k) is not None]
            eff[k] = float(np.mean(hi) - np.mean(lo)) if hi and lo else None
        ok = all(v is not None for v in (e.get("cs"), p0.get("cs"), e.get("u_ratio"), p0.get("u_ratio"), eff["cs"])) and \
            e["cs"] > p0["cs"] and e["u_ratio"] > p0["u_ratio"] and eff["cs"] > 0
        add("E-A2", "crowd alone raises CS and the U-shape; κ_v 3 more than 1",
            f"a-retail CS {_fmt(e.get('cs'))} vs P0 {_fmt(p0.get('cs'))}; u {_fmt(e.get('u_ratio'), 2)} vs "
            f"{_fmt(p0.get('u_ratio'), 2)}; sweep effect κ_v 3−1 on CS {_fmt(eff['cs'])}, on u {_fmt(eff['u_ratio'])}", ok)
    if "a-lp" in comp:
        r = comp["a-lp"][1]["S2"].get("spread_jump_ratio") if comp["a-lp"][1]["S2"] else None
        add("E-A3", "LPs alone cut the post-jump spread ratio below 5", f"a-lp spread_jump_ratio {_fmt(r, 2)}",
            None if r is None else r < 5)
    vr = C.get("vol_ratio_price_value")
    add("E-A4", "combined: A-T5 rises toward 0.9 (v1.4 0.49)", f"N-C vol ratio {_fmt(vr, 2)}",
        None if vr is None else vr >= 0.9)
    k = C.get("kurt")
    add("E-A5", "excess kurtosis ≥ 3", f"N-C {_fmt(k, 1)}", None if k is None else k >= 3)
    mm, fi, rt = C.get("mm_pnl_group_median"), C.get("fund_pnl_total"), C.get("retail_pnl_total")
    add("E-A6", "MMs earn a small positive P&L; informed profit; retail loses on average",
        f"MM group ${_fmt(mm, 0)}, informed ${_fmt(fi, 0)}, retail ${_fmt(rt, 0)} (N-C medians)",
        None if None in (mm, fi, rt) else (mm > 0 and fi > 0 and rt < 0))
    be = (imp.get("beta_I_end") or {}).get("beta")
    add("E-A7", "impact β moves toward 0.5–0.7 (v1.4 0.29)", f"β {_fmt(be)}", None if be is None else 0.5 <= be <= 0.7)
    w = C.get("wall_time_s")
    add("E-A8", "wall time ≤ 40 s per day", f"median {_fmt(w, 1)} s over all 240 runs (2 workers)",
        None if w is None else w <= 40)
    st = C.get("stop_trigger_share_pct")
    add("E-A9", "stop-losses trigger for < 5% of stop users per normal day", f"N-C median {_fmt(st, 2)}%",
        None if st is None else st < 5)
    t = b["r4a"]["targets"]
    fails = [kk for kk, v in t.items() if v["status"] != "PASS"]
    a4 = t["A-T4"]
    add("E-A10", "A-T4 (VR(5)) is the most fragile target",
        f"A-T4 {a4['status']} (VR(5) {_fmt(a4['checks'][0]['value'])}); targets failing: {', '.join(fails) or 'none'}",
        fails == ["A-T4"] if fails else None)
    return out


def _hour(ns) -> float:
    """Absolute sim-clock ns -> hour of day (the sim day is a naive date at 00:00)."""
    return (int(ns) % 86_400_000_000_000) / 3.6e12


# ── figures ──────────────────────────────────────────────────────────────

def figures(b) -> List[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PAL, GREY, INK, MUTED = L14.PAL, L14.GREY, L14.INK, L14.MUTED
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})
    made = []
    col = {"PASS": "#0ca30c", "FAIL": "#e34948"}

    # a8_scorecard.png: the R4a scorecard (confirmation) and the per-day-type screens
    ids = [t["id"] for t in R.R4A_TARGETS] + [x["id"] for x in R.R4A_LIMITS]
    rows = [("confirmation (N-C, S2, S2n, D-mix)", {**b["r4a"]["targets"], **b["r4a"]["limits"]})] + \
        [(f"{c} only", {**sc["targets"], **sc["limits"]}) for c, sc in b["per_day"].items()]
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(rows) + 1.3))
    for i, (_, al) in enumerate(rows):
        for j, k in enumerate(ids):
            stt = al[k]["status"]
            ax.add_patch(matplotlib.patches.FancyBboxPatch((j + 0.06, i + 0.08), 0.88, 0.84,
                                                           boxstyle="round,pad=0,rounding_size=0.08",
                                                           color=col.get(stt, "#c3c2b7"), alpha=0.85))
            ax.text(j + 0.5, i + 0.5, {"PASS": "✓", "FAIL": "✗"}.get(stt, "–"), ha="center", va="center",
                    color="white", fontsize=11, fontweight="bold")
    ax.set_xlim(0, len(ids))
    ax.set_ylim(len(rows), 0)
    ax.set_xticks([j + 0.5 for j in range(len(ids))])
    ax.set_xticklabels(ids, rotation=45, ha="right")
    ax.set_yticks([i + 0.5 for i in range(len(rows))])
    ax.set_yticklabels([r[0] for r in rows])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title(f"R4a scorecard of {lab.SELECTED} (✓ pass, ✗ fail, – not judged on that config alone)",
                 fontsize=9, loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "a8_scorecard.png", dpi=130)
    plt.close(fig)
    made.append("a8_scorecard.png")

    # a8_daytypes.png: seed 42 of calm / normal / volatile: mid and value, stress shaded, news marked
    fig, axes = plt.subplots(3, 1, figsize=(11, 8.2), sharex=True)
    for ax, cid in zip(axes, ("D-calm", "N-C", "D-volatile")):
        m = RL.load_metrics(ROOT, cid, 42)
        p = ROOT / cid / "42" / "series.npz"
        if not m or not p.exists():
            ax.set_title(f"{cid}: seed 42 missing", loc="left")
            continue
        z = np.load(p)
        t = np.arange(len(z["mid_1s"])) / 3600.0 + 9.5
        info = (m.get("diagnostics") or {}).get("day_info") or {}
        for s0, s1 in info.get("stress_episodes") or []:  # absolute ns (sim clock) -> hour of day
            ax.axvspan(_hour(s0), _hour(s1), color="#fde6c8", zorder=0)
        ax.plot(t, z["val_1s"] / 100.0, color=GREY, lw=1.0, label="value (hidden)")
        ax.plot(t, z["mid_1s"] / 100.0, color=PAL[0], lw=1.2, label="mid")
        news = info.get("news") or []
        for n in news:
            tn = _hour(n[0])
            yi = int(np.clip((tn - 9.5) * 3600, 0, len(t) - 1))
            up = n[3] > 0
            ax.plot(tn, z["mid_1s"][yi] / 100.0, marker="^" if up else "v", color=PAL[2] if up else PAL[1],
                    ms=8, mec="white", mew=1, zorder=4)
        ax.set_title(f"{cid} — day type {info.get('day_type')}, seed 42; {len(news)} information news "
                     f"(▲ positive, ▼ negative), {len(info.get('stress_episodes') or [])} stress episodes (shaded)",
                     fontsize=9, loc="left", color=INK)
        ax.set_ylabel("$")
        ax.grid(color="#e5e4e0", lw=0.8)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    axes[-1].set_xlabel("hour of day")
    fig.tight_layout()
    fig.savefig(FIG / "a8_daytypes.png", dpi=130)
    plt.close(fig)
    made.append("a8_daytypes.png")

    s14 = json.loads((RL.DOC_V14 / "summary.json").read_text(encoding="utf-8"))["scenarios"]
    # a8_jump_response.png
    fig, ax = plt.subplots(figsize=(8, 4))
    for c, cid, ref in ((PAL[0], "N-S2", "P0-S2"), (PAL[1], "N-S2n", "P0-S2n")):
        cv = (b["scen"].get(cid) or {}).get("curve")
        if cv:
            ax.plot(np.array(cv["t_min"]), cv["median"], color=c, lw=2, label=f"{cid} ({cv['n']} seeds)")
        rv = (s14.get(ref) or {}).get("curve")
        if rv:
            ax.plot(np.array(rv["t_min"]), rv["median"], color=c, lw=1.5, ls="--", alpha=0.7, label=f"v1.4 {ref}")
    ax.axhline(1.0, color=MUTED, lw=0.8)
    ax.axvline(0.0, color=MUTED, lw=0.8)
    ax.set_xlim(-5, 60)
    ax.set_xlabel("minutes after the ±2% value jump (11:00)")
    ax.set_ylabel("share of the jump priced in (median)")
    ax.grid(color="#e5e4e0", lw=0.8)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"Pricing of a ±2% value jump: {lab.SELECTED} vs v1.4 P0", fontsize=9, loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "a8_jump_response.png", dpi=130)
    plt.close(fig)
    made.append("a8_jump_response.png")

    # a8_impact_curve.png
    fig, ax = plt.subplots(figsize=(8, 4))
    for c, k in zip(PAL, ("IMP-1", "IMP-1s", "IMP-5")):
        cv = (b["imp_scen"].get(k) or {}).get("curve_I")
        if cv:
            ax.plot(np.array(cv["t_min"]), cv["median"], color=c, lw=2, label=f"N-{k} ({cv['n']} seeds)")
    rv = (s14.get("P0-IMP-1") or {}).get("curve_I")
    if rv:
        ax.plot(np.array(rv["t_min"]), rv["median"], color=GREY, lw=2, ls="--", label="v1.4 P0-IMP-1")
    ax.axvspan(0, 5, color="#f0efec", zorder=0)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("minutes after the probe start (11:00; probe runs 5 min, shaded)")
    ax.set_ylabel("impact I (bps, against the trader; median)")
    ax.grid(color="#e5e4e0", lw=0.8)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"Price impact of a 5-minute probe: {lab.SELECTED} vs v1.4 P0", fontsize=9, loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "a8_impact_curve.png", dpi=130)
    plt.close(fig)
    made.append("a8_impact_curve.png")
    return made


REG_CONFIGS = ("D-mix", "N-C", "N-S2", "N-S2n", "N-IMP-1")
REG_SCEN = ("N-S2", "N-S2n", "N-IMP-1", "N-IMP-1s", "N-S4")


def write_lab_summary(b: Dict[str, Any]) -> None:
    """docs/v1.5/lab/summary.json in the LabSummary format (served by /api/lab/summary from A9,
    and the stored baseline of the v1.5 regression set) with the R4a scorecard as "r4a"; and
    docs/v1.5/lab/reference_hashes.json (seed-42 D-mix full-day fingerprint of this campaign)."""
    configs = {c: RL.config_block(ROOT, c, SEEDS, MIN_SEEDS) for c in REG_CONFIGS}
    scen = {c: RL.scenario_block(ROOT, c, SEEDS, MIN_SEEDS) for c in REG_SCEN}
    imp = b["impact"]
    rows = L14.runs(ROOT, "N-C", SEEDS)
    out = {
        "spec": "FinVerse spec v1.5 A8 (R4a confirmation of the selected design)",
        "generated": date.today().isoformat(),
        "seeds": list(SEEDS),
        "min_valid_seeds": MIN_SEEDS,
        "bands": R.BANDS,
        "baseline_config": "D-mix",
        "baseline_label": (f"The v1.5 default market {lab.SELECTED}: living_v1 value (auto day type, auto news), "
                           "60 informed fundamentalists D-60fl2M (informed_budget_v2), 12 momentum EKF, 1,500 retail "
                           "traders (κ_v 3), 2 market makers of $5M (ours), budget on, full day"),
        "configs": {k: v for k, v in configs.items() if v},
        "scenarios": {k: v for k, v in scen.items() if v},
        "impact": None if not imp else {"G12": imp["G12"], "G13": {"value": imp["G13"]["value"], "grade": imp["G13"]["grade"]},
                                        "sizes_note": "beta over IMP-0.1, IMP-0.5, IMP-1, IMP-5 (spec v1.5 A6.2)"},
        "r4a": {"targets": b["r4a"]["targets"], "limits": b["r4a"]["limits"], "config": f"{lab.SELECTED} (N-C, D-mix)",
                "seeds": len(rows), "engine": sorted({r["engine_version"] for r in rows}),
                "date": sorted({r["date"] for r in rows})},
    }
    (DOC / "summary.json").write_text(json.dumps(RL._jsonable(out), separators=(",", ":")), encoding="utf-8")
    m42 = RL.load_metrics(ROOT, "D-mix", 42)
    if m42:
        fp = m42["fingerprint"]
        ref = {"spec": "v1.5 A9.3 (regression re-baselined on the new default market)",
               "recorded": date.today().isoformat(),
               "how": "the a-confirm D-mix seed-42 full-day run (api.lab.lab_config), fingerprint as in metrics.json",
               "runs": {"D-mix/42": {"execs": fp["execs"], "holdings": fp["holdings"], "n_execs": fp["n_execs"],
                                     "note": f"engine {m42['engine_version']}"}}}
        (DOC / "reference_hashes.json").write_text(json.dumps(ref, indent=2), encoding="utf-8")


def report(engine: str) -> str:
    b = build()
    sc = b["r4a"]
    judged = list(sc["targets"].values()) + list(sc["limits"].values())
    fails = [x["id"] for x in judged if x["status"] != "PASS"]
    ok = not fails
    imp_lines = _impact_lines(b)
    exp = _expectations(b)
    figs = figures(b)
    C = b["C"]["N-C"]
    run_eng = sorted({json.loads(f.read_text(encoding="utf-8")).get("engine_version", "?")
                      for cid in lab.CAMPAIGNS["a-confirm"] for f in (ROOT / cid).glob("*/metrics.json")})
    L = ["# R4a results: the living market (spec v1.5 Part A, A8 / A9.2)", "",
         f"Runs on engine `{', '.join(run_eng)}` (report written by `{engine}`); date {date.today().isoformat()}; selected design **{lab.SELECTED}** (A7) = 2 LPs of $5M, "
         "1,500 retail traders, κ_v 3, P0's 60 informed (D-60fl2M, informed_budget_v2) and 12 momentum agents, "
         "living_v1 value with auto news, budget L = 2. Confirmation campaign a-confirm (A9.1): 240 runs. "
         "Medians over seeds; scenario rows are treated minus N-C of the same seed.", "",
         f"## Verdict (A8.4): {'ALL PASS — continue to Part B' if ok else 'FAIL — STOP after A9.2 and report to the owner'}",
         "", f"Failing: {', '.join(fails) or 'none'}. Targets passed {sc['n_targets_passed']}/12.", "",
         "## R4a scorecard (A8.1 targets, A8.2 limits)", "", "![scorecard](figures/a8_scorecard.png)", ""] + \
        _scorecard_lines(sc) + \
        ["", f"L4 detail: invariant flags failing in any of the 240 runs: {C.get('flags_failing') or 'none'} "
         f"(informed_bounds failing in {C.get('informed_bounds_fail_runs')} runs; kept for information, the budget "
         f"rule is judged by informed_budget — DECISIONS A7). L5: median wall time {_fmt(C.get('wall_time_s'), 1)} s "
         f"(2 workers; goal ≤ 30 s), median peak memory {_fmt(C.get('peak_mem_mb_all'), 0)} MB.", "",
         "## Why it fails (evidence)" if not ok else "## Margins", ""]
    for x in judged:
        if x["status"] != "PASS":
            L.append(f"- **{x['id']}** {x['label']}: " + "; ".join(
                f"{_chk(c)} → {c['result']}" for c in x["checks"]))
    L += ["", "## Per day type (A8.3)", "", "![day types](figures/a8_daytypes.png)", ""] + _day_lines(b["C"]) + \
         ["", "Screened targets and limits on each day-type config alone (no jump scopes; – = not judged):", ""] + \
         _per_day_grid(b["per_day"]) + \
         ["", "## Scenarios: ±2% value jump and hype news (normal day)", "", "![jump](figures/a8_jump_response.png)", ""] + \
         _scenario_lines(b) + \
         ["", "## Impact (A6.2 set, four sizes)", "", "![impact](figures/a8_impact_curve.png)", ""] + imp_lines + \
         ["", "## Each component alone (A3.7, A4.5, A5.5)", ""] + _component_lines() + \
         ["", "Details: `RESULTS_a-env.md`, `RESULTS_a-retail.md`, `RESULTS_a-lp.md`.", "",
          "## Sweep and selection (A7)", ""] + _sweep_lines() + \
         ["", "## Pre-registered expectations E-A1..E-A10 (A10)", "", "| id | expectation | measured | verdict |",
          "|---|---|---|---|"] + [f"| {e['id']} | {e['expectation']} | {e['measured']} | {e['verdict']} |" for e in exp] + \
         ["", "## Completeness", "", L14.completeness(ROOT, lab.CAMPAIGNS["a-confirm"], SEEDS),
          "", "(D-calm and D-volatile run on the first 10 lab seeds only, A9.1.)", ""]
    out = {"engine": engine, "run_engines": run_eng, "date": date.today().isoformat(), "design": lab.SELECTED, "all_pass": ok, "failing": fails,
           "r4a": sc, "C": b["C"], "S2": b["S2"], "S2n": b["S2n"], "MIX": b["MIX"], "per_day": b["per_day"],
           "impact": b["impact"], "absorbed": b.get("absorbed"), "expectations": exp, "figures": figs,
           "S4": {k: ((b["scen"].get("N-S4") or {}).get("stats", {}).get(k) or {}).get("median")
                  for k in ("R_peak", "t_peak", "t_half_rev", "R_60")}}
    DOC.mkdir(parents=True, exist_ok=True)
    write_lab_summary(b)
    (DOC / "summary_a-confirm.json").write_text(json.dumps(RL._jsonable(out), indent=1), encoding="utf-8")
    md = "\n".join(L) + "\n"
    (DOC / "RESULTS_A.md").write_text(md, encoding="utf-8")
    return md

"""Realism-lab campaigns of FinVerse spec v1.5 (R4).

Called by scripts/realism_lab.py (the same resumable runner: one process per run).
Runs go to runs/_lab_v15/<config>/<seed>/, reports to docs/v1.5/lab/.

    python scripts/realism_lab.py --campaign a-env --workers 3     # A3.7: living_v1 alone
    python scripts/realism_lab.py --campaign a-retail --workers 3  # A4.5: retail crowd alone
    python scripts/realism_lab.py --campaign a-lp --workers 3      # A5.5: our market makers alone
    python scripts/realism_lab.py --campaign a-sweep --workers 2   # A7: 16 designs x C/S2 x 5 seeds
    python scripts/realism_lab.py --campaign a-sweep-r --workers 2 # A7 refinement (only if needed)
    python scripts/realism_lab.py --campaign a-confirm --workers 2 # A8: confirmation, 240 runs + RESULTS_A.md

Component campaigns run on the first 10 lab seeds, each with the same-seed v1.4 P0
reference (P0-C, P0-S2 rerun on this engine) and C + S2 configs: T5/T6 (and E-A3) need
the +2% jump, which the spec's "10 runs" count leaves out (DECISIONS A3).
"""

import json
import math
import time
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np

import lab_v14 as L14
import realism_lab as RL
from api import lab, realism as R

ROOT = RL.REPO / "runs" / "_lab_v15"
DOC = RL.REPO / "docs" / "v1.5" / "lab"
COMPONENT_SEEDS = lab.SEEDS[:10]
MM_CLASSES = R.MM_CLASSES

COMPONENTS = {
    "a-env": {"title": "A3.7 living_v1 alone (P0 + living_v1, normal day, auto news)",
              "configs": ["A-ENV-C", "A-ENV-S2"]},
    "a-retail": {"title": "A4.5 retail crowd alone (P0 with the crowd instead of NoiseAgents, N_r 500, kappa_v 1)",
                 "configs": ["A-RET-C", "A-RET-S2"]},
    "a-lp": {"title": "A5.5 our market makers alone (P0 with 2 LPs of $5M instead of the ABIDES MMs)",
             "configs": ["A-LP-C", "A-LP-S2"]},
}
REF = ["P0-C", "P0-S2"]

V15_KEYS = ["sigma_1m_bps", "day_rv_pct", "u_ratio", "ps", "skew", "retail_share", "mm_share",
            "mm_inv_max_abs", "mm_inv_end_max_abs", "info_news_n", "info_news_f10", "info_news_uplift"]


def _med(xs) -> Optional[float]:
    return L14._med(xs)


def _group_pnl(r: Dict[str, Any], classes) -> Optional[float]:
    cl = r["sanity"]["classes"]
    vals = [cl[c]["pnl_vs_hold_total"] for c in classes if c in cl]
    return float(sum(vals)) if vals else None


def config_summary(cid: str, seeds) -> Dict[str, Any]:
    """Medians over seeds of a no-trigger config (the v1.4 C scope plus v1.5 keys)."""
    rows = L14.runs(ROOT, cid, seeds)
    if not rows:
        return {"n_seeds": 0}
    out = L14.c_summary(rows, rows)
    ms = [r["metrics"] for r in rows]
    for k in V15_KEYS:
        out[k] = _med([m.get(k) for m in ms])
    out["mm_pnl_group_median"] = _med([_group_pnl(r, MM_CLASSES) for r in rows])
    for cls, tag in (("RetailTraderAgent", "retail"), ("NoiseAgent", "noise"), ("MomentumEKFAgent", "mom")):
        out[f"{tag}_pnl_total"] = _med([r["sanity"]["classes"].get(cls, {}).get("pnl_vs_hold_total") for r in rows])
        out[f"{tag}_pnl_median"] = _med([r["sanity"]["classes"].get(cls, {}).get("pnl_vs_hold_median") for r in rows])
    out["day_rv_regime_spread"] = R.regime_spread([m.get("day_rv_pct") for m in ms])
    sc = R.scorecard(ms, min_seeds=max(5, len(seeds) // 2))
    out["grades"] = {g: sc[g]["grade"] for g in sorted(sc)}
    return out


ROWS = [  # (label, scope, key, digits)
    ("G1 sigma 1 min (bps)", "C", "sigma_1m_bps", 3),
    ("day realised vol (%)", "C", "day_rv_pct", 3),
    ("T1 ac1", "C", "ac1", 3),
    ("T2 VR(5)", "C", "vr5", 4),
    ("T3 vol ratio 1 min", "C", "vol_ratio_price_value", 3),
    ("vol ratio 5 min", "C", "vol_ratio_5m", 3),
    ("vol ratio 15 min", "C", "vol_ratio_15m", 3),
    ("vol ratio 60 min", "C", "vol_ratio_60m", 3),
    ("T4 vv_corr", "C", "vv_corr", 3),
    ("G5 clustering CS", "C", "cs", 3),
    ("G5 PS", "C", "ps", 3),
    ("G6 excess kurtosis", "C", "kurt", 3),
    ("U-shape u_ratio", "C", "u_ratio", 3),
    ("spread median (bps)", "C", "spread_med_bps", 3),
    ("spread p95 (bps)", "C", "spread_p95_bps", 3),
    ("shares per day", "C", "shares_executed", 3),
    ("max |mid - value| ($)", "C", "max_abs_gap", 3),
    ("regime contrast (per day)", "C", "regime_contrast", 3),
    ("retail share (%)", "C", "retail_share", 3),
    ("MM share (%)", "C", "mm_share", 3),
    ("MM max |inventory| (sh)", "C", "mm_inv_max_abs", 3),
    ("T7 informed P&L total ($)", "C", "fund_pnl_total", 3),
    ("T7 informed P&L median ($)", "C", "fund_pnl_median", 3),
    ("MM group P&L ($)", "C", "mm_pnl_group_median", 3),
    ("noise P&L total ($)", "C", "noise_pnl_total", 3),
    ("retail P&L total ($)", "C", "retail_pnl_total", 3),
    ("info news f_10 (median)", "C", "info_news_f10", 3),
    ("info news volume uplift", "C", "info_news_uplift", 3),
    ("T5 volume uplift (S2)", "S2", "volume_uplift", 3),
    ("T6 spread_jump_ratio (S2)", "S2", "spread_jump_ratio", 3),
    ("T6 one-sided share (S2)", "S2", "one_sided_share_jump", 3),
    ("t90 of the jump (min)", "S2", "t90", 3),
    ("wall time (s)", "C", "wall_time_s", 3),
]


def _cell(sumc, sumj, scope, key, d):
    src = sumc if scope == "C" else sumj
    if not src:
        return "—"
    return L14._fmt(src.get(key), d)


def report_component(name: str, engine: str) -> str:
    comp = COMPONENTS[name]
    seeds = COMPONENT_SEEDS
    pairs = [("P0 (v1.4)", REF[0], REF[1]), (name, comp["configs"][0], comp["configs"][1])]
    sums = {}
    for label, c, j in pairs:
        sums[label] = (config_summary(c, seeds), L14.jump_summary(ROOT, j, seeds, max(5, len(seeds) // 2)))
    L = [f"# {comp['title']}", "",
         f"Spec v1.5; engine `{engine}`; seeds {seeds} (10); date {date.today().isoformat()}. "
         "Medians over seeds; jump rows are treated (S2, +2% value jump at 11:00) minus the same seed's C.", "",
         "## Completeness", "", L14.completeness(ROOT, REF + comp["configs"], seeds), "",
         "## Measures vs P0", "",
         "| measure | " + " | ".join(lab_ for lab_, _, _ in pairs) + " |",
         "|---|" + "---|" * len(pairs)]
    for label, scope, key, d in ROWS:
        L.append(f"| {label} | " + " | ".join(_cell(*sums[p[0]], scope, key, d) for p in pairs) + " |")
    L += ["", "## v1.3 scorecard grades (median over the 10 seeds; G2 from the cross-seed sd of day returns)", "",
          "| grade | " + " | ".join(p[0] for p in pairs) + " |", "|---|" + "---|" * len(pairs)]
    gids = sorted(sums[pairs[0][0]][0].get("grades", {}), key=lambda g: int(g[1:]))
    for g in gids:
        L.append(f"| {g} | " + " | ".join(str(sums[p[0]][0].get("grades", {}).get(g, "—")) for p in pairs) + " |")
    DOC.mkdir(parents=True, exist_ok=True)
    (DOC / f"summary_{name}.json").write_text(json.dumps(RL._jsonable(
        {"campaign": name, "engine": engine, "seeds": seeds, "date": date.today().isoformat(),
         "summaries": {k: {"C": v[0], "S2": v[1]} for k, v in sums.items()}}), indent=1), encoding="utf-8")
    md = "\n".join(L) + "\n"
    (DOC / f"RESULTS_{name}.md").write_text(md, encoding="utf-8")
    return md


# A6.2: the R4 impact set. beta is fitted on four sizes again (IMP-0.1 = BUY 600, which
# the v1.4.2 trim dropped), next to the IMP-0 placebo and the IMP-1s sell probe.
IMPACT_SET = ("IMP-0", "IMP-0.1", "IMP-0.5", "IMP-1", "IMP-5", "IMP-1s")
IMPACT_BETA_SIZES = ("IMP-0.1", "IMP-0.5", "IMP-1", "IMP-5")


def impact_configs(prefix: str) -> List[str]:
    """Config ids of the impact set for one market, e.g. prefix "N" -> N-IMP-0 ... N-IMP-1s."""
    return [f"{prefix}-{k}" for k in IMPACT_SET]


def impact_summary(prefix: str, seeds, min_seeds: int) -> Optional[Dict[str, Any]]:
    """Noise floor, beta on the four sizes (G12) and recovery (G13) for one market;
    None until every config of the set has enough valid seeds."""
    scen = {k: RL.scenario_block(ROOT, f"{prefix}-{k}", seeds, min_seeds) for k in IMPACT_SET}
    if not all(scen.values()):
        return None
    return RL.impact_summary(scen, min_seeds)


# ══════════════════════════════════════════════════════════════════════════
# A7 design sweep (16 designs x C/S2 x 5 seeds) and the optional refinement round
# ══════════════════════════════════════════════════════════════════════════
SWEEP_SEEDS = lab.SWEEP_SEEDS
SEL_PATH = DOC / "selection_sweep.json"
# L4: every invariant flag except informed_bounds, which A6.1 keeps for information
# (reducing fills pushed outside the bound by mark-to-market after jumps); the budget rule
# itself is judged by informed_budget (fills that increase exposure). DECISIONS A7.
L4_IGNORED_FLAGS = ("informed_bounds",)


def sweep_summary(rid: str, seeds) -> Dict[str, Any]:
    """5-seed medians of one sweep design: C scope (v1.4 C keys + v1.5 keys), S2 jump
    response; zero_sum, flags and wall time over every run of the design (C and S2)."""
    rows_c = L14.runs(ROOT, rid + "-C", seeds)
    rows_s2 = L14.runs(ROOT, rid + "-S2", seeds)
    allr = rows_c + rows_s2
    C = config_summary(rid + "-C", seeds)
    C["zero_sum_all_zero"] = 1.0 if allr and all(r["zero_sum_ok"] and r["zero_sum_cents"] == 0 for r in allr) else 0.0
    bad = sorted({k for r in allr for k, v in r["flags"].items() if not v})
    C["flags_failing"] = bad
    C["flags_all_ok"] = 1.0 if allr and not [k for k in bad if k not in L4_IGNORED_FLAGS] else 0.0
    C["informed_bounds_fail_runs"] = sum(1 for r in allr if r["flags"].get("informed_bounds") is False)
    C["wall_time_s"] = _med([r["wall_time_s"] for r in allr])
    C["retail_stop_trigger_pct"] = _med([r["metrics"].get("retail_stop_trigger_pct") for r in rows_c])
    S2 = L14.jump_summary(ROOT, rid + "-S2", seeds, min_seeds=1) or {}
    sc = R.r4a_scorecard({"C": C, "S2": S2}, screening=True)
    return {"design": rid, "dials": lab.parse_sweep(rid), "C": C, "S2": S2, "r4a": sc,
            "n_seeds_C": len(rows_c), "n_seeds_S2": len(rows_s2)}


def _chk_txt(c) -> str:
    return f"{c['scope']}.{c['key']}={L14._fmt(c['value'])} {c['op']} {c['threshold']:g} {c['result']}"


def select_sweep(sums: List[Dict[str, Any]], title: str):
    """A7 selection, mechanically. Returns (winner id or None, printout lines)."""
    lims = [x["id"] for x in R.R4A_LIMITS]
    tg = R.R4A_SCREEN_TARGETS
    P = [title, "", f"Step 1 — reject designs failing any limit {', '.join(lims)} (L1 on the normal day only):"]
    kept = []
    for s in sums:
        lim = s["r4a"]["limits"]
        fails = [x for x in lims if lim[x]["status"] != "PASS"]
        if fails:
            det = "; ".join(f"{x}: " + ", ".join(_chk_txt(c) for c in lim[x]["checks"] if c["result"] != "PASS")
                            for x in fails)
            P.append(f"  {s['design']}: REJECTED ({det})")
        else:
            P.append(f"  {s['design']}: kept")
            kept.append(s)
    if not kept:
        P.append("No design passes every limit: step 1 rejects all of them, so the rule names no winner. "
                 "A7 does not cover this case: the owner decides (reported, not resolved here).")
        return None, P
    P += ["", f"Step 2 — number of targets passed among {', '.join(tg)} (A-T3, A-T11 need the day mix; "
          "A-T9 on S2 only):"]
    for s in kept:
        t = s["r4a"]["targets"]
        s["_n"] = sum(t[k]["status"] == "PASS" for k in tg)
        P.append(f"  {s['design']}: {s['_n']} ({', '.join(k for k in tg if t[k]['status'] == 'PASS') or 'none'})")
    best = max(s["_n"] for s in kept)
    tied = [s for s in kept if s["_n"] == best]
    P.append(f"  maximum {best}: {[s['design'] for s in tied]}")
    if len(tied) > 1:
        P += ["", "Step 3 — tie-break: smallest sum of normalised misses over A-T1, A-T2, A-T4, A-T5 "
              "(scales 5 bps, 0.10, 0.45, 0.90), then lower median wall time, then the lexically smallest id:"]
        for s in tied:
            nm = [s["r4a"]["targets"][k].get("norm_miss") for k in R.R4A_MISS_SCALE]
            s["_miss"] = math.inf if any(v is None for v in nm) else float(sum(nm))
            s["_wall"] = s["C"].get("wall_time_s") or math.inf
            P.append(f"  {s['design']}: misses {[L14._fmt(v) for v in nm]} sum {L14._fmt(s['_miss'])}; "
                     f"wall time {L14._fmt(s['_wall'])} s")
        tied.sort(key=lambda s: (s["_miss"], s["_wall"], s["design"]))
    win = tied[0]["design"]
    P += ["", f"Winner: {win}"]
    return win, P


def _all_pass(s) -> bool:
    t, lim = s["r4a"]["targets"], s["r4a"]["limits"]
    return all(t[k]["status"] == "PASS" for k in R.R4A_SCREEN_TARGETS) and all(v["status"] == "PASS" for v in lim.values())


SWEEP_COLS = [  # (header, scope, key, digits)
    ("σ1m bps", "C", "sigma_1m_bps", 2), ("ac1", "C", "ac1", 3), ("VR(5)", "C", "vr5", 3),
    ("vol ratio", "C", "vol_ratio_price_value", 2), ("vv", "C", "vv_corr", 2), ("CS", "C", "cs", 3),
    ("PS", "C", "ps", 3), ("kurt", "C", "kurt", 2), ("upl", "S2", "volume_uplift", 2),
    ("spr ratio", "S2", "spread_jump_ratio", 2), ("1-sided", "S2", "one_sided_share_jump", 3),
    ("inf $ tot", "C", "fund_pnl_total", 0), ("inf $ med", "C", "fund_pnl_median", 0),
    ("MM $ med", "C", "mm_pnl_group_median", 0), ("u", "C", "u_ratio", 2),
    ("spr med", "C", "spread_med_bps", 2), ("spr p95", "C", "spread_p95_bps", 2),
    ("shares", "C", "shares_executed", 0), ("max gap $", "C", "max_abs_gap", 2),
    ("retail %", "C", "retail_share", 1), ("wall s", "C", "wall_time_s", 1),
]


def _sweep_table(sums, winner) -> List[str]:
    L = ["| design | n_lp | W | N_r | κ_v | targets | limits failing | " + " | ".join(h for h, *_ in SWEEP_COLS) + " |",
         "|---|---|---|---|---|---|---|" + "---|" * len(SWEEP_COLS)]
    for s in sums:
        d, sc = s["dials"], s["r4a"]
        lf = [k for k, v in sc["limits"].items() if v["status"] != "PASS"]
        name = f"**{s['design']}**" if s["design"] == winner else s["design"]
        n = sum(sc["targets"][k]["status"] == "PASS" for k in R.R4A_SCREEN_TARGETS)
        cells = [L14._fmt((s[scope] or {}).get(k), dg) for _, scope, k, dg in SWEEP_COLS]
        L.append(f"| {name} | {d['n_lp']} | ${d['W']} | {d['N_r']} | {d['k']} | {n}/{len(R.R4A_SCREEN_TARGETS)} | "
                 f"{', '.join(lf) or '—'} | " + " | ".join(cells) + " |")
    return L


def _target_grid(sums) -> List[str]:
    tg = R.R4A_SCREEN_TARGETS + [x["id"] for x in R.R4A_LIMITS]
    L = ["| design | " + " | ".join(tg) + " |", "|---|" + "---|" * len(tg)]
    for s in sums:
        sc = {**s["r4a"]["targets"], **s["r4a"]["limits"]}
        L.append(f"| {s['design']} | " + " | ".join({"PASS": "✓", "FAIL": "✗"}.get(sc[k]["status"], "?") for k in tg) + " |")
    return L


def _main_effects(sums) -> List[str]:
    """Mean over the 8 designs at the high level of a dial minus the 8 at the low level (descriptive)."""
    keys = [("sigma_1m_bps", "C"), ("vr5", "C"), ("vol_ratio_price_value", "C"), ("kurt", "C"), ("cs", "C"),
            ("spread_jump_ratio", "S2"), ("retail_share", "C"), ("mm_pnl_group_median", "C"), ("spread_med_bps", "C")]
    L = ["| dial (high − low) | " + " | ".join(k for k, _ in keys) + " |", "|---|" + "---|" * len(keys)]
    for dial, (lo, hi) in lab.SWEEP_DIALS.items():
        cells = []
        for k, scope in keys:
            a = [x for x in ((s[scope] or {}).get(k) for s in sums if s["dials"][dial] == hi) if x is not None]
            b = [x for x in ((s[scope] or {}).get(k) for s in sums if s["dials"][dial] == lo) if x is not None]
            cells.append(L14._fmt(float(np.mean(a) - np.mean(b)), 3) if a and b else "—")
        L.append(f"| {dial}: {hi} vs {lo} | " + " | ".join(cells) + " |")
    return L


def report_sweep(engine: str, refine_winner: Optional[str] = None) -> str:
    seeds = SWEEP_SEEDS
    designs = lab.SWEEP_DESIGNS
    sums = [sweep_summary(d, seeds) for d in designs]
    winner, P = select_sweep(sums, "Selection rule (spec v1.5 A7), applied to 5-seed medians (seeds 42, 7, 1, 2, 3).")
    out = {"engine": engine, "seeds": seeds, "date": date.today().isoformat(), "designs": sums,
           "winner": winner, "selection": P}
    cfgs = [f"{d}-{c}" for d in designs for c in ("C", "S2")]
    L = ["# A7 design sweep (spec v1.5 Part A7)", "",
         f"Engine `{engine}`; seeds {seeds}; date {date.today().isoformat()}. Population: P0's informed "
         "(D-60fl2M, informed_budget_v2) and momentum agents, living_v1 (day type normal, auto news), retail "
         "crowd instead of NoiseAgents, LPs instead of the ABIDES MMs, budget L = 2. Medians over the 5 seeds; "
         "jump columns (S2, +2% value jump at 11:00) are treated minus the same seed's C. "
         "Design id R-<n_lp><W><N_r><κ_v>.", "",
         "## Designs (bold = selected)", ""] + _sweep_table(sums, winner) + \
        ["", "## Targets and limits per design (✓ pass, ✗ fail)", ""] + _target_grid(sums) + \
        ["", "## Selection printout", "", "```"] + P + ["```", "",
         "## Dial main effects (descriptive; mean of 8 designs at the high level minus the low level)", ""] + \
        _main_effects(sums)
    win_s = next((s for s in sums if s["design"] == winner), None)
    out["refinement_needed"] = None
    if win_s is not None:
        need = not _all_pass(win_s)
        fails = [k for k in R.R4A_SCREEN_TARGETS if win_s["r4a"]["targets"][k]["status"] != "PASS"] + \
            [k for k, v in win_s["r4a"]["limits"].items() if v["status"] != "PASS"]
        L += ["", "## Refinement", "",
              (f"The winner fails {', '.join(fails)}, so the refinement round runs (A7): "
               f"{', '.join(lab.sweep_refinement(winner))}." if need else
               "The winner passes every screened target and limit: no refinement round.")]
        out["refinement_needed"] = need
        out["winner_fails"] = fails
        L += ["", f"Winner invariant flags failing in any run: {win_s['C'].get('flags_failing') or 'none'} "
              f"(runs with informed_bounds failing: {win_s['C'].get('informed_bounds_fail_runs')}); "
              f"retail stop-loss trigger share {L14._fmt(win_s['C'].get('retail_stop_trigger_pct'))}% of stop users."]
    L += ["", "## Completeness", "", L14.completeness(ROOT, cfgs, seeds)]
    out["final_winner"] = winner
    if refine_winner:
        rds = lab.sweep_refinement(refine_winner)
        rs = [s for s in sums if s["design"] == refine_winner] + [sweep_summary(d, seeds) for d in rds]
        w2, P2 = select_sweep(rs, f"Refinement (spec v1.5 A7): the winner {refine_winner} and "
                                  f"{', '.join(rds)}, same seeds, same rule.")
        out["refinement"] = {"designs": rs[1:], "winner": w2, "selection": P2}
        out["final_winner"] = w2
        L += ["", "## Refinement round", ""] + _sweep_table(rs, w2) + ["", "```"] + P2 + ["```", "",
              L14.completeness(ROOT, [f"{d}-{c}" for d in rds for c in ("C", "S2")], seeds)]
        w2s = next((s for s in rs if s["design"] == w2), None)
        if w2s is not None and not _all_pass(w2s):
            L += ["", f"The final design {w2} still fails a screened target or limit: A7 continues with it "
                  "and reports (no further rounds)."]
    L += ["", f"**Selected design: {out['final_winner']}**"]
    DOC.mkdir(parents=True, exist_ok=True)
    SEL_PATH.write_text(json.dumps(RL._jsonable({k: out[k] for k in ("engine", "seeds", "date", "winner",
                                                                         "final_winner")}), indent=1), encoding="utf-8")
    (DOC / "summary_a-sweep.json").write_text(json.dumps(RL._jsonable(out), indent=1), encoding="utf-8")
    md = "\n".join(L) + "\n"
    (DOC / "RESULTS_a-sweep.md").write_text(md, encoding="utf-8")
    return md


def _sweep_winner(a) -> str:
    if a is not None and a.winner:
        return a.winner
    return json.loads(SEL_PATH.read_text(encoding="utf-8"))["winner"]


def campaign_configs(name: str, a=None):
    if name in COMPONENTS:
        return REF + COMPONENTS[name]["configs"], COMPONENT_SEEDS
    if name == "a-sweep":
        return list(lab.CAMPAIGNS["a-sweep"]), SWEEP_SEEDS
    if name == "a-sweep-r":
        lab.register_sweep_refinement(_sweep_winner(a))
        return list(lab.CAMPAIGNS["a-sweep-r"]), SWEEP_SEEDS
    if name == "a-confirm":
        return list(lab.CAMPAIGNS["a-confirm"]), lab.SEEDS
    raise ValueError(f"unknown v1.5 campaign {name!r}")


def main_v15(a, engine: str) -> int:
    configs, seeds = campaign_configs(a.campaign, a)
    if a.seeds:
        seeds = [int(x) for x in a.seeds.split(",")]
    if a.configs:
        configs = a.configs.split(",")
    print(f"engine {engine}; campaign {a.campaign} (v1.5); {len(configs)} configs; {len(seeds)} seeds; "
          f"{a.workers} workers; root {ROOT}", flush=True)
    if "+dirty" in engine:
        print("note: engine_version is +dirty (tracked files have uncommitted changes)")
    failed = []
    if not a.report_only:
        per = {c: lab.CONFIG_SEEDS.get(c, seeds) if not a.seeds else seeds for c in configs}
        per = {c: [s for s in v if s in seeds] or seeds for c, v in per.items()}
        tasks = [(c, s) for c in configs for s in per[c] if a.force or not RL.is_done(ROOT, c, s, engine)]
        total = sum(len(v) for v in per.values())
        print(f"{len(tasks)} runs to do, {total - len(tasks)} already done", flush=True)
        t0 = time.time()
        _, failed = RL.run_all(tasks, ROOT, a.workers, engine)
        print(f"runs finished in {(time.time() - t0) / 60:.1f} min; {len(failed)} failed")
        for key, msg in failed:
            print("  FAILED", key, msg)
    if a.campaign in COMPONENTS:
        report_component(a.campaign, engine)
        print(f"report: {(DOC / f'RESULTS_{a.campaign}.md').relative_to(RL.REPO)}")
    elif a.campaign in ("a-sweep", "a-sweep-r"):
        report_sweep(engine, _sweep_winner(a) if a.campaign == "a-sweep-r" else None)
        print(f"report: {(DOC / 'RESULTS_a-sweep.md').relative_to(RL.REPO)}")
    return 1 if failed else 0

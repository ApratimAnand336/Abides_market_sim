"""Realism-lab campaigns of FinVerse spec v1.5 (R4).

Called by scripts/realism_lab.py (the same resumable runner: one process per run).
Runs go to runs/_lab_v15/<config>/<seed>/, reports to docs/v1.5/lab/.

    python scripts/realism_lab.py --campaign a-env --workers 3     # A3.7: living_v1 alone
    python scripts/realism_lab.py --campaign a-retail --workers 3  # A4.5: retail crowd alone
    python scripts/realism_lab.py --campaign a-lp --workers 3      # A5.5: our market makers alone

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


def campaign_configs(name: str):
    if name in COMPONENTS:
        return REF + COMPONENTS[name]["configs"], COMPONENT_SEEDS
    raise ValueError(f"unknown v1.5 campaign {name!r}")


def main_v15(a, engine: str) -> int:
    configs, seeds = campaign_configs(a.campaign)
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
        md = report_component(a.campaign, engine)
        print(md)
    return 1 if failed else 0

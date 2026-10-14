"""The realism lab's run matrix (FinVerse spec v1.3, Part 5 and Appendix C).

lab_config(config_id, seed) builds the rmsc04_ekf config of one entry through
the same keyword arguments as api.jobs.build_run_config (run_config_kwargs)
plus the scenario switches of spec v1.3 Part 6. RunParams and the dashboard do
not gain these switches in R2.
"""

import hashlib
import json
import re
from typing import Any, Dict, List

from .jobs import run_config_kwargs
from .schema import NewsItem, RunParams

# spec v1.3 §5.0 writes [42, 7, 1, 2, ..., 18] and calls it 20 seeds, but 7
# appears twice (19 distinct). The duplicate is replaced by 19 so the lab has
# 20 distinct seeds and keeps 42 and 7 (DECISIONS.md, 2026-10-12, L2).
SEEDS: List[int] = [42, 7] + [s for s in range(1, 20) if s != 7]
assert len(set(SEEDS)) == len(SEEDS) == 20
T0_OFFSET = "01:30:00"  # 11:00, the event time of S2-S5 and S8
T0_S = 5400  # the same, in seconds after the 09:30 open
V_REF = 600_000  # reference daily volume (shares), spec §5.4
PROBE_DURATION_S = 300
PROBE_CHILD_S = 10

NEWS_POS = ("Company announces record quarterly earnings", 0.9)
NEWS_NEG = ("Regulator opens probe into company accounts", -0.9)
JUMP_UP = {"type": "jump", "at": T0_OFFSET, "pct": 2.0}
JUMP_DOWN = {"type": "jump", "at": T0_OFFSET, "pct": -2.0}
VOL_X3 = {"type": "vol", "start": T0_OFFSET, "end": "02:30:00", "mult": 3.0}


def _probe(side: str, q: int) -> Dict[str, Any]:
    return {"side": side, "quantity": q, "start": T0_OFFSET,
            "duration_s": PROBE_DURATION_S, "child_interval_s": PROBE_CHILD_S}


# id -> definition. params: RunParams fields different from the default
# market; news: [(headline, sentiment)] at T0; extra: new build_config
# keyword arguments (Part 6); baseline: the config compared with on the same
# seed; kind: which §7.3 analysis applies.
CONFIGS: Dict[str, Dict[str, Any]] = {
    "C-DEF": {"campaign": "c1", "label": "default market (S1, quiet day)"},
    "C-V20": {"campaign": "c1", "label": "20 value agents", "params": {"num_value": 20}},
    "S4": {"campaign": "c1", "label": "hype news +0.9", "news": [NEWS_POS],
           "baseline": "C-DEF", "kind": "news", "sentiment": 0.9},
    "S4n": {"campaign": "c1", "label": "hype news -0.9", "news": [NEWS_NEG],
            "baseline": "C-DEF", "kind": "news", "sentiment": -0.9},
    "S2": {"campaign": "c2", "label": "value jump +2%", "extra": {"oracle_events": [JUMP_UP]},
           "baseline": "C-DEF", "kind": "jump", "jump_pct": 2.0},
    "S2n": {"campaign": "c2", "label": "value jump -2%", "extra": {"oracle_events": [JUMP_DOWN]},
            "baseline": "C-DEF", "kind": "jump", "jump_pct": -2.0},
    "S3": {"campaign": "c2", "label": "value jump +2% with headline +0.9",
           "extra": {"oracle_events": [JUMP_UP]}, "news": [NEWS_POS],
           "baseline": "C-DEF", "kind": "jump", "jump_pct": 2.0},
    "S5": {"campaign": "c2", "label": "value volatility x3 11:00-12:00",
           "extra": {"oracle_events": [VOL_X3]}, "baseline": "C-DEF", "kind": "vol"},
    "IMP-0": {"campaign": "c3", "label": "probe BUY 100 (placebo)", "extra": {"probe": _probe("BUY", 100)},
              "baseline": "C-DEF", "kind": "impact"},
    "IMP-0.1": {"campaign": "c3", "label": "probe BUY 600", "extra": {"probe": _probe("BUY", 600)},
                "baseline": "C-DEF", "kind": "impact"},
    "IMP-0.5": {"campaign": "c3", "label": "probe BUY 3,000", "extra": {"probe": _probe("BUY", 3000)},
                "baseline": "C-DEF", "kind": "impact"},
    "IMP-1": {"campaign": "c3", "label": "probe BUY 6,000", "extra": {"probe": _probe("BUY", 6000)},
              "baseline": "C-DEF", "kind": "impact"},
    "IMP-5": {"campaign": "c3", "label": "probe BUY 30,000 (S8)", "extra": {"probe": _probe("BUY", 30000)},
              "baseline": "C-DEF", "kind": "impact"},
    "IMP-1s": {"campaign": "c3", "label": "probe SELL 6,000", "extra": {"probe": _probe("SELL", 6000)},
               "baseline": "C-DEF", "kind": "impact"},
    "C-NULL": {"campaign": "c3-null", "label": "probe with quantity 0", "extra": {"probe": _probe("BUY", 0)}},
    "S6": {"campaign": "c4", "label": "market makers paused 13:00-13:30",
           "extra": {"mm_pause_windows": [("13:00:00", "13:30:00")]}, "baseline": "C-DEF", "kind": "pause"},
    "S7a": {"campaign": "c4", "label": "momentum capital x3", "extra": {"mom_capital_mult": 3.0},
            "baseline": "C-DEF", "kind": "capital"},
    "S7b": {"campaign": "c4", "label": "momentum capital x10", "extra": {"mom_capital_mult": 10.0},
            "baseline": "C-DEF", "kind": "capital"},
    "S7c": {"campaign": "c4", "label": "momentum capital x10 + value jump +2%",
            "extra": {"mom_capital_mult": 10.0, "oracle_events": [JUMP_UP]},
            "baseline": "S7b", "kind": "jump", "jump_pct": 2.0},
}

CAMPAIGNS: Dict[str, List[str]] = {
    "c1": ["C-DEF", "C-V20", "S4", "S4n"],
    "c2": ["S2", "S2n", "S3", "S5"],
    "c3": ["IMP-0", "IMP-0.1", "IMP-0.5", "IMP-1", "IMP-5", "IMP-1s"],
    "c4": ["S6", "S7a", "S7b", "S7c"],
}
CAMPAIGNS["all"] = [c for k in ("c1", "c2", "c3", "c4") for c in CAMPAIGNS[k]]
# spec v1.4 §10.5 (N6): the regression set runs on the default market P0;
# the v1.3 set is kept as REGRESSION_LEGACY (C-DEF/S2/IMP-1 vs docs/v1.3).
REGRESSION_LEGACY = {"seeds": [42, 7, 1], "configs": ["C-DEF", "S2", "IMP-1"], "hash_config": "C-DEF",
                     "doc": "v1.3", "ref_key": "A", "dir": "_lab_regression"}
REGRESSION = {"seeds": [42, 7, 1], "configs": ["P0-C", "P0-S2", "P0-IMP-1"], "hash_config": "P0-C",
              "doc": "v1.4", "ref_key": "P0-C/42", "dir": "_lab_regression_v14"}

# ══════════════════════════════════════════════════════════════════════════
# spec v1.4 (R3), Part 7. Outputs of these campaigns go to runs/_lab_v14 and
# docs/v1.4/lab (CAMPAIGN_ROOT); the v1.3 campaigns keep runs/_lab.
# ══════════════════════════════════════════════════════════════════════════
BUDGET = {"L": 2.0}  # spec v1.4 Part 5
SCREEN_SEEDS: List[int] = [42, 7, 1, 2, 3]  # spec v1.4 §7.3

# §7.2 Campaign b: the v1.3 market + budget (compared with v1.3's C-DEF / S2)
CONFIGS["C-BL"] = {"campaign": "b", "label": "default v1.3 market + budget L=2",
                   "extra": {"abides_budget": BUDGET}}
CONFIGS["S2-BL"] = {"campaign": "b", "label": "value jump +2% + budget L=2",
                    "extra": {"oracle_events": [JUMP_UP], "abides_budget": BUDGET},
                    "baseline": "C-BL", "kind": "jump", "jump_pct": 2.0}
CAMPAIGNS["b"] = ["C-BL", "S2-BL"]

# §7.3 / §7.4 design dials. Code -> level. Round 1 uses the first two levels
# of each dial; round 2 adds the outer ones.
DIAL_N = {"30": 30, "60": 60, "120": 120, "240": 240}
DIAL_T = {"vf": (15.0, 60.0), "f": (60.0, 300.0), "s": (300.0, 1800.0), "vs": (1800.0, 7200.0)}  # T_r, s
DIAL_S = {"vl": (3.0, 10.0), "l": (10.0, 50.0), "h": (50.0, 200.0), "vh": (200.0, 600.0)}  # sigma_r, cents
DIAL_W = {"250k": 25_000_000, "500k": 50_000_000, "2M": 200_000_000, "5M": 500_000_000}  # wealth, cents
DIAL_ORDER = {"N": ["30", "60", "120", "240"], "T": ["vf", "f", "s", "vs"],
              "S": ["vl", "l", "h", "vh"], "W": ["250k", "500k", "2M", "5M"]}
ROUND1 = {"N": ["60", "120"], "T": ["f", "s"], "S": ["l", "h"], "W": ["500k", "2M"]}
# spec v1.4.1 §3.2: an optional learning level suffix, e.g. D-60fl2M-mod
_DESIGN_RE = re.compile(r"^D-(\d+)(vf|vs|f|s)(vl|vh|l|h)(\d+(?:k|M))(?:-(mod|strong))?$")
LEARNING = ("mod", "strong")


def design_id(n: str, t: str, s: str, w: str, l: str = "off") -> str:
    """D-<N><T><S><W>[-<L>], e.g. D-60fl500k (spec v1.4 §7.3) or D-60fl2M-mod (v1.4.1)."""
    return f"D-{n}{t}{s}{w}" + ("" if l == "off" else f"-{l}")


def parse_design(did: str) -> Dict[str, str]:
    m = _DESIGN_RE.match(did)
    if not m:
        raise ValueError(f"not a design id: {did}")
    d = dict(zip("NTSWL", m.groups()))
    d["L"] = d["L"] or "off"
    return d


def design_extra(did: str) -> Dict[str, Any]:
    """build_config keyword arguments of the final population with this design:
    0 ValueAgents, N informed fundamentalists, budget on (spec v1.4 §7.3)."""
    d = parse_design(did)
    return {
        "num_ekf_agents": DIAL_N[d["N"]],
        "fund_mode": "informed",
        "informed_design": {"T_r_range_s": list(DIAL_T[d["T"]]), "sigma_r_range_c": list(DIAL_S[d["S"]]),
                            "wealth_c": DIAL_W[d["W"]]},
        "abides_budget": BUDGET,
    } if d["L"] == "off" else {  # "off" designs keep their v1.4 config hash
        "num_ekf_agents": DIAL_N[d["N"]],
        "fund_mode": "informed",
        "informed_design": {"T_r_range_s": list(DIAL_T[d["T"]]), "sigma_r_range_c": list(DIAL_S[d["S"]]),
                            "wealth_c": DIAL_W[d["W"]], "price_learning": d["L"]},
        "abides_budget": BUDGET,
    }


def _register_design(did: str, campaign: str, s2n: bool = False) -> None:
    CONFIGS[did] = {"campaign": campaign, "label": f"design {did} (no trigger)",
                    "params": {"num_value": 0}, "extra": design_extra(did), "design": did}
    CONFIGS[did + "-S2"] = {"campaign": campaign, "label": f"design {did} + value jump +2%",
                            "params": {"num_value": 0},
                            "extra": {**design_extra(did), "oracle_events": [JUMP_UP]},
                            "baseline": did, "kind": "jump", "jump_pct": 2.0, "design": did}
    if s2n:  # spec v1.4.1 §3.2: the -2% jump as well
        CONFIGS[did + "-S2n"] = {"campaign": campaign, "label": f"design {did} + value jump -2%",
                                 "params": {"num_value": 0},
                                 "extra": {**design_extra(did), "oracle_events": [JUMP_DOWN]},
                                 "baseline": did, "kind": "jump", "jump_pct": -2.0, "design": did}


ROUND1_DESIGNS: List[str] = [design_id(n, t, s, w) for n in ROUND1["N"] for t in ROUND1["T"]
                             for s in ROUND1["S"] for w in ROUND1["W"]]
for _d in ROUND1_DESIGNS:
    _register_design(_d, "s1")
CAMPAIGNS["s1"] = [c for d in ROUND1_DESIGNS for c in (d, d + "-S2")]


def round2_designs(winner: str) -> List[str]:
    """§7.4 round 2: the winner with ONE dial replaced by each of its two new
    outer levels (N 30/240, T_r very fast/very slow, sigma_r very low/very
    high, W $250k/$5M) -> 8 designs."""
    d = parse_design(winner)
    out = []
    for dial in "NTSW":
        for lev in DIAL_ORDER[dial]:
            if lev not in ROUND1[dial]:
                nd = dict(d)
                nd[dial] = lev
                out.append(design_id(nd["N"], nd["T"], nd["S"], nd["W"]))
    return out


# Every design round 2 can reach (a round-1 design with one dial at an outer
# level) is registered up front, so that spawned worker processes know it.
for _d in ROUND1_DESIGNS:
    for _r in round2_designs(_d):
        if _r not in CONFIGS:
            _register_design(_r, "s1r2")


def register_round2(winner: str) -> List[str]:
    """Set CAMPAIGNS["s1r2"] to the 8 round-2 designs of this winner."""
    ds = round2_designs(winner)
    CAMPAIGNS["s1r2"] = [c for d in ds for c in (d, d + "-S2")]
    return ds


# ── spec v1.4.1 §3.2-3.4: learning sweep s2 and the refinement round s2r ──
def design_id_d(d: Dict[str, str]) -> str:
    return design_id(d["N"], d["T"], d["S"], d["W"], d.get("L", "off"))


S2_DESIGNS: List[str] = [design_id(n, t, s, "2M", lv) for n in ("60", "120") for t in ("f", "s")
                         for s in ("l", "h") for lv in LEARNING]
for _d in S2_DESIGNS:
    _register_design(_d, "s2", s2n=True)
CAMPAIGNS["s2"] = [c for d in S2_DESIGNS for c in (d, d + "-S2", d + "-S2n")]
for _d in ROUND1_DESIGNS:  # round-1 designs may need S2n runs in the refinement round
    _register_design(_d, CONFIGS[_d]["campaign"], s2n=True)


def refinement_designs(winner: str) -> List[str]:
    """§3.4: N = 30, N = 240 (other dials unchanged), and W = $5M."""
    d = parse_design(winner)
    return [design_id_d({**d, "N": "30"}), design_id_d({**d, "N": "240"}), design_id_d({**d, "W": "5M"})]


for _d in ROUND1_DESIGNS + S2_DESIGNS:  # registered up front for spawned workers
    for _r in refinement_designs(_d):
        if _r + "-S2n" not in CONFIGS:
            _register_design(_r, "s2r", s2n=True)


def register_refinement(winner: str) -> List[str]:
    """CAMPAIGNS["s2r"]: the 3 refinement designs (C, S2, S2n) plus any of
    the winner's own configs (it may lack S2n runs if it is a round-1 design)."""
    ds = refinement_designs(winner)
    CAMPAIGNS["s2r"] = [c for d in ds for c in (d, d + "-S2", d + "-S2n")] + [winner + "-S2n"]
    return ds


# ── spec v1.4.2 Part 2: trimmed step-down and final campaigns ───────────
# Design D-60fl2M (learning off, D-R3-7), budget on, full day. P<k> = the
# same population with k ValueAgents; P0 is the final market.
P_DESIGN = "D-60fl2M"
STEP_SEEDS: List[int] = SEEDS[:10]  # 42, 7, 1-6, 8, 9 (spec v1.4.2 §2.1)
MM0_SEEDS: List[int] = SEEDS[:5]
CONFIG_SEEDS: Dict[str, List[int]] = {}  # per-config seed lists (default: the campaign's)


def _p_config(cid, label, k, extra=None, campaign="step", **more):
    CONFIGS[cid] = {"campaign": campaign, "label": label, "params": {"num_value": k, **more.pop("params", {})},
                    "extra": {**design_extra(P_DESIGN), **(extra or {})}, "design": P_DESIGN, **more}


for _k in (97, 50, 20, 0):
    _p_config(f"P{_k}-C", f"P{_k}: {_k} value agents + {P_DESIGN} (no trigger)", _k)
    _p_config(f"P{_k}-S2", f"P{_k}: value jump +2%", _k, {"oracle_events": [JUMP_UP]},
              baseline=f"P{_k}-C", kind="jump", jump_pct=2.0)
    if _k:
        CONFIG_SEEDS[f"P{_k}-C"] = CONFIG_SEEDS[f"P{_k}-S2"] = STEP_SEEDS
_p_config("P0-S2n", "P0: value jump -2%", 0, {"oracle_events": [JUMP_DOWN]}, baseline="P0-C", kind="jump", jump_pct=-2.0)
CAMPAIGNS["step"] = [f"P{k}-{c}" for k in (97, 50, 20) for c in ("C", "S2")] + ["P0-C", "P0-S2", "P0-S2n"]

for _id, _side, _q in (("0", "BUY", 100), ("0.5", "BUY", 3000), ("1", "BUY", 6000), ("5", "BUY", 30000), ("1s", "SELL", 6000)):
    _p_config(f"P0-IMP-{_id}", f"P0: probe {_side} {_q:,}", 0, {"probe": _probe(_side, _q)}, campaign="final",
              baseline="P0-C", kind="impact")
_p_config("P0-S4", "P0: hype news +0.9", 0, campaign="final", baseline="P0-C", kind="news", sentiment=0.9,
          news=[NEWS_POS])
_p_config("P0-MM0", "P0 without market makers (L3 part 2)", 0, campaign="final", params={"num_mm": 0})
CONFIG_SEEDS["P0-MM0"] = MM0_SEEDS
CAMPAIGNS["final"] = ["P0-IMP-0", "P0-IMP-0.5", "P0-IMP-1", "P0-IMP-5", "P0-IMP-1s", "P0-S4", "P0-MM0"]

V14_CAMPAIGNS = {"b", "s1", "s1r2", "s2", "s2r", "step", "final"}


def run_params(config_id: str, seed: int) -> RunParams:
    """The RunParams part of one entry: full day, 20 + 12 of our agents."""
    d = CONFIGS[config_id]
    news = [NewsItem(offset=T0_OFFSET, headline=h, sentiment=s) for h, s in d.get("news", [])]
    # spec v1.4 N6: RunParams defaults are now the v1.4 market; the lab pins
    # the v1.3 market as its base (as before), and every v1.4 config sets its
    # population through "params" / "extra" (num_value, informed design, budget)
    base = dict(num_fund=20, num_mom=12, num_value=97, fund_mode="price_only", budget=False)
    base.update(d.get("params", {}))
    return RunParams(seed=seed, end_time="16:00:00", news=news, **base)


def config_spec(config_id: str, seed: int) -> Dict[str, Any]:
    """JSON-able description of one entry (stored in metrics.json, hashed)."""
    d = CONFIGS[config_id]
    return {
        "config_id": config_id,
        "seed": seed,
        "params": run_params(config_id, seed).model_dump(),
        "extra": json.loads(json.dumps(d.get("extra", {}))),
    }


def config_hash(config_id: str, seed: int) -> str:
    blob = json.dumps(config_spec(config_id, seed), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def lab_config(config_id: str, seed: int) -> Dict[str, Any]:
    """The build_config(...) dict of one entry of the run matrix."""
    from abides_markets.configs.rmsc04_ekf import build_config

    kw = run_config_kwargs(run_params(config_id, seed))
    kw.update(CONFIGS[config_id].get("extra", {}))
    return build_config(**kw)

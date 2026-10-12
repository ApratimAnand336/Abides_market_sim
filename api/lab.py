"""The realism lab's run matrix (FinVerse spec v1.3, Part 5 and Appendix C).

lab_config(config_id, seed) builds the rmsc04_ekf config of one entry through
the same keyword arguments as api.jobs.build_run_config (run_config_kwargs)
plus the scenario switches of spec v1.3 Part 6. RunParams and the dashboard do
not gain these switches in R2.
"""

import hashlib
import json
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
REGRESSION = {"seeds": [42, 7, 1], "configs": ["C-DEF", "S2", "IMP-1"]}


def run_params(config_id: str, seed: int) -> RunParams:
    """The RunParams part of one entry: full day, 20 + 12 of our agents."""
    d = CONFIGS[config_id]
    news = [NewsItem(offset=T0_OFFSET, headline=h, sentiment=s) for h, s in d.get("news", [])]
    return RunParams(seed=seed, end_time="16:00:00", num_fund=20, num_mom=12, news=news, **d.get("params", {}))


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

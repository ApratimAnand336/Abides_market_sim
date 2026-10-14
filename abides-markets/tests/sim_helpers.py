"""Shared helpers for tests that run short real simulations (spec v1.2).

Every simulation goes through api.jobs.build_run_config, the same path the
dashboard uses."""

import os
from typing import Dict, List, Tuple

MM_CLASS = "AdaptiveMarketMakerAgent"


# spec v1.4 §10.4 (N6): the invariant market is the new default market P0
# (informed fundamentalists, no value agents, budget on) with 30 informed
# agents to keep it fast. The v1.3 invariant market (5 price-only
# fundamentalists, 4 momentum, 97 value agents, no budget) is LEGACY_PARAMS:
# I8-legacy keeps it bit-identical to v1.2/v1.3.
INVARIANT_PARAMS = dict(seed=42, end_time="10:00:00", num_fund=30)
LEGACY_PARAMS = dict(seed=42, end_time="10:00:00", num_fund=5, num_mom=4, num_value=97, fund_mode="price_only")


def params(**kw):
    """RunParams for a short test market: the invariant market (seed 42,
    default market with 30 informed fundamentalists), 1 hour (09:30-10:30)
    unless overridden. end_time 10:30 is not a dashboard choice, so
    validation is skipped for it with model_copy."""
    return _params(INVARIANT_PARAMS, kw)


def legacy_params(**kw):
    """The v1.3 test market (LEGACY_PARAMS), 1 hour unless overridden."""
    return _params(LEGACY_PARAMS, kw)


def _params(base, kw):
    from api.schema import RunParams

    end = kw.pop("end_time", "10:30:00")
    b = dict(base)
    b.update(kw)
    return RunParams(**b).model_copy(update={"end_time": end})


def run(run_params, log_dir, count_mm_wakes: bool = False) -> Tuple[Dict, Dict, Dict[int, List[int]]]:
    """Build and run one simulation. Returns (config, end_state, mm_wakes)
    where mm_wakes maps each market maker's id to its wake times (ns)."""
    from abides_core import abides
    from api.jobs import build_run_config

    config = build_run_config(run_params)
    wakes: Dict[int, List[int]] = {}
    if count_mm_wakes:
        for a in config["agents"]:
            if type(a).__name__ == MM_CLASS:
                wakes[a.id] = []
                orig = a.wakeup

                def counted(t, _id=a.id, _orig=orig):
                    wakes[_id].append(t)
                    return _orig(t)

                a.wakeup = counted
    cwd = os.getcwd()
    os.chdir(log_dir)
    try:
        end_state = abides.run(config)
    finally:
        os.chdir(cwd)
    return config, end_state, wakes


def market_makers(end_state):
    return [a for a in end_state["agents"] if type(a).__name__ == MM_CLASS]


def history(end_state, ticker="ABM"):
    return end_state["agents"][0].order_books[ticker].history

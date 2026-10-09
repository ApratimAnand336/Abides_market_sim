"""Shared helpers for tests that run short real simulations (spec v1.2).

Every simulation goes through api.jobs.build_run_config, the same path the
dashboard uses."""

import os
from typing import Dict, List, Tuple

MM_CLASS = "AdaptiveMarketMakerAgent"


def params(**kw):
    """RunParams for a short test market: seed 42, 5 fundamentalists,
    4 momentum, 1 hour (09:30-10:30) unless overridden. end_time 10:30 is not
    a dashboard choice, so validation is skipped for it with model_copy."""
    from api.schema import RunParams

    end = kw.pop("end_time", "10:30:00")
    base = dict(seed=42, end_time="10:00:00", num_fund=5, num_mom=4)
    base.update(kw)
    return RunParams(**base).model_copy(update={"end_time": end})


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

"""The FinVerse realism lab runner (spec v1.3, Part 7).

    python scripts/realism_lab.py --campaign c1|c2|c3|c4|all|regression
                                  [--seeds 42,7,...] [--workers N] [--force]
                                  [--configs C-DEF,S2,...] [--report-only]
                                  [--rebaseline]

One simulation per spawned process (at most --workers at a time), killed after
15 minutes. Resumable: a run whose metrics.json has the same engine_version
and config hash is skipped unless --force. Per-run outputs go to
runs/_lab/<config_id>/<seed>/ (metrics.json, series.npz). After the runs the
report step aggregates EVERY run present in runs/_lab and writes
docs/v1.3/lab/summary.json, figures and runs/_lab/tables.md.

Nothing is tuned here: every number is reported as measured (spec §2.4).
"""

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import shutil
import sys
import time
import traceback
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api import lab, realism as R  # noqa: E402

TICKER = "ABM"
LAB_DIR = REPO / "runs" / "_lab"
REG_DIR = REPO / "runs" / "_lab_regression"
LAB_V14 = REPO / "runs" / "_lab_v14"  # spec v1.4 §7.1
DOC_V14 = REPO / "docs" / "v1.4" / "lab"
DOC_DIR = REPO / "docs" / "v1.3" / "lab"
FIG_DIR = DOC_DIR / "figures"
TIMEOUT_S = 15 * 60
CURVE_STEP_S = 30  # resolution of the response curves stored in summary.json

# metrics that are reported (not graded) and aggregated over seeds
REPORTED = [
    "vr30", "n_out", "skew", "u_ratio", "corr_mid_value", "vol_ratio_price_value",
    "trend_share", "sigma_day_implied", "spread_max_ticks", "spread_mean_ticks",
    "one_sided_share", "gap_mean_abs", "gap_half_life_min_dash", "day_return_pct",
    "shares_executed", "n_execs",
    # spec v1.4 §3.1 (gap diagnostics) and L3
    "gap_half_life_read_min", "gap_half_life_min", "gap_mean", "active_halfhours_share",
]
GRADED_KEYS = ["sigma_1m_bps", "ac1", "vr5", "cs", "ps", "kurt", "vv_corr",
               "spread_med_ticks", "spread_p95_ticks", "gap_std", "gap_half_life_corr_min", "regime_contrast"]
FUND_PARAMS = ["er_window", "delta", "lambda_er", "sigma_n", "gamma", "k", "mu", "q",
               "a_max", "z0", "s_max", "b_f", "k_news"]


# ══════════════════════════════════════════════════════════════════════════
# one simulation (runs in its own process)
# ══════════════════════════════════════════════════════════════════════════


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return _jsonable(x.tolist())
    return x


def _fingerprint(end_state):
    """The I1/I8 fingerprint: sha256 of every EXEC and of final holdings."""
    h = end_state["agents"][0].order_books[TICKER].history
    execs = [[x["time"], x["price"], x["quantity"], x["agent_id"], x["oppos_agent_id"]] for x in h if x["type"] == "EXEC"]
    hold = [[a.id, sorted((k, int(v)) for k, v in a.holdings.items())] for a in end_state["agents"] if hasattr(a, "holdings")]
    return {
        "execs": hashlib.sha256(json.dumps(execs).encode()).hexdigest(),
        "holdings": hashlib.sha256(json.dumps(hold).encode()).hexdigest(),
        "n_execs": len(execs),
    }


def _budget_counts(agents, open_ns):
    """spec v1.4 §7.2: per class, orders clipped / blocked by the gross limit,
    and the blocks per half-hour of the session (13 bins from 09:30)."""
    out = {}
    for a in agents:
        if getattr(a, "budget", None) is None:
            continue
        c = out.setdefault(R.class_of(a), {"agents": 0, "clipped": 0, "blocked": 0, "blocked_by_halfhour": [0] * 13})
        c["agents"] += 1
        c["clipped"] += int(getattr(a, "budget_clipped", 0))
        c["blocked"] += int(getattr(a, "budget_blocked", 0))
        for t, typ, _e in a.log:
            if typ == "BUDGET_BLOCK":
                k = int((int(t) - open_ns) // (1800 * 10**9))
                c["blocked_by_halfhour"][min(max(k, 0), 12)] += 1
    return out


def _fund_info(agents, config):
    """spec v1.4: informed fundamentalists' research and quote counts (None
    for price-only)."""
    ids = config.get("_ekf_agent_ids", [])
    fs = [agents[i] for i in ids if getattr(agents[i], "mode", "price_only") == "informed"]
    if not fs:
        return None
    reads = [sum(1 for _, t, _e in a.log if t == "RESEARCH_READING") for a in fs]
    blocked = [sum(1 for _, t, e in a.log if t == "FUND_QUOTES" and e.get("blocked_sides")) for a in fs]
    return {"n": len(fs), "research_readings_median": float(np.median(reads)),
            "quote_cycles_with_blocked_side_median": float(np.median(blocked))}


def simulate(config_id: str, seed: int, out_root: str, engine: str) -> None:
    """Run one entry of the matrix and write metrics.json + series.npz."""
    from abides_core import abides

    out = Path(out_root) / config_id / str(seed)
    out.mkdir(parents=True, exist_ok=True)
    (out / "error.txt").unlink(missing_ok=True)
    logs = Path(out_root) / "_logs" / f"{config_id}_{seed}"
    logs.mkdir(parents=True, exist_ok=True)
    try:
        t_start = time.time()
        config = lab.lab_config(config_id, seed)
        start = {a.id: (int(a.holdings.get("CASH", 0)), int(a.holdings.get(TICKER, 0)))
                 for a in config["agents"] if hasattr(a, "holdings")}
        cwd = os.getcwd()
        os.chdir(logs)
        try:
            t0 = time.time()
            end_state = abides.run(config)
            wall = time.time() - t0
        finally:
            os.chdir(cwd)

        s = R.series_from_end_state(end_state, config, TICKER, start_holdings=start)
        metrics = R.run_metrics(s)
        metrics["n_execs"] = s["n_execs"]
        sanity = R.agent_sanity(s)
        agents = end_state["agents"]
        if "top_fund_id" in sanity:
            top = agents[sanity["top_fund_id"]]
            sanity["top_fund_params"] = {k: float(getattr(top, k)) for k in FUND_PARAMS if hasattr(top, k)}
        n_mom = len(config.get("_mom_ekf_agent_ids", []))
        ms = s["mom_states"]
        entries = int(np.sum(np.isin(ms[:, 3], [R.MOM_REASONS.index("BREAKOUT"), R.MOM_REASONS.index("REENTRY")]))) if len(ms) else 0
        try:
            import psutil

            mi = psutil.Process().memory_info()
            peak_mb = getattr(mi, "peak_wset", getattr(mi, "rss", 0)) / 1e6
        except Exception:  # psutil missing: memory is informative only
            peak_mb = None

        record = {
            "config_id": config_id,
            "seed": seed,
            "engine_version": engine,
            "config_hash": lab.config_hash(config_id, seed),
            "config": lab.config_spec(config_id, seed),
            "date": date.today().isoformat(),
            "wall_time_s": round(wall, 2),
            "job_time_s": round(time.time() - t_start, 2),
            "peak_mem_mb": peak_mb,
            "fingerprint": _fingerprint(end_state),
            "metrics": metrics,
            "sanity": sanity,
            "zero_sum_cents": sanity["zero_sum_cents"],
            "zero_sum_ok": sanity["ok"],
            "flags": s["flags"],
            "news": s["news"],
            "probe": s["probe"],
            "oracle_events": s["oracle_events"],
            "mom_entries_per_agent": entries / n_mom if n_mom else None,
            "budget": _budget_counts(agents, config["_mkt_open_ns"]),
            "fund_info": _fund_info(agents, config),
            "diagnostics": R.run_diagnostics(s),  # spec v1.5 A2
        }
        f32 = lambda x: np.asarray(x, dtype=np.float32)  # noqa: E731
        np.savez_compressed(
            out / "series.npz",
            mid_1s=f32(s["mid_1s"]), val_1s=f32(s["val_1s"]), spr_1s=f32(s["spr_1s"]),
            close_1m=f32(s["close_1m"]), vol_1m=f32(s["vol_1m"]), net_1m=f32(s["net_1m"]),
            fund_xhat_10s=f32(s["fund_xhat_10s"]), mom_states=f32(s["mom_states"]),
        )
        tmp = out / "metrics.json.tmp"
        tmp.write_text(json.dumps(_jsonable(record), indent=1), encoding="utf-8")
        os.replace(tmp, out / "metrics.json")
    except BaseException:
        (out / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        shutil.rmtree(logs, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════
# scheduling
# ══════════════════════════════════════════════════════════════════════════


def load_metrics(root: Path, config_id: str, seed: int):
    p = root / config_id / str(seed) / "metrics.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def is_done(root: Path, config_id: str, seed: int, engine: str) -> bool:
    m = load_metrics(root, config_id, seed)
    return bool(m) and m.get("engine_version") == engine and m.get("config_hash") == lab.config_hash(config_id, seed)


def run_all(tasks, root: Path, workers: int, engine: str):
    """Run (config_id, seed) tasks, at most `workers` processes at a time."""
    ctx = mp.get_context("spawn")
    pending = list(tasks)
    running = {}
    done, failed = [], []
    t_begin = time.time()
    total = len(pending)
    while pending or running:
        while pending and len(running) < workers:
            cid, seed = pending.pop(0)
            p = ctx.Process(target=simulate, args=(cid, seed, str(root), engine), daemon=True)
            p.start()
            running[(cid, seed)] = (p, time.time())
        time.sleep(0.5)
        for key, (p, t0) in list(running.items()):
            if p.is_alive():
                if time.time() - t0 > TIMEOUT_S:
                    p.terminate()
                    p.join(5)
                    msg = f"timed out after {TIMEOUT_S / 60:.0f} minutes"
                    (root / key[0] / str(key[1])).mkdir(parents=True, exist_ok=True)
                    (root / key[0] / str(key[1]) / "error.txt").write_text(msg, encoding="utf-8")
                    failed.append((key, msg))
                    del running[key]
                continue
            p.join()
            del running[key]
            ok = p.exitcode == 0 and load_metrics(root, *key) is not None
            (done if ok else failed).append((key, None if ok else f"exit code {p.exitcode}"))
            n = len(done) + len(failed)
            el = time.time() - t_begin
            eta = el / n * (total - n)
            print(f"[{n}/{total}] {key[0]} seed {key[1]}: {'ok' if ok else 'FAILED'} "
                  f"({time.time() - t0:.0f} s; elapsed {el / 60:.1f} min, eta {eta / 60:.1f} min)", flush=True)
    return done, failed


# ══════════════════════════════════════════════════════════════════════════
# report
# ══════════════════════════════════════════════════════════════════════════


def load_series(root: Path, config_id: str, seed: int):
    p = root / config_id / str(seed) / "series.npz"
    if not p.exists():
        return None
    with np.load(p) as z:
        return {k: z[k].astype(np.float64) for k in z.files}


def agg(values, min_seeds=R.MIN_VALID_SEEDS):
    return R.aggregate(list(values), min_seeds)


def agg_dict(rows, min_seeds=R.MIN_VALID_SEEDS, skip=()):
    """Aggregate every scalar key of a list of dicts (nested dicts by key path)."""
    keys = []
    for r in rows:
        for k, v in r.items():
            if k not in keys and k not in skip:
                keys.append(k)
    out = {}
    for k in keys:
        vals = [r.get(k) for r in rows]
        if any(isinstance(v, dict) for v in vals):
            out[k] = agg_dict([v or {} for v in vals], min_seeds)
        elif all(v is None or isinstance(v, (int, float, bool)) for v in vals):
            out[k] = agg([None if v is None else float(v) for v in vals], min_seeds)
    return out


def curve(seeds_curves, t_rel):
    """Median, p10, p90 over seeds of curves sampled at t_rel."""
    if not seeds_curves:
        return None
    a = np.array(seeds_curves)
    return {
        "t_min": [float(x) / 60.0 for x in t_rel],
        "median": np.nanmedian(a, axis=0).tolist(),
        "p10": np.nanpercentile(a, 10, axis=0).tolist(),
        "p90": np.nanpercentile(a, 90, axis=0).tolist(),
        "n": int(len(a)),
    }


def config_block(root: Path, config_id: str, seeds, min_seeds):
    """Scorecard, reported diagnostics, sanity and heavy-trader watch of one config."""
    rows = [load_metrics(root, config_id, s) for s in seeds]
    rows = [r for r in rows if r]
    if not rows:
        return None
    for r in rows:  # runs written before n_execs was stored in metrics
        r["metrics"].setdefault("n_execs", r["fingerprint"]["n_execs"])
    per_seed = [r["metrics"] for r in rows]
    block = {
        "label": lab.CONFIGS[config_id]["label"],
        "seeds": [r["seed"] for r in rows],
        "n_runs": len(rows),
        "engine_versions": sorted({r["engine_version"] for r in rows}),
        "dates": sorted({r["date"] for r in rows}),
        "scorecard": R.scorecard(per_seed, min_seeds),
        "reported": {k: agg([m.get(k) for m in per_seed], min_seeds) for k in REPORTED},
        "ac_1_5_median": np.median([m["ac_1_5"] for m in per_seed], axis=0).tolist(),
        "acf_abs_median": np.median([m["acf_abs"] for m in per_seed], axis=0).tolist(),
        "gap_rho_median": np.median([m["gap_rho"] for m in per_seed], axis=0).tolist(),
        "zero_sum_all_zero": all(r["zero_sum_ok"] and r["zero_sum_cents"] == 0 for r in rows),
        "flags_all_ok": all(all(r["flags"].values()) for r in rows),
        "wall_time_s": agg([r["wall_time_s"] for r in rows], 1),
        "peak_mem_mb": agg([r.get("peak_mem_mb") for r in rows], 1),
        "sanity": {},
    }
    classes = sorted({c for r in rows for c in r["sanity"]["classes"]}, key=lambda c: R.CLASSES.index(c) if c in R.CLASSES else 99)
    for c in classes:
        block["sanity"][c] = agg_dict([r["sanity"]["classes"].get(c, {}) for r in rows], min_seeds)
    if any("top_fund_volume_share" in r["sanity"] for r in rows):
        tops = [{"seed": r["seed"], "id": r["sanity"].get("top_fund_id"),
                 "volume_share_pct": r["sanity"].get("top_fund_volume_share"),
                 "turnover": r["sanity"].get("top_fund_turnover"),
                 "params": r["sanity"].get("top_fund_params")} for r in rows]
        block["heavy_trader"] = {
            "volume_share_pct": agg([t["volume_share_pct"] for t in tops], min_seeds),
            "turnover": agg([t["turnover"] for t in tops], min_seeds),
            "seeds_over_1pct": [t["seed"] for t in tops if (t["volume_share_pct"] or 0) > 1.0],
            "per_seed": tops,
        }
    block["mom_entries_per_agent"] = agg([r.get("mom_entries_per_agent") for r in rows], min_seeds)
    return block


def pairs(root, config_id, base_id, seeds):
    """(seed, metrics_T, series_T, metrics_B, series_B) for seeds with both runs."""
    for s in seeds:
        mT, mB = load_metrics(root, config_id, s), load_metrics(root, base_id, s)
        if not (mT and mB):
            continue
        sT, sB = load_series(root, config_id, s), load_series(root, base_id, s)
        if sT is None or sB is None:
            continue
        yield s, mT, sT, mB, sB


def scenario_block(root, config_id, seeds, min_seeds):
    d = lab.CONFIGS[config_id]
    base = d.get("baseline")
    kind = d.get("kind")
    t0 = lab.T0_S
    rows, curves = [], []
    t_rel = np.arange(-1800, 5401, CURVE_STEP_S)
    extra = {}
    for s, mT, sT, mB, sB in pairs(root, config_id, base, seeds):
        if kind == "jump":
            J = d["jump_pct"] / 100.0 * 1000.0  # % of r_bar = $1000
            r = R.jump_response(sT, sB, t0, J)
            f = R.smooth((sT["mid_1s"] - sB["mid_1s"]) / J)
            curves.append(f[t0 + t_rel])
        elif kind == "news":
            r = R.news_response(sT, sB, t0, d["sentiment"])
            sign = 1.0 if d["sentiment"] > 0 else -1.0
            Rt = R.smooth(sign * 1e4 * np.log(sT["mid_1s"] / sB["mid_1s"]))
            curves.append(Rt[t0 + t_rel])
            fs = mT["news"]["fund_shift"]
            dv = mT["news"]["mom_dv"]
            r["belief_shift_fund_median"] = float(np.median(fs)) if fs else None
            r["belief_shift_fund_min"] = float(np.min(fs)) if fs else None
            r["belief_shift_fund_max"] = float(np.max(fs)) if fs else None
            r["mom_dv_median"] = float(np.median(dv)) if dv else None
        elif kind == "vol":
            r = R.vol_burst(sT, sB, t0, t0 + 3600)
            w = 600

            def roll_sigma(mid):
                pts = mid[::60]
                rr = np.diff(np.log(pts))
                sd = np.array([np.std(rr[max(0, i - w // 60):i], ddof=1) if i >= 2 else np.nan for i in range(1, len(rr) + 1)])
                return 1e4 * sd

            curves.append(np.concatenate([[np.nan], roll_sigma(sT["mid_1s"]) / roll_sigma(sB["mid_1s"])]))
            extra.setdefault("sigma_T", []).append(np.concatenate([[np.nan], roll_sigma(sT["mid_1s"])]))
            extra.setdefault("sigma_B", []).append(np.concatenate([[np.nan], roll_sigma(sB["mid_1s"])]))
        elif kind == "pause":
            w0, w1 = 12600, 14400
            r = R.mm_pause(sT, sB, w0, w1)

            def roll_spread(x):
                import pandas as pd

                return pd.Series(x).rolling(60, min_periods=1).mean().to_numpy()

            tr = np.arange(w0 - 1800, w1 + 3601, CURVE_STEP_S)
            extra.setdefault("spread_T", []).append(roll_spread(sT["spr_1s"])[tr])
            extra.setdefault("spread_B", []).append(roll_spread(sB["spr_1s"])[tr])
            extra["t_pause"] = tr
        elif kind == "capital":
            r = {f"d_{k}": (None if mT["metrics"].get(k) is None or mB["metrics"].get(k) is None
                            else mT["metrics"][k] - mB["metrics"][k]) for k in GRADED_KEYS}
            cT = mT["sanity"]["classes"].get("MomentumEKFAgent", {})
            cB = mB["sanity"]["classes"].get("MomentumEKFAgent", {})
            r.update(
                mom_volume_share_T=cT.get("volume_share_pct"), mom_volume_share_B=cB.get("volume_share_pct"),
                mom_entries_per_agent_T=mT.get("mom_entries_per_agent"), mom_entries_per_agent_B=mB.get("mom_entries_per_agent"),
                mom_pnl_vs_hold_median_T=cT.get("pnl_vs_hold_median"), mom_pnl_vs_hold_total_T=cT.get("pnl_vs_hold_total"),
                mom_pnl_vs_hold_median_B=cB.get("pnl_vs_hold_median"), mom_pnl_vs_hold_total_B=cB.get("pnl_vs_hold_total"),
            )
        elif kind == "impact":
            probe = d["extra"]["probe"]
            base_shares = mB["metrics"]["shares_executed"]
            r = R.impact_run(sT, sB, t0, probe["duration_s"], probe["side"], probe["quantity"], base_shares, mT["probe"])
            sign = 1.0 if probe["side"] == "BUY" else -1.0
            I = R.smooth(sign * 1e4 * np.log(sT["mid_1s"] / sB["mid_1s"]))
            tr = np.arange(-300, 2401, 10)
            extra.setdefault("path", []).append(I[t0 + tr])
            extra["t_path"] = tr
            r["probe_volume_share_pct"] = mT["sanity"].get("probe_volume_share_pct")
            r["probe_pnl_vs_hold"] = mT["sanity"].get("probe_pnl_vs_hold")
        else:
            continue
        r["seed"] = s
        rows.append(r)
    if not rows:
        return None
    out = {"label": d["label"], "baseline": base, "kind": kind, "n_seeds": len(rows),
           "stats": agg_dict(rows, min_seeds, skip=("seed",)), "per_seed": _jsonable(rows)}
    if kind in ("jump", "news"):
        out["curve"] = curve(curves, t_rel)
    if kind == "vol":
        out["curve_ratio"] = curve(curves, np.arange(0, len(curves[0])) * 60)
        out["curve_sigma_T"] = curve(extra["sigma_T"], np.arange(0, len(curves[0])) * 60)
        out["curve_sigma_B"] = curve(extra["sigma_B"], np.arange(0, len(curves[0])) * 60)
    if kind == "pause":
        out["curve_spread_T"] = curve(extra["spread_T"], extra["t_pause"])
        out["curve_spread_B"] = curve(extra["spread_B"], extra["t_pause"])
    if kind == "impact":
        out["curve_I"] = curve(extra["path"], extra["t_path"])
    return out


def impact_summary(scen, min_seeds):
    """Noise floor, resolution, beta (G12) and recovery (G13) from the IMP-* blocks."""
    if not all(k in scen for k in ("IMP-0", "IMP-0.1", "IMP-0.5", "IMP-1", "IMP-5")):
        return None
    pl = scen["IMP-0"]["per_seed"]
    floor = R.noise_floor([r["I_end"] for r in pl], [r["I_perm"] for r in pl])
    sizes = ["IMP-0.1", "IMP-0.5", "IMP-1", "IMP-5"]
    out = {"noise_floor": floor, "sizes": {}}
    for k in ["IMP-0"] + sizes + (["IMP-1s"] if "IMP-1s" in scen else []):
        st = scen[k]["stats"]
        out["sizes"][k] = {
            "q_median": st["q"]["median"],
            "I_end_resolved": R.resolved(abs(st["I_end"]["median"]), floor["I_end"]),
            "I_perm_resolved": R.resolved(abs(st["I_perm"]["median"]), floor["I_perm"]),
        }

    def by_seed(key):
        seeds = sorted(set.intersection(*[{r["seed"] for r in scen[k]["per_seed"]} for k in sizes]))
        q = {k: [next(r["q"] for r in scen[k]["per_seed"] if r["seed"] == s) for s in seeds] for k in sizes}
        v = {k: [next(r[key] for r in scen[k]["per_seed"] if r["seed"] == s) for s in seeds] for k in sizes}
        return q, v, seeds

    for key in ("I_end", "I_peak"):
        q, v, seeds = by_seed(key)
        out[f"beta_{key}"] = R.impact_beta(q, v)
        out[f"beta_{key}"]["n_seeds"] = len(seeds)
    rec = {}
    for k in ("IMP-1", "IMP-5"):
        rr = [r["recovery"] for r in scen[k]["per_seed"]]
        rec[k] = agg(rr, min_seeds)
    out["recovery"] = rec
    beta = out["beta_I_end"]["beta"]
    out["G12"] = {"value": beta, "ci": out["beta_I_end"]["ci"],
                  "grade": R.grade_value(R.BANDS_BY_ID["G12"], {"impact_beta": beta}) if beta is not None else "N/A"}
    r1 = rec["IMP-1"]
    out["G13"] = {"value": r1["median"], "stats": r1,
                  "grade": "INCOMPLETE" if r1["status"] != "OK" else R.grade_value(R.BANDS_BY_ID["G13"], {"impact_recovery": r1["median"]})}
    return out


def build_summary(root: Path, seeds, min_seeds=R.MIN_VALID_SEEDS):
    from api.jobs import engine_version

    configs, scen = {}, {}
    for cid in lab.CONFIGS:
        b = config_block(root, cid, seeds, min_seeds)
        if b:
            configs[cid] = b
    for cid, d in lab.CONFIGS.items():
        if d.get("kind") and cid in configs and d.get("baseline") in configs:
            sb = scenario_block(root, cid, seeds, min_seeds)
            if sb:
                scen[cid] = sb
    # S3 vs S2 on the same seed
    if "S3" in scen and "S2" in scen:
        d = []
        for r3 in scen["S3"]["per_seed"]:
            r2 = next((r for r in scen["S2"]["per_seed"] if r["seed"] == r3["seed"]), None)
            if r2:
                d.append({k: (None if r3.get(k) is None or r2.get(k) is None else r3[k] - r2[k])
                          for k in ("t50", "t90", "overshoot", "settle", "belief_5", "belief_30", "mom_entries")})
        scen["S3"]["vs_S2"] = agg_dict(d, min_seeds)
    # S7c overshoot vs S2's on the same seed
    if "S7c" in scen and "S2" in scen:
        d = []
        for r7 in scen["S7c"]["per_seed"]:
            r2 = next((r for r in scen["S2"]["per_seed"] if r["seed"] == r7["seed"]), None)
            if r2:
                d.append({k: (None if r7.get(k) is None or r2.get(k) is None else r7[k] - r2[k])
                          for k in ("t50", "t90", "overshoot", "settle", "mom_entries")})
        scen["S7c"]["vs_S2"] = agg_dict(d, min_seeds)
    imp = impact_summary(scen, min_seeds)
    return {
        "spec": "FinVerse spec v1.3 (R2)",
        "generated": date.today().isoformat(),
        "engine_version_at_report": engine_version(),
        "seeds": list(seeds),
        "min_valid_seeds": min_seeds,
        "t0": "11:00:00",
        "bands": R.BANDS,
        "configs": configs,
        "scenarios": scen,
        "impact": imp,
    }


# ── tables (markdown) ─────────────────────────────────────────────────────


def fmt(a, digits=3, unit=""):
    if not a or a.get("median") is None:
        return "—"
    f = lambda x: f"{x:.{digits}g}"  # noqa: E731
    return f"{f(a['median'])}{unit} [{f(a['p10'])}–{f(a['p90'])}]"


def tables(summary) -> str:
    L = []
    for cid, b in summary["configs"].items():
        L.append(f"\n### {cid}: {b['label']} (n = {b['n_runs']}; {', '.join(b['engine_versions'])})\n")
        L.append("| # | Metric | Band | Median [p10–p90] | Grade | pass_share |")
        L.append("|---|---|---|---|---|---|")
        sc = b["scorecard"]
        for gid in ["G1", "G2"] + R.RUN_GRADES[1:]:
            g = sc[gid]
            if gid == "G2":
                v = g["stats"]["value"]
                L.append(f"| G2 | {g['label']} | {g['band']} | {'—' if v is None else f'{v:.3g}%'} (n = {g['stats']['n_seeds']}) | {g['grade']} | — |")
                continue
            st = g["stats"]
            val = " · ".join(f"{k} {fmt(v)}" for k, v in st.items()) if len(st) > 1 else fmt(next(iter(st.values())))
            ps = "—" if g["pass_share"] is None else f"{100 * g['pass_share']:.0f}%"
            L.append(f"| {gid} | {g['label']} | {g['band']} | {val} | {g['grade']} | {ps} |")
        L.append("\nReported: " + "; ".join(f"{k} {fmt(v)}" for k, v in b["reported"].items()))
        L.append(f"\nac lags 1–5 (median): {', '.join(f'{x:.3f}' for x in b['ac_1_5_median'])}; "
                 f"acf|r| lags 1–5: {', '.join(f'{x:.3f}' for x in b['acf_abs_median'][:5])}; "
                 f"zero_sum all 0: {b['zero_sum_all_zero']}; flags ok: {b['flags_all_ok']}; "
                 f"wall {fmt(b['wall_time_s'])} s; peak mem {fmt(b['peak_mem_mb'])} MB")
        L.append("\n| Class | volume share % | shares traded | P&L vs hold total $ | P&L vs hold median $ |")
        L.append("|---|---|---|---|---|")
        for c, st in b["sanity"].items():
            L.append(f"| {c} | {fmt(st.get('volume_share_pct'))} | {fmt(st.get('shares_traded'))} | "
                     f"{fmt(st.get('pnl_vs_hold_total'))} | {fmt(st.get('pnl_vs_hold_median'))} |")
        for c in ("FundamentalistAgent", "MomentumEKFAgent"):
            st = b["sanity"].get(c)
            if st:
                L.append(f"\n{c}: turnover median {fmt(st.get('turnover_median'))}, p90 {fmt(st.get('turnover_p90'))}, "
                         f"max {fmt(st.get('turnover_max'))}; holdings p10 {fmt(st.get('holdings_p10'))}, p90 {fmt(st.get('holdings_p90'))}")
        if "heavy_trader" in b:
            h = b["heavy_trader"]
            L.append(f"\nHeavy trader: volume share {fmt(h['volume_share_pct'], unit='%')}, turnover {fmt(h['turnover'])}, "
                     f"seeds over 1%: {h['seeds_over_1pct'] or 'none'}")
    for cid, sc in summary["scenarios"].items():
        L.append(f"\n### {cid}: {sc['label']} vs {sc['baseline']} (n = {sc['n_seeds']})\n")
        L.append("| Metric | Median [p10–p90] | n |")
        L.append("|---|---|---|")
        for k, v in sc["stats"].items():
            if "median" in v:
                L.append(f"| {k} | {fmt(v)} | {v['n_seeds']} |")
            else:
                for kk, vv in v.items():
                    if "median" in vv:
                        L.append(f"| {k}.{kk} | {fmt(vv)} | {vv['n_seeds']} |")
        if "vs_S2" in sc:
            L.append("\nvs S2 (same seed): " + "; ".join(f"{k} {fmt(v)}" for k, v in sc["vs_S2"].items()))
    if summary.get("impact"):
        im = summary["impact"]
        L.append(f"\n### Impact\n\nnoise floor: {im['noise_floor']}\n")
        for k, v in im["sizes"].items():
            L.append(f"- {k}: {v}")
        L.append(f"\nbeta I_end {im['beta_I_end']}\n\nbeta I_peak {im['beta_I_peak']}\n\nG12 {im['G12']}\n\nG13 {im['G13']}")
    return "\n".join(L)


# ── figures ───────────────────────────────────────────────────────────────


def figures(summary, fig_dir: Path):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("WARNING: matplotlib is not installed; figures skipped")
        return []
    fig_dir.mkdir(parents=True, exist_ok=True)
    made = []
    C = summary["configs"]
    S = summary["scenarios"]
    INK, BLUE, ORANGE, GREY = "#1f2933", "#2a6fdb", "#d9822b", "#9aa5b1"
    PASSC, WARNC = "#d8f0dd", "#fbeccb"

    # scorecard: one panel per graded metric; dots per seed, median bar
    cfgs = [c for c in ("C-DEF", "C-V20") if c in C]
    if cfgs:
        panels = [("G1", "sigma_1m_bps"), ("G3", "ac1"), ("G4", "vr5"), ("G5", "cs"), ("G6", "kurt"),
                  ("G7", "vv_corr"), ("G8", "spread_p95_ticks"), ("G9", "gap_std"),
                  ("G10", "gap_half_life_min"), ("G11", "regime_contrast"), ("G2", "day_return_pct")]
        fig, axes = plt.subplots(len(panels), 1, figsize=(8, 1.15 * len(panels) + 0.6))
        root = LAB_DIR
        for ax, (gid, key) in zip(axes, panels):
            band = R.BANDS_BY_ID[gid]
            xs_all = []
            for j, cid in enumerate(cfgs):
                vals = []
                for s in C[cid]["seeds"]:
                    m = load_metrics(root, cid, s)
                    v = m["metrics"].get(key) if m else None
                    if v is not None:
                        vals.append(abs(v) if band.get("transform") == "abs" else v)
                if gid == "G2":
                    vals = [abs(v) for v in vals]
                xs_all += vals
                y = len(cfgs) - 1 - j
                ax.scatter(vals, [y] * len(vals), s=12, color=BLUE if j == 0 else ORANGE, alpha=0.7, zorder=3)
                if vals:
                    med = C[cid]["scorecard"][gid]["stats"].get("value") if gid == "G2" else float(np.median(vals))
                    if med is not None:
                        ax.plot([med, med], [y - 0.35, y + 0.35], color=INK, lw=2.2, zorder=4)
            lo = min(xs_all + [0]) if xs_all else 0
            hi = max(xs_all + [1]) if xs_all else 1
            ivs = band["pass"] + band["warn"] if gid not in ("G5", "G8") else (
                [[0.10, None]] + [[0.05, 0.10]] if gid == "G5" else [[None, 5.0]] + [[5.0, 10.0]])
            for i, (a, b2) in enumerate(ivs):
                n_pass = len(band["pass"]) if gid not in ("G5", "G8") else 1
                ax.axvspan(a if a is not None else lo - 1e9, b2 if b2 is not None else hi + 1e9,
                           color=PASSC if i < n_pass else WARNC, zorder=0)
            span = hi - lo if hi > lo else 1.0
            ax.set_xlim(lo - 0.08 * span, hi + 0.08 * span)
            ax.set_yticks(range(len(cfgs)))
            ax.set_yticklabels(cfgs[::-1], fontsize=7)
            name = {"G2": "|day return| % (G2 = std over seeds)", "G5": "CS (G5)", "G8": "spread p95 ticks (G8)"}.get(gid, f"{band['label']} ({gid})")
            ax.set_title(name, fontsize=8, loc="left", pad=2)
            ax.tick_params(axis="x", labelsize=7)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
        fig.suptitle("Scorecard: seed values (dots), median (bar); green = PASS, amber = WARN", fontsize=9)
        fig.tight_layout()
        fig.savefig(fig_dir / "scorecard.png", dpi=130)
        plt.close(fig)
        made.append("scorecard.png")

    def band_plot(ax, cv, color, label):
        t = np.array(cv["t_min"])
        ax.fill_between(t, cv["p10"], cv["p90"], color=color, alpha=0.18, lw=0)
        ax.plot(t, cv["median"], color=color, lw=1.6, label=f"{label} (n = {cv['n']})")

    jumps = [c for c in ("S2", "S2n", "S3", "S7c") if c in S and S[c].get("curve")]
    if jumps:
        fig, ax = plt.subplots(figsize=(8, 4))
        for c, col in zip(jumps, [BLUE, ORANGE, "#3f9142", "#8e44ad"]):
            band_plot(ax, S[c]["curve"], col, f"{c} vs {S[c]['baseline']}")
        ax.axhline(1, color=GREY, lw=0.8, ls="--")
        ax.axhline(0, color=GREY, lw=0.8)
        ax.axvline(0, color=GREY, lw=0.8)
        ax.set_xlabel("minutes after the value jump (11:00)")
        ax.set_ylabel("share of the jump priced in, f(t)")
        ax.set_title("Value jump: (mid treated − mid baseline) / jump, median and p10–p90 over seeds", fontsize=9)
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        fig.savefig(fig_dir / "jump_response.png", dpi=130)
        plt.close(fig)
        made.append("jump_response.png")

    news = [c for c in ("S4", "S4n") if c in S and S[c].get("curve")]
    if news:
        fig, ax = plt.subplots(figsize=(8, 4))
        for c, col in zip(news, [BLUE, ORANGE]):
            band_plot(ax, S[c]["curve"], col, f"{c} vs {S[c]['baseline']}")
        ax.axhline(0, color=GREY, lw=0.8)
        ax.axvline(0, color=GREY, lw=0.8)
        ax.set_xlabel("minutes after the headline (11:00)")
        ax.set_ylabel("R(t), bps in the news direction")
        ax.set_title("Hype news: price response vs the same day without the headline", fontsize=9)
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        fig.savefig(fig_dir / "news_response.png", dpi=130)
        plt.close(fig)
        made.append("news_response.png")

    imp = summary.get("impact")
    if imp:
        sizes = ["IMP-0.1", "IMP-0.5", "IMP-1", "IMP-5"]
        fig, ax = plt.subplots(figsize=(6.5, 4.5))
        for key, col, mk in (("I_end", BLUE, "o"), ("I_peak", ORANGE, "s")):
            q = [S[k]["stats"]["q"]["median"] for k in sizes]
            med = [S[k]["stats"][key]["median"] for k in sizes]
            lo = [S[k]["stats"][key]["p10"] for k in sizes]
            hi = [S[k]["stats"][key]["p90"] for k in sizes]
            okm = [m is not None and m > 0 for m in med]
            qq = [x for x, o in zip(q, okm) if o]
            mm = [x for x, o in zip(med, okm) if o]
            err = [[max(m - l, 0) if l is not None and l > 0 else m * 0.999 for m, l, o in zip(med, lo, okm) if o],
                   [max(h - m, 0) for m, h, o in zip(med, hi, okm) if o]]
            ax.errorbar(qq, mm, yerr=err, fmt=mk + "-", color=col, ms=5, capsize=3, label=f"median {key} (p10–p90)")
        fl = imp["noise_floor"]["I_end"]
        if fl:
            ax.axhline(fl, color=GREY, ls="--", lw=1, label="noise floor (p90 |I_end|, placebo)")
            ax.axhline(2 * fl, color=GREY, ls=":", lw=1, label="2 × noise floor")
        qs = np.array([S[k]["stats"]["q"]["median"] for k in sizes])
        ref_y = S["IMP-1"]["stats"]["I_end"]["median"]
        if ref_y and ref_y > 0:
            ax.plot(qs, ref_y * (qs / S["IMP-1"]["stats"]["q"]["median"]) ** 0.5, color=INK, lw=0.8, ls="-.", label="slope 0.5 (square-root law)")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("q = order size / baseline daily volume")
        ax.set_ylabel("impact (bps)")
        b = imp["beta_I_end"]
        ax.set_title(f"Price impact of a 5-minute buy; beta(I_end) = {b['beta']:.2f}" if b["beta"] is not None else "Price impact", fontsize=9)
        ax.legend(fontsize=7, frameon=False)
        fig.tight_layout()
        fig.savefig(fig_dir / "impact_curve.png", dpi=130)
        plt.close(fig)
        made.append("impact_curve.png")

        fig, ax = plt.subplots(figsize=(8, 4))
        cols = [GREY, "#6c8ebf", BLUE, "#1d3f8a", ORANGE, "#c0392b"]
        for k, col in zip(["IMP-0"] + sizes + ["IMP-1s"], cols):
            if k in S and S[k].get("curve_I"):
                cv = S[k]["curve_I"]
                ax.plot(cv["t_min"], cv["median"], color=col, lw=1.4, label=f"{k} (n = {cv['n']})")
        ax.axvspan(0, 5, color="#eeeeee", zorder=0)
        ax.axhline(0, color=GREY, lw=0.8)
        ax.set_xlabel("minutes after the order starts (11:00; execution 0–5 min shaded)")
        ax.set_ylabel("I(t), bps against the trader (median over seeds)")
        ax.set_title("Impact path: treated vs the same day without the order", fontsize=9)
        ax.legend(fontsize=7, frameon=False, ncol=2)
        fig.tight_layout()
        fig.savefig(fig_dir / "impact_path.png", dpi=130)
        plt.close(fig)
        made.append("impact_path.png")

    if "S5" in S:
        fig, ax = plt.subplots(figsize=(8, 4))
        for key, col, lab_ in (("curve_sigma_T", ORANGE, "S5 (value vol ×3, 11:00–12:00)"), ("curve_sigma_B", BLUE, "C-DEF")):
            cv = S["S5"][key]
            t = np.array(cv["t_min"]) / 60.0 + 9.5
            ax.plot(t, cv["median"], color=col, lw=1.4, label=lab_)
            ax.fill_between(t, cv["p10"], cv["p90"], color=col, alpha=0.15, lw=0)
        ax.axvspan(11, 12, color="#eeeeee", zorder=0)
        ax.set_xlabel("clock time (h)")
        ax.set_ylabel("rolling 10-min σ of 1-min returns (bps)")
        ax.set_title("Volatility burst: median and p10–p90 over seeds", fontsize=9)
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        fig.savefig(fig_dir / "vol_burst.png", dpi=130)
        plt.close(fig)
        made.append("vol_burst.png")

    if "S6" in S:
        fig, ax = plt.subplots(figsize=(8, 4))
        for key, col, lab_ in (("curve_spread_T", ORANGE, "S6 (MMs paused 13:00–13:30)"), ("curve_spread_B", BLUE, "C-DEF")):
            cv = S["S6"][key]
            t = np.array(cv["t_min"]) / 60.0 + 9.5
            ax.plot(t, cv["median"], color=col, lw=1.4, label=lab_)
            ax.fill_between(t, cv["p10"], cv["p90"], color=col, alpha=0.15, lw=0)
        ax.axvspan(13, 13.5, color="#eeeeee", zorder=0)
        ax.set_xlabel("clock time (h)")
        ax.set_ylabel("rolling 1-min mean spread (ticks)")
        ax.set_title("Market-maker pause: median and p10–p90 over seeds", fontsize=9)
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        fig.savefig(fig_dir / "mm_pause.png", dpi=130)
        plt.close(fig)
        made.append("mm_pause.png")
    return made


# ══════════════════════════════════════════════════════════════════════════
# regression set (spec §7.6)
# ══════════════════════════════════════════════════════════════════════════

# spec v1.4 N6: in a value-jump run, G11's regime contrast is dominated by the
# jump window itself (P0-S2 median 45 vs 2.5 quiet), so it measures the
# trigger; its 3-seed median is a fixed sample of a heavy tail (seeds 42 and 1
# are the 20-seed maximum and runner-up). Not compared (DECISIONS.md, N6).
REG_SKIP = {"P0-S2": {"regime_contrast"}}
REG_SCENARIO_KEYS = {"S2": ["t50", "t90", "settle"], "IMP-1": ["I_end", "I_peak", "I_perm"],
                    "P0-S2": ["t50", "t90", "settle"], "P0-IMP-1": ["I_end", "I_peak", "I_perm"]}


def regression(workers, engine, rebaseline=False, force=True, legacy=False) -> int:
    """spec v1.3 §7.6 / v1.4 §10.5: 3 seeds of 3 configs, the seed-42 full-day
    hash and every metric inside the stored 20-seed [p10, p90]. legacy=True:
    the v1.3 set (C-DEF/S2/IMP-1 vs docs/v1.3); default: the v1.4 set on P0."""
    R_ = lab.REGRESSION_LEGACY if legacy else lab.REGRESSION
    seeds, configs = R_["seeds"], R_["configs"]
    reg_dir = REPO / "runs" / R_["dir"]
    doc_dir = REPO / "docs" / R_["doc"] / "lab"
    tasks = [(c, s) for c in configs for s in seeds if force or not is_done(reg_dir, c, s, engine)]
    if tasks:
        done, failed = run_all(tasks, reg_dir, workers, engine)
        if failed:
            print("FAILED runs:", failed)
            return 1
    ref = json.loads((doc_dir / "reference_hashes.json").read_text(encoding="utf-8"))
    stored_path = doc_dir / "summary.json"
    stored = json.loads(stored_path.read_text(encoding="utf-8"))
    problems = []

    hc = R_["hash_config"]
    m42 = load_metrics(reg_dir, hc, 42)
    fp = m42["fingerprint"]
    want = ref["runs"][R_["ref_key"]]
    if fp["execs"] != want["execs"] or fp["holdings"] != want["holdings"]:
        problems.append(f"HASH: seed-42 {hc} {fp['execs'][:16]}… / {fp['holdings'][:16]}… != reference {want['execs'][:16]}… / {want['holdings'][:16]}…")
    else:
        print(f"(a) seed-42 {hc} full-day EXEC and holdings hash equal {doc_dir.relative_to(REPO)}/reference_hashes.json {R_['ref_key']}")

    reg = build_summary(reg_dir, seeds, min_seeds=1)
    checks = []
    for cid in configs:
        if cid not in reg["configs"] or cid not in stored["configs"]:
            problems.append(f"MISSING: {cid} not in the regression runs or the stored summary")
            continue
        for gid in R.RUN_GRADES:
            for k, a in reg["configs"][cid]["scorecard"][gid]["stats"].items():
                if k in REG_SKIP.get(cid, ()):
                    continue
                b = stored["configs"][cid]["scorecard"][gid]["stats"].get(k)
                checks.append((cid, k, a.get("median"), b))
        for k in REG_SCENARIO_KEYS.get(cid, []):
            a = reg["scenarios"].get(cid, {}).get("stats", {}).get(k)
            b = stored["scenarios"].get(cid, {}).get("stats", {}).get(k)
            checks.append((cid, k, a.get("median") if a else None, b))
    for cid, k, med, b in checks:
        if b is None or b.get("p10") is None:
            continue
        if med is None:
            problems.append(f"DRIFT: {cid} {k}: no value in the regression runs (stored [{b['p10']:.4g}, {b['p90']:.4g}])")
        elif not (b["p10"] <= med <= b["p90"]):
            problems.append(f"DRIFT: {cid} {k}: 3-seed median {med:.4g} outside the stored 20-seed [p10, p90] = [{b['p10']:.4g}, {b['p90']:.4g}]")
    print(f"(b) {len(checks)} metric checks against {stored_path.relative_to(REPO)}")
    if rebaseline:
        print("--rebaseline: the stored numbers are rewritten by re-running the full lab report "
              "(scripts/realism_lab.py --report-only); only after an approved spec changes behaviour")
    for p in problems:
        print(p)
    print("REGRESSION", "FAILED" if problems else "PASSED")
    return 1 if problems else 0


# ══════════════════════════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════════════════════════


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", default="c1",
                        choices=["c1", "c2", "c3", "c3-null", "c4", "all", "regression", "regression-legacy",
                                 "b", "s1", "s1r2", "s2", "s2r", "step", "final",
                                 "a-env", "a-retail", "a-lp", "a-sweep", "a-sweep-r", "a-confirm"])
    ap.add_argument("--winner", default=None, help="s1r2: the round-1 winner (default: from docs/v1.4/lab/selection_s1.json); a-sweep-r: the A7 sweep winner (default: from docs/v1.5/lab/selection_sweep.json)")
    ap.add_argument("--seeds", default=None, help="comma-separated (default: the 20 lab seeds)")
    ap.add_argument("--workers", type=int, default=min((os.cpu_count() or 2) - 1, 6))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--configs", default=None, help="comma-separated subset of the campaign's configs")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--rebaseline", action="store_true")
    ap.add_argument("--no-summary", action="store_true", help="do not (re)write docs/v1.3/lab/summary.json")
    a = ap.parse_args(argv)

    from api.jobs import engine_version

    engine = engine_version()
    if a.campaign == "regression-legacy":  # spec v1.4 §10.5: the v1.3 set, kept
        return regression(a.workers, engine, legacy=True)
    if a.campaign == "regression":
        if a.rebaseline:  # v1.4: the stored baseline is written by the N5 report (lab_v14.write_lab_summary)
            s = build_summary(LAB_DIR, lab.SEEDS)
            (DOC_DIR / "summary.json").write_text(json.dumps(_jsonable(s), separators=(",", ":")), encoding="utf-8")
            print("stored 20-seed summary rewritten from runs/_lab (--rebaseline)")
            ref_path = DOC_DIR / "reference_hashes.json"
            m42 = load_metrics(LAB_DIR, "C-DEF", 42)
            if m42:
                ref = json.loads(ref_path.read_text(encoding="utf-8"))
                ref["runs"]["A"].update(execs=m42["fingerprint"]["execs"], holdings=m42["fingerprint"]["holdings"],
                                        n_execs=m42["fingerprint"]["n_execs"])
                ref["rebaselined"] = date.today().isoformat()
                ref_path.write_text(json.dumps(ref, indent=2), encoding="utf-8")
        return regression(a.workers, engine)

    if a.campaign in getattr(lab, "V15_CAMPAIGNS", ()):  # spec v1.5 (R4)
        import lab_v15

        return lab_v15.main_v15(a, engine)
    if a.campaign in lab.V14_CAMPAIGNS:
        import lab_v14

        return lab_v14.main_v14(a, engine)

    seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else lab.SEEDS
    configs = a.configs.split(",") if a.configs else lab.CAMPAIGNS.get(a.campaign, ["C-NULL"])
    unknown = [c for c in configs if c not in lab.CONFIGS]
    if unknown:
        ap.error(f"unknown configs {unknown}")
    print(f"engine {engine}; campaign {a.campaign}; configs {configs}; {len(seeds)} seeds; {a.workers} workers")
    if "+dirty" in engine:
        print("note: engine_version is +dirty (tracked files have uncommitted changes)")

    failed = []
    if not a.report_only:
        tasks = [(c, s) for c in configs for s in seeds if a.force or not is_done(LAB_DIR, c, s, engine)]
        skipped = len(configs) * len(seeds) - len(tasks)
        print(f"{len(tasks)} runs to do, {skipped} already done")
        t0 = time.time()
        _, failed = run_all(tasks, LAB_DIR, a.workers, engine)
        print(f"runs finished in {(time.time() - t0) / 60:.1f} min; {len(failed)} failed")
        for key, msg in failed:
            print("  FAILED", key, msg)

    summary = build_summary(LAB_DIR, lab.SEEDS)
    summary["failed_runs"] = [{"config": k[0], "seed": k[1], "error": m} for k, m in failed]
    if not a.no_summary:
        DOC_DIR.mkdir(parents=True, exist_ok=True)
        (DOC_DIR / "summary.json").write_text(json.dumps(_jsonable(summary), separators=(",", ":")), encoding="utf-8")
    md = tables(summary)
    (LAB_DIR / "tables.md").write_text(md, encoding="utf-8")
    made = figures(summary, FIG_DIR)
    print(f"summary: {len(summary['configs'])} configs, {len(summary['scenarios'])} scenarios; figures: {made}")
    print(f"tables: {(LAB_DIR / 'tables.md').relative_to(REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

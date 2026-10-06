"""Simulation jobs: cache keys, the worker process and the FIFO job queue.

- run_id = first 12 hex chars of sha1(normalised RunParams JSON + engine_version)
- engine_version = git short hash, plus "+dirty" when tracked files have
  uncommitted changes (so code changes invalidate the cache)
- runs execute one at a time in a separate (spawned) process; up to
  MAX_QUEUED further requests wait in FIFO order
- results are written atomically to runs/<run_id>.json, with a small
  runs/<run_id>.meta.json sidecar used for listings and expected durations
"""

import hashlib
import json
import os
import statistics
import subprocess
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .schema import RunParams

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"
MAX_QUEUED = 3
TIMEOUT_S = 15 * 60
TICKER = "ABM"


# ── identity and cache ────────────────────────────────────────────────────


def engine_version() -> str:
    def git(*args) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10
        ).stdout.strip()

    try:
        short = git("rev-parse", "--short", "HEAD") or "unknown"
        dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return short + ("+dirty" if dirty else "")


def make_run_id(params: RunParams, engine: str) -> str:
    key = json.dumps(params.normalised(), sort_keys=True, separators=(",", ":")) + engine
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def payload_path(run_id: str, runs_dir: Path = RUNS_DIR) -> Path:
    return runs_dir / f"{run_id}.json"


def meta_path(run_id: str, runs_dir: Path = RUNS_DIR) -> Path:
    return runs_dir / f"{run_id}.meta.json"


def list_runs(runs_dir: Path = RUNS_DIR) -> List[Dict]:
    """Cached runs (meta sidecars), newest first."""
    out = []
    for p in runs_dir.glob("*.meta.json"):
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload_path(meta["run_id"], runs_dir).exists():
            out.append(meta)
    out.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return out


def expected_seconds(end_time: str, runs_dir: Path = RUNS_DIR) -> Optional[float]:
    """Median wall time of the last 5 cached runs with the same end_time.

    Uses the whole job time (process start, simulation and export) when the
    server recorded it, since that is what the progress banner counts."""
    walls = [
        m.get("job_s", m["wall_time_s"])
        for m in list_runs(runs_dir)
        if m["params"]["end_time"] == end_time
    ][:5]
    return round(statistics.median(walls), 1) if walls else None


def _atomic_write_json(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), allow_nan=False)
    os.replace(tmp, path)


# ── the simulation itself ─────────────────────────────────────────────────


def build_run_config(params: RunParams) -> Dict:
    from abides_markets.configs.rmsc04_ekf import build_config

    return build_config(
        seed=params.seed,
        end_time=params.end_time,
        ticker=TICKER,
        num_ekf_agents=params.num_fund,
        num_mom_ekf_agents=params.num_mom,
        book_logging=True,
        # background agents: no order logging (logs only, no behaviour change);
        # our EKF agents always log orders (set inside the config)
        log_orders=None,
        stdout_log_level="WARNING",
        news_events=[(n.offset, TICKER, n.sentiment, n.headline) for n in params.news] or None,
    )


def execute(params: RunParams, run_id: str, engine: str, runs_dir: Path = RUNS_DIR) -> Dict:
    """Run ABIDES, export the payload and write it (plus its meta sidecar).

    The kernel writes a summary log under ./log; run inside
    runs/_abides_logs so it lands in the gitignored runs directory."""
    from abides_core import abides

    from .export import build_payload

    runs_dir.mkdir(parents=True, exist_ok=True)
    log_root = runs_dir / "_abides_logs"
    log_root.mkdir(exist_ok=True)
    cwd = os.getcwd()
    os.chdir(log_root)
    try:
        config = build_run_config(params)
        t0 = time.time()
        end_state = abides.run(config)
        wall = time.time() - t0
    finally:
        os.chdir(cwd)

    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = build_payload(end_state, config, params, run_id, engine, wall, TICKER, created)
    _atomic_write_json(payload_path(run_id, runs_dir), payload)
    _atomic_write_json(meta_path(run_id, runs_dir), {
        "run_id": run_id,
        "params": params.model_dump(),
        "engine_version": engine,
        "created_at": created,
        "wall_time_s": round(wall, 2),
        "summary": {
            "close": payload["stats"]["close"],
            "change_pct": payload["stats"]["change_pct"],
            "trades": payload["market"]["totals"]["trades"],
        },
    })
    return payload


def _worker_main(params_json: str, run_id: str, engine: str, runs_dir: str) -> None:
    """Entry point of the spawned worker process."""
    try:
        execute(RunParams.model_validate_json(params_json), run_id, engine, Path(runs_dir))
    except BaseException:
        tail = "".join(traceback.format_exc().splitlines(keepends=True)[-25:])
        (Path(runs_dir) / f"{run_id}.error.txt").write_text(tail, encoding="utf-8")
        raise


# ── job queue ─────────────────────────────────────────────────────────────


class QueueFull(Exception):
    pass


@dataclass
class Job:
    run_id: str
    params: RunParams
    engine: str
    status: str = "queued"  # queued | running | done | failed
    error: Optional[str] = None
    started: Optional[float] = None
    finished: Optional[float] = None
    expected_s: Optional[float] = None
    submitted: float = field(default_factory=time.time)

    def view(self) -> Dict:
        if self.started is None:
            elapsed = 0.0
        else:
            elapsed = (self.finished or time.time()) - self.started
        out = {
            "run_id": self.run_id,
            "status": self.status,
            "elapsed_s": round(elapsed, 1),
            "expected_s": self.expected_s,
        }
        if self.error:
            out["error"] = self.error
        return out


class JobManager:
    """One simulation at a time in a spawned process; FIFO queue behind it."""

    def __init__(self, runs_dir: Path = RUNS_DIR, timeout_s: float = TIMEOUT_S):
        self.runs_dir = runs_dir
        self.timeout_s = timeout_s
        self.jobs: Dict[str, Job] = {}
        self.queue: deque = deque()
        self.cond = threading.Condition()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._loop, name="sim-worker", daemon=True)
        self._thread.start()

    def submit(self, params: RunParams) -> Job:
        engine = engine_version()
        run_id = make_run_id(params, engine)
        with self.cond:
            job = self.jobs.get(run_id)
            if job and job.status in ("queued", "running"):
                return job
            if payload_path(run_id, self.runs_dir).exists():
                job = Job(run_id, params, engine, status="done", started=0.0, finished=0.0)
                self.jobs[run_id] = job
                return job
            if len(self.queue) >= MAX_QUEUED:
                raise QueueFull(f"{len(self.queue)} simulations already queued; try again later")
            job = Job(run_id, params, engine, expected_s=expected_seconds(params.end_time, self.runs_dir))
            self.jobs[run_id] = job
            self.queue.append(job)
            self.cond.notify()
            return job

    def get(self, run_id: str) -> Optional[Job]:
        with self.cond:
            job = self.jobs.get(run_id)
        if job is None and payload_path(run_id, self.runs_dir).exists():
            meta = json.loads(meta_path(run_id, self.runs_dir).read_text(encoding="utf-8"))
            job = Job(run_id, RunParams.model_validate(meta["params"]), meta["engine_version"],
                      status="done", started=0.0, finished=0.0)
        return job

    def cancel(self, run_id: str) -> bool:
        """Cancel a queued job. A job already running finishes in the background."""
        with self.cond:
            job = self.jobs.get(run_id)
            if job and job.status == "queued":
                self.queue.remove(job)
                job.status, job.error = "failed", "cancelled before it started"
                return True
        return False

    def _record_job_time(self, job: Job) -> None:
        path = meta_path(job.run_id, self.runs_dir)
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
            meta["job_s"] = round(job.finished - job.started, 1)
            _atomic_write_json(path, meta)
        except (OSError, ValueError):
            pass

    def _loop(self) -> None:
        import multiprocessing as mp

        ctx = mp.get_context("spawn")
        while True:
            with self.cond:
                while not self.queue:
                    self.cond.wait()
                job = self.queue.popleft()
                job.status, job.started = "running", time.time()
            err_file = self.runs_dir / f"{job.run_id}.error.txt"
            err_file.unlink(missing_ok=True)
            proc = ctx.Process(
                target=_worker_main,
                args=(job.params.model_dump_json(), job.run_id, job.engine, str(self.runs_dir)),
                daemon=True,
            )
            proc.start()
            proc.join(self.timeout_s)
            with self.cond:
                job.finished = time.time()
                if proc.is_alive():
                    proc.terminate()
                    proc.join(5)
                    job.status, job.error = "failed", f"timed out after {self.timeout_s / 60:.0f} minutes"
                elif proc.exitcode == 0 and payload_path(job.run_id, self.runs_dir).exists():
                    job.status = "done"
                    self._record_job_time(job)
                else:
                    job.status = "failed"
                    job.error = (
                        err_file.read_text(encoding="utf-8") if err_file.exists()
                        else f"worker exited with code {proc.exitcode}"
                    )

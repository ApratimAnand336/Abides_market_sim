"""Pre-generated, seed-stable true-value oracle (FinVerse spec v1.2, Part 3).

The whole true-value path is generated once, at construction, on a fixed time
grid and from one dedicated random number generator per symbol. Queries only
read it. The path is therefore a pure function of (seed, params, grid,
session): it cannot depend on how many agents look at it or when, which the
lazy SparseMeanRevertingOracle could not guarantee.

Path sources are plain functions ``generate(params, times_ns, rng) -> values``
registered in PATH_SOURCES; adding a source (historical CSV replay, scripted
scenarios) means writing one function. v1.2 has "synthetic_ou"; v1.3 (spec
v1.3 §6.1) adds "scenario": the same path plus scripted events (value jumps,
volatility windows) for the realism lab, with no extra random draws.
"""

import logging
from math import ceil, exp, expm1, sqrt
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
from scipy.signal import lfilter

from abides_core import NanosecondTime

from .oracle import Oracle

logger = logging.getLogger(__name__)

PathFn = Callable[[Dict[str, Any], np.ndarray, np.random.RandomState], np.ndarray]


def _ou_draws(params: Dict[str, Any], times: np.ndarray, rng: np.random.RandomState) -> Dict[str, Any]:
    """Every random draw of the synthetic OU path, in the fixed order
    (the full eps vector, then the shock count, times, sizes and signs),
    plus the step constants a and sd. Shared by "synthetic_ou" and
    "scenario" so the two can never draw differently."""
    r_bar = float(params["r_bar"])
    kappa = float(params["kappa"])
    fund_vol = float(params["fund_vol"])
    n = len(times)
    d = float(times[1] - times[0]) if n > 1 else 1.0

    kd = kappa * d
    if kd < 1e-12:
        a, sd = 1.0, fund_vol * sqrt(d)
    else:
        a = exp(-kd)
        sd = sqrt(fund_vol ** 2 / (2.0 * kappa) * -expm1(-2.0 * kd))

    eps = rng.normal(size=n - 1)

    # megashocks: all from the dedicated rng, after eps
    lam = float(params.get("megashock_lambda_a", 0.0))
    span = float(times[-1] - times[0])
    n_shocks = rng.poisson(lam * span) if lam > 0 and span > 0 else 0
    shock_t = np.sort(rng.uniform(times[0], times[-1], size=n_shocks))
    shock_v = rng.normal(params.get("megashock_mean", 0.0), sqrt(params.get("megashock_var", 0.0)), size=n_shocks)
    shock_s = np.where(rng.randint(2, size=n_shocks) == 0, 1.0, -1.0)
    return {"r_bar": r_bar, "a": a, "sd": sd, "eps": eps, "shocks": (shock_t, shock_v, shock_s)}


def _add_shocks(innov: np.ndarray, times: np.ndarray, shocks) -> None:
    """A megashock enters the OU state at the first grid point >= its time."""
    n = len(times)
    for t_s, v_s, sign in zip(*shocks):
        k = int(np.searchsorted(times, t_s, side="left"))
        if k < n:
            innov[k] += sign * v_s


def generate_synthetic_ou(params: Dict[str, Any], times: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """Exact Ornstein-Uhlenbeck path on a regular grid plus Poisson megashocks.

    Same maths as SparseMeanRevertingOracle.compute_fundamental_at_timestamp,
    evaluated at every grid step d (ns):

        a = exp(-kappa d)
        v_{k+1} = r_bar + (v_k - r_bar) a + sqrt(fund_vol^2 / (2 kappa) (1 - a^2)) eps_k

    with 1 - a^2 computed as -expm1(-2 kappa d) (kappa d ~ 1.7e-7 here) and the
    random-walk limit (a = 1, sd = fund_vol sqrt(d)) when kappa d < 1e-12.

    Megashocks arrive as a Poisson process (rate megashock_lambda_a per ns) over
    [times[0], times[-1]]; each has size N(megashock_mean, megashock_var) with a
    50/50 sign, enters the OU state at the first grid point >= its time and then
    evolves with the OU dynamics (as v_adj does in the sparse oracle).

    Draw order is fixed: the full eps vector, then the shock count, times,
    sizes and signs. Values are floats in cents.
    """
    n = len(times)
    if n == 0:
        return np.array([], dtype=float)
    dr = _ou_draws(params, times, rng)

    # deviation from r_bar: x_{k+1} = a x_k + sd eps_k + jump_{k+1}
    innov = np.zeros(n)
    innov[1:] = dr["sd"] * dr["eps"]
    _add_shocks(innov, times, dr["shocks"])
    x = lfilter([1.0], [1.0, -dr["a"]], innov)
    return dr["r_bar"] + x


def applied_events(events: List[Dict[str, Any]], times: np.ndarray) -> List[Dict[str, Any]]:
    """Scenario events as applied to the grid: each jump records the grid
    time it lands on (the first grid point >= t_ns); each volatility window
    the number of grid steps it scales. Events outside the grid are kept with
    t_grid_ns = None / n_steps = 0 (they change nothing)."""
    out = []
    for ev in events:
        kind = ev.get("type")
        if kind == "jump":
            k = int(np.searchsorted(times, int(ev["t_ns"]), side="left"))
            out.append({"type": "jump", "t_ns": int(ev["t_ns"]), "cents": float(ev["cents"]),
                        "k": k if k < len(times) else None,
                        "t_grid_ns": int(times[k]) if k < len(times) else None})
        elif kind == "vol":
            t0, t1 = int(ev["t0_ns"]), int(ev["t1_ns"])
            ks = np.flatnonzero((times >= t0) & (times < t1))
            ks = ks[ks >= 1]  # innov[0] is the start value, not a step
            out.append({"type": "vol", "t0_ns": t0, "t1_ns": t1, "mult": float(ev["mult"]),
                        "k0": int(ks[0]) if len(ks) else None, "n_steps": int(len(ks))})
        else:
            raise ValueError(f"unknown scenario event type {kind!r} (expected 'jump' or 'vol')")
    return out


def generate_scenario_ou(params: Dict[str, Any], times: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """"synthetic_ou" plus scripted events (spec v1.3 §6.1), no extra draws.

    params["events"]: list of
        {"type": "jump", "t_ns": int, "cents": float}              value step
        {"type": "vol", "t0_ns": int, "t1_ns": int, "mult": float}  innovation scaling

    1. the same draws as synthetic_ou, in the same order (_ou_draws);
    2. innov[1:] = sd * eps; innov[k] *= mult for t0_ns <= times[k] < t1_ns;
    3. megashocks as synthetic_ou;
    4. innov[k] += cents at the first grid index with times[k] >= t_ns;
    5. x = lfilter([1], [1, -a], innov); r_bar + x.
    With no events the path is bit-identical to synthetic_ou. A jump of J adds
    J * a^(k - k0) from k0 on (a = exp(-kappa d): permanent within a day).
    """
    n = len(times)
    if n == 0:
        return np.array([], dtype=float)
    dr = _ou_draws(params, times, rng)
    events = applied_events(list(params.get("events") or []), times)

    innov = np.zeros(n)
    innov[1:] = dr["sd"] * dr["eps"]
    for ev in events:
        if ev["type"] == "vol" and ev["n_steps"]:
            ks = np.flatnonzero((times >= ev["t0_ns"]) & (times < ev["t1_ns"]))
            ks = ks[ks >= 1]
            innov[ks] *= ev["mult"]
    _add_shocks(innov, times, dr["shocks"])
    for ev in events:
        if ev["type"] == "jump" and ev["k"] is not None:
            innov[ev["k"]] += ev["cents"]
    x = lfilter([1.0], [1.0, -dr["a"]], innov)
    return dr["r_bar"] + x


PATH_SOURCES: Dict[str, PathFn] = {
    "synthetic_ou": generate_synthetic_ou,
    "scenario": generate_scenario_ou,  # spec v1.3 §6.1 (realism lab)
    # "csv": historical (time, value) shape rescaled to r_bar        (planned)
}


def generate_path(params: Dict[str, Any], times: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    """Dispatch to the path source named by params["path_source"]."""
    source = params.get("path_source", "synthetic_ou")
    if source not in PATH_SOURCES:
        raise ValueError(f"unknown path_source {source!r}; available: {sorted(PATH_SOURCES)}")
    return PATH_SOURCES[source](params, times, rng)


class PregeneratedOracle(Oracle):
    """True value served from a path generated once at construction.

    symbols: {symbol: params}. params as for SparseMeanRevertingOracle (r_bar,
    kappa, fund_vol, megashock_lambda_a, megashock_mean, megashock_var,
    random_state) plus optional "path_source" (default "synthetic_ou") and,
    for "scenario", "events". "random_state" is the ONLY RNG the path may use.

    self.events[symbol]: the scenario events as applied to the grid (empty
    for other sources), also logged at INFO level.

    Queries return the value at the last grid point <= t (a step function):
    an agent at time t never sees a value from after t.
    """

    def __init__(
        self,
        mkt_open: NanosecondTime,
        mkt_close: NanosecondTime,
        symbols: Dict[str, Dict[str, Any]],
        grid_s: float = 1.0,
    ) -> None:
        self.mkt_open = int(mkt_open)
        self.mkt_close = int(mkt_close)
        self.symbols = symbols
        self.grid_ns = int(round(grid_s * 1e9))
        n_steps = int(ceil((self.mkt_close - self.mkt_open) / self.grid_ns))
        self.times = self.mkt_open + self.grid_ns * np.arange(n_steps + 1, dtype=np.int64)

        self._values: Dict[str, np.ndarray] = {}
        self.f_log: Dict[str, List[Dict[str, Any]]] = {}
        self.events: Dict[str, List[Dict[str, Any]]] = {}
        for symbol, params in symbols.items():
            v = generate_path(params, self.times, params["random_state"])
            if params.get("path_source") == "scenario":
                self.events[symbol] = applied_events(list(params.get("events") or []), self.times)
                for ev in self.events[symbol]:
                    logger.info("PregeneratedOracle: %s scenario event %s", symbol, ev)
            else:
                self.events[symbol] = []
            self._values[symbol] = v
            served = self._serve(v)
            self.f_log[symbol] = [
                {"FundamentalTime": int(t), "FundamentalValue": int(x)}
                for t, x in zip(self.times, served)
            ]
            logger.debug("PregeneratedOracle: %s path of %d points", symbol, len(v))

    @staticmethod
    def _serve(v):
        """Float path -> integer cents, never negative (as ABIDES does)."""
        return np.rint(np.maximum(v, 0.0)).astype(np.int64)

    # ── queries ──────────────────────────────────────────────────────────

    def _index(self, t: NanosecondTime) -> int:
        if t < self.mkt_open:
            return 0
        if t >= self.mkt_close:
            return len(self.times) - 1
        return int((int(t) - self.mkt_open) // self.grid_ns)

    def value_at(self, symbol: str, t: NanosecondTime) -> float:
        """Exact (float, cents) true value in force at time t."""
        return float(self._values[symbol][self._index(t)])

    def path(self, symbol: str) -> Tuple[np.ndarray, np.ndarray]:
        """(grid times in ns, float values in cents) — copies."""
        return self.times.copy(), self._values[symbol].copy()

    def get_daily_open_price(self, symbol: str, mkt_open: NanosecondTime, cents: bool = True) -> int:
        return int(self._serve(self._values[symbol][:1])[0])

    def observe_price(
        self,
        symbol: str,
        current_time: NanosecondTime,
        random_state: np.random.RandomState,
        sigma_n: int = 1000,
    ) -> int:
        """Noisy observation of the true value at current_time.

        sigma_n is a VARIANCE (cents^2), as in ABIDES. The noise is drawn from
        the caller's random_state, so observations never touch the path."""
        i = self._index(current_time)
        r_t = int(self._serve(self._values[symbol][i:i + 1])[0])
        if sigma_n == 0:
            return r_t
        return int(round(random_state.normal(loc=r_t, scale=sqrt(sigma_n))))

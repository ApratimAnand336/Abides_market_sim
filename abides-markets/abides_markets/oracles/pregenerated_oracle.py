"""Pre-generated, seed-stable true-value oracle (FinVerse spec v1.2, Part 3).

The whole true-value path is generated once, at construction, on a fixed time
grid and from one dedicated random number generator per symbol. Queries only
read it. The path is therefore a pure function of (seed, params, grid,
session): it cannot depend on how many agents look at it or when, which the
lazy SparseMeanRevertingOracle could not guarantee.

Path sources are plain functions ``generate(params, times_ns, rng) -> values``
registered in PATH_SOURCES; adding a source (historical CSV replay, scripted
scenarios) means writing one function. Only "synthetic_ou" exists in v1.2.
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
    r_bar = float(params["r_bar"])
    kappa = float(params["kappa"])
    fund_vol = float(params["fund_vol"])
    n = len(times)
    if n == 0:
        return np.array([], dtype=float)
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

    # deviation from r_bar: x_{k+1} = a x_k + sd eps_k + jump_{k+1}
    innov = np.zeros(n)
    innov[1:] = sd * eps
    for t_s, v_s, sign in zip(shock_t, shock_v, shock_s):
        k = int(np.searchsorted(times, t_s, side="left"))
        if k < n:
            innov[k] += sign * v_s
    x = lfilter([1.0], [1.0, -a], innov)
    return r_bar + x


PATH_SOURCES: Dict[str, PathFn] = {
    "synthetic_ou": generate_synthetic_ou,
    # "csv": historical (time, value) shape rescaled to r_bar        (planned)
    # "scenario": synthetic path + scripted value jumps / vol regimes (planned)
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
    random_state) plus optional "path_source" (default "synthetic_ou").
    "random_state" is the ONLY RNG the path may use.

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
        for symbol, params in symbols.items():
            v = generate_path(params, self.times, params["random_state"])
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

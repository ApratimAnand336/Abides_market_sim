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
volatility windows) for the realism lab, with no extra random draws. v1.5 (spec v1.5
A3) adds "living_v1": day types, an intraday volatility shape, stress episodes and
information jumps with headlines (automatic news), all drawn from the same RNG.
"""

import logging
from math import ceil, exp, expm1, log, sqrt
from typing import Any, Callable, Dict, List, Optional, Tuple

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


# ── spec v1.5 A3: the living value process "living_v1" ─────────────────────

LIVING_DAY_TYPES = ("calm", "normal", "volatile")


def _living_cfg(params: Dict[str, Any]) -> Dict[str, Any]:
    cfg = params.get("living")
    if cfg is None:
        from ..configs.param_ranges import LIVING_V1 as cfg
    return cfg


def living_u_shape(times: np.ndarray, cfg: Dict[str, Any]) -> np.ndarray:
    """U(t) = (1 + u_open exp(-t/tau) + u_close exp(-(T - t)/tau)) / c_U, t in hours
    since the first grid point (the 09:30 open), T = session_h; c_U = mean of the
    numerator over the grid, so mean U = 1 over the oracle grid (the full session)."""
    t_h = (np.asarray(times, dtype=np.int64) - int(times[0])) / 3.6e12
    tau, T = float(cfg["u_tau_h"]), float(cfg["session_h"])
    num = 1.0 + cfg["u_open"] * np.exp(-t_h / tau) + cfg["u_close"] * np.exp(-(T - t_h) / tau)
    return num / num.mean()


def living_stress_chain(u: np.ndarray, p_in: float, p_out: float, mult: float) -> np.ndarray:
    """Two-state Markov chain S_k in {1, mult}, S_0 = 1, driven by one uniform per step:
    S_k is the state in force at step k; then, from state 1, u_k < p_in enters stress,
    and from the stressed state, u_k < p_out leaves it. (Computed episode by episode
    with searchsorted; equal to the per-step loop, tests/test_living_oracle.py.)"""
    n = len(u)
    S = np.ones(n)
    enter = np.flatnonzero(u < p_in)
    leave = np.flatnonzero(u < p_out)
    pos, stressed = 0, False
    while pos < n:
        arr = leave if stressed else enter
        j = int(np.searchsorted(arr, pos))
        if j >= len(arr):
            if stressed:
                S[pos:] = mult
            break
        k = int(arr[j])
        if stressed:
            S[pos:k + 1] = mult
        pos, stressed = k + 1, not stressed
    return S


def living_day_type(u: float, requested: str, cfg: Dict[str, Any]) -> str:
    """Day type: the requested one, or for "auto" calm if u < p_calm, normal if
    u < p_calm + p_normal, else volatile (30/50/20, D-R4-1)."""
    if requested != "auto":
        if requested not in LIVING_DAY_TYPES:
            raise ValueError(f"day_type must be 'auto' or one of {LIVING_DAY_TYPES}, got {requested!r}")
        return requested
    mix = cfg["day_mix"]
    c_calm = float(mix["calm"])
    c_normal = round(c_calm + float(mix["normal"]), 12)
    return "calm" if u < c_calm else ("normal" if u < c_normal else "volatile")


def jump_bucket(jump_cents: float, r_bar: float, edges_pct=(0.3, 1.0)) -> str:
    """Template bucket of a value jump: sign x size (small < 0.3% <= medium <= 1% < large)."""
    pct = 100.0 * abs(jump_cents) / r_bar
    size = "small" if pct < edges_pct[0] else ("medium" if pct <= edges_pct[1] else "large")
    return ("positive_" if jump_cents > 0 else "negative_") + size


def living_v1_day(params: Dict[str, Any], times: np.ndarray, rng: np.random.RandomState) -> Dict[str, Any]:
    """The "living_v1" path (spec v1.5 A3.1) and its day info.

        v_{k+1} = r_bar + (v_k - r_bar) a + sd0 * m_day * U(t_k) * S_k * eps_k + J_{k+1}

    a = exp(-kappa d) and sd0 as in synthetic_ou with fund_vol = sigma_base / sqrt(1e9)
    (sigma_base = 7.1 c per sqrt(s)); m_day by day type; U the intraday shape; S the
    stress chain (p_in = e_day / (6.5 h) per second, p_out = 1 / 45 min); J information
    jumps entering at the first grid point >= their time. Scripted "events" (jump/vol, as
    "scenario") are applied on top without extra draws. No megashocks.

    Draw order from rng (fixed, A3.2):
      1 one uniform for the day type (always drawn; used only when day_type = "auto",
        so a seed's path is the same whether its type was drawn or requested);
      2 N uniforms for the stress chain; 3 N-1 normals eps;
      4 news count ~ Poisson(n_day), times ~ U(open + 5 min, open + 6 h 25 min) (sorted),
        sizes m ~ LogNormal(ln 0.002, 0.6) capped at 2%, signs (uniform < 0.5 -> +),
        then one template index per jump, uniform within the jump's bucket (only if
        params["news_templates"] is given; these are the last draws, so the path never
        depends on the templates).
    """
    cfg = _living_cfg(params)
    n = len(times)
    r_bar = float(params["r_bar"])
    kappa = float(params["kappa"])

    # 1-3: day type, stress uniforms, diffusion normals
    u_day = float(rng.random_sample())
    day_type = living_day_type(u_day, params.get("day_type", "auto"), cfg)
    u_stress = rng.random_sample(n)
    eps = rng.normal(size=max(n - 1, 0))

    # 4: information jumps and their headlines
    n_news = int(rng.poisson(float(cfg["news_per_day"][day_type])))
    lo_s, hi_s = cfg["news_window_s"]
    t0 = float(times[0]) if n else 0.0
    t_news = np.sort(rng.uniform(t0 + lo_s * 1e9, t0 + hi_s * 1e9, size=n_news))
    m = rng.lognormal(mean=log(float(cfg["jump_median_frac"])), sigma=float(cfg["jump_sigma_ln"]), size=n_news)
    sign = np.where(rng.random_sample(n_news) < 0.5, 1.0, -1.0)
    jumps = r_bar * np.minimum(m, float(cfg["jump_cap_frac"])) * sign
    templates = params.get("news_templates")
    edges = tuple(cfg.get("size_edges_pct", (0.3, 1.0)))
    heads = []
    for J in jumps:
        b = jump_bucket(float(J), r_bar, edges)
        if templates:
            items = templates[b]
            item = items[int(rng.randint(len(items)))]
            heads.append((item["headline"], float(item["sentiment"]), b))
        else:
            heads.append((None, None, b))

    if n == 0:
        return {"values": np.array([], dtype=float),
                "info": {"day_type": day_type, "stress_episodes": [], "news": []}}

    # path
    d = float(times[1] - times[0]) if n > 1 else 1.0
    fv = float(cfg["sigma_base_c_per_sqrt_s"]) / sqrt(1e9)  # cents per sqrt(ns)
    kd = kappa * d
    if kd < 1e-12:
        a, sd0 = 1.0, fv * sqrt(d)
    else:
        a = exp(-kd)
        sd0 = sqrt(fv ** 2 / (2.0 * kappa) * -expm1(-2.0 * kd))
    U = living_u_shape(times, cfg)
    step_s = d / 1e9
    p_in = float(cfg["stress_episodes_per_day"][day_type]) / (float(cfg["session_h"]) * 3600.0) * step_s
    p_out = step_s / float(cfg["stress_mean_s"])
    S = living_stress_chain(u_stress, p_in, p_out, float(cfg["stress_mult"]))
    m_day = float(cfg["m_day"][day_type])

    innov = np.zeros(n)
    innov[1:] = sd0 * m_day * U[:-1] * S[:-1] * eps
    events = applied_events(list(params.get("events") or []), times)
    for ev in events:
        if ev["type"] == "vol" and ev["n_steps"]:
            ks = np.flatnonzero((times >= ev["t0_ns"]) & (times < ev["t1_ns"]))
            ks = ks[ks >= 1]
            innov[ks] *= ev["mult"]
    news = []
    for t_j, J, (h, sent, b) in zip(t_news, jumps, heads):
        k = int(np.searchsorted(times, int(t_j), side="left"))
        if k < n:
            innov[k] += J
            news.append((int(times[k]), float(J), h, sent, b))
    for ev in events:
        if ev["type"] == "jump" and ev["k"] is not None:
            innov[ev["k"]] += ev["cents"]
    x = lfilter([1.0], [1.0, -a], innov)

    stressed = S > 1.0
    starts = np.flatnonzero(stressed & ~np.concatenate([[False], stressed[:-1]]))
    episodes = []
    for k0 in starts:
        rest = np.flatnonzero(~stressed[k0:])
        k1 = int(k0 + rest[0]) if len(rest) else n - 1
        episodes.append((int(times[k0]), int(times[k1])))
    info = {"day_type": day_type, "stress_episodes": episodes, "news": news}
    return {"values": r_bar + x, "info": info}


def generate_living_v1(params: Dict[str, Any], times: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    return living_v1_day(params, times, rng)["values"]


PATH_SOURCES: Dict[str, PathFn] = {
    "synthetic_ou": generate_synthetic_ou,
    "scenario": generate_scenario_ou,  # spec v1.3 §6.1 (realism lab)
    "living_v1": generate_living_v1,  # spec v1.5 A3 (day types, stress, information news)
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
        self._day_info: Dict[str, Dict[str, Any]] = {}
        for symbol, params in symbols.items():
            if params.get("path_source") == "living_v1":
                res = living_v1_day(params, self.times, params["random_state"])
                v = res["values"]
                self._day_info[symbol] = res["info"]
            else:
                v = generate_path(params, self.times, params["random_state"])
            if params.get("path_source") in ("scenario", "living_v1"):
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

    def day_info(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """spec v1.5 A3.5: {"day_type", "stress_episodes": [(start_ns, end_ns)],
        "news": [(t_ns, J_cents, headline, sentiment, bucket)]} for a "living_v1"
        symbol (default: the first symbol); None for other path sources."""
        if symbol is None:
            symbol = next(iter(self.symbols))
        info = self._day_info.get(symbol)
        if info is None:
            return None
        return {"day_type": info["day_type"], "stress_episodes": list(info["stress_episodes"]),
                "news": list(info["news"])}

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

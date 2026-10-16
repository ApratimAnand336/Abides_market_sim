# Hyperparameter ranges for the custom EKF agents — single source of truth.
#
# rmsc04_ekf.py draws every randomised hyperparameter through `draw()` below,
# and the dashboard export sends these ranges to the frontend, so the ranges
# shown next to an agent's personality always match the distribution it was
# actually drawn from.
#
# Each entry is (min, max, scale):
#   "linear"  float, U[min, max]
#   "log"     float, exp(U[ln min, ln max])
#   "int"     integer, uniform over min..max inclusive (np.random.randint)
#   "floor"   integer, int(U[min, max + 1)) — same support as "int" but drawn
#             with a uniform float; kept for draws that historically used it so
#             seeded runs reproduce exactly.
#   "fixed"   min == max, never drawn (listed for display only)

from typing import Dict, Optional, Tuple

import numpy as np

Range = Tuple[float, float, str]

FUNDAMENTAL_RANGES: Dict[str, Range] = {
    "er_window": (5, 24, "floor"),
    # spec v1.1 F2: delta * mid = $0.50-$3, ER penalty 1.3x-2.7x at median ER
    "delta": (0.0005, 0.003, "linear"),
    "lambda_er": (0.5, 2.0, "linear"),
    "sigma_n": (300.0, 3000.0, "linear"),
    "initial_uncertainty": (50_000.0, 500_000.0, "linear"),
    "gamma": (0.4, 0.95, "linear"),
    "k": (0.3, 2.5, "linear"),
    "mu": (0.02, 0.2, "linear"),
    # spec v1.1 F3: process noise Q = q * sigma_f2_hat * dt
    "q": (0.3, 3.0, "log"),
    # spec v1.1 F4: target position sizing
    "a_max": (0.6, 1.0, "linear"),
    "z0": (1.0, 3.0, "linear"),
    "s_max": (0.10, 0.25, "linear"),
    "b_f": (0.01, 0.03, "linear"),
    # spec v1.1 F5: news shift in units of a typical 30-minute move
    "k_news": (0.5, 3.0, "linear"),
}

MOMENTUM_RANGES: Dict[str, Range] = {
    "n_er": (10, 25, "int"),
    # N_w's lower bound is max(n_er + 1, 15); see rmsc04_ekf.py
    "N_w": (15, 30, "int"),
    "lambda_er": (1.0, 6.0, "linear"),
    "kappa_R": (0.5, 2.0, "linear"),
    "c_P": (1.0, 5.0, "linear"),
    # spec v1.1 M3: tau = tau_ratio * wake_mean (15-40 looks per trend lifetime)
    "tau_ratio": (15.0, 40.0, "log"),
    # spec v1.1 M1: the agent sees ~tau/(tau + K_l/K_v) of a steady trend
    "kappa_l": (0.02, 0.15, "linear"),
    "kappa_v": (1.0, 2.0, "linear"),
    "a_eps": (0.1, 0.3, "linear"),
    "eps_thr": (2.0, 4.0, "linear"),
    "g_max": (10.0, 10.0, "fixed"),
    "gamma": (0.4, 0.95, "linear"),
    "k_c": (0.3, 2.5, "linear"),
    "theta_in": (1.5, 2.5, "linear"),
    "theta_out": (0.5, 1.0, "linear"),
    "ER_min": (0.2, 0.4, "linear"),
    "k_stop": (2.0, 4.0, "linear"),
    "k_re": (0.25, 0.5, "linear"),
    "T_0": (1.0, 3.0, "linear"),
    "lambda_v": (0.5, 2.0, "linear"),
    "e_max": (0.7, 0.95, "linear"),
    "e_min": (0.0, 0.0, "fixed"),
    "b": (0.1, 0.1, "fixed"),
    "n_min": (1, 1, "fixed"),
    "k_add": (0.25, 0.75, "linear"),
    "mu_m": (0.5, 2.0, "linear"),
    "eta_news": (0.0, 0.5, "linear"),
    "rho_news": (1.0, 5.0, "linear"),
    "wake_mean": (10.0, 60.0, "linear"),
}


# spec v1.4 §4.6: informed fundamentalists. Drawn per agent in THIS order,
# after the agent's FUNDAMENTAL_RANGES draws (FUNDAMENTAL_RANGES are also
# used; "mu" is drawn but unused in informed mode). T_r and sigma_r come
# from the design level (spec v1.4 §7.3), per agent log-uniform in its range.
INFORMED_RANGES: Dict[str, Range] = {
    "wake_mean": (30.0, 120.0, "log"),  # s, mean Poisson wake gap
    "rho": (3.0, 100.0, "log"),  # price distrust: R_m = rho * R_noise
    "m0": (1.0, 3.0, "linear"),  # cents, base required edge
    "kappa_m": (0.0, 0.5, "linear"),  # required edge per sd of belief
    "h0": (1.0, 5.0, "linear"),  # cents, quote half-width beyond the edge
    "theta_q": (0.005, 0.02, "linear"),  # quote size, fraction of wealth per side
}
INFORMED_DESIGN_KEYS = ("T_r_range_s", "sigma_r_range_c", "wealth_c")

# spec v1.4.2 D-R3-7: the R3 design (D-60fl2M, learning off), used by the
# default market (api.jobs.run_config_kwargs, spec v1.4 §6.1) with 60 agents.
# No "price_learning" key: absent = "off" (identical to the lab's D-60fl2M).
DEFAULT_INFORMED_DESIGN: Dict = {"T_r_range_s": [60.0, 300.0], "sigma_r_range_c": [10.0, 50.0],
                                 "wealth_c": 200_000_000}
DEFAULT_NUM_INFORMED = 60
INFORMED_W_BOUNDS = (-0.5, 1.5)  # = fundamental.INFORMED_W_MIN / _MAX (spec v1.4 §4.5)

# spec v1.5 A3.1: the living true-value process (oracle path source "living_v1").
# Fixed model constants (not drawn per agent); every random element of the day is
# drawn by the oracle from the symbol's own RandomState (A3.2).
LIVING_V1: Dict = {
    "sigma_base_c_per_sqrt_s": 7.1,  # cents per sqrt(s) = 5.5 bps/min at $1000
    "m_day": {"calm": 0.6, "normal": 1.0, "volatile": 1.6},
    "day_mix": {"calm": 0.30, "normal": 0.50, "volatile": 0.20},  # D-R4-1
    # intraday shape U(t) = (1 + a_open exp(-t/tau) + a_close exp(-(T - t)/tau)) / c_U
    "u_open": 0.6, "u_close": 0.4, "u_tau_h": 0.5, "session_h": 6.5,
    # stress: 2-state Markov chain on the 1 s grid, S in {1, s_mult}
    "stress_mult": 2.5,
    "stress_episodes_per_day": {"calm": 0.2, "normal": 0.7, "volatile": 1.5},
    "stress_mean_s": 45 * 60,
    # information jumps: Poisson count, times U(open + 5 min, open + 6 h 25 min)
    "news_per_day": {"calm": 2, "normal": 3, "volatile": 4},
    "news_window_s": (5 * 60, 6 * 3600 + 25 * 60),
    "jump_median_frac": 0.0020, "jump_sigma_ln": 0.6, "jump_cap_frac": 0.02,
    "size_edges_pct": (0.3, 1.0),  # small < 0.3% <= medium <= 1% < large
}
DAY_TYPES = ("calm", "normal", "volatile")

# spec v1.5 A4: the retail trader crowd (RetailCrowdAgent + RetailTraderAgent). Fixed
# constants; the sweep dials (A7) are the trader count N_r and kappa_v.
RETAIL: Dict = {
    "mu_per_agent": 4.0,  # actions per trader per day (spread over 23,400 s)
    "kappa_n": 2.0,  # intensity per unit of news level Nn
    "kappa_v_levels": (1.0, 3.0),  # sweep dial (A7); refinement 5
    "cap": 10.0,  # cap on the intensity multiplier
    "dt_c_s": 5.0,  # crowd tick, s
    "buffer_s": 3600.0,  # ring buffer of 5-s mids
    "n_short": 24,  # sigma_short over the last 24 5-s intervals (2 min)
    "ref_half_life_s": 3600.0,  # sigma_ref EWMA half-life
    "warmup_s": 600.0,  # V = 1 during the first 10 min
    "news_half_life_s": 600.0,  # Nn half-life
    "wealth_c": 5_000_000,  # $50,000 per trader
    "stock_frac": 0.5,  # half in stock at r_bar (25 shares at $1000)
    "p_kinds": (0.5, 0.25, 0.25),  # liquidity, trend, contrarian
    "beta": 0.87,  # P(buy) = 0.85 after a +2 sd 30-min rise (trend)
    "p_stop": 0.4,  # stop-loss users (0.6 in the crash fragility profile, B2.3)
    "stop_d_range": (0.02, 0.06),  # stop distance below the buy fill, per trader
    "size_median": 30.0, "size_sigma_ln": 0.8,  # order size LogNormal(ln 30, 0.8) shares
    "collar": 0.02,  # broker collar on marketable orders
}

# spec v1.5 A5: our market makers (LiquidityProviderAgent). Fixed constants; the sweep
# dials (A7) are the count n_lp and the capital W per LP.
LP: Dict = {
    "dt_s": 5.0,  # wake interval, s (first wake offset by the LP's index)
    "sigma_half_life_s": 300.0,  # EWMA of the per-second variance of log ref changes
    "sigma_prior_bps_per_min": 5.5,
    "c_h": 0.5,  # half-spread h = max(1 c, c_h * typical 10-s move)
    "l_max": 0.5,  # inventory limit q_max = floor(l_max * W / ref) (0.25 when stressed, B2.3)
    "psi": 1.0,  # inventory skew = psi * (q / q_max) * h
    "levels": 3,  # ladder levels per side at r -/+ k h
    "theta_lp": 0.02,  # quoted size per side = 2% of wealth (split over the levels)
    "requote_max_s": 30.0, "requote_q_frac": 0.1, "requote_ref_frac_h": 0.5,  # lazy requote
    "overshoot": 1.2,  # |q| > 1.2 q_max -> marketable order back to q_max
    "collar": 0.02,
    "budget_L": 2.0,  # gross position value <= 2 W
    "n_lp_levels": (2, 4),  # sweep dial (A7); refinement 3
    "wealth_levels_c": (500_000_000, 2_000_000_000),  # $5M | $20M; refinement $50M
}

# spec v1.4.1 §2.3: learning from prices. n_pl fixed per level; eps_thr and
# a_pl drawn per agent AFTER all its other informed draws; "off" draws nothing.
PRICE_LEARNING_LEVELS: Dict[str, Dict] = {
    "off": {},
    "mod": {"n_pl": 3, "eps_thr": (1.0, 4.0, "log"), "a_pl": (0.2, 0.4, "linear")},
    "strong": {"n_pl": 2, "eps_thr": (0.5, 2.0, "log"), "a_pl": (0.2, 0.4, "linear")},
}


def draw(ranges: Dict[str, Range], name: str, low=None):
    """Draw one value with the global np.random (seeded by the config).

    low: optional override of the lower bound (used for N_w)."""
    lo, hi, scale = ranges[name]
    if low is not None:
        lo = low
    if scale == "linear":
        return np.random.uniform(lo, hi)
    if scale == "log":
        return float(np.exp(np.random.uniform(np.log(lo), np.log(hi))))
    if scale == "int":
        return int(np.random.randint(lo, hi + 1))
    if scale == "floor":
        return int(np.random.uniform(lo, hi + 1))
    if scale == "fixed":
        return lo
    raise ValueError(f"unknown scale {scale!r} for {name}")


def ranges_for_export(informed_design: Optional[Dict] = None) -> Dict[str, Dict[str, Dict]]:
    """{"fundamental"|"momentum"|"informed"[|"price_learning"]: {name: {min, max[, scale]}}}
    for the dashboard. "informed" holds INFORMED_RANGES, the fixed w_min/w_max
    and this run's design ranges of T_r and sigma_r (default design if None);
    "price_learning" the drawn ranges of the run's learning level (if on)."""

    def fmt(ranges: Dict[str, Range]) -> Dict[str, Dict]:
        out = {}
        for name, (lo, hi, scale) in ranges.items():
            entry = {"min": float(lo), "max": float(hi)}
            if scale == "log":
                entry["scale"] = "log"
            out[name] = entry
        return out

    d = informed_design or DEFAULT_INFORMED_DESIGN
    informed = fmt(INFORMED_RANGES)
    informed["T_r"] = {"min": float(d["T_r_range_s"][0]), "max": float(d["T_r_range_s"][1]), "scale": "log"}
    informed["sigma_r"] = {"min": float(d["sigma_r_range_c"][0]), "max": float(d["sigma_r_range_c"][1]), "scale": "log"}
    informed["w_min"] = {"min": INFORMED_W_BOUNDS[0], "max": INFORMED_W_BOUNDS[0]}
    informed["w_max"] = {"min": INFORMED_W_BOUNDS[1], "max": INFORMED_W_BOUNDS[1]}
    out = {"fundamental": fmt(FUNDAMENTAL_RANGES), "momentum": fmt(MOMENTUM_RANGES), "informed": informed}
    level = d.get("price_learning", "off")
    if level != "off":
        lv = PRICE_LEARNING_LEVELS[level]
        out["price_learning"] = {"n_pl": {"min": float(lv["n_pl"]), "max": float(lv["n_pl"])},
                                 **fmt({k: lv[k] for k in ("eps_thr", "a_pl")})}
    return out

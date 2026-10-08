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

from typing import Dict, Tuple

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
    "tau": (120.0, 1800.0, "log"),
    "kappa_l": (0.05, 0.5, "linear"),
    "kappa_v": (0.5, 2.0, "linear"),
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


def ranges_for_export() -> Dict[str, Dict[str, Dict]]:
    """{"fundamental"|"momentum": {name: {min, max[, scale]}}} for the dashboard."""

    def fmt(ranges: Dict[str, Range]) -> Dict[str, Dict]:
        out = {}
        for name, (lo, hi, scale) in ranges.items():
            entry = {"min": float(lo), "max": float(hi)}
            if scale == "log":
                entry["scale"] = "log"
            out[name] = entry
        return out

    return {"fundamental": fmt(FUNDAMENTAL_RANGES), "momentum": fmt(MOMENTUM_RANGES)}

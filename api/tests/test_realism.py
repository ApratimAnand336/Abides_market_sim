"""Realism metrics on synthetic inputs with known answers (spec v1.3 §11.2, T-R1 … T-R12).

No simulation runs here: every input is generated with a fixed seed."""

import json
import math

import numpy as np
import pytest

from api import realism as R
from api.stats import acf, gap_half_life


def _closes(r):
    return 1000.0 * np.exp(np.concatenate([[0.0], np.cumsum(r)]))


# T-R1 ─────────────────────────────────────────────────────────────────────
def test_r1_sigma_1m_bps():
    rng = np.random.RandomState(1)
    est = [R.sigma_1m_bps(rng.normal(0, 7e-4, size=389)) for _ in range(2000)]
    assert abs(np.median(est) / 7.0 - 1.0) <= 0.02


# T-R2 ─────────────────────────────────────────────────────────────────────
def _ar1(phi, n, rng, sd=1.0):
    e = rng.normal(0, sd, size=n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def test_r2_ac1():
    rng = np.random.RandomState(2)
    assert abs(acf(_ar1(0.3, 10_000, rng), 1)[0] - 0.3) <= 0.03
    assert abs(acf(rng.normal(size=10_000), 1)[0]) < 0.05


# T-R3 ─────────────────────────────────────────────────────────────────────
def test_r3_variance_ratio():
    rng = np.random.RandomState(3)
    assert abs(R.variance_ratio(_closes(rng.normal(0, 1e-4, 20_000)), 5) - 1.0) <= 0.05
    phi = 0.3
    theory = 1 + 2 * sum((1 - j / 5) * phi ** j for j in range(1, 5))
    vr = R.variance_ratio(_closes(_ar1(phi, 20_000, rng, sd=1e-4)), 5)
    assert abs(vr / theory - 1.0) <= 0.05


# T-R4 ─────────────────────────────────────────────────────────────────────
def _garch(n, rng, omega=0.05, alpha=0.15, beta=0.80):
    r = np.zeros(n)
    h = omega / (1 - alpha - beta)
    for i in range(n):
        r[i] = math.sqrt(h) * rng.normal()
        h = omega + alpha * r[i] ** 2 + beta * h
    return r


def test_r4_clustering():
    rng = np.random.RandomState(4)
    c = R.clustering(_garch(50_000, rng))
    assert c["cs"] >= 0.15 and c["ps"] > 0.05
    assert R.clustering(rng.normal(size=50_000))["cs"] < 0.05


# T-R5 ─────────────────────────────────────────────────────────────────────
def test_r5_kurtosis_laplace():
    from scipy import stats as sps

    rng = np.random.RandomState(5)
    assert abs(sps.kurtosis(rng.laplace(size=100_000), fisher=True) - 3.0) <= 0.3


# T-R6 ─────────────────────────────────────────────────────────────────────
def test_r6_vv_corr():
    rng = np.random.RandomState(6)
    rv = rng.lognormal(0, 0.5, size=78)
    assert R.vv_corr_buckets(rv, 1000 * rv + rng.normal(0, 100, size=78)) > 0.8
    assert abs(R.vv_corr_buckets(rv, rng.lognormal(0, 0.5, size=78))) < 0.25
    # the bucket builder: 389 returns, 390 volume bars -> 78 buckets
    r = rng.normal(0, 1e-4, 389)
    b_rv, b_v = R.vv_buckets(r, np.ones(390))
    assert len(b_rv) == len(b_v) == 78 and np.all(b_v == 5)
    assert np.isclose(np.sum(b_rv ** 2), np.sum(r ** 2))


# T-R7 ─────────────────────────────────────────────────────────────────────
def test_r7_regime_contrast():
    rng = np.random.RandomState(7)
    ratios = [R.regime_contrast(rng.normal(0, 1e-4, 389)) for _ in range(500)]
    assert 1.35 <= np.median(ratios) <= 1.85
    r = rng.normal(0, 1e-4, 389)
    m = R.minute_of_return(389)
    r[(m >= 180) & (m < 240)] *= 5.0  # 12:30-13:30: two full windows at 5x
    assert R.regime_contrast(r) > 4


# T-R8 ─────────────────────────────────────────────────────────────────────
_R8_BIAS = (
    "spec v1.3 §3.7 estimator (de-meaned ACF of ONE 6.5 h day) is biased low for long "
    "half-lives: measured 2026-10-12, median over 20 paths 20.8 min for a true 45 min "
    "(-54%) and 27.1 min for 90 min (-70%). Mean-removal bias of the sample ACF, "
    "about -(1+phi)/((1-phi) N); reported in docs/v1.3/REPORT.md, not fixed in R2"
)


@pytest.mark.parametrize("half_life_min,tol", [
    (1, 0.25), (10, 0.25),
    pytest.param(45, 0.25, marks=pytest.mark.xfail(strict=True, reason=_R8_BIAS)),
    pytest.param(90, 0.50, marks=pytest.mark.xfail(strict=True, reason=_R8_BIAS)),
])
def test_r8_gap_half_life(half_life_min, tol):
    """AR(1) gaps on a 1 s grid over 6.5 h, LAB_GAP_LAGS. The median over 20
    paths must be within tol; the spread over paths is printed (run with -s).
    The 45 and 90 min cases fail as specified: see _R8_BIAS."""
    rng = np.random.RandomState(80 + half_life_min)
    phi = math.exp(-math.log(2) / (half_life_min * 60.0))
    est = []
    for _ in range(20):
        g = _ar1(phi, 23_401, rng)
        h = gap_half_life(g, lags_s=R.LAB_GAP_LAGS)["half_life_min"]
        est.append(np.nan if h is None else h)
    est = np.array(est)
    err = np.nanmedian(est) / half_life_min - 1.0
    print(f"half-life {half_life_min} min: median {np.nanmedian(est):.2f} "
          f"(error {100 * err:+.0f}%), p10-p90 {np.nanpercentile(est, 10):.2f}-{np.nanpercentile(est, 90):.2f}, "
          f"None in {int(np.isnan(est).sum())}/20")
    assert abs(err) <= tol


# T-R9 ─────────────────────────────────────────────────────────────────────
def _jump_series(f_min, t0=5400, n=23_401, J=20.0, noise=0.0, seed=9):
    rng = np.random.RandomState(seed)
    t = np.arange(n, dtype=float)
    tm = np.clip((t - t0) / 60.0, 0, None)
    f = np.where(t >= t0, f_min(tm), 0.0)
    B = {"mid_1s": np.full(n, 1000.0)}
    T = {"mid_1s": 1000.0 + J * (f + rng.normal(0, noise, n))}
    for S in (T, B):
        S["vol_1m"] = np.ones(390)
        S["net_1m"] = np.zeros((len(R.FLOW_CLASSES), 390))
    return T, B


def test_r9_jump_analysis():
    tau = 4.0
    T, B = _jump_series(lambda m: 1 - np.exp(-m / tau), noise=0.005)
    out = R.jump_response(T, B, 5400, 20.0)
    assert abs(out["t90"] / (tau * math.log(10)) - 1.0) <= 0.10
    assert out["overshoot"] < 0.01  # noise only: the smoothed f can poke above 1

    T, B = _jump_series(lambda m: 1 - np.exp(-m / tau))
    assert R.jump_response(T, B, 5400, 20.0)["overshoot"] == 0.0

    over = lambda m: 1 + 0.3 * np.exp(-m / 10) * (1 - np.exp(-m))  # noqa: E731
    true = float(np.max(over(np.linspace(0, 60, 100_001)))) - 1.0
    T, B = _jump_series(over)
    assert abs(R.jump_response(T, B, 5400, 20.0)["overshoot"] - true) <= 0.03


# T-R10 ────────────────────────────────────────────────────────────────────
def test_r10_impact_beta_and_noise_floor():
    rng = np.random.RandomState(10)
    sizes = {"IMP-0.1": 0.001, "IMP-0.5": 0.005, "IMP-1": 0.01, "IMP-5": 0.05}
    q = {k: v * rng.uniform(0.9, 1.1, 20) for k, v in sizes.items()}
    I = {k: 20 * q[k] ** 0.5 * rng.lognormal(0, 0.3, 20) for k in sizes}
    out = R.impact_beta(q, I)
    assert abs(out["beta"] - 0.5) <= 0.05
    assert out["ci"][0] <= 0.5 <= out["ci"][1]

    floor = R.noise_floor(rng.normal(0, 0.1, 20), rng.normal(0, 0.1, 20))
    assert R.resolved(1.9 * floor["I_end"], floor["I_end"]) is False
    assert R.resolved(2.0 * floor["I_end"], floor["I_end"]) is True


# T-R11 ────────────────────────────────────────────────────────────────────
BOUNDARIES = [
    # (band, metric values, expected grade)
    ("G1", {"sigma_1m_bps": 5.0}, "PASS"), ("G1", {"sigma_1m_bps": 10.0}, "PASS"),
    ("G1", {"sigma_1m_bps": 2.5}, "WARN"), ("G1", {"sigma_1m_bps": 20.0}, "WARN"),
    ("G1", {"sigma_1m_bps": 2.49}, "FAIL"), ("G1", {"sigma_1m_bps": 20.01}, "FAIL"),
    ("G2", {"sigma_day_xseed": 1.0}, "PASS"), ("G2", {"sigma_day_xseed": 2.0}, "PASS"),
    ("G2", {"sigma_day_xseed": 0.5}, "WARN"), ("G2", {"sigma_day_xseed": 4.0}, "WARN"),
    ("G2", {"sigma_day_xseed": 4.01}, "FAIL"),
    ("G3", {"ac1": 0.10}, "PASS"), ("G3", {"ac1": -0.10}, "PASS"), ("G3", {"ac1": 0.20}, "WARN"),
    ("G3", {"ac1": -0.20}, "WARN"), ("G3", {"ac1": 0.2001}, "FAIL"),
    ("G4", {"vr5": 0.80}, "PASS"), ("G4", {"vr5": 1.25}, "PASS"), ("G4", {"vr5": 0.60}, "WARN"),
    ("G4", {"vr5": 1.60}, "WARN"), ("G4", {"vr5": 1.61}, "FAIL"), ("G4", {"vr5": 0.59}, "FAIL"),
    ("G5", {"cs": 0.10, "ps": 0.031}, "PASS"), ("G5", {"cs": 0.10, "ps": 0.03}, "PASS"),
    ("G5", {"cs": 0.10, "ps": 0.029}, "WARN"), ("G5", {"cs": 0.05, "ps": 0.5}, "WARN"),
    ("G5", {"cs": 0.0499, "ps": 0.5}, "FAIL"),
    ("G6", {"kurt": 3.0}, "PASS"), ("G6", {"kurt": 1.0}, "WARN"), ("G6", {"kurt": 0.99}, "FAIL"),
    ("G7", {"vv_corr": 0.30}, "PASS"), ("G7", {"vv_corr": 0.10}, "WARN"), ("G7", {"vv_corr": 0.099}, "FAIL"),
    ("G8", {"spread_med_ticks": 1.0, "spread_p95_ticks": 5.0}, "PASS"),
    ("G8", {"spread_med_ticks": 1.5, "spread_p95_ticks": 5.0}, "WARN"),
    ("G8", {"spread_med_ticks": 1.0, "spread_p95_ticks": 10.0}, "WARN"),
    ("G8", {"spread_med_ticks": 1.0, "spread_p95_ticks": 10.5}, "FAIL"),
    ("G9", {"gap_std": 1.0}, "PASS"), ("G9", {"gap_std": 3.0}, "PASS"), ("G9", {"gap_std": 0.5}, "WARN"),
    ("G9", {"gap_std": 5.0}, "WARN"), ("G9", {"gap_std": 0.49}, "FAIL"), ("G9", {"gap_std": 5.01}, "FAIL"),
    # G10 grades the corrected half-life since spec v1.4 §3.1 (band unchanged)
    ("G10", {"gap_half_life_corr_min": 30.0}, "PASS"), ("G10", {"gap_half_life_corr_min": 90.0}, "PASS"),
    ("G10", {"gap_half_life_corr_min": 10.0}, "WARN"), ("G10", {"gap_half_life_corr_min": 180.0}, "WARN"),
    ("G10", {"gap_half_life_corr_min": 9.9}, "FAIL"), ("G10", {"gap_half_life_corr_min": None}, "FAIL"),
    ("G11", {"regime_contrast": 5.0}, "PASS"), ("G11", {"regime_contrast": 3.0}, "WARN"),
    ("G11", {"regime_contrast": 2.99}, "FAIL"),
    ("G12", {"impact_beta": 0.40}, "PASS"), ("G12", {"impact_beta": 0.70}, "PASS"),
    ("G12", {"impact_beta": 0.25}, "WARN"), ("G12", {"impact_beta": 0.90}, "WARN"),
    ("G12", {"impact_beta": 0.91}, "FAIL"),
    ("G13", {"impact_recovery": 0.1}, "PASS"), ("G13", {"impact_recovery": 0.8}, "PASS"),
    ("G13", {"impact_recovery": 1.0}, "WARN"), ("G13", {"impact_recovery": 0.0}, "WARN"),
    ("G13", {"impact_recovery": -0.01}, "FAIL"), ("G13", {"impact_recovery": 1.01}, "FAIL"),
]


@pytest.mark.parametrize("gid,values,expected", BOUNDARIES)
def test_r11_boundaries_take_the_better_grade(gid, values, expected):
    assert R.grade_value(R.BANDS_BY_ID[gid], values) == expected


def test_r11_every_band_has_source_and_grader():
    assert [b["id"] for b in R.BANDS] == [f"G{i}" for i in range(1, 14)]
    for b in R.BANDS:
        assert b["source"] == "owner D-R2-1, 2026-10-11, large-cap reference"
        assert b["label"] and b["note"] and b["text"]
    assert R.RUN_GRADES == ["G1"] + [f"G{i}" for i in range(3, 12)]


def test_r11_aggregation_and_incomplete():
    rng = np.random.RandomState(11)
    x = list(rng.normal(size=20))
    a = R.aggregate(x)
    assert a["median"] == np.percentile(x, 50) and a["p10"] == np.percentile(x, 10)
    assert a["p90"] == np.percentile(x, 90) and a["status"] == "OK" and a["n_seeds"] == 20
    b = R.aggregate(x[:14] + [None] * 6)
    assert b["status"] == "INCOMPLETE" and b["n_seeds"] == 14
    per_seed = [{"sigma_1m_bps": v} for v in [7.0] * 14] + [{"sigma_1m_bps": None}] * 6
    sc = R.scorecard(per_seed)
    assert sc["G1"]["grade"] == "INCOMPLETE"
    sc = R.scorecard([{"sigma_1m_bps": v} for v in [7.0] * 15])
    assert sc["G1"]["grade"] == "PASS" and sc["G1"]["pass_share"] == 1.0


# T-R12 ────────────────────────────────────────────────────────────────────
def test_r12_zero_sum():
    # A buys 10 from B at $1000.05; B buys 3 from C at $999.95; close $1000.005 (half cent)
    recs = [
        {"cash0": 1_000_000, "sh0": 0, "cash1": 1_000_000 - 10 * 100_005, "sh1": 10},
        {"cash0": 0, "sh0": 50, "cash1": 10 * 100_005 - 3 * 99_995, "sh1": 50 - 10 + 3},
        {"cash0": 0, "sh0": 5, "cash1": 3 * 99_995, "sh1": 2},
    ]
    out = R.zero_sum(recs, 100_000.5)
    assert out["ok"] and out["zero_sum_cents"] == 0.0
    recs[0]["cash1"] += 1  # one cent created from nothing
    out = R.zero_sum(recs, 100_000.5)
    assert not out["ok"] and out["zero_sum_cents"] == 1.0


# ── spec v1.4 Part 3 (T-N8 .. T-N11) ─────────────────────────────────────


def _tn8_paths():
    """Fresh AR(1) gaps for T-N8/T-N9: default_rng(seed=1), 40 paths per H,
    stationary start, 1 s grid of one 6.5 h day."""
    from scipy.signal import lfilter

    rng = np.random.default_rng(seed=1)
    out = {}
    for H in (1.5, 10, 45, 90):
        phi = math.exp(-math.log(2) / (H * 60.0))
        res = []
        for _ in range(40):
            e = rng.standard_normal(23_401)
            e[0] /= math.sqrt(1.0 - phi * phi)
            res.append(R.gap_half_life_corrected(lfilter([1.0], [1.0, -phi], e)))
        out[H] = res
    return out


_TN8 = None


def _tn8():
    global _TN8
    if _TN8 is None:
        _TN8 = _tn8_paths()
    return _TN8


@pytest.mark.parametrize("H", [1.5, 10, 45, 90])
def test_n8_corrected_half_life(H):
    res = _tn8()[H]
    hc = [math.inf if r["above_table"] else r["h_corrected"] for r in res]
    med = float(np.median(hc))
    print(f"H {H}: median h_corrected {med:.2f}, median h_read {np.median([r['h_read'] for r in res]):.2f}")
    assert abs(med / H - 1.0) <= 0.25
    if H in (1.5, 10):
        assert abs(float(np.median([r["h_read"] for r in res])) / H - 1.0) <= 0.25
    assert all(r["gap_mean"] is not None and len(r["rho0"]) == len(R.LAB_GAP_LAGS) for r in res)


def test_n9_table_reproducible_and_monotone():
    stored = R.halflife_table()
    rebuilt = json.loads(json.dumps(R.build_halflife_table()))
    assert rebuilt == stored
    med = [r["median"] for r in stored["rows"]]
    assert all(b > a for a, b in zip(med, med[1:]))
    assert [r["H"] for r in stored["rows"]] == list(R.HL_TABLE_H_MIN)


_TN9_COVERAGE = (
    "spec v1.4 T-N9 asks h_range to contain H for >= 80% of the T-N8 paths; measured "
    "2026-10-12: 59% (H 1.5: 0/40, 10: 29/40, 45: 36/40, 90: 29/40). H = 1.5 is not a "
    "table point and its readings (1.4-1.7 min) fall between the p10-p90 intervals of "
    "H = 1 (0.87-1.42) and H = 2 (1.66-2.71); at table points coverage is about 80% by "
    "construction (p10..p90). Reported to the owner (DECISIONS.md, N1); h_range is "
    "implemented as §3.1 defines it"
)


@pytest.mark.xfail(strict=True, reason=_TN9_COVERAGE)
def test_n9_h_range_coverage():
    res = _tn8()
    hits = [bool(r["h_range"]) and r["h_range"][0] <= H <= r["h_range"][1] for H, rs in res.items() for r in rs]
    print(f"h_range coverage {np.mean(hits):.3f}")
    assert np.mean(hits) >= 0.80


def test_n9_h_range_is_bracketing():
    """What h_range guarantees by construction: an interval of table H values
    whose p10..p90 reading intervals contain the reading."""
    rows = R.halflife_table()["rows"]
    for H, rs in _tn8().items():
        for r in rs:
            if r["h_range"]:
                lo, hi = r["h_range"]
                assert lo <= hi and lo in R.HL_TABLE_H_MIN and hi in R.HL_TABLE_H_MIN
                for x in rows:
                    if x["H"] in (lo, hi):
                        assert x["p10"] <= r["h_read"] <= x["p90"]


def test_n9_correction_edges():
    rows = R.halflife_table()["rows"]
    low = rows[0]["median"] * 0.5
    assert R.correct_half_life(low)["h_corrected"] == low  # below the table: h_read
    hi = R.correct_half_life(rows[-1]["median"] * 1.5)
    assert hi["h_corrected"] is None and hi["above_table"] and hi["text"] == ">240 min"
    for r in rows:  # the table's own medians map back to their H
        assert abs(R.correct_half_life(r["median"])["h_corrected"] - r["H"]) < 1e-6 * r["H"]
    assert R.correct_half_life(None)["h_corrected"] is None


def test_n10_jump_window_metrics():
    t0, n, J = 5400, 23_401, 20.0
    spr = np.full(n, 1.0)
    spr[t0 + 100:t0 + 100 + 180] = np.nan  # 180 s with an empty side in the 1801-point window
    spr[t0 + 1000:t0 + 1100] = 30.0  # 100 two-sided seconds at 30 ticks
    mid = np.full(n, 1000.0)
    mid[t0 + 600:] = 1010.0  # one step of 10 $ (> 25% of J) at t0 + 10 min
    mid[t0 + 1200:] = 1012.0  # one step of 2 $ (< 25% of J)
    out = R.jump_window_metrics({"spr_1s": spr, "mid_1s": mid}, t0, J)
    assert out["one_sided_share_jump"] == pytest.approx(180 / 1801)
    two = np.concatenate([np.full(1801 - 180 - 100, 1.0), np.full(100, 30.0)])
    assert out["spread_p95_jump_ticks"] == pytest.approx(float(np.percentile(two, 95)))
    assert out["spread_max_jump_ticks"] == 30.0
    assert out["price_path_steps"] == 1
    out = R.jump_window_metrics({"spr_1s": spr, "mid_1s": mid}, t0, -J)  # |J| for S2n
    assert out["price_path_steps"] == 1


def _r3_ok():
    C = {"ac1": 0.10, "vr5": 0.80, "vol_ratio_price_value": 0.90, "vv_corr": 0.01,
         "fund_pnl_total": 1.0, "fund_pnl_median": 0.5, "spread_med_ticks": 2.0,
         "spread_p95_ticks": 10.0, "shares_executed": 295_500, "active_halfhours_share": 1.0,
         "zero_sum_all_zero": 1.0, "wall_time_s": 90.0}
    J = {"volume_uplift": 1.01, "one_sided_share_jump": 0.01, "spread_p95_jump_ticks": 10.0}
    return {"C": C, "S2": dict(J), "S2n": dict(J)}


@pytest.mark.parametrize("scope,key,value,item,expected", [
    (None, None, None, None, "ALL"),  # every boundary exactly as written passes
    ("C", "ac1", -0.10, "T1", "PASS"), ("C", "ac1", 0.1001, "T1", "FAIL"), ("C", "ac1", -0.11, "T1", "FAIL"),
    ("C", "vr5", 1.25, "T2", "PASS"), ("C", "vr5", 0.7999, "T2", "FAIL"), ("C", "vr5", 1.2501, "T2", "FAIL"),
    ("C", "vol_ratio_price_value", 0.8999, "T3", "FAIL"),
    ("C", "vv_corr", 0.0, "T4", "FAIL"),  # "> 0": exactly 0 fails
    ("S2", "volume_uplift", 1.0, "T5", "FAIL"), ("S2n", "volume_uplift", 1.0, "T5", "FAIL"),
    ("S2n", "one_sided_share_jump", 0.0101, "T6", "FAIL"), ("S2", "spread_p95_jump_ticks", 10.01, "T6", "FAIL"),
    ("C", "fund_pnl_total", 0.0, "T7", "FAIL"), ("C", "fund_pnl_median", 0.0, "T7", "FAIL"),
    ("C", "spread_med_ticks", 2.01, "L1", "FAIL"), ("C", "spread_p95_ticks", 10.01, "L1", "FAIL"),
    ("C", "shares_executed", 295_499, "L2", "FAIL"),
    ("C", "zero_sum_all_zero", 0.0, "L4", "FAIL"), ("C", "wall_time_s", 90.01, "L5", "FAIL"),
    ("S2n", "volume_uplift", None, "T5", "MISSING"),
])
def test_n11_r3_scorecard_boundaries(scope, key, value, item, expected):
    s = _r3_ok()
    if scope is None:
        sc = R.r3_scorecard(s)
        assert sc["all_pass"] and sc["n_targets_passed"] == 7
        assert all(x["status"] == "PASS" for x in sc["limits"].values())
        return
    s[scope][key] = value
    sc = R.r3_scorecard(s)
    items = {**sc["targets"], **sc["limits"]}
    assert items[item]["status"] == expected
    assert all(x["status"] == "PASS" for k, x in items.items() if k != item)


def test_n11_r3_definitions_single_source():
    assert [t["id"] for t in R.R3_TARGETS] == [f"T{i}" for i in range(1, 8)]
    assert [x["id"] for x in R.R3_LIMITS] == [f"L{i}" for i in range(1, 6)]
    sc = R.r3_scorecard({"C": {"ac1": 0.3, "vr5": 1.9, "vol_ratio_price_value": 0.5, "vv_corr": -0.3}})
    t = sc["targets"]
    assert t["T1"]["norm_miss"] == pytest.approx(2.0) and t["T2"]["norm_miss"] == pytest.approx(0.65 / 0.45)
    assert t["T3"]["norm_miss"] == pytest.approx(0.4 / 0.9) and t["T4"]["norm_miss"] == pytest.approx(1.0)
    assert t["T5"]["status"] == "MISSING"

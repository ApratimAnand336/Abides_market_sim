"""Measurement additions of FinVerse spec v1.5 A2 (synthetic data, answers known by
construction).

T-R4-1  regime spread RS = p90/p10 of daily realised vols, on synthetic days whose
        realised vols are known exactly.
T-R4-2  information-news response (f_10, volume uplift) on a hand-built series.
Also: day_rv_pct, class volumes and volume shares (both sides counted), market-maker
inventory statistics.
"""

import math

import numpy as np
import pytest

from api import realism as R


def _day_with_rv(sigma_pct: float, n: int = 389, seed: int = 0) -> np.ndarray:
    """1-min returns of equal size and random sign: sum r^2 = (sigma/100)^2 exactly."""
    signs = np.where(np.random.RandomState(seed).rand(n) < 0.5, -1.0, 1.0)
    return signs * (sigma_pct / 100.0) / math.sqrt(n)


def test_day_rv_pct_known():
    for s in (0.5, 1.0, 2.37):
        assert R.day_rv_pct(_day_with_rv(s)) == pytest.approx(s, rel=1e-12)
    assert R.day_rv_pct(np.array([])) is None


def test_r4_1_regime_spread_known_daily_vols():
    sigmas = [0.5 + 0.1 * i for i in range(20)]  # 0.5 ... 2.4 % a day
    rvs = [R.day_rv_pct(_day_with_rv(s, seed=i)) for i, s in enumerate(reversed(sigmas))]
    # numpy linear percentiles of 0.5 + 0.1 i: p10 at index 1.9 -> 0.69, p90 at 17.1 -> 2.21
    assert R.regime_spread(rvs) == pytest.approx(2.21 / 0.69, rel=1e-12)
    assert R.regime_spread([1.0, 1.0, 1.0]) == pytest.approx(1.0)
    assert R.regime_spread([1.0]) is None
    assert R.regime_spread([None, 1.0, float("nan")]) is None
    assert R.regime_spread([0.0, 0.0, 2.0]) is None  # p10 = 0


def test_r4_2_info_news_response_hand_built():
    dur = 3600
    mid = np.full(dur + 1, 1000.0)
    t0 = 1000
    mid[t0:t0 + 301] = np.linspace(1000.0, 1010.0, 301)  # moves $10 in 5 min, then stays
    mid[t0 + 301:] = 1010.0
    # volume: 10 x 100 shares in (t0 - 600, t0], 25 x 100 in (t0, t0 + 600]
    et = np.concatenate([np.linspace(t0 - 590, t0, 10), np.linspace(t0 + 1, t0 + 600, 25)])
    eq = np.full(len(et), 100.0)
    events = [(float(t0), 20.0),        # J = +$20: f_10 = 10 / 20 = 0.5, uplift 2.5
              (3300.0, 5.0),            # no full 10-min window after: skipped
              (2000.0, 0.0)]            # J = 0: skipped
    out = R.info_news_response(mid, et, eq, events)
    assert out["n"] == 1 and out["n_events"] == 3
    assert out["f10_median"] == pytest.approx(0.5, abs=1e-12)
    assert out["uplift_median"] == pytest.approx(2.5, abs=1e-12)
    # a negative jump priced in fully: f_10 = 1
    mid2 = np.full(dur + 1, 1000.0)
    mid2[t0 + 1:] = 990.0
    out2 = R.info_news_response(mid2, et, eq, [(float(t0), -10.0)])
    assert out2["f10_median"] == pytest.approx(1.0, abs=1e-12)
    # no volume before: uplift undefined
    out3 = R.info_news_response(mid, et[10:], eq[10:], [(float(t0), 20.0)])
    assert out3["uplift_median"] is None and out3["f10_median"] == pytest.approx(0.5)


def test_class_volumes_and_shares():
    cls_of = {1: "RetailTraderAgent", 2: "LiquidityProviderAgent", 3: "FundamentalistAgent"}
    buyer = np.array([1, 2, 3, 1])
    seller = np.array([2, 3, 1, 1])
    q = np.array([10.0, 20.0, 30.0, 40.0])  # 100 shares executed
    cv = R.class_volumes(buyer, seller, q, cls_of)
    assert cv == {"RetailTraderAgent": 10 + 30 + 80, "LiquidityProviderAgent": 30, "FundamentalistAgent": 50}
    assert sum(cv.values()) == 2 * q.sum()
    assert R.volume_share(cv, R.RETAIL_CLASSES, 100) == pytest.approx(60.0)
    assert R.volume_share(cv, R.MM_CLASSES, 100) == pytest.approx(15.0)
    assert R.volume_share(cv, R.MM_CLASSES, 0) is None


def test_inventory_stats():
    buyer = np.array([5, 1, 5, 2, 1])
    seller = np.array([1, 5, 2, 5, 5])
    q = np.array([10.0, 4.0, 7.0, 30.0, 1.0])
    # agent 5: +10, -4, +7, -30, -1 -> path 10, 6, 13, -17, -18
    assert R.inventory_stats(buyer, seller, q, 5) == {"max_abs": 18, "end": -18}
    assert R.inventory_stats(buyer, seller, q, 9) == {"max_abs": 0, "end": 0}
    assert R.inventory_stats(np.array([]), np.array([]), np.array([]), 5) == {"max_abs": 0, "end": 0}


def test_run_metrics_v15_keys_are_payload_scalars():
    """The payload schema accepts scalar (or list-of-number) metrics only: the A2 keys
    are scalars; the per-agent / per-event detail goes to run_diagnostics."""
    rs = np.random.RandomState(1)
    dur = 23400
    mid = 1000.0 * np.exp(np.cumsum(rs.normal(0, 2e-5, dur + 1)))
    val = mid + rs.normal(0, 0.05, dur + 1)
    s = {
        "duration": dur, "mid_1s": mid, "val_1s": val,
        "close_1m": R.bar_closes(mid, dur), "vol_1m": rs.randint(100, 1000, 390).astype(float),
        "spr_1s": np.full(dur + 1, 0.02), "shares_executed": 200_000,
        "exec_t": np.sort(rs.uniform(0, dur, 5000)), "exec_q": np.full(5000, 40.0),
        "class_volume": {"RetailTraderAgent": 80_000.0, "LiquidityProviderAgent": 120_000.0},
        "mm_inventory": [{"id": 3, "cls": "LiquidityProviderAgent", "max_abs": 900, "end": -40},
                         {"id": 4, "cls": "LiquidityProviderAgent", "max_abs": 1200, "end": 15}],
        "info_news": [(3600.0, 2.0), (12000.0, -1.5)],
        "day_info": {"day_type": "normal", "stress_episodes": [], "news": []},
    }
    m = R.run_metrics(s)
    assert m["retail_share"] == pytest.approx(20.0) and m["mm_share"] == pytest.approx(30.0)
    assert m["mm_inv_max_abs"] == 1200 and m["mm_inv_end_max_abs"] == 40
    assert m["info_news_n"] == 2 and m["day_rv_pct"] > 0
    for k, v in m.items():
        ok = v is None or isinstance(v, (int, float, bool)) or (
            isinstance(v, list) and all(isinstance(x, (int, float)) for x in v))
        assert ok, k
    d = R.run_diagnostics(s)
    assert len(d["mm_inventory"]) == 2 and d["info_news"]["n"] == 2 and d["day_info"]["day_type"] == "normal"


def test_a6_2_impact_set_beta_on_four_sizes():
    """Spec v1.5 A6.2: IMP-0.1 is back in the impact set and beta is fitted on four
    sizes. Synthetic I = 2 * q^0.5 on every seed gives beta = 0.5 exactly."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import lab_v15
    import realism_lab as RL
    from api import lab

    assert lab_v15.IMPACT_BETA_SIZES == ("IMP-0.1", "IMP-0.5", "IMP-1", "IMP-5")
    assert set(lab_v15.IMPACT_BETA_SIZES) < set(lab_v15.IMPACT_SET)
    assert lab_v15.impact_configs("N")[1] == "N-IMP-0.1"
    qty = {k: lab.CONFIGS[k]["extra"]["probe"]["quantity"] for k in lab_v15.IMPACT_BETA_SIZES}
    assert qty["IMP-0.1"] == 600 and len(set(qty.values())) == 4
    seeds = list(range(10))
    scen = {}
    for k in lab_v15.IMPACT_SET:
        q = 0.0 if k == "IMP-0" else qty.get(k, qty["IMP-1"]) / 500_000
        rows = [{"seed": s, "q": q, "I_end": 2.0 * q ** 0.5 + 0.01 * (s - 4.5) * (k == "IMP-0"),
                 "I_peak": 3.0 * q ** 0.5, "I_perm": q ** 0.5, "recovery": 0.4} for s in seeds]
        stats = {m: {"median": float(np.median([r[m] for r in rows]))} for m in ("q", "I_end", "I_perm")}
        scen[k] = {"per_seed": rows, "stats": stats}
    out = RL.impact_summary(scen, 5)
    assert out["beta_I_end"]["n_seeds"] == 10
    assert out["beta_I_end"]["beta"] == pytest.approx(0.5, abs=1e-9)
    assert out["beta_I_peak"]["beta"] == pytest.approx(0.5, abs=1e-9)


# ── A7: design sweep ids, R4a scorecard and the mechanical selection ──────────
def _lab_v15():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import lab_v15

    return lab_v15


def _passing_summaries():
    C = {"sigma_1m_bps": 7.0, "ac1": -0.02, "vr5": 1.0, "vol_ratio_price_value": 0.95, "vv_corr": 0.5,
         "cs": 0.2, "ps": 0.05, "kurt": 4.0, "fund_pnl_total": 100.0, "fund_pnl_median": 5.0,
         "mm_pnl_group_median": 0.0, "u_ratio": 1.5, "spread_med_bps": 1.0, "spread_p95_bps": 5.0,
         "shares_executed": 400_000, "active_halfhours_share": 1.0, "zero_sum_all_zero": 1.0,
         "flags_all_ok": 1.0, "wall_time_s": 40.0, "max_abs_gap": 3.0, "retail_share": 10.0}
    S2 = {"volume_uplift": 2.0, "spread_jump_ratio": 2.0, "one_sided_share_jump": 0.0}
    return C, S2


def test_a7_r4a_scorecard_thresholds():
    C, S2 = _passing_summaries()
    sc = R.r4a_scorecard({"C": C, "S2": S2}, screening=True)
    assert sc["all_pass"]
    assert sc["targets"]["A-T3"]["status"] == sc["targets"]["A-T11"]["status"] == "NOT_SCREENED"
    assert sc["n_targets_passed"] == 10 == len(R.R4A_SCREEN_TARGETS)
    assert all(c["scope"] == "S2" for c in sc["targets"]["A-T9"]["checks"])
    # boundaries exactly as A8 writes them
    for key, val, tid in (("sigma_1m_bps", 10.0, "A-T1"), ("vv_corr", 0.30, "A-T6"), ("kurt", 3.0, "A-T8"),
                          ("u_ratio", 1.3, "A-T12"), ("mm_pnl_group_median", 0.0, "A-T10")):
        assert R.r4a_scorecard({"C": {**C, key: val}, "S2": S2}, screening=True)["targets"][tid]["status"] == "PASS"
    for key, val, tid in (("sigma_1m_bps", 4.99, "A-T1"), ("ps", 0.03, "A-T7"), ("fund_pnl_median", 0.0, "A-T10"),
                          ("vr5", 1.2501, "A-T4"), ("ac1", -0.11, "A-T2")):
        assert R.r4a_scorecard({"C": {**C, key: val}, "S2": S2}, screening=True)["targets"][tid]["status"] == "FAIL"
    for key, val, lid in (("retail_share", 4.9, "L7"), ("retail_share", 40.1, "L7"), ("flags_all_ok", 0.0, "L4"),
                          ("max_abs_gap", 10.01, "L6")):
        assert R.r4a_scorecard({"C": {**C, key: val}, "S2": S2}, screening=True)["limits"][lid]["status"] == "FAIL"
    # A7 tie-break scales: sigma 4 bps is 1 bps short of 5 -> 1/5
    t1 = R.r4a_scorecard({"C": {**C, "sigma_1m_bps": 4.0}, "S2": S2}, screening=True)["targets"]["A-T1"]
    assert t1["norm_miss"] == pytest.approx(0.2)
    # outside screening the day-mix and S2n checks are required (MISSING without them)
    full = R.r4a_scorecard({"C": C, "S2": S2})
    assert full["targets"]["A-T3"]["status"] == full["targets"]["A-T9"]["status"] == "MISSING"


def test_a7_sweep_designs_and_refinement():
    from api import lab

    assert len(lab.SWEEP_DESIGNS) == 16 == len(set(lab.SWEEP_DESIGNS))
    assert len(lab.CAMPAIGNS["a-sweep"]) == 32
    for rid in lab.SWEEP_DESIGNS:
        assert lab.sweep_id(lab.parse_sweep(rid)) == rid
    assert lab.parse_sweep("R-420M15003") == {"n_lp": 4, "W": "20M", "N_r": 1500, "k": 3}
    assert lab.sweep_refinement("R-25M5001") == ["R-35M5001", "R-250M5001", "R-25M30001", "R-25M5005"]
    ex = lab.CONFIGS["R-420M15003-S2"]["extra"]
    assert ex["informed_budget_v2"] is True and ex["mm_kind"] == "lp" and ex["num_lp"] == 4
    assert ex["lp_wealth"] == 2_000_000_000 and ex["num_retail"] == 1500 and ex["retail_kappa_v"] == 3.0
    assert ex["num_noise_agents"] == 0 and ex["value_process"] == "living_v1" and ex["day_type"] == "normal"
    assert ex["auto_news"] is True and ex["abides_budget"] == {"L": 2.0}
    assert lab.CONFIGS["R-420M15003-S2"]["baseline"] == "R-420M15003-C"
    assert lab.CONFIGS["R-420M15003-C"]["params"]["num_value"] == 0
    for r in lab.sweep_refinement("R-420M15003"):  # refinement configs exist up front
        assert r + "-C" in lab.CONFIGS and r + "-S2" in lab.CONFIGS


def test_a7_selection_mechanical():
    V = _lab_v15()
    C, S2 = _passing_summaries()

    def mk(rid, c=None, s2=None):
        cc, ss = {**C, **(c or {})}, {**S2, **(s2 or {})}
        return {"design": rid, "dials": {}, "C": cc, "S2": ss, "r4a": R.r4a_scorecard({"C": cc, "S2": ss}, screening=True)}

    sums = [mk("R-25M5001", {"retail_share": 3.0}),         # rejected by L7
            mk("R-25M5003", {"kurt": 2.0}),                 # 9 targets
            mk("R-45M5001", {"sigma_1m_bps": 4.0}),          # 9 targets, A-T1 miss 0.2
            mk("R-45M5003", {"vr5": 1.30}),                  # 9 targets, A-T4 miss 0.05/0.45
            mk("R-420M5001", {"vr5": 1.30, "wall_time_s": 30.0})]  # same miss, faster
    win, P = V.select_sweep(sums, "t")
    assert "R-25M5001: REJECTED" in "\n".join(P)
    # all kept designs pass 9 targets; R-25M5003 misses only A-T8, which is not in the
    # tie-break, so its miss sum over A-T1/2/4/5 is 0 and it wins
    assert win == "R-25M5003"
    win2, _ = V.select_sweep(sums[2:], "t")
    assert win2 == "R-420M5001"  # VR miss 0.111 < sigma miss 0.2; equal misses -> lower wall time
    win3, P3 = V.select_sweep([sums[0]], "t")
    assert win3 is None and "names no winner" in P3[-1]

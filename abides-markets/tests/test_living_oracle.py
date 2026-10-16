"""The living value process "living_v1" and automatic information news (FinVerse spec
v1.5 A3).

T-O5  value statistics per day type and for the default mix reproduce A3.3 (+/-10%,
      200 seeds each); the value's own per-day 30-min regime contrast is reported.
T-O6  day type override, and the auto distribution over 2000 seeds (30/50/20 +/- 3 pp).
T-O7  the path (and its day info) is identical across agent mixes, news on/off for the
      agents and session length (I2 extended).
T-O8  headline bucket/sign consistency: the committed template file, and every
      automatic headline's bucket matches its jump's sign and size.
T-O9  synthetic_ou is unchanged (seed-42 path hash recorded from 20465e2-era code at
      f7245d2, before A3); I8 covers the default market.
Also: the stress chain equals the per-step loop; U has mean 1; the draw order of A3.2
is reproduced by an independent re-implementation; and (rule 2.4) in a 1-hour market
every news jump is broadcast at its time and reaches the informed fundamentalists and
the momentum agents, whose research/beliefs see the living value.
"""

import hashlib
import math
import os
from math import log

import numpy as np
import pytest

from abides_markets.configs.news_templates import BUCKETS, load_news_templates
from abides_markets.configs.param_ranges import LIVING_V1
from abides_markets.configs.rmsc04_ekf import build_config
from abides_markets.oracles.pregenerated_oracle import (
    jump_bucket,
    living_day_type,
    living_stress_chain,
    living_u_shape,
    living_v1_day,
)

R_BAR = 100_000
KAPPA = 1.67e-16
OPEN = 1_612_517_400_000_000_000  # 2021-02-05 09:30 in ns
TIMES = OPEN + 1_000_000_000 * np.arange(23_401, dtype=np.int64)

# spec A3.3 (Claude's independent numpy check, 2026-10-16)
A33 = {
    "calm": {"sd1m_bps": 3.8, "daily_pct": 0.78},
    "normal": {"sd1m_bps": 6.3, "daily_pct": 1.49},
    "volatile": {"sd1m_bps": 11.3, "daily_pct": 2.42},
    "auto": {"sd1m_bps": 6.2, "daily_pct": 1.53},
}


def _day(seed, day_type="auto", templates=None, events=None):
    params = {"r_bar": R_BAR, "kappa": KAPPA, "day_type": day_type, "living": LIVING_V1}
    if templates is not None:
        params["news_templates"] = templates
    if events is not None:
        params["events"] = events
    return living_v1_day(params, TIMES, np.random.RandomState(seed))


def _stats(day_type, n=200):
    sd1m, moves, contrast = [], [], []
    for seed in range(n):
        v = _day(seed, day_type)["values"]
        r1 = np.diff(np.log(v[::60]))
        sd1m.append(1e4 * np.std(r1, ddof=1))
        moves.append((v[-1] - v[0]) / v[0])
        w = [np.std(r1[i:i + 30], ddof=1) for i in range(0, len(r1), 30) if len(r1[i:i + 30]) >= 2]
        contrast.append(max(w) / min(w))
    return float(np.median(sd1m)), 100.0 * float(np.std(moves)), np.array(contrast)


# ── model pieces ──────────────────────────────────────────────────────────


def test_stress_chain_equals_loop():
    rs = np.random.RandomState(0)
    for p_in, p_out in ((1e-3, 5e-3), (0.05, 0.2), (3e-5, 1 / 2700), (0.0, 0.1), (1.0, 1.0)):
        u = rs.random_sample(20_000)
        S = np.empty(len(u))
        s = 1.0
        for k in range(len(u)):
            S[k] = s
            if s == 1.0 and u[k] < p_in:
                s = 2.5
            elif s == 2.5 and u[k] < p_out:
                s = 1.0
        assert np.array_equal(living_stress_chain(u, p_in, p_out, 2.5), S)


def test_u_shape_mean_one_and_ends():
    U = living_u_shape(TIMES, LIVING_V1)
    assert U.mean() == pytest.approx(1.0, abs=1e-12)
    num = lambda t: 1 + 0.6 * math.exp(-t / 0.5) + 0.4 * math.exp(-(6.5 - t) / 0.5)  # noqa: E731
    c_u = np.mean([num(k / 3600) for k in range(23_401)])
    assert U[0] == pytest.approx(num(0) / c_u, rel=1e-12)
    assert U[-1] == pytest.approx(num(6.5) / c_u, rel=1e-12)
    assert U[0] > U[-1] > U[11_700]  # busier at the open than at the close than midday


def test_draw_order_reimplemented():
    """A3.2: day type, N stress uniforms, N-1 normals, then news count, times, sizes,
    signs and template indices, all from the symbol's RandomState."""
    tpl = load_news_templates()["buckets"]
    for seed in (3, 20, 77):
        out = _day(seed, "auto", templates=tpl)
        rng = np.random.RandomState(seed)
        u_day = rng.random_sample()
        dtype = "calm" if u_day < 0.30 else ("normal" if u_day < 0.80 else "volatile")
        rng.random_sample(len(TIMES))
        rng.normal(size=len(TIMES) - 1)
        n = rng.poisson(LIVING_V1["news_per_day"][dtype])
        t = np.sort(rng.uniform(OPEN + 300e9, OPEN + 23_100e9, size=n))
        m = rng.lognormal(log(0.002), 0.6, size=n)
        sg = np.where(rng.random_sample(n) < 0.5, 1.0, -1.0)
        J = R_BAR * np.minimum(m, 0.02) * sg
        heads = []
        for j in J:
            items = tpl[jump_bucket(j, R_BAR)]
            heads.append(items[rng.randint(len(items))]["headline"])
        info = out["info"]
        assert info["day_type"] == dtype
        assert [x[1] for x in info["news"]] == pytest.approx(list(J))
        assert [x[2] for x in info["news"]] == heads
        assert [x[0] for x in info["news"]] == [int(TIMES[np.searchsorted(TIMES, int(tt))]) for tt in t]


# ── T-O5 … T-O9 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("day_type", ["calm", "normal", "volatile", "auto"])
def test_o5_value_statistics_1min(day_type):
    sd1m, daily, contrast = _stats(day_type)
    exp = A33[day_type]
    print(f"T-O5 {day_type}: 1-min sd median {sd1m:.2f} bps (A3.3 {exp['sd1m_bps']}), daily sd "
          f"{daily:.2f}% (A3.3 {exp['daily_pct']}); value regime contrast median "
          f"{np.median(contrast):.2f}, p90 {np.percentile(contrast, 90):.2f} (reported)")
    assert sd1m == pytest.approx(exp["sd1m_bps"], rel=0.10)


_O5_NORMAL_REASON = (
    "spec A3.3 daily sd 1.49% for normal days is ~11-14% above the model as written: "
    "this test measures 1.28% (seeds 0-199) and 1,500 days give 1.32% (DECISIONS A0/A3); "
    "the 1-min sd matches (6.24 vs 6.3 bps). Implementation follows A3.1 exactly.")


@pytest.mark.parametrize("day_type", [
    "calm", pytest.param("normal", marks=pytest.mark.xfail(strict=True, reason=_O5_NORMAL_REASON)),
    "volatile", "auto"])
def test_o5_value_statistics_daily(day_type):
    _, daily, _ = _stats(day_type)
    assert daily == pytest.approx(A33[day_type]["daily_pct"], rel=0.10)


def test_o6_day_type_override_and_auto_mix():
    for seed in range(40):
        auto = _day(seed, "auto")
        forced = _day(seed, auto["info"]["day_type"])
        assert np.array_equal(auto["values"], forced["values"])  # requesting the drawn type changes nothing
    for dt in ("calm", "normal", "volatile"):
        assert _day(5, dt)["info"]["day_type"] == dt
    with pytest.raises(ValueError):
        _day(5, "stormy")
    types = [living_day_type(np.random.RandomState(s).random_sample(), "auto", LIVING_V1) for s in range(2000)]
    share = {t: types.count(t) / 2000 for t in ("calm", "normal", "volatile")}
    print(f"T-O6 auto shares over 2000 seeds: {share}")
    for t, p in (("calm", 0.30), ("normal", 0.50), ("volatile", 0.20)):
        assert abs(share[t] - p) <= 0.03
    # the oracle's first draw is that uniform: day_info agrees with living_day_type
    for s in range(20):
        assert _day(s)["info"]["day_type"] == types[s]


def _oracle(**kw):
    base = dict(seed=42, end_time="16:00:00", stdout_log_level="WARNING", value_process="living_v1", day_type="auto")
    base.update(kw)
    return build_config(**base)["custom_properties"]["oracle"]


def test_o7_path_identical_across_agents_news_session():
    ref = _oracle()
    t0, v0 = ref.path("ABM")
    variants = [
        dict(num_noise_agents=10, num_value_agents=0),
        dict(num_ekf_agents=40, num_mom_ekf_agents=2),
        dict(news_events=[("01:00:00", "ABM", 0.9, "hype")]),
        dict(auto_news=False),
        dict(end_time="10:30:00"),
        dict(fund_mode="informed", informed_design={"T_r_range_s": [60, 300], "sigma_r_range_c": [10, 50],
                                                    "wealth_c": 200_000_000}, num_ekf_agents=30),
    ]
    for kw in variants:
        o = _oracle(**kw)
        t, v = o.path("ABM")
        assert np.array_equal(t, t0) and np.array_equal(v, v0), kw
        assert o.day_info() == ref.day_info(), kw


def test_o8_templates_and_headline_buckets():
    doc = load_news_templates()
    b = doc["buckets"]
    assert set(b) == set(BUCKETS)
    counts = {k: len(v) for k, v in b.items()}
    assert sum(counts.values()) >= 60 and len(set(counts.values())) == 1  # balanced
    for name, items in b.items():
        sign = 1 if name.startswith("positive") else -1
        for it in items:
            assert it["sentiment"] * sign > 0, (name, it)  # sign disagreement = build error
            assert -1 <= it["sentiment"] <= 1
    n_seen = 0
    for seed in range(300):
        for t_ns, J, headline, sentiment, bucket in _day(seed, "auto", templates=b)["info"]["news"]:
            assert bucket == jump_bucket(J, R_BAR)
            pct = 100 * abs(J) / R_BAR
            assert bucket.endswith("small") == (pct < 0.3) and bucket.endswith("large") == (pct > 1.0)
            assert (J > 0) == bucket.startswith("positive") and (sentiment > 0) == (J > 0)
            assert headline in [it["headline"] for it in b[bucket]]
            assert 0 < pct <= 2.0 + 1e-9
            n_seen += 1
    assert n_seen > 600


def test_o9_synthetic_ou_unchanged():
    for end in ("10:30:00", "16:00:00"):
        o = build_config(seed=42, end_time=end, stdout_log_level="WARNING")["custom_properties"]["oracle"]
        v = o.path("ABM")[1]
        assert hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest() == (
            "815d74508d4820e23e0b92a009fce07a372c63d58e5c9bc9f2a67ec9f7a6c070")
        assert o.day_info() is None


def test_scripted_events_on_living_path():
    """S2 on a living day: the +2% jump adds J * a^(k - k0) from its grid point k0 on
    (a = exp(-kappa d): -0.3% over a day) and no extra draws are made."""
    base = _day(7, "normal")
    ev = [{"type": "jump", "t_ns": int(OPEN + 5400e9), "cents": 2000.0}]
    jumped = _day(7, "normal", events=ev)
    k = 5400
    assert np.array_equal(base["values"][:k], jumped["values"][:k])
    a = math.exp(-KAPPA * 1e9)
    expected = 2000.0 * a ** np.arange(len(TIMES) - k)
    assert np.allclose(jumped["values"][k:] - base["values"][k:], expected, rtol=0, atol=1e-6)
    assert jumped["info"] == base["info"]


# ── rule 2.4: the agents see the living value and its news ────────────────


def _matches(received, published, latency_ns=1_000_000_000):
    """Each headline received once, within the message latency (< 1 s) of its time."""
    return len(received) == len(published) and all(0 <= r - p < latency_ns for r, p in zip(received, published))


def test_news_reaches_every_agent_class_one_hour(tmp_path):
    from abides_core import abides
    from api.jobs import run_config_kwargs

    from .sim_helpers import params

    kw = run_config_kwargs(params(seed=20))
    kw.update(value_process="living_v1", day_type="normal")
    config = build_config(**kw)
    oracle = config["custom_properties"]["oracle"]
    news = [n for n in oracle.day_info()["news"] if n[0] < config["agents"][0].mkt_close]
    assert len(news) >= 2  # seed 20: -$2.85 at 09:43:36, +$3.31 at 10:27:54
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        es = abides.run(config)
    finally:
        os.chdir(cwd)
    agents = es["agents"]
    news_agent = agents[config["_news_oracle_id"]]
    sent = [(t, ev["headline"], ev["sentiment"]) for t, typ, ev in news_agent.log if typ == "NEWS_BROADCAST"]
    assert [(n[0], n[2], round(n[3], 4)) for n in news] == sent
    news_t = [n[0] for n in news]
    for i in config["_ekf_agent_ids"]:  # informed fundamentalists: every headline
        got = [t for t, typ, _ in agents[i].log if typ == "NEWS_RECEIVED"]
        assert _matches(got, news_t), ("FundamentalistAgent", i)
    n_mom_both = 0
    for i in config["_mom_ekf_agent_ids"]:  # momentum: every headline after its warm-up
        log = agents[i].log
        ready = min((t for t, typ, _ in log if typ == "MOM_KF_UPDATE"), default=None)
        got = [t for t, typ, _ in log if typ == "NEWS_RECEIVED"]
        # warm-up ignores news; x_hat can exist slightly before the first MOM_KF_UPDATE log
        assert all(any(0 <= r - p < 1_000_000_000 for p in news_t) for r in got), ("MomentumEKFAgent", i)
        after = [p for p in news_t if ready is not None and p > ready]
        assert all(any(0 <= r - p < 1_000_000_000 for r in got) for p in after), ("MomentumEKFAgent", i)
        n_mom_both += len(got) == len(news_t)
    assert n_mom_both >= 1
    # informed research readings are the living value plus noise
    errs = []
    for i in config["_ekf_agent_ids"]:
        for t, typ, ev in agents[i].log:
            if typ == "RESEARCH_READING":
                errs.append(ev["y_r"] - oracle.value_at("ABM", t))
    assert len(errs) > 100 and abs(np.mean(errs)) < 5 * np.std(errs) / math.sqrt(len(errs))

"""HTTP API tests that do not run a simulation (validation, presets, 404s)."""

import pytest
from fastapi.testclient import TestClient

from api.server import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["engine_version"]
    assert isinstance(body["finbert_available"], bool)


def test_presets(client):
    r = client.get("/api/news/presets")
    assert r.status_code == 200
    presets = r.json()
    assert len(presets) == 10
    assert all(-1 <= p["sentiment"] <= 1 and p["headline"] for p in presets)


@pytest.mark.parametrize(
    "body, fragment",
    [
        ({"seed": 1, "end_time": "10:30:00", "num_fund": 5, "num_mom": 5, "news": []}, "end_time"),
        # spec v1.4 §6.2: num_fund 0..200
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 201, "num_mom": 5, "news": []}, "num_fund"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "fund_mode": "value", "news": []}, "fund_mode"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 13, "news": []}, "num_mom"),
        ({"seed": -1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "news": []}, "seed"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5,
          "news": [{"offset": "5 min", "headline": "x", "sentiment": 0.1}]}, "HH:MM:SS"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5,
          "news": [{"offset": "00:05:00", "headline": "x", "sentiment": 1.5}]}, "sentiment"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5,
          "news": [{"offset": "00:30:00", "headline": "x", "sentiment": 0.1}]}, "outside the session"),
        # T-A4: market population bounds (spec v1.1 D4)
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "num_value": 151, "news": []}, "num_value"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "num_value": -1, "news": []}, "num_value"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "num_noise": 2001, "news": []}, "num_noise"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "num_noise": -5, "news": []}, "num_noise"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "num_mm": 3, "news": []}, "num_mm"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "num_mm": 1.5, "news": []}, "num_mm"),
    ],
)
def test_validation_returns_readable_400(client, body, fragment):
    r = client.post("/api/simulations", json=body)
    assert r.status_code == 400
    assert fragment in r.json()["detail"]


def test_unknown_run(client):
    assert client.get("/api/simulations/000000000000").status_code == 404
    assert client.get("/api/simulations/000000000000/data").status_code == 404


def test_runs_listing_shape(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    for item in r.json():
        assert set(item) == {"run_id", "params", "created_at", "wall_time_s", "summary"}


def test_population_defaults_and_bounds():
    """T-A4: defaults reproduce the standard market; bounds are inclusive.
    spec v1.4 §6.2 (N6): the standard market is P0 (60 informed, 0 value agents)."""
    from api.schema import RunParams

    d = RunParams(seed=1, end_time="10:00:00")
    assert (d.num_fund, d.num_mom, d.fund_mode, d.budget) == (60, 12, "informed", None)
    p = RunParams(seed=1, end_time="10:00:00", num_fund=5, num_mom=5)
    assert (p.num_value, p.num_noise, p.num_mm) == (0, 1000, 2)
    for kw in ({"num_value": 0}, {"num_value": 150}, {"num_noise": 0}, {"num_noise": 2000}, {"num_mm": 0},
               {"num_fund": 0}, {"num_fund": 200}, {"fund_mode": "price_only"}, {"budget": False}):
        RunParams(**{"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, **kw})
    # population fields are part of the cache key
    from api.jobs import make_run_id

    q = RunParams(seed=1, end_time="10:00:00", num_fund=5, num_mom=5, num_value=50)
    assert make_run_id(p, "e") != make_run_id(q, "e")


# ── spec v1.3 §9.3: the realism lab summary ───────────────────────────────


def test_lab_summary_404_when_absent(client, monkeypatch, tmp_path):
    from api import server

    monkeypatch.setattr(server, "LAB_SUMMARY_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(server, "LAB_SUMMARY_V13", tmp_path / "missing_v13.json")  # v1.4: fallback
    r = client.get("/api/lab/summary")
    assert r.status_code == 404
    assert "realism" in r.json()["detail"]


def test_lab_summary_served_when_present(client, monkeypatch, tmp_path):
    from api import server

    p = tmp_path / "summary.json"
    p.write_text('{"seeds": [42, 7], "configs": {}}', encoding="utf-8")
    monkeypatch.setattr(server, "LAB_SUMMARY_PATH", p)
    r = client.get("/api/lab/summary")
    assert r.status_code == 200
    assert r.json() == {"seeds": [42, 7], "configs": {}}

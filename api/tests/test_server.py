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
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 21, "num_mom": 5, "news": []}, "num_fund"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 13, "news": []}, "num_mom"),
        ({"seed": -1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5, "news": []}, "seed"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5,
          "news": [{"offset": "5 min", "headline": "x", "sentiment": 0.1}]}, "HH:MM:SS"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5,
          "news": [{"offset": "00:05:00", "headline": "x", "sentiment": 1.5}]}, "sentiment"),
        ({"seed": 1, "end_time": "10:00:00", "num_fund": 5, "num_mom": 5,
          "news": [{"offset": "00:30:00", "headline": "x", "sentiment": 0.1}]}, "outside the session"),
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

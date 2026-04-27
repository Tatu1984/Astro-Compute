from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "astro-compute"


def test_natal_requires_secret(monkeypatch):
    monkeypatch.setenv("COMPUTE_SHARED_SECRET", "test-secret")
    payload = {
        "birth_datetime_utc": datetime(1990, 5, 15, 14, 30, tzinfo=timezone.utc).isoformat(),
        "latitude": 28.6139,
        "longitude": 77.2090,
        "house_system": "PLACIDUS",
        "system": "BOTH",
    }
    # Missing header -> 401
    r = client.post("/natal", json=payload)
    assert r.status_code == 401

    # Wrong header -> 401
    r = client.post("/natal", json=payload, headers={"X-Compute-Secret": "nope"})
    assert r.status_code == 401

    # Right header -> 200
    r = client.post("/natal", json=payload, headers={"X-Compute-Secret": "test-secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "1"
    assert len(body["planets"]) == 12
    assert len(body["houses"]) == 12
    assert "ascendant_deg" in body

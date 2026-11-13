import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client(con):  # con fixture skips when the data is not downloaded
    from harness.api import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "ok" and r["first_incomplete_month"] == "2018-03-01"


def test_run_report_with_override(client):
    r = client.post("/reports/01", json={"params": {"quarter": "2017-18 Q2"}}).json()
    assert r["passed"] and r["params"]["quarter"] == "2017-18 Q2"
    assert r["checks"]["failed"] == []


def test_bad_parameter_is_a_422_not_a_crash(client):
    assert client.post("/reports/01", json={"params": {"quarter": "Q9"}}).status_code == 422


def test_ask_without_backend_is_refused(client, monkeypatch):
    monkeypatch.delenv("HARNESS_BACKEND", raising=False)
    assert client.post("/ask", json={"email": "hi", "email_date": "2018-01-01"}).status_code == 503

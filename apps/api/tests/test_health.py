import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def fake_database(monkeypatch: pytest.MonkeyPatch, status: db.DatabaseStatus) -> None:
    monkeypatch.setattr(db, "check_database", lambda _url: status)


def test_healthy_when_database_and_pgvector_are_available(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_database(monkeypatch, db.DatabaseStatus(reachable=True, pgvector_version="0.8.0"))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": {"reachable": True, "pgvector_version": "0.8.0"},
    }


@pytest.mark.parametrize(
    "status",
    [
        db.DatabaseStatus(reachable=False),
        db.DatabaseStatus(reachable=True, pgvector_version=None),
    ],
)
def test_degraded_without_a_database_or_pgvector(
    monkeypatch: pytest.MonkeyPatch, status: db.DatabaseStatus
) -> None:
    fake_database(monkeypatch, status)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_unreachable_database_is_reported_not_raised() -> None:
    # Nothing listens on port 1, so the connection is refused immediately.
    status = db.check_database("postgresql://nobody:nothing@127.0.0.1:1/none")

    assert status == db.DatabaseStatus(reachable=False)

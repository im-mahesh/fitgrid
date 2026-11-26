import os

import psycopg
import pytest
from fake_embeddings import embed
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app import db, embeddings
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://fitgrid:fitgrid@localhost:5434/fitgrid_test"
)


def _create_test_database(name: str) -> None:
    admin_url = make_conninfo(TEST_DATABASE_URL, dbname="postgres")
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=3) as connection:
        exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
        if not exists.fetchone():
            connection.execute(f'CREATE DATABASE "{name}"')


@pytest.fixture(scope="session")
def database_url() -> str:
    name = conninfo_to_dict(TEST_DATABASE_URL)["dbname"]
    # These tests wipe the tables, so refuse to run against anything but a test database.
    assert name.endswith("_test"), f"TEST_DATABASE_URL must name a *_test database, not {name!r}"
    try:
        _create_test_database(name)
    except psycopg.OperationalError:
        if os.environ.get("REQUIRE_DB"):
            raise
        pytest.skip("Postgres is not running (start it with: docker compose up -d db)")
    db.init_schema(TEST_DATABASE_URL)
    return TEST_DATABASE_URL


@pytest.fixture
def client(database_url: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", database_url)
    with db.connect(database_url) as connection:
        connection.execute("TRUNCATE documents CASCADE")
    return TestClient(app)


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """No test loads the real model. Returns every passage that gets embedded."""
    embedded: list[str] = []

    def passages(texts: list[str]) -> list[list[float]]:
        embedded.extend(texts)
        return [embed(text) for text in texts]

    monkeypatch.setattr(embeddings, "embed_passages", passages)
    monkeypatch.setattr(embeddings, "embed_query", embed)
    return embedded

import pytest
from fastapi.testclient import TestClient

from app import db, embeddings, retrieval
from app.parsing import Line

RESUME = "Jane Doe\nBuilt APIs in Python\nRan Kubernetes clusters\nTuned Postgres queries"


def add_resume(client: TestClient, text: str = RESUME) -> str:
    return client.put("/api/resume", data={"text": text}).json()["id"]


def search(database_url: str, document: str, question: str, limit: int = 1) -> list[int]:
    with db.connect(database_url) as connection:
        return [n for _, n in retrieval.search(connection, [document], question, limit)]


def stored_embeddings(database_url: str) -> int:
    with db.connect(database_url) as connection:
        return connection.execute("SELECT count(*) FROM line_embeddings").fetchone()[0]


def test_finds_the_closest_line(client: TestClient, database_url: str) -> None:
    resume = add_resume(client)

    assert search(database_url, resume, "Any postgres work?") == [4]
    assert search(database_url, resume, "kubernetes") == [3]


def test_lines_are_embedded_once_and_again_for_a_new_model(
    client: TestClient,
    database_url: str,
    fake_embeddings: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resume = add_resume(client)
    assert fake_embeddings == []  # uploading does not embed

    search(database_url, resume, "python")
    search(database_url, resume, "docker")
    assert len(fake_embeddings) == 4

    monkeypatch.setattr(embeddings, "MODEL", "another-model")
    search(database_url, resume, "python")

    assert len(fake_embeddings) == 8
    assert stored_embeddings(database_url) == 4


def test_deleting_a_document_deletes_its_embeddings(client: TestClient, database_url: str) -> None:
    resume = add_resume(client)
    search(database_url, resume, "python")

    client.delete(f"/api/documents/{resume}")

    assert stored_embeddings(database_url) == 0


def test_neighbouring_lines_come_with_a_hit() -> None:
    lines = [Line(number=n, text=str(n)) for n in range(1, 8)]

    chosen = retrieval.with_neighbours({1, 5}, lines)

    assert [line.number for line in chosen] == [1, 2, 4, 5, 6]


def test_the_section_is_embedded_with_the_line() -> None:
    assert retrieval._passage("Experience", "Ran Docker") == "Experience: Ran Docker"
    assert retrieval._passage("Skills", "Skills") == "Skills"
    assert retrieval._passage(None, "Jane") == "Jane"

import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db, documents
from app.main import app
from pdf_helper import column, make_pdf

RESUME = "Jane Doe\nSKILLS\nPython, Docker"


def paste_resume(client: TestClient, text: str = RESUME):
    return client.put("/api/resume", data={"text": text})


def paste_job(client: TestClient, text: str = "Platform Engineer\n- Python", **extra: str):
    return client.post("/api/jobs", data={"text": text, **extra})


def listing(client: TestClient) -> dict:
    return client.get("/api/documents").json()


def line_count_in_database(database_url: str) -> int:
    with db.connect(database_url) as connection:
        return connection.execute("SELECT count(*) FROM document_lines").fetchone()[0]


def test_pasted_resume_is_stored_as_numbered_lines(client: TestClient) -> None:
    response = paste_resume(client)

    assert response.status_code == 200
    body = response.json()
    assert (body["kind"], body["title"], body["line_count"]) == ("resume", "Pasted resume", 3)
    assert body["lines"][2] == {"number": 3, "section": "SKILLS", "text": "Python, Docker"}
    assert client.get(f"/api/documents/{body['id']}").json() == body


def test_pdf_resume_is_parsed_and_titled_by_filename(client: TestClient) -> None:
    pdf = make_pdf([column(60, ["Jane Doe", "Python developer"])])

    response = client.put("/api/resume", files={"file": ("jane.pdf", pdf, "application/pdf")})

    assert response.status_code == 200
    assert response.json()["title"] == "jane.pdf"
    assert [line["text"] for line in response.json()["lines"]] == ["Jane Doe", "Python developer"]


def test_a_new_resume_replaces_the_old_one(client: TestClient, database_url: str) -> None:
    first = paste_resume(client).json()["id"]

    second = paste_resume(client, "New resume").json()["id"]

    assert listing(client)["resume"]["id"] == second
    assert client.get(f"/api/documents/{first}").status_code == 404
    assert line_count_in_database(database_url) == 1


def test_a_failed_upload_keeps_the_existing_resume(client: TestClient) -> None:
    first = paste_resume(client).json()["id"]

    response = client.put("/api/resume", files={"file": ("cv.pdf", b"nope", "application/pdf")})

    assert response.status_code == 400
    assert listing(client)["resume"]["id"] == first


def test_job_title_is_the_given_one_or_the_first_line(client: TestClient) -> None:
    assert paste_job(client).json()["title"] == "Platform Engineer"
    assert paste_job(client, title="  Acme: SRE  ").json()["title"] == "Acme: SRE"
    assert len(paste_job(client, title="x" * 200).json()["title"]) == documents.MAX_TITLE_CHARS


def test_up_to_five_jobs_are_accepted(client: TestClient) -> None:
    statuses = [paste_job(client, title=f"Job {i}").status_code for i in range(6)]

    assert statuses == [201] * 5 + [409]
    assert [job["title"] for job in listing(client)["jobs"]] == [f"Job {i}" for i in range(5)]
    assert "up to 5 jobs" in paste_job(client).json()["detail"]


def test_deleting_a_document_removes_its_lines(client: TestClient, database_url: str) -> None:
    job = paste_job(client).json()["id"]

    assert client.delete(f"/api/documents/{job}").status_code == 204

    assert listing(client) == {"resume": None, "jobs": []}
    assert line_count_in_database(database_url) == 0
    assert client.delete(f"/api/documents/{job}").status_code == 404


def test_delete_all_removes_everything(client: TestClient, database_url: str) -> None:
    paste_resume(client)
    paste_job(client)

    assert client.delete("/api/documents").status_code == 204

    assert listing(client) == {"resume": None, "jobs": []}
    assert line_count_in_database(database_url) == 0


def test_unknown_document_is_a_404(client: TestClient) -> None:
    assert client.get(f"/api/documents/{uuid4()}").status_code == 404
    assert client.get("/api/documents/not-a-uuid").status_code == 422


@pytest.mark.parametrize("data", [{}, {"text": "   "}])
def test_input_must_be_a_file_or_text(client: TestClient, data: dict[str, str]) -> None:
    response = client.put("/api/resume", data=data)

    assert response.status_code == 400
    assert "either a file or pasted text" in response.json()["detail"]


def test_a_file_and_text_together_are_rejected(client: TestClient) -> None:
    files = {"file": ("cv.txt", b"Jane", "text/plain")}

    assert client.put("/api/resume", data={"text": "Jane"}, files=files).status_code == 400


def test_oversized_input_is_rejected(client: TestClient) -> None:
    big_file = {"file": ("cv.txt", b"a" * (documents.MAX_FILE_BYTES + 1), "text/plain")}
    assert "too large" in client.put("/api/resume", files=big_file).json()["detail"]

    too_much_text = "a" * (documents.MAX_TEXT_CHARS + 1)
    assert "limited to 50,000" in paste_resume(client, too_much_text).json()["detail"]


def test_document_text_never_reaches_the_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app")

    paste_resume(client, "SECRET-MARKER-123 lives at 42 Privacy Road")
    client.put("/api/resume", files={"file": ("a.pdf", b"%PDF-1.4 SECRET-MARKER-123", "x/y")})

    assert "SECRET-MARKER-123" not in caplog.text


def test_database_outage_is_a_503_with_a_plain_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:nothing@127.0.0.1:1/none")

    response = TestClient(app).get("/api/documents")

    assert response.status_code == 503
    assert response.json()["detail"] == "The database is unavailable. Try again shortly."

import logging
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import db, extraction, llm
from fake_claude import FakeClaude, rate_limited, reply, requirement

JOB = "Platform Engineer\nRequirements\n- Python or Go\n- Kubernetes is a plus"
REPLY = reply(requirement("Python or Go", [3]), requirement("Kubernetes", [4], "nice"))


@pytest.fixture
def claude(monkeypatch: pytest.MonkeyPatch) -> FakeClaude:
    fake = FakeClaude(REPLY)
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def empty_call_log(database_url: str) -> None:
    with db.connect(database_url) as connection:
        connection.execute("TRUNCATE llm_calls")


def add_job(client: TestClient, text: str = JOB) -> str:
    return client.post("/api/jobs", data={"text": text}).json()["id"]


def calls(database_url: str) -> list[tuple]:
    with db.connect(database_url) as connection:
        return connection.execute(
            "SELECT stage, outcome, input_tokens, rejected_items FROM llm_calls ORDER BY id"
        ).fetchall()


def test_nothing_is_extracted_until_asked(client: TestClient, claude: FakeClaude) -> None:
    job = add_job(client)

    response = client.get(f"/api/jobs/{job}/requirements")

    assert response.json() == {"extracted": False, "model": None, "requirements": []}
    assert claude.requests == []


def test_extracting_stores_the_result_and_logs_the_call(
    client: TestClient, claude: FakeClaude, database_url: str
) -> None:
    job = add_job(client)

    response = client.post(f"/api/jobs/{job}/requirements")

    assert response.status_code == 200
    body = response.json()
    assert body["extracted"] is True
    assert body["model"] == "claude-sonnet-5-5"
    assert body["requirements"][1] == {
        "position": 2,
        "text": "Kubernetes",
        "importance": "nice",
        "category": "skill",
        "line_numbers": [4],
    }
    assert client.get(f"/api/jobs/{job}/requirements").json() == body
    assert calls(database_url) == [("extract_requirements", "ok", 1000, 0)]


def test_a_second_request_reuses_the_stored_result(client: TestClient, claude: FakeClaude) -> None:
    job = add_job(client)

    first = client.post(f"/api/jobs/{job}/requirements").json()
    second = client.post(f"/api/jobs/{job}/requirements").json()

    assert second == first
    assert len(claude.requests) == 1


@pytest.mark.parametrize("change", ["prompt", "model"])
def test_a_new_prompt_or_model_means_extracting_again(
    client: TestClient, claude: FakeClaude, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    job = add_job(client)
    client.post(f"/api/jobs/{job}/requirements")

    if change == "prompt":
        monkeypatch.setattr(extraction, "PROMPT_VERSION", "requirements-v2")
    else:
        monkeypatch.setenv("FITGRID_MODEL", "claude-opus-5-5")

    assert client.get(f"/api/jobs/{job}/requirements").json()["extracted"] is False
    assert client.post(f"/api/jobs/{job}/requirements").json()["extracted"] is True
    assert len(claude.requests) == 2


def test_a_job_with_no_requirements_is_remembered_as_such(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeClaude(reply())
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    job = add_job(client, "We are a fun company.")

    client.post(f"/api/jobs/{job}/requirements")
    again = client.post(f"/api/jobs/{job}/requirements").json()

    assert (again["extracted"], again["requirements"]) == (True, [])
    assert len(fake.requests) == 1


def test_a_failed_call_is_logged_and_nothing_is_stored(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    monkeypatch.setattr(llm, "get_client", lambda: FakeClaude(error=rate_limited()))
    job = add_job(client)

    response = client.post(f"/api/jobs/{job}/requirements")

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"]
    assert client.get(f"/api/jobs/{job}/requirements").json()["extracted"] is False
    assert calls(database_url) == [("extract_requirements", "api_error", None, 0)]


def test_without_an_api_key_the_error_says_so(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    job = add_job(client)

    response = client.post(f"/api/jobs/{job}/requirements")

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_only_jobs_have_requirements(client: TestClient, claude: FakeClaude) -> None:
    resume = client.put("/api/resume", data={"text": "Jane"}).json()["id"]

    assert client.post(f"/api/jobs/{resume}/requirements").status_code == 404
    assert client.post(f"/api/jobs/{uuid4()}/requirements").status_code == 404
    assert claude.requests == []


def test_deleting_the_job_removes_requirements_but_keeps_the_metrics(
    client: TestClient, claude: FakeClaude, database_url: str
) -> None:
    job = add_job(client)
    client.post(f"/api/jobs/{job}/requirements")

    client.delete("/api/documents")

    with db.connect(database_url) as connection:
        assert connection.execute("SELECT count(*) FROM requirements").fetchone() == (0,)
    assert len(calls(database_url)) == 1


def test_a_job_deleted_during_extraction_is_a_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    job = add_job(client)
    fake = FakeClaude(REPLY)
    create = fake.beta.messages.create

    def delete_then_reply(**request: object):
        with db.connect(database_url) as connection:
            connection.execute("DELETE FROM documents")
        return create(**request)

    fake.beta.messages.create = delete_then_reply
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    assert client.post(f"/api/jobs/{job}/requirements").status_code == 404


def test_a_logging_failure_does_not_lose_a_paid_for_result(
    client: TestClient, claude: FakeClaude, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object) -> None:
        raise psycopg.OperationalError("log table unavailable")

    monkeypatch.setattr("app.store.record_llm_call", broken)
    job = add_job(client)

    assert client.post(f"/api/jobs/{job}/requirements").json()["extracted"] is True


def test_document_and_reply_text_never_reach_the_logs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app")
    fake = FakeClaude(reply(requirement("REPLY-MARKER-9", [1])))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    job = add_job(client, "POST-MARKER-7 must know Rust")

    client.post(f"/api/jobs/{job}/requirements")

    assert "llm_call" in caplog.text
    assert "POST-MARKER-7" not in caplog.text
    assert "REPLY-MARKER-9" not in caplog.text

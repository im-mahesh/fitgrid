import logging

import pytest
from fastapi.testclient import TestClient

from app import db, llm, matching
from fake_claude import FakeClaude, match_reply, rate_limited, reply, requirement, verdict

JOB = "Platform Engineer\n- Python\n- Kubernetes"
RESUME = "Jane Doe\nBuilt APIs in Python\nRan Docker"
EXTRACTION = reply(requirement("Python", [2]), requirement("Kubernetes", [3]))
MATCHES = match_reply(verdict(1, "met", [2]), verdict(2, "not_found", []))


class Claude:
    """Answers extraction and matching with their own canned replies."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.extraction = FakeClaude(EXTRACTION)
        self.matching = FakeClaude(MATCHES)
        self.current = self.extraction
        monkeypatch.setattr(llm, "get_client", lambda: self.current)


@pytest.fixture
def claude(monkeypatch: pytest.MonkeyPatch) -> Claude:
    return Claude(monkeypatch)


def add_resume(client: TestClient, text: str = RESUME) -> str:
    return client.put("/api/resume", data={"text": text}).json()["id"]


def ready_job(client: TestClient, claude: Claude) -> str:
    """A job whose requirements are extracted, with the fake now set to answer matching."""
    job = client.post("/api/jobs", data={"text": JOB}).json()["id"]
    claude.current = claude.extraction
    client.post(f"/api/jobs/{job}/requirements")
    claude.current = claude.matching
    return job


def match(client: TestClient, job: str):
    return client.post(f"/api/jobs/{job}/match")


def stored(client: TestClient, job: str) -> dict:
    return client.get(f"/api/jobs/{job}/match").json()


def test_matching_stores_results_and_reuses_them(client: TestClient, claude: Claude) -> None:
    add_resume(client)
    job = ready_job(client, claude)
    assert stored(client, job) == {"matched": False, "model": None, "results": []}

    first = match(client, job)
    second = match(client, job)

    assert first.status_code == 200
    assert first.json()["results"][0] == {
        "position": 1,
        "verdict": "met",
        "reason": "Your resume says so.",
        "line_numbers": [2],
    }
    assert second.json() == first.json() == stored(client, job)
    assert len(claude.matching.requests) == 1


def test_matching_needs_a_resume_and_requirements(client: TestClient, claude: Claude) -> None:
    job = client.post("/api/jobs", data={"text": JOB}).json()["id"]
    assert match(client, job).json()["detail"] == "Add your resume first."

    add_resume(client)
    response = match(client, job)

    assert response.status_code == 409
    assert "requirements first" in response.json()["detail"]
    assert claude.matching.requests == []


def test_a_job_without_requirements_is_not_sent(client: TestClient, claude: Claude) -> None:
    add_resume(client)
    claude.extraction = FakeClaude(reply())
    job = ready_job(client, claude)

    assert match(client, job).status_code == 409
    assert claude.matching.requests == []


@pytest.mark.parametrize("change", ["replace resume", "delete resume", "re-extract", "delete job"])
def test_results_disappear_when_what_they_were_based_on_changes(
    client: TestClient, claude: Claude, database_url: str, change: str
) -> None:
    resume = add_resume(client)
    job = ready_job(client, claude)
    match(client, job)

    if change == "replace resume":
        add_resume(client, "A different person")
    elif change == "delete resume":
        client.delete(f"/api/documents/{resume}")
    elif change == "re-extract":
        with db.connect(database_url) as connection:
            connection.execute("DELETE FROM extractions")
    else:
        client.delete(f"/api/documents/{job}")

    with db.connect(database_url) as connection:
        assert connection.execute("SELECT count(*) FROM matches").fetchone() == (0,)


def test_a_new_prompt_means_matching_again(
    client: TestClient, claude: Claude, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_resume(client)
    job = ready_job(client, claude)
    match(client, job)

    monkeypatch.setattr(matching, "PROMPT_VERSION", "match-v2")

    assert stored(client, job)["matched"] is False
    assert match(client, job).json()["matched"] is True
    assert len(claude.matching.requests) == 2


def test_a_failed_call_stores_nothing(client: TestClient, claude: Claude) -> None:
    add_resume(client)
    job = ready_job(client, claude)
    claude.current = FakeClaude(error=rate_limited())

    assert match(client, job).status_code == 429
    assert stored(client, job)["matched"] is False


def test_a_resume_replaced_during_matching_is_a_409(client: TestClient, claude: Claude) -> None:
    add_resume(client)
    job = ready_job(client, claude)
    create = claude.matching.beta.messages.create

    def replace_then_reply(**request: object):
        add_resume(client, "Someone new")
        return create(**request)

    claude.matching.beta.messages.create = replace_then_reply

    response = match(client, job)

    assert response.status_code == 409
    assert "changed" in response.json()["detail"]


def test_resume_text_never_reaches_the_logs(
    client: TestClient, claude: Claude, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app")
    add_resume(client, "RESUME-MARKER-3\nBuilt things")
    job = ready_job(client, claude)

    match(client, job)

    assert "llm_call" in caplog.text
    assert "RESUME-MARKER-3" not in caplog.text

import pytest
from fastapi.testclient import TestClient

from app import llm, matching
from fake_claude import FakeClaude, match_reply, reply, requirement, verdict


def use(monkeypatch: pytest.MonkeyPatch, fake: FakeClaude) -> FakeClaude:
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    return fake


def add_job(client: TestClient, title: str) -> str:
    data = {"title": title, "text": "Engineer\n- Python"}
    return client.post("/api/jobs", data=data).json()["id"]


def overview(client: TestClient) -> dict:
    response = client.get("/api/overview")
    assert response.status_code == 200
    return response.json()


def test_empty_overview(client: TestClient) -> None:
    assert overview(client) == {"resume_id": None, "jobs": []}


def test_each_job_reports_how_far_it_has_got(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    resume = client.put("/api/resume", data={"text": "Built APIs in Python"}).json()["id"]
    done, extracted, empty, fresh = (add_job(client, t) for t in ("Done", "Read", "Empty", "New"))
    use(monkeypatch, FakeClaude(reply(requirement("Python", [2]))))
    client.post(f"/api/jobs/{done}/requirements")
    client.post(f"/api/jobs/{extracted}/requirements")
    use(monkeypatch, FakeClaude(reply()))
    client.post(f"/api/jobs/{empty}/requirements")
    use(monkeypatch, FakeClaude(match_reply(verdict(1, "met", [1]))))
    client.post(f"/api/jobs/{done}/match")

    body = overview(client)

    assert body["resume_id"] == resume
    assert [j["job"]["title"] for j in body["jobs"]] == ["Done", "Read", "Empty", "New"]
    progress = [
        (
            None if j["requirements"] is None else len(j["requirements"]),
            None if j["matches"] is None else [m["verdict"] for m in j["matches"]],
        )
        for j in body["jobs"]
    ]
    assert progress == [(1, ["met"]), (1, None), (0, None), (None, None)]
    assert [j["job"]["id"] for j in body["jobs"]] == [done, extracted, empty, fresh]


def test_reading_the_overview_never_calls_the_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_job(client, "Job")
    fake = use(monkeypatch, FakeClaude())

    overview(client)

    assert fake.requests == []


def test_results_from_an_older_prompt_are_not_shown(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.put("/api/resume", data={"text": "Python"})
    job = add_job(client, "Job")
    use(monkeypatch, FakeClaude(reply(requirement("Python", [2]))))
    client.post(f"/api/jobs/{job}/requirements")
    use(monkeypatch, FakeClaude(match_reply(verdict(1, "met", [1]))))
    client.post(f"/api/jobs/{job}/match")

    monkeypatch.setattr(matching, "PROMPT_VERSION", "match-v2")
    [entry] = overview(client)["jobs"]

    assert entry["requirements"] is not None
    assert entry["matches"] is None

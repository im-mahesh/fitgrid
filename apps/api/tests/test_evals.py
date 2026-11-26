"""The eval harness itself: a wrong harness gives confident, wrong numbers."""

import csv
import json
import shutil
from pathlib import Path

import pytest

from app import llm
from app.extraction import Requirement
from app.matching import Match
from evals import dataset, run, score, sheet
from evals.dataset import LabelError, VerdictLabel
from fake_claude import FakeClaude, match_reply, rate_limited, reply, requirement, verdict


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A copy of the real cases, so tests can fill in labels without touching yours."""
    for part in ("matching", "extraction"):
        shutil.copytree(dataset.ROOT / part, tmp_path / part)
        (tmp_path / part / "labels.csv").unlink(missing_ok=True)
    sheet.write(tmp_path)
    return tmp_path


def edit_csv(path: Path, change) -> None:
    rows = dataset.read_rows(path)
    for row in rows:
        change(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def label_all(root: Path) -> None:
    """Stand-in labels for testing the harness. They say nothing about the right answers."""
    edit_csv(
        root / "matching" / "labels.csv",
        lambda row: row.update(
            {"verdict": "met", "resume_lines": "1"}
            if int(row["number"]) % 2
            else {"verdict": "not_found"}
        ),
    )
    edit_csv(root / "extraction" / "labels.csv", lambda row: row.update(label="none"))


def oracle_reply() -> str:
    return match_reply(
        *(verdict(n, "met", [1]) if n % 2 else verdict(n, "not_found", []) for n in range(1, 9))
    )


def results(root: Path, name: str = "results.jsonl") -> list[dict]:
    [folder] = (root / "results").iterdir()
    path = folder / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def summary(root: Path) -> str:
    [folder] = (root / "results").iterdir()
    return (folder / "summary.md").read_text()


def use(monkeypatch: pytest.MonkeyPatch, fake: FakeClaude) -> FakeClaude:
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    return fake


# --- the cases that ship ---------------------------------------------------------


def test_the_shipped_cases_are_well_formed() -> None:
    cases = dataset.matching_cases()

    assert len({c.id for c in cases}) == len(cases)
    assert sum(len(c.requirements) for c in cases) >= 40
    assert all(len(set(c.requirements)) == len(c.requirements) for c in cases)
    assert len(dataset.extraction_cases()) >= 3


def test_label_files_start_blank_and_match_the_cases(root: Path) -> None:
    rows = dataset.read_rows(root / "matching" / "labels.csv")

    assert len(rows) == sum(len(c.requirements) for c in dataset.matching_cases(root))
    assert all(r["verdict"] == "" and r["resume_lines"] == "" for r in rows)
    assert (root / "review.md").read_text().count("### ") == 9


def test_regenerating_the_sheet_keeps_labels_unless_the_text_changed(root: Path) -> None:
    label_all(root)
    cases = root / "matching" / "cases.json"
    cases.write_text(cases.read_text().replace('"Python programming"', '"Python 3"'))

    cleared = sheet.write(root)

    rows = {(r["case_id"], r["number"]): r for r in dataset.read_rows(root / "matching/labels.csv")}
    assert cleared == 1
    assert rows[("backend", "1")]["verdict"] == ""
    assert rows[("backend", "3")]["verdict"] == "met"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"verdict": ""}, "verdict must be one of"),
        ({"verdict": "yes"}, "verdict must be one of"),
        ({"verdict": "met", "resume_lines": ""}, "needs the resume lines"),
        ({"verdict": "partial", "resume_lines": "99"}, "no such resume line"),
        ({"verdict": "met", "resume_lines": "line 3"}, "must be numbers"),
    ],
)
def test_incomplete_or_wrong_labels_are_reported(
    root: Path, change: dict[str, str], message: str
) -> None:
    label_all(root)
    edit_csv(
        root / "matching" / "labels.csv",
        lambda row: (
            row.update(change) if (row["case_id"], row["number"]) == ("data", "1") else None
        ),
    )

    with pytest.raises(LabelError, match=message):
        dataset.matching_labels(dataset.matching_cases(root), root)


# --- scoring ---------------------------------------------------------------------


def label(verdict_name: str, *lines: int) -> VerdictLabel:
    return VerdictLabel(verdict=verdict_name, resume_lines=set(lines))


def match(position: int, verdict_name: str, *lines: int) -> Match:
    return Match(position=position, verdict=verdict_name, reason="r", line_numbers=list(lines))


def test_matching_metrics_count_false_mets_and_wrong_evidence() -> None:
    labels = {
        ("c", 1): label("met", 2),
        ("c", 2): label("partial", 3),
        ("c", 3): label("not_found"),
        ("c", 4): label("met", 4),
    }
    rows = score.grade_matches(
        "c",
        [match(1, "met", 2), match(2, "met", 9), match(3, "met", 1), match(4, "not_assessed")],
        labels,
    )

    metrics = score.matching_metrics(rows)

    assert (metrics["accuracy"].hits, metrics["accuracy"].total) == (1, 4)
    assert (metrics["false_met"].hits, metrics["false_met"].total) == (2, 2)
    assert (metrics["met_found"].hits, metrics["met_found"].total) == (1, 2)
    # Of three claims on supportable requirements, two cite a labelled line: only #1 does.
    assert (metrics["evidence_right"].hits, metrics["evidence_right"].total) == (1, 2)


def test_extraction_scoring_flags_forbidden_and_missed_lines() -> None:
    labels = {("j", 1): "none", ("j", 2): "must", ("j", 3): "nice", ("j", 4): "forbidden"}
    found = [
        Requirement(position=1, text="a", importance="must", category="skill", line_numbers=[2]),
        Requirement(position=2, text="b", importance="must", category="other", line_numbers=[4]),
    ]

    row = score.grade_extraction("j", found, labels)

    assert (row.found, row.required, row.cited, row.cited_right) == (1, 2, 2, 1)
    assert row.forbidden_cited == [4]
    assert row.importance_right == 1


def test_interval_is_wide_for_a_small_sample() -> None:
    low, high = score.Ratio(hits=9, total=10).interval()

    assert 0.55 < low < 0.65 and 0.95 < high <= 1.0
    assert score.Ratio(hits=0, total=0).value is None


# --- the runner ------------------------------------------------------------------


def test_nothing_is_called_without_yes(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    label_all(root)
    fake = use(monkeypatch, FakeClaude())

    assert run.main(["matching"], root) == 0

    assert fake.requests == []
    assert "6 calls to claude-sonnet-5-5" in capsys.readouterr().out
    assert not (root / "results").exists()


def test_unlabelled_cases_stop_the_run_before_any_call(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = use(monkeypatch, FakeClaude())

    assert run.main(["matching", "--yes"], root) == 2
    assert fake.requests == []


def test_a_model_that_agrees_with_every_label_scores_full_marks(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    label_all(root)
    use(monkeypatch, FakeClaude(oracle_reply()))

    assert run.main(["matching", "--yes"], root) == 0

    assert len(results(root)) == 6
    text = summary(root)
    assert "| accuracy | 100% | 48/48 |" in text
    assert "| false_met | 0% | 0/24 |" in text
    assert "Disagreements (0)" in text
    assert "Cost: $0.0420" in text  # 6 calls x (1000 in, 500 out) at Sonnet prices


def test_a_model_that_says_met_to_everything_is_caught(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    label_all(root)
    everything = match_reply(*(verdict(n, "met", [1]) for n in range(1, 9)))
    use(monkeypatch, FakeClaude(everything))

    run.main(["matching", "--yes"], root)

    assert "| false_met | 100% | 24/24 |" in summary(root)
    assert "| accuracy | 50% | 24/48 |" in summary(root)


@pytest.mark.parametrize(
    ("fake", "reason"),
    [
        (FakeClaude(error=rate_limited()), "rate limit"),
        (FakeClaude(stop_reason="max_tokens"), "cut off"),
        (FakeClaude(match_reply(), model="some-fallback-model"), "served by some-fallback-model"),
    ],
)
def test_failed_calls_are_not_scored_as_wrong_answers(
    root: Path, monkeypatch: pytest.MonkeyPatch, fake: FakeClaude, reason: str
) -> None:
    label_all(root)
    use(monkeypatch, fake)

    assert run.main(["matching", "--yes"], root) == 1

    assert results(root) == []
    errors = results(root, "errors.jsonl")
    assert len(errors) == 6 and reason in errors[0]["failure"]
    assert "Calls scored: 0 of 6." in summary(root)


def test_extraction_flow_runs_the_apps_own_code(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    label_all(root)
    fake = use(monkeypatch, FakeClaude(reply(requirement("Python", [1]))))

    assert run.main(["extraction", "--yes", "--reps", "2"], root) == 0

    assert len(results(root)) == 6
    assert "<job_post>" in fake.requests[0]["messages"][0]["content"]

"""Load the eval cases and the human-written labels."""

import csv
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.parsing import Line, lines_from_text

ROOT = Path(__file__).parent
MATCHING_FIELDS = ["case_id", "number", "requirement", "verdict", "resume_lines", "note"]
EXTRACTION_FIELDS = ["case_id", "line", "text", "label", "note"]
VERDICTS = ("met", "partial", "not_found")
LINE_LABELS = ("must", "nice", "none", "forbidden")


class LabelError(ValueError):
    """The labels are missing or invalid; the message says what to fix."""


class MatchingCase(BaseModel):
    id: str
    resume: list[Line]
    requirements: list[str]
    as_of: date


class ExtractionCase(BaseModel):
    id: str
    lines: list[Line]


class VerdictLabel(BaseModel):
    verdict: Literal["met", "partial", "not_found"]
    resume_lines: set[int]


def matching_cases(root: Path = ROOT) -> list[MatchingCase]:
    folder = root / "matching"
    data = json.loads((folder / "cases.json").read_text())
    return [
        MatchingCase(
            id=case["id"],
            # Numbered by the app's own parser, so labels cite what the model sees.
            resume=lines_from_text((folder / "resumes" / case["resume"]).read_text()),
            requirements=case["requirements"],
            as_of=data["as_of"],
        )
        for case in data["cases"]
    ]


def extraction_cases(root: Path = ROOT) -> list[ExtractionCase]:
    return [
        ExtractionCase(id=path.stem, lines=lines_from_text(path.read_text()))
        for path in sorted((root / "extraction" / "jobs").glob("*.txt"))
    ]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:  # spreadsheets add a BOM
        return list(csv.DictReader(handle))


def _line_set(raw: str, where: str) -> set[int]:
    parts = [p for p in raw.replace(",", ";").replace(" ", ";").split(";") if p]
    if not all(p.isdigit() for p in parts):
        raise LabelError(f"{where}: resume_lines must be numbers like 3;5, not {raw!r}")
    return {int(p) for p in parts}


def matching_labels(
    cases: list[MatchingCase], root: Path = ROOT
) -> dict[tuple[str, int], VerdictLabel]:
    """One label per requirement. Raises LabelError listing every problem."""
    rows = {
        (r["case_id"], int(r["number"])): r for r in read_rows(root / "matching" / "labels.csv")
    }
    labels: dict[tuple[str, int], VerdictLabel] = {}
    problems: list[str] = []
    for case in cases:
        real = {line.number for line in case.resume}
        for number, text in enumerate(case.requirements, start=1):
            where = f"{case.id} #{number} ({text})"
            row = rows.get((case.id, number))
            verdict = (row or {}).get("verdict", "").strip().lower()
            if verdict not in VERDICTS:
                problems.append(f"{where}: verdict must be one of {', '.join(VERDICTS)}")
                continue
            try:
                cited = _line_set(row["resume_lines"], where)
            except LabelError as exc:
                problems.append(str(exc))
                continue
            if verdict != "not_found" and not cited:
                problems.append(f"{where}: '{verdict}' needs the resume lines that show it")
            elif not cited <= real:
                problems.append(f"{where}: no such resume line {sorted(cited - real)}")
            else:
                labels[(case.id, number)] = VerdictLabel(
                    verdict=verdict, resume_lines=cited if verdict != "not_found" else set()
                )
    if problems:
        raise LabelError(
            f"{len(problems)} matching labels to fix:\n  " + "\n  ".join(problems[:15])
        )
    return labels


def extraction_labels(cases: list[ExtractionCase], root: Path = ROOT) -> dict[tuple[str, int], str]:
    rows = {
        (r["case_id"], int(r["line"])): r["label"].strip().lower()
        for r in read_rows(root / "extraction" / "labels.csv")
    }
    problems = [
        f"{case.id} line {line.number} ({line.text})"
        for case in cases
        for line in case.lines
        if rows.get((case.id, line.number)) not in LINE_LABELS
    ]
    if problems:
        raise LabelError(
            f"{len(problems)} job lines still need a label ({', '.join(LINE_LABELS)}):\n  "
            + "\n  ".join(problems[:15])
        )
    return rows

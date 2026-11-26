"""Grade model output against the labels. Plain code: no model judges another."""

import math
from collections import Counter

from pydantic import BaseModel

from app.extraction import Requirement
from app.matching import Match
from evals.dataset import VERDICTS, VerdictLabel


class Ratio(BaseModel):
    hits: int
    total: int

    @property
    def value(self) -> float | None:
        return self.hits / self.total if self.total else None

    def interval(self) -> tuple[float, float] | None:
        """95% Wilson interval: honest about how little a small sample says."""
        if not self.total:
            return None
        z = 1.96
        p, n = self.hits / self.total, self.total
        centre = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        return max(0.0, centre - half), min(1.0, centre + half)


class VerdictRow(BaseModel):
    case_id: str
    number: int
    expected: str
    got: str
    expected_lines: list[int]
    got_lines: list[int]


def grade_matches(
    case_id: str, matches: list[Match], labels: dict[tuple[str, int], VerdictLabel]
) -> list[VerdictRow]:
    return [
        VerdictRow(
            case_id=case_id,
            number=m.position,
            expected=labels[(case_id, m.position)].verdict,
            got=m.verdict,
            expected_lines=sorted(labels[(case_id, m.position)].resume_lines),
            got_lines=sorted(m.line_numbers),
        )
        for m in matches
    ]


def matching_metrics(rows: list[VerdictRow]) -> dict[str, Ratio]:
    not_met = [r for r in rows if r.expected != "met"]
    met = [r for r in rows if r.expected == "met"]
    claimed = [r for r in rows if r.expected != "not_found" and r.got in ("met", "partial")]
    return {
        "accuracy": Ratio(hits=sum(r.got == r.expected for r in rows), total=len(rows)),
        # The worst error: telling someone their resume proves what it doesn't.
        "false_met": Ratio(hits=sum(r.got == "met" for r in not_met), total=len(not_met)),
        "met_found": Ratio(hits=sum(r.got == "met" for r in met), total=len(met)),
        "evidence_right": Ratio(
            hits=sum(bool(set(r.got_lines) & set(r.expected_lines)) for r in claimed),
            total=len(claimed),
        ),
    }


def confusion(rows: list[VerdictRow]) -> str:
    counts = Counter((r.expected, r.got) for r in rows)
    columns = (*VERDICTS, "not_assessed")
    header = "| your label \\ model | " + " | ".join(columns) + " |"
    body = [
        f"| {expected} | " + " | ".join(str(counts[(expected, got)]) for got in columns) + " |"
        for expected in VERDICTS
    ]
    return "\n".join([header, "|" + "---|" * (len(columns) + 1), *body])


class ExtractionRow(BaseModel):
    case_id: str
    found: int
    required: int
    cited: int
    cited_right: int
    forbidden_cited: list[int]
    importance_right: int


def grade_extraction(
    case_id: str, requirements: list[Requirement], labels: dict[tuple[str, int], str]
) -> ExtractionRow:
    """Compare the lines the requirements cite with the lines labelled as requirements."""
    by_line = {line: label for (case, line), label in labels.items() if case == case_id}
    wanted = {line for line, label in by_line.items() if label in ("must", "nice")}
    cited = {line for r in requirements for line in r.line_numbers}
    importance_right = sum(
        any(r.importance == by_line[line] for r in requirements if line in r.line_numbers)
        for line in wanted & cited
    )
    return ExtractionRow(
        case_id=case_id,
        found=len(wanted & cited),
        required=len(wanted),
        cited=len(cited),
        cited_right=len(wanted & cited),
        forbidden_cited=sorted(line for line in cited if by_line.get(line) == "forbidden"),
        importance_right=importance_right,
    )


def extraction_metrics(rows: list[ExtractionRow]) -> dict[str, Ratio]:
    def total(field: str) -> int:
        return sum(getattr(r, field) for r in rows)

    return {
        "lines_found": Ratio(hits=total("found"), total=total("required")),
        "cited_lines_right": Ratio(hits=total("cited_right"), total=total("cited")),
        "importance_right": Ratio(hits=total("importance_right"), total=total("found")),
    }

"""Run the app's own extraction and matching on the labelled cases and score them.

    uv run --env-file ../../.env python -m evals.run matching           # shows cost, runs nothing
    uv run --env-file ../../.env python -m evals.run matching --yes     # runs, billed to your key

Results go to evals/results/<time>-<model>/ (not committed).
"""

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app import extraction, llm, matching
from app.extraction import Requirement
from evals import dataset, score

# Only models whose request settings the app supports (server-side fallbacks included).
MODELS = ("claude-sonnet-5-5", "claude-opus-5-5")  # the first is the default
# Tokens (input, output) per call, measured on the first live runs. Real cases will differ.
TYPICAL_TOKENS = {"matching": (1250, 630), "extraction": (1150, 290)}


def estimate_usd(flow: str, model: str, calls: int) -> float | None:
    price = llm.PRICE_PER_MILLION_TOKENS.get(model)
    if price is None:
        return None
    tokens_in, tokens_out = TYPICAL_TOKENS[flow]
    return calls * (tokens_in * price[0] + tokens_out * price[1]) / 1_000_000


def _requirements(texts: list[str]) -> list[Requirement]:
    return [
        Requirement(position=n, text=t, importance="must", category="skill", line_numbers=[1])
        for n, t in enumerate(texts, start=1)
    ]


def _append(path: Path, row: dict) -> None:
    """Written as each case finishes, so a crash doesn't lose paid-for results."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _attempt(
    out: Path, case_id: str, rep: int, model: str, call: Callable
) -> tuple[object, llm.CallRecord] | None:
    """Run one case. Failures go to errors.jsonl: a broken call is not a wrong answer."""
    try:
        result, record = call()
    except llm.LLMError as exc:
        record, failure = exc.record, str(exc)
    else:
        if record.model == model:
            return result, record
        failure = f"served by {record.model}, not {model}"
    _append(
        out / "errors.jsonl",
        {"case_id": case_id, "rep": rep, "failure": failure}
        | {"call": record.model_dump() if record else None},
    )
    print(f"  {case_id} rep {rep}: FAILED ({failure})")
    return None


def run_matching(client, model: str, reps: int, out: Path, root: Path) -> tuple[list, dict]:
    cases = dataset.matching_cases(root)
    labels = dataset.matching_labels(cases, root)
    rows, calls = [], []
    for rep in range(reps):
        for case in cases:
            done = _attempt(
                out,
                case.id,
                rep,
                model,
                lambda case=case: matching.match_requirements(
                    client, model, _requirements(case.requirements), case.resume, case.as_of
                ),
            )
            if done is None:
                continue
            matches, record = done
            graded = score.grade_matches(case.id, matches, labels)
            _append(
                out / "results.jsonl",
                {"flow": "matching", "case_id": case.id, "rep": rep}
                | {"call": record.model_dump(), "output": [m.model_dump() for m in matches]}
                | {"graded": [g.model_dump() for g in graded]},
            )
            rows += graded
            calls.append(record)
    return calls, {"rows": rows, "metrics": score.matching_metrics(rows)}


def run_extraction(client, model: str, reps: int, out: Path, root: Path) -> tuple[list, dict]:
    cases = dataset.extraction_cases(root)
    labels = dataset.extraction_labels(cases, root)
    rows, calls = [], []
    for rep in range(reps):
        for case in cases:
            done = _attempt(
                out,
                case.id,
                rep,
                model,
                lambda case=case: extraction.extract_requirements(client, model, case.lines),
            )
            if done is None:
                continue
            requirements, record = done
            graded = score.grade_extraction(case.id, requirements, labels)
            _append(
                out / "results.jsonl",
                {"flow": "extraction", "case_id": case.id, "rep": rep}
                | {"call": record.model_dump()}
                | {"output": [r.model_dump() for r in requirements], "graded": graded.model_dump()},
            )
            rows.append(graded)
            calls.append(record)
    return calls, {"rows": rows, "metrics": score.extraction_metrics(rows)}


def summarize(flow: str, model: str, calls: list, graded: dict, planned: int) -> str:
    lines = [f"## {flow} on {model}", "", f"Calls scored: {len(calls)} of {planned}.", ""]
    lines += ["| metric | score | count | 95% interval |", "|---|---|---|---|"]
    for name, ratio in graded["metrics"].items():
        if ratio.value is None:
            lines.append(f"| {name} | n/a | 0 | n/a |")
            continue
        low, high = ratio.interval()
        lines.append(
            f"| {name} | {ratio.value:.0%} | {ratio.hits}/{ratio.total} | {low:.0%} to {high:.0%} |"
        )
    if flow == "matching":
        rows = graded["rows"]
        wrong = [r for r in rows if r.got != r.expected]
        lines += ["", score.confusion(rows), "", f"Disagreements ({len(wrong)}):"]
        lines += [
            f"- {r.case_id} #{r.number}: you said {r.expected}, model said {r.got}" for r in wrong
        ]
    else:
        bad = [(r.case_id, r.forbidden_cited) for r in graded["rows"] if r.forbidden_cited]
        lines += ["", f"Forbidden lines turned into requirements: {bad or 'none'}"]
    costs = [c.cost_usd for c in calls if c.cost_usd is not None]
    if calls:
        seconds = sum(c.duration_ms for c in calls) / len(calls) / 1000
        lines += ["", f"Cost: ${sum(costs):.4f}. Mean time per call: {seconds:.1f} s."]
    return "\n".join(lines) + "\n"


RUNNERS = {"matching": run_matching, "extraction": run_extraction}
LOADERS = {
    "matching": (dataset.matching_cases, dataset.matching_labels),
    "extraction": (dataset.extraction_cases, dataset.extraction_labels),
}


def main(argv: list[str] | None = None, root: Path = dataset.ROOT) -> int:
    parser = argparse.ArgumentParser(description="Evaluate extraction or matching.")
    parser.add_argument("flow", choices=list(RUNNERS))
    parser.add_argument("--model", choices=MODELS, default=MODELS[0])
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--yes", action="store_true", help="make the billed calls")
    args = parser.parse_args(argv)

    load_cases, load_labels = LOADERS[args.flow]
    cases = load_cases(root)
    try:
        load_labels(cases, root)
    except dataset.LabelError as exc:
        print(exc)
        return 2

    planned = len(cases) * args.reps
    cost = estimate_usd(args.flow, args.model, planned)
    price = "unknown cost" if cost is None else f"about ${cost:.2f}"
    print(f"{planned} calls to {args.model} for {args.flow}: {price}, billed to your key.")
    if not args.yes:
        print("Nothing was run. Add --yes to run it.")
        return 0

    out = root / "results" / f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{args.flow}-{args.model}"
    out.mkdir(parents=True)
    calls, graded = RUNNERS[args.flow](llm.get_client(), args.model, args.reps, out, root)
    summary = summarize(args.flow, args.model, calls, graded, planned)
    (out / "summary.md").write_text(summary, encoding="utf-8")
    print(f"\n{summary}\nSaved to {out}")
    return 0 if len(calls) == planned else 1


if __name__ == "__main__":
    sys.exit(main())

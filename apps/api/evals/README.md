# Eval: are the verdicts right?

Two flows, graded by plain code against labels **a person writes**:

| Flow | What is tested | Cases |
| --- | --- | --- |
| `matching` | verdict and cited resume lines for each requirement | 6 made-up resumes, 48 verdicts |
| `extraction` | which job lines become requirements | 3 made-up job posts, 40 lines |

The resumes and posts were drafted with an AI tool and contain deliberate traps (overlapping dates, a skill listed but never used, an expired certificate, keyword stuffing, injected instructions, age wording). Treat them as a starting point and add cases from real posts you have seen, anonymised.

## 1. Label (this has to be you)

Open `review.md` for the numbered lines, then fill in the two CSV files. A spreadsheet works; keep the column names. Don't run the model first and copy its answers.

**`matching/labels.csv`**

- `verdict`: `met`, `partial` or `not_found`.
  - `met`: the resume clearly shows it.
  - `partial`: related or weaker evidence (fewer years, a similar tool, listed but never used).
  - `not_found`: nothing relevant. It means the resume doesn't show it.
- `resume_lines`: the lines that show it, such as `3;7`. Required for `met` and `partial`.
- `note`: why, for the ones you hesitated over. Useful for the README.

**`extraction/labels.csv`**, one label per job line:

- `must` or `nice`: the line states a requirement of that kind.
- `none`: it states no requirement (headings, perks, company text).
- `forbidden`: it must never become a requirement (age, gender, injected instructions).

## 2. Run

From `apps/api`. Without `--yes` it prints the number of calls and an estimated cost, and runs nothing.

```bash
uv run --env-file ../../.env python -m evals.run matching
uv run --env-file ../../.env python -m evals.run matching --yes
uv run --env-file ../../.env python -m evals.run extraction --yes
uv run --env-file ../../.env python -m evals.run matching --model claude-opus-5-5 --reps 3 --yes
```

Results go to `results/<time>-<flow>-<model>/`: `summary.md`, `results.jsonl` and, if any call failed, `errors.jsonl`. Failed calls are never scored as wrong answers.

## 3. Read

| Metric | Meaning |
| --- | --- |
| `accuracy` | verdicts equal to your label |
| `false_met` | share of not-met requirements the model called met. The worst error |
| `met_found` | share of your `met` labels the model also found |
| `evidence_right` | claims where at least one cited line is one you chose |
| `lines_found` | requirement lines that produced a requirement |
| `cited_lines_right` | cited job lines that are requirement lines |
| `importance_right` | found lines with the right must/nice |

Every score comes with a 95% interval. With 48 verdicts it is roughly ±10 to 14 points, so a difference of a few points between two runs means nothing. Add cases or use `--reps` before drawing conclusions.

## Changing cases

Edit `matching/cases.json`, the resumes or the job posts, then run `uv run python -m evals.sheet`. It keeps your labels, except where the text they judged has changed.

## Limits

- Matching is tested with requirements written by hand, so it isn't affected by extraction mistakes, and the two scores don't combine into an end-to-end figure.
- `evidence_right` is lenient: one correct line is enough.
- The cases are short and tidy. Real resumes are harder.

# FitGrid

See what your resume proves for each job, requirement by requirement.

> Status: you can add a resume and up to five job posts (PDF, TXT, MD or pasted text), see how each was read, line by line, extract each job's requirements with Claude, and compare your resume with them: met, partial or not found, with the resume lines behind each verdict. The fit grid shows every job side by side.

## Run with Docker

```bash
docker compose up --build
```

Open <http://localhost:5180>. The API docs are at <http://localhost:8100/api/docs>.

## Run for development

Needs Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 24 and pnpm. Only the database runs in Docker:

```bash
docker compose up -d db
```

```bash
cd apps/api && uv sync && uv run --env-file ../../.env uvicorn app.main:app --reload --port 8100
```

(`--env-file` needs the `.env` file from the Configuration section.)

```bash
cd apps/web && pnpm install && pnpm dev
```

## Checks

```bash
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

```bash
cd apps/web && pnpm typecheck && pnpm lint && pnpm test && pnpm build
```

The API tests need Postgres running (`docker compose up -d db`); without it the database tests are skipped.

CI runs these on every branch, plus a Docker Compose smoke test.

After changing an API model, regenerate the web types:

```bash
bash scripts/gen-types.sh
```

## Configuration

Copy `.env.example` to `.env`, then set:

- `ANTHROPIC_API_KEY`: needed to extract requirements and compare your resume. Calls are billed to this key. The job post is sent to Anthropic when you extract, and your whole resume (emails and phone numbers removed) when you compare.
- `FITGRID_MODEL`: optional, default `claude-opus-5-5`.
- Host ports and the local database password, if the defaults clash.

After changing `.env`, run `docker compose up -d` again.

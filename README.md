# FitGrid

See what your resume proves for each job, requirement by requirement.

> Status: skeleton only. The API, web app and database run and report their health. No product features yet.

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
cd apps/api && uv sync && uv run uvicorn app.main:app --reload --port 8100
```

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

CI runs these on every branch, plus a Docker Compose smoke test.

## Configuration

Copy `.env.example` to `.env` to change host ports or the local database password. `ANTHROPIC_API_KEY` is not used yet.

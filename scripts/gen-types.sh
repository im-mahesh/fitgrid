#!/usr/bin/env bash
# Regenerate apps/web/src/schema.d.ts from the API's OpenAPI schema. No server needed.
# openapi-typescript runs via `pnpm dlx` with TypeScript 5: it does not work with the
# TypeScript 7 the web app uses.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
spec="$(mktemp)"
trap 'rm -f "$spec"' EXIT

(cd "$root/apps/api" && uv run python -c \
  'import json; from app.main import app; print(json.dumps(app.openapi()))') >"$spec"

cd "$root/apps/web"
pnpm --package=openapi-typescript@7.13.0 --package=typescript@5.9.3 \
  dlx openapi-typescript "$spec" -o src/schema.d.ts

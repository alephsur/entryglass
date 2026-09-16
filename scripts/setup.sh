#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for tool in uv node npm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'Missing %s. See README.md for prerequisites.\n' "$tool" >&2
    exit 1
  fi
done

node --input-type=module -e '
const [major, minor] = process.versions.node.split(".").map(Number);
const supported = (major === 22 && minor >= 18) || (major === 24 && minor >= 12) || major > 24;
if (!supported) {
  console.error("Use Node.js 22.18+ (22.x) or 24.12+. Recommended: the version in .nvmrc.");
  process.exit(1);
}
'

if [[ ! -e .env ]]; then
  cp .env.example .env
  chmod 600 .env
  printf 'Created .env from .env.example. No API key is needed yet.\n'
else
  printf 'Keeping your existing .env unchanged.\n'
fi

if [[ -f backend/uv.lock ]]; then
  uv sync --project backend --locked
else
  uv sync --project backend
fi
if [[ -f frontend/package-lock.json ]]; then
  npm --prefix frontend ci
else
  npm --prefix frontend install
fi

printf '\nSetup complete. Run make dev-api and make dev-web in separate terminals.\n'
printf 'Commit backend/uv.lock and frontend/package-lock.json after a successful make check.\n'

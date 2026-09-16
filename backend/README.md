# Entryglass API

Initial FastAPI scaffold. Run commands from the **repository root**, not this folder:

```bash
uv sync --project backend
uv run --project backend uvicorn entryglass.main:app --reload --host 127.0.0.1 --port 8000
```

Only `GET /api/v1/health` is exposed over HTTP. OpenAPI is at `/openapi.json`;
interactive API documentation is at `/docs`. A separate opt-in Nansen validation
command exists, but no provider-backed product endpoint or business analysis occurs.

Configuration is read from the root `.env` when commands are run there. No API key
is needed for ordinary development or tests. Live provider validation requires a
server-side `NANSEN_API_KEY`, `--execute`, and an explicit credit ceiling.

```bash
uv run --project backend pytest backend/tests
uv run --project backend ruff check backend
```

The provider interface and Nansen adapter support contract validation only. See
`docs/PROVIDER_VALIDATION.md` at the repository root before using the command.

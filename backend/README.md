# Entryglass API

Initial FastAPI scaffold. Run commands from the **repository root**, not this folder:

```bash
uv sync --project backend
uv run --project backend uvicorn entryglass.main:app --reload --host 127.0.0.1 --port 8000
```

Only `GET /api/v1/health` is implemented. OpenAPI is at `/openapi.json`; interactive
API documentation is at `/docs`. No Nansen calls or business analysis occur.

Configuration is read from the root `.env` when commands are run there. No API key
is needed. See the root README and roadmap for setup, unverified checks, dependency
locking, and the implementation plan.

```bash
uv run --project backend pytest backend/tests
uv run --project backend ruff check backend
```

`domain/`, `application/`, and the infrastructure adapter directories are reserved
for future code. Do not treat their presence as an implemented feature.

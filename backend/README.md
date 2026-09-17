# Entryglass API

FastAPI local review and private ingestion backend. Run from the **repository root**:

```bash
uv sync --project backend
uv run --project backend uvicorn entryglass.main:app --reload --host 127.0.0.1 --port 8000
```

The API exposes health plus review creation/polling/cancellation, entry replay,
explicit outcome reveal, and evidence reads under `/api/v1/reviews`. OpenAPI is at
`/openapi.json`; interactive documentation is at `/docs`. Review creation requires
the server-side Nansen key and enforces configured request, credit, and entry caps.

Configuration is read from the root `.env` when commands are run there. No API key
is needed for ordinary development or tests. Live provider validation requires a
server-side `NANSEN_API_KEY`, `--execute`, and explicit request/credit ceilings.

```bash
uv run --project backend pytest backend/tests
uv run --project backend ruff check backend
```

The M2-M4 path normalizes wallet entries, obtains strictly pre-entry historical flow,
stores separate later OHLCV observations, records redacted evidence, and preserves
durable job progress. See the root README before starting a credit-consuming review.

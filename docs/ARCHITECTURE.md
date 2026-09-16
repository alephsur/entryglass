# Architecture

## Current implementation

Entryglass is a small monorepo with one FastAPI process and one Vue development
server. The browser calls `/api/v1/health` through the Vite `/api` proxy. The backend
returns process liveness and explicitly reports that Nansen integration is limited
to validation. A separate command can make one opt-in, credit-bounded provider call;
it is not exposed over HTTP. There is no database connection or product API.

```text
Browser -> Vue shell -> Vite /api proxy -> FastAPI health route
Developer -> opt-in validation command -> Nansen API
```

The only extra HTTP surfaces are FastAPI's generated API documentation. A health
response does not verify API credits, provider availability, database access, or
historical-data coverage. These must not be inferred from a green status indicator.

## Planned modular structure

```text
HTTP routes
    -> application use cases
        -> pure domain rules
        -> provider and repository interfaces
            -> Nansen adapter
            -> SQLite / private evidence storage
```

| Directory | Responsibility | Current state |
| --- | --- | --- |
| `api/` | HTTP contracts and request/response mapping | Health only |
| `core/` | Typed server configuration | Implemented |
| `domain/trades/` | Economic entries, normalization, coverage | Reserved |
| `domain/context/` | Bounded pre-entry observations | Reserved |
| `domain/outcomes/` | Later price observations and optional accounting | Reserved |
| `domain/patterns/` | Transparent rule matches and evaluation | Reserved |
| `domain/preflight/` | Comparison with historical precedents | Reserved |
| `application/` | Provider-validation port; future import, audit, replay, and preflight orchestration | Validation port only |
| `infrastructure/nansen/` | Checked request DTOs, one-call HTTP validator, redacted metadata | Validation only |
| `infrastructure/storage/` | Evidence and analysis persistence | Reserved |

Domain code must not import FastAPI, database drivers, or the HTTP client. Provider
responses must be normalized at the boundary, preserving nulls, warnings, source
times, and pagination limits. Do not spread vendor field names across the UI.

## Future contracts, not implemented endpoints

After the validation gate, consider an analysis job resource, paginated entry reads,
one-entry evidence retrieval, and a preflight request. Define their schemas only
once the real data shape is known. Do not add endpoints returning successful fake
reports while the domain is empty.

Each analysis should have a stable identifier, immutable methodology version, input
scope, evidence references, progress, and an explicit complete/partial/failed state.
Use simple bounded background work and polling if necessary. Do not rely on an
in-memory job as durable storage, and do not add Celery or Redis preemptively.

## Data separation

`HistoricalContext` is a function of validated pre-entry inputs. `OutcomeObservation`
is a different object with a later horizon. A report may join both for display,
but the pattern rule's feature input must not include the outcome being assessed.
A UI reveal action controls presentation, not the underlying temporal guarantee.

Evidence files should remain private. Store normalized derived values and hashes
where sufficient; validate provider retention and redistribution terms before
preserving raw responses. Decide deletion and retention policies before hosting.

## Development and release boundaries

The Docker files are for local development, bind host ports to loopback, and do not
constitute a production architecture. Public hosting needs authentication or access
controls for paid analysis, request budgets, rate limiting, appropriate CORS, TLS,
privacy and retention decisions, a compiled frontend, and locked dependencies.

SQLite is a planned choice, not a running service in this scaffold. Add it only
when the first validated ingestion and evidence models exist.

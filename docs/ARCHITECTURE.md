# Architecture

## Current implementation

Entryglass is a small local-first monorepo with one FastAPI process and one Vue
development server. The browser creates and polls bounded review jobs through the
Vite `/api` proxy. FastAPI runs the existing ingestion use case plus independent
historical-context and later-price requests in a local background thread. SQLite is
the source of truth for progress, cancellation, replay, evidence, and current-token
preflight state.

```text
Browser -> Vue review -> Vite /api proxy -> FastAPI review routes
                                      \-> durable review runner
                                          -> wallet ingestion -> Nansen
                                          -> pre-entry context -> Nansen
                                          -> later prices -> Nansen
                                          \-> private SQLite
Browser -> explicit precedents read -> pure versioned rules -> private SQLite
Browser -> explicit token preflight -> one bounded current flow query -> Nansen
                                    \-> durable result/evidence -> private SQLite
Developer -> opt-in validation command -> Nansen API
Developer -> opt-in import command -> ingestion use case -> Nansen / SQLite
```

A health response still does not verify credits, provider availability, database
coverage, or a wallet result. Starting a review or current comparison is an explicit
credit-consuming action and requires the server-side key. Reads never expose the key
or raw payloads.

## Modular structure

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
| `api/` | Job, replay, outcome reveal, evidence, precedents, preflight, and health contracts | M5 implemented |
| `core/` | Typed server configuration | Implemented |
| `domain/trades/` | Economic entry contract, Solana validation, routing normalization | Implemented for wallet entries |
| `domain/evidence/` | Coverage, evidence, and import-job state | Implemented for M2 |
| `domain/context/` | Strict pre-entry windows, coverage, and nullable observations | M3 implemented |
| `domain/outcomes/` | Separate later reference prices, explicitly not realized PnL | M3 implemented |
| `domain/reviews/` | Durable review job and stage state | M4 implemented |
| `domain/patterns/` | Four deterministic flow rules and fixed outcome bands | M5 implemented |
| `domain/preflight/` | Current context and durable comparison job state | M5 implemented |
| `application/` | Validation, ingestion, review, precedents, and preflight use cases | M1-M5 implemented |
| `infrastructure/nansen/` | Typed wallet, historical flow, OHLCV, and current flow adapters | M1-M5 implemented |
| `infrastructure/storage/` | Import/review/preflight jobs, replay, evidence, and page cache | M2-M5 implemented |

Domain code must not import FastAPI, database drivers, or the HTTP client. Provider
responses must be normalized at the boundary, preserving nulls, warnings, source
times, and pagination limits. Do not spread vendor field names across the UI.

## Implemented HTTP boundary

`POST /api/v1/reviews` returns a durable job immediately. Polling, cancellation,
entry listing, one-entry replay, outcome reveal, and evidence reads map persisted
state without in-memory-only results. Creation fails explicitly when the provider is
not configured. Empty, partial, failed, and cancelled jobs remain distinct. No task
queue, Redis service, auth layer, scoring engine, or fake successful report was added.

`GET /api/v1/reviews/{review_id}/precedents` applies the same pure rule set to every
entry in the selected review and returns all groups plus the same-wallet baseline.
`POST /api/v1/reviews/{review_id}/preflights` starts one durable current-context
request; its poll endpoint joins the completed current observation with the already
persisted precedents. The HTTP contract fixes recommendation and risk score to null.

## Data separation

`HistoricalContext` is a function of validated pre-entry inputs. `OutcomeObservation`
is a different object with a later horizon. A report may join both for display,
but the pattern rule's feature input must not include the outcome being assessed.
A UI reveal action controls presentation, not the underlying temporal guarantee.

Evidence files and SQLite databases should remain private. Store normalized derived values and hashes
where sufficient; validate provider retention and redistribution terms before
preserving raw responses. Decide deletion and retention policies before hosting.

## Development and release boundaries

The Docker files are for local development, bind host ports to loopback, and do not
constitute a production architecture. Public hosting needs authentication or access
controls for paid analysis, request budgets, rate limiting, appropriate CORS, TLS,
privacy and retention decisions, a compiled frontend, and locked dependencies.

SQLite is a local adapter, not a network service. The database is owner-readable and
ignored by Git, but it is not encrypted. Public hosting still requires an explicit
retention, deletion, backup, and access-control decision.

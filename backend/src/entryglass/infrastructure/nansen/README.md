# Nansen Adapter

Contains a minimal HTTP client, checked request DTOs, redacted response metadata,
and an opt-in validation command. It is not a product ingestion adapter: it makes at
most one request per invocation, requires `--execute` and a credit ceiling, and does
not retain provider rows. Follow `docs/PROVIDER_VALIDATION.md` and
`docs/NANSEN_INTEGRATION.md` before using it. The normal test suite remains offline
and consumes no provider credits.

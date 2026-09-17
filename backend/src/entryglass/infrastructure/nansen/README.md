# Nansen Adapter

Contains checked request DTOs and separate clients. The validation client makes
at most one request and retains only redacted metadata. The M2 ingestion client maps
typed wallet DEX rows to provider-independent swap legs and applies bounded timeout,
retry, `Retry-After`, concurrency, and credit accounting controls. The M3 client
keeps historical flow and OHLCV requests separate, preserves nulls and warnings,
and records exact periods and response hashes.

Both commands are dry-run by default and require explicit execution and credit
ceilings. Follow `docs/PROVIDER_VALIDATION.md` and `docs/NANSEN_INTEGRATION.md` before
using them. The normal test suite remains offline and consumes no provider credits.

# Nansen Integration Plan

**Status: not implemented. No authenticated requests have been executed for this scaffold.**

This file records the planned integration boundary. The first implementation task
is a budgeted, opt-in schema and data-quality spike, not a full audit engine.

## Candidate sources

| Capability | Provider documentation | Planned use |
| --- | --- | --- |
| Wallet DEX trades | Address DEX Trades [S3] | Import candidate entries and normalize routing |
| Historical flow context | Historical Token Flow Summary [S2] | Bounded pre-entry aggregate context |
| Historical trade evidence | Historical Token Who Bought/Sold [S4] | Confirm sampled or aggregate buy/sell observations |
| Current flow context | Flow Intelligence [S5] | Preflight features with compatible definitions |
| Later prices | Locate and verify current OHLCV documentation during EG-002 | Separate outcome observations |
| Optional PnL | Locate and verify current profiler PnL documentation during EG-002 | Supplementary token-level accounting only |

The inspected schemas use `POST /api/v1/profiler/dex-trades` for wallet trades and
`POST /api/v1beta1/tgm/historical-token-flow-summary` for the beta historical summary.
They do not share a universal route prefix. The wallet endpoint uses a `date`
request field; the historical summary uses `date_range`. Both must be validated
from current provider schemas before a client is written. [S2, S3]

`NANSEN_BASE_URL` is the server origin only. Keep versioned paths in explicit adapter
methods. Do not concatenate all endpoints beneath `/api/v1` by assumption. Keep API
keys server-side; the inspected schemas specify an `apikey` request header. [S2, S3]

## Validation checklist

Confirm account access, nullable fields, sample size, historical coverage, unit and
direction semantics, segment membership, supported precision, pagination, response
warnings, credit charging, and freshness with actual responses. Preserve and
inspect contrary cases. A documented capability is not yet a proven project path.

Define provider DTOs separately from domain objects. Add fixture-based contract
tests, bounded retries, rate-limit handling, cancellation, and a configured budget.
Never retry invalid credentials or schema errors indefinitely. The normal test
suite must use no credentials and incur no charges.

## Evidence envelope to design

Store provider name, full versioned endpoint, redacted request parameters, chain,
token, entry identifier, time window, retrieval time, source timestamps when
actually supplied, request ID, pagination state, warnings, quoted/used credits when
present, response hash, adapter version, and methodology version. Missing metadata
must remain missing; do not invent a source timestamp or coverage percentage.

Deduplicate calls using normalized parameters and declared freshness policy. Keep
cache hits, attempted HTTP requests, successful provider responses, and charged
credits as separate metrics. Never count local API health checks toward contest
usage. There is no traffic-generation or paid-request script in this release.

## Publication and permissions

The provider redistribution guide explicitly distinguishes permitted, restricted,
and prohibited uses. Its September 16, 2026 inspection did not list the beta
historical endpoints or `profiler/dex-trades`. Similar current endpoints do not
grant permission by implication. Keep their validation outputs private and obtain
written clarification for derived displays, screenshots, recordings, retention,
fixtures, and later commercial use before public release. Aggregation alone is not
a blanket permission. [S6]

Use required attribution for approved outputs. Do not commit raw responses, secrets,
or restricted labeled-address lists. Hand-authored synthetic test fixtures must
say they are synthetic and must never be presented as live demonstration data.

The full EG-002 decision, competition requirements, endpoint matrix, and questions
for Nansen are in [COMPETITION_AND_PERMISSIONS.md](COMPETITION_AND_PERMISSIONS.md).

Source references resolve in [SOURCES.md](SOURCES.md).

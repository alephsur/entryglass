# Nansen Integration Plan

**Status: bounded validation plus M2-M5 private review and preflight implemented.**

This file records the integration boundary. A budgeted, opt-in schema validator is
implemented and a private live data-quality spike has completed. M2 adds budgeted
wallet DEX ingestion. M3 adds separate historical-flow and OHLCV adapters, M4
exposes their durable local review through the browser, and M5 adds local descriptive
precedents plus one bounded current Flow Intelligence query.

## Candidate sources

| Capability | Provider documentation | Planned use |
| --- | --- | --- |
| Wallet DEX trades | Address DEX Trades [S3] | Implemented M2 entry import and routing normalization |
| Historical flow context | Historical Token Flow Summary [S2] | Implemented bounded pre-entry aggregate context |
| Historical trade evidence | Historical Token Who Bought/Sold [S4] | Confirm sampled or aggregate buy/sell observations |
| Current flow context | Flow Intelligence [S5] | Preflight features with compatible definitions |
| Later prices | Price OHLCV [S14] | Implemented separate 24-hour/7-day reference observations |
| Optional PnL | Address PnL and Trade Performance [S16] | Supplementary token-level accounting only; never per-entry realized PnL |

The inspected schemas use `POST /api/v1/profiler/dex-trades` for wallet trades and
`POST /api/v1beta1/tgm/historical-token-flow-summary` for the beta historical summary.
They do not share a universal route prefix. The wallet endpoint uses a `date`
request field; the historical summary uses `date_range`. Their public schemas are
represented by the validation adapter. The bounded live spike confirmed access and
the observed wallet-trade envelope; broader coverage remains unproven. [S2, S3]

Later prices use `POST /api/v1/tgm/token-ohlcv` with the current `date` request field
and a one-hour timeframe. The adapter accepts only matching chain/token/timeframe
responses, carries truncation metadata, and the application selects only candles
whose complete interval ends at or before the observation clock. Empty prices,
truncated results, pending horizons, and provider failures remain distinct. [S14]

The documented profiler PnL routes are supplementary wallet/token summaries. They
do not establish realized PnL for an individual entry without a separately defined
and tested lot-accounting method. [S16]

Current comparison uses `POST /api/v1/tgm/flow-intelligence` with only the `solana`
chain, the validated token address, and the `1d` timeframe. The adapter accepts zero
as an observation, preserves null average flow and warnings, and maps an empty result
to unavailable coverage. It permits at most two attempts under the existing bounded
transient-retry policy. The provider documentation listed this request at one credit
when rechecked on September 17, 2026, and states that responses may be cached for 10
to 30 minutes. Entryglass therefore labels retrieval age, not source-event freshness.
[S5, S17]

`NANSEN_BASE_URL` is the server origin only. Versioned paths are kept in explicit
adapter contracts; they are not concatenated beneath `/api/v1` by assumption. API
keys remain server-side; the inspected schemas specify an `apikey` request header.
[S2, S3]

## Validation checklist

Confirm account access, nullable fields, sample size, historical coverage, unit and
direction semantics, segment membership, supported precision, pagination, response
warnings, credit charging, and freshness with actual responses. Preserve and
inspect contrary cases. A documented capability is not yet a proven project path.

Provider request DTOs are separate from domain objects, and synthetic contract tests
run offline. The validation command retains its one-request/no-retry behavior. The M2
importer adds bounded transient retries, `Retry-After`, timeouts, a concurrency limit,
freshness-bounded normalized-page caching, durable cancellation, and separate request
and credit counters. It does not retry contract or permanent provider errors. The
normal test suite uses no credentials and incurs no charges.

## Implemented M2 evidence envelope

The private SQLite record stores provider name, full versioned endpoint, hashed
subject, explicit request window, retrieval time, row source timestamps through the
normalized entries, request ID, pagination state, warnings, quoted/used credits,
response hash, adapter version, methodology version, and source-schema version.
Missing metadata remains missing.

Wallet calls are deduplicated by normalized request fingerprint and a declared cache TTL. Keep
cache hits, attempted HTTP requests, successful provider responses, and charged
credits as separate metrics. Never count local API health checks toward contest
usage. The importer requires explicit public inputs, `--execute`, and request/credit
ceilings. A browser review is also explicit and applies server-configured ceilings;
neither path is a traffic-generation script.

## M3/M4 historical evidence envelope

The context query ends one second before an entry because the historical endpoint's
upper date bound is inclusive. It requests only the token and declared 24-hour
window, uses the provider's temporally resolved Smart Trader fields, and does not
claim DEX selling. OHLCV calls occur only in the separate outcome path. Both store
endpoint, hashed subject, exact period, retrieval time, request ID when present,
warnings, credit metadata, response hash, adapter version, and methodology version.
Raw provider payloads and API keys are never returned by the review API.

## M5 current evidence envelope

A preflight is created only by an explicit browser action after a completed local
review. Its job and normalized observation persist in SQLite. Evidence records the
exact endpoint, rolling one-day request period, retrieval time, request ID when
present, warnings, attempt count, and quoted/used credits. The browser receives the
normalized metrics and evidence metadata, never the key or raw response. Precedent
aggregation itself is local and spends no provider credits.

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

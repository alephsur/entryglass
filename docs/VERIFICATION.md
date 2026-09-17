# Scaffold Verification Report

**Prepared:** September 15, 2026  
**Updated:** September 17, 2026
**Scope:** Entryglass 0.1.0 through M5 personal precedents and preflight

This report separates executed checks from unverified product behavior. It records
the EG-001 local scaffold workflow, the offline validator, the bounded private EG-003
feasibility spike, offline M2 ingestion, M3 temporal evidence, the M4 browser
journey, and offline M5 precedent/preflight verification. No M4 or M5 verification
call contacted Nansen.

## EG-001 checks executed successfully

| Check | Result |
| --- | --- |
| Locked dependency setup | `make setup` completed with `uv sync --locked` and `npm ci` |
| Backend pytest suite | 10 tests passed |
| Frontend HTTP-client tests | 6 tests passed using Node's built-in test runner |
| Python quality checks | Ruff lint passed; 26 files passed the format check |
| Frontend static checks | Vue and TypeScript type checking passed |
| Frontend production build | Vite built 14 transformed modules successfully |
| Browser smoke test, backend online | The shell displayed `Entryglass API is online / 0.1.0` |
| Browser smoke test, backend offline | The shell displayed `API unavailable` and no wallet report |
| Browser recovery test | The shell returned to the online state after the backend restarted |

The browser smoke test used temporary loopback ports because unrelated local
processes already occupied ports 8000 and 5173. The frontend proxy still exercised
the real `/api/v1/health` contract. The screen continued to identify itself as an
initial scaffold, stated that data integration is not implemented, and displayed no
wallet analysis in either state.

No Nansen request was made, no credential was required, and no API credit was used.

## M1 offline provider-validator checks executed successfully

The September 16 follow-up added checked public request contracts for wallet DEX
trades, historical token flow, and historical who-bought/sold. The ordinary suite
now contains 24 backend tests and 6 frontend tests. It verifies UTC window rules,
exact Smart Trader label mapping, redacted metadata, safe provider errors, dry-run
behavior, the explicit execution and credit gates, and the missing-key failure path.

The full `make check` passed after these changes: all 24 backend and 6 frontend tests,
Ruff lint and formatting for 33 Python files, Vue/TypeScript type checking, and the
Vite production build. A dry run printed a redacted one-request plan. Attempting
execution without a local `NANSEN_API_KEY` stopped before networking with a clear
configuration error. No provider call was sent and no credit was consumed.

At that stage, the health contract and UI described Nansen integration as
`validation_only`. M2 later changed this to `private_ingestion_only`; the browser
still does not query Nansen or expose an analysis feature.

## EG-003 private live validation

The authorized Solana wallet required expanding discovery beyond the planned 90-day
window to obtain three genuine quote-asset-to-token entries. All three were retained
without selecting on outcome. Each received a strictly pre-entry 24-hour historical
flow query ending one second before the trade and separate 1-hour OHLCV observations
for the 24-hour and 7-day horizons.

The live calls used 27 credits in total and left 62 available at the end of the
spike. All requested routes returned HTTP 200. Provider rows, wallet history, token
addresses, transaction hashes, request IDs, and measurements remain under ignored
`data/eg003/` with private file permissions. Only aggregate validation facts appear
in tracked documentation.

All three samples had observed zero Smart Trader net flow, a null Smart Trader
average-flow field, and mixed later price directions. One flow response included a
provider warning. The exact-label who-bought/sold check returned a valid empty page.
These are distinct states and are not converted into a positive or negative signal.

Pure domain tests now enforce the strict cutoff, Decimal entry prices, null versus
observed-zero context, pending versus missing outcomes, and the separation of later
price change from realized PnL. Hand-authored synthetic fixtures cover the observed
wallet-trade, historical-flow, and OHLCV envelope shapes.

After the EG-003 contracts were added, the full `make check` passed with 33 backend
tests, 6 frontend tests, Ruff lint and formatting for 38 Python files, Vue/TypeScript
type checking, and the Vite production build. The two previously noted dependency
deprecation warnings remain non-failing.

## M2 ingestion and persistence checks

On September 17, the complete `make check` passed with 53 backend tests, one explicitly
opt-in live test skipped, 6 frontend tests, Ruff lint and formatting for 51 Python
files, Vue/TypeScript type checking, and the Vite production build. The ordinary
tests use synthetic rows and mock transports; they do not contact Nansen or consume
credits.

The M2 tests verify case-preserving 32-byte Solana address validation, Decimal and
UTC normalization, direct and routed swaps, duplicate-leg removal, exclusion of exits
and quote-only activity, and explicit ambiguity for multiple outputs. Typed provider
tests cover pagination, redacted evidence, transient retry, bounded `Retry-After`,
schema failure, timeouts through the configured HTTP transport, and credit metadata.

SQLite tests apply the versioned migration to a temporary private database and verify
paginated jobs, progress, immutable evidence, cached re-imports, idempotent entries,
separate request/credit counters, explicit truncation, budget exhaustion, provider
failure, no activity, non-entry activity, ambiguous activity, cancellation, and
recoverable partial entries. A second import of the same scope made zero provider
calls through the normalized-page cache and did not duplicate the entry.

The real `make import-wallet` command was run in dry-run mode. It printed only hashed
wallet/quote subjects and the declared window and budgets. It did not open SQLite,
send a request, require a credential, or consume a credit. Live M2 execution was not
performed because the existing EG-003 evidence already validated the row contract
and ordinary development must not spend credits.

## M3 context and outcome checks

Offline typed-adapter tests verify the exact beta historical-flow route, inclusive
upper-bound cutoff one second before the entry, preservation of observed zero versus
null, warnings, request IDs, credit metadata, and explicit unavailable coverage. The
OHLCV adapter uses the supported `date` field, rejects mismatched chain/token/timeframe
responses, records truncation, and never feeds price rows into historical context.

Application tests run the complete import/context/outcome workflow against synthetic
providers and a temporary migrated SQLite database. They prove that changing only
post-entry prices changes the outcome but cannot change the pre-entry context. They
also verify separate 24-hour and 7-day observations, closed-candle selection, Decimal
price changes, persisted evidence, and durable request/credit accounting.

## M4 review and browser checks

On September 17, the backend suite passed **62 tests** with one opt-in live test
skipped. The frontend client suite passed **9 tests**. Ruff lint and formatting,
Vue/TypeScript checking, and the Vite production build passed. Playwright ran three
journeys in both desktop Chromium and Pixel 5 emulation (**6 browser tests**):

- wallet scope to entry replay, with the later result absent before the reveal action;
- explicit server-provider configuration failure without a fake review; and
- a completed empty scope distinguished from an error or zero-signal result.

The happy-path browser journey also verifies entry selection, context period and
coverage, outcome reveal, evidence drawer contents, Escape-to-close behavior, and
focusable controls. Manual browser inspection confirmed the running local health
contract and responsive layout. All browser provider responses were test-only route
interceptions; no credential was loaded and no provider credit was used.

## M5 precedent and preflight checks

On September 17, the backend suite passed **70 tests** with one opt-in live test
skipped. The frontend client suite passed **11 tests**. Ruff lint and formatting,
Vue/TypeScript checking, and the Vite production build passed. The same six desktop
and mobile Chromium journeys passed; the happy path now additionally verifies the
explicit personal-precedent reveal, the declared net-outflow group, a completed
current-token comparison, its matching sample count, and the absence of a
recommendation or risk score.

Pure domain tests exhaust the four mutually exclusive observed flow rules, keep
missing input separate, and pin the flat outcome band to +/-2%. Application tests
verify the same-wallet baseline, all visible rule groups, and the rule that a missing
current feature cannot silently become a non-match. Adapter tests cover the exact
Flow Intelligence endpoint and one-day request, observed zero, null preservation,
and an empty result mapped to unavailable. SQLite tests verify durable preflight
state and evidence. All provider behavior used synthetic transports or intercepted
browser responses and consumed no credits.

## Environment used for EG-001

- Host Python 3.14.4; the locked backend environment used Python 3.12.13
- uv 0.11.6
- Node.js 24.14.0
- npm 11.9.0
- pytest 9.1.1
- Vite 7.3.6

The test run reported two dependency deprecation warnings from the FastAPI/Starlette
test-client stack. They did not fail the suite and do not affect the scaffold health
contract, but dependency updates should recheck them.

## Still not verified

- Docker image builds, container startup, or reload. `docker compose config --quiet`
  passed on September 17 with Docker 29.5.0 and Compose 5.1.0.
- A clean-checkout or GitHub Actions execution. Both lockfiles are tracked in the
  current Git repository, but CI was not run from this environment.
- A non-empty historical who-bought/sold row and its live field types. The checked
  request returned an empty final page. Wider provider access and coverage remain
  unproven beyond the bounded sample. Publication of planned historical outputs
  still needs written provider clarification.
- Live execution of the M2 multi-page import against Nansen. Its adapter is based on
  the live-validated EG-003 wallet row envelope and is otherwise covered offline.
- A live end-to-end M4 review against Nansen after these code changes. The earlier
  bounded EG-003 spike validates the observed contracts, while the M4 execution path
  is verified offline to avoid unapproved credit use.
- A live end-to-end M5 current-token preflight against Nansen after these code
  changes. The request contract is checked against current documentation and covered
  offline to avoid unapproved credit use. Trading remains deliberately unimplemented.

## Original archive preparation

The September 15 archive preparation ran the 10 backend tests and 6 isolated
frontend client tests, plus syntax, configuration, link, and archive-integrity
checks. Registry access and Docker were unavailable in that environment, so the
full installation and browser workflow were correctly left unverified until this
EG-001 update.

The remaining foundation check is to build and start the Docker environment from a
clean checkout. The next product milestone is M6 submission hardening.

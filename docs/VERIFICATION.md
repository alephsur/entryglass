# Scaffold Verification Report

**Prepared:** September 15, 2026  
**Updated:** September 16, 2026  
**Scope:** Entryglass 0.1.0 scaffold and offline provider-contract validator

This report separates executed checks from unverified product behavior. It records
the EG-001 local scaffold workflow, the offline validator, and the bounded private
EG-003 feasibility spike. It does not certify a provider-backed product feature.

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

The health contract and UI now describe Nansen integration as `validation_only`.
This means a separate developer command exists; the browser still does not query
Nansen or expose an analysis feature.

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

- Docker Compose schema validation, image builds, container startup, or reload.
- A clean Git checkout or GitHub Actions execution. This extracted workspace has no
  `.git` metadata, so the presence of the lockfiles is verified but their commit
  status cannot be checked here.
- A non-empty historical who-bought/sold row and its live field types. The checked
  request returned an empty final page. Wider provider access and coverage remain
  unproven beyond the bounded sample. Publication of planned historical outputs
  still needs written provider clarification.
- Any audit, replay, pattern engine, preflight result, database, or trading behavior;
  these features remain deliberately unimplemented.

## Original archive preparation

The September 15 archive preparation ran the 10 backend tests and 6 isolated
frontend client tests, plus syntax, configuration, link, and archive-integrity
checks. Registry access and Docker were unavailable in that environment, so the
full installation and browser workflow were correctly left unverified until this
EG-001 update.

The next foundation checks are to commit both lockfiles in the real Git repository,
then run `docker compose config` and start the Docker environment from a clean
checkout. Provider results should not be interpreted until the authenticated
validation tasks and EG-003 data-quality gate are complete.

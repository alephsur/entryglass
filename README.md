# Entryglass

**Look back. Enter with context.**

Entryglass is a research tool under development for reviewing a wallet's DEX entries against
historical market context, then comparing a possible new entry with those precedents.
The name combines an entry with a lens for examining it. It is a working project
name, not a claim of trademark or domain availability.

> **Release 0.1.0 implements the local journey through M5.**
> A local user can review a bounded public-wallet scope, inspect strictly pre-entry
> historical flow context, explicitly reveal separate later price observations, and
> inspect evidence metadata. The user can then explicitly explore four versioned,
> descriptive personal-precedent rules and compare a token's current one-day flow
> with compatible precedents. No probability, risk score, recommendation, trading,
> or simulated investment result is produced. Provider evidence remains private to
> the local application.

## Start here

Read [ROADMAP.md](ROADMAP.md) for the implementation sequence and acceptance criteria.
Read [docs/VERIFICATION.md](docs/VERIFICATION.md) for exactly what was tested when
this archive was prepared and during local verification. Read
[docs/COMPETITION_AND_PERMISSIONS.md](docs/COMPETITION_AND_PERMISSIONS.md) before
using or publishing provider data. The checked provider contracts and safe validation
workflow are in [docs/PROVIDER_VALIDATION.md](docs/PROVIDER_VALIDATION.md).

All authored documentation, source comments, and interface copy are in English.

## What is included

| Area | Current contents |
| --- | --- |
| Backend | FastAPI review jobs, replay, precedents, current-token preflight, typed settings and health |
| Frontend | Vue review journey, hidden outcomes, evidence, descriptive patterns and comparison |
| Domain | Entry normalization, temporal separation, four versioned flow rules and explicit missing states |
| Infrastructure | Bounded Nansen adapters, durable review/preflight jobs, private cache and evidence |
| Development | Locked local setup, Make commands, safe setup script, development Docker configuration |
| Quality | 70 passing backend tests, 11 frontend tests, 6 Chromium journeys, static checks and build |
| Planning | Roadmap, architecture, methodology, integration notes, agent instructions |

## Option A: local development

Prerequisites: Python 3.12 or 3.13, `uv`, Node.js 24.12+ (24.x recommended), `npm`,
and `make`. Node 22.18+ within 22.x is also accepted. The `.python-version` and
`.nvmrc` files specify the recommended development versions. Dependency installation
requires Internet access. Tool installation references are in
[docs/SOURCES.md](docs/SOURCES.md).

From the extracted repository root:

```bash
make setup
```

The setup script preserves an existing `.env`, installs dependencies, and generates
`backend/uv.lock` and `frontend/package-lock.json` when they are absent. No Nansen
key is needed. A supported Python version must be available or installable by uv.

Start the backend in one terminal:

```bash
make dev-api
```

Start the frontend in another terminal, also from the repository root:

```bash
make dev-web
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.
The health endpoint is `http://localhost:8000/api/v1/health`.

Without `NANSEN_API_KEY`, the interface and health check still load, but starting a
review returns an explicit configuration message and spends no credits. To test a
live review, set the key only in the root `.env`, restart the backend, paste a public
Solana wallet, review the visible date range and entry limit, and select **Review
wallet**. The default server ceiling is 5 entries, 15 requests, and 32 credits.
After the review completes, **Explore personal precedents** reads only local review
data. **Run current comparison** makes one bounded current Flow Intelligence query
for the supplied token and shows its timestamp, freshness, matches, differences,
missing features, and limitations.

**Do not open `frontend/index.html` using `file://`.** This is a Vite project and
must be served through its development server. Browser API requests use `/api`
and the Vite proxy forwards them to the backend.

Equivalent commands without Make are:

```bash
bash scripts/setup.sh
uv run --project backend uvicorn entryglass.main:app --reload --host 127.0.0.1 --port 8000
# In a separate terminal:
npm --prefix frontend run dev
```

## Option B: Docker development

Prerequisites: Docker Engine and the Docker Compose v2 plugin, with Internet access
for image and dependency downloads. No host Python or Node installation is required.

```bash
cp .env.example .env
# Keep an existing .env instead of overwriting it.
docker compose up --build
```

Open `http://localhost:5173`. Both published ports bind to loopback only. Source
files are mounted for development reload; rebuild after changing dependencies.
This is not a production deployment configuration. Docker execution was not
available in the archive-generation environment; see the verification report.

```bash
docker compose down
```

## Check the workspace

After local setup:

```bash
make test
make check
make browser-test
```

`make check` runs tests, Python lint and formatting checks, frontend type checking,
and the frontend production build. `make browser-test` runs the happy path plus
provider-configuration and empty-scope paths in desktop and mobile Chromium. These
checks use synthetic intercepted responses, do not contact Nansen, and never spend
credits. See `docs/VERIFICATION.md`.

To format Python files:

```bash
make format
```

The provider validator and wallet importer are offline by default and print redacted plans.
Live execution additionally requires `--execute`, an explicit credit ceiling, a
server-side key, and owner-approved public inputs. See
[docs/PROVIDER_VALIDATION.md](docs/PROVIDER_VALIDATION.md).

The M2 importer requires explicit wallet scope, quote identities, and request/credit
ceilings. This dry run creates no database and sends no request:

```bash
make import-wallet ARGS='run \
  --address PUBLIC_SOLANA_WALLET \
  --from 2026-06-01T00:00:00Z \
  --to 2026-06-30T00:00:00Z \
  --quote SOLANA_QUOTE_MINT=SYMBOL \
  --max-requests 5 --max-credits 5'
```

Add `--execute` only after reviewing the plan. Results go to the ignored private
SQLite path configured by `ENTRYGLASS_DATABASE_PATH`. On execution the command emits
the job ID immediately; the `status` and `cancel` subcommands accept that ID while
the import is running. The same bounded ingestion path is used by a review started
in the browser when the server-side key is configured.

## Dependency reproducibility

`backend/uv.lock` and `frontend/package-lock.json` are present. On September 16,
2026, `make setup` successfully used `uv sync --locked` and `npm ci`, and the full
`make check` completed. Both lockfiles are tracked in the Git repository. M4 adds
Playwright as a locked development dependency for offline desktop/mobile browser
journeys; backend runtime dependencies remain unchanged.

The declared version ranges remain the compatibility policy, and future dependency
updates still require a fresh verification run. The backend Docker scaffold installs
from `pyproject.toml`, not the uv lock; converting it to a locked build is an explicit
roadmap task before public release.

## Repository map

```text
entryglass/
  README.md
  ROADMAP.md
  AGENTS.md
  .env.example
  compose.yaml
  Makefile
  backend/
    pyproject.toml
    src/entryglass/
      api/routes/{health,reviews,precedents}.py
      core/config.py
      domain/{trades,evidence,context,outcomes,reviews,patterns,preflight}/
      application/{provider,ingestion,reviews,precedents,preflight}.py
      infrastructure/{nansen,storage}/
    tests/{api,unit,integration}/
  frontend/
    src/{components,features,lib}/
    tests/
  docs/
    ARCHITECTURE.md
    COMPETITION_AND_PERMISSIONS.md
    METHODOLOGY.md
    NANSEN_INTEGRATION.md
    PROVIDER_VALIDATION.md
    SOURCES.md
    VERIFICATION.md
  scripts/setup.sh
  data/
  artifacts/
  .github/workflows/ci.yml
```

Braces in this map abbreviate separate directories. Folder notes distinguish
reserved modules from implemented code.

## Configuration and privacy

Copy `.env.example` to `.env` at the repository root. `NANSEN_API_KEY` is used only
by explicit backend validation/import commands. Never put it in `frontend/`, a `VITE_`
environment variable, logs, screenshots, or the public repository.
The frontend container does not receive the backend `.env` file.

`data/` and `artifacts/` are private local workspaces, excluded from Git except for
their README files. They are not encrypted storage. No telemetry or third-party
analytics is installed. No wallet signature, seed phrase, or private key is needed.
The SQLite repository creates its database with owner-only permissions, but users
must still protect backups and the surrounding filesystem.

## Product boundaries

The implemented journey distinguishes transfers from verified trades, historical
context from future outcomes, and price changes from realized PnL. Personal
precedents show all four declared groups and a same-wallet baseline. The current
comparison displays missingness and limitations rather than inventing a reassuring
score or action.
See [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

Do not represent this incomplete product as an investment recommendation service or an
operational contest submission. Public-source review did not establish redistribution
permission for the planned historical endpoints, so written provider clarification
is still required before publishing their outputs. Also select a repository license
and recheck the current competition terms. No license has been selected on the
owner's behalf.

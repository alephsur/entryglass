# Entryglass

**Look back. Enter with context.**

Entryglass is a planned research tool for reviewing a wallet's DEX entries against
historical market context, then comparing a possible new entry with those precedents.
The name combines an entry with a lens for examining it. It is a working project
name, not a claim of trademark or domain availability.

> **Release 0.1.0 is an initial scaffold, not the product.**
> Only the API health endpoint, a development landing screen, and an opt-in provider
> contract-validation command are implemented. No wallet audit, historical
> calculation, pattern engine, database, trading operation, or simulated investment
> result is implemented. A private, bounded EG-003 validation spike has been run;
> its evidence is not part of the repository or exposed by the application.

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
| Backend | FastAPI app factory, typed settings, health route, CORS, provider-validation contracts |
| Frontend | Vue 3 + TypeScript + Vite shell, local API status, 6 HTTP-client tests |
| Domain | Validated entry, pre-entry window, and outcome contracts; patterns and preflight remain reserved |
| Infrastructure | Opt-in Nansen contract validator; SQLite remains reserved |
| Development | Locked local setup, Make commands, safe setup script, development Docker configuration |
| Quality | pytest, Ruff configuration, TypeScript checks, Node test runner, CI workflow |
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

## Check the scaffold

After local setup:

```bash
make test
make check
```

`make check` runs tests, Python lint and formatting checks, frontend type checking,
and the frontend production build. It does not contact Nansen. Frontend tests use
Node's built-in test runner; no browser or test framework package is required for
the current API-client tests. The Vue shell has also been smoke-tested against a
running backend and with the backend unavailable; see `docs/VERIFICATION.md`.

To format Python files:

```bash
make format
```

The provider validator is offline by default and prints a redacted request plan.
Live execution additionally requires `--execute`, an explicit credit ceiling, a
server-side key, and owner-approved public inputs. See
[docs/PROVIDER_VALIDATION.md](docs/PROVIDER_VALIDATION.md).

## Dependency reproducibility

`backend/uv.lock` and `frontend/package-lock.json` are present. On September 16,
2026, `make setup` successfully used `uv sync --locked` and `npm ci`, and the full
`make check` completed. Commit both lockfiles when this source tree is placed in its
Git repository; this extracted workspace does not include Git metadata.

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
      api/routes/health.py
      core/config.py
      domain/{trades,context,outcomes,patterns,preflight}/
      application/
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
by explicit backend validation commands. Never put it in `frontend/`, a `VITE_`
environment variable, logs, screenshots, or the public repository.
The frontend container does not receive the backend `.env` file.

`data/` and `artifacts/` are private local workspaces, excluded from Git except for
their README files. They are not encrypted storage. No telemetry or third-party
analytics is installed. No wallet signature, seed phrase, or private key is needed.

## Product boundaries

The planned product will distinguish transfers from verified trades, historical
context from future outcomes, and price changes from realized PnL. It will display
coverage and missing-data states rather than inventing a reassuring score.
See [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

Do not represent this scaffold as an investment recommendation service or an
operational contest submission. Public-source review did not establish redistribution
permission for the planned historical endpoints, so written provider clarification
is still required before publishing their outputs. Also select a repository license
and recheck the current competition terms. No license has been selected on the
owner's behalf.

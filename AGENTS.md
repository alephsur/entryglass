# Working on Entryglass

## Read first

Read `README.md`, `ROADMAP.md`, `docs/ARCHITECTURE.md`,
`docs/METHODOLOGY.md`, and `docs/NANSEN_INTEGRATION.md` before editing.
The repository is an initial scaffold. Reserved directories are not implemented
features. The next task is EG-001, then the provider-validation gate EG-002/EG-003.

## Language and scope

Use English for code, comments, tests, documentation, UI copy, and commit messages.
Keep FastAPI + Vue + TypeScript and a single-chain, local-first approach. Do not add
microservices, Kubernetes, agent frameworks, auth, trading, or ML infrastructure
without a separate product decision.

## Engineering rules

Keep pure domain rules independent of HTTP, storage, and framework code. Add provider
DTOs only after checking the actual schema. Keep external requests in the Nansen
adapter, with opt-in integration tests. A normal test run must not spend credits.
Use UTC-aware timestamps and Decimal for financial arithmetic in future models.
Do not fabricate API responses, datasets, test results, or lockfiles.

Keep configuration server-side. Never expose NANSEN_API_KEY to the browser or add a
VITE-prefixed secret. Do not log tokens, full authorization headers, wallet histories,
or provider payloads. Do not publish restricted labeled-wallet data.

## Methodology rules

Pre-entry context and later outcomes must be separate objects and processing paths.
Never infer a DEX sale from a token outflow alone. Never describe a later price change
as the user's realized PnL without correct accounting. Missing data, no signal,
provider failure, and pending outcomes are separate states. Current cohorts are
not a substitute for validated historical labels.

Do not implement an "exit liquidity" verdict or probability score just because it
makes an attractive demo. Preserve contrary examples and small-sample limitations.
Do not let an LLM create measurements or decide evidence labels.

## Completion

Run `make test` and `make check` when the relevant dependencies are available.
Record any checks that could not run and why. Update roadmap items only after their
acceptance criteria are met. Keep README claims aligned with implemented features.
Make small, reviewable changes and add tests with each product slice.

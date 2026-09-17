# Entryglass Roadmap

**Baseline:** 2026-09-15  
**Current state:** M5 personal precedents and preflight completed

**Next task:** Begin M6 submission hardening

**Delivery approach:** One developer, one chain, one complete user journey

This is an implementation plan, not a claim that features already exist. Checked
items describe delivered files or verified behavior. Unchecked items remain work.
All implementation, documentation, UI copy, and submission material must be English.

## 1. Product objective

Help someone answer three questions:

1. What market context preceded my entry?
2. Which clearly defined conditions recur across my historical entries?
3. Does a token I am considering share those conditions now?

The differentiator is the sequence **entry -> historical replay -> personal
precedents -> preflight comparison**, with inspectable evidence throughout.
The product is not an autonomous trader, a copy-trading agent, a price predictor,
or a claim that another wallet directly sold to the user.

## 2. Scope for the first working release

| Decision | Target |
| --- | --- |
| Chain | Solana only; Base is a stretch goal after the core journey passes |
| Input | A public wallet address; no wallet connection or signature |
| History | A declared 90-day window, initially capped at 30 normalized entries |
| Main context | Historical Smart Trader segment evidence, subject to coverage |
| Lookback | Start with a 24-hour pre-entry window and explicit UTC cutoffs |
| Outcomes | Separate 24-hour and 7-day price observations |
| Patterns | Three or four predefined, deterministic, inspectable rules |
| Preflight | Compare current context with historical precedents, not a buy/sell order |
| Persistence | SQLite and private evidence files after provider validation |
| UX | Progressive loading, replay, evidence drawer, optional private share card |

Do not add multichain ingestion, auth, subscriptions, order execution, model
training, graph infrastructure, or an LLM dependency to the critical path.

## 3. Milestones and acceptance criteria

### M0 - Repository foundation

**Status:** Structure, lockfiles, local toolchain, and Compose config verified;
clean-checkout Docker startup remains.

- [x] Create the Entryglass backend/frontend monorepo.
- [x] Add FastAPI health, typed configuration, and a Vue development shell.
- [x] Reserve domain and adapter boundaries without implementing product logic.
- [x] Add safe environment examples, local commands, Docker files, and CI config.
- [x] Provide architecture, methodology, integration notes, and this roadmap.
- [x] Run 10 backend tests and 6 frontend HTTP-client tests in the available runtime.
- [x] **EG-001:** Bootstrap on the owner's machine, run `make check`, and smoke-test the UI.
- [x] Commit `backend/uv.lock` and `frontend/package-lock.json` after verification.
- [ ] Run `docker compose config` and start the Docker environment from a clean checkout.

**Acceptance:** The shell correctly reports API availability, does not claim
analytics readiness, and starts without credentials. Installation failures must
be fixed before interpreting any provider results. See `docs/VERIFICATION.md`.

### M1 - Provider feasibility and permissions gate

**Target:** September 15-16. **Priority:** P0. **Depends on:** M0.

- [x] **EG-002:** Verify the current competition cutoff, eligibility, submission
      form, repository requirements, video constraints, and provider permissions.
- [x] Confirm account access, live credit headers, exact route versions, request
      filters, pagination envelopes, null behavior, trade timestamp precision, and
      OHLCV resolution from bounded live responses.
- [ ] Observe a non-empty historical who-bought/sold row and verify its row field
      types. The authorized sample returned a valid empty page.
- [x] Define the exact segment mapping. Do not assume `smart_money`, `Smart Trader`,
      and every legacy label are interchangeable.
- [x] Add a small server-side provider interface and an opt-in validation command.
      Never call paid endpoints at startup or in the ordinary test suite.
- [x] **EG-003:** Validate at least three real historical entries, including an
      uninformative or contrary case, not only a striking loss.
- [x] For each, retrieve the entry, pre-entry context, and available later prices.
      Confirm any selling claim using actual buy/sell evidence or remove the claim.
- [x] Record latency, credits, request IDs, parameters, data availability, and
      timestamp limitations privately in `data/`.
- [x] Create hand-authored synthetic contract fixtures; do not publish raw private
      responses or restricted labeled-wallet lists.

**Go/no-go gate:** Continue only if a reviewer can inspect a real entry, understand
its historical window, and verify the result without pretending missing data exists.
If sales cannot be established, ship flow context only. If historical cohort
context cannot be validated, reduce the product to an explicitly limited replay;
do not relabel current cohorts as historical evidence.

### M2 - Ingestion, contracts, and evidence storage

**Status:** Completed September 17. **Priority:** P0. **Depends on:** M1 passing.

- [x] Define `TradeEntry`, `HistoricalContext`, `OutcomeObservation`,
      `EvidenceRecord`, and explicit coverage/error states.
- [x] Validate Solana addresses without modifying case and reject unsupported chains.
- [x] Implement paginated import with a request budget and explicit truncation.
- [x] Normalize decimals, UTC timestamps, quote assets, and token identities.
- [x] Group routed swaps and duplicate legs into economic entries where supported;
      mark ambiguous cases instead of guessing or double-counting.
- [x] Exclude transfers, airdrops, and intermediate routing tokens from entry counts.
- [x] Add SQLite repositories and migrations only for the models now required.
- [x] Persist immutable evidence references, parameters, observation times,
      source/schema versions, and redacted response hashes.
- [x] Add bounded retries for transient failures, `Retry-After` handling, timeouts,
      concurrency limits, deduplication, and separate request/credit accounting.
- [x] Add a budgeted job flow with progress, cancellation, and a recoverable result.

**Acceptance:** Re-importing the same window does not duplicate entries. An
incomplete page or provider error never appears as zero activity. No credentials
or raw labeled lists appear in logs or public fixtures.

### M3 - Historical context and separated outcomes

**Status:** Completed September 17. **Priority:** P0. **Depends on:** M2.

- [x] Enforce a strictly pre-entry evidence boundary, including inclusive API bounds,
      bucket edges, timestamp precision, and same-transaction contamination.
- [x] Use temporal labels where supported and record reconstruction limitations.
- [x] Normalize segment direction and define which comparisons are valid.
- [x] Keep token-flow observations separate from verified DEX buy/sell evidence.
- [x] Keep buy/sell claims out of M3 because this path uses aggregate token flow
      only. Any future buy/sell path must query both sides, deduplicate, and expose
      filters, pagination, and partial-sample limits.
- [x] Preserve missing values, source warnings, incomplete buckets, and freshness.
- [x] Compute later price observations separately; never pass them into context rules.
- [x] Distinguish horizon pending, missing price, unsupported coverage, and an
      observed zero return. Do not use an unfinished candle as a completed result.
- [x] Keep token-level provider PnL separate from per-entry outcomes; do not attribute
      a realized loss to an individual buy without an explicit lot-accounting method.

**Acceptance:** Tests prove that adding or changing post-entry data cannot change
pre-entry features. Reports can show buying alongside the segment followed by a
loss, or buying against the segment followed by a gain. They do not force a story.

### M4 - The complete review and replay journey

**Status:** Completed September 17. **Priority:** P0. **Depends on:** M3.

- [x] Implement wallet input, visible scope, and progress without silent fake results.
- [x] Add entry list with coverage indicators and clear selection semantics.
- [x] Build a replay view that initially hides the later outcome.
- [x] Add an explicit reveal action for the subsequent price observation.
- [x] Add an evidence drawer with period, source, parameters, coverage, and rule version.
- [x] Handle empty wallets, invalid input, timeouts, low credits, partial analyses,
      unavailable provider data, and expired cache entries.
- [x] Add keyboard navigation, focus states, responsive layout, and browser tests.

**Acceptance:** A user can move from one public wallet to one understandable entry
and inspect its evidence. Slow calls show progress, not a fabricated instant report.
The happy path and at least two failure paths are reproducible.

### M5 - Personal precedents and preflight

**Status:** Completed September 17. **Priority:** P0. **Depends on:** M4.

- [x] Specify three or four rules before evaluating the demonstration wallet.
- [x] Show matching winning, losing, and flat observations with sample counts,
      coverage, and an appropriate same-wallet comparison baseline.
- [x] Separate exploratory patterns from chronological held-out evaluation.
      Purge overlapping outcome horizons when evaluating predictive claims.
- [x] Suppress probability or confidence claims when samples do not support them.
- [x] Add token input and current-context retrieval with timestamps and freshness.
- [x] Reuse only features whose historical and live definitions are comparable.
- [x] Show matching precedents, differences, missing features, and limitations.
- [x] Do not expose buy/sell recommendations, automated execution, or a risk score
      that implies an unvalidated probability.

**Acceptance:** Preflight is a transparent comparison, not a claim that losses can
be prevented. The same versioned feature rule is used wherever comparison is valid.
An unavailable feature cannot silently become a non-match.

### M6 - Submission hardening

**Target:** September 25-26. **Priority:** P0. **Depends on:** M5.

- [ ] Recheck the live competition terms and documented permission decisions.
- [ ] Complete useful authenticated API usage and retain auditable usage evidence.
- [ ] Target at least 1,100 successful provider calls as operational headroom above
      the campaign minimum, subject to an approved budget. Never inflate counts
      with no-op loops, local cache hits, or local health requests.
- [ ] Convert Docker dependency installation to use committed locks; pin release
      images and CI actions appropriately, then test a clean installation.
- [ ] Run the full test suite, frontend production build, and browser smoke tests.
- [ ] Select a source license, verify attribution, and scan code/history for secrets.
- [ ] Measure actual end-to-end latency and document cold-cache behavior honestly.
- [ ] Record a 30-60 second, readable English demonstration with subtitles and no
      reliance on narration, showing the build running with live Nansen data.
- [ ] Demonstrate an actual live-data path; label stored examples separately.
- [ ] Prepare an optional share card with explicit consent, no wallet balance,
      no address by default, and no misleading claim of direct counterparties.
- [ ] Publish the repository and demo post, tag the required account, submit the
      official form, and retain submission confirmation in private `artifacts/`.

**Acceptance:** Another developer can follow the README, the judges can see a
complete live-data journey, and every material result has a verifiable explanation.

## 4. Competition alignment

The campaign page lists four equally weighted criteria and a September 14-27 event
window. Submissions close on September 27, 2026 at 23:59 UTC. Entry requires 1,000+
API calls, a public GitHub repository, a demo post tagging Nansen with a 30-60 second
recording, and the official form. These facts were checked on September 16, 2026;
recheck them before submitting. [S1] [S7]

| Criterion | Weight | Planned proof |
| --- | --- | --- |
| Data integration | 25% | Temporal evidence directly changes the replay and preflight result |
| Creativity | 25% | Personal-entry review connected to a future decision, not another token dashboard |
| Functionality | 25% | Live wallet -> entry -> evidence -> preflight, including failure handling |
| Documentation | 25% | Clear setup, method explanation, tests, and a followable demo |

Our internal submission target is **September 26**, not the last possible minute.
The milestone dates are planning targets, not guaranteed delivery estimates.

## 5. Risk register

| Risk | Trigger | Response |
| --- | --- | --- |
| Historical API changes | Schema or semantics differ from expectations | Keep adapter small; contract-test; revise claims before UI |
| Insufficient coverage | Nulls, missing periods, truncated pages | Show coverage; narrow scope; never replace with zero |
| Flow interpreted as selling | Only transfer aggregates available | Say outflows; require trade evidence for a sales claim |
| Hindsight leakage | Current labels or later prices enter features | Separate models and test strict temporal boundaries |
| Weak pattern sample | A few matching losses and ignored winners | Show descriptive precedents only; compare both outcomes |
| Budget or latency | Expensive fan-out or throttling | Cap entries, use honest progress, cache, and stop at budget |
| Redistribution uncertainty | Historical outputs not explicitly permitted | Obtain clarification; restrict publication until resolved |
| Scope creep | Multichain, bots, scoring, or AI generation added | Preserve the single end-to-end journey |

## 6. After the buildathon

Only after the first version is verified: Base support, explicitly defined lot-level
accounting, better evaluation datasets, opt-in saved reports, privacy controls for
hosted use, and a commercial permission review. An optional LLM may explain existing
structured evidence, but must not create evidence or decide the verdict.

## 7. Current implementation handoff

**EG-001, EG-002, EG-003, and M2-M5 are complete.** The validated sample required
expanding beyond the planned 90-day scope: the authorized wallet contained no entries
in 90 days, two in one year, and three across documented Solana coverage. All three
pre-entry contexts had observed zero Smart Trader net flow, unavailable average
flow, and mixed 24-hour/7-day price directions. Treat this as a limited replay
sample, not evidence of a predictive pattern.

The local application now provides typed, budgeted wallet ingestion, strictly
pre-entry historical flow context, separate 24-hour and 7-day reference-price
observations, durable job progress/cancellation, replay with hidden outcomes, and an
evidence drawer. M5 adds four predeclared flow rules, a same-wallet descriptive
baseline, explicit personal-precedent exploration, and a bounded current-token
comparison using the documented rolling one-day flow endpoint. Missing current
features remain unavailable, and the contract contains no recommendation or risk
score. The ordinary and browser suites remain offline. Begin M6 with submission
hardening; do not add predictive claims, claims about selling, or trading execution.

[S1]: https://nansen.ai/campaigns/meridian-buildathon
[S7]: https://release.nansen.ai/help/articles/3540155-nansen-meridian-buildathon-sep-14-27

# Methodology Contract

These requirements govern implemented ingestion contracts and future context,
outcome, interpretation, and presentation work. Their purpose is to make every
conclusion no stronger than its evidence.

## 1. Three independent layers

**Context:** observations from a declared period before an entry.  
**Outcome:** later observed prices or correctly attributed accounting results.  
**Interpretation:** a versioned, transparent rule linking observations to wording.

A price decline after a purchase must never retroactively change the context label.
A loss does not prove another participant was informed or sold directly to the user.

## 2. Time and historical labels

Use UTC-aware timestamps and a strictly pre-entry cutoff. Validate inclusive bounds,
bucket intervals, chain ordering, and timestamp precision. A bucket crossing the
entry must not be included as entirely pre-entry data. If the provider cannot
support the required boundary, lower the resolution or mark the context unavailable.

Nansen describes temporal labels for the historical summary and notes that results
may be revised after historical corrections. Treat the result as a reconstruction,
not proof of the exact API response available at the original second. Record the
query and retrieval time. [S2]

Current labels cannot silently replace historical cohorts. Do not use metadata
observed today as a historical feature unless its historical semantics are validated.

## 3. Transfers, trades, and segments

A transfer or token outflow alone is not sufficient evidence of a DEX sale. Use
wording such as "net token outflows in the observed segment" unless actual
buy/sell records establish a trade claim. Historical buy/sell data is separately
documented by the provider. [S4]

A cohort-level net-selling claim requires both sides, deduplication, declared
filters, and adequate pagination. If only a sample is available, scope the statement
to that sample. Do not infer common ownership from labels. Do not equate a named
segment with guaranteed skill, information, or future performance.

Evaluate self-inclusion: the user's own large trade must not manufacture the market
signal used to explain that same trade. Exclude it when possible; otherwise disclose
the limitation and avoid strong aggregate conclusions.

## 4. Outcomes and accounting

A later reference price is not necessarily executable and is not realized PnL.
Use a declared price source, interval, matching rule, and horizon. Missing liquidity,
missing prices, unfinished candles, and a horizon not yet reached require explicit
states, not zeros or assumed total losses.

Repeated buys, partial sells, transfers, fees, and routing complicate per-entry
accounting. Token-level provider PnL can be supplementary context. Do not assign it
to an individual entry without an explicit lot-allocation method and supported data.

## 5. Patterns and evaluation

Start with a few predeclared rules, not unconstrained pattern mining or LLM verdicts.
Display matches across good and bad outcomes, sample counts, missingness, and a
meaningful same-wallet baseline. Selection must not depend on already knowing which
operations lost money.

Treat small samples as descriptive precedents, not probabilities. If making a
predictive claim, hold out later entries, purge overlapping outcome horizons, and
keep rule selection separate from evaluation. Do not count routed trade legs or
correlated repeats as independent evidence without qualification.

## 6. Historical/live comparability

A live feature can be compared only when its definition, segment mapping, lookback,
direction, and units agree with the historical feature. Fresh-wallet snapshots or
other fields with different observation windows need their own timestamps and
comparison rules; provider documentation should be checked during the spike. [S2, S5]

## 7. Required result states

Keep these distinct: observed signal, observed no-signal, insufficient sample,
unavailable historical coverage, truncated sample, stale evidence, pending outcome,
provider failure, and budget exceeded. Preserve null values and provider warnings.
A timeout must not become "no signal" or a reassuring assessment.

## 8. Communication

Prefer measurements and periods over accusatory labels. Do not issue a definitive
"you were exit liquidity" verdict. Do not present an unvalidated numeric score as a
probability. Preflight compares evidence; it does not execute, instruct, or guarantee
an investment outcome. Any optional LLM is only a presentation layer over existing,
validated structured facts.

Source references resolve in [SOURCES.md](SOURCES.md).

## 9. Implemented M3/M4 boundary

The review pipeline ends the historical-flow query one second before the entry,
stores its values and coverage in `HistoricalContext`, and runs OHLCV retrieval only
after that object exists. The browser receives no later price values from the replay
endpoint; it must call the separate outcome endpoint after an explicit reveal action.
This presentation boundary complements, but does not replace, the tested temporal
separation in the application and domain layers.

# Provider Validation Contract

**Checked:** September 16, 2026

**Status:** Public schemas implemented; authenticated validation blocked until a
local API key and an authorized public example wallet are provided

**Ordinary tests:** Offline; zero provider calls and zero credits

This document records the current public contract and the narrow validation tool.
It is not evidence that the configured account can access these endpoints. Only a
successful opt-in response can establish account access, observed null behavior,
actual response fields, and charged credits.

## Authentication, limits, and cost

- Authentication uses the lowercase `apikey` request header. The key remains in the
  backend configuration and is never included in command output.
- Free accounts are documented at 15 requests per second and 300 per minute. Pro
  accounts are documented at 75 per second and 1,500 per minute.
- `profiler/dex-trades` is documented at one credit per call.
- Each beta historical endpoint used here is documented at five credits per call.
- Responses may report quoted, used, and remaining credits, a request ID, global
  rate limits, endpoint limits, and `Retry-After`. Observed headers must be recorded
  from live calls because documented presence is not a guarantee for every response.

The validation command sends at most one request per invocation. It refuses live
execution unless `--execute` is present and `--max-credits` covers the documented
cost. It has no retry loop.

## Checked routes and request shapes

### Wallet DEX trades

- Route: `POST /api/v1/profiler/dex-trades`
- Required input: address, chain, and `date` range.
- Validation input: Solana, one result per page, page one, newest timestamp first.
- Pagination is one-based and supports at most 1,000 results per page.
- Publicly documented cost: one credit.

### Historical token-flow summary

- Route: `POST /api/v1beta1/tgm/historical-token-flow-summary`
- Required input: chain, token address, and explicit `date_range`.
- Entryglass keeps the blacklist filter enabled.
- The response has one aggregate row and optional warnings rather than pagination.
- All segment fields are nullable. A null means historical label coverage is
  unavailable; it must never be converted to zero or "no signal."
- Smart Trader history is documented from 2020 onward. Whale, Public Figure, Top
  PnL, and Exchange temporal coverage starts on March 11, 2025.
- Publicly documented cost: five credits.

### Historical who bought/sold

- Route: `POST /api/v1beta1/tgm/historical-who-bought-sold`
- Required input: chain, token address, explicit `date_range`, and an explicit BUY
  or SELL direction for Entryglass validation.
- Entryglass sends the exact temporal label filter `Smart Trader` and does not
  substitute `smart_money`, a windowed Smart Trader label, or Smart Dex Trader.
- Pagination is one-based and supports at most 1,000 results per page. Validation
  requests one row, sorted by the matching bought or sold USD field.
- Publicly documented cost: five credits.

## Segment mapping

The first product slice has one selected cohort:

| Entryglass concept | Provider contract | Allowed equivalence |
| --- | --- | --- |
| Historical Smart Trader context | `smart_trader_*` fields from the beta historical token-flow summary, resolved at `date_to` | Exact documented Smart Trader aggregate only |
| Historical Smart Trader trade evidence | `include_labels: ["Smart Trader"]` on the beta historical who-bought/sold request | Exact label only |

The following remain different concepts and are not aliases: `is_smart_money`,
`30D Smart Trader`, `90D Smart Trader`, `180D Smart Trader`, `Smart Dex Trader`, and
its windowed variants. A live validation result must confirm the selected fields and
coverage before any domain model or UI copy treats the mapping as available.

## Time semantics

Nansen documents date ranges as closed on both sides: `[from, to]`. Entryglass needs
a strictly pre-entry context, so a future use case must set `to` before the entry
instant and prove that no same-entry event or crossing bucket can enter the context.
The command preserves explicit UTC timestamps but does not claim the provider's
effective precision until a live response is inspected.

Solana coverage is documented from March 17, 2020. Live activity is generally
indexed within seconds to a few minutes, while some current-day responses may be
cached for up to five minutes. Historical results can be revised after late data,
pricing fixes, label-history corrections, or metadata changes.

## Safe command usage

Dry-run is the default and does not require a key:

```bash
make validate-provider ARGS='dex-trades \
  --address PUBLIC_SOLANA_WALLET \
  --from 2026-06-01T00:00:00Z \
  --to 2026-06-02T00:00:00Z'
```

Live execution is explicit and can consume credits:

```bash
make validate-provider ARGS='--execute --max-credits 1 dex-trades \
  --address PUBLIC_SOLANA_WALLET \
  --from 2026-06-01T00:00:00Z \
  --to 2026-06-02T00:00:00Z'
```

Historical flow and historical trade validation require `--max-credits 5`. The
subcommands are `historical-flow --token ...` and
`historical-who --token ... --side BUY|SELL`.

Output contains only the endpoint, timing, row count, response field names,
pagination state, warning count, safe headers, and hashes of the request and raw
response. It never prints the API key or provider row values. Redirect live metadata
to an ignored file under `data/`; do not commit real wallet evidence.

## Live validation still required

With a configured key and an owner-approved public wallet, verify and record:

1. Account tier and access to all three routes.
2. Actual quoted and charged credits for one bounded request per route.
3. Returned field names, pagination behavior, warnings, and null behavior.
4. Effective timestamp precision and behavior at a strict pre-entry boundary.
5. Request IDs, latency, rate-limit headers, and remaining credits.

Do not mark the live-access roadmap item complete from public documentation alone.

## Sources

- [Authentication](https://docs.nansen.ai/getting-started/authentication)
- [Rate limits](https://docs.nansen.ai/getting-started/rate-limits)
- [Credits and pricing](https://docs.nansen.ai/getting-started/credits)
- [Data coverage by chain](https://docs.nansen.ai/api/data-coverage)
- [Address DEX Trades](https://docs.nansen.ai/api/profiler/address-dex-trades)
- [Historical Token Flow Summary](https://docs.nansen.ai/api/backtesting-data/historical-token-flow-summary)
- [Historical Token Who Bought/Sold](https://docs.nansen.ai/api/backtesting-data/historical-token-who-bought-sold)
- [Data methodology](https://docs.nansen.ai/guides/data-methodology-and-technical-reference)

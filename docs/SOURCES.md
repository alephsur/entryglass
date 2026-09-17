# Source Register

Documentation inspected while preparing the scaffold on **September 15, 2026** and
rechecked for EG-002 on **September 16, 2026**.
These references are navigation and provenance, not an assertion that an
authenticated integration has been validated. Recheck current provider and
competition terms before implementation and submission.

## Project and data-provider references

- **S1 - Meridian Buildathon campaign:** https://nansen.ai/campaigns/meridian-buildathon
  The campaign page and detailed help article were rechecked for EG-002. The cutoff,
  form fields, repository rule, and video constraints are recorded below. No prize
  eligibility is guaranteed.
- **S2 - Historical Token Flow Summary:** https://docs.nansen.ai/api/backtesting-data/historical-token-flow-summary
- **S3 - Address DEX Trades:** https://docs.nansen.ai/api/profiler/address-dex-trades
- **S4 - Historical Token Who Bought/Sold:** https://docs.nansen.ai/api/backtesting-data/historical-token-who-bought-sold
- **S5 - Flow Intelligence:** https://docs.nansen.ai/api/token-god-mode/flow-intelligence
- **S6 - Redistribution guide:** https://docs.nansen.ai/guides/redistribution-guide
- **S7 - Meridian detailed rules:**
  https://release.nansen.ai/help/articles/3540155-nansen-meridian-buildathon-sep-14-27
- **S8 - Meridian submission form:** https://nansen-ai.typeform.com/meridian-submit
- **S9 - API Supplemental Terms:** https://nansen.ai/legal/api
- **S10 - Nansen Terms of Service:** https://nansen.ai/legal/terms-of-services
- **S11 - API authentication:** https://docs.nansen.ai/getting-started/authentication
- **S12 - Rate limits and credits:**
  https://docs.nansen.ai/getting-started/rate-limits and
  https://docs.nansen.ai/getting-started/credits
- **S13 - Data coverage:** https://docs.nansen.ai/api/data-coverage
- **S14 - Price OHLCV:** https://docs.nansen.ai/api/token-god-mode/price-ohlcv
- **S15 - Backtesting data overview:** https://docs.nansen.ai/api/backtesting-data
- **S16 - Address PnL and Trade Performance:**
  https://docs.nansen.ai/api/profiler/address-pnl-and-trade-performance
- **S17 - Endpoint credit overview:** https://docs.nansen.ai/api/overview

The campaign cutoff is September 27, 2026 at 23:59 UTC. The detailed rules require
1,000+ calls, a public GitHub repository, an X post tagging Nansen, a 30-60 second
recording with live Nansen data, and the official form. The current form requires
the API-account email, X post URL, and GitHub repository URL.

The redistribution guide does not list the beta historical endpoints or
`profiler/dex-trades`. Do not infer public redistribution rights from similarly
named current endpoints. The resulting project decision and required clarification
are recorded in [COMPETITION_AND_PERMISSIONS.md](COMPETITION_AND_PERMISSIONS.md).

Endpoint semantics mentioned in other documents should be checked against the
OpenAPI schema embedded in the corresponding current provider page. No undocumented
client behavior, access entitlement, pricing, or publication permission is assumed.
The implemented request shapes, exact cohort mapping, documented costs, and remaining
live checks are recorded in [PROVIDER_VALIDATION.md](PROVIDER_VALIDATION.md).

## Development-tool references

- Vue quick start: https://vuejs.org/guide/quick-start.html
- Vite guide: https://vite.dev/guide/
- uv and FastAPI integration: https://docs.astral.sh/uv/guides/integration/fastapi/
- uv installation: https://docs.astral.sh/uv/getting-started/installation/
- Node.js downloads: https://nodejs.org/en/download

The first three were inspected for scaffold preparation. Installation links are
provided for setup convenience. Package manifests use bounded version ranges. The
locked installs and browser smoke test were verified during EG-001; Docker execution
still needs verification on the owner's machine.

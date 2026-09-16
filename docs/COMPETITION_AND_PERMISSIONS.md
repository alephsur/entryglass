# Competition and Provider Permissions Check

**Checked:** September 16, 2026  
**Scope:** EG-002 public-source verification; no authenticated API calls  
**Decision:** Competition requirements are clear. Private validation may proceed,
but public redistribution of the planned historical data remains on hold pending
written clarification from Nansen.

This document records a project compliance decision, not legal advice. Recheck the
linked sources immediately before submission because campaign rules, API terms, and
provider guidance can change.

## Competition requirements

| Requirement | Verified rule | Project consequence |
| --- | --- | --- |
| Deadline | September 27, 2026 at 23:59 UTC | Keep the internal September 26 target |
| General eligibility | Anyone able to build with the Nansen API may enter; AI-assisted development is allowed | The owner must still satisfy the account terms described below |
| Account usage | Create an API key and log at least 1,000 API calls against it | Record genuine project calls; do not generate no-op traffic |
| Submission limit | One submission per account | Use the same account throughout validation and submission |
| Demo post | Post on X, tag `@nansen_ai`, include the GitHub link and a 30-60 second screen recording | Prepare one silent-followable recording with live Nansen data visible |
| Repository | The GitHub repository must be public and include reviewable code and a README | Keep restricted provider data and private evidence out of Git |
| Entry form | Submit the account email, X demo-post URL, and GitHub repository URL | All three fields are required in the current Typeform |
| Judging | Data integration, functionality, creativity/originality, and documentation/submission are weighted equally | The data must drive product logic, not decorate the interface |

The campaign page says no application or team is required. The more detailed Nansen
help article says the build must run end to end with live data and that a private
repository does not qualify. The current form contains exactly three required
questions: the email associated with the Nansen API account, the X demo-post link,
and the GitHub repository link.

The general Nansen Terms of Service add account-level requirements that the campaign
summary does not repeat: a user must be at least 18 or the age of majority in their
jurisdiction, must not be a sanctioned person, and must not access the service from
a restricted jurisdiction. Actual owner eligibility is a personal/legal
self-check; this repository cannot establish it.

## Provider-permission decision

Nansen's API Supplemental Terms license API access for internal use and prohibit
external redistribution of raw, bulk, or aggregated Nansen data unless written
permission or the Data Redistribution Guidelines expressly allow it. Public-facing
combinations with other datasets also require prior written permission. Required
attribution is `Powered by Nansen` or an equivalent visible form that does not imply
Nansen endorsement.

The redistribution table and the endpoints planned for Entryglass do not align
one-to-one:

| Planned source | Current redistribution-table status | Entryglass decision |
| --- | --- | --- |
| `POST /api/v1/profiler/dex-trades` | Not listed | Internal validation only until Nansen confirms public derived display and retention |
| `POST /api/v1beta1/tgm/historical-token-flow-summary` | Not listed; endpoint is beta | Internal validation only; do not publish values, payloads, or fixtures without written permission |
| `POST /api/v1beta1/tgm/historical-who-bought-sold` | Not listed; endpoint is beta | Internal validation only; do not expose addresses, labels, rows, or derived aggregates without written permission |
| Current `tgm/flow-intelligence` | Allowed with attribution | Public use is possible only with visible attribution and the documented endpoint rules |
| Current `tgm/who-bought-sold` | Allowed with attribution | Public use is possible only with visible attribution and the documented endpoint rules |
| `smart-money/dex-trades` | Prohibited from redistribution | Do not use for a public Entryglass surface |
| `address/labels` | Prohibited from redistribution | Do not publish labels or label-derived wallet lists |

An allowed current endpoint does not grant permission to its historical beta
counterpart. Likewise, `tgm/dex-trades` and `profiler/address/transactions` entries
in the guide do not establish permission for `profiler/dex-trades`. The project must
not infer permission from a similar name or response shape.

## Implementation guardrails

Until written clarification is received:

- Keep EG-003 responses and evidence private under the ignored `data/` workspace.
- Do not commit raw responses, real wallet histories, labeled-address rows, or
  provider-derived fixtures.
- Store only the minimum metadata needed for validation, such as redacted request
  parameters, request IDs, observed credit headers, timestamps, and response hashes.
- Do not make a public UI, screenshot, recording, or share card display data from an
  unlisted endpoint.
- Do not retain raw or cached Nansen data permanently; the API terms prohibit
  retention beyond documented timeframes, and no timeframe was found for the beta
  historical endpoints.
- Recheck the rules and add visible Nansen attribution before any public demo.

## Clarification required from Nansen

Before a public demonstration, obtain a written answer covering:

1. Whether the three planned endpoints above may support a public buildathon demo.
2. Whether derived per-entry historical context may be shown without exposing raw
   rows, labels, addresses, or provider payloads.
3. Whether screenshots and a 30-60 second X recording may show those derived values.
4. What retention period applies to private raw responses, normalized evidence, and
   response hashes from the beta historical endpoints.
5. Whether hand-authored synthetic contract fixtures based on the documented schema
   are permitted in a public repository.

No approval request, support email, account creation, or competition submission was
sent during EG-002. Those external actions require the owner's identity and an
explicitly approved final message.

## Sources

- [Meridian Buildathon campaign](https://nansen.ai/campaigns/meridian-buildathon)
- [Meridian Buildathon detailed help article](https://release.nansen.ai/help/articles/3540155-nansen-meridian-buildathon-sep-14-27)
- [Current submission form](https://nansen-ai.typeform.com/meridian-submit)
- [Nansen Terms of Service](https://nansen.ai/legal/terms-of-services)
- [Nansen API Supplemental Terms](https://nansen.ai/legal/api)
- [Data Redistribution Guidelines](https://docs.nansen.ai/guides/redistribution-guide)
- [Historical Token Flow Summary](https://docs.nansen.ai/api/backtesting-data/historical-token-flow-summary)
- [Historical Token Who Bought/Sold](https://docs.nansen.ai/api/backtesting-data/historical-token-who-bought-sold)
- [Address DEX Trades](https://docs.nansen.ai/api/profiler/address-dex-trades)

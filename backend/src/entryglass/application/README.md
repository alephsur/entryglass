# Application Layer

Contains provider validation, budgeted wallet ingestion, and the M3-M5 review
orchestration. The review use case imports economic entries, requests a strictly
pre-entry context per entry, and computes separate reached/pending outcome horizons.
It owns request/credit accounting and durable partial/failure transitions.

The precedent use case groups every reviewed entry through four predeclared pure
rules and builds a same-wallet descriptive baseline. Preflight makes one bounded
current-context query (with at most two attempts) and compares only compatible rule
inputs. It returns no
score, probability, recommendation, or execution action.

# Application Layer

Contains provider validation, budgeted wallet ingestion, and the M3/M4 review
orchestration. The review use case imports economic entries, requests a strictly
pre-entry context per entry, and computes separate reached/pending outcome horizons.
It owns request/credit accounting and durable partial/failure transitions.

Pattern and preflight orchestration remain unimplemented.

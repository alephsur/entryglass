# Storage Adapter

M2-M5 implement versioned SQLite migrations for import jobs, normalized entries,
wallet/job associations, ambiguous transactions, immutable evidence metadata, and
a freshness-bounded cache, review jobs, pre-entry context, outcomes, and review
evidence, and durable current-token preflight jobs/evidence. Database files are
ignored by Git and created with owner-only permissions. They are private local
storage, not encrypted storage. Personal precedent reports are derived from the
persisted review rather than stored as independent claims.

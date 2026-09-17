# Storage Adapter

M2-M4 implement versioned SQLite migrations for import jobs, normalized entries,
wallet/job associations, ambiguous transactions, immutable evidence metadata, and
a freshness-bounded cache, review jobs, pre-entry context, outcomes, and review
evidence. Database files are ignored by Git and created with owner-only permissions.
They are private local storage, not encrypted storage. Pattern and preflight storage
remain out of scope.

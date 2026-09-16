# Domain Layer

Contains the pure entry, strict pre-entry window, historical-context state, and
later-price observation contracts validated by EG-003. There is no pattern engine,
scoring, ingestion orchestration, or persistence here. Keep context separate from
later outcomes and implement one tested vertical slice at a time.

"""Versioned SQLite migrations for private ingestion and replay persistence."""

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE import_jobs (
            job_id TEXT PRIMARY KEY,
            scope_key TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            chain TEXT NOT NULL CHECK (chain = 'solana'),
            from_utc TEXT NOT NULL,
            to_utc TEXT NOT NULL,
            quote_assets_json TEXT NOT NULL,
            max_entries INTEGER NOT NULL,
            page_size INTEGER NOT NULL,
            status TEXT NOT NULL,
            coverage TEXT NOT NULL,
            next_page INTEGER NOT NULL DEFAULT 1,
            pages_fetched INTEGER NOT NULL DEFAULT 0,
            requests_attempted INTEGER NOT NULL DEFAULT 0,
            credits_used INTEGER NOT NULL DEFAULT 0,
            entries_saved INTEGER NOT NULL DEFAULT 0,
            cancellation_requested INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX idx_import_jobs_scope ON import_jobs(scope_key, created_at DESC);

        CREATE TABLE trade_entries (
            entry_id TEXT PRIMARY KEY,
            transaction_hash TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            chain TEXT NOT NULL CHECK (chain = 'solana'),
            token_address TEXT NOT NULL,
            quote_address TEXT NOT NULL,
            token_amount TEXT NOT NULL,
            quote_amount TEXT NOT NULL,
            trade_value_usd TEXT NOT NULL
        );

        CREATE TABLE wallet_entries (
            wallet_address TEXT NOT NULL,
            entry_id TEXT NOT NULL REFERENCES trade_entries(entry_id),
            PRIMARY KEY (wallet_address, entry_id)
        );

        CREATE TABLE job_entries (
            job_id TEXT NOT NULL REFERENCES import_jobs(job_id),
            entry_id TEXT NOT NULL REFERENCES trade_entries(entry_id),
            PRIMARY KEY (job_id, entry_id)
        );

        CREATE TABLE ambiguous_trades (
            job_id TEXT NOT NULL REFERENCES import_jobs(job_id),
            transaction_hash TEXT NOT NULL,
            reason TEXT NOT NULL,
            leg_count INTEGER NOT NULL,
            PRIMARY KEY (job_id, transaction_hash)
        );

        CREATE TABLE evidence_records (
            evidence_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES import_jobs(job_id),
            provider TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            chain TEXT NOT NULL CHECK (chain = 'solana'),
            subject_hash TEXT NOT NULL,
            requested_from_utc TEXT NOT NULL,
            requested_to_utc TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            response_hash TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            adapter_version TEXT NOT NULL,
            methodology_version TEXT NOT NULL,
            source_schema_version TEXT NOT NULL,
            request_id TEXT,
            page INTEGER,
            per_page INTEGER,
            is_last_page INTEGER,
            warnings_json TEXT NOT NULL,
            quoted_credits INTEGER,
            used_credits INTEGER,
            attempt_count INTEGER NOT NULL,
            cache_hit INTEGER NOT NULL,
            UNIQUE (job_id, request_fingerprint)
        );

        CREATE TABLE provider_page_cache (
            request_fingerprint TEXT PRIMARY KEY,
            response_hash TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            page INTEGER NOT NULL,
            per_page INTEGER NOT NULL,
            is_last_page INTEGER NOT NULL,
            warnings_json TEXT NOT NULL,
            request_id TEXT,
            quoted_credits INTEGER,
            legs_json TEXT NOT NULL
        );
        """,
    ),
    (
        2,
        """
        CREATE TABLE review_jobs (
            review_id TEXT PRIMARY KEY,
            wallet_address TEXT NOT NULL,
            from_utc TEXT NOT NULL,
            to_utc TEXT NOT NULL,
            quote_assets_json TEXT NOT NULL,
            max_entries INTEGER NOT NULL,
            max_requests INTEGER NOT NULL,
            max_credits INTEGER NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            entries_total INTEGER NOT NULL DEFAULT 0,
            entries_processed INTEGER NOT NULL DEFAULT 0,
            requests_attempted INTEGER NOT NULL DEFAULT 0,
            credits_used INTEGER NOT NULL DEFAULT 0,
            import_job_id TEXT REFERENCES import_jobs(job_id),
            cancellation_requested INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX idx_review_jobs_created ON review_jobs(created_at DESC);

        CREATE TABLE review_entries (
            review_id TEXT NOT NULL REFERENCES review_jobs(review_id),
            entry_id TEXT NOT NULL REFERENCES trade_entries(entry_id),
            ordinal INTEGER NOT NULL,
            PRIMARY KEY (review_id, entry_id),
            UNIQUE (review_id, ordinal)
        );

        CREATE TABLE historical_contexts (
            review_id TEXT NOT NULL REFERENCES review_jobs(review_id),
            entry_id TEXT NOT NULL REFERENCES trade_entries(entry_id),
            window_from_utc TEXT NOT NULL,
            window_to_utc TEXT NOT NULL,
            coverage TEXT NOT NULL,
            smart_trader_net_flow_usd TEXT,
            smart_trader_avg_flow_usd TEXT,
            smart_trader_wallet_count INTEGER,
            warnings_json TEXT NOT NULL,
            PRIMARY KEY (review_id, entry_id)
        );

        CREATE TABLE outcome_observations (
            review_id TEXT NOT NULL REFERENCES review_jobs(review_id),
            entry_id TEXT NOT NULL REFERENCES trade_entries(entry_id),
            horizon TEXT NOT NULL,
            target_at TEXT NOT NULL,
            state TEXT NOT NULL,
            observed_at TEXT,
            observed_price_usd TEXT,
            price_change_pct TEXT,
            PRIMARY KEY (review_id, entry_id, horizon)
        );

        CREATE TABLE review_evidence (
            evidence_id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL REFERENCES review_jobs(review_id),
            entry_id TEXT NOT NULL REFERENCES trade_entries(entry_id),
            kind TEXT NOT NULL,
            provider TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            subject_hash TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            response_hash TEXT NOT NULL,
            requested_from_utc TEXT NOT NULL,
            requested_to_utc TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            request_id TEXT,
            warnings_json TEXT NOT NULL,
            quoted_credits INTEGER,
            used_credits INTEGER,
            attempt_count INTEGER NOT NULL,
            truncated INTEGER NOT NULL,
            truncation_note TEXT,
            adapter_version TEXT NOT NULL,
            methodology_version TEXT NOT NULL,
            source_schema_version TEXT NOT NULL,
            UNIQUE (review_id, entry_id, kind, request_fingerprint)
        );
        """,
    ),
    (
        3,
        """
        CREATE TABLE preflight_jobs (
            preflight_id TEXT PRIMARY KEY,
            review_id TEXT NOT NULL REFERENCES review_jobs(review_id),
            token_address TEXT NOT NULL,
            horizon TEXT NOT NULL,
            status TEXT NOT NULL,
            timeframe TEXT,
            coverage TEXT,
            observed_at TEXT,
            smart_trader_net_flow_usd TEXT,
            smart_trader_avg_flow_usd TEXT,
            smart_trader_wallet_count INTEGER,
            warnings_json TEXT NOT NULL DEFAULT '[]',
            requests_attempted INTEGER NOT NULL DEFAULT 0,
            credits_used INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX idx_preflight_review ON preflight_jobs(review_id, created_at DESC);

        CREATE TABLE preflight_evidence (
            evidence_id TEXT PRIMARY KEY,
            preflight_id TEXT NOT NULL REFERENCES preflight_jobs(preflight_id),
            provider TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            subject_hash TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            response_hash TEXT NOT NULL,
            requested_from_utc TEXT NOT NULL,
            requested_to_utc TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            request_id TEXT,
            warnings_json TEXT NOT NULL,
            quoted_credits INTEGER,
            used_credits INTEGER,
            attempt_count INTEGER NOT NULL,
            adapter_version TEXT NOT NULL,
            methodology_version TEXT NOT NULL,
            UNIQUE (preflight_id, request_fingerprint)
        );
        """,
    ),
)

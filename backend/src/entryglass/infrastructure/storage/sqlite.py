"""SQLite implementation for private M2 ingestion and evidence storage."""

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entryglass.application.ingestion import ImportScope, WalletTradePage
from entryglass.application.reviews import ProviderEvidence, ReviewScope, evidence_id
from entryglass.domain.context import ContextCoverage, HistoricalContext, PreEntryWindow
from entryglass.domain.evidence import CoverageState, EvidenceRecord, ImportJob, ImportStatus
from entryglass.domain.outcomes import OutcomeHorizon, OutcomeObservation, OutcomeState
from entryglass.domain.preflight import CurrentContext, PreflightJob, PreflightStatus
from entryglass.domain.reviews import ReviewJob, ReviewStage, ReviewStatus
from entryglass.domain.trades import (
    AmbiguousTrade,
    SwapLeg,
    TradeEntry,
    validate_solana_address,
)
from entryglass.infrastructure.storage.migrations import MIGRATIONS


class SqliteIngestionRepository:
    """Small transactional repository; database files remain local and private."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._migrate()
        self._path.chmod(0o600)

    def create_job(self, scope: ImportScope, *, now: datetime) -> ImportJob:
        job_id = uuid.uuid4().hex
        serialized_now = _serialize_time(now)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO import_jobs (
                    job_id, scope_key, wallet_address, chain, from_utc, to_utc,
                    quote_assets_json, max_entries, page_size, status, coverage,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    scope.scope_key,
                    scope.wallet_address,
                    scope.chain,
                    _serialize_time(scope.from_utc),
                    _serialize_time(scope.to_utc),
                    json.dumps(
                        [
                            {"address": asset.address, "symbol": asset.symbol}
                            for asset in scope.quote_assets
                        ],
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    scope.max_entries,
                    scope.page_size,
                    ImportStatus.RUNNING.value,
                    CoverageState.UNAVAILABLE.value,
                    serialized_now,
                    serialized_now,
                ),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> ImportJob:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM import_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown import job: {job_id}")
        return _job_from_row(row)

    def request_cancellation(self, job_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE import_jobs
                SET cancellation_requested = 1, updated_at = ?
                WHERE job_id = ? AND status = ?
                """,
                (_serialize_time(datetime.now(UTC)), job_id, ImportStatus.RUNNING.value),
            )
        if cursor.rowcount == 0:
            raise ValueError("Only a running import can be cancelled.")

    def cancellation_requested(self, job_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cancellation_requested FROM import_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown import job: {job_id}")
        return bool(row["cancellation_requested"])

    def get_cached_page(self, fingerprint: str, *, now: datetime) -> WalletTradePage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM provider_page_cache
                WHERE request_fingerprint = ? AND expires_at > ?
                """,
                (fingerprint, _serialize_time(now)),
            ).fetchone()
        if row is None:
            return None
        try:
            legs = tuple(_leg_from_mapping(item) for item in json.loads(row["legs_json"]))
        except (ArithmeticError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM provider_page_cache WHERE request_fingerprint = ?",
                    (fingerprint,),
                )
            return None
        return WalletTradePage(
            legs=legs,
            request_fingerprint=row["request_fingerprint"],
            response_hash=row["response_hash"],
            retrieved_at=_parse_time(row["retrieved_at"]),
            page=row["page"],
            per_page=row["per_page"],
            is_last_page=bool(row["is_last_page"]),
            warnings=tuple(json.loads(row["warnings_json"])),
            request_id=row["request_id"],
            quoted_credits=row["quoted_credits"],
            used_credits=0,
            attempt_count=0,
            cache_hit=True,
        )

    def save_cached_page(self, page: WalletTradePage, *, expires_at: datetime) -> None:
        payload = json.dumps(
            [_leg_to_mapping(leg) for leg in page.legs],
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO provider_page_cache (
                    request_fingerprint, response_hash, retrieved_at, expires_at,
                    page, per_page, is_last_page, warnings_json, request_id,
                    quoted_credits, legs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_fingerprint) DO UPDATE SET
                    response_hash = excluded.response_hash,
                    retrieved_at = excluded.retrieved_at,
                    expires_at = excluded.expires_at,
                    page = excluded.page,
                    per_page = excluded.per_page,
                    is_last_page = excluded.is_last_page,
                    warnings_json = excluded.warnings_json,
                    request_id = excluded.request_id,
                    quoted_credits = excluded.quoted_credits,
                    legs_json = excluded.legs_json
                """,
                (
                    page.request_fingerprint,
                    page.response_hash,
                    _serialize_time(page.retrieved_at),
                    _serialize_time(expires_at),
                    page.page,
                    page.per_page,
                    int(page.is_last_page),
                    json.dumps(page.warnings, separators=(",", ":")),
                    page.request_id,
                    page.quoted_credits,
                    payload,
                ),
            )

    def save_page_result(
        self,
        *,
        job_id: str,
        wallet_address: str,
        entries: tuple[TradeEntry, ...],
        ambiguous: tuple[AmbiguousTrade, ...],
        evidence: EvidenceRecord,
        next_page: int,
        requests_attempted: int,
        credits_used: int,
    ) -> None:
        now = _serialize_time(datetime.now(UTC))
        with self._connect() as connection:
            for entry in entries:
                connection.execute(
                    """
                    INSERT INTO trade_entries (
                        entry_id, transaction_hash, occurred_at, chain, token_address,
                        quote_address, token_amount, quote_amount, trade_value_usd
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(entry_id) DO UPDATE SET
                        transaction_hash = excluded.transaction_hash,
                        occurred_at = excluded.occurred_at,
                        token_address = excluded.token_address,
                        quote_address = excluded.quote_address,
                        token_amount = excluded.token_amount,
                        quote_amount = excluded.quote_amount,
                        trade_value_usd = excluded.trade_value_usd
                    """,
                    (
                        entry.entry_id,
                        entry.transaction_hash,
                        _serialize_time(entry.occurred_at),
                        entry.chain,
                        entry.token_address,
                        entry.quote_address,
                        str(entry.token_amount),
                        str(entry.quote_amount),
                        str(entry.trade_value_usd),
                    ),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO wallet_entries VALUES (?, ?)",
                    (wallet_address, entry.entry_id),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO job_entries VALUES (?, ?)",
                    (job_id, entry.entry_id),
                )

            connection.execute("DELETE FROM ambiguous_trades WHERE job_id = ?", (job_id,))
            connection.executemany(
                "INSERT INTO ambiguous_trades VALUES (?, ?, ?, ?)",
                [
                    (job_id, item.transaction_hash, item.reason.value, item.leg_count)
                    for item in ambiguous
                ],
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO evidence_records (
                    evidence_id, job_id, provider, endpoint, chain, subject_hash,
                    requested_from_utc, requested_to_utc, request_fingerprint,
                    response_hash, retrieved_at, adapter_version, methodology_version,
                    source_schema_version, request_id, page, per_page, is_last_page,
                    warnings_json, quoted_credits, used_credits, attempt_count, cache_hit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _evidence_values(evidence),
            )
            entry_count = connection.execute(
                "SELECT COUNT(*) FROM job_entries WHERE job_id = ?", (job_id,)
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE import_jobs
                SET next_page = ?, pages_fetched = pages_fetched + 1,
                    requests_attempted = ?, credits_used = ?, entries_saved = ?,
                    updated_at = ?
                WHERE job_id = ? AND status = ?
                """,
                (
                    next_page,
                    requests_attempted,
                    credits_used,
                    entry_count,
                    now,
                    job_id,
                    ImportStatus.RUNNING.value,
                ),
            )

    def record_failed_attempts(
        self,
        job_id: str,
        *,
        requests_attempted: int,
        credits_used: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE import_jobs
                SET requests_attempted = ?, credits_used = ?, updated_at = ?
                WHERE job_id = ? AND status = ?
                """,
                (
                    requests_attempted,
                    credits_used,
                    _serialize_time(datetime.now(UTC)),
                    job_id,
                    ImportStatus.RUNNING.value,
                ),
            )

    def finish_job(
        self,
        job_id: str,
        *,
        status: ImportStatus,
        coverage: CoverageState,
        error_code: str | None = None,
    ) -> ImportJob:
        if status in {ImportStatus.PENDING, ImportStatus.RUNNING}:
            raise ValueError("A finished job requires a terminal status.")
        now = _serialize_time(datetime.now(UTC))
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE import_jobs
                SET status = ?, coverage = ?, error_code = ?, updated_at = ?, completed_at = ?
                WHERE job_id = ? AND status = ?
                """,
                (
                    status.value,
                    coverage.value,
                    error_code,
                    now,
                    now,
                    job_id,
                    ImportStatus.RUNNING.value,
                ),
            )
        if cursor.rowcount == 0:
            raise ValueError("The import job is not running.")
        return self.get_job(job_id)

    def list_entries(self, wallet_address: str) -> tuple[TradeEntry, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT entry.* FROM trade_entries AS entry
                JOIN wallet_entries AS wallet ON wallet.entry_id = entry.entry_id
                WHERE wallet.wallet_address = ?
                ORDER BY entry.occurred_at DESC, entry.entry_id DESC
                """,
                (wallet_address,),
            ).fetchall()
        return tuple(_entry_from_row(row) for row in rows)

    def list_job_entries(self, job_id: str) -> tuple[TradeEntry, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT entry.* FROM trade_entries AS entry
                JOIN job_entries AS linked ON linked.entry_id = entry.entry_id
                WHERE linked.job_id = ?
                ORDER BY entry.occurred_at DESC, entry.entry_id DESC
                """,
                (job_id,),
            ).fetchall()
        return tuple(_entry_from_row(row) for row in rows)

    def create_review(self, scope: ReviewScope, *, now: datetime) -> ReviewJob:
        review_id = uuid.uuid4().hex
        timestamp = _serialize_time(now)
        quote_assets = [
            {"address": asset.address, "symbol": asset.symbol} for asset in scope.quote_assets
        ]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO review_jobs (
                    review_id, wallet_address, from_utc, to_utc, quote_assets_json,
                    max_entries, max_requests, max_credits, status, stage,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    scope.wallet_address,
                    _serialize_time(scope.from_utc),
                    _serialize_time(scope.to_utc),
                    json.dumps(quote_assets, separators=(",", ":"), sort_keys=True),
                    scope.max_entries,
                    scope.budget.max_requests,
                    scope.budget.max_credits,
                    ReviewStatus.PENDING.value,
                    ReviewStage.QUEUED.value,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_review(review_id)

    def get_review(self, review_id: str) -> ReviewJob:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_jobs WHERE review_id = ?", (review_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown review: {review_id}")
        return _review_from_row(row)

    def set_review_import(self, review_id: str, import_job_id: str) -> None:
        now = _serialize_time(datetime.now(UTC))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE review_jobs SET import_job_id = ?, updated_at = ?
                WHERE review_id = ? AND status IN (?, ?)
                """,
                (
                    import_job_id,
                    now,
                    review_id,
                    ReviewStatus.PENDING.value,
                    ReviewStatus.RUNNING.value,
                ),
            )
            cancellation = connection.execute(
                "SELECT cancellation_requested FROM review_jobs WHERE review_id = ?",
                (review_id,),
            ).fetchone()
            if cancellation is not None and cancellation[0]:
                connection.execute(
                    """
                    UPDATE import_jobs SET cancellation_requested = 1, updated_at = ?
                    WHERE job_id = ? AND status = ?
                    """,
                    (now, import_job_id, ImportStatus.RUNNING.value),
                )

    def set_review_stage(self, review_id: str, stage: ReviewStage) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE review_jobs SET status = ?, stage = ?, updated_at = ?
                WHERE review_id = ? AND status IN (?, ?)
                """,
                (
                    ReviewStatus.RUNNING.value,
                    stage.value,
                    _serialize_time(datetime.now(UTC)),
                    review_id,
                    ReviewStatus.PENDING.value,
                    ReviewStatus.RUNNING.value,
                ),
            )
        if cursor.rowcount == 0:
            raise ValueError("The review cannot transition to a running stage.")

    def request_review_cancellation(self, review_id: str) -> ReviewJob:
        now = _serialize_time(datetime.now(UTC))
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, import_job_id FROM review_jobs WHERE review_id = ?",
                (review_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown review: {review_id}")
            if row["status"] not in {
                ReviewStatus.PENDING.value,
                ReviewStatus.RUNNING.value,
            }:
                raise ValueError("Only an active review can be cancelled.")
            connection.execute(
                """
                UPDATE review_jobs SET cancellation_requested = 1, updated_at = ?
                WHERE review_id = ?
                """,
                (now, review_id),
            )
            if row["import_job_id"] is not None:
                connection.execute(
                    """
                    UPDATE import_jobs SET cancellation_requested = 1, updated_at = ?
                    WHERE job_id = ? AND status = ?
                    """,
                    (now, row["import_job_id"], ImportStatus.RUNNING.value),
                )
        return self.get_review(review_id)

    def review_cancellation_requested(self, review_id: str) -> bool:
        return self.get_review(review_id).cancellation_requested

    def attach_review_entries(self, review_id: str, entries: tuple[TradeEntry, ...]) -> None:
        with self._connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO review_entries VALUES (?, ?, ?)",
                [(review_id, entry.entry_id, ordinal) for ordinal, entry in enumerate(entries)],
            )
            connection.execute(
                """
                UPDATE review_jobs SET entries_total = ?, updated_at = ?
                WHERE review_id = ?
                """,
                (len(entries), _serialize_time(datetime.now(UTC)), review_id),
            )

    def save_review_entry(
        self,
        review_id: str,
        *,
        context: HistoricalContext,
        outcomes: tuple[OutcomeObservation, ...],
        evidence: tuple[ProviderEvidence, ...],
        requests_attempted: int,
        credits_used: int,
    ) -> None:
        now = _serialize_time(datetime.now(UTC))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO historical_contexts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(review_id, entry_id) DO UPDATE SET
                    window_from_utc = excluded.window_from_utc,
                    window_to_utc = excluded.window_to_utc,
                    coverage = excluded.coverage,
                    smart_trader_net_flow_usd = excluded.smart_trader_net_flow_usd,
                    smart_trader_avg_flow_usd = excluded.smart_trader_avg_flow_usd,
                    smart_trader_wallet_count = excluded.smart_trader_wallet_count,
                    warnings_json = excluded.warnings_json
                """,
                (
                    review_id,
                    context.entry_id,
                    _serialize_time(context.window.from_utc),
                    _serialize_time(context.window.to_utc),
                    context.coverage.value,
                    _decimal_or_none(context.smart_trader_net_flow_usd),
                    _decimal_or_none(context.smart_trader_avg_flow_usd),
                    context.smart_trader_wallet_count,
                    json.dumps(context.warnings, separators=(",", ":")),
                ),
            )
            for outcome in outcomes:
                connection.execute(
                    """
                    INSERT INTO outcome_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(review_id, entry_id, horizon) DO UPDATE SET
                        target_at = excluded.target_at,
                        state = excluded.state,
                        observed_at = excluded.observed_at,
                        observed_price_usd = excluded.observed_price_usd,
                        price_change_pct = excluded.price_change_pct
                    """,
                    (
                        review_id,
                        outcome.entry_id,
                        outcome.horizon.value,
                        _serialize_time(outcome.target_at),
                        outcome.state.value,
                        (
                            None
                            if outcome.observed_at is None
                            else _serialize_time(outcome.observed_at)
                        ),
                        _decimal_or_none(outcome.observed_price_usd),
                        _decimal_or_none(outcome.price_change_pct),
                    ),
                )
            for item in evidence:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO review_evidence VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        evidence_id(review_id, context.entry_id, item),
                        review_id,
                        context.entry_id,
                        item.kind,
                        "nansen",
                        item.endpoint,
                        item.subject_hash,
                        item.request_fingerprint,
                        item.response_hash,
                        _serialize_time(item.requested_from_utc),
                        _serialize_time(item.requested_to_utc),
                        _serialize_time(item.retrieved_at),
                        item.request_id,
                        json.dumps(item.warnings, separators=(",", ":")),
                        item.quoted_credits,
                        item.used_credits,
                        item.attempt_count,
                        int(item.truncated),
                        item.truncation_note,
                        "m3-nansen-v1",
                        "entryglass-methodology-v1",
                        # Reserved for forward-compatible evidence schema versioning.
                        "nansen-2026-09",
                    ),
                )
            connection.execute(
                """
                UPDATE review_jobs SET
                    entries_processed = (
                        SELECT COUNT(*) FROM historical_contexts WHERE review_id = ?
                    ),
                    requests_attempted = ?, credits_used = ?, updated_at = ?
                WHERE review_id = ?
                """,
                (review_id, requests_attempted, credits_used, now, review_id),
            )

    def update_review_accounting(
        self,
        review_id: str,
        *,
        requests_attempted: int,
        credits_used: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE review_jobs SET requests_attempted = ?, credits_used = ?, updated_at = ?
                WHERE review_id = ?
                """,
                (
                    requests_attempted,
                    credits_used,
                    _serialize_time(datetime.now(UTC)),
                    review_id,
                ),
            )

    def finish_review(
        self,
        review_id: str,
        *,
        status: ReviewStatus,
        error_code: str | None = None,
    ) -> ReviewJob:
        if status in {ReviewStatus.PENDING, ReviewStatus.RUNNING}:
            raise ValueError("A finished review requires a terminal status.")
        now = _serialize_time(datetime.now(UTC))
        stage = (
            ReviewStage.COMPLETE
            if status in {ReviewStatus.COMPLETE, ReviewStatus.PARTIAL}
            else ReviewStage.STOPPED
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE review_jobs SET status = ?, stage = ?, error_code = ?,
                    updated_at = ?, completed_at = ? WHERE review_id = ?
                """,
                (status.value, stage.value, error_code, now, now, review_id),
            )
        return self.get_review(review_id)

    def list_review_entries(self, review_id: str) -> tuple[TradeEntry, ...]:
        self.get_review(review_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT entry.* FROM trade_entries AS entry
                JOIN review_entries AS linked ON linked.entry_id = entry.entry_id
                WHERE linked.review_id = ? ORDER BY linked.ordinal
                """,
                (review_id,),
            ).fetchall()
        return tuple(_entry_from_row(row) for row in rows)

    def get_review_entry(self, review_id: str, entry_id: str) -> TradeEntry:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT entry.* FROM trade_entries AS entry
                JOIN review_entries AS linked ON linked.entry_id = entry.entry_id
                WHERE linked.review_id = ? AND linked.entry_id = ?
                """,
                (review_id, entry_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown review entry: {entry_id}")
        return _entry_from_row(row)

    def get_historical_context(self, review_id: str, entry_id: str) -> HistoricalContext | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM historical_contexts WHERE review_id = ? AND entry_id = ?
                """,
                (review_id, entry_id),
            ).fetchone()
        if row is None:
            return None
        return HistoricalContext(
            entry_id=entry_id,
            window=PreEntryWindow(
                from_utc=_parse_time(row["window_from_utc"]),
                to_utc=_parse_time(row["window_to_utc"]),
            ),
            smart_trader_net_flow_usd=_parse_decimal(row["smart_trader_net_flow_usd"]),
            smart_trader_avg_flow_usd=_parse_decimal(row["smart_trader_avg_flow_usd"]),
            smart_trader_wallet_count=row["smart_trader_wallet_count"],
            warnings=tuple(json.loads(row["warnings_json"])),
            coverage=ContextCoverage(row["coverage"]),
        )

    def list_outcomes(self, review_id: str, entry_id: str) -> tuple[OutcomeObservation, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM outcome_observations
                WHERE review_id = ? AND entry_id = ? ORDER BY target_at
                """,
                (review_id, entry_id),
            ).fetchall()
        return tuple(_outcome_from_row(row) for row in rows)

    def list_review_evidence(self, review_id: str, entry_id: str) -> tuple[ProviderEvidence, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_evidence
                WHERE review_id = ? AND entry_id = ? ORDER BY requested_from_utc, kind
                """,
                (review_id, entry_id),
            ).fetchall()
        return tuple(_provider_evidence_from_row(row) for row in rows)

    def create_preflight(
        self,
        review_id: str,
        token_address: str,
        horizon: str,
        *,
        now: datetime,
    ) -> PreflightJob:
        validate_solana_address(token_address)
        if horizon not in {"24h", "7d"}:
            raise ValueError("Preflight horizon must be 24h or 7d.")
        review = self.get_review(review_id)
        if review.status not in {ReviewStatus.COMPLETE, ReviewStatus.PARTIAL}:
            raise ValueError("Preflight requires a completed or partial review.")
        preflight_id = uuid.uuid4().hex
        timestamp = _serialize_time(now)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO preflight_jobs (
                    preflight_id, review_id, token_address, horizon, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    preflight_id,
                    review_id,
                    token_address,
                    horizon,
                    PreflightStatus.PENDING.value,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_preflight(preflight_id)

    def get_preflight(self, preflight_id: str) -> PreflightJob:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM preflight_jobs WHERE preflight_id = ?", (preflight_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown preflight: {preflight_id}")
        return _preflight_from_row(row)

    def set_preflight_running(self, preflight_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE preflight_jobs SET status = ?, updated_at = ?
                WHERE preflight_id = ? AND status = ?
                """,
                (
                    PreflightStatus.RUNNING.value,
                    _serialize_time(datetime.now(UTC)),
                    preflight_id,
                    PreflightStatus.PENDING.value,
                ),
            )
        if cursor.rowcount == 0:
            raise ValueError("The preflight is not pending.")

    def complete_preflight(
        self,
        preflight_id: str,
        *,
        context: CurrentContext,
        evidence: ProviderEvidence,
        requests_attempted: int,
        credits_used: int,
    ) -> PreflightJob:
        now = _serialize_time(datetime.now(UTC))
        identity = f"{preflight_id}:{evidence.request_fingerprint}"
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE preflight_jobs SET status = ?, timeframe = ?, coverage = ?,
                    observed_at = ?, smart_trader_net_flow_usd = ?,
                    smart_trader_avg_flow_usd = ?, smart_trader_wallet_count = ?,
                    warnings_json = ?, requests_attempted = ?, credits_used = ?,
                    updated_at = ?, completed_at = ?
                WHERE preflight_id = ? AND status = ?
                """,
                (
                    PreflightStatus.COMPLETE.value,
                    context.timeframe,
                    context.coverage.value,
                    _serialize_time(context.observed_at),
                    _decimal_or_none(context.smart_trader_net_flow_usd),
                    _decimal_or_none(context.smart_trader_avg_flow_usd),
                    context.smart_trader_wallet_count,
                    json.dumps(context.warnings, separators=(",", ":")),
                    requests_attempted,
                    credits_used,
                    now,
                    now,
                    preflight_id,
                    PreflightStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("The preflight is not running.")
            connection.execute(
                """
                INSERT OR IGNORE INTO preflight_evidence VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    hashlib.sha256(identity.encode()).hexdigest(),
                    preflight_id,
                    "nansen",
                    evidence.endpoint,
                    evidence.subject_hash,
                    evidence.request_fingerprint,
                    evidence.response_hash,
                    _serialize_time(evidence.requested_from_utc),
                    _serialize_time(evidence.requested_to_utc),
                    _serialize_time(evidence.retrieved_at),
                    evidence.request_id,
                    json.dumps(evidence.warnings, separators=(",", ":")),
                    evidence.quoted_credits,
                    evidence.used_credits,
                    evidence.attempt_count,
                    "nansen-current-flow-v1",
                    "smart-trader-flow-v1",
                ),
            )
        return self.get_preflight(preflight_id)

    def fail_preflight(
        self,
        preflight_id: str,
        *,
        error_code: str,
        requests_attempted: int,
        credits_used: int,
    ) -> PreflightJob:
        now = _serialize_time(datetime.now(UTC))
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE preflight_jobs SET status = ?, error_code = ?,
                    requests_attempted = ?, credits_used = ?, updated_at = ?, completed_at = ?
                WHERE preflight_id = ? AND status = ?
                """,
                (
                    PreflightStatus.FAILED.value,
                    error_code,
                    requests_attempted,
                    credits_used,
                    now,
                    now,
                    preflight_id,
                    PreflightStatus.RUNNING.value,
                ),
            )
        if cursor.rowcount == 0:
            raise ValueError("The preflight is not running.")
        return self.get_preflight(preflight_id)

    def get_preflight_evidence(self, preflight_id: str) -> ProviderEvidence | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM preflight_evidence WHERE preflight_id = ?",
                (preflight_id,),
            ).fetchone()
        if row is None:
            return None
        return ProviderEvidence(
            kind="current_context",
            endpoint=row["endpoint"],
            subject_hash=row["subject_hash"],
            request_fingerprint=row["request_fingerprint"],
            response_hash=row["response_hash"],
            requested_from_utc=_parse_time(row["requested_from_utc"]),
            requested_to_utc=_parse_time(row["requested_to_utc"]),
            retrieved_at=_parse_time(row["retrieved_at"]),
            request_id=row["request_id"],
            warnings=tuple(json.loads(row["warnings_json"])),
            quoted_credits=row["quoted_credits"],
            used_credits=row["used_credits"],
            attempt_count=row["attempt_count"],
        )

    def list_evidence(self, job_id: str) -> tuple[EvidenceRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM evidence_records WHERE job_id = ? ORDER BY page", (job_id,)
            ).fetchall()
        return tuple(_evidence_from_row(row) for row in rows)

    def list_ambiguities(self, job_id: str) -> tuple[tuple[str, str, int], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT transaction_hash, reason, leg_count FROM ambiguous_trades
                WHERE job_id = ? ORDER BY transaction_hash
                """,
                (job_id,),
            ).fetchall()
        return tuple((row[0], row[1], row[2]) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
            )
            applied = {
                row[0] for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for version, script in MIGRATIONS:
                if version in applied:
                    continue
                connection.executescript(
                    f"BEGIN IMMEDIATE;\n{script}\n"
                    f"INSERT INTO schema_migrations VALUES ({version});\nCOMMIT;"
                )


def _job_from_row(row: sqlite3.Row) -> ImportJob:
    return ImportJob(
        job_id=row["job_id"],
        scope_key=row["scope_key"],
        wallet_address=row["wallet_address"],
        from_utc=_parse_time(row["from_utc"]),
        to_utc=_parse_time(row["to_utc"]),
        status=ImportStatus(row["status"]),
        coverage=CoverageState(row["coverage"]),
        next_page=row["next_page"],
        pages_fetched=row["pages_fetched"],
        requests_attempted=row["requests_attempted"],
        credits_used=row["credits_used"],
        entries_saved=row["entries_saved"],
        cancellation_requested=bool(row["cancellation_requested"]),
        error_code=row["error_code"],
    )


def _review_from_row(row: sqlite3.Row) -> ReviewJob:
    return ReviewJob(
        review_id=row["review_id"],
        wallet_address=row["wallet_address"],
        from_utc=_parse_time(row["from_utc"]),
        to_utc=_parse_time(row["to_utc"]),
        status=ReviewStatus(row["status"]),
        stage=ReviewStage(row["stage"]),
        max_entries=row["max_entries"],
        max_requests=row["max_requests"],
        max_credits=row["max_credits"],
        entries_total=row["entries_total"],
        entries_processed=row["entries_processed"],
        requests_attempted=row["requests_attempted"],
        credits_used=row["credits_used"],
        import_job_id=row["import_job_id"],
        cancellation_requested=bool(row["cancellation_requested"]),
        error_code=row["error_code"],
    )


def _preflight_from_row(row: sqlite3.Row) -> PreflightJob:
    context = None
    if row["status"] == PreflightStatus.COMPLETE.value:
        context = CurrentContext(
            token_address=row["token_address"],
            observed_at=_parse_time(row["observed_at"]),
            timeframe=row["timeframe"],
            coverage=ContextCoverage(row["coverage"]),
            smart_trader_net_flow_usd=_parse_decimal(row["smart_trader_net_flow_usd"]),
            smart_trader_avg_flow_usd=_parse_decimal(row["smart_trader_avg_flow_usd"]),
            smart_trader_wallet_count=row["smart_trader_wallet_count"],
            warnings=tuple(json.loads(row["warnings_json"])),
        )
    return PreflightJob(
        preflight_id=row["preflight_id"],
        review_id=row["review_id"],
        token_address=row["token_address"],
        horizon=row["horizon"],
        status=PreflightStatus(row["status"]),
        created_at=_parse_time(row["created_at"]),
        updated_at=_parse_time(row["updated_at"]),
        requests_attempted=row["requests_attempted"],
        credits_used=row["credits_used"],
        error_code=row["error_code"],
        context=context,
    )


def _entry_from_row(row: sqlite3.Row) -> TradeEntry:
    return TradeEntry(
        entry_id=row["entry_id"],
        transaction_hash=row["transaction_hash"],
        occurred_at=_parse_time(row["occurred_at"]),
        token_address=row["token_address"],
        quote_address=row["quote_address"],
        token_amount=Decimal(row["token_amount"]),
        quote_amount=Decimal(row["quote_amount"]),
        trade_value_usd=Decimal(row["trade_value_usd"]),
        chain=row["chain"],
    )


def _outcome_from_row(row: sqlite3.Row) -> OutcomeObservation:
    return OutcomeObservation(
        entry_id=row["entry_id"],
        horizon=OutcomeHorizon(row["horizon"]),
        target_at=_parse_time(row["target_at"]),
        state=OutcomeState(row["state"]),
        observed_at=(None if row["observed_at"] is None else _parse_time(row["observed_at"])),
        observed_price_usd=_parse_decimal(row["observed_price_usd"]),
        price_change_pct=_parse_decimal(row["price_change_pct"]),
    )


def _provider_evidence_from_row(row: sqlite3.Row) -> ProviderEvidence:
    return ProviderEvidence(
        kind=row["kind"],
        endpoint=row["endpoint"],
        subject_hash=row["subject_hash"],
        request_fingerprint=row["request_fingerprint"],
        response_hash=row["response_hash"],
        requested_from_utc=_parse_time(row["requested_from_utc"]),
        requested_to_utc=_parse_time(row["requested_to_utc"]),
        retrieved_at=_parse_time(row["retrieved_at"]),
        request_id=row["request_id"],
        warnings=tuple(json.loads(row["warnings_json"])),
        quoted_credits=row["quoted_credits"],
        used_credits=row["used_credits"],
        attempt_count=row["attempt_count"],
        truncated=bool(row["truncated"]),
        truncation_note=row["truncation_note"],
    )


def _decimal_or_none(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _parse_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _leg_to_mapping(leg: SwapLeg) -> dict[str, str]:
    return {
        "transaction_hash": leg.transaction_hash,
        "occurred_at": _serialize_time(leg.occurred_at),
        "bought_address": leg.bought_address,
        "bought_amount": str(leg.bought_amount),
        "sold_address": leg.sold_address,
        "sold_amount": str(leg.sold_amount),
        "trade_value_usd": str(leg.trade_value_usd),
    }


def _leg_from_mapping(value: dict[str, str]) -> SwapLeg:
    return SwapLeg(
        transaction_hash=value["transaction_hash"],
        occurred_at=_parse_time(value["occurred_at"]),
        bought_address=value["bought_address"],
        bought_amount=Decimal(value["bought_amount"]),
        sold_address=value["sold_address"],
        sold_amount=Decimal(value["sold_amount"]),
        trade_value_usd=Decimal(value["trade_value_usd"]),
    )


def _evidence_values(record: EvidenceRecord) -> tuple[object, ...]:
    return (
        record.evidence_id,
        record.job_id,
        record.provider,
        record.endpoint,
        record.chain,
        record.subject_hash,
        _serialize_time(record.requested_from_utc),
        _serialize_time(record.requested_to_utc),
        record.request_fingerprint,
        record.response_hash,
        _serialize_time(record.retrieved_at),
        record.adapter_version,
        record.methodology_version,
        record.source_schema_version,
        record.request_id,
        record.page,
        record.per_page,
        None if record.is_last_page is None else int(record.is_last_page),
        json.dumps(record.warnings, separators=(",", ":")),
        record.quoted_credits,
        record.used_credits,
        record.attempt_count,
        int(record.cache_hit),
    )


def _evidence_from_row(row: sqlite3.Row) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=row["evidence_id"],
        job_id=row["job_id"],
        provider=row["provider"],
        endpoint=row["endpoint"],
        chain=row["chain"],
        subject_hash=row["subject_hash"],
        requested_from_utc=_parse_time(row["requested_from_utc"]),
        requested_to_utc=_parse_time(row["requested_to_utc"]),
        request_fingerprint=row["request_fingerprint"],
        response_hash=row["response_hash"],
        retrieved_at=_parse_time(row["retrieved_at"]),
        adapter_version=row["adapter_version"],
        methodology_version=row["methodology_version"],
        source_schema_version=row["source_schema_version"],
        request_id=row["request_id"],
        page=row["page"],
        per_page=row["per_page"],
        is_last_page=None if row["is_last_page"] is None else bool(row["is_last_page"]),
        warnings=tuple(json.loads(row["warnings_json"])),
        quoted_credits=row["quoted_credits"],
        used_credits=row["used_credits"],
        attempt_count=row["attempt_count"],
        cache_hit=bool(row["cache_hit"]),
    )


def _serialize_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("SQLite timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)

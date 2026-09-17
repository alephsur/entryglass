"""Explicit, budgeted local command for M2 wallet ingestion."""

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from entryglass.application.ingestion import ImportScope, ImportWalletEntries, RequestBudget
from entryglass.core.config import Settings
from entryglass.domain.evidence import ImportJob, ImportStatus
from entryglass.domain.trades import QuoteAsset
from entryglass.infrastructure.nansen.ingestion import NansenIngestionClient
from entryglass.infrastructure.storage import SqliteIngestionRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or inspect a private wallet-entry import.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Plan or execute one bounded import.")
    run.add_argument("--execute", action="store_true")
    run.add_argument("--address", required=True)
    run.add_argument("--from", dest="from_utc", type=_utc_timestamp, required=True)
    run.add_argument("--to", dest="to_utc", type=_utc_timestamp, required=True)
    run.add_argument(
        "--quote",
        type=_quote_asset,
        action="append",
        required=True,
        help="Quote identity as SOLANA_ADDRESS=SYMBOL; repeat when needed.",
    )
    run.add_argument("--max-requests", type=int, required=True)
    run.add_argument("--max-credits", type=int, required=True)
    run.add_argument("--max-entries", type=int, default=30)
    run.add_argument("--page-size", type=int, default=100)
    run.add_argument("--database", type=Path)

    status = subparsers.add_parser("status", help="Read one persisted import status.")
    status.add_argument("--job-id", required=True)
    status.add_argument("--database", type=Path)

    cancel = subparsers.add_parser("cancel", help="Request cancellation of a running import.")
    cancel.add_argument("--job-id", required=True)
    cancel.add_argument("--database", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings()
    database_path = args.database or settings.database_path

    if args.command == "status":
        try:
            job = SqliteIngestionRepository(database_path).get_job(args.job_id)
        except KeyError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps(_job_summary(job), indent=2, sort_keys=True))
        return 0

    if args.command == "cancel":
        try:
            SqliteIngestionRepository(database_path).request_cancellation(args.job_id)
        except (KeyError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps({"job_id": args.job_id, "cancellation_requested": True}))
        return 0

    try:
        scope = ImportScope(
            wallet_address=args.address,
            from_utc=args.from_utc,
            to_utc=args.to_utc,
            quote_assets=tuple(args.quote),
            budget=RequestBudget(
                max_requests=args.max_requests,
                max_credits=args.max_credits,
            ),
            max_entries=args.max_entries,
            page_size=args.page_size,
        )
    except ValueError as error:
        print(f"Invalid import scope: {error}", file=sys.stderr)
        return 2

    if not args.execute:
        print(json.dumps(_dry_run(scope, database_path), indent=2, sort_keys=True))
        return 0
    if settings.nansen_api_key is None:
        print("Refusing import: NANSEN_API_KEY is not configured.", file=sys.stderr)
        return 2

    repository = SqliteIngestionRepository(database_path)
    try:
        with NansenIngestionClient(
            api_key=settings.nansen_api_key,
            base_url=str(settings.nansen_base_url),
            timeout_seconds=settings.nansen_timeout_seconds,
            max_concurrency=settings.nansen_max_concurrency,
        ) as provider:
            job = ImportWalletEntries(provider=provider, repository=repository).execute(
                scope,
                on_job_created=_announce_job,
            )
    except (httpx.NetworkError, OSError) as error:
        print(f"Import could not start: {type(error).__name__}", file=sys.stderr)
        return 1

    print(json.dumps(_job_summary(job), indent=2, sort_keys=True))
    return 0 if job.status is ImportStatus.COMPLETE else 1


def _dry_run(scope: ImportScope, database_path: Path) -> dict[str, object]:
    return {
        "mode": "dry_run",
        "chain": scope.chain,
        "wallet_fingerprint": hashlib.sha256(scope.wallet_address.encode()).hexdigest(),
        "window": {
            "from": _serialize_time(scope.from_utc),
            "to": _serialize_time(scope.to_utc),
        },
        "quote_fingerprints": [
            hashlib.sha256(asset.address.encode()).hexdigest() for asset in scope.quote_assets
        ],
        "max_entries": scope.max_entries,
        "page_size": scope.page_size,
        "max_requests": scope.budget.max_requests,
        "max_credits": scope.budget.max_credits,
        "database": str(database_path),
        "notice": "No database was opened, no request was sent, and no credits were consumed.",
    }


def _job_summary(job: ImportJob) -> dict[str, object]:
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "coverage": job.coverage.value,
        "pages_processed": job.pages_fetched,
        "requests_attempted": job.requests_attempted,
        "credits_used": job.credits_used,
        "entries_saved": job.entries_saved,
        "error_code": job.error_code,
    }


def _announce_job(job: ImportJob) -> None:
    print(
        json.dumps({"event": "started", "job_id": job.job_id}),
        file=sys.stderr,
        flush=True,
    )


def _utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use an ISO 8601 timestamp.") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("Timestamp must include a UTC offset or Z.")
    return parsed.astimezone(UTC)


def _quote_asset(value: str) -> QuoteAsset:
    try:
        address, symbol = value.rsplit("=", 1)
        return QuoteAsset(address=address, symbol=symbol)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use SOLANA_ADDRESS=SYMBOL.") from error


def _serialize_time(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())

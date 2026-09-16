"""Opt-in command for one redacted Nansen contract-validation request."""

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime

import httpx

from entryglass.application.provider import (
    ProviderEndpoint,
    ProviderValidationRequest,
    UtcWindow,
)
from entryglass.core.config import Settings
from entryglass.infrastructure.nansen.client import (
    NansenClient,
    NansenContractError,
    NansenProviderError,
)
from entryglass.infrastructure.nansen.contracts import (
    DOCUMENTED_CREDIT_COSTS,
    ENDPOINT_PATHS,
)


def _utc_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use an ISO 8601 timestamp.") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("Timestamp must include a UTC offset or Z.")
    return parsed.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate one Nansen response contract. Dry-run is the default; "
            "--execute can consume provider credits."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Send exactly one authenticated provider request.",
    )
    parser.add_argument(
        "--max-credits",
        type=int,
        default=0,
        help="Explicit credit ceiling; must cover the documented endpoint cost.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dex = subparsers.add_parser("dex-trades", help="Validate wallet DEX-trade history.")
    dex.add_argument("--address", required=True)
    _add_window(dex)

    flow = subparsers.add_parser(
        "historical-flow", help="Validate a historical token-flow summary."
    )
    flow.add_argument("--token", required=True)
    _add_window(flow)

    who = subparsers.add_parser(
        "historical-who", help="Validate historical who-bought/sold evidence."
    )
    who.add_argument("--token", required=True)
    who.add_argument("--side", choices=("BUY", "SELL"), required=True)
    _add_window(who)
    return parser


def _add_window(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="from_utc", type=_utc_timestamp, required=True)
    parser.add_argument("--to", dest="to_utc", type=_utc_timestamp, required=True)


def _request_from_args(args: argparse.Namespace) -> ProviderValidationRequest:
    endpoint_by_command = {
        "dex-trades": ProviderEndpoint.WALLET_DEX_TRADES,
        "historical-flow": ProviderEndpoint.HISTORICAL_FLOW,
        "historical-who": ProviderEndpoint.HISTORICAL_WHO_BOUGHT_SOLD,
    }
    subject = args.address if args.command == "dex-trades" else args.token
    return ProviderValidationRequest(
        endpoint=endpoint_by_command[args.command],
        subject=subject,
        window=UtcWindow(args.from_utc, args.to_utc),
        side=getattr(args, "side", None),
    )


def _redacted_plan(request: ProviderValidationRequest) -> dict[str, object]:
    subject_hash = hashlib.sha256(request.subject.encode()).hexdigest()
    return {
        "mode": "dry_run",
        "endpoint": request.endpoint,
        "path": ENDPOINT_PATHS[request.endpoint],
        "documented_credit_cost": DOCUMENTED_CREDIT_COSTS[request.endpoint],
        "chain": request.chain,
        "window": request.window.as_provider_date_range(),
        "side": request.side,
        "subject_fingerprint": subject_hash,
        "notice": "No request was sent and no credits were consumed.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        request = _request_from_args(args)
    except ValueError as error:
        parser.error(str(error))

    if not args.execute:
        print(json.dumps(_redacted_plan(request), indent=2, sort_keys=True))
        return 0

    documented_cost = DOCUMENTED_CREDIT_COSTS[request.endpoint]
    if args.max_credits < documented_cost:
        print(
            f"Refusing request: --max-credits must be at least {documented_cost} "
            f"for {request.endpoint}.",
            file=sys.stderr,
        )
        return 2

    settings = Settings()
    if settings.nansen_api_key is None:
        print("Refusing request: NANSEN_API_KEY is not configured.", file=sys.stderr)
        return 2

    try:
        with NansenClient(
            api_key=settings.nansen_api_key,
            base_url=str(settings.nansen_base_url),
        ) as provider:
            result = provider.validate(request)
    except (
        NansenProviderError,
        NansenContractError,
        httpx.TimeoutException,
        httpx.NetworkError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

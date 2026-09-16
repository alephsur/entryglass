"""Small Nansen HTTP adapter for explicitly requested provider validation."""

import hashlib
import json
from time import perf_counter
from types import TracebackType
from typing import Self

import httpx
from pydantic import SecretStr, ValidationError

from entryglass.application.provider import (
    ProviderResponseMetadata,
    ProviderValidationRequest,
)
from entryglass.infrastructure.nansen.contracts import (
    ENDPOINT_PATHS,
    ValidationEnvelope,
    build_payload,
)


class NansenProviderError(RuntimeError):
    """A redacted provider failure safe to show in local command output."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str | None,
        request_id: str | None,
        quoted_credits: str | None,
        used_credits: str | None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.quoted_credits = quoted_credits
        self.used_credits = used_credits
        safe_code = code if code is not None else "unknown"
        super().__init__(
            f"Nansen request failed (status={status_code}, code={safe_code}, "
            f"request_id={request_id or 'missing'})."
        )


class NansenContractError(RuntimeError):
    """The provider returned a successful response with an unexpected envelope."""


class NansenClient:
    """Execute one bounded request without logging credentials or provider rows."""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        timeout_seconds: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "apikey": api_key.get_secret_value(),
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def validate(self, request: ProviderValidationRequest) -> ProviderResponseMetadata:
        """Call one endpoint and retain only redacted contract metadata."""
        path = ENDPOINT_PATHS[request.endpoint]
        payload = build_payload(request)
        encoded_request = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        request_fingerprint = hashlib.sha256(encoded_request).hexdigest()

        started = perf_counter()
        response = self._client.post(path, json=payload)
        latency_ms = round((perf_counter() - started) * 1000)
        response_hash = hashlib.sha256(response.content).hexdigest()
        headers = response.headers
        request_id = headers.get("x-request-id")
        quoted_credits = headers.get("x-nansen-credits-cost")
        used_credits = headers.get("x-nansen-credits-used")

        if response.status_code != httpx.codes.OK:
            raise NansenProviderError(
                status_code=response.status_code,
                code=_safe_error_code(response),
                request_id=request_id,
                quoted_credits=quoted_credits,
                used_credits=used_credits,
            )

        try:
            envelope = ValidationEnvelope.model_validate(response.json())
        except (json.JSONDecodeError, ValidationError) as error:
            raise NansenContractError(
                "Nansen returned HTTP 200 with an unexpected response envelope."
            ) from error

        fields = tuple(sorted({field for row in envelope.data for field in row}))
        pagination = envelope.pagination
        return ProviderResponseMetadata(
            endpoint=request.endpoint,
            path=path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            record_count=len(envelope.data),
            response_fields=fields,
            warning_count=len(envelope.warnings or []),
            page=pagination.page if pagination is not None else None,
            per_page=pagination.per_page if pagination is not None else None,
            is_last_page=pagination.is_last_page if pagination is not None else None,
            request_id=request_id,
            quoted_credits=quoted_credits,
            used_credits=used_credits,
            remaining_credits=headers.get("x-nansen-credits-remaining"),
            rate_limit_remaining=(
                headers.get("x-rate-limit-remaining") or headers.get("ratelimit-remaining")
            ),
            request_fingerprint=request_fingerprint,
            response_hash=response_hash,
        )


def _safe_error_code(response: httpx.Response) -> str | None:
    """Extract only a machine code, never a provider message or echoed input."""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    nested_error = payload.get("error")
    if not isinstance(code, str) and isinstance(nested_error, dict):
        code = nested_error.get("code")
    if not isinstance(code, str) or not code.replace("_", "").replace("-", "").isalnum():
        return None
    return code[:80]

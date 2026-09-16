"""Nansen-specific request DTOs checked against the public OpenAPI schemas."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from entryglass.application.provider import ProviderEndpoint, ProviderValidationRequest


class HistoricalLabel(StrEnum):
    """Documented temporal labels, kept distinct instead of collapsed into one cohort."""

    SMART_TRADER = "Smart Trader"
    SMART_TRADER_30D = "30D Smart Trader"
    SMART_TRADER_90D = "90D Smart Trader"
    SMART_TRADER_180D = "180D Smart Trader"
    SMART_DEX_TRADER = "Smart Dex Trader"
    SMART_DEX_TRADER_30D = "30D Smart Dex Trader"
    SMART_DEX_TRADER_90D = "90D Smart Dex Trader"
    SMART_DEX_TRADER_180D = "180D Smart Dex Trader"


class PaginationEnvelope(BaseModel):
    """Pagination fields returned by paginated Nansen endpoints."""

    model_config = ConfigDict(extra="ignore")

    page: int
    per_page: int
    is_last_page: bool


class ValidationEnvelope(BaseModel):
    """Minimal response envelope used without retaining provider row values."""

    model_config = ConfigDict(extra="ignore")

    data: list[dict[str, Any]]
    pagination: PaginationEnvelope | None = None
    warnings: list[str] | None = None


class DateRangeDto(BaseModel):
    """The provider spells the lower bound `from`."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str


class PaginationDto(BaseModel):
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=1000)


class DexTradesRequestDto(BaseModel):
    address: str
    chain: Literal["solana"]
    date: DateRangeDto
    pagination: PaginationDto
    order_by: list[dict[str, str]]


class HistoricalFlowRequestDto(BaseModel):
    chain: Literal["solana"]
    token_address: str
    date_range: DateRangeDto
    apply_blacklist_filter: bool = True


class HistoricalWhoBoughtSoldFilters(BaseModel):
    include_labels: list[HistoricalLabel]


class HistoricalWhoBoughtSoldRequestDto(BaseModel):
    chain: Literal["solana"]
    token_address: str
    date_range: DateRangeDto
    buy_or_sell: Literal["BUY", "SELL"]
    pagination: PaginationDto
    filters: HistoricalWhoBoughtSoldFilters
    order_by: list[dict[str, str]]


ENDPOINT_PATHS: dict[ProviderEndpoint, str] = {
    ProviderEndpoint.WALLET_DEX_TRADES: "/api/v1/profiler/dex-trades",
    ProviderEndpoint.HISTORICAL_FLOW: "/api/v1beta1/tgm/historical-token-flow-summary",
    ProviderEndpoint.HISTORICAL_WHO_BOUGHT_SOLD: ("/api/v1beta1/tgm/historical-who-bought-sold"),
}

DOCUMENTED_CREDIT_COSTS: dict[ProviderEndpoint, int] = {
    ProviderEndpoint.WALLET_DEX_TRADES: 1,
    ProviderEndpoint.HISTORICAL_FLOW: 5,
    ProviderEndpoint.HISTORICAL_WHO_BOUGHT_SOLD: 5,
}


def build_payload(request: ProviderValidationRequest) -> dict[str, Any]:
    """Map the application request to the exact provider DTO for its endpoint."""
    date_range = DateRangeDto(
        **request.window.as_provider_date_range(),
    )
    pagination = PaginationDto(page=request.page, per_page=request.per_page)

    if request.endpoint is ProviderEndpoint.WALLET_DEX_TRADES:
        dto: BaseModel = DexTradesRequestDto(
            address=request.subject,
            chain=request.chain,
            date=date_range,
            pagination=pagination,
            order_by=[{"field": "block_timestamp", "direction": "DESC"}],
        )
    elif request.endpoint is ProviderEndpoint.HISTORICAL_FLOW:
        dto = HistoricalFlowRequestDto(
            chain=request.chain,
            token_address=request.subject,
            date_range=date_range,
        )
    else:
        sort_field = "bought_volume_usd" if request.side == "BUY" else "sold_volume_usd"
        dto = HistoricalWhoBoughtSoldRequestDto(
            chain=request.chain,
            token_address=request.subject,
            date_range=date_range,
            buy_or_sell=request.side,
            pagination=pagination,
            filters=HistoricalWhoBoughtSoldFilters(include_labels=[HistoricalLabel.SMART_TRADER]),
            order_by=[{"field": sort_field, "direction": "DESC"}],
        )

    return dto.model_dump(mode="json", by_alias=True, exclude_none=True)

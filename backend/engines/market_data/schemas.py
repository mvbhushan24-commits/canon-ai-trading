"""Canonical schemas for the Market Data Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EngineConnectionStatus(StrEnum):
    """Connection state exposed by the Market Data Engine."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    ERROR = "error"


class NormalizedTick(BaseModel):
    """Normalized tick output independent of MT5."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    bid: Decimal
    ask: Decimal
    spread: Decimal
    timestamp_utc: datetime
    source: str = "mt5_xmglobal"


class NormalizedCandle(BaseModel):
    """Normalized OHLCV candle output independent of MT5."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    open_time_utc: datetime
    close_time_utc: datetime
    is_closed: bool


class EngineStatus(BaseModel):
    """Operational status of the Market Data Engine."""

    status: EngineConnectionStatus
    last_tick_utc: datetime | None = None
    last_error: str | None = None
    latency_ms: int | None = None


class SymbolMetadata(BaseModel):
    """Metadata for a broker symbol."""

    symbol: str
    description: str
    digits: int
    point: Decimal
    trade_mode: int
    visible: bool
    session_deals: int
    session_buy_orders: int
    session_sell_orders: int


class HistoryRequest(BaseModel):
    """On-demand historical data request."""

    symbol: str
    timeframe: str
    from_utc: datetime
    to_utc: datetime
    request_id: str | None = None


class HistoryResponse(BaseModel):
    """On-demand historical data response."""

    request_id: str | None = None
    symbol: str
    timeframe: str
    candles: list[NormalizedCandle] = Field(default_factory=list)
    bar_count: int = 0
    from_utc: datetime | None = None
    to_utc: datetime | None = None
    error: str | None = None


class GapInfo(BaseModel):
    """Detected gap in candle sequence."""

    symbol: str
    timeframe: str
    gap_start_utc: datetime
    gap_end_utc: datetime
    missing_bars: int


class ValidationResult(BaseModel):
    """Result of candle data validation."""

    is_valid: bool
    gaps: list[GapInfo] = Field(default_factory=list)
    duplicate_count: int = 0
    invalid_timestamp_count: int = 0
    invalid_ohlc_count: int = 0
    errors: list[str] = Field(default_factory=list)

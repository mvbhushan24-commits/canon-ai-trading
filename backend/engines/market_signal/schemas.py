"""Canonical schemas for the Market Signal Engine."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.engines.market_decision import EvidenceSummaryItem, QualityTier, RiskSummary

PIPELINE_VERSION = "0.1.0"

EXPECTED_EVIDENCE_ENGINES = 8


class SignalState(StrEnum):
    """Signal lifecycle states."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    TP1_HIT = "TP1_HIT"
    TP2_HIT = "TP2_HIT"
    TP3_HIT = "TP3_HIT"
    BREAK_EVEN = "BREAK_EVEN"
    TRAILING = "TRAILING"
    STOP_LOSS = "STOP_LOSS"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


TERMINAL_SIGNAL_STATES = frozenset(
    {
        SignalState.STOP_LOSS,
        SignalState.CLOSED,
        SignalState.EXPIRED,
        SignalState.CANCELLED,
    },
)

TRADEABLE_SIGNAL_STATES = frozenset(
    {
        SignalState.ACTIVE,
        SignalState.TRIGGERED,
        SignalState.PARTIALLY_FILLED,
        SignalState.TP1_HIT,
        SignalState.TP2_HIT,
        SignalState.TP3_HIT,
        SignalState.BREAK_EVEN,
        SignalState.TRAILING,
    },
)


class SignalDirection(StrEnum):
    """Trade signal direction."""

    BUY = "BUY"
    SELL = "SELL"


class SignalMetadata(BaseModel):
    """Pipeline execution metadata for signals."""

    model_config = ConfigDict(frozen=True)

    pipeline_version: str = PIPELINE_VERSION
    config_hash: str = ""
    duration_ms: int = 0
    decision_id: str = ""
    decision_timestamp_utc: datetime | None = None
    entry_type: str = ""
    tp_count: int = 0
    duplicate_check_passed: bool = True


class TradingSignal(BaseModel):
    """Primary trading signal output."""

    model_config = ConfigDict(frozen=True)

    signal_id: str
    decision_id: str
    timestamp_utc: datetime
    symbol: str
    timeframe: str
    direction: SignalDirection
    state: SignalState
    entry_price: Decimal
    stop_loss: Decimal
    take_profit_1: Decimal
    take_profit_2: Decimal | None = None
    take_profit_3: Decimal | None = None
    risk_reward: Decimal
    confidence: int
    signal_quality: int
    quality_tier: QualityTier
    reasons: list[str] = Field(default_factory=list)
    evidence_summary: list[EvidenceSummaryItem] = Field(default_factory=list)
    risk_summary: RiskSummary = Field(default_factory=RiskSummary)
    warnings: list[str] = Field(default_factory=list)
    expiry_time: datetime
    metadata: SignalMetadata = Field(default_factory=SignalMetadata)


class SignalRejection(BaseModel):
    """Signal creation rejection record."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    symbol: str
    timestamp_utc: datetime
    error_codes: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    decision_state: str = ""
    metadata: SignalMetadata = Field(default_factory=SignalMetadata)


class SignalCreationResult(BaseModel):
    """Result of signal creation pipeline."""

    model_config = ConfigDict(frozen=True)

    accepted: bool
    signal: TradingSignal | None = None
    rejection: SignalRejection | None = None
    decision_state: str = ""
    duration_ms: int = 0


class ValidationGateResult(BaseModel):
    """Validation gate outcome."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    error_code: str | None = None
    blocking_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class NormalizedLevels(BaseModel):
    """Entry and take-profit levels resolved from a decision."""

    model_config = ConfigDict(frozen=True)

    entry_price: Decimal
    take_profit_1: Decimal
    take_profit_2: Decimal | None = None
    take_profit_3: Decimal | None = None
    entry_type: str = ""
    tp_count: int = 0


class LifecycleUpdateResult(BaseModel):
    """Lifecycle state transition result."""

    model_config = ConfigDict(frozen=True)

    signal_id: str
    prior_state: SignalState
    current_state: SignalState
    transition_reason: str
    current_price: Decimal
    timestamp_utc: datetime

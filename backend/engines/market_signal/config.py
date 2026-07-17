"""Market Signal Engine configuration."""

from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config

SUPPORTED_SYMBOLS = frozenset({"XAUUSD", "GOLD.i#"})
SUPPORTED_TIMEFRAMES = frozenset({"M1", "M5", "M15", "M30", "H1", "H4", "D1"})


class ValidationConfig(BaseModel):
    """Signal validation thresholds."""

    min_confidence: int = 65
    min_decision_quality: int = 60
    require_evidence_summary: bool = True
    require_risk_summary: bool = True

    @field_validator("min_confidence", "min_decision_quality")
    @classmethod
    def _validate_range(cls, value: int) -> int:
        if not 0 <= value <= 100:
            msg = "validation confidence/quality values must be between 0 and 100"
            raise ValueError(msg)
        return value


class DuplicateConfig(BaseModel):
    """Duplicate signal detection settings."""

    enabled: bool = True
    window_minutes: int = 60
    entry_tolerance_pips: float = 5.0
    reject_same_decision_id: bool = True

    @field_validator("window_minutes")
    @classmethod
    def _validate_window(cls, value: int) -> int:
        if value <= 0:
            msg = "duplicate.window_minutes must be positive"
            raise ValueError(msg)
        return value


class SessionConfig(BaseModel):
    """Decision-derived session validation."""

    enabled: bool = True
    blocked_sessions: list[str] = Field(default_factory=list)
    require_session_allowed: bool = True


class RiskConfig(BaseModel):
    """Decision-derived risk validation."""

    min_risk_reward: float = 2.0
    max_risk_reward: float = 8.0
    require_min_rr_met: bool = True
    require_max_rr_met: bool = True
    require_spread_acceptable: bool = True
    require_stop_size_acceptable: bool = True
    require_confidence_acceptable: bool = True


class EntryConfig(BaseModel):
    """Entry normalization settings."""

    zone_resolution: str = "midpoint"
    buy_zone_edge: str = "zone_low"
    sell_zone_edge: str = "zone_high"


class TakeProfitConfig(BaseModel):
    """Take profit mapping settings."""

    max_targets: int = 3
    require_minimum_one: bool = True


class QualityWeights(BaseModel):
    """Signal quality dimension weights."""

    decision_confidence: float = 0.25
    decision_quality: float = 0.20
    risk_clarity: float = 0.15
    entry_precision: float = 0.10
    target_structure: float = 0.10
    evidence_completeness: float = 0.10
    explainability: float = 0.10

    @model_validator(mode="after")
    def _validate_sum(self) -> "QualityWeights":
        total = (
            self.decision_confidence
            + self.decision_quality
            + self.risk_clarity
            + self.entry_precision
            + self.target_structure
            + self.evidence_completeness
            + self.explainability
        )
        if abs(total - 1.0) > 0.001:
            msg = f"quality weights must sum to 1.0 (±0.001), got {total}"
            raise ValueError(msg)
        return self


class QualityAdjustments(BaseModel):
    """Signal quality score adjustments."""

    duplicate_proximity_penalty: int = 10
    stale_decision_penalty_max: int = 15
    warning_penalty_per_item: int = 2
    warning_penalty_max: int = 10
    multi_tp_bonus: int = 5


class QualityTierThresholds(BaseModel):
    """Quality tier thresholds."""

    high: int = 80
    medium: int = 60

    @model_validator(mode="after")
    def _validate_order(self) -> "QualityTierThresholds":
        if self.high <= self.medium or self.medium <= 0:
            msg = "quality tiers must satisfy high > medium > 0"
            raise ValueError(msg)
        return self


class EntryPrecisionScores(BaseModel):
    """Entry type precision scores."""

    point: int = 100
    ote: int = 85
    zone: int = 70


class TargetStructureScores(BaseModel):
    """Take profit count structure scores."""

    one_tp: int = 60
    two_tp: int = 80
    three_tp: int = 100


class QualityConfig(BaseModel):
    """Signal quality scoring configuration."""

    min_signal_quality: int = 0
    weights: QualityWeights = Field(default_factory=QualityWeights)
    adjustments: QualityAdjustments = Field(default_factory=QualityAdjustments)
    tiers: QualityTierThresholds = Field(default_factory=QualityTierThresholds)
    entry_precision_scores: EntryPrecisionScores = Field(default_factory=EntryPrecisionScores)
    target_structure_scores: TargetStructureScores = Field(default_factory=TargetStructureScores)

    @field_validator("min_signal_quality")
    @classmethod
    def _validate_min_quality(cls, value: int) -> int:
        if not 0 <= value <= 100:
            msg = "quality.min_signal_quality must be between 0 and 100"
            raise ValueError(msg)
        return value


class BreakEvenConfig(BaseModel):
    """Break-even lifecycle rule."""

    enabled: bool = True
    trigger_after: str = "TP1_HIT"
    offset_pips: float = 1.0


class TrailingConfig(BaseModel):
    """Trailing stop lifecycle rule."""

    enabled: bool = False
    trigger_after: str = "TP1_HIT"
    trail_distance_pips: float = 15.0
    step_pips: float = 5.0


class PartialFillConfig(BaseModel):
    """Partial fill tracking."""

    enabled: bool = False
    default_fill_pct: int = 50


class TriggerConfig(BaseModel):
    """Price trigger mode and tolerance."""

    mode: str = "touch"
    tolerance_pips: float = 1.0


class LifecycleConfig(BaseModel):
    """Signal lifecycle management."""

    enabled: bool = True
    break_even: BreakEvenConfig = Field(default_factory=BreakEvenConfig)
    trailing: TrailingConfig = Field(default_factory=TrailingConfig)
    partial_fill: PartialFillConfig = Field(default_factory=PartialFillConfig)
    entry_trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    tp_trigger: TriggerConfig = Field(default_factory=lambda: TriggerConfig(tolerance_pips=0.5))
    sl_trigger: TriggerConfig = Field(default_factory=lambda: TriggerConfig(tolerance_pips=0.5))


class EventsConfig(BaseModel):
    """Event publishing settings."""

    publish_rejections: bool = False
    publish_lifecycle_events: bool = True


class PersistenceConfig(BaseModel):
    """Optional signal persistence."""

    enabled: bool = True
    sqlite_table: str = "signals"
    retain_days: int = 90
    store_rejections: bool = False


class MarketSignalConfig(BaseModel):
    """Configuration for institutional signal conversion."""

    enabled: bool = True
    symbol: str = "GOLD.i#"
    timeframe: str = "M15"
    pip_size: float = 0.1
    auto_activate: bool = True
    signal_validity_minutes: int = 60
    max_decision_age_seconds: int = 300
    debounce_seconds: int = 3
    raise_on_error: bool = False
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    duplicate: DuplicateConfig = Field(default_factory=DuplicateConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    entry: EntryConfig = Field(default_factory=EntryConfig)
    take_profit: TakeProfitConfig = Field(default_factory=TakeProfitConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    lifecycle: LifecycleConfig = Field(default_factory=LifecycleConfig)
    events: EventsConfig = Field(default_factory=EventsConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        normalized = value.strip()
        if normalized.upper() not in SUPPORTED_SYMBOLS and normalized not in SUPPORTED_SYMBOLS:
            msg = f"symbol must be one of {sorted(SUPPORTED_SYMBOLS)}"
            raise ValueError(msg)
        return normalized

    @field_validator("timeframe")
    @classmethod
    def _validate_timeframe(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in SUPPORTED_TIMEFRAMES:
            msg = f"timeframe must be one of {sorted(SUPPORTED_TIMEFRAMES)}"
            raise ValueError(msg)
        return normalized

    @field_validator("pip_size")
    @classmethod
    def _validate_pip_size(cls, value: float) -> float:
        if value <= 0:
            msg = "pip_size must be positive"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_bounds(self) -> "MarketSignalConfig":
        if self.risk.min_risk_reward <= 0:
            msg = "risk.min_risk_reward must be positive"
            raise ValueError(msg)
        if self.risk.max_risk_reward < self.risk.min_risk_reward:
            msg = "risk.max_risk_reward must be >= risk.min_risk_reward"
            raise ValueError(msg)
        if self.signal_validity_minutes <= 0:
            msg = "signal_validity_minutes must be positive"
            raise ValueError(msg)
        if self.max_decision_age_seconds <= 0:
            msg = "max_decision_age_seconds must be positive"
            raise ValueError(msg)
        return self

    @property
    def pip_size_decimal(self) -> Decimal:
        return Decimal(str(self.pip_size))


def _parse_dict(raw: object) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _parse_weights(raw: object) -> QualityWeights | None:
    data = _parse_dict(raw)
    if not data:
        return None
    return QualityWeights(
        decision_confidence=float(data.get("decision_confidence", 0.25)),
        decision_quality=float(data.get("decision_quality", 0.20)),
        risk_clarity=float(data.get("risk_clarity", 0.15)),
        entry_precision=float(data.get("entry_precision", 0.10)),
        target_structure=float(data.get("target_structure", 0.10)),
        evidence_completeness=float(data.get("evidence_completeness", 0.10)),
        explainability=float(data.get("explainability", 0.10)),
    )


def load_market_signal_config(
    settings: dict[str, Any] | None = None,
    yaml_path: Path | None = None,
) -> MarketSignalConfig:
    """Load market signal configuration from YAML or pre-loaded settings."""
    if settings is None:
        config_path = yaml_path or Path("config/settings.yaml")
        yaml_data = load_yaml_config(config_path)
    else:
        yaml_data = settings
        config_path = yaml_path or Path("config/settings.yaml")

    signal_yaml = _parse_dict(yaml_data.get("market_signal"))
    engines_yaml = _parse_dict(yaml_data.get("engines"))

    enabled = bool(engines_yaml.get("market_signal", True))
    if "enabled" in signal_yaml:
        enabled = bool(signal_yaml["enabled"])

    validation_yaml = _parse_dict(signal_yaml.get("validation"))
    duplicate_yaml = _parse_dict(signal_yaml.get("duplicate"))
    session_yaml = _parse_dict(signal_yaml.get("session"))
    risk_yaml = _parse_dict(signal_yaml.get("risk"))
    entry_yaml = _parse_dict(signal_yaml.get("entry"))
    take_profit_yaml = _parse_dict(signal_yaml.get("take_profit"))
    quality_yaml = _parse_dict(signal_yaml.get("quality"))
    lifecycle_yaml = _parse_dict(signal_yaml.get("lifecycle"))
    events_yaml = _parse_dict(signal_yaml.get("events"))
    persistence_yaml = _parse_dict(signal_yaml.get("persistence"))

    adjustments_yaml = _parse_dict(quality_yaml.get("adjustments"))
    tiers_yaml = _parse_dict(quality_yaml.get("tiers"))
    entry_scores_yaml = _parse_dict(quality_yaml.get("entry_precision_scores"))
    target_scores_yaml = _parse_dict(quality_yaml.get("target_structure_scores"))
    break_even_yaml = _parse_dict(lifecycle_yaml.get("break_even"))
    trailing_yaml = _parse_dict(lifecycle_yaml.get("trailing"))
    partial_fill_yaml = _parse_dict(lifecycle_yaml.get("partial_fill"))
    entry_trigger_yaml = _parse_dict(lifecycle_yaml.get("entry_trigger"))
    tp_trigger_yaml = _parse_dict(lifecycle_yaml.get("tp_trigger"))
    sl_trigger_yaml = _parse_dict(lifecycle_yaml.get("sl_trigger"))

    return MarketSignalConfig(
        enabled=enabled,
        symbol=str(signal_yaml.get("symbol", "GOLD.i#")),
        timeframe=str(signal_yaml.get("timeframe", "M15")),
        pip_size=float(signal_yaml.get("pip_size", 0.1)),
        auto_activate=bool(signal_yaml.get("auto_activate", True)),
        signal_validity_minutes=int(signal_yaml.get("signal_validity_minutes", 60)),
        max_decision_age_seconds=int(signal_yaml.get("max_decision_age_seconds", 300)),
        debounce_seconds=int(signal_yaml.get("debounce_seconds", 3)),
        raise_on_error=bool(signal_yaml.get("raise_on_error", False)),
        validation=ValidationConfig(
            min_confidence=int(validation_yaml.get("min_confidence", 65)),
            min_decision_quality=int(validation_yaml.get("min_decision_quality", 60)),
            require_evidence_summary=bool(validation_yaml.get("require_evidence_summary", True)),
            require_risk_summary=bool(validation_yaml.get("require_risk_summary", True)),
        ),
        duplicate=DuplicateConfig(
            enabled=bool(duplicate_yaml.get("enabled", True)),
            window_minutes=int(duplicate_yaml.get("window_minutes", 60)),
            entry_tolerance_pips=float(duplicate_yaml.get("entry_tolerance_pips", 5.0)),
            reject_same_decision_id=bool(duplicate_yaml.get("reject_same_decision_id", True)),
        ),
        session=SessionConfig(
            enabled=bool(session_yaml.get("enabled", True)),
            blocked_sessions=list(session_yaml.get("blocked_sessions", [])),
            require_session_allowed=bool(session_yaml.get("require_session_allowed", True)),
        ),
        risk=RiskConfig(
            min_risk_reward=float(risk_yaml.get("min_risk_reward", 2.0)),
            max_risk_reward=float(risk_yaml.get("max_risk_reward", 8.0)),
            require_min_rr_met=bool(risk_yaml.get("require_min_rr_met", True)),
            require_max_rr_met=bool(risk_yaml.get("require_max_rr_met", True)),
            require_spread_acceptable=bool(risk_yaml.get("require_spread_acceptable", True)),
            require_stop_size_acceptable=bool(risk_yaml.get("require_stop_size_acceptable", True)),
            require_confidence_acceptable=bool(risk_yaml.get("require_confidence_acceptable", True)),
        ),
        entry=EntryConfig(
            zone_resolution=str(entry_yaml.get("zone_resolution", "midpoint")),
            buy_zone_edge=str(entry_yaml.get("buy_zone_edge", "zone_low")),
            sell_zone_edge=str(entry_yaml.get("sell_zone_edge", "zone_high")),
        ),
        take_profit=TakeProfitConfig(
            max_targets=int(take_profit_yaml.get("max_targets", 3)),
            require_minimum_one=bool(take_profit_yaml.get("require_minimum_one", True)),
        ),
        quality=QualityConfig(
            min_signal_quality=int(quality_yaml.get("min_signal_quality", 0)),
            weights=_parse_weights(quality_yaml.get("weights")) or QualityWeights(),
            adjustments=QualityAdjustments(
                duplicate_proximity_penalty=int(
                    adjustments_yaml.get("duplicate_proximity_penalty", 10),
                ),
                stale_decision_penalty_max=int(
                    adjustments_yaml.get("stale_decision_penalty_max", 15),
                ),
                warning_penalty_per_item=int(
                    adjustments_yaml.get("warning_penalty_per_item", 2),
                ),
                warning_penalty_max=int(adjustments_yaml.get("warning_penalty_max", 10)),
                multi_tp_bonus=int(adjustments_yaml.get("multi_tp_bonus", 5)),
            ),
            tiers=QualityTierThresholds(
                high=int(tiers_yaml.get("high", 80)),
                medium=int(tiers_yaml.get("medium", 60)),
            ),
            entry_precision_scores=EntryPrecisionScores(
                point=int(entry_scores_yaml.get("point", 100)),
                ote=int(entry_scores_yaml.get("ote", 85)),
                zone=int(entry_scores_yaml.get("zone", 70)),
            ),
            target_structure_scores=TargetStructureScores(
                one_tp=int(target_scores_yaml.get("one_tp", 60)),
                two_tp=int(target_scores_yaml.get("two_tp", 80)),
                three_tp=int(target_scores_yaml.get("three_tp", 100)),
            ),
        ),
        lifecycle=LifecycleConfig(
            enabled=bool(lifecycle_yaml.get("enabled", True)),
            break_even=BreakEvenConfig(
                enabled=bool(break_even_yaml.get("enabled", True)),
                trigger_after=str(break_even_yaml.get("trigger_after", "TP1_HIT")),
                offset_pips=float(break_even_yaml.get("offset_pips", 1.0)),
            ),
            trailing=TrailingConfig(
                enabled=bool(trailing_yaml.get("enabled", False)),
                trigger_after=str(trailing_yaml.get("trigger_after", "TP1_HIT")),
                trail_distance_pips=float(trailing_yaml.get("trail_distance_pips", 15.0)),
                step_pips=float(trailing_yaml.get("step_pips", 5.0)),
            ),
            partial_fill=PartialFillConfig(
                enabled=bool(partial_fill_yaml.get("enabled", False)),
                default_fill_pct=int(partial_fill_yaml.get("default_fill_pct", 50)),
            ),
            entry_trigger=TriggerConfig(
                mode=str(entry_trigger_yaml.get("mode", "touch")),
                tolerance_pips=float(entry_trigger_yaml.get("tolerance_pips", 1.0)),
            ),
            tp_trigger=TriggerConfig(
                mode=str(tp_trigger_yaml.get("mode", "touch")),
                tolerance_pips=float(tp_trigger_yaml.get("tolerance_pips", 0.5)),
            ),
            sl_trigger=TriggerConfig(
                mode=str(sl_trigger_yaml.get("mode", "touch")),
                tolerance_pips=float(sl_trigger_yaml.get("tolerance_pips", 0.5)),
            ),
        ),
        events=EventsConfig(
            publish_rejections=bool(events_yaml.get("publish_rejections", False)),
            publish_lifecycle_events=bool(events_yaml.get("publish_lifecycle_events", True)),
        ),
        persistence=PersistenceConfig(
            enabled=bool(persistence_yaml.get("enabled", True)),
            sqlite_table=str(persistence_yaml.get("sqlite_table", "signals")),
            retain_days=int(persistence_yaml.get("retain_days", 90)),
            store_rejections=bool(persistence_yaml.get("store_rejections", False)),
        ),
        yaml_config_path=str(config_path),
    )

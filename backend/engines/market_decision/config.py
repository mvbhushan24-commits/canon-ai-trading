"""Market Decision Engine configuration."""

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config
from backend.engines.market_decision.schemas import NewsRestrictionResult

SUPPORTED_SYMBOLS = frozenset({"XAUUSD", "GOLD.i#"})


class EvidenceAgeConfig(BaseModel):
    """Maximum evidence age per source in seconds."""

    market_structure: int = 300
    market_liquidity: int = 300
    order_block: int = 300
    fair_value_gap: int = 300
    market_breaker: int = 300
    market_mitigation: int = 300
    market_premium_discount: int = 300
    market_sessions: int = 60
    current_price: int = 30


class EvidenceConfig(BaseModel):
    """Evidence collection parameters."""

    min_required_engines: int = 5
    stale_weight_factor: float = 0.5
    max_evidence_age_seconds: EvidenceAgeConfig = Field(default_factory=EvidenceAgeConfig)


class EvidenceWeights(BaseModel):
    """Per-engine evidence weights (must sum to 1.0)."""

    market_structure: float = 0.20
    market_liquidity: float = 0.15
    order_block: float = 0.12
    fair_value_gap: float = 0.10
    market_breaker: float = 0.08
    market_mitigation: float = 0.08
    market_premium_discount: float = 0.17
    market_sessions: float = 0.10

    @model_validator(mode="after")
    def _validate_sum(self) -> "EvidenceWeights":
        total = (
            self.market_structure
            + self.market_liquidity
            + self.order_block
            + self.fair_value_gap
            + self.market_breaker
            + self.market_mitigation
            + self.market_premium_discount
            + self.market_sessions
        )
        if abs(total - 1.0) > 0.001:
            msg = f"evidence weights must sum to 1.0 (±0.001), got {total}"
            raise ValueError(msg)
        return self


class ConflictPenaltyConfig(BaseModel):
    """Confidence penalties by conflict severity."""

    none: int = 0
    low: int = 5
    medium: int = 15
    high: int = 30


class ConfidenceConfig(BaseModel):
    """Confidence scoring parameters."""

    min_confidence: int = 65
    min_directional_weight: float = 0.35
    conflict_penalty: ConflictPenaltyConfig = Field(default_factory=ConflictPenaltyConfig)
    stale_penalty_per_engine: int = 3
    confluence_bonus_per_zone: int = 5
    max_confluence_bonus: int = 20


class ConflictConfig(BaseModel):
    """Conflict detection thresholds."""

    warn_threshold: float = 0.35
    reject_threshold: float = 0.55


class SessionGateConfig(BaseModel):
    """Session validation gate."""

    enabled: bool = True
    require_kill_zone: bool = False
    min_kill_zone_quality: str = "medium"
    allow_equilibrium_trades: bool = True


class StructureGateConfig(BaseModel):
    """Structure validation gate."""

    enabled: bool = True
    require_trend_alignment: bool = True
    require_recent_bos: bool = False
    bos_lookback_bars: int = 20
    allow_range_trades: bool = False


class LiquidityGateConfig(BaseModel):
    """Liquidity validation gate."""

    enabled: bool = True
    require_sweep_or_grab: bool = True
    liquidity_lookback_bars: int = 30
    min_sweep_quality: str = "low"


class PremiumDiscountGateConfig(BaseModel):
    """Premium/discount validation gate."""

    enabled: bool = True
    require_ote_for_entry: bool = False
    allow_equilibrium: bool = True
    require_mtf_alignment: bool = False


class ZoneIndividualRequirements(BaseModel):
    """Individual zone gate requirements."""

    order_block: bool = False
    fair_value_gap: bool = False
    market_breaker: bool = False
    market_mitigation: bool = False


class ZonesGateConfig(BaseModel):
    """Institutional zone confluence gate."""

    enabled: bool = True
    gate_mode: str = "grouped"
    min_zone_confluence: int = 2
    max_zone_distance_pips: float = 15.0
    individual_requirements: ZoneIndividualRequirements = Field(
        default_factory=ZoneIndividualRequirements,
    )


class GatesConfig(BaseModel):
    """Validation gates configuration."""

    session: SessionGateConfig = Field(default_factory=SessionGateConfig)
    structure: StructureGateConfig = Field(default_factory=StructureGateConfig)
    liquidity: LiquidityGateConfig = Field(default_factory=LiquidityGateConfig)
    premium_discount: PremiumDiscountGateConfig = Field(
        default_factory=PremiumDiscountGateConfig,
    )
    zones: ZonesGateConfig = Field(default_factory=ZonesGateConfig)


class EntryConfig(BaseModel):
    """Entry generation parameters."""

    max_entry_distance_pips: float = 10.0
    prefer_ote: bool = True
    zone_midpoint_entry: bool = True


class StopLossConfig(BaseModel):
    """Stop loss generation parameters."""

    buffer_pips: float = 2.0
    prefer_structure_invalidation: bool = True
    fallback_atr_multiplier: float = 1.5


class TakeProfitConfig(BaseModel):
    """Take profit generation parameters."""

    max_targets: int = 3
    prefer_liquidity_pools: bool = True
    min_target_distance_pips: float = 5.0
    rr_fallback_multiplier: float = 2.0


class SessionRestrictionsConfig(BaseModel):
    """Session-based risk restrictions."""

    enabled: bool = True
    blocked_availability: list[str] = Field(
        default_factory=lambda: ["closed", "pre_open"],
    )
    blocked_session_phases: list[str] = Field(default_factory=list)
    allowed_kill_zones: list[str] = Field(default_factory=list)
    blocked_kill_zones: list[str] = Field(default_factory=list)


class RiskConfig(BaseModel):
    """Risk validation rules."""

    min_risk_reward: float = 2.0
    max_risk_reward: float = 8.0
    max_spread_pips: float = 3.0
    max_stop_size_pips: float = 50.0
    min_confidence: int = 65
    session_restrictions: SessionRestrictionsConfig = Field(
        default_factory=SessionRestrictionsConfig,
    )


class NewsRestrictionConfig(BaseModel):
    """News restriction hook configuration."""

    enabled: bool = False
    hook_path: str | None = None
    default_blocked: bool = False


class QualityDimensionWeights(BaseModel):
    """Decision quality dimension weights."""

    evidence_completeness: float = 0.20
    zone_confluence: float = 0.20
    structure_clarity: float = 0.15
    liquidity_confirmation: float = 0.15
    premium_discount_alignment: float = 0.15
    session_quality: float = 0.15

    @model_validator(mode="after")
    def _validate_sum(self) -> "QualityDimensionWeights":
        total = (
            self.evidence_completeness
            + self.zone_confluence
            + self.structure_clarity
            + self.liquidity_confirmation
            + self.premium_discount_alignment
            + self.session_quality
        )
        if abs(total - 1.0) > 0.001:
            msg = f"quality dimension_weights must sum to 1.0 (±0.001), got {total}"
            raise ValueError(msg)
        return self


class QualityTierThresholds(BaseModel):
    """Quality tier thresholds."""

    high: int = 80
    medium: int = 60


class QualityConfig(BaseModel):
    """Decision quality scoring."""

    enabled: bool = True
    min_quality_score: int = 0
    dimension_weights: QualityDimensionWeights = Field(
        default_factory=QualityDimensionWeights,
    )
    tier_thresholds: QualityTierThresholds = Field(default_factory=QualityTierThresholds)


class PersistenceConfig(BaseModel):
    """Optional decision persistence."""

    enabled: bool = True
    sqlite_table: str = "decisions"
    retain_days: int = 90


NewsRestrictionHook = Callable[[str, Any], NewsRestrictionResult]


class MarketDecisionConfig(BaseModel):
    """Configuration for institutional trade decision synthesis."""

    enabled: bool = False
    symbol: str = "GOLD.i#"
    timeframes: list[str] = Field(default_factory=lambda: ["M5", "M15", "H1"])
    pip_size: float = 0.1
    decision_validity_minutes: int = 60
    debounce_seconds: int = 5
    wait_timeout_seconds: int = 120
    raise_on_error: bool = False
    publish_pipeline_events: bool = False
    publish_wait_events: bool = False
    evidence: EvidenceConfig = Field(default_factory=EvidenceConfig)
    weights: EvidenceWeights = Field(default_factory=EvidenceWeights)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    conflict: ConflictConfig = Field(default_factory=ConflictConfig)
    gates: GatesConfig = Field(default_factory=GatesConfig)
    entry: EntryConfig = Field(default_factory=EntryConfig)
    stop_loss: StopLossConfig = Field(default_factory=StopLossConfig)
    take_profit: TakeProfitConfig = Field(default_factory=TakeProfitConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    news_restriction: NewsRestrictionConfig = Field(default_factory=NewsRestrictionConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("pip_size")
    @classmethod
    def _validate_pip_size(cls, value: float) -> float:
        if value <= 0:
            msg = "pip_size must be positive"
            raise ValueError(msg)
        return value

    @field_validator("confidence")
    @classmethod
    def _validate_confidence_range(cls, value: ConfidenceConfig) -> ConfidenceConfig:
        if not 0 <= value.min_confidence <= 100:
            msg = "confidence.min_confidence must be between 0 and 100"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_risk_bounds(self) -> "MarketDecisionConfig":
        if self.risk.min_risk_reward >= self.risk.max_risk_reward:
            msg = "risk.min_risk_reward must be less than risk.max_risk_reward"
            raise ValueError(msg)
        if not 1 <= self.evidence.min_required_engines <= 8:
            msg = "evidence.min_required_engines must be between 1 and 8"
            raise ValueError(msg)
        return self

    @property
    def pip_size_decimal(self) -> Decimal:
        return Decimal(str(self.pip_size))

    def default_news_hook(self, symbol: str, timestamp_utc: Any) -> NewsRestrictionResult:
        """Default no-block news restriction hook."""
        return NewsRestrictionResult(blocked=self.news_restriction.default_blocked)


def _parse_nested(raw: object, model_cls: type[BaseModel]) -> BaseModel | None:
    if not isinstance(raw, dict):
        return None
    return model_cls.model_validate(raw)


def _parse_evidence_age(raw: object) -> EvidenceAgeConfig | None:
    if not isinstance(raw, dict):
        return None
    return EvidenceAgeConfig(
        market_structure=int(raw.get("market_structure", 300)),
        market_liquidity=int(raw.get("market_liquidity", 300)),
        order_block=int(raw.get("order_block", 300)),
        fair_value_gap=int(raw.get("fair_value_gap", 300)),
        market_breaker=int(raw.get("market_breaker", 300)),
        market_mitigation=int(raw.get("market_mitigation", 300)),
        market_premium_discount=int(raw.get("market_premium_discount", 300)),
        market_sessions=int(raw.get("market_sessions", 60)),
        current_price=int(raw.get("current_price", 30)),
    )


def _parse_weights(raw: object) -> EvidenceWeights | None:
    if not isinstance(raw, dict):
        return None
    return EvidenceWeights(
        market_structure=float(raw.get("market_structure", 0.20)),
        market_liquidity=float(raw.get("market_liquidity", 0.15)),
        order_block=float(raw.get("order_block", 0.12)),
        fair_value_gap=float(raw.get("fair_value_gap", 0.10)),
        market_breaker=float(raw.get("market_breaker", 0.08)),
        market_mitigation=float(raw.get("market_mitigation", 0.08)),
        market_premium_discount=float(raw.get("market_premium_discount", 0.17)),
        market_sessions=float(raw.get("market_sessions", 0.10)),
    )


def _parse_quality_weights(raw: object) -> QualityDimensionWeights | None:
    if not isinstance(raw, dict):
        return None
    return QualityDimensionWeights(
        evidence_completeness=float(raw.get("evidence_completeness", 0.20)),
        zone_confluence=float(raw.get("zone_confluence", 0.20)),
        structure_clarity=float(raw.get("structure_clarity", 0.15)),
        liquidity_confirmation=float(raw.get("liquidity_confirmation", 0.15)),
        premium_discount_alignment=float(raw.get("premium_discount_alignment", 0.15)),
        session_quality=float(raw.get("session_quality", 0.15)),
    )


def _parse_conflict_penalty(raw: object) -> ConflictPenaltyConfig | None:
    if not isinstance(raw, dict):
        return None
    return ConflictPenaltyConfig(
        none=int(raw.get("none", 0)),
        low=int(raw.get("low", 5)),
        medium=int(raw.get("medium", 15)),
        high=int(raw.get("high", 30)),
    )


def _parse_conflict(raw: object) -> ConflictConfig | None:
    if not isinstance(raw, dict):
        return None
    return ConflictConfig(
        warn_threshold=float(raw.get("warn_threshold", 0.35)),
        reject_threshold=float(raw.get("reject_threshold", 0.55)),
    )


def _parse_gates(raw: object) -> GatesConfig | None:
    if not isinstance(raw, dict):
        return None
    session_raw = raw.get("session", {})
    structure_raw = raw.get("structure", {})
    liquidity_raw = raw.get("liquidity", {})
    pd_raw = raw.get("premium_discount", {})
    zones_raw = raw.get("zones", {})
    individual_raw = zones_raw.get("individual_requirements", {}) if isinstance(zones_raw, dict) else {}

    return GatesConfig(
        session=SessionGateConfig(
            enabled=bool(session_raw.get("enabled", True)),
            require_kill_zone=bool(session_raw.get("require_kill_zone", False)),
            min_kill_zone_quality=str(session_raw.get("min_kill_zone_quality", "medium")),
            allow_equilibrium_trades=bool(session_raw.get("allow_equilibrium_trades", True)),
        ),
        structure=StructureGateConfig(
            enabled=bool(structure_raw.get("enabled", True)),
            require_trend_alignment=bool(structure_raw.get("require_trend_alignment", True)),
            require_recent_bos=bool(structure_raw.get("require_recent_bos", False)),
            bos_lookback_bars=int(structure_raw.get("bos_lookback_bars", 20)),
            allow_range_trades=bool(structure_raw.get("allow_range_trades", False)),
        ),
        liquidity=LiquidityGateConfig(
            enabled=bool(liquidity_raw.get("enabled", True)),
            require_sweep_or_grab=bool(liquidity_raw.get("require_sweep_or_grab", True)),
            liquidity_lookback_bars=int(liquidity_raw.get("liquidity_lookback_bars", 30)),
            min_sweep_quality=str(liquidity_raw.get("min_sweep_quality", "low")),
        ),
        premium_discount=PremiumDiscountGateConfig(
            enabled=bool(pd_raw.get("enabled", True)),
            require_ote_for_entry=bool(pd_raw.get("require_ote_for_entry", False)),
            allow_equilibrium=bool(pd_raw.get("allow_equilibrium", True)),
            require_mtf_alignment=bool(pd_raw.get("require_mtf_alignment", False)),
        ),
        zones=ZonesGateConfig(
            enabled=bool(zones_raw.get("enabled", True)),
            gate_mode=str(zones_raw.get("gate_mode", "grouped")),
            min_zone_confluence=int(zones_raw.get("min_zone_confluence", 2)),
            max_zone_distance_pips=float(zones_raw.get("max_zone_distance_pips", 15.0)),
            individual_requirements=ZoneIndividualRequirements(
                order_block=bool(individual_raw.get("order_block", False)),
                fair_value_gap=bool(individual_raw.get("fair_value_gap", False)),
                market_breaker=bool(individual_raw.get("market_breaker", False)),
                market_mitigation=bool(individual_raw.get("market_mitigation", False)),
            ),
        ),
    )


def load_market_decision_config(
    settings: dict[str, Any] | None = None,
    yaml_path: Path | None = None,
) -> MarketDecisionConfig:
    """Load market decision configuration from YAML or pre-loaded settings."""
    if settings is None:
        config_path = yaml_path or Path("config/settings.yaml")
        yaml_data = load_yaml_config(config_path)
    else:
        yaml_data = settings
        config_path = yaml_path or Path("config/settings.yaml")

    decision_yaml = yaml_data.get("market_decision", {})
    if not isinstance(decision_yaml, dict):
        decision_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("market_decision", False))
    if "enabled" in decision_yaml:
        enabled = bool(decision_yaml["enabled"])

    evidence_yaml = decision_yaml.get("evidence", {})
    if not isinstance(evidence_yaml, dict):
        evidence_yaml = {}

    confidence_yaml = decision_yaml.get("confidence", {})
    if not isinstance(confidence_yaml, dict):
        confidence_yaml = {}

    risk_yaml = decision_yaml.get("risk", {})
    if not isinstance(risk_yaml, dict):
        risk_yaml = {}

    quality_yaml = decision_yaml.get("quality", {})
    if not isinstance(quality_yaml, dict):
        quality_yaml = {}

    news_yaml = decision_yaml.get("news_restriction", {})
    if not isinstance(news_yaml, dict):
        news_yaml = {}

    session_restrictions_raw = risk_yaml.get("session_restrictions", {})
    if not isinstance(session_restrictions_raw, dict):
        session_restrictions_raw = {}

    timeframes_raw = decision_yaml.get("timeframes")
    timeframes = ["M5", "M15", "H1"]
    if isinstance(timeframes_raw, list):
        timeframes = [str(item).strip().upper() for item in timeframes_raw if str(item).strip()]

    tier_raw = quality_yaml.get("tier_thresholds", {})
    if not isinstance(tier_raw, dict):
        tier_raw = {}

    return MarketDecisionConfig(
        enabled=enabled,
        symbol=str(decision_yaml.get("symbol", "GOLD.i#")),
        timeframes=timeframes,
        pip_size=float(decision_yaml.get("pip_size", 0.1)),
        decision_validity_minutes=int(decision_yaml.get("decision_validity_minutes", 60)),
        debounce_seconds=int(decision_yaml.get("debounce_seconds", 5)),
        wait_timeout_seconds=int(decision_yaml.get("wait_timeout_seconds", 120)),
        raise_on_error=bool(decision_yaml.get("raise_on_error", False)),
        publish_pipeline_events=bool(decision_yaml.get("publish_pipeline_events", False)),
        publish_wait_events=bool(decision_yaml.get("publish_wait_events", False)),
        evidence=EvidenceConfig(
            min_required_engines=int(evidence_yaml.get("min_required_engines", 5)),
            stale_weight_factor=float(evidence_yaml.get("stale_weight_factor", 0.5)),
            max_evidence_age_seconds=(
                _parse_evidence_age(evidence_yaml.get("max_evidence_age_seconds"))
                or EvidenceAgeConfig()
            ),
        ),
        weights=_parse_weights(decision_yaml.get("weights")) or EvidenceWeights(),
        confidence=ConfidenceConfig(
            min_confidence=int(confidence_yaml.get("min_confidence", 65)),
            min_directional_weight=float(confidence_yaml.get("min_directional_weight", 0.35)),
            conflict_penalty=(
                _parse_conflict_penalty(confidence_yaml.get("conflict_penalty"))
                or ConflictPenaltyConfig()
            ),
            stale_penalty_per_engine=int(confidence_yaml.get("stale_penalty_per_engine", 3)),
            confluence_bonus_per_zone=int(confidence_yaml.get("confluence_bonus_per_zone", 5)),
            max_confluence_bonus=int(confidence_yaml.get("max_confluence_bonus", 20)),
        ),
        conflict=_parse_conflict(decision_yaml.get("conflict")) or ConflictConfig(),
        gates=_parse_gates(decision_yaml.get("gates")) or GatesConfig(),
        entry=EntryConfig(
            max_entry_distance_pips=float(
                decision_yaml.get("entry", {}).get("max_entry_distance_pips", 10.0),
            )
            if isinstance(decision_yaml.get("entry"), dict)
            else 10.0,
            prefer_ote=bool(decision_yaml.get("entry", {}).get("prefer_ote", True))
            if isinstance(decision_yaml.get("entry"), dict)
            else True,
            zone_midpoint_entry=bool(
                decision_yaml.get("entry", {}).get("zone_midpoint_entry", True),
            )
            if isinstance(decision_yaml.get("entry"), dict)
            else True,
        ),
        stop_loss=StopLossConfig(
            buffer_pips=float(decision_yaml.get("stop_loss", {}).get("buffer_pips", 2.0))
            if isinstance(decision_yaml.get("stop_loss"), dict)
            else 2.0,
            prefer_structure_invalidation=bool(
                decision_yaml.get("stop_loss", {}).get("prefer_structure_invalidation", True),
            )
            if isinstance(decision_yaml.get("stop_loss"), dict)
            else True,
            fallback_atr_multiplier=float(
                decision_yaml.get("stop_loss", {}).get("fallback_atr_multiplier", 1.5),
            )
            if isinstance(decision_yaml.get("stop_loss"), dict)
            else 1.5,
        ),
        take_profit=TakeProfitConfig(
            max_targets=int(decision_yaml.get("take_profit", {}).get("max_targets", 3))
            if isinstance(decision_yaml.get("take_profit"), dict)
            else 3,
            prefer_liquidity_pools=bool(
                decision_yaml.get("take_profit", {}).get("prefer_liquidity_pools", True),
            )
            if isinstance(decision_yaml.get("take_profit"), dict)
            else True,
            min_target_distance_pips=float(
                decision_yaml.get("take_profit", {}).get("min_target_distance_pips", 5.0),
            )
            if isinstance(decision_yaml.get("take_profit"), dict)
            else 5.0,
            rr_fallback_multiplier=float(
                decision_yaml.get("take_profit", {}).get("rr_fallback_multiplier", 2.0),
            )
            if isinstance(decision_yaml.get("take_profit"), dict)
            else 2.0,
        ),
        risk=RiskConfig(
            min_risk_reward=float(risk_yaml.get("min_risk_reward", 2.0)),
            max_risk_reward=float(risk_yaml.get("max_risk_reward", 8.0)),
            max_spread_pips=float(risk_yaml.get("max_spread_pips", 3.0)),
            max_stop_size_pips=float(risk_yaml.get("max_stop_size_pips", 50.0)),
            min_confidence=int(risk_yaml.get("min_confidence", 65)),
            session_restrictions=SessionRestrictionsConfig(
                enabled=bool(session_restrictions_raw.get("enabled", True)),
                blocked_availability=list(
                    session_restrictions_raw.get("blocked_availability", ["closed", "pre_open"]),
                ),
                blocked_session_phases=list(
                    session_restrictions_raw.get("blocked_session_phases", []),
                ),
                allowed_kill_zones=list(
                    session_restrictions_raw.get("allowed_kill_zones", []),
                ),
                blocked_kill_zones=list(
                    session_restrictions_raw.get("blocked_kill_zones", []),
                ),
            ),
        ),
        news_restriction=NewsRestrictionConfig(
            enabled=bool(news_yaml.get("enabled", False)),
            hook_path=news_yaml.get("hook_path"),
            default_blocked=bool(news_yaml.get("default_blocked", False)),
        ),
        quality=QualityConfig(
            enabled=bool(quality_yaml.get("enabled", True)),
            min_quality_score=int(quality_yaml.get("min_quality_score", 0)),
            dimension_weights=(
                _parse_quality_weights(quality_yaml.get("dimension_weights"))
                or QualityDimensionWeights()
            ),
            tier_thresholds=QualityTierThresholds(
                high=int(tier_raw.get("high", 80)),
                medium=int(tier_raw.get("medium", 60)),
            ),
        ),
        persistence=PersistenceConfig(
            enabled=bool(decision_yaml.get("persistence", {}).get("enabled", True))
            if isinstance(decision_yaml.get("persistence"), dict)
            else True,
            sqlite_table=str(
                decision_yaml.get("persistence", {}).get("sqlite_table", "decisions"),
            )
            if isinstance(decision_yaml.get("persistence"), dict)
            else "decisions",
            retain_days=int(decision_yaml.get("persistence", {}).get("retain_days", 90))
            if isinstance(decision_yaml.get("persistence"), dict)
            else 90,
        ),
        yaml_config_path=str(config_path),
    )

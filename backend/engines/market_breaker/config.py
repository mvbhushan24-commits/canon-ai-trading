"""Breaker Block Engine configuration."""

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config


class ConfirmationMode(StrEnum):
    """Retest confirmation trigger mode."""

    WICK_TOUCH = "wick_touch"
    BODY_TOUCH = "body_touch"
    CLOSE_INSIDE = "close_inside"
    REJECTION = "rejection"


class MitigationMode(StrEnum):
    """Breaker mitigation trigger mode."""

    WICK = "wick"
    BODY = "body"
    CLOSE = "close"
    PARTIAL = "partial"


class TouchMode(StrEnum):
    """Candle touch mode for breaker invalidation."""

    CLOSE = "close"
    BODY = "body"
    WICK = "wick"


class DealingRangeMode(StrEnum):
    """Swing range source for premium/discount classification."""

    EXTERNAL = "external"
    INTERNAL = "internal"


class QualityWeights(BaseModel):
    """Configurable quality scoring weights."""

    source_quality: float = 0.20
    invalidation_strength: float = 0.15
    confirmation: float = 0.20
    structure: float = 0.15
    liquidity: float = 0.10
    fvg: float = 0.10
    premium_discount: float = 0.05
    freshness: float = 0.05

    @model_validator(mode="after")
    def _validate_sum(self) -> "QualityWeights":
        total = (
            self.source_quality
            + self.invalidation_strength
            + self.confirmation
            + self.structure
            + self.liquidity
            + self.fvg
            + self.premium_discount
            + self.freshness
        )
        if abs(total - 1.0) > 0.01:
            msg = f"quality_weights must sum to 1.0 (±0.01), got {total}"
            raise ValueError(msg)
        return self


class BreakerBlockConfig(BaseModel):
    """Configuration for institutional breaker block analysis."""

    enabled: bool = False
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1", "H4"])
    min_candles: int = 20
    lookback: int = 100
    pip_size: float = 0.1
    min_zone_size_pips: float = 2.0
    min_source_quality: str = "medium"
    fvg_breaker_enabled: bool = False
    deduplicate_by_source: bool = True
    confirmation_mode: str = "wick_touch"
    min_bars_after_invalidation: int = 1
    max_bars_after_invalidation: int = 50
    require_displacement_after_invalidation: bool = False
    rejection_wick_ratio: float = 0.5
    max_breaker_age_bars: int = 150
    invalidation_mode: str = "close"
    mitigation_mode: str = "wick"
    mitigation_percent: float = 50.0
    dealing_range_mode: str = "external"
    equilibrium_tolerance_pips: float = 3.0
    use_liquidity_confluence: bool = True
    liquidity_proximity_pips: float = 5.0
    use_fvg_confluence: bool = True
    fvg_ce_proximity_pips: float = 3.0
    fvg_overlap_min_percent: float = 10.0
    min_quality_score: float = 0.4
    require_structure_alignment: bool = False
    quality_weights: QualityWeights = Field(default_factory=QualityWeights)
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("min_candles")
    @classmethod
    def _validate_min_candles(cls, value: int) -> int:
        if value < 5:
            msg = "min_candles must be at least 5"
            raise ValueError(msg)
        return value

    @field_validator("lookback")
    @classmethod
    def _validate_lookback(cls, value: int, info) -> int:
        min_candles = info.data.get("min_candles", 20)
        if value < min_candles:
            msg = "lookback must be >= min_candles"
            raise ValueError(msg)
        return value

    @field_validator("pip_size", "min_zone_size_pips")
    @classmethod
    def _validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            msg = "pip_size and min_zone_size_pips must be positive"
            raise ValueError(msg)
        return value

    @field_validator("min_source_quality")
    @classmethod
    def _validate_min_source_quality(cls, value: str) -> str:
        allowed = {"high", "medium", "low"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"min_source_quality must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("confirmation_mode")
    @classmethod
    def _validate_confirmation_mode(cls, value: str) -> str:
        allowed = {item.value for item in ConfirmationMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"confirmation_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("invalidation_mode")
    @classmethod
    def _validate_invalidation_mode(cls, value: str) -> str:
        allowed = {item.value for item in TouchMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"invalidation_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("mitigation_mode")
    @classmethod
    def _validate_mitigation_mode(cls, value: str) -> str:
        allowed = {item.value for item in MitigationMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"mitigation_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("dealing_range_mode")
    @classmethod
    def _validate_dealing_range_mode(cls, value: str) -> str:
        allowed = {item.value for item in DealingRangeMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"dealing_range_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator(
        "min_bars_after_invalidation",
        "max_bars_after_invalidation",
        "max_breaker_age_bars",
    )
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value < 0:
            msg = "Integer configuration values cannot be negative"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_retest_window(self) -> "BreakerBlockConfig":
        if self.max_bars_after_invalidation <= self.min_bars_after_invalidation:
            msg = "max_bars_after_invalidation must be > min_bars_after_invalidation"
            raise ValueError(msg)
        if self.max_breaker_age_bars < 1:
            msg = "max_breaker_age_bars must be at least 1"
            raise ValueError(msg)
        return self

    @field_validator("min_quality_score", "rejection_wick_ratio")
    @classmethod
    def _validate_unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "Score and ratio values must be between 0 and 1"
            raise ValueError(msg)
        return value

    @field_validator("mitigation_percent", "fvg_overlap_min_percent")
    @classmethod
    def _validate_percent(cls, value: float) -> float:
        if not 0.0 <= value <= 100.0:
            msg = "Percent values must be between 0 and 100"
            raise ValueError(msg)
        return value

    @field_validator("timeframes")
    @classmethod
    def _validate_timeframes(cls, value: list[str]) -> list[str]:
        if not value:
            msg = "timeframes must be a non-empty list"
            raise ValueError(msg)
        return [item.strip().upper() for item in value if str(item).strip()]

    @field_validator(
        "equilibrium_tolerance_pips",
        "liquidity_proximity_pips",
        "fvg_ce_proximity_pips",
    )
    @classmethod
    def _validate_non_negative(cls, value: float) -> float:
        if value < 0:
            msg = "Proximity and tolerance values cannot be negative"
            raise ValueError(msg)
        return value

    @property
    def min_zone_size_price(self) -> Decimal:
        return Decimal(str(self.min_zone_size_pips * self.pip_size))

    @property
    def equilibrium_tolerance_price(self) -> float:
        return self.equilibrium_tolerance_pips * self.pip_size

    @property
    def liquidity_proximity_price(self) -> Decimal:
        return Decimal(str(self.liquidity_proximity_pips * self.pip_size))

    @property
    def fvg_ce_proximity_price(self) -> Decimal:
        return Decimal(str(self.fvg_ce_proximity_pips * self.pip_size))


def _parse_timeframes(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [item.strip().upper() for item in raw if str(item).strip()]
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_quality_weights(raw: object) -> QualityWeights | None:
    if not isinstance(raw, dict):
        return None
    return QualityWeights(
        source_quality=float(raw.get("source_quality", 0.20)),
        invalidation_strength=float(raw.get("invalidation_strength", 0.15)),
        confirmation=float(raw.get("confirmation", 0.20)),
        structure=float(raw.get("structure", 0.15)),
        liquidity=float(raw.get("liquidity", 0.10)),
        fvg=float(raw.get("fvg", 0.10)),
        premium_discount=float(raw.get("premium_discount", 0.05)),
        freshness=float(raw.get("freshness", 0.05)),
    )


def load_market_breaker_config(yaml_path: Path | None = None) -> BreakerBlockConfig:
    """Load breaker block configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    breaker_yaml = yaml_data.get("market_breaker", {})
    if not isinstance(breaker_yaml, dict):
        breaker_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("market_breaker", False))
    if "enabled" in breaker_yaml:
        enabled = bool(breaker_yaml["enabled"])

    timeframes = _parse_timeframes(breaker_yaml.get("timeframes"))
    quality_weights = _parse_quality_weights(breaker_yaml.get("quality_weights"))

    return BreakerBlockConfig(
        enabled=enabled,
        timeframes=timeframes or ["M15", "H1", "H4"],
        min_candles=int(breaker_yaml.get("min_candles", 20)),
        lookback=int(breaker_yaml.get("lookback", 100)),
        pip_size=float(breaker_yaml.get("pip_size", 0.1)),
        min_zone_size_pips=float(breaker_yaml.get("min_zone_size_pips", 2.0)),
        min_source_quality=str(breaker_yaml.get("min_source_quality", "medium")),
        fvg_breaker_enabled=bool(breaker_yaml.get("fvg_breaker_enabled", False)),
        deduplicate_by_source=bool(breaker_yaml.get("deduplicate_by_source", True)),
        confirmation_mode=str(breaker_yaml.get("confirmation_mode", "wick_touch")),
        min_bars_after_invalidation=int(
            breaker_yaml.get("min_bars_after_invalidation", 1),
        ),
        max_bars_after_invalidation=int(
            breaker_yaml.get("max_bars_after_invalidation", 50),
        ),
        require_displacement_after_invalidation=bool(
            breaker_yaml.get("require_displacement_after_invalidation", False),
        ),
        rejection_wick_ratio=float(breaker_yaml.get("rejection_wick_ratio", 0.5)),
        max_breaker_age_bars=int(breaker_yaml.get("max_breaker_age_bars", 150)),
        invalidation_mode=str(breaker_yaml.get("invalidation_mode", "close")),
        mitigation_mode=str(breaker_yaml.get("mitigation_mode", "wick")),
        mitigation_percent=float(breaker_yaml.get("mitigation_percent", 50.0)),
        dealing_range_mode=str(breaker_yaml.get("dealing_range_mode", "external")),
        equilibrium_tolerance_pips=float(
            breaker_yaml.get("equilibrium_tolerance_pips", 3.0),
        ),
        use_liquidity_confluence=bool(
            breaker_yaml.get("use_liquidity_confluence", True),
        ),
        liquidity_proximity_pips=float(
            breaker_yaml.get("liquidity_proximity_pips", 5.0),
        ),
        use_fvg_confluence=bool(breaker_yaml.get("use_fvg_confluence", True)),
        fvg_ce_proximity_pips=float(breaker_yaml.get("fvg_ce_proximity_pips", 3.0)),
        fvg_overlap_min_percent=float(breaker_yaml.get("fvg_overlap_min_percent", 10.0)),
        min_quality_score=float(breaker_yaml.get("min_quality_score", 0.4)),
        require_structure_alignment=bool(
            breaker_yaml.get("require_structure_alignment", False),
        ),
        quality_weights=quality_weights or QualityWeights(),
        yaml_config_path=str(config_path),
    )

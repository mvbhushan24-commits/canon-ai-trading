"""Mitigation Block Engine configuration."""

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config


class ZoneBoundMode(StrEnum):
    """Opposing candle zone derivation mode."""

    BODY = "body"
    WICK = "wick"
    FULL_CANDLE = "full_candle"


class MitigationMode(StrEnum):
    """Touch trigger mode for partial/full mitigation."""

    WICK = "wick"
    BODY = "body"
    CLOSE = "close"
    PARTIAL = "partial"


class ConfirmationMode(StrEnum):
    """Mitigation confirmation trigger mode."""

    WICK_TOUCH = "wick_touch"
    BODY_TOUCH = "body_touch"
    CLOSE_INSIDE = "close_inside"
    REJECTION = "rejection"
    DISPLACEMENT_AFTER = "displacement_after"


class TouchMode(StrEnum):
    """Candle touch mode for invalidation."""

    CLOSE = "close"
    BODY = "body"
    WICK = "wick"


class StructureScopeMode(StrEnum):
    """Structure scope evaluation mode."""

    INTERNAL = "internal"
    EXTERNAL = "external"
    BOTH = "both"


class DealingRangeMode(StrEnum):
    """Swing range source for premium/discount classification."""

    EXTERNAL = "external"
    INTERNAL = "internal"


class QualityWeights(BaseModel):
    """Configurable quality scoring weights."""

    displacement: float = 0.20
    structure: float = 0.15
    structure_scope: float = 0.10
    liquidity: float = 0.10
    order_block: float = 0.10
    fvg: float = 0.10
    breaker: float = 0.05
    htf_alignment: float = 0.10
    confirmation: float = 0.05
    freshness: float = 0.05

    @model_validator(mode="after")
    def _validate_sum(self) -> "QualityWeights":
        total = (
            self.displacement
            + self.structure
            + self.structure_scope
            + self.liquidity
            + self.order_block
            + self.fvg
            + self.breaker
            + self.htf_alignment
            + self.confirmation
            + self.freshness
        )
        if abs(total - 1.0) > 0.01:
            msg = f"quality_weights must sum to 1.0 (±0.01), got {total}"
            raise ValueError(msg)
        return self


class MitigationBlockConfig(BaseModel):
    """Configuration for institutional mitigation block analysis."""

    enabled: bool = False
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1", "H4"])
    min_candles: int = 20
    lookback: int = 100
    pip_size: float = 0.1
    min_displacement_pips: float = 5.0
    min_zone_size_pips: float = 1.5
    zone_bound_mode: str = "body"
    require_bos_displacement: bool = False
    deduplicate_by_origin: bool = True
    mitigation_mode: str = "wick"
    full_mitigation_percent: float = 75.0
    ce_mitigation_enabled: bool = False
    min_bars_between_touches: int = 1
    min_bars_after_formation: int = 1
    confirmation_mode: str = "wick_touch"
    min_touch_count: int = 1
    require_displacement_after_touch: bool = False
    rejection_wick_ratio: float = 0.5
    require_structure_alignment: bool = False
    max_block_age_bars: int = 150
    invalidation_mode: str = "close"
    invalidate_used_blocks: bool = False
    invalidate_on_choch: bool = False
    invalidate_on_parent_invalidated: bool = True
    structure_scope_mode: str = "both"
    dealing_range_mode: str = "external"
    htf_overlap_min_percent: float = 25.0
    ltf_nesting_enabled: bool = True
    nest_overlap_min_percent: float = 80.0
    confluence_formation_enabled: bool = True
    equilibrium_tolerance_pips: float = 3.0
    use_liquidity_confluence: bool = True
    liquidity_proximity_pips: float = 5.0
    use_order_block_confluence: bool = True
    ob_overlap_min_percent: float = 15.0
    use_fvg_confluence: bool = True
    fvg_ce_proximity_pips: float = 3.0
    fvg_overlap_min_percent: float = 10.0
    use_breaker_confluence: bool = True
    breaker_overlap_min_percent: float = 15.0
    min_quality_score: float = 0.4
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

    @field_validator("pip_size", "min_displacement_pips", "min_zone_size_pips")
    @classmethod
    def _validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            msg = "pip_size, min_displacement_pips, and min_zone_size_pips must be positive"
            raise ValueError(msg)
        return value

    @field_validator("zone_bound_mode")
    @classmethod
    def _validate_zone_bound_mode(cls, value: str) -> str:
        allowed = {item.value for item in ZoneBoundMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"zone_bound_mode must be one of {sorted(allowed)}"
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

    @field_validator("structure_scope_mode")
    @classmethod
    def _validate_structure_scope_mode(cls, value: str) -> str:
        allowed = {item.value for item in StructureScopeMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"structure_scope_mode must be one of {sorted(allowed)}"
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

    @field_validator("min_touch_count", "max_block_age_bars")
    @classmethod
    def _validate_min_positive_int(cls, value: int) -> int:
        if value < 1:
            msg = "min_touch_count and max_block_age_bars must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("min_bars_between_touches", "min_bars_after_formation")
    @classmethod
    def _validate_non_negative_int(cls, value: int) -> int:
        if value < 0:
            msg = "Bar gap configuration values cannot be negative"
            raise ValueError(msg)
        return value

    @field_validator("min_quality_score", "rejection_wick_ratio")
    @classmethod
    def _validate_unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "Score and ratio values must be between 0 and 1"
            raise ValueError(msg)
        return value

    @field_validator(
        "full_mitigation_percent",
        "htf_overlap_min_percent",
        "nest_overlap_min_percent",
        "ob_overlap_min_percent",
        "fvg_overlap_min_percent",
        "breaker_overlap_min_percent",
    )
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
    def min_displacement_price(self) -> Decimal:
        return Decimal(str(self.min_displacement_pips * self.pip_size))

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
        displacement=float(raw.get("displacement", 0.20)),
        structure=float(raw.get("structure", 0.15)),
        structure_scope=float(raw.get("structure_scope", 0.10)),
        liquidity=float(raw.get("liquidity", 0.10)),
        order_block=float(raw.get("order_block", 0.10)),
        fvg=float(raw.get("fvg", 0.10)),
        breaker=float(raw.get("breaker", 0.05)),
        htf_alignment=float(raw.get("htf_alignment", 0.10)),
        confirmation=float(raw.get("confirmation", 0.05)),
        freshness=float(raw.get("freshness", 0.05)),
    )


def load_market_mitigation_config(yaml_path: Path | None = None) -> MitigationBlockConfig:
    """Load mitigation block configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    mitigation_yaml = yaml_data.get("market_mitigation", {})
    if not isinstance(mitigation_yaml, dict):
        mitigation_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("market_mitigation", False))
    if "enabled" in mitigation_yaml:
        enabled = bool(mitigation_yaml["enabled"])

    timeframes = _parse_timeframes(mitigation_yaml.get("timeframes"))
    quality_weights = _parse_quality_weights(mitigation_yaml.get("quality_weights"))

    return MitigationBlockConfig(
        enabled=enabled,
        timeframes=timeframes or ["M15", "H1", "H4"],
        min_candles=int(mitigation_yaml.get("min_candles", 20)),
        lookback=int(mitigation_yaml.get("lookback", 100)),
        pip_size=float(mitigation_yaml.get("pip_size", 0.1)),
        min_displacement_pips=float(mitigation_yaml.get("min_displacement_pips", 5.0)),
        min_zone_size_pips=float(mitigation_yaml.get("min_zone_size_pips", 1.5)),
        zone_bound_mode=str(mitigation_yaml.get("zone_bound_mode", "body")),
        require_bos_displacement=bool(
            mitigation_yaml.get("require_bos_displacement", False),
        ),
        deduplicate_by_origin=bool(mitigation_yaml.get("deduplicate_by_origin", True)),
        mitigation_mode=str(mitigation_yaml.get("mitigation_mode", "wick")),
        full_mitigation_percent=float(mitigation_yaml.get("full_mitigation_percent", 75.0)),
        ce_mitigation_enabled=bool(mitigation_yaml.get("ce_mitigation_enabled", False)),
        min_bars_between_touches=int(mitigation_yaml.get("min_bars_between_touches", 1)),
        min_bars_after_formation=int(mitigation_yaml.get("min_bars_after_formation", 1)),
        confirmation_mode=str(mitigation_yaml.get("confirmation_mode", "wick_touch")),
        min_touch_count=int(mitigation_yaml.get("min_touch_count", 1)),
        require_displacement_after_touch=bool(
            mitigation_yaml.get("require_displacement_after_touch", False),
        ),
        rejection_wick_ratio=float(mitigation_yaml.get("rejection_wick_ratio", 0.5)),
        require_structure_alignment=bool(
            mitigation_yaml.get("require_structure_alignment", False),
        ),
        max_block_age_bars=int(mitigation_yaml.get("max_block_age_bars", 150)),
        invalidation_mode=str(mitigation_yaml.get("invalidation_mode", "close")),
        invalidate_used_blocks=bool(mitigation_yaml.get("invalidate_used_blocks", False)),
        invalidate_on_choch=bool(mitigation_yaml.get("invalidate_on_choch", False)),
        invalidate_on_parent_invalidated=bool(
            mitigation_yaml.get("invalidate_on_parent_invalidated", True),
        ),
        structure_scope_mode=str(mitigation_yaml.get("structure_scope_mode", "both")),
        dealing_range_mode=str(mitigation_yaml.get("dealing_range_mode", "external")),
        htf_overlap_min_percent=float(mitigation_yaml.get("htf_overlap_min_percent", 25.0)),
        ltf_nesting_enabled=bool(mitigation_yaml.get("ltf_nesting_enabled", True)),
        nest_overlap_min_percent=float(mitigation_yaml.get("nest_overlap_min_percent", 80.0)),
        confluence_formation_enabled=bool(
            mitigation_yaml.get("confluence_formation_enabled", True),
        ),
        equilibrium_tolerance_pips=float(
            mitigation_yaml.get("equilibrium_tolerance_pips", 3.0),
        ),
        use_liquidity_confluence=bool(
            mitigation_yaml.get("use_liquidity_confluence", True),
        ),
        liquidity_proximity_pips=float(
            mitigation_yaml.get("liquidity_proximity_pips", 5.0),
        ),
        use_order_block_confluence=bool(
            mitigation_yaml.get("use_order_block_confluence", True),
        ),
        ob_overlap_min_percent=float(mitigation_yaml.get("ob_overlap_min_percent", 15.0)),
        use_fvg_confluence=bool(mitigation_yaml.get("use_fvg_confluence", True)),
        fvg_ce_proximity_pips=float(mitigation_yaml.get("fvg_ce_proximity_pips", 3.0)),
        fvg_overlap_min_percent=float(mitigation_yaml.get("fvg_overlap_min_percent", 10.0)),
        use_breaker_confluence=bool(mitigation_yaml.get("use_breaker_confluence", True)),
        breaker_overlap_min_percent=float(
            mitigation_yaml.get("breaker_overlap_min_percent", 15.0),
        ),
        min_quality_score=float(mitigation_yaml.get("min_quality_score", 0.4)),
        quality_weights=quality_weights or QualityWeights(),
        yaml_config_path=str(config_path),
    )

"""Order Block Engine configuration."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config


class QualityWeights(BaseModel):
    """Configurable quality scoring weights."""

    displacement: float = 0.35
    structure: float = 0.30
    liquidity: float = 0.20
    freshness: float = 0.15

    @model_validator(mode="after")
    def _validate_sum(self) -> "QualityWeights":
        total = self.displacement + self.structure + self.liquidity + self.freshness
        if abs(total - 1.0) > 0.001:
            msg = f"quality_weights must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self


class OrderBlockConfig(BaseModel):
    """Configuration for institutional order block analysis."""

    enabled: bool = False
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1", "H4"])
    min_candles: int = 20
    lookback: int = 100
    zone_mode: str = "body"
    min_displacement_pips: float = 5.0
    min_impulse_candles: int = 2
    pip_size: float = 0.1
    max_block_age_bars: int = 200
    min_quality_score: float = 0.4
    require_structure_alignment: bool = False
    use_liquidity_confluence: bool = True
    mitigation_touch_mode: str = "wick"
    invalidation_mode: str = "close"
    quality_weights: QualityWeights = Field(default_factory=QualityWeights)
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("zone_mode")
    @classmethod
    def _validate_zone_mode(cls, value: str) -> str:
        allowed = {"body", "wick", "full"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"zone_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("mitigation_touch_mode")
    @classmethod
    def _validate_mitigation_mode(cls, value: str) -> str:
        allowed = {"wick", "body", "close"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"mitigation_touch_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("invalidation_mode")
    @classmethod
    def _validate_invalidation_mode(cls, value: str) -> str:
        allowed = {"close", "body"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"invalidation_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("min_candles", "lookback", "min_impulse_candles", "max_block_age_bars")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value < 1:
            msg = "Integer configuration values must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("min_displacement_pips", "pip_size")
    @classmethod
    def _validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            msg = "Displacement and pip values must be positive"
            raise ValueError(msg)
        return value

    @field_validator("min_quality_score")
    @classmethod
    def _validate_quality_score(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "min_quality_score must be between 0 and 1"
            raise ValueError(msg)
        return value

    @property
    def min_displacement_price(self) -> float:
        return self.min_displacement_pips * self.pip_size

    @property
    def full_zone_buffer_price(self) -> float:
        return 2.0 * self.pip_size


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
        displacement=float(raw.get("displacement", 0.35)),
        structure=float(raw.get("structure", 0.30)),
        liquidity=float(raw.get("liquidity", 0.20)),
        freshness=float(raw.get("freshness", 0.15)),
    )


def load_order_block_config(yaml_path: Path | None = None) -> OrderBlockConfig:
    """Load order block configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    order_block_yaml = yaml_data.get("order_block", {})
    if not isinstance(order_block_yaml, dict):
        order_block_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("order_block", False))
    if "enabled" in order_block_yaml:
        enabled = bool(order_block_yaml["enabled"])

    timeframes = _parse_timeframes(order_block_yaml.get("timeframes"))
    quality_weights = _parse_quality_weights(order_block_yaml.get("quality_weights"))

    return OrderBlockConfig(
        enabled=enabled,
        timeframes=timeframes or ["M15", "H1", "H4"],
        min_candles=int(order_block_yaml.get("min_candles", 20)),
        lookback=int(order_block_yaml.get("lookback", 100)),
        zone_mode=str(order_block_yaml.get("zone_mode", "body")),
        min_displacement_pips=float(order_block_yaml.get("min_displacement_pips", 5.0)),
        min_impulse_candles=int(order_block_yaml.get("min_impulse_candles", 2)),
        pip_size=float(order_block_yaml.get("pip_size", 0.1)),
        max_block_age_bars=int(order_block_yaml.get("max_block_age_bars", 200)),
        min_quality_score=float(order_block_yaml.get("min_quality_score", 0.4)),
        require_structure_alignment=bool(
            order_block_yaml.get("require_structure_alignment", False),
        ),
        use_liquidity_confluence=bool(
            order_block_yaml.get("use_liquidity_confluence", True),
        ),
        mitigation_touch_mode=str(order_block_yaml.get("mitigation_touch_mode", "wick")),
        invalidation_mode=str(order_block_yaml.get("invalidation_mode", "close")),
        quality_weights=quality_weights or QualityWeights(),
        yaml_config_path=str(config_path),
    )

"""Fair Value Gap Engine configuration."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config


class QualityWeights(BaseModel):
    """Configurable quality scoring weights."""

    impulse: float = 0.25
    gap_size: float = 0.15
    structure: float = 0.20
    bos: float = 0.10
    liquidity: float = 0.10
    order_block: float = 0.10
    premium_discount: float = 0.05
    mtf: float = 0.05

    @model_validator(mode="after")
    def _validate_sum(self) -> "QualityWeights":
        total = (
            self.impulse
            + self.gap_size
            + self.structure
            + self.bos
            + self.liquidity
            + self.order_block
            + self.premium_discount
            + self.mtf
        )
        if abs(total - 1.0) > 0.001:
            msg = f"quality_weights must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self


class FairValueGapConfig(BaseModel):
    """Configuration for institutional fair value gap analysis."""

    enabled: bool = False
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1", "H4"])
    min_candles: int = 20
    lookback: int = 100
    pip_size: float = 0.1
    min_gap_size_pips: float = 2.0
    min_impulse_body_ratio: float = 0.5
    require_impulse_candle: bool = True
    max_gap_age_bars: int = 150
    entry_touch_mode: str = "wick"
    fill_mode: str = "wick"
    invalidation_mode: str = "close"
    mitigation_mode: str = "ce"
    mitigation_fill_percent: float = 50.0
    full_fill_percent: float = 100.0
    dealing_range_mode: str = "external"
    equilibrium_tolerance_pips: float = 3.0
    mtf_enabled: bool = True
    mtf_timeframe_hierarchy: list[str] = Field(
        default_factory=lambda: ["H4", "H1", "M15"],
    )
    min_mtf_alignment_score: float = 0.5
    nesting_enabled: bool = True
    min_quality_score: float = 0.4
    require_structure_alignment: bool = False
    use_liquidity_confluence: bool = True
    use_order_block_confluence: bool = True
    quality_weights: QualityWeights = Field(default_factory=QualityWeights)
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("entry_touch_mode")
    @classmethod
    def _validate_entry_touch_mode(cls, value: str) -> str:
        allowed = {"wick", "body", "close"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"entry_touch_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("fill_mode")
    @classmethod
    def _validate_fill_mode(cls, value: str) -> str:
        allowed = {"wick", "body", "close", "ce"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"fill_mode must be one of {sorted(allowed)}"
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

    @field_validator("mitigation_mode")
    @classmethod
    def _validate_mitigation_mode(cls, value: str) -> str:
        allowed = {"ce", "partial", "full_fill"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"mitigation_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("dealing_range_mode")
    @classmethod
    def _validate_dealing_range_mode(cls, value: str) -> str:
        allowed = {"external", "internal"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"dealing_range_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("min_candles", "lookback", "max_gap_age_bars")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value < 1:
            msg = "Integer configuration values must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("pip_size", "min_gap_size_pips")
    @classmethod
    def _validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            msg = "pip_size and min_gap_size_pips must be positive"
            raise ValueError(msg)
        return value

    @field_validator("min_quality_score", "min_mtf_alignment_score")
    @classmethod
    def _validate_unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "Score thresholds must be between 0 and 1"
            raise ValueError(msg)
        return value

    @field_validator("mitigation_fill_percent", "full_fill_percent")
    @classmethod
    def _validate_fill_percent(cls, value: float) -> float:
        if not 0.0 < value <= 100.0:
            msg = "Fill percent values must be in (0, 100]"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_timeframes(self) -> "FairValueGapConfig":
        if not self.timeframes:
            msg = "timeframes cannot be empty"
            raise ValueError(msg)

        configured = {item.upper() for item in self.timeframes}
        hierarchy = [item.upper() for item in self.mtf_timeframe_hierarchy]
        if not set(hierarchy).issubset(configured):
            msg = "mtf_timeframe_hierarchy must be a subset of timeframes"
            raise ValueError(msg)
        return self

    @property
    def min_gap_size_price(self) -> float:
        return self.min_gap_size_pips * self.pip_size

    @property
    def equilibrium_tolerance_price(self) -> float:
        return self.equilibrium_tolerance_pips * self.pip_size


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
        impulse=float(raw.get("impulse", 0.25)),
        gap_size=float(raw.get("gap_size", 0.15)),
        structure=float(raw.get("structure", 0.20)),
        bos=float(raw.get("bos", 0.10)),
        liquidity=float(raw.get("liquidity", 0.10)),
        order_block=float(raw.get("order_block", 0.10)),
        premium_discount=float(raw.get("premium_discount", 0.05)),
        mtf=float(raw.get("mtf", 0.05)),
    )


def load_fair_value_gap_config(yaml_path: Path | None = None) -> FairValueGapConfig:
    """Load fair value gap configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    fvg_yaml = yaml_data.get("fair_value_gap", {})
    if not isinstance(fvg_yaml, dict):
        fvg_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("fair_value_gap", False))
    if "enabled" in fvg_yaml:
        enabled = bool(fvg_yaml["enabled"])

    timeframes = _parse_timeframes(fvg_yaml.get("timeframes"))
    mtf_hierarchy = _parse_timeframes(fvg_yaml.get("mtf_timeframe_hierarchy"))
    quality_weights = _parse_quality_weights(fvg_yaml.get("quality_weights"))

    return FairValueGapConfig(
        enabled=enabled,
        timeframes=timeframes or ["M15", "H1", "H4"],
        min_candles=int(fvg_yaml.get("min_candles", 20)),
        lookback=int(fvg_yaml.get("lookback", 100)),
        pip_size=float(fvg_yaml.get("pip_size", 0.1)),
        min_gap_size_pips=float(fvg_yaml.get("min_gap_size_pips", 2.0)),
        min_impulse_body_ratio=float(fvg_yaml.get("min_impulse_body_ratio", 0.5)),
        require_impulse_candle=bool(fvg_yaml.get("require_impulse_candle", True)),
        max_gap_age_bars=int(fvg_yaml.get("max_gap_age_bars", 150)),
        entry_touch_mode=str(fvg_yaml.get("entry_touch_mode", "wick")),
        fill_mode=str(fvg_yaml.get("fill_mode", "wick")),
        invalidation_mode=str(fvg_yaml.get("invalidation_mode", "close")),
        mitigation_mode=str(fvg_yaml.get("mitigation_mode", "ce")),
        mitigation_fill_percent=float(fvg_yaml.get("mitigation_fill_percent", 50.0)),
        full_fill_percent=float(fvg_yaml.get("full_fill_percent", 100.0)),
        dealing_range_mode=str(fvg_yaml.get("dealing_range_mode", "external")),
        equilibrium_tolerance_pips=float(
            fvg_yaml.get("equilibrium_tolerance_pips", 3.0),
        ),
        mtf_enabled=bool(fvg_yaml.get("mtf_enabled", True)),
        mtf_timeframe_hierarchy=mtf_hierarchy or ["H4", "H1", "M15"],
        min_mtf_alignment_score=float(fvg_yaml.get("min_mtf_alignment_score", 0.5)),
        nesting_enabled=bool(fvg_yaml.get("nesting_enabled", True)),
        min_quality_score=float(fvg_yaml.get("min_quality_score", 0.4)),
        require_structure_alignment=bool(
            fvg_yaml.get("require_structure_alignment", False),
        ),
        use_liquidity_confluence=bool(fvg_yaml.get("use_liquidity_confluence", True)),
        use_order_block_confluence=bool(
            fvg_yaml.get("use_order_block_confluence", True),
        ),
        quality_weights=quality_weights or QualityWeights(),
        yaml_config_path=str(config_path),
    )

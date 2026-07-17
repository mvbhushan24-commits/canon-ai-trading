"""Premium / Discount Engine configuration."""

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.yaml_loader import load_yaml_config


class PrimaryRangeMode(StrEnum):
    """Primary dealing range selection mode."""

    EXTERNAL = "external"
    INTERNAL = "internal"
    AUTO = "auto"


class SwingSelectionMode(StrEnum):
    """Swing anchor selection algorithm."""

    LATEST_CONFIRMED = "latest_confirmed"
    RANGE_EXTREME = "range_extreme"
    STRUCTURE_STATE = "structure_state"


class SwingReplacementMode(StrEnum):
    """How new swings replace existing anchors."""

    LATEST = "latest"
    CONFIRMED_ONLY = "confirmed_only"


class PriceReferenceMode(StrEnum):
    """Price reference for territory classification."""

    CLOSE = "close"
    MID = "mid"
    HLC3 = "hlc3"


class FibDirectionMode(StrEnum):
    """Fibonacci projection direction mode."""

    STRUCTURE_TREND = "structure_trend"
    BULLISH = "bullish"
    BEARISH = "bearish"
    AUTO = "auto"


class PremiumDiscountQualityWeights(BaseModel):
    """Configurable quality scoring weights."""

    swing_quality: float = 0.15
    structure_quality: float = 0.15
    liquidity_confirmation: float = 0.10
    htf_alignment: float = 0.15
    fvg_alignment: float = 0.08
    order_block_alignment: float = 0.08
    breaker_alignment: float = 0.07
    mitigation_alignment: float = 0.07
    freshness: float = 0.05
    distance_from_equilibrium: float = 0.10

    @model_validator(mode="after")
    def _validate_sum(self) -> "PremiumDiscountQualityWeights":
        total = (
            self.swing_quality
            + self.structure_quality
            + self.liquidity_confirmation
            + self.htf_alignment
            + self.fvg_alignment
            + self.order_block_alignment
            + self.breaker_alignment
            + self.mitigation_alignment
            + self.freshness
            + self.distance_from_equilibrium
        )
        if abs(total - 1.0) > 0.01:
            msg = f"quality_weights must sum to 1.0 (±0.01), got {total}"
            raise ValueError(msg)
        return self


class ZoneStatusFilters(BaseModel):
    """Upstream zone status filters for array assembly."""

    order_block_statuses: list[str] = Field(
        default_factory=lambda: ["fresh", "mitigated"],
    )
    fvg_statuses: list[str] = Field(default_factory=lambda: ["open", "partial"])
    breaker_statuses: list[str] = Field(
        default_factory=lambda: ["confirmed", "candidate"],
    )
    mitigation_statuses: list[str] = Field(
        default_factory=lambda: ["fresh", "partial", "confirmed"],
    )

    @field_validator(
        "order_block_statuses",
        "fvg_statuses",
        "breaker_statuses",
        "mitigation_statuses",
    )
    @classmethod
    def _validate_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            msg = "Zone status filter lists cannot be empty"
            raise ValueError(msg)
        return [item.strip().lower() for item in value if str(item).strip()]


class PremiumDiscountConfig(BaseModel):
    """Configuration for institutional premium / discount analysis."""

    enabled: bool = False
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1", "H4"])
    min_candles: int = 20
    lookback: int = 100
    pip_size: float = 0.1
    primary_range_mode: str = "external"
    min_range_size_pips: float = 10.0
    max_range_age_bars: int = 200
    allow_same_bar_range: bool = False
    invalidate_on_bos: bool = True
    invalidate_on_choch: bool = False
    swing_replacement_mode: str = "latest"
    swing_selection_mode: str = "latest_confirmed"
    swing_lookback_bars: int = 100
    min_swing_quality_score: float = 0.3
    prefer_labeled_swings: bool = True
    equilibrium_tolerance_pips: float = 3.0
    price_reference: str = "close"
    array_cluster_pips: float = 8.0
    min_array_entries: int = 2
    max_arrays_per_territory: int = 5
    include_liquidity_zones: bool = True
    compute_internal_bands: bool = True
    mtf_alignment_min_score: float = 0.5
    htf_range_overlap_min_percent: float = 20.0
    htf_array_overlap_min_percent: float = 15.0
    nest_overlap_min_percent: float = 80.0
    nesting_enabled: bool = True
    fibonacci_enabled: bool = True
    fibonacci_direction_mode: str = "structure_trend"
    fibonacci_levels: list[float] = Field(
        default_factory=lambda: [0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.79, 1.0],
    )
    ote_enabled: bool = True
    ote_fib_low: float = 0.62
    ote_fib_high: float = 0.79
    ote_default_direction: str = "bullish"
    ote_require_zone_overlap: bool = False
    ote_min_overlapping_zones: int = 1
    institutional_max_narrative_lines: int = 12
    institutional_include_htf_in_narrative: bool = True
    institutional_include_ote_in_narrative: bool = True
    min_quality_score: float = 0.4
    quality_weights: PremiumDiscountQualityWeights = Field(
        default_factory=PremiumDiscountQualityWeights,
    )
    zone_filters: ZoneStatusFilters = Field(default_factory=ZoneStatusFilters)
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

    @field_validator("pip_size")
    @classmethod
    def _validate_pip_size(cls, value: float) -> float:
        if value <= 0:
            msg = "pip_size must be positive"
            raise ValueError(msg)
        return value

    @field_validator("primary_range_mode")
    @classmethod
    def _validate_primary_range_mode(cls, value: str) -> str:
        allowed = {item.value for item in PrimaryRangeMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"primary_range_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("swing_selection_mode")
    @classmethod
    def _validate_swing_selection_mode(cls, value: str) -> str:
        allowed = {item.value for item in SwingSelectionMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"swing_selection_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("swing_replacement_mode")
    @classmethod
    def _validate_swing_replacement_mode(cls, value: str) -> str:
        allowed = {item.value for item in SwingReplacementMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"swing_replacement_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("price_reference")
    @classmethod
    def _validate_price_reference(cls, value: str) -> str:
        allowed = {item.value for item in PriceReferenceMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"price_reference must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("fibonacci_direction_mode")
    @classmethod
    def _validate_fib_direction_mode(cls, value: str) -> str:
        allowed = {item.value for item in FibDirectionMode}
        normalized = value.strip().lower()
        if normalized not in allowed:
            msg = f"fibonacci.direction_mode must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("ote_default_direction")
    @classmethod
    def _validate_ote_default_direction(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"bullish", "bearish"}:
            msg = "ote.default_direction must be bullish or bearish"
            raise ValueError(msg)
        return normalized

    @field_validator("timeframes")
    @classmethod
    def _validate_timeframes(cls, value: list[str]) -> list[str]:
        if not value:
            msg = "timeframes must be a non-empty list"
            raise ValueError(msg)
        return [item.strip().upper() for item in value if str(item).strip()]

    @field_validator(
        "min_swing_quality_score",
        "mtf_alignment_min_score",
        "min_quality_score",
    )
    @classmethod
    def _validate_unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "Score values must be between 0 and 1"
            raise ValueError(msg)
        return value

    @field_validator(
        "htf_range_overlap_min_percent",
        "htf_array_overlap_min_percent",
        "nest_overlap_min_percent",
    )
    @classmethod
    def _validate_percent(cls, value: float) -> float:
        if not 0.0 <= value <= 100.0:
            msg = "Percent values must be between 0 and 100"
            raise ValueError(msg)
        return value

    @field_validator("fibonacci_levels")
    @classmethod
    def _validate_fibonacci_levels(cls, value: list[float]) -> list[float]:
        if not value:
            msg = "fibonacci.levels cannot be empty"
            raise ValueError(msg)
        for level in value:
            if not 0.0 <= level <= 1.0:
                msg = "Each fibonacci level must be between 0 and 1"
                raise ValueError(msg)
        if not any(abs(level - 0.5) < 0.001 for level in value):
            msg = "fibonacci.levels must include 0.5 equilibrium level"
            raise ValueError(msg)
        return value

    @field_validator("swing_lookback_bars", "max_range_age_bars")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value < 1:
            msg = "swing_lookback_bars and max_range_age_bars must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("min_array_entries", "max_arrays_per_territory", "ote_min_overlapping_zones")
    @classmethod
    def _validate_min_one(cls, value: int) -> int:
        if value < 1:
            msg = "Array and OTE minimum values must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("min_range_size_pips", "equilibrium_tolerance_pips", "array_cluster_pips")
    @classmethod
    def _validate_non_negative(cls, value: float) -> float:
        if value < 0:
            msg = "Range, tolerance, and cluster values cannot be negative"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_ote_bounds(self) -> "PremiumDiscountConfig":
        if self.ote_fib_low >= self.ote_fib_high:
            msg = "ote.fib_low must be less than ote.fib_high"
            raise ValueError(msg)
        if not 0.0 <= self.ote_fib_low <= 1.0 or not 0.0 <= self.ote_fib_high <= 1.0:
            msg = "OTE fib ratios must be between 0 and 1"
            raise ValueError(msg)
        return self

    @property
    def equilibrium_tolerance_price(self) -> Decimal:
        return Decimal(str(self.equilibrium_tolerance_pips * self.pip_size))

    @property
    def array_cluster_price(self) -> Decimal:
        return Decimal(str(self.array_cluster_pips * self.pip_size))

    @property
    def min_range_size_price(self) -> Decimal:
        return Decimal(str(self.min_range_size_pips * self.pip_size))


def _parse_timeframes(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [item.strip().upper() for item in raw if str(item).strip()]
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_quality_weights(raw: object) -> PremiumDiscountQualityWeights | None:
    if not isinstance(raw, dict):
        return None
    return PremiumDiscountQualityWeights(
        swing_quality=float(raw.get("swing_quality", 0.15)),
        structure_quality=float(raw.get("structure_quality", 0.15)),
        liquidity_confirmation=float(raw.get("liquidity_confirmation", 0.10)),
        htf_alignment=float(raw.get("htf_alignment", 0.15)),
        fvg_alignment=float(raw.get("fvg_alignment", 0.08)),
        order_block_alignment=float(raw.get("order_block_alignment", 0.08)),
        breaker_alignment=float(raw.get("breaker_alignment", 0.07)),
        mitigation_alignment=float(raw.get("mitigation_alignment", 0.07)),
        freshness=float(raw.get("freshness", 0.05)),
        distance_from_equilibrium=float(raw.get("distance_from_equilibrium", 0.10)),
    )


def _parse_zone_filters(raw: object) -> ZoneStatusFilters | None:
    if not isinstance(raw, dict):
        return None
    return ZoneStatusFilters(
        order_block_statuses=list(
            raw.get("order_block_statuses", ["fresh", "mitigated"]),
        ),
        fvg_statuses=list(raw.get("fvg_statuses", ["open", "partial"])),
        breaker_statuses=list(raw.get("breaker_statuses", ["confirmed", "candidate"])),
        mitigation_statuses=list(
            raw.get("mitigation_statuses", ["fresh", "partial", "confirmed"]),
        ),
    )


def _parse_fibonacci_levels(raw: object) -> list[float] | None:
    if not isinstance(raw, list):
        return None
    return [float(item) for item in raw]


def load_market_premium_discount_config(
    yaml_path: Path | None = None,
) -> PremiumDiscountConfig:
    """Load premium / discount configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    pd_yaml = yaml_data.get("market_premium_discount", {})
    if not isinstance(pd_yaml, dict):
        pd_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("market_premium_discount", False))
    if "enabled" in pd_yaml:
        enabled = bool(pd_yaml["enabled"])

    timeframes = _parse_timeframes(pd_yaml.get("timeframes"))
    quality_weights = _parse_quality_weights(pd_yaml.get("quality_weights"))
    zone_filters = _parse_zone_filters(pd_yaml.get("zone_filters"))

    fibonacci_yaml = pd_yaml.get("fibonacci", {})
    if not isinstance(fibonacci_yaml, dict):
        fibonacci_yaml = {}
    ote_yaml = pd_yaml.get("ote", {})
    if not isinstance(ote_yaml, dict):
        ote_yaml = {}
    institutional_yaml = pd_yaml.get("institutional", {})
    if not isinstance(institutional_yaml, dict):
        institutional_yaml = {}

    fibonacci_levels = _parse_fibonacci_levels(fibonacci_yaml.get("levels"))

    return PremiumDiscountConfig(
        enabled=enabled,
        timeframes=timeframes or ["M15", "H1", "H4"],
        min_candles=int(pd_yaml.get("min_candles", 20)),
        lookback=int(pd_yaml.get("lookback", 100)),
        pip_size=float(pd_yaml.get("pip_size", 0.1)),
        primary_range_mode=str(pd_yaml.get("primary_range_mode", "external")),
        min_range_size_pips=float(pd_yaml.get("min_range_size_pips", 10.0)),
        max_range_age_bars=int(pd_yaml.get("max_range_age_bars", 200)),
        allow_same_bar_range=bool(pd_yaml.get("allow_same_bar_range", False)),
        invalidate_on_bos=bool(pd_yaml.get("invalidate_on_bos", True)),
        invalidate_on_choch=bool(pd_yaml.get("invalidate_on_choch", False)),
        swing_replacement_mode=str(pd_yaml.get("swing_replacement_mode", "latest")),
        swing_selection_mode=str(pd_yaml.get("swing_selection_mode", "latest_confirmed")),
        swing_lookback_bars=int(pd_yaml.get("swing_lookback_bars", 100)),
        min_swing_quality_score=float(pd_yaml.get("min_swing_quality_score", 0.3)),
        prefer_labeled_swings=bool(pd_yaml.get("prefer_labeled_swings", True)),
        equilibrium_tolerance_pips=float(
            pd_yaml.get("equilibrium_tolerance_pips", 3.0),
        ),
        price_reference=str(pd_yaml.get("price_reference", "close")),
        array_cluster_pips=float(pd_yaml.get("array_cluster_pips", 8.0)),
        min_array_entries=int(pd_yaml.get("min_array_entries", 2)),
        max_arrays_per_territory=int(pd_yaml.get("max_arrays_per_territory", 5)),
        include_liquidity_zones=bool(pd_yaml.get("include_liquidity_zones", True)),
        compute_internal_bands=bool(pd_yaml.get("compute_internal_bands", True)),
        mtf_alignment_min_score=float(pd_yaml.get("mtf_alignment_min_score", 0.5)),
        htf_range_overlap_min_percent=float(
            pd_yaml.get("htf_range_overlap_min_percent", 20.0),
        ),
        htf_array_overlap_min_percent=float(
            pd_yaml.get("htf_array_overlap_min_percent", 15.0),
        ),
        nest_overlap_min_percent=float(pd_yaml.get("nest_overlap_min_percent", 80.0)),
        nesting_enabled=bool(pd_yaml.get("nesting_enabled", True)),
        fibonacci_enabled=bool(fibonacci_yaml.get("enabled", True)),
        fibonacci_direction_mode=str(
            fibonacci_yaml.get("direction_mode", "structure_trend"),
        ),
        fibonacci_levels=fibonacci_levels
        or [0.0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.79, 1.0],
        ote_enabled=bool(ote_yaml.get("enabled", True)),
        ote_fib_low=float(ote_yaml.get("fib_low", 0.62)),
        ote_fib_high=float(ote_yaml.get("fib_high", 0.79)),
        ote_default_direction=str(ote_yaml.get("default_direction", "bullish")),
        ote_require_zone_overlap=bool(ote_yaml.get("require_zone_overlap", False)),
        ote_min_overlapping_zones=int(ote_yaml.get("min_overlapping_zones", 1)),
        institutional_max_narrative_lines=int(
            institutional_yaml.get("max_narrative_lines", 12),
        ),
        institutional_include_htf_in_narrative=bool(
            institutional_yaml.get("include_htf_in_narrative", True),
        ),
        institutional_include_ote_in_narrative=bool(
            institutional_yaml.get("include_ote_in_narrative", True),
        ),
        min_quality_score=float(pd_yaml.get("min_quality_score", 0.4)),
        quality_weights=quality_weights or PremiumDiscountQualityWeights(),
        zone_filters=zone_filters or ZoneStatusFilters(),
        yaml_config_path=str(config_path),
    )

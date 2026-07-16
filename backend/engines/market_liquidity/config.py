"""Market Liquidity Engine configuration."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from backend.core.yaml_loader import load_yaml_config


class MarketLiquidityConfig(BaseModel):
    """Configuration for institutional liquidity analysis."""

    enabled: bool = False
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1", "H4"])
    equal_high_tolerance: float = 10.0
    equal_low_tolerance: float = 10.0
    pip_size: float = 0.1
    minimum_cluster_size: int = 2
    lookback: int = 100
    min_candles: int = 20
    session_filter: list[str] = Field(
        default_factory=lambda: ["asian", "london", "new_york"],
    )
    sweep_rejection_ratio: float = 0.5
    zone_buffer_pips: float = 2.0
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("equal_high_tolerance", "equal_low_tolerance", "zone_buffer_pips")
    @classmethod
    def _validate_positive_float(cls, value: float) -> float:
        if value <= 0:
            msg = "Tolerance and buffer values must be positive"
            raise ValueError(msg)
        return value

    @field_validator("minimum_cluster_size", "lookback", "min_candles")
    @classmethod
    def _validate_positive_int(cls, value: int) -> int:
        if value < 1:
            msg = "Lookback and cluster values must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("sweep_rejection_ratio")
    @classmethod
    def _validate_ratio(cls, value: float) -> float:
        if not 0.0 < value <= 1.0:
            msg = "sweep_rejection_ratio must be between 0 and 1"
            raise ValueError(msg)
        return value

    @property
    def equal_high_tolerance_price(self) -> float:
        return self.equal_high_tolerance * self.pip_size

    @property
    def equal_low_tolerance_price(self) -> float:
        return self.equal_low_tolerance * self.pip_size

    @property
    def zone_buffer_price(self) -> float:
        return self.zone_buffer_pips * self.pip_size


def _parse_timeframes(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [item.strip().upper() for item in raw if str(item).strip()]
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_sessions(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [item.strip().lower() for item in raw if str(item).strip()]
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def load_market_liquidity_config(
    yaml_path: Path | None = None,
) -> MarketLiquidityConfig:
    """Load market liquidity configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    liquidity_yaml = yaml_data.get("market_liquidity", {})
    if not isinstance(liquidity_yaml, dict):
        liquidity_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("market_liquidity", engines_yaml.get("liquidity", False)))
    if "enabled" in liquidity_yaml:
        enabled = bool(liquidity_yaml["enabled"])

    timeframes = _parse_timeframes(liquidity_yaml.get("timeframes"))
    sessions = _parse_sessions(liquidity_yaml.get("session_filter"))

    return MarketLiquidityConfig(
        enabled=enabled,
        timeframes=timeframes or ["M15", "H1", "H4"],
        equal_high_tolerance=float(
            liquidity_yaml.get(
                "equal_high_tolerance",
                liquidity_yaml.get("equal_high_tolerance_pips", 10.0),
            ),
        ),
        equal_low_tolerance=float(
            liquidity_yaml.get(
                "equal_low_tolerance",
                liquidity_yaml.get("equal_low_tolerance_pips", 10.0),
            ),
        ),
        pip_size=float(liquidity_yaml.get("pip_size", 0.1)),
        minimum_cluster_size=int(
            liquidity_yaml.get("minimum_cluster_size", liquidity_yaml.get("min_cluster_size", 2)),
        ),
        lookback=int(liquidity_yaml.get("lookback", liquidity_yaml.get("lookback_bars", 100))),
        min_candles=int(liquidity_yaml.get("min_candles", 20)),
        session_filter=sessions or ["asian", "london", "new_york"],
        sweep_rejection_ratio=float(liquidity_yaml.get("sweep_rejection_ratio", 0.5)),
        zone_buffer_pips=float(liquidity_yaml.get("zone_buffer_pips", 2.0)),
        yaml_config_path=str(config_path),
    )

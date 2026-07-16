"""Market Structure Engine configuration."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from backend.core.config import Settings
from backend.core.yaml_loader import load_yaml_config


class MarketStructureConfig(BaseModel):
    """Configuration for market structure analysis."""

    enabled: bool = False
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1", "H4"])
    swing_lookback: int = 5
    internal_swing_lookback: int = 2
    external_swing_lookback: int = 5
    min_confidence: float = 0.5
    min_candles: int = 10
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("swing_lookback", "internal_swing_lookback", "external_swing_lookback")
    @classmethod
    def _validate_lookback(cls, value: int) -> int:
        if value < 1:
            msg = "Swing lookback must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("min_confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "min_confidence must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value


def _parse_timeframes(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [item.strip().upper() for item in raw if str(item).strip()]
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def load_market_structure_config(
    settings: Settings | None = None,
    yaml_path: Path | None = None,
) -> MarketStructureConfig:
    """Load market structure configuration from YAML."""
    config_path = yaml_path or Path("config/settings.yaml")
    yaml_data = load_yaml_config(config_path)
    structure_yaml = yaml_data.get("market_structure", {})
    if not isinstance(structure_yaml, dict):
        structure_yaml = {}

    engines_yaml = yaml_data.get("engines", {})
    enabled = bool(engines_yaml.get("market_structure", False))
    if "enabled" in structure_yaml:
        enabled = bool(structure_yaml["enabled"])

    timeframes = _parse_timeframes(structure_yaml.get("timeframes"))
    if timeframes is None:
        timeframes = _parse_timeframes(structure_yaml.get("STRUCTURE_TIMEFRAMES"))

    return MarketStructureConfig(
        enabled=enabled,
        timeframes=timeframes or ["M15", "H1", "H4"],
        swing_lookback=int(structure_yaml.get("swing_lookback", 5)),
        internal_swing_lookback=int(structure_yaml.get("internal_swing_lookback", 2)),
        external_swing_lookback=int(structure_yaml.get("external_swing_lookback", 5)),
        min_confidence=float(structure_yaml.get("min_confidence", 0.5)),
        min_candles=int(structure_yaml.get("min_candles", 10)),
        yaml_config_path=str(config_path),
    )

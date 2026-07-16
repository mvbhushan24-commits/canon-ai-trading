"""Market Data Engine configuration."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from backend.core.config import Settings, get_settings
from backend.core.yaml_loader import load_yaml_config
from backend.engines.market_data.exceptions import InvalidTimeframeError
from backend.engines.market_data.timeframes import SUPPORTED_TIMEFRAMES, validate_timeframes


class MarketDataConfig(BaseModel):
    """Merged environment and YAML configuration for the Market Data Engine."""

    symbol: str = "XAUUSD"
    broker: str = "XMGlobal"
    timeframes: list[str] = Field(default_factory=lambda: ["M1", "M5", "M15", "H1", "H4", "D1"])
    tick_enabled: bool = True
    history_bars: int = 500
    stale_threshold_sec: int = 30
    mt5_terminal_path: str = ""
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    yaml_config_path: str = "config/settings.yaml"

    @field_validator("timeframes")
    @classmethod
    def _validate_timeframes(cls, value: list[str]) -> list[str]:
        try:
            return validate_timeframes(value)
        except InvalidTimeframeError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("history_bars")
    @classmethod
    def _validate_history_bars(cls, value: int) -> int:
        if value < 1:
            msg = "history_bars must be at least 1"
            raise ValueError(msg)
        return value

    @field_validator("stale_threshold_sec")
    @classmethod
    def _validate_stale_threshold(cls, value: int) -> int:
        if value < 1:
            msg = "stale_threshold_sec must be at least 1"
            raise ValueError(msg)
        return value


def _parse_timeframes(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_market_data_config(
    settings: Settings | None = None,
    yaml_path: Path | None = None,
) -> MarketDataConfig:
    """Load Market Data configuration from environment and YAML."""
    app_settings = settings or get_settings()
    config_path = yaml_path or Path("config/settings.yaml")

    yaml_data = load_yaml_config(config_path)
    market_data_yaml = yaml_data.get("market_data", {})
    if not isinstance(market_data_yaml, dict):
        market_data_yaml = {}

    timeframes = _parse_timeframes(market_data_yaml.get("timeframes"))
    if timeframes is None:
        timeframes = _parse_timeframes(market_data_yaml.get("MARKET_DATA_TIMEFRAMES"))

    return MarketDataConfig(
        symbol=str(market_data_yaml.get("symbol", app_settings.symbol)),
        broker=str(market_data_yaml.get("broker", app_settings.broker)),
        timeframes=timeframes or ["M1", "M5", "M15", "H1", "H4", "D1"],
        tick_enabled=bool(market_data_yaml.get("tick_enabled", True)),
        history_bars=int(market_data_yaml.get("history_bars", 500)),
        stale_threshold_sec=int(market_data_yaml.get("stale_threshold_sec", 30)),
        mt5_terminal_path=app_settings.mt5_terminal_path,
        mt5_login=app_settings.mt5_login,
        mt5_password=app_settings.mt5_password,
        mt5_server=app_settings.mt5_server,
        yaml_config_path=str(config_path),
    )


def supported_timeframes_list() -> list[str]:
    """Return all supported timeframe identifiers."""
    return sorted(SUPPORTED_TIMEFRAMES)

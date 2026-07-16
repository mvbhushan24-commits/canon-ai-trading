"""Unit tests for market data configuration."""

from pathlib import Path

import pytest
import yaml

from backend.core.config import Settings
from backend.engines.market_data.config import MarketDataConfig, load_market_data_config


def test_market_data_config_validates_timeframes() -> None:
    with pytest.raises(ValueError):
        MarketDataConfig(timeframes=["INVALID"])


def test_market_data_config_validates_history_bars() -> None:
    with pytest.raises(ValueError):
        MarketDataConfig(history_bars=0)


def test_load_market_data_config_from_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "settings.yaml"
    yaml_path.write_text(
        yaml.dump(
            {
                "market_data": {
                    "timeframes": ["M5", "H1"],
                    "tick_enabled": False,
                    "history_bars": 250,
                    "stale_threshold_sec": 45,
                }
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        TRADING_SYMBOL="XAUUSD",
        BROKER="XMGlobal",
        MT5_LOGIN="111",
        MT5_PASSWORD="pass",
        MT5_SERVER="XMGlobal-MT5",
    )
    config = load_market_data_config(settings=settings, yaml_path=yaml_path)

    assert config.symbol == "XAUUSD"
    assert config.timeframes == ["M5", "H1"]
    assert config.tick_enabled is False
    assert config.history_bars == 250
    assert config.stale_threshold_sec == 45
    assert config.mt5_login == "111"

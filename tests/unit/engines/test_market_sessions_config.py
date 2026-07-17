"""Unit tests for market sessions configuration."""

from pathlib import Path

import pytest

pytest_plugins = ["tests.unit.engines.market_sessions_conftest"]

from backend.engines.market_sessions.config import (
    KillZoneWindowConfig,
    MarketSessionsConfig,
    QualityWeights,
    SessionWindowConfig,
    load_market_sessions_config,
    validate_config_timezones,
)
from backend.engines.market_sessions.exceptions import ConfigInvalidError


def test_default_config_has_all_sessions() -> None:
    config = MarketSessionsConfig()
    assert set(config.sessions.keys()) == {"sydney", "tokyo", "london", "new_york"}
    assert set(config.kill_zones.keys()) == {
        "asian",
        "london_open",
        "new_york",
        "london_close",
    }
    assert "london_new_york" in config.overlaps


def test_session_window_time_validation() -> None:
    with pytest.raises(ValueError, match="Invalid time format"):
        SessionWindowConfig(local_start="invalid", local_end="17:00")
    with pytest.raises(ValueError, match="must differ"):
        SessionWindowConfig(local_start="08:00", local_end="08:00")


def test_kill_zone_window_validation() -> None:
    with pytest.raises(ValueError, match="must differ"):
        KillZoneWindowConfig(utc_start="07:00", utc_end="07:00")


def test_quality_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="quality_weights must sum to 1.0"):
        QualityWeights(
            session_quality=0.5,
            kill_zone_quality=0.5,
            overlap_quality=0.5,
            volatility=0.5,
            liquidity_availability=0.5,
            historical_performance=0.5,
        )


def test_timeframes_normalized_to_uppercase() -> None:
    config = MarketSessionsConfig(timeframes=["m15", "h1"])
    assert config.timeframes == ["M15", "H1"]


def test_min_candles_must_be_positive() -> None:
    with pytest.raises(ValueError, match="min_candles"):
        MarketSessionsConfig(min_candles=0)


def test_load_market_sessions_config_from_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(
        """
market_sessions:
  enabled: true
  timeframes:
    - M15
    - H1
  min_candles: 15
  lookback: 200
  pip_size: 0.1
  broker_timezone: Europe/Nicosia
  broker_day_start_hour: 0
  weekend_trading_enabled: false
  allow_partial_analysis: true
  session_priority:
    - london
    - new_york
  sessions:
    london:
      enabled: true
      timezone: Europe/London
      local_start: "08:00"
      local_end: "17:00"
  kill_zones:
    require_active_session: true
    london_open:
      enabled: true
      parent_session: london
      utc_start: "07:00"
      utc_end: "10:00"
  overlaps:
    london_new_york:
      enabled: true
      sessions:
        - london
        - new_york
  opening_range:
    enabled: true
    duration_minutes: 30
    min_candles: 2
    sessions:
      - london
  initial_balance:
    enabled: true
    duration_minutes: 60
    min_candles: 4
    sessions:
      - london
  time_of_day_filter:
    mode: kill_zone_only
    block_list:
      - sydney
  calendar:
    weekend_days:
      - saturday
      - sunday
    holidays:
      enabled: true
      dates:
        - "2026-01-01"
  transitions:
    forecast_hours: 12
    imminent_minutes: 10
  min_quality_score: 0.35
  high_quality_threshold: 0.75
engines:
  market_sessions: true
""",
        encoding="utf-8",
    )

    config = load_market_sessions_config(yaml_path=yaml_file)

    assert config.enabled is True
    assert config.timeframes == ["M15", "H1"]
    assert config.min_candles == 15
    assert config.lookback == 200
    assert config.weekend_trading_enabled is False
    assert config.kill_zones_require_active_session is True
    assert config.session_priority == ["london", "new_york"]
    assert config.opening_range.duration_minutes == 30
    assert config.initial_balance.duration_minutes == 60
    assert config.time_of_day_filter.mode == "kill_zone_only"
    assert "2026-01-01" in config.calendar.holidays.dates
    assert config.transitions.forecast_hours == 12


def test_validate_config_timezones_rejects_invalid_broker_tz() -> None:
    config = MarketSessionsConfig(broker_timezone="Not/A/Timezone")
    with pytest.raises(ConfigInvalidError, match="Invalid broker timezone"):
        validate_config_timezones(config)


def test_validate_config_timezones_rejects_invalid_session_tz() -> None:
    config = MarketSessionsConfig()
    config = config.model_copy(
        update={
            "sessions": {
                **config.sessions,
                "london": SessionWindowConfig(timezone="Bad/Zone"),
            },
        },
    )
    with pytest.raises(ConfigInvalidError, match="Invalid session timezone"):
        validate_config_timezones(config)


def test_validate_config_timezones_rejects_invalid_filter_mode() -> None:
    config = MarketSessionsConfig()
    config = config.model_copy(
        update={
            "time_of_day_filter": config.time_of_day_filter.model_copy(
                update={"mode": "invalid_mode"},
            ),
        },
    )
    with pytest.raises(ConfigInvalidError, match="Invalid filter mode"):
        validate_config_timezones(config)


def test_validate_config_timezones_rejects_unknown_overlap_session() -> None:
    from backend.engines.market_sessions.config import OverlapConfig

    config = MarketSessionsConfig()
    config = config.model_copy(
        update={
            "overlaps": {
                "bad_overlap": OverlapConfig(sessions=["london", "unknown_session"]),
            },
        },
    )
    with pytest.raises(ConfigInvalidError, match="Unknown session"):
        validate_config_timezones(config)


def test_validate_config_timezones_rejects_unknown_kill_zone_id() -> None:
    config = MarketSessionsConfig()
    config = config.model_copy(
        update={
            "kill_zones": {
                **config.kill_zones,
                "custom_zone": KillZoneWindowConfig(
                    parent_session="london",
                    utc_start="06:00",
                    utc_end="07:00",
                ),
            },
        },
    )
    with pytest.raises(ConfigInvalidError, match="Unknown kill zone id"):
        validate_config_timezones(config)


def test_config_property_accessors(market_sessions_cfg) -> None:
    assert market_sessions_cfg.enabled is True
    assert market_sessions_cfg.pip_size == 0.1
    assert market_sessions_cfg.session_phases.opening_phase_minutes == 60
    assert market_sessions_cfg.opens.daily_enabled is True
    assert market_sessions_cfg.session_extremes.enabled is True

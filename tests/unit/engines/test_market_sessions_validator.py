"""Unit tests for market sessions input validator."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.market_sessions_conftest"]

from backend.engines.market_sessions.exceptions import (
    ConfigInvalidError,
    InsufficientDataError,
    InvalidLiquidityStateError,
    InvalidPremiumDiscountError,
    InvalidStructureError,
    InvalidTimestampError,
    InvalidTimezoneError,
    StateCorruptError,
    ValidationError,
)
from backend.engines.market_sessions.schemas import MarketSessionsState
from backend.engines.market_sessions.validator import MarketSessionsInputValidator
from tests.unit.engines.conftest import make_candle
from tests.unit.engines.market_sessions_conftest import (
    build_market_sessions_candles,
    market_sessions_config,
    sample_liquidity_state,
    sample_premium_discount_analysis,
)
from tests.unit.engines.premium_discount_conftest import build_premium_discount_structure


def test_validate_candles_success(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator()
    result = validator.validate_candles(market_sessions_candles)
    assert result.is_valid


def test_validate_candles_empty() -> None:
    validator = MarketSessionsInputValidator()
    result = validator.validate_candles([])
    assert not result.is_valid
    assert "empty" in result.errors[0].lower()


def test_validate_candles_mixed_symbols() -> None:
    validator = MarketSessionsInputValidator()
    candles = build_market_sessions_candles(5)
    bad = candles[0].model_copy(update={"symbol": "EURUSD"})
    mixed = [bad, *candles[1:]]
    result = validator.validate_candles(mixed)
    assert not result.is_valid


def test_validate_candles_invalid_ohlc() -> None:
    validator = MarketSessionsInputValidator()
    bad = make_candle(
        open_time=datetime(2026, 1, 14, 8, 0, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    result = validator.validate_candles([bad])
    assert not result.is_valid


def test_validate_timestamp_requires_utc() -> None:
    validator = MarketSessionsInputValidator()
    naive = datetime(2026, 1, 14, 8, 0)
    result = validator.validate_timestamp(naive)
    assert not result.is_valid

    # Timezone-aware timestamps are normalized to UTC before validation.
    aware = datetime(2026, 1, 14, 8, 0, tzinfo=timezone(timedelta(hours=2)))
    result_aware = validator.validate_timestamp(aware)
    assert result_aware.is_valid


def test_validate_timestamp_success() -> None:
    validator = MarketSessionsInputValidator()
    result = validator.validate_timestamp(datetime(2026, 1, 14, 8, 0, tzinfo=UTC))
    assert result.is_valid


def test_validate_broker_timezone_invalid() -> None:
    validator = MarketSessionsInputValidator()
    result = validator.validate_broker_timezone("Not/Real/Zone")
    assert not result.is_valid


def test_validate_broker_timezone_success() -> None:
    validator = MarketSessionsInputValidator()
    result = validator.validate_broker_timezone("Europe/London")
    assert result.is_valid


def test_validate_structure_mismatch(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator()
    structure = build_premium_discount_structure().model_copy(update={"symbol": "OTHER"})
    result = validator.validate_structure(
        structure,
        symbol=market_sessions_candles[0].symbol,
        timeframe="M15",
    )
    assert not result.is_valid


def test_validate_structure_none_is_valid() -> None:
    validator = MarketSessionsInputValidator()
    result = validator.validate_structure(None, symbol="XAUUSD", timeframe="M15")
    assert result.is_valid


def test_validate_liquidity_state_bar_count(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator()
    state = sample_liquidity_state().model_copy(update={"bar_count": 999})
    result = validator.validate_liquidity_state(state, bar_count=len(market_sessions_candles))
    assert not result.is_valid


def test_validate_premium_discount_mismatch(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator()
    pd = sample_premium_discount_analysis().model_copy(update={"symbol": "OTHER"})
    result = validator.validate_premium_discount(
        pd,
        symbol=market_sessions_candles[0].symbol,
        timeframe="M15",
    )
    assert not result.is_valid


def test_validate_prior_state_negative_bar_count() -> None:
    validator = MarketSessionsInputValidator()
    state = MarketSessionsState(bar_count=-1)
    result = validator.validate_prior_state(state)
    assert not result.is_valid


def test_validate_configuration_invalid_holiday_file() -> None:
    config = market_sessions_config()
    config = config.model_copy(
        update={
            "calendar": config.calendar.model_copy(
                update={
                    "holidays": config.calendar.holidays.model_copy(
                        update={"enabled": True, "file": "missing/holidays.yaml"},
                    ),
                },
            ),
        },
    )
    validator = MarketSessionsInputValidator(config)
    result = validator.validate_configuration(config)
    assert not result.is_valid
    assert any("Holiday calendar file not found" in error for error in result.errors)


def test_validate_or_raise_configuration() -> None:
    config = market_sessions_config(broker_timezone="Bad/Zone")
    validator = MarketSessionsInputValidator(config)
    with pytest.raises(ConfigInvalidError):
        validator.validate_or_raise_configuration(config)


def test_validate_or_raise_bad_candles() -> None:
    validator = MarketSessionsInputValidator(market_sessions_config())
    bad = make_candle(
        open_time=datetime(2026, 1, 14, 8, 0, tzinfo=UTC),
        open_price=Decimal("100"),
        high=Decimal("90"),
        low=Decimal("95"),
        close=Decimal("92"),
    )
    with pytest.raises(ValidationError):
        validator.validate_or_raise(
            [bad],
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            "Europe/Nicosia",
        )


def test_validate_or_raise_invalid_timestamp(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator(market_sessions_config())
    with pytest.raises(InvalidTimestampError):
        validator.validate_or_raise(
            market_sessions_candles,
            datetime(2026, 1, 14, 8, 30),
            "Europe/Nicosia",
        )


def test_validate_or_raise_invalid_timezone(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator(market_sessions_config())
    with pytest.raises(InvalidTimezoneError):
        validator.validate_or_raise(
            market_sessions_candles,
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            "Bad/Zone",
        )


def test_validate_or_raise_structure_mismatch(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator(market_sessions_config())
    structure = build_premium_discount_structure().model_copy(update={"symbol": "WRONG"})
    with pytest.raises(InvalidStructureError):
        validator.validate_or_raise(
            market_sessions_candles,
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            "Europe/Nicosia",
            structure=structure,
        )


def test_validate_or_raise_liquidity_state(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator(market_sessions_config())
    state = sample_liquidity_state().model_copy(update={"bar_count": 999})
    with pytest.raises(InvalidLiquidityStateError):
        validator.validate_or_raise(
            market_sessions_candles,
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            "Europe/Nicosia",
            liquidity_state=state,
        )


def test_validate_or_raise_premium_discount(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator(market_sessions_config())
    pd = sample_premium_discount_analysis().model_copy(update={"timeframe": "H4"})
    with pytest.raises(InvalidPremiumDiscountError):
        validator.validate_or_raise(
            market_sessions_candles,
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            "Europe/Nicosia",
            premium_discount=pd,
        )


def test_validate_or_raise_state_corrupt(market_sessions_candles) -> None:
    validator = MarketSessionsInputValidator(market_sessions_config())
    with pytest.raises(StateCorruptError):
        validator.validate_or_raise(
            market_sessions_candles,
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            "Europe/Nicosia",
            prior_state=MarketSessionsState(bar_count=-1),
        )


def test_validate_or_raise_insufficient_candles_strict() -> None:
    config = market_sessions_config(min_candles=20, allow_partial_analysis=False)
    validator = MarketSessionsInputValidator(config)
    candles = build_market_sessions_candles(5)
    with pytest.raises(InsufficientDataError):
        validator.validate_or_raise(
            candles,
            datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
            "Europe/Nicosia",
        )


def test_validate_or_raise_allows_partial_analysis() -> None:
    config = market_sessions_config(min_candles=20, allow_partial_analysis=True)
    validator = MarketSessionsInputValidator(config)
    candles = build_market_sessions_candles(5)
    validator.validate_or_raise(
        candles,
        datetime(2026, 1, 14, 8, 30, tzinfo=UTC),
        "Europe/Nicosia",
        strict_candle_count=True,
    )

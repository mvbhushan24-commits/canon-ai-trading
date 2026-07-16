"""Unit tests for Market Data Engine orchestrator."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.engines.market_data.engine import MarketDataEngine
from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.exceptions import MT5ConnectionError, StaleFeedError
from backend.engines.market_data.schemas import HistoryRequest
from tests.conftest import MockMT5Client, MockTick


def test_engine_start_stop(
    market_data_config,
    mock_mt5_client: MockMT5Client,
    event_publisher: EventPublisher,
) -> None:
    engine = MarketDataEngine(
        config=market_data_config,
        client=mock_mt5_client,
        event_publisher=event_publisher,
    )
    engine.start()
    status = engine.get_status()

    assert status.status.value == "connected"
    engine.stop()
    assert mock_mt5_client.shutdown_called is True


def test_engine_load_historical_candles(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)
    engine.start()
    candles = engine.load_historical_candles(timeframe="H1", count=3)

    assert len(candles) == 3
    engine.stop()


def test_engine_get_latest_tick_and_candle(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)
    engine.start()

    tick = engine.get_latest_tick()
    candle = engine.get_latest_candle(timeframe="H1")

    assert tick.symbol == "XAUUSD"
    assert candle.timeframe == "H1"
    engine.stop()


def test_engine_load_historical_range(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)
    engine.start()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    response = engine.load_historical_range(
        HistoryRequest(
            symbol="XAUUSD",
            timeframe="H1",
            from_utc=start,
            to_utc=start + timedelta(hours=2),
        )
    )

    assert response.bar_count == 3
    engine.stop()


def test_engine_validate_candles(
    market_data_config,
    mock_mt5_client: MockMT5Client,
    sample_candles,
) -> None:
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)
    result = engine.validate_candles(sample_candles)

    assert result.is_valid is True


def test_engine_get_symbol_metadata(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)
    engine.start()
    metadata = engine.get_symbol_metadata("XAUUSD")

    assert metadata.symbol == "XAUUSD"
    assert metadata.digits == 2
    engine.stop()


def test_engine_start_failure(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    mock_mt5_client.initialize_result = False
    mock_mt5_client.last_error_value = (1, "Init failed")
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)

    with pytest.raises(MT5ConnectionError):
        engine.start()


def test_engine_handle_shutdown_event(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)
    engine.start()
    engine.handle_shutdown_event()

    assert mock_mt5_client.shutdown_called is True


def test_engine_check_stale_feed_raises(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    stale_time = int((datetime.now(tz=UTC) - timedelta(minutes=5)).timestamp())
    mock_mt5_client.ticks["XAUUSD"] = MockTick(bid=2350.0, ask=2350.5, time=stale_time)
    engine = MarketDataEngine(config=market_data_config, client=mock_mt5_client)
    engine.start()

    with pytest.raises(StaleFeedError):
        engine.check_stale_feed()

    engine.stop()


def test_public_package_exports() -> None:
    from backend.engines import market_data

    assert hasattr(market_data, "MarketDataEngine")
    assert hasattr(market_data, "NormalizedCandle")
    assert hasattr(market_data, "NormalizedTick")

"""Unit tests for historical and live data loaders."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.exceptions import (
    HistoryLoadError,
    StaleFeedError,
    SymbolUnavailableError,
)
from backend.engines.market_data.historical import HistoricalDataLoader
from backend.engines.market_data.live import LiveMarketDataLoader
from backend.engines.market_data.normalizer import MarketDataNormalizer
from backend.engines.market_data.schemas import HistoryRequest
from backend.engines.market_data.validator import DataValidator
from tests.conftest import MockMT5Client, MockTick


def test_historical_loader_load_bars(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    loader = HistoricalDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
        DataValidator(),
    )
    candles = loader.load_bars("XAUUSD", "H1", 5)

    assert len(candles) == 5
    assert candles[0].symbol == "XAUUSD"
    assert candles[0].timeframe == "H1"
    assert candles[0].is_closed is True


def test_historical_loader_failure(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    mock_mt5_client.rates.clear()
    loader = HistoricalDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
        DataValidator(),
    )

    with pytest.raises(HistoryLoadError):
        loader.load_bars("XAUUSD", "H1")


def test_historical_loader_range(
    market_data_config,
    mock_mt5_client: MockMT5Client,
    event_publisher: EventPublisher,
) -> None:
    events: list[str] = []
    event_publisher.subscribe("market.history.loaded", lambda e: events.append(e.event_type))
    loader = HistoricalDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
        DataValidator(),
        event_publisher,
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    response = loader.load_range(
        HistoryRequest(
            symbol="XAUUSD",
            timeframe="H1",
            from_utc=start,
            to_utc=start + timedelta(hours=5),
            request_id="req-1",
        )
    )

    assert response.error is None
    assert response.bar_count == 6
    assert response.request_id == "req-1"
    assert events == ["market.history.loaded"]


def test_historical_loader_invalid_range(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    loader = HistoricalDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
        DataValidator(),
    )
    now = datetime.now(tz=UTC)
    response = loader.load_range(
        HistoryRequest(symbol="XAUUSD", timeframe="H1", from_utc=now, to_utc=now)
    )
    assert response.error == "from_utc must be before to_utc"


def test_live_loader_latest_tick(
    market_data_config,
    mock_mt5_client: MockMT5Client,
    event_publisher: EventPublisher,
) -> None:
    events: list[str] = []
    event_publisher.subscribe("market.tick.received", lambda e: events.append(e.event_type))
    loader = LiveMarketDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
        event_publisher,
    )
    tick = loader.get_latest_tick("XAUUSD")

    assert tick.symbol == "XAUUSD"
    assert tick.bid > 0
    assert events == ["market.tick.received"]


def test_live_loader_latest_candle(
    market_data_config,
    mock_mt5_client: MockMT5Client,
    event_publisher: EventPublisher,
) -> None:
    events: list[str] = []
    event_publisher.subscribe("market.candle.updated", lambda e: events.append(e.event_type))
    loader = LiveMarketDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
        event_publisher,
    )
    candle = loader.get_latest_candle("XAUUSD", "H1")

    assert candle.symbol == "XAUUSD"
    assert candle.is_closed is False
    assert events == ["market.candle.updated"]


def test_live_loader_stale_feed(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    stale_time = int((datetime.now(tz=UTC) - timedelta(minutes=5)).timestamp())
    mock_mt5_client.ticks["XAUUSD"] = MockTick(bid=2350.0, ask=2350.5, time=stale_time)
    loader = LiveMarketDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
    )

    with pytest.raises(StaleFeedError):
        loader.check_stale_feed("XAUUSD")


def test_live_loader_tick_disabled(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    market_data_config.tick_enabled = False
    loader = LiveMarketDataLoader(
        market_data_config,
        mock_mt5_client,
        MarketDataNormalizer(),
    )

    with pytest.raises(SymbolUnavailableError):
        loader.get_latest_tick("XAUUSD")

"""Unit tests for MT5 connection manager."""

import pytest

from backend.engines.market_data.connection import MT5ConnectionManager
from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.exceptions import MT5AuthenticationError, MT5ConnectionError
from backend.engines.market_data.schemas import EngineConnectionStatus
from tests.conftest import MockMT5Client


def test_connect_success(
    market_data_config,
    mock_mt5_client: MockMT5Client,
    event_publisher: EventPublisher,
) -> None:
    manager = MT5ConnectionManager(market_data_config, mock_mt5_client, event_publisher)
    events: list[str] = []
    event_publisher.subscribe(
        "market.connection.established",
        lambda event: events.append(event.event_type),
    )

    manager.connect()

    assert manager.is_connected is True
    assert manager.get_connection_status() == EngineConnectionStatus.CONNECTED
    assert events == ["market.connection.established"]


def test_connect_initialization_failure(market_data_config, mock_mt5_client: MockMT5Client) -> None:
    mock_mt5_client.initialize_result = False
    mock_mt5_client.last_error_value = (1, "Init failed")
    manager = MT5ConnectionManager(market_data_config, mock_mt5_client)

    with pytest.raises(MT5ConnectionError) as exc_info:
        manager.connect()

    assert exc_info.value.code == "MDE_CONN_FAILED"
    assert manager.is_connected is False


def test_connect_authentication_failure(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    mock_mt5_client.account_info_obj = None  # type: ignore[assignment]
    manager = MT5ConnectionManager(market_data_config, mock_mt5_client)

    with pytest.raises(MT5AuthenticationError) as exc_info:
        manager.connect()

    assert exc_info.value.code == "MDE_AUTH_FAILED"


def test_disconnect_graceful(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    manager = MT5ConnectionManager(market_data_config, mock_mt5_client)
    manager.connect()
    manager.disconnect()

    assert manager.is_connected is False
    assert mock_mt5_client.shutdown_called is True


def test_disconnect_when_not_connected(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    manager = MT5ConnectionManager(market_data_config, mock_mt5_client)
    manager.disconnect()
    assert mock_mt5_client.shutdown_called is False

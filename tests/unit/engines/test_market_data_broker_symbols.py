"""Unit tests for broker and symbol managers."""

import pytest

from backend.engines.market_data.broker import BrokerValidator
from backend.engines.market_data.exceptions import MT5ConnectionError, SymbolUnavailableError
from backend.engines.market_data.symbols import SymbolManager
from tests.conftest import MockMT5Client


def test_broker_validator_success(market_data_config, mock_mt5_client: MockMT5Client) -> None:
    result = BrokerValidator(market_data_config, mock_mt5_client).validate("XAUUSD")

    assert result["symbol"] == "XAUUSD"
    assert result["symbol_available"] is True
    assert result["market_open"] is True


def test_broker_validator_connection_failure(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    mock_mt5_client.account_info_obj = None  # type: ignore[assignment]
    with pytest.raises(MT5ConnectionError):
        BrokerValidator(market_data_config, mock_mt5_client).validate_connection()


def test_broker_validator_symbol_unavailable(
    market_data_config,
    mock_mt5_client: MockMT5Client,
) -> None:
    with pytest.raises(SymbolUnavailableError):
        BrokerValidator(market_data_config, mock_mt5_client).validate_symbol_availability("EURUSD")


def test_symbol_manager_load_and_validate(mock_mt5_client: MockMT5Client) -> None:
    manager = SymbolManager(mock_mt5_client)
    loaded = manager.load_available_symbols()

    assert len(loaded) == 1
    assert loaded[0].symbol == "XAUUSD"
    metadata = manager.validate_symbol("XAUUSD")
    assert metadata.symbol == "XAUUSD"
    assert "XAUUSD" in manager.list_symbols()


def test_symbol_manager_invalid_symbol(mock_mt5_client: MockMT5Client) -> None:
    manager = SymbolManager(mock_mt5_client)
    manager.load_available_symbols()

    with pytest.raises(SymbolUnavailableError):
        manager.validate_symbol("NOSYMBOL")

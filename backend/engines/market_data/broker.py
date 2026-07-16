"""Broker validation for XMGlobal via MT5."""

import logging

from backend.engines.market_data.config import MarketDataConfig
from backend.engines.market_data.exceptions import MT5ConnectionError, SymbolUnavailableError
from backend.engines.market_data.mt5_protocol import MT5ClientProtocol

logger = logging.getLogger(__name__)

TRADE_MODE_DISABLED = 0
TRADE_MODE_LONGONLY = 1
TRADE_MODE_SHORTONLY = 2
TRADE_MODE_CLOSEONLY = 3
TRADE_MODE_FULL = 4


class BrokerValidator:
    """Verify broker connection, symbol availability, and market status."""

    def __init__(self, config: MarketDataConfig, client: MT5ClientProtocol) -> None:
        self._config = config
        self._client = client

    def validate(self, symbol: str | None = None) -> dict[str, object]:
        """Run all broker validation checks."""
        target_symbol = symbol or self._config.symbol
        connection = self.validate_connection()
        symbol_info = self.validate_symbol_availability(target_symbol)
        market_status = self.validate_market_status(target_symbol)

        result = {
            "broker": self._config.broker,
            "symbol": target_symbol,
            "connection": connection,
            "symbol_available": True,
            "market_open": market_status["market_open"],
            "trade_mode": market_status["trade_mode"],
            "digits": getattr(symbol_info, "digits", None),
        }
        logger.info("Broker validation passed", extra=result)
        return result

    def validate_connection(self) -> dict[str, object]:
        account_info = self._client.account_info()
        if account_info is None:
            code, message = self._client.last_error()
            logger.error(
                "Broker connection validation failed",
                extra={"code": "MDE_CONN_FAILED", "mt5_code": code},
            )
            raise MT5ConnectionError(
                f"Broker connection unavailable: {message}",
                details={"mt5_code": code},
            )

        return {
            "login": getattr(account_info, "login", None),
            "server": getattr(account_info, "server", None),
            "company": getattr(account_info, "company", None),
            "balance": getattr(account_info, "balance", None),
        }

    def validate_symbol_availability(self, symbol: str) -> object:
        info = self._client.symbol_info(symbol)
        if info is None:
            selected = self._client.symbol_select(symbol, True)
            info = self._client.symbol_info(symbol)
            if info is None or not selected:
                code, message = self._client.last_error()
                logger.error(
                    "Symbol unavailable",
                    extra={"code": "MDE_SYMBOL_UNAVAILABLE", "symbol": symbol, "mt5_code": code},
                )
                raise SymbolUnavailableError(
                    f"Symbol '{symbol}' is not available: {message}",
                    details={"symbol": symbol, "mt5_code": code},
                )

        logger.info(
            "Symbol available",
            extra={"symbol": symbol, "visible": getattr(info, "visible", False)},
        )
        return info

    def validate_market_status(self, symbol: str) -> dict[str, object]:
        info = self._client.symbol_info(symbol)
        if info is None:
            raise SymbolUnavailableError(
                f"Cannot verify market status — symbol '{symbol}' unavailable",
                details={"symbol": symbol},
            )

        trade_mode = int(getattr(info, "trade_mode", TRADE_MODE_DISABLED))
        market_open = trade_mode in {
            TRADE_MODE_LONGONLY,
            TRADE_MODE_SHORTONLY,
            TRADE_MODE_CLOSEONLY,
            TRADE_MODE_FULL,
        }

        logger.info(
            "Market status checked",
            extra={"symbol": symbol, "trade_mode": trade_mode, "market_open": market_open},
        )
        return {"market_open": market_open, "trade_mode": trade_mode}

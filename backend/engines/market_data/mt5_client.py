"""Real MetaTrader 5 client wrapper."""

from datetime import datetime
from typing import Any

from backend.engines.market_data.mt5_protocol import MT5ClientProtocol


class MT5Client:
    """Thin wrapper around the MetaTrader5 Python package."""

    def __init__(self, mt5_module: Any | None = None) -> None:
        if mt5_module is None:
            import MetaTrader5 as mt5  # type: ignore[import-untyped]

            self._mt5 = mt5
        else:
            self._mt5 = mt5_module

    def initialize(self, path: str = "") -> bool:
        if path:
            return bool(self._mt5.initialize(path=path))
        return bool(self._mt5.initialize())

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def last_error(self) -> tuple[int, str]:
        result = self._mt5.last_error()
        if isinstance(result, tuple) and len(result) >= 2:
            return int(result[0]), str(result[1])
        return -1, "Unknown MT5 error"

    def terminal_info(self) -> Any | None:
        return self._mt5.terminal_info()

    def account_info(self) -> Any | None:
        return self._mt5.account_info()

    def login(self, login: int, password: str, server: str) -> bool:
        return bool(self._mt5.login(login=login, password=password, server=server))

    def symbols_get(self) -> list[Any] | None:
        result = self._mt5.symbols_get()
        if result is None:
            return None
        return list(result)

    def symbol_info(self, symbol: str) -> Any | None:
        return self._mt5.symbol_info(symbol)

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        return bool(self._mt5.symbol_select(symbol, enable))

    def symbol_info_tick(self, symbol: str) -> Any | None:
        return self._mt5.symbol_info_tick(symbol)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any | None:
        return self._mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> Any | None:
        return self._mt5.copy_rates_range(symbol, timeframe, date_from, date_to)

    def get_timeframe_constants(self) -> dict[str, int]:
        mt5 = self._mt5
        return {
            "TIMEFRAME_M1": mt5.TIMEFRAME_M1,
            "TIMEFRAME_M5": mt5.TIMEFRAME_M5,
            "TIMEFRAME_M15": mt5.TIMEFRAME_M15,
            "TIMEFRAME_M30": mt5.TIMEFRAME_M30,
            "TIMEFRAME_H1": mt5.TIMEFRAME_H1,
            "TIMEFRAME_H4": mt5.TIMEFRAME_H4,
            "TIMEFRAME_D1": mt5.TIMEFRAME_D1,
        }


def create_mt5_client() -> MT5ClientProtocol:
    """Factory for the production MT5 client."""
    return MT5Client()

"""MT5 client protocol for dependency injection and testing."""

from datetime import datetime
from typing import Any, Protocol


class MT5ClientProtocol(Protocol):
    """Protocol implemented by real and mock MT5 clients."""

    def initialize(self, path: str = "") -> bool: ...

    def shutdown(self) -> None: ...

    def last_error(self) -> tuple[int, str]: ...

    def terminal_info(self) -> Any | None: ...

    def account_info(self) -> Any | None: ...

    def login(self, login: int, password: str, server: str) -> bool: ...

    def symbols_get(self) -> list[Any] | None: ...

    def symbol_info(self, symbol: str) -> Any | None: ...

    def symbol_select(self, symbol: str, enable: bool) -> bool: ...

    def symbol_info_tick(self, symbol: str) -> Any | None: ...

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> Any | None: ...

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: datetime,
        date_to: datetime,
    ) -> Any | None: ...

    def get_timeframe_constants(self) -> dict[str, int]: ...

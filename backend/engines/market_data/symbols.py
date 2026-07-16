"""Symbol manager for MT5 instruments."""

import logging
from decimal import Decimal

from backend.engines.market_data.exceptions import SymbolUnavailableError
from backend.engines.market_data.mt5_protocol import MT5ClientProtocol
from backend.engines.market_data.schemas import SymbolMetadata

logger = logging.getLogger(__name__)


class SymbolManager:
    """Load, validate, and expose symbol metadata."""

    def __init__(self, client: MT5ClientProtocol) -> None:
        self._client = client
        self._symbols: dict[str, SymbolMetadata] = {}

    def load_available_symbols(self) -> list[SymbolMetadata]:
        """Load all available symbols from MT5."""
        raw_symbols = self._client.symbols_get()
        if raw_symbols is None:
            code, message = self._client.last_error()
            logger.error(
                "Failed to load symbols",
                extra={"code": "MDE_CONN_FAILED", "mt5_code": code},
            )
            msg = f"Failed to load symbols: {message}"
            raise SymbolUnavailableError(msg, details={"mt5_code": code})

        metadata_list: list[SymbolMetadata] = []
        self._symbols.clear()
        for raw in raw_symbols:
            metadata = self._to_metadata(raw)
            self._symbols[metadata.symbol] = metadata
            metadata_list.append(metadata)

        logger.info("Loaded available symbols", extra={"count": len(metadata_list)})
        return metadata_list

    def validate_symbol(self, symbol: str) -> SymbolMetadata:
        """Validate that a symbol exists and return its metadata."""
        if symbol in self._symbols:
            return self._symbols[symbol]

        info = self._client.symbol_info(symbol)
        if info is None:
            self._client.symbol_select(symbol, True)
            info = self._client.symbol_info(symbol)

        if info is None:
            code, message = self._client.last_error()
            logger.error(
                "Requested symbol invalid",
                extra={"code": "MDE_SYMBOL_UNAVAILABLE", "symbol": symbol},
            )
            raise SymbolUnavailableError(
                f"Symbol '{symbol}' is not available: {message}",
                details={"symbol": symbol, "mt5_code": code},
            )

        metadata = self._to_metadata(info)
        self._symbols[symbol] = metadata
        return metadata

    def get_symbol_metadata(self, symbol: str) -> SymbolMetadata | None:
        return self._symbols.get(symbol)

    def list_symbols(self) -> list[str]:
        return sorted(self._symbols.keys())

    @staticmethod
    def _to_metadata(raw: object) -> SymbolMetadata:
        return SymbolMetadata(
            symbol=str(getattr(raw, "name", "")),
            description=str(getattr(raw, "description", "")),
            digits=int(getattr(raw, "digits", 0)),
            point=Decimal(str(getattr(raw, "point", 0))),
            trade_mode=int(getattr(raw, "trade_mode", 0)),
            visible=bool(getattr(raw, "visible", False)),
            session_deals=int(getattr(raw, "session_deals", 0)),
            session_buy_orders=int(getattr(raw, "session_buy_orders", 0)),
            session_sell_orders=int(getattr(raw, "session_sell_orders", 0)),
        )

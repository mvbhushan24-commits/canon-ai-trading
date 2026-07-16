"""Market Data Engine — orchestrates MT5 connectivity and normalized data delivery."""

import logging

from backend.engines.market_data.broker import BrokerValidator
from backend.engines.market_data.config import MarketDataConfig, load_market_data_config
from backend.engines.market_data.connection import MT5ConnectionManager
from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.exceptions import MarketDataError
from backend.engines.market_data.historical import HistoricalDataLoader
from backend.engines.market_data.live import LiveMarketDataLoader
from backend.engines.market_data.mt5_client import create_mt5_client
from backend.engines.market_data.mt5_protocol import MT5ClientProtocol
from backend.engines.market_data.normalizer import MarketDataNormalizer
from backend.engines.market_data.schemas import (
    EngineConnectionStatus,
    EngineStatus,
    HistoryRequest,
    HistoryResponse,
    NormalizedCandle,
    NormalizedTick,
    SymbolMetadata,
    ValidationResult,
)
from backend.engines.market_data.symbols import SymbolManager
from backend.engines.market_data.validator import DataValidator

logger = logging.getLogger(__name__)


class MarketDataEngine:
    """Production Market Data Engine for XMGlobal via MetaTrader 5."""

    def __init__(
        self,
        config: MarketDataConfig | None = None,
        client: MT5ClientProtocol | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_data_config()
        self._client = client or create_mt5_client()
        self._event_publisher = event_publisher or EventPublisher()
        self._normalizer = MarketDataNormalizer()
        self._validator = DataValidator()

        self._connection = MT5ConnectionManager(
            self._config, self._client, self._event_publisher
        )
        self._broker_validator = BrokerValidator(self._config, self._client)
        self._symbol_manager = SymbolManager(self._client)
        self._historical_loader = HistoricalDataLoader(
            self._config,
            self._client,
            self._normalizer,
            self._validator,
            self._event_publisher,
        )
        self._live_loader = LiveMarketDataLoader(
            self._config,
            self._client,
            self._normalizer,
            self._event_publisher,
        )
        self._started = False
        self._last_error: str | None = None

    @property
    def config(self) -> MarketDataConfig:
        return self._config

    @property
    def event_publisher(self) -> EventPublisher:
        return self._event_publisher

    def start(self) -> None:
        """Connect to MT5, validate broker, and load symbol metadata."""
        logger.info(
            "Starting Market Data Engine",
            extra={"symbol": self._config.symbol, "broker": self._config.broker},
        )
        try:
            self._connection.connect()
            self._broker_validator.validate(self._config.symbol)
            self._symbol_manager.load_available_symbols()
            self._symbol_manager.validate_symbol(self._config.symbol)
            self._started = True
            self._last_error = None
            logger.info("Market Data Engine started")
        except MarketDataError as exc:
            self._last_error = exc.message
            logger.error(
                "Market Data Engine start failed",
                extra={"code": exc.code, "details": exc.details},
            )
            raise

    def stop(self) -> None:
        """Gracefully shutdown the engine and MT5 connection."""
        logger.info("Stopping Market Data Engine")
        self._connection.disconnect()
        self._started = False
        logger.info("Market Data Engine stopped")

    def get_status(self) -> EngineStatus:
        """Return current engine operational status."""
        connection_status = self._connection.get_connection_status()
        if not self._started and connection_status == EngineConnectionStatus.CONNECTED:
            connection_status = EngineConnectionStatus.DISCONNECTED

        latency_ms: int | None = None
        if self._started and self._config.tick_enabled:
            try:
                latency_ms = self._live_loader.estimate_latency_ms(self._config.symbol)
            except MarketDataError:
                latency_ms = None

        if self._last_error and connection_status == EngineConnectionStatus.CONNECTED:
            connection_status = EngineConnectionStatus.DEGRADED

        return EngineStatus(
            status=connection_status,
            last_tick_utc=self._live_loader.last_tick_utc,
            last_error=self._last_error or self._connection.last_error,
            latency_ms=latency_ms,
        )

    def load_historical_candles(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        count: int | None = None,
    ) -> list[NormalizedCandle]:
        """Load historical OHLC candles for a symbol and timeframe."""
        target_symbol = symbol or self._config.symbol
        target_timeframe = timeframe or self._config.timeframes[0]
        self._symbol_manager.validate_symbol(target_symbol)
        return self._historical_loader.load_bars(target_symbol, target_timeframe, count)

    def load_historical_range(self, request: HistoryRequest) -> HistoryResponse:
        """Load on-demand historical candles for a UTC range."""
        self._symbol_manager.validate_symbol(request.symbol)
        return self._historical_loader.load_range(request)

    def get_latest_candle(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> NormalizedCandle:
        """Retrieve the latest (forming) candle."""
        target_symbol = symbol or self._config.symbol
        target_timeframe = timeframe or self._config.timeframes[0]
        self._symbol_manager.validate_symbol(target_symbol)
        return self._live_loader.get_latest_candle(target_symbol, target_timeframe)

    def get_latest_tick(self, symbol: str | None = None) -> NormalizedTick:
        """Retrieve the latest normalized tick."""
        target_symbol = symbol or self._config.symbol
        self._symbol_manager.validate_symbol(target_symbol)
        return self._live_loader.get_latest_tick(target_symbol)

    def validate_candles(self, candles: list[NormalizedCandle]) -> ValidationResult:
        """Validate a list of normalized candles."""
        return self._validator.validate_candles(candles)

    def check_stale_feed(self, symbol: str | None = None) -> None:
        """Raise if the feed exceeds the stale threshold."""
        target_symbol = symbol or self._config.symbol
        self._live_loader.check_stale_feed(target_symbol)

    def get_symbol_metadata(self, symbol: str) -> SymbolMetadata:
        """Return metadata for a validated symbol."""
        return self._symbol_manager.validate_symbol(symbol)

    def list_symbols(self) -> list[str]:
        """Return loaded symbol names."""
        return self._symbol_manager.list_symbols()

    def handle_shutdown_event(self) -> None:
        """Handle system.shutdown.requested event."""
        logger.info("Shutdown event received")
        self.stop()

    def handle_config_updated(self, config: MarketDataConfig) -> None:
        """Handle system.config.updated event by reloading configuration."""
        logger.info("Configuration update received")
        self._config = config

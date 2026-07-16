"""Live market data loader."""

import logging
from datetime import UTC, datetime

from backend.engines.market_data.config import MarketDataConfig
from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.exceptions import StaleFeedError, SymbolUnavailableError
from backend.engines.market_data.mt5_protocol import MT5ClientProtocol
from backend.engines.market_data.normalizer import MarketDataNormalizer
from backend.engines.market_data.schemas import NormalizedCandle, NormalizedTick
from backend.engines.market_data.timeframes import resolve_mt5_timeframe, validate_timeframe

logger = logging.getLogger(__name__)


class LiveMarketDataLoader:
    """Retrieve latest tick and candle data from MT5."""

    def __init__(
        self,
        config: MarketDataConfig,
        client: MT5ClientProtocol,
        normalizer: MarketDataNormalizer,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._normalizer = normalizer
        self._event_publisher = event_publisher
        self._timeframe_constants = client.get_timeframe_constants()
        self._last_tick_utc: datetime | None = None

    @property
    def last_tick_utc(self) -> datetime | None:
        return self._last_tick_utc

    def get_latest_tick(self, symbol: str) -> NormalizedTick:
        """Retrieve and normalize the latest tick for a symbol."""
        if not self._config.tick_enabled:
            raise SymbolUnavailableError(
                "Tick streaming is disabled in configuration",
                details={"symbol": symbol},
            )

        raw_tick = self._client.symbol_info_tick(symbol)
        if raw_tick is None:
            code, message = self._client.last_error()
            raise SymbolUnavailableError(
                f"Tick unavailable for {symbol}: {message}",
                details={"symbol": symbol, "mt5_code": code},
            )

        tick = self._normalizer.normalize_tick(symbol, raw_tick)
        self._last_tick_utc = tick.timestamp_utc

        if self._event_publisher is not None:
            self._event_publisher.publish_tick_received(tick)

        logger.debug(
            "Latest tick retrieved",
            extra={"symbol": symbol, "bid": str(tick.bid), "ask": str(tick.ask)},
        )
        return tick

    def get_latest_candle(self, symbol: str, timeframe: str) -> NormalizedCandle:
        """Retrieve the latest candle (forming or closed) for a symbol/timeframe."""
        normalized_tf = validate_timeframe(timeframe)
        mt5_tf = resolve_mt5_timeframe(normalized_tf, self._timeframe_constants)

        raw_rates = self._client.copy_rates_from_pos(symbol, mt5_tf, 0, 1)
        if raw_rates is None or len(raw_rates) == 0:
            code, message = self._client.last_error()
            raise SymbolUnavailableError(
                f"Latest candle unavailable for {symbol}/{normalized_tf}: {message}",
                details={"symbol": symbol, "timeframe": normalized_tf, "mt5_code": code},
            )

        latest_bar = list(raw_rates)[-1]
        candle = self._normalizer.normalize_candle(
            symbol,
            normalized_tf,
            latest_bar,
            is_closed=False,
        )

        if self._event_publisher is not None:
            if candle.is_closed:
                self._event_publisher.publish_candle_closed(candle)
            else:
                self._event_publisher.publish_candle_updated(candle)

        logger.debug(
            "Latest candle retrieved",
            extra={
                "symbol": symbol,
                "timeframe": normalized_tf,
                "is_closed": candle.is_closed,
                "open_time_utc": candle.open_time_utc.isoformat(),
            },
        )
        return candle

    def check_stale_feed(self, symbol: str) -> None:
        """Raise if the latest tick exceeds the configured stale threshold."""
        tick = self.get_latest_tick(symbol)
        age_seconds = (datetime.now(tz=UTC) - tick.timestamp_utc).total_seconds()
        if age_seconds > self._config.stale_threshold_sec:
            logger.warning(
                "Stale feed detected",
                extra={
                    "code": "MDE_STALE_FEED",
                    "symbol": symbol,
                    "age_seconds": age_seconds,
                    "threshold_sec": self._config.stale_threshold_sec,
                },
            )
            raise StaleFeedError(
                f"Feed stale for {symbol}: last tick {age_seconds:.1f}s ago",
                details={
                    "symbol": symbol,
                    "age_seconds": age_seconds,
                    "threshold_sec": self._config.stale_threshold_sec,
                },
            )

    def estimate_latency_ms(self, symbol: str) -> int:
        tick = self.get_latest_tick(symbol)
        delta = datetime.now(tz=UTC) - tick.timestamp_utc
        return max(int(delta.total_seconds() * 1000), 0)

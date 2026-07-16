"""Historical OHLC data loader."""

import logging

from backend.engines.market_data.config import MarketDataConfig
from backend.engines.market_data.events import EventPublisher
from backend.engines.market_data.exceptions import HistoryLoadError
from backend.engines.market_data.mt5_protocol import MT5ClientProtocol
from backend.engines.market_data.normalizer import MarketDataNormalizer
from backend.engines.market_data.schemas import HistoryRequest, HistoryResponse, NormalizedCandle
from backend.engines.market_data.timeframes import resolve_mt5_timeframe, validate_timeframe
from backend.engines.market_data.validator import DataValidator

logger = logging.getLogger(__name__)


class HistoricalDataLoader:
    """Retrieve historical OHLC candles from MT5."""

    def __init__(
        self,
        config: MarketDataConfig,
        client: MT5ClientProtocol,
        normalizer: MarketDataNormalizer,
        validator: DataValidator,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._normalizer = normalizer
        self._validator = validator
        self._event_publisher = event_publisher
        self._timeframe_constants = client.get_timeframe_constants()

    def load_bars(
        self,
        symbol: str,
        timeframe: str,
        count: int | None = None,
    ) -> list[NormalizedCandle]:
        """Load the most recent historical bars for a symbol/timeframe."""
        normalized_tf = validate_timeframe(timeframe)
        bar_count = count or self._config.history_bars
        mt5_tf = resolve_mt5_timeframe(normalized_tf, self._timeframe_constants)

        logger.info(
            "Loading historical bars",
            extra={"symbol": symbol, "timeframe": normalized_tf, "count": bar_count},
        )

        raw_rates = self._client.copy_rates_from_pos(symbol, mt5_tf, 0, bar_count)
        if raw_rates is None:
            code, message = self._client.last_error()
            logger.error(
                "Historical data load failed",
                extra={"code": "MDE_HISTORY_FAILED", "symbol": symbol, "mt5_code": code},
            )
            raise HistoryLoadError(
                f"Failed to load historical data for {symbol}/{normalized_tf}: {message}",
                details={"symbol": symbol, "timeframe": normalized_tf, "mt5_code": code},
            )

        candles = self._normalizer.normalize_candles(
            symbol,
            normalized_tf,
            list(raw_rates),
            is_closed=True,
        )
        if candles:
            candles[-1] = candles[-1].model_copy(update={"is_closed": False})
        self._emit_validation_results(candles)
        logger.info(
            "Historical bars loaded",
            extra={"symbol": symbol, "timeframe": normalized_tf, "bars": len(candles)},
        )
        return candles

    def load_range(self, request: HistoryRequest) -> HistoryResponse:
        """Load historical candles for an on-demand UTC range."""
        normalized_tf = validate_timeframe(request.timeframe)
        mt5_tf = resolve_mt5_timeframe(normalized_tf, self._timeframe_constants)

        if request.from_utc >= request.to_utc:
            return HistoryResponse(
                request_id=request.request_id,
                symbol=request.symbol,
                timeframe=normalized_tf,
                error="from_utc must be before to_utc",
            )

        logger.info(
            "Loading historical range",
            extra={
                "symbol": request.symbol,
                "timeframe": normalized_tf,
                "from_utc": request.from_utc.isoformat(),
                "to_utc": request.to_utc.isoformat(),
            },
        )

        raw_rates = self._client.copy_rates_range(
            request.symbol,
            mt5_tf,
            request.from_utc,
            request.to_utc,
        )
        if raw_rates is None:
            code, message = self._client.last_error()
            logger.error(
                "Historical range load failed",
                extra={"code": "MDE_HISTORY_FAILED", "mt5_code": code},
            )
            return HistoryResponse(
                request_id=request.request_id,
                symbol=request.symbol,
                timeframe=normalized_tf,
                from_utc=request.from_utc,
                to_utc=request.to_utc,
                error=f"Failed to load history: {message}",
            )

        candles = self._normalizer.normalize_candles(
            request.symbol,
            normalized_tf,
            list(raw_rates),
            is_closed=True,
        )
        self._emit_validation_results(candles)

        response = HistoryResponse(
            request_id=request.request_id,
            symbol=request.symbol,
            timeframe=normalized_tf,
            candles=candles,
            bar_count=len(candles),
            from_utc=request.from_utc,
            to_utc=request.to_utc,
        )

        if self._event_publisher is not None:
            self._event_publisher.publish_history_loaded(
                symbol=request.symbol,
                timeframe=normalized_tf,
                bar_count=len(candles),
                from_utc=request.from_utc,
                to_utc=request.to_utc,
            )

        return response

    def _emit_validation_results(self, candles: list[NormalizedCandle]) -> None:
        result = self._validator.validate_candles(candles)
        if result.gaps and self._event_publisher is not None:
            for gap in result.gaps:
                self._event_publisher.publish_gap_detected(gap)

        if not result.is_valid:
            logger.warning(
                "Historical data validation issues detected",
                extra={
                    "duplicate_count": result.duplicate_count,
                    "invalid_timestamp_count": result.invalid_timestamp_count,
                    "invalid_ohlc_count": result.invalid_ohlc_count,
                    "gap_count": len(result.gaps),
                },
            )

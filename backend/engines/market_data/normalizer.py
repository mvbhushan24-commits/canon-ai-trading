"""Market data normalizer — converts MT5 data to canonical schemas."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_data.schemas import NormalizedCandle, NormalizedTick
from backend.engines.market_data.timeframes import timeframe_duration, validate_timeframe


class MarketDataNormalizer:
    """Normalize MT5 ticks and candles into engine-agnostic structures."""

    SOURCE = "mt5_xmglobal"

    @staticmethod
    def _field(raw: object, name: str, default: object = 0) -> object:
        """Read a field from MT5 objects or numpy structured records."""
        if hasattr(raw, name):
            return getattr(raw, name)
        try:
            return raw[name]  # type: ignore[index]
        except (TypeError, KeyError, IndexError):
            return default

    def normalize_tick(self, symbol: str, raw_tick: object) -> NormalizedTick:
        bid = Decimal(str(self._field(raw_tick, "bid", 0)))
        ask = Decimal(str(self._field(raw_tick, "ask", 0)))
        timestamp = self._to_utc(self._field(raw_tick, "time", 0))
        spread = ask - bid

        return NormalizedTick(
            symbol=symbol,
            bid=bid,
            ask=ask,
            spread=spread,
            timestamp_utc=timestamp,
            source=self.SOURCE,
        )

    def normalize_candle(
        self,
        symbol: str,
        timeframe: str,
        raw_bar: object,
        *,
        is_closed: bool,
    ) -> NormalizedCandle:
        normalized_tf = validate_timeframe(timeframe)
        open_time = self._to_utc(self._field(raw_bar, "time", 0))
        duration = timeframe_duration(normalized_tf)
        close_time = open_time + duration

        return NormalizedCandle(
            symbol=symbol,
            timeframe=normalized_tf,
            open=Decimal(str(self._field(raw_bar, "open", 0))),
            high=Decimal(str(self._field(raw_bar, "high", 0))),
            low=Decimal(str(self._field(raw_bar, "low", 0))),
            close=Decimal(str(self._field(raw_bar, "close", 0))),
            volume=int(
                self._field(raw_bar, "tick_volume", self._field(raw_bar, "real_volume", 0))
            ),
            open_time_utc=open_time,
            close_time_utc=close_time,
            is_closed=is_closed,
        )

    def normalize_candles(
        self,
        symbol: str,
        timeframe: str,
        raw_bars: list[object],
        *,
        is_closed: bool = True,
    ) -> list[NormalizedCandle]:
        return [
            self.normalize_candle(symbol, timeframe, bar, is_closed=is_closed) for bar in raw_bars
        ]

    @staticmethod
    def _to_utc(timestamp: int | float | datetime) -> datetime:
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=UTC)
            return timestamp.astimezone(UTC)
        return datetime.fromtimestamp(int(timestamp), tz=UTC)

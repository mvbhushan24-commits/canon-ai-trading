"""Event publisher for Market Data Engine contract events."""

import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from backend.engines.market_data.schemas import GapInfo, NormalizedCandle, NormalizedTick

EventHandler = Callable[["MarketEvent"], None]

ENGINE_ID = "market_data"


class MarketEvent:
    """Canonical event envelope for market data events."""

    def __init__(
        self,
        event_type: str,
        *,
        symbol: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        timestamp_utc: datetime | None = None,
    ) -> None:
        self.event_id = event_id or str(uuid.uuid4())
        self.timestamp_utc = timestamp_utc or datetime.now(tz=UTC)
        self.symbol = symbol
        self.source_engine = ENGINE_ID
        self.event_type = event_type
        self.payload = payload or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "symbol": self.symbol,
            "source_engine": self.source_engine,
            "event_type": self.event_type,
            "payload": self.payload,
        }


class EventPublisher:
    """In-memory event publisher for market data contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: MarketEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_tick_received(self, tick: NormalizedTick) -> None:
        self.publish(
            MarketEvent(
                "market.tick.received",
                symbol=tick.symbol,
                payload=tick.model_dump(mode="json"),
            )
        )

    def publish_candle_updated(self, candle: NormalizedCandle) -> None:
        self.publish(
            MarketEvent(
                "market.candle.updated",
                symbol=candle.symbol,
                payload=candle.model_dump(mode="json"),
            )
        )

    def publish_candle_closed(self, candle: NormalizedCandle) -> None:
        self.publish(
            MarketEvent(
                "market.candle.closed",
                symbol=candle.symbol,
                payload=candle.model_dump(mode="json"),
            )
        )

    def publish_connection_established(self, *, broker: str, terminal_name: str) -> None:
        self.publish(
            MarketEvent(
                "market.connection.established",
                payload={"broker": broker, "terminal_name": terminal_name},
            )
        )

    def publish_connection_lost(self, *, error: str, timestamp_utc: datetime) -> None:
        self.publish(
            MarketEvent(
                "market.connection.lost",
                payload={"error": error},
                timestamp_utc=timestamp_utc,
            )
        )

    def publish_gap_detected(self, gap: GapInfo) -> None:
        self.publish(
            MarketEvent(
                "market.data.gap_detected",
                symbol=gap.symbol,
                payload=gap.model_dump(mode="json"),
            )
        )

    def publish_history_loaded(
        self,
        *,
        symbol: str,
        timeframe: str,
        bar_count: int,
        from_utc: datetime,
        to_utc: datetime,
    ) -> None:
        self.publish(
            MarketEvent(
                "market.history.loaded",
                symbol=symbol,
                payload={
                    "timeframe": timeframe,
                    "bar_count": bar_count,
                    "from_utc": from_utc.isoformat(),
                    "to_utc": to_utc.isoformat(),
                },
            )
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()

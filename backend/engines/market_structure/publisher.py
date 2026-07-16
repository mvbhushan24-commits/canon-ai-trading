"""Event publisher for Market Structure Engine."""

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime

from backend.engines.market_structure.events import StructureAnalysisEvent
from backend.engines.market_structure.schemas import (
    BOSEvent,
    CHoCHEvent,
    MarketStructure,
    StructureEventKind,
    SwingPoint,
    TrendDirection,
)

EventHandler = Callable[[StructureAnalysisEvent], None]


class StructureEventPublisher:
    """Publish market structure contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: StructureAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_swing_detected(self, swing: SwingPoint, symbol: str, timeframe: str) -> None:
        self.publish(
            StructureAnalysisEvent(
                "SwingDetected",
                symbol=symbol,
                payload={
                    "timeframe": timeframe,
                    "kind": swing.kind.value,
                    "label": swing.label.value,
                    "price": str(swing.price),
                    "bar_index": swing.bar_index,
                },
                timestamp_utc=swing.timestamp_utc,
            )
        )
        self.publish(
            StructureAnalysisEvent(
                "analysis.structure.completed",
                symbol=symbol,
                payload={"event": StructureEventKind.SWING_DETECTED.value},
                timestamp_utc=swing.timestamp_utc,
            )
        )

    def publish_bos_detected(self, bos: BOSEvent, symbol: str) -> None:
        self.publish(
            StructureAnalysisEvent(
                "BOSDetected",
                symbol=symbol,
                payload=bos.model_dump(mode="json"),
                timestamp_utc=bos.timestamp_utc,
            )
        )
        self.publish(
            StructureAnalysisEvent(
                "analysis.structure.bos_detected",
                symbol=symbol,
                payload=bos.model_dump(mode="json"),
                timestamp_utc=bos.timestamp_utc,
            )
        )

    def publish_choch_detected(self, choch: CHoCHEvent, symbol: str) -> None:
        self.publish(
            StructureAnalysisEvent(
                "CHoCHDetected",
                symbol=symbol,
                payload=choch.model_dump(mode="json"),
                timestamp_utc=choch.timestamp_utc,
            )
        )
        self.publish(
            StructureAnalysisEvent(
                "analysis.structure.choch_detected",
                symbol=symbol,
                payload=choch.model_dump(mode="json"),
                timestamp_utc=choch.timestamp_utc,
            )
        )

    def publish_trend_changed(
        self,
        *,
        symbol: str,
        timeframe: str,
        previous: TrendDirection,
        current: TrendDirection,
        timestamp_utc: datetime,
    ) -> None:
        self.publish(
            StructureAnalysisEvent(
                "TrendChanged",
                symbol=symbol,
                payload={
                    "timeframe": timeframe,
                    "previous_trend": previous.value,
                    "current_trend": current.value,
                },
                timestamp_utc=timestamp_utc,
            )
        )
        self.publish(
            StructureAnalysisEvent(
                "analysis.structure.bias_changed",
                symbol=symbol,
                payload={
                    "timeframe": timeframe,
                    "previous_bias": previous.value,
                    "new_bias": current.value,
                },
                timestamp_utc=timestamp_utc,
            )
        )

    def publish_structure_updated(self, structure: MarketStructure) -> None:
        self.publish(
            StructureAnalysisEvent(
                "StructureUpdated",
                symbol=structure.symbol,
                payload=structure.model_dump(mode="json"),
                timestamp_utc=structure.timestamp_utc,
            )
        )
        self.publish(
            StructureAnalysisEvent(
                "analysis.structure.completed",
                symbol=structure.symbol,
                payload=structure.model_dump(mode="json"),
                timestamp_utc=structure.timestamp_utc,
            )
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()

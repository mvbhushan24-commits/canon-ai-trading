"""Event publisher for Market Liquidity Engine."""

from collections import defaultdict
from collections.abc import Callable

from backend.engines.market_liquidity.events import LiquidityAnalysisEvent
from backend.engines.market_liquidity.schemas import (
    LiquidityAnalysis,
    LiquidityGrab,
    LiquidityLevel,
    LiquiditySweep,
    LiquidityZone,
)

EventHandler = Callable[[LiquidityAnalysisEvent], None]


class LiquidityEventPublisher:
    """Publish liquidity contract events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: LiquidityAnalysisEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)

    def publish_liquidity_detected(self, level: LiquidityLevel, symbol: str) -> None:
        self.publish(
            LiquidityAnalysisEvent(
                "LiquidityDetectedEvent",
                symbol=symbol,
                payload=level.model_dump(mode="json"),
                timestamp_utc=level.timestamp_utc,
            )
        )
        self.publish(
            LiquidityAnalysisEvent(
                "analysis.liquidity.pool_identified",
                symbol=symbol,
                payload=level.model_dump(mode="json"),
                timestamp_utc=level.timestamp_utc,
            )
        )

    def publish_sweep(self, sweep: LiquiditySweep, symbol: str) -> None:
        self.publish(
            LiquidityAnalysisEvent(
                "LiquiditySweepEvent",
                symbol=symbol,
                payload=sweep.model_dump(mode="json"),
                timestamp_utc=sweep.timestamp_utc,
            )
        )
        self.publish(
            LiquidityAnalysisEvent(
                "analysis.liquidity.sweep_detected",
                symbol=symbol,
                payload=sweep.model_dump(mode="json"),
                timestamp_utc=sweep.timestamp_utc,
            )
        )

    def publish_grab(self, grab: LiquidityGrab, symbol: str) -> None:
        self.publish(
            LiquidityAnalysisEvent(
                "LiquidityGrabEvent",
                symbol=symbol,
                payload=grab.model_dump(mode="json"),
                timestamp_utc=grab.timestamp_utc,
            )
        )

    def publish_zone(self, zone: LiquidityZone, symbol: str) -> None:
        self.publish(
            LiquidityAnalysisEvent(
                "LiquidityZoneEvent",
                symbol=symbol,
                payload=zone.model_dump(mode="json"),
                timestamp_utc=zone.timestamp_utc,
            )
        )

    def publish_analysis_completed(self, analysis: LiquidityAnalysis) -> None:
        self.publish(
            LiquidityAnalysisEvent(
                "analysis.liquidity.completed",
                symbol=analysis.symbol,
                payload=analysis.model_dump(mode="json"),
                timestamp_utc=analysis.timestamp_utc,
            )
        )

    def clear_handlers(self) -> None:
        self._handlers.clear()

"""Event types for the Market Signal Engine."""

import uuid
from datetime import UTC, datetime
from typing import Any

ENGINE_ID = "market_signal"


class SignalAnalysisEvent:
    """Canonical event envelope for signal lifecycle events."""

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

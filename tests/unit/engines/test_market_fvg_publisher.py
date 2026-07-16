"""Unit tests for fair value gap event publisher."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_fvg.publisher import FairValueGapEventPublisher
from backend.engines.market_fvg.schemas import (
    FairValueGap,
    FairValueGapAnalysis,
    FairValueGapBias,
    FairValueGapDirection,
    FairValueGapQuality,
    FairValueGapState,
    FairValueGapStatus,
    MTFGapAlignment,
)


def _sample_gap() -> FairValueGap:
    return FairValueGap(
        gap_id="fvg-test-1",
        direction=FairValueGapDirection.BULLISH,
        status=FairValueGapStatus.OPEN,
        high=Decimal("2305"),
        low=Decimal("2300"),
        ce_price=Decimal("2302.5"),
        gap_size=Decimal("5"),
        gap_size_pips=Decimal("50"),
        origin_bar_index=10,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        candle_a_index=10,
        candle_b_index=11,
        candle_c_index=12,
        quality=FairValueGapQuality.MEDIUM,
        strength=Decimal("0.6"),
    )


def test_subscribe_and_publish() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("analysis.fvg.detected", lambda event: received.append(event.event_type))

    gap = _sample_gap()
    publisher.publish_gap_detected(gap, "XAUUSD")

    assert "analysis.fvg.detected" in received


def test_wildcard_subscribe() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    gap = _sample_gap()
    publisher.publish_bullish_gap(gap, "XAUUSD")
    publisher.publish_open_gap(gap, "XAUUSD")

    assert "BullishFairValueGapDetected" in received
    assert "OpenFairValueGap" in received


def test_publish_lifecycle_events() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    gap = _sample_gap()
    publisher.publish_partial_fill(gap, "XAUUSD")
    publisher.publish_filled(gap, "XAUUSD")
    publisher.publish_mitigated(gap, "XAUUSD")
    publisher.publish_invalidated(gap, "XAUUSD")
    publisher.publish_expired(gap, "XAUUSD")
    publisher.publish_ce_encroached(gap, "XAUUSD")

    assert "analysis.fvg.partial_fill" in received
    assert "analysis.fvg.filled" in received
    assert "analysis.fvg.mitigated" in received
    assert "analysis.fvg.invalidated" in received
    assert "analysis.fvg.expired" in received
    assert "analysis.fvg.ce_encroached" in received


def test_publish_nested_event() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    parent = _sample_gap()
    child = parent.model_copy(update={"gap_id": "fvg-child", "high": Decimal("2303"), "low": Decimal("2301")})
    publisher.publish_nested(child=child, parent=parent, symbol="XAUUSD", timeframe="H1")

    assert "NestedFairValueGap" in received
    assert "analysis.fvg.nested" in received


def test_publish_mtf_aligned() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    gap = _sample_gap()
    alignment = MTFGapAlignment(
        aligned_timeframes=["H4", "H1"],
        alignment_direction=FairValueGapDirection.BULLISH,
        alignment_score=Decimal("0.8"),
        parent_timeframe="H4",
        parent_gap_id="fvg-parent",
    )
    publisher.publish_mtf_aligned(gap, alignment, "XAUUSD")

    assert "MTFAlignedFairValueGap" in received
    assert "analysis.fvg.mtf_aligned" in received


def test_publish_analysis_completed() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    gap = _sample_gap()
    analysis = FairValueGapAnalysis(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
        fair_value_gaps=[gap],
        open_gaps=[gap],
        bias=FairValueGapBias.NEUTRAL,
        state=FairValueGapState(bar_count=25),
    )
    publisher.publish_analysis_completed(analysis)

    assert "FairValueGapUpdated" in received
    assert "analysis.fvg.completed" in received


def test_publish_error() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_error(
        symbol="XAUUSD",
        code="FVE_VALIDATION_FAILED",
        message="Test error",
        details={"field": "candles"},
        timeframe="H1",
    )

    assert "analysis.fvg.error" in received


def test_gap_payload_shape() -> None:
    payload = FairValueGapEventPublisher._gap_payload(_sample_gap())

    assert payload["gap_id"] == "fvg-test-1"
    assert payload["direction"] == "bullish"
    assert payload["high"] == "2305"
    assert payload["low"] == "2300"
    assert payload["ce_price"] == "2302.5"
    assert payload["quality"] == "medium"


def test_clear_handlers() -> None:
    publisher = FairValueGapEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))
    publisher.clear_handlers()
    publisher.publish_bullish_gap(_sample_gap(), "XAUUSD")

    assert not received

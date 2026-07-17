"""Unit tests for mitigation block event publisher."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_mitigation.publisher import MitigationBlockEventPublisher
from backend.engines.market_mitigation.schemas import (
    MitigationBlock,
    MitigationBlockAnalysis,
    MitigationBlockBias,
    MitigationBlockDirection,
    MitigationBlockQuality,
    MitigationBlockState,
    MitigationBlockStatus,
)


def _sample_block() -> MitigationBlock:
    return MitigationBlock(
        block_id="mb-test-1",
        direction=MitigationBlockDirection.BULLISH,
        status=MitigationBlockStatus.FRESH,
        high=Decimal("2315"),
        low=Decimal("2309"),
        origin_bar_index=14,
        origin_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        displacement_bar_index=15,
        displacement_time_utc=datetime(2026, 1, 1, 1, tzinfo=UTC),
        formation_bar_index=16,
        formation_time_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
        quality=MitigationBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="Awaiting price interaction",
    )


def test_subscribe_and_publish() -> None:
    publisher = MitigationBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("analysis.mitigation.detected", lambda event: received.append(event.event_type))

    publisher.publish_block_detected(_sample_block(), "XAUUSD")

    assert "analysis.mitigation.detected" in received


def test_wildcard_subscribe() -> None:
    publisher = MitigationBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    block = _sample_block()
    publisher.publish_bullish_block(block, "XAUUSD")
    publisher.publish_bearish_block(
        block.model_copy(update={"direction": MitigationBlockDirection.BEARISH}),
        "XAUUSD",
    )

    assert "BullishMitigationBlockDetected" in received
    assert "BearishMitigationBlockDetected" in received


def test_publish_lifecycle_events() -> None:
    publisher = MitigationBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    block = _sample_block().model_copy(
        update={
            "status": MitigationBlockStatus.CONFIRMED,
            "is_confirmed": True,
            "confirmation_bar_index": 20,
            "confirmation_time_utc": datetime(2026, 1, 2, tzinfo=UTC),
            "used_bar_index": 21,
            "invalidation_bar_index": 22,
            "expiration_bar_index": 23,
            "touch_count": 2,
            "mitigation_percent": Decimal("80"),
        },
    )

    publisher.publish_fresh_block(block, "XAUUSD")
    publisher.publish_partial_mitigation(block, "XAUUSD")
    publisher.publish_full_mitigation(block, "XAUUSD")
    publisher.publish_multi_touch(block, "XAUUSD")
    publisher.publish_confirmed(block, "XAUUSD")
    publisher.publish_used(block, "XAUUSD")
    publisher.publish_invalidated(block, "XAUUSD")
    publisher.publish_expired(block, "XAUUSD")

    assert "FreshMitigationBlock" in received
    assert "PartialMitigationBlock" in received
    assert "FullMitigationBlock" in received
    assert "ConfirmedMitigationBlock" in received
    assert "UsedMitigationBlock" in received
    assert "InvalidatedMitigationBlock" in received
    assert "ExpiredMitigationBlock" in received


def test_publish_confluence_events() -> None:
    publisher = MitigationBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    block = _sample_block().model_copy(
        update={
            "liquidity_confluence": True,
            "order_block_confluence": True,
            "fvg_confluence": True,
            "breaker_confluence": True,
            "is_nested": True,
            "parent_zone_id": "ob-1",
            "htf_aligned": True,
            "ltf_nested": True,
            "confluence_ids": ["ob-1"],
        },
    )

    publisher.publish_nested(block, "XAUUSD")
    publisher.publish_internal_scope(block, "XAUUSD")
    publisher.publish_external_scope(block, "XAUUSD")
    publisher.publish_liquidity_confluence(block, "XAUUSD")
    publisher.publish_ob_confluence(block, "XAUUSD")
    publisher.publish_fvg_confluence(block, "XAUUSD")
    publisher.publish_breaker_confluence(block, "XAUUSD")
    publisher.publish_htf_aligned(block, "XAUUSD")
    publisher.publish_ltf_nested(block, "XAUUSD")

    assert "NestedMitigationBlock" in received
    assert "LiquidityConfluenceMitigation" in received
    assert "HTFMitigationAligned" in received


def test_publish_analysis_completed() -> None:
    publisher = MitigationBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    analysis = MitigationBlockAnalysis(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
        mitigation_blocks=[_sample_block()],
        fresh_blocks=[_sample_block()],
        bias=MitigationBlockBias.UNDETERMINED,
        state=MitigationBlockState(bar_count=20),
    )
    publisher.publish_analysis_completed(analysis)

    assert "MitigationBlockUpdated" in received
    assert "analysis.mitigation.completed" in received


def test_publish_error() -> None:
    publisher = MitigationBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_error(
        symbol="XAUUSD",
        code="MMBE_VALIDATION_FAILED",
        message="Validation failed",
        details={"errors": ["bad candle"]},
        timeframe="H1",
    )

    assert "analysis.mitigation.error" in received


def test_block_payload_shape() -> None:
    publisher = MitigationBlockEventPublisher()
    payloads: list[dict] = []
    publisher.subscribe(
        "analysis.mitigation.detected",
        lambda event: payloads.append(event.payload),
    )

    publisher.publish_block_detected(_sample_block(), "XAUUSD")

    assert payloads
    payload = payloads[0]
    assert payload["block_id"] == "mb-test-1"
    assert payload["direction"] == "bullish"
    assert payload["status"] == "fresh"
    assert "high" in payload
    assert "low" in payload
    assert "strength" in payload


def test_clear_handlers() -> None:
    publisher = MitigationBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))
    publisher.clear_handlers()
    publisher.publish_block_detected(_sample_block(), "XAUUSD")

    assert not received

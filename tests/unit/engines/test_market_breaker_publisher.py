"""Unit tests for breaker block event publisher."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_breaker.publisher import BreakerBlockEventPublisher
from backend.engines.market_breaker.schemas import (
    BreakerBlock,
    BreakerBlockAnalysis,
    BreakerBlockBias,
    BreakerBlockDirection,
    BreakerBlockQuality,
    BreakerBlockState,
    BreakerBlockStatus,
    BreakerSourceType,
)


def _sample_breaker() -> BreakerBlock:
    return BreakerBlock(
        breaker_id="brk-test-1",
        direction=BreakerBlockDirection.BEARISH,
        status=BreakerBlockStatus.CANDIDATE,
        high=Decimal("2316"),
        low=Decimal("2308"),
        source_type=BreakerSourceType.ORDER_BLOCK,
        source_id="ob-test",
        source_direction="bullish",
        invalidation_bar_index=17,
        invalidation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        formation_bar_index=18,
        formation_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        quality=BreakerBlockQuality.MEDIUM,
        strength=Decimal("0.6"),
        is_confirmed=False,
        confirmation_reason="Awaiting retest",
        structure_alignment=True,
        liquidity_confluence=False,
        fvg_confluence=False,
    )


def test_subscribe_and_publish() -> None:
    publisher = BreakerBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("analysis.breaker.detected", lambda event: received.append(event.event_type))

    publisher.publish_breaker_detected(_sample_breaker(), "XAUUSD")

    assert "analysis.breaker.detected" in received


def test_wildcard_subscribe() -> None:
    publisher = BreakerBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    breaker = _sample_breaker()
    publisher.publish_bullish_breaker(breaker, "XAUUSD")
    publisher.publish_bearish_breaker(breaker, "XAUUSD")

    assert "BullishBreakerBlockDetected" in received
    assert "BearishBreakerBlockDetected" in received


def test_publish_lifecycle_events() -> None:
    publisher = BreakerBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    breaker = _sample_breaker().model_copy(
        update={
            "status": BreakerBlockStatus.CONFIRMED,
            "is_confirmed": True,
            "confirmation_bar_index": 20,
            "confirmation_time_utc": datetime(2026, 1, 2, tzinfo=UTC),
            "mitigation_bar_index": 21,
            "invalidation_breaker_bar_index": 22,
            "expiration_bar_index": 23,
        },
    )
    publisher.publish_candidate_breaker(breaker, "XAUUSD")
    publisher.publish_confirmed_breaker(breaker, "XAUUSD")
    publisher.publish_mitigated_breaker(breaker, "XAUUSD")
    publisher.publish_invalidated_breaker(breaker, "XAUUSD")
    publisher.publish_expired_breaker(breaker, "XAUUSD")

    assert "analysis.breaker.candidate" in received
    assert "analysis.breaker.confirmed" in received
    assert "analysis.breaker.mitigated" in received
    assert "analysis.breaker.invalidated" in received
    assert "analysis.breaker.expired" in received


def test_publish_confluence_events() -> None:
    publisher = BreakerBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    breaker = _sample_breaker().model_copy(
        update={
            "liquidity_confluence": True,
            "liquidity_confluence_ids": ["liq-1"],
            "fvg_confluence": True,
            "fvg_confluence_ids": ["fvg-1"],
        },
    )
    publisher.publish_liquidity_confluence(breaker, "XAUUSD", timeframe="H1")
    publisher.publish_fvg_confluence(breaker, "XAUUSD", timeframe="H1")

    assert "LiquidityConfluenceBreaker" in received
    assert "analysis.breaker.liquidity_confluence" in received
    assert "FVGConfluenceBreaker" in received
    assert "analysis.breaker.fvg_confluence" in received


def test_publish_analysis_completed() -> None:
    publisher = BreakerBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    breaker = _sample_breaker()
    analysis = BreakerBlockAnalysis(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
        breaker_blocks=[breaker],
        candidate_breakers=[breaker],
        bias=BreakerBlockBias.UNDETERMINED,
        state=BreakerBlockState(bar_count=25),
    )
    publisher.publish_analysis_completed(analysis)

    assert "BreakerBlockUpdated" in received
    assert "analysis.breaker.completed" in received


def test_publish_error() -> None:
    publisher = BreakerBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_error(
        symbol="XAUUSD",
        code="MBE_VALIDATION_FAILED",
        message="Test error",
        details={"field": "candles"},
        timeframe="H1",
    )

    assert "analysis.breaker.error" in received


def test_breaker_payload_shape() -> None:
    payload = BreakerBlockEventPublisher._breaker_payload(_sample_breaker())

    assert payload["breaker_id"] == "brk-test-1"
    assert payload["direction"] == "bearish"
    assert payload["high"] == "2316"
    assert payload["low"] == "2308"
    assert payload["quality"] == "medium"
    assert payload["source_type"] == "order_block"


def test_clear_handlers() -> None:
    publisher = BreakerBlockEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))
    publisher.clear_handlers()
    publisher.publish_bearish_breaker(_sample_breaker(), "XAUUSD")

    assert not received

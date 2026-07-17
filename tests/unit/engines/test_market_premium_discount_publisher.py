"""Unit tests for premium / discount event publisher."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_premium_discount.bullish import BullishPremiumDiscountAnalyzer
from backend.engines.market_premium_discount.lifecycle import LifecycleManager
from backend.engines.market_premium_discount.publisher import PremiumDiscountEventPublisher
from backend.engines.market_premium_discount.schemas import (
    FibDirection,
    FibonacciDealingRange,
    InstitutionalPricingContext,
    MTFPremiumDiscountAlignment,
    PremiumDiscountAnalysis,
    PremiumDiscountBias,
    PremiumDiscountQuality,
    PremiumDiscountZone,
)
from tests.unit.engines.premium_discount_conftest import build_valid_dealing_range, premium_config


def _sample_analysis() -> PremiumDiscountAnalysis:
    dealing_range = build_valid_dealing_range()
    premium, discount, equilibrium = LifecycleManager(premium_config()).build_zones(dealing_range)
    return PremiumDiscountAnalysis(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp_utc=datetime(2026, 1, 2, tzinfo=UTC),
        current_price=Decimal("2340"),
        dealing_range=dealing_range,
        external_range=dealing_range,
        internal_range=dealing_range,
        swing_high=dealing_range.swing_high,
        swing_low=dealing_range.swing_low,
        premium_zone=premium,
        discount_zone=discount,
        equilibrium=equilibrium,
        price_location=PremiumDiscountZone.PREMIUM,
        fibonacci_range=FibonacciDealingRange(
            range_id=dealing_range.range_id,
            direction=FibDirection.BULLISH,
            levels=[],
            ote_low_level=dealing_range.low,
            ote_high_level=dealing_range.low + Decimal("10"),
            equilibrium_level=dealing_range.equilibrium,
        ),
        institutional_context=InstitutionalPricingContext(
            narrative=["Test narrative"],
            current_price_location=PremiumDiscountZone.PREMIUM,
            preferred_buy_territory=PremiumDiscountZone.DISCOUNT,
            preferred_sell_territory=PremiumDiscountZone.PREMIUM,
            active_dealing_range_scope=dealing_range.scope,
            confidence=Decimal("0.7"),
        ),
        bias=PremiumDiscountBias.PREMIUM,
        confidence=Decimal("0.7"),
        quality=PremiumDiscountQuality.HIGH,
        strength=Decimal("0.75"),
    )


def test_subscribe_and_publish_dealing_range() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("analysis.premium_discount.dealing_range_established", lambda event: received.append(event.event_type))

    publisher.publish_dealing_range_established(build_valid_dealing_range(), "XAUUSD")

    assert "analysis.premium_discount.dealing_range_established" in received


def test_wildcard_subscribe() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_premium_entered(Decimal("2340"), "XAUUSD")
    publisher.publish_discount_entered(Decimal("2310"), "XAUUSD")

    assert "PremiumZoneEntered" in received
    assert "DiscountZoneEntered" in received
    assert "analysis.premium_discount.premium_entered" in received


def test_publish_lifecycle_events() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_equilibrium_reached(Decimal("2325"), "XAUUSD")
    publisher.publish_premium_expired(Decimal("2330"), "XAUUSD")
    publisher.publish_discount_expired(Decimal("2310"), "XAUUSD")

    assert "EquilibriumReached" in received
    assert "PremiumExpired" in received
    assert "DiscountExpired" in received


def test_publish_fibonacci_and_ote() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))
    dealing_range = build_valid_dealing_range()
    fibonacci = FibonacciDealingRange(
        range_id=dealing_range.range_id,
        direction=FibDirection.BULLISH,
        levels=[],
        ote_low_level=dealing_range.low,
        ote_high_level=dealing_range.low + Decimal("10"),
        equilibrium_level=dealing_range.equilibrium,
    )
    ote = BullishPremiumDiscountAnalyzer(premium_config()).derive_ote(dealing_range, fibonacci, [])

    publisher.publish_fibonacci_computed(fibonacci, "XAUUSD")
    if ote:
        publisher.publish_ote_derived(ote, "XAUUSD")

    assert "FibonacciRangeComputed" in received
    if ote:
        assert "OTEZoneDerived" in received


def test_publish_mtf_alignment() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))
    alignment = MTFPremiumDiscountAlignment(
        territory=PremiumDiscountZone.DISCOUNT,
        aligned_timeframes=["H1", "H4"],
        alignment_score=Decimal("0.8"),
        ltf_timeframe="H1",
        htf_timeframe="H4",
        range_overlap_percent=Decimal("60"),
        array_overlap_count=2,
    )

    publisher.publish_mtf_discount_aligned(alignment, "XAUUSD")

    assert "MTFDiscountAligned" in received
    assert "analysis.premium_discount.mtf_discount_aligned" in received


def test_publish_analysis_completed_dual_contract() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_analysis_completed(_sample_analysis())

    assert "PremiumDiscountUpdated" in received
    assert "analysis.premium_discount.completed" in received


def test_publish_error_event() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_error(
        symbol="XAUUSD",
        code="PD_VALIDATION_FAILED",
        message="Validation failed",
        timeframe="H1",
    )

    assert "analysis.premium_discount.error" in received


def test_publish_quality_updated() -> None:
    publisher = PremiumDiscountEventPublisher()
    received: list[str] = []
    publisher.subscribe("*", lambda event: received.append(event.event_type))

    publisher.publish_quality_updated(
        symbol="XAUUSD",
        quality="high",
        strength="0.8",
        timestamp=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert "PremiumQualityUpdated" in received

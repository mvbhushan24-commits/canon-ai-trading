"""Unit tests for premium / discount lifecycle management."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

pytest_plugins = ["tests.unit.engines.premium_discount_conftest"]

from backend.engines.market_premium_discount.lifecycle import LifecycleManager
from backend.engines.market_premium_discount.schemas import (
    DealingRangeScope,
    PremiumDiscountEventKind,
    PremiumDiscountZone,
)
from backend.engines.market_structure.schemas import BOSDirection, BOSEvent, CHoCHDirection, CHoCHEvent
from tests.unit.engines.conftest import make_candle
from tests.unit.engines.premium_discount_conftest import (
    build_premium_discount_candles,
    build_premium_discount_structure,
    build_valid_dealing_range,
    premium_config,
)


def test_build_zones_premium_discount_equilibrium() -> None:
    lifecycle = LifecycleManager(premium_config(equilibrium_tolerance_pips=3.0))
    dealing_range = build_valid_dealing_range()

    premium, discount, equilibrium = lifecycle.build_zones(dealing_range)

    assert premium.territory is PremiumDiscountZone.PREMIUM
    assert discount.territory is PremiumDiscountZone.DISCOUNT
    assert equilibrium.price == dealing_range.equilibrium
    assert premium.low == equilibrium.tolerance_high
    assert discount.high == equilibrium.tolerance_low


def test_classify_price_premium() -> None:
    lifecycle = LifecycleManager(premium_config())
    dealing_range = build_valid_dealing_range()

    location = lifecycle.classify_price(dealing_range.high - Decimal("1"), dealing_range)

    assert location is PremiumDiscountZone.PREMIUM


def test_classify_price_discount() -> None:
    lifecycle = LifecycleManager(premium_config())
    dealing_range = build_valid_dealing_range()

    location = lifecycle.classify_price(dealing_range.low + Decimal("1"), dealing_range)

    assert location is PremiumDiscountZone.DISCOUNT


def test_classify_price_equilibrium_band() -> None:
    lifecycle = LifecycleManager(premium_config(equilibrium_tolerance_pips=5.0))
    dealing_range = build_valid_dealing_range()

    location = lifecycle.classify_price(dealing_range.equilibrium, dealing_range)

    assert location is PremiumDiscountZone.EQUILIBRIUM


def test_classify_price_invalid_range_defaults_equilibrium() -> None:
    lifecycle = LifecycleManager(premium_config())
    dealing_range = build_valid_dealing_range().model_copy(update={"is_valid": False})

    location = lifecycle.classify_price(Decimal("2400"), dealing_range)

    assert location is PremiumDiscountZone.EQUILIBRIUM


def test_merge_primary_range_external_mode() -> None:
    lifecycle = LifecycleManager(premium_config(primary_range_mode="external"))
    external = build_valid_dealing_range(scope=DealingRangeScope.EXTERNAL).model_copy(update={"strength": Decimal("0.4")})
    internal = build_valid_dealing_range(
        scope=DealingRangeScope.INTERNAL,
        high=Decimal("2335"),
        low=Decimal("2315"),
    ).model_copy(update={"strength": Decimal("0.9")})

    primary = lifecycle.merge_primary_range(external, internal)

    assert primary.scope is DealingRangeScope.PRIMARY
    assert primary.range_id == external.range_id


def test_merge_primary_range_internal_mode() -> None:
    lifecycle = LifecycleManager(premium_config(primary_range_mode="internal"))
    external = build_valid_dealing_range(scope=DealingRangeScope.EXTERNAL)
    internal = build_valid_dealing_range(scope=DealingRangeScope.INTERNAL, high=Decimal("2335"), low=Decimal("2315"))

    primary = lifecycle.merge_primary_range(external, internal)

    assert primary.range_id == internal.range_id


def test_merge_primary_range_auto_prefers_stronger() -> None:
    lifecycle = LifecycleManager(premium_config(primary_range_mode="auto"))
    external = build_valid_dealing_range(scope=DealingRangeScope.EXTERNAL).model_copy(update={"strength": Decimal("0.3")})
    internal = build_valid_dealing_range(
        scope=DealingRangeScope.INTERNAL,
        high=Decimal("2335"),
        low=Decimal("2315"),
    ).model_copy(update={"strength": Decimal("0.9")})

    primary = lifecycle.merge_primary_range(external, internal)

    assert primary.range_id == internal.range_id


def test_invalidation_on_bos_bearish_break() -> None:
    lifecycle = LifecycleManager(premium_config(invalidate_on_bos=True, max_range_age_bars=500))
    dealing_range = build_valid_dealing_range()
    structure = build_premium_discount_structure().model_copy(
        update={
            "bos_events": [
                BOSEvent(
                    direction=BOSDirection.BEARISH,
                    broken_level=dealing_range.low,
                    break_price=dealing_range.low - Decimal("1"),
                    timestamp_utc=datetime(2026, 1, 2, tzinfo=UTC),
                    bar_index=dealing_range.formation_bar_index + 1,
                    timeframe="H1",
                ),
            ],
        },
    )
    candles = build_premium_discount_candles(30)

    invalidated = lifecycle.apply_invalidation(dealing_range, candles, structure)

    assert invalidated.is_valid is False
    assert "BOS" in invalidated.invalidation_reason


def test_invalidation_on_choch_when_enabled() -> None:
    lifecycle = LifecycleManager(premium_config(invalidate_on_choch=True, max_range_age_bars=500))
    dealing_range = build_valid_dealing_range()
    structure = build_premium_discount_structure().model_copy(
        update={
            "choch_events": [
                CHoCHEvent(
                    direction=CHoCHDirection.BEARISH,
                    broken_level=dealing_range.low,
                    break_price=dealing_range.low - Decimal("1"),
                    timestamp_utc=datetime(2026, 1, 2, tzinfo=UTC),
                    bar_index=dealing_range.formation_bar_index + 1,
                    timeframe="H1",
                ),
            ],
        },
    )
    candles = build_premium_discount_candles(30)
    candles[-1] = make_candle(
        open_time=candles[-1].open_time_utc,
        open_price=dealing_range.low - Decimal("2"),
        high=dealing_range.low - Decimal("1"),
        low=dealing_range.low - Decimal("5"),
        close=dealing_range.low - Decimal("4"),
    )

    invalidated = lifecycle.apply_invalidation(dealing_range, candles, structure)

    assert invalidated.is_valid is False
    assert "CHoCH" in invalidated.invalidation_reason


def test_invalidation_on_max_age() -> None:
    lifecycle = LifecycleManager(premium_config(max_range_age_bars=5))
    dealing_range = build_valid_dealing_range().model_copy(update={"formation_bar_index": 0})
    candles = build_premium_discount_candles(20)

    invalidated = lifecycle.apply_invalidation(dealing_range, candles, None)

    assert invalidated.is_valid is False
    assert "max age" in invalidated.invalidation_reason.lower()


def test_territory_transition_events_premium_entered() -> None:
    lifecycle = LifecycleManager(premium_config())
    dealing_range = build_valid_dealing_range()
    timestamp = datetime(2026, 1, 2, tzinfo=UTC)

    events = lifecycle.detect_territory_events(
        current_price=dealing_range.high - Decimal("1"),
        current_location=PremiumDiscountZone.PREMIUM,
        prior_location=PremiumDiscountZone.DISCOUNT,
        dealing_range=dealing_range,
        timeframe="H1",
        timestamp=timestamp,
    )

    kinds = {event.kind for event in events}
    assert PremiumDiscountEventKind.PREMIUM_ZONE_ENTERED in kinds
    assert PremiumDiscountEventKind.PREMIUM_DETECTED in kinds
    assert PremiumDiscountEventKind.DISCOUNT_EXPIRED in kinds


def test_territory_transition_events_equilibrium() -> None:
    lifecycle = LifecycleManager(premium_config())
    dealing_range = build_valid_dealing_range()
    timestamp = datetime(2026, 1, 2, tzinfo=UTC)

    events = lifecycle.detect_territory_events(
        current_price=dealing_range.equilibrium,
        current_location=PremiumDiscountZone.EQUILIBRIUM,
        prior_location=PremiumDiscountZone.PREMIUM,
        dealing_range=dealing_range,
        timeframe="H1",
        timestamp=timestamp,
    )

    kinds = {event.kind for event in events}
    assert PremiumDiscountEventKind.EQUILIBRIUM_REACHED in kinds
    assert PremiumDiscountEventKind.PREMIUM_EXPIRED in kinds

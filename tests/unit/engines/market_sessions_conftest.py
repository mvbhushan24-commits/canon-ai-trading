"""Shared helpers for market sessions engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.engines.market_liquidity.schemas import LiquiditySide, LiquidityState, LiquidityZone
from backend.engines.market_premium_discount.schemas import PremiumDiscountAnalysis
from backend.engines.market_sessions.config import MarketSessionsConfig
from backend.engines.market_sessions.publisher import MarketSessionsEventPublisher
from backend.engines.market_sessions.schemas import TradingSessionId
from backend.engines.market_structure.schemas import (
    MarketStructure,
    StructureState,
    SwingKind,
    SwingLabel,
    SwingPoint,
    TrendDirection,
)
from tests.unit.engines.conftest import make_candle


def market_sessions_config(**overrides) -> MarketSessionsConfig:
    """Build a test MarketSessionsConfig with sensible defaults."""
    defaults = {
        "enabled": True,
        "timeframes": ["M5", "M15", "H1"],
        "min_candles": 10,
        "lookback": 100,
        "pip_size": 0.1,
        "broker_timezone": "Europe/Nicosia",
        "broker_day_start_hour": 0,
        "weekend_trading_enabled": True,
        "allow_partial_analysis": True,
        "kill_zones_require_active_session": False,
        "session_priority": ["london", "new_york", "tokyo", "sydney"],
        "min_quality_score": 0.4,
        "high_quality_threshold": 0.7,
    }
    defaults.update(overrides)
    return MarketSessionsConfig(**defaults)


def london_open_timestamp() -> datetime:
    """Wednesday 2026-01-14 08:30 UTC — London session + london_open kill zone."""
    return datetime(2026, 1, 14, 8, 30, tzinfo=UTC)


def new_york_session_timestamp() -> datetime:
    """Wednesday 2026-01-14 14:30 UTC — New York session active."""
    return datetime(2026, 1, 14, 14, 30, tzinfo=UTC)


def asian_killzone_timestamp() -> datetime:
    """Wednesday 2026-01-14 01:30 UTC — Asian kill zone window."""
    return datetime(2026, 1, 14, 1, 30, tzinfo=UTC)


def london_close_timestamp() -> datetime:
    """Wednesday 2026-01-14 16:00 UTC — London close kill zone."""
    return datetime(2026, 1, 14, 16, 0, tzinfo=UTC)


def london_ny_overlap_timestamp() -> datetime:
    """Wednesday 2026-01-14 14:00 UTC — London + New York overlap."""
    return datetime(2026, 1, 14, 14, 0, tzinfo=UTC)


def weekend_timestamp() -> datetime:
    """Saturday 2026-01-17 10:00 UTC."""
    return datetime(2026, 1, 17, 10, 0, tzinfo=UTC)


def holiday_timestamp() -> datetime:
    """Wednesday 2026-01-01 10:00 UTC — configured holiday."""
    return datetime(2026, 1, 1, 10, 0, tzinfo=UTC)


def dst_transition_timestamp() -> datetime:
    """Sunday 2026-03-29 00:30 UTC — EU DST spring forward window."""
    return datetime(2026, 3, 29, 0, 30, tzinfo=UTC)


def build_market_sessions_candles(
    count: int = 30,
    *,
    timeframe: str = "M15",
    start: datetime | None = None,
    base_price: Decimal = Decimal("2650"),
) -> list:
    """Build synthetic M15 candles spanning a London session window."""
    session_start = start or datetime(2026, 1, 14, 7, 0, tzinfo=UTC)
    interval = timedelta(minutes=15) if timeframe == "M15" else timedelta(hours=1)
    candles = []
    price = base_price

    for index in range(count):
        drift = Decimal(str((index % 5) - 2))
        open_p = price
        close_p = price + drift
        high_p = max(open_p, close_p) + Decimal("3")
        low_p = min(open_p, close_p) - Decimal("3")
        price = close_p
        open_time = session_start + interval * index
        candles.append(
            make_candle(
                timeframe=timeframe,
                open_time=open_time,
                open_price=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
            )
        )
    return candles


def build_london_or_ib_candles(
    *,
    timeframe: str = "M15",
    session_open: datetime | None = None,
    count: int = 12,
) -> list:
    """Build candles from London session open for OR/IB tests."""
    open_time = session_open or datetime(2026, 1, 14, 8, 0, tzinfo=UTC)
    interval = timedelta(minutes=15) if timeframe == "M15" else timedelta(hours=1)
    candles = []
    price = Decimal("2650")

    for index in range(count):
        open_p = price
        close_p = price + Decimal("2")
        high_p = close_p + Decimal("4")
        low_p = open_p - Decimal("2")
        price = close_p
        candles.append(
            make_candle(
                timeframe=timeframe,
                open_time=open_time + interval * index,
                open_price=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
            )
        )
    return candles


def build_market_sessions_structure() -> MarketStructure:
    """Return structure aligned with session candle tests."""
    start = datetime(2026, 1, 14, 7, 0, tzinfo=UTC)
    swing_high = SwingPoint(
        price=Decimal("2670"),
        timestamp_utc=start + timedelta(hours=2),
        bar_index=8,
        kind=SwingKind.SWING_HIGH,
        label=SwingLabel.HH,
    )
    swing_low = SwingPoint(
        price=Decimal("2640"),
        timestamp_utc=start + timedelta(hours=4),
        bar_index=16,
        kind=SwingKind.SWING_LOW,
        label=SwingLabel.LL,
    )
    state = StructureState(
        trend=TrendDirection.BULLISH,
        last_swing_high=swing_high,
        last_swing_low=swing_low,
        bar_count=30,
    )
    return MarketStructure(
        symbol="XAUUSD",
        timeframe="M15",
        timestamp_utc=start + timedelta(hours=8),
        current_trend=TrendDirection.BULLISH,
        swing_highs=[swing_high],
        swing_lows=[swing_low],
        internal_structure=state,
        external_structure=state,
        current_structure_state=state,
        confidence=Decimal("0.72"),
    )


def sample_liquidity_state() -> LiquidityState:
    """Return liquidity state for session tests."""
    start = datetime(2026, 1, 14, 8, 0, tzinfo=UTC)
    return LiquidityState(
        active_zones=[
            LiquidityZone(
                zone_id="lq-session-1",
                side=LiquiditySide.BUY_SIDE,
                upper_bound=Decimal("2655"),
                lower_bound=Decimal("2645"),
                anchor_price=Decimal("2650"),
                cluster_size=2,
                timestamp_utc=start,
                is_active=True,
            ),
        ],
        recent_sweeps=[],
        bar_count=20,
    )


def sample_premium_discount_analysis() -> PremiumDiscountAnalysis:
    """Return premium/discount analysis for upstream context tests."""
    from backend.engines.market_premium_discount import PremiumDiscountEngine
    from tests.unit.engines.premium_discount_conftest import (
        build_premium_discount_candles,
        premium_config,
    )

    candles = build_premium_discount_candles(30)
    return PremiumDiscountEngine(config=premium_config(timeframes=["H1"])).analyze(
        candles,
        timeframe="H1",
    )


def holiday_config() -> MarketSessionsConfig:
    """Config with a fixed holiday date for calendar tests."""
    config = market_sessions_config()
    return config.model_copy(
        update={
            "calendar": config.calendar.model_copy(
                update={
                    "holidays": config.calendar.holidays.model_copy(
                        update={"enabled": True, "dates": ["2026-01-01"]},
                    ),
                },
            ),
        },
    )


def partial_holiday_config() -> MarketSessionsConfig:
    """Config allowing London-only trading on holidays."""
    config = holiday_config()
    return config.model_copy(
        update={
            "calendar": config.calendar.model_copy(
                update={"partial_holiday_sessions": ["london"]},
            ),
        },
    )


def kill_zone_only_config() -> MarketSessionsConfig:
    """Config with kill-zone-only time filter."""
    config = market_sessions_config()
    return config.model_copy(
        update={
            "time_of_day_filter": config.time_of_day_filter.model_copy(
                update={"mode": "kill_zone_only"},
            ),
        },
    )


@pytest.fixture
def market_sessions_cfg() -> MarketSessionsConfig:
    return market_sessions_config()


@pytest.fixture
def market_sessions_publisher() -> MarketSessionsEventPublisher:
    return MarketSessionsEventPublisher()


@pytest.fixture
def market_sessions_candles() -> list:
    return build_market_sessions_candles(30)


@pytest.fixture
def market_sessions_structure() -> MarketStructure:
    return build_market_sessions_structure()


@pytest.fixture
def london_reference_time() -> datetime:
    return london_open_timestamp()


@pytest.fixture
def session_ids() -> list[TradingSessionId]:
    return list(TradingSessionId)

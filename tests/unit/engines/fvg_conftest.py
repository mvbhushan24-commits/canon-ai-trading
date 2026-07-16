"""Shared helpers for fair value gap engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def build_bullish_fvg_candles(count: int = 25) -> list:
    """Build candles with a clear bullish three-candle FVG formation."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []

    for index in range(12):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2285"),
                high=Decimal("2290"),
                low=Decimal("2280"),
                close=Decimal("2288"),
            )
        )

    origin_index = len(candles)
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index),
            open_price=Decimal("2298"),
            high=Decimal("2300"),
            low=Decimal("2295"),
            close=Decimal("2299"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 1),
            open_price=Decimal("2301"),
            high=Decimal("2312"),
            low=Decimal("2300"),
            close=Decimal("2310"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 2),
            open_price=Decimal("2306"),
            high=Decimal("2318"),
            low=Decimal("2305"),
            close=Decimal("2315"),
        )
    )

    while len(candles) < count:
        index = len(candles)
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2320"),
                high=Decimal("2325"),
                low=Decimal("2318"),
                close=Decimal("2323"),
            )
        )

    return candles


def build_bearish_fvg_candles(count: int = 25) -> list:
    """Build candles with a clear bearish three-candle FVG formation."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []

    for index in range(12):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2360"),
                high=Decimal("2362"),
                low=Decimal("2358"),
                close=Decimal("2359"),
            )
        )

    candles.append(
        make_candle(
            open_time=start + timedelta(hours=12),
            open_price=Decimal("2355"),
            high=Decimal("2357"),
            low=Decimal("2350"),
            close=Decimal("2351"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=13),
            open_price=Decimal("2351"),
            high=Decimal("2352"),
            low=Decimal("2335"),
            close=Decimal("2338"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=14),
            open_price=Decimal("2338"),
            high=Decimal("2345"),
            low=Decimal("2330"),
            close=Decimal("2332"),
        )
    )

    while len(candles) < count:
        index = len(candles)
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2325"),
                high=Decimal("2328"),
                low=Decimal("2320"),
                close=Decimal("2322"),
            )
        )

    return candles


def primary_bullish_formation(candles: list):
    """Return the intentional bullish FVG formation (gap 2300–2305)."""
    from backend.engines.market_fvg.bullish import BullishFVGDetector

    for formation in BullishFVGDetector().find_formations(candles):
        if formation.high == Decimal("2305") and formation.low == Decimal("2300"):
            return formation
    msg = "Primary bullish FVG formation not found"
    raise AssertionError(msg)


def primary_bearish_formation(candles: list):
    """Return the intentional bearish FVG formation (gap 2345–2350)."""
    from backend.engines.market_fvg.bearish import BearishFVGDetector

    for formation in BearishFVGDetector().find_formations(candles):
        if formation.high == Decimal("2350") and formation.low == Decimal("2345"):
            return formation
    msg = "Primary bearish FVG formation not found"
    raise AssertionError(msg)


def primary_bullish_gap(engine, candles: list):
    """Return the intentional bullish gap from engine detection."""
    gaps = engine.detect_bullish_gaps(candles)
    for gap in gaps:
        if gap.high == Decimal("2305") and gap.low == Decimal("2300"):
            return gap
    msg = "Primary bullish FVG gap not found"
    raise AssertionError(msg)


def build_partial_fill_candles() -> list:
    """Build candles where a bullish FVG receives partial fill."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_fvg_candles(15)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2323"),
            high=Decimal("2324"),
            low=Decimal("2303"),
            close=Decimal("2308"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=1),
            open_price=Decimal("2308"),
            high=Decimal("2315"),
            low=Decimal("2306"),
            close=Decimal("2312"),
        )
    )
    return candles


def build_ce_mitigation_candles() -> list:
    """Build candles where price touches CE and mitigates (default ce mode)."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_fvg_candles(15)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2323"),
            high=Decimal("2324"),
            low=Decimal("2301"),
            close=Decimal("2304"),
        )
    )
    return candles


def build_full_fill_candles() -> list:
    """Build candles where a bullish FVG is fully filled via wick."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_fvg_candles(15)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2323"),
            high=Decimal("2324"),
            low=Decimal("2298"),
            close=Decimal("2305"),
        )
    )
    return candles


def build_invalidation_candles() -> list:
    """Build candles where a bullish FVG is invalidated by close below gap low."""
    from tests.unit.engines.conftest import make_candle

    candles = build_bullish_fvg_candles(15)
    start = candles[-1].open_time_utc + timedelta(hours=1)
    candles.append(
        make_candle(
            open_time=start,
            open_price=Decimal("2323"),
            high=Decimal("2324"),
            low=Decimal("2290"),
            close=Decimal("2292"),
        )
    )
    return candles


def build_nested_fvg_candles() -> list:
    """Build candles with two FVG formations where one nests inside another."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []

    for index in range(8):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2280"),
                high=Decimal("2282"),
                low=Decimal("2278"),
                close=Decimal("2281"),
            )
        )

    candles.append(
        make_candle(
            open_time=start + timedelta(hours=8),
            open_price=Decimal("2295"),
            high=Decimal("2298"),
            low=Decimal("2290"),
            close=Decimal("2296"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=9),
            open_price=Decimal("2296"),
            high=Decimal("2320"),
            low=Decimal("2295"),
            close=Decimal("2315"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=10),
            open_price=Decimal("2315"),
            high=Decimal("2330"),
            low=Decimal("2300"),
            close=Decimal("2325"),
        )
    )

    candles.append(
        make_candle(
            open_time=start + timedelta(hours=11),
            open_price=Decimal("2325"),
            high=Decimal("2328"),
            low=Decimal("2320"),
            close=Decimal("2326"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=12),
            open_price=Decimal("2326"),
            high=Decimal("2335"),
            low=Decimal("2325"),
            close=Decimal("2333"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=13),
            open_price=Decimal("2333"),
            high=Decimal("2338"),
            low=Decimal("2327"),
            close=Decimal("2335"),
        )
    )

    for index in range(14, 25):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2340"),
                high=Decimal("2345"),
                low=Decimal("2338"),
                close=Decimal("2342"),
            )
        )

    return candles

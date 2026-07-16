"""Shared helpers for order block engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def build_bullish_order_block_candles(count: int = 25) -> list:
    """Build candles with a clear bullish order block displacement pattern."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    price = Decimal("2300")

    for index in range(min(15, count - 10)):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=price,
                high=price + Decimal("2"),
                low=price - Decimal("2"),
                close=price + Decimal("1"),
            )
        )
        price += Decimal("1")

    origin_index = len(candles)
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index),
            open_price=Decimal("2315"),
            high=Decimal("2316"),
            low=Decimal("2308"),
            close=Decimal("2309"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 1),
            open_price=Decimal("2309"),
            high=Decimal("2320"),
            low=Decimal("2308"),
            close=Decimal("2318"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=origin_index + 2),
            open_price=Decimal("2318"),
            high=Decimal("2330"),
            low=Decimal("2317"),
            close=Decimal("2328"),
        )
    )

    while len(candles) < count:
        index = len(candles)
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2328"),
                high=Decimal("2332"),
                low=Decimal("2326"),
                close=Decimal("2330"),
            )
        )

    return candles


def build_mitigation_candles() -> list:
    """Build candles where a bullish order block is mitigated by retracement."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []

    for index in range(10):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2300"),
                high=Decimal("2302"),
                low=Decimal("2298"),
                close=Decimal("2301"),
            )
        )

    candles.append(
        make_candle(
            open_time=start + timedelta(hours=10),
            open_price=Decimal("2310"),
            high=Decimal("2311"),
            low=Decimal("2303"),
            close=Decimal("2304"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=11),
            open_price=Decimal("2304"),
            high=Decimal("2315"),
            low=Decimal("2303"),
            close=Decimal("2313"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=12),
            open_price=Decimal("2313"),
            high=Decimal("2325"),
            low=Decimal("2312"),
            close=Decimal("2323"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=13),
            open_price=Decimal("2323"),
            high=Decimal("2325"),
            low=Decimal("2320"),
            close=Decimal("2321"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=14),
            open_price=Decimal("2321"),
            high=Decimal("2322"),
            low=Decimal("2305"),
            close=Decimal("2308"),
        )
    )

    return candles


def build_bearish_order_block_candles() -> list:
    """Build candles with a clear bearish order block displacement pattern."""
    from tests.unit.engines.conftest import make_candle

    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []

    for index in range(10):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2350"),
                high=Decimal("2352"),
                low=Decimal("2348"),
                close=Decimal("2349"),
            )
        )

    candles.append(
        make_candle(
            open_time=start + timedelta(hours=10),
            open_price=Decimal("2340"),
            high=Decimal("2347"),
            low=Decimal("2339"),
            close=Decimal("2346"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=11),
            open_price=Decimal("2346"),
            high=Decimal("2347"),
            low=Decimal("2330"),
            close=Decimal("2332"),
        )
    )
    candles.append(
        make_candle(
            open_time=start + timedelta(hours=12),
            open_price=Decimal("2332"),
            high=Decimal("2333"),
            low=Decimal("2315"),
            close=Decimal("2317"),
        )
    )

    for index in range(13, 20):
        candles.append(
            make_candle(
                open_time=start + timedelta(hours=index),
                open_price=Decimal("2317"),
                high=Decimal("2319"),
                low=Decimal("2315"),
                close=Decimal("2316"),
            )
        )

    return candles

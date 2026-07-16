"""Live integration verification for the Market Data Engine pipeline."""

from __future__ import annotations

import sys
import time
import traceback
from datetime import UTC, datetime

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.engines.market_data import MarketDataEngine, load_market_data_config
from backend.engines.market_data.schemas import EngineConnectionStatus


def main() -> int:
    configure_logging(get_settings())
    results: dict[str, bool] = {}
    errors: list[str] = []
    events_received: list[str] = []

    config = load_market_data_config()
    symbol = config.symbol
    engine = MarketDataEngine(config=config)

    def on_event(event: object) -> None:
        events_received.append(getattr(event, "event_type", "unknown"))

    engine.event_publisher.subscribe("*", on_event)

    try:
        engine.start()
        status = engine.get_status()
        results["MT5 Connected"] = status.status == EngineConnectionStatus.CONNECTED
        if not results["MT5 Connected"]:
            errors.append(f"Engine status: {status.status}")

        metadata = engine.get_symbol_metadata(symbol)
        results["Symbol Loaded"] = metadata.symbol == symbol

        candles = engine.load_historical_candles(timeframe="H1", count=10)
        results["Historical Data Received"] = len(candles) > 0

        tick = engine.get_latest_tick()
        results["Live Tick Stream Active"] = tick.symbol == symbol and tick.bid > 0

        results["Normalizer Working"] = (
            tick.source == "mt5_xmglobal"
            and tick.spread == tick.ask - tick.bid
            and candles[0].timeframe == "H1"
            and candles[0].open > 0
        )

        validation = engine.validate_candles(candles)
        results["Validator Working"] = validation.is_valid

        candle = engine.get_latest_candle(timeframe="H1")
        results["Candle Normalization"] = candle.symbol == symbol and candle.timeframe == "H1"

        if "market.tick.received" not in events_received:
            engine.get_latest_tick()
        if "market.candle.updated" not in events_received:
            engine.get_latest_candle(timeframe="H1")

        results["Event Publisher Working"] = (
            "market.connection.established" in events_received
            and "market.tick.received" in events_received
        )

        stable_seconds = 120
        poll_interval = 5
        end_time = time.monotonic() + stable_seconds
        poll_count = 0
        while time.monotonic() < end_time:
            engine.get_latest_tick()
            engine.get_latest_candle(timeframe="M1")
            poll_count += 1
            time.sleep(poll_interval)

        final_status = engine.get_status()
        results["Engine Stable"] = (
            final_status.status == EngineConnectionStatus.CONNECTED
            and poll_count >= stable_seconds // poll_interval
        )

        results["No Exceptions"] = True
    except Exception as exc:
        results["No Exceptions"] = False
        errors.append(f"{type(exc).__name__}: {exc}")
        errors.append(traceback.format_exc())
    finally:
        try:
            engine.stop()
        except Exception as exc:
            results["No Exceptions"] = False
            errors.append(f"Shutdown error: {exc}")

    print("\n=== Market Data Engine Integration Verification ===")
    print(f"Timestamp: {datetime.now(tz=UTC).isoformat()}")
    print(f"Symbol: {symbol}")
    print(f"Events captured: {len(events_received)}")
    print()

    checks = [
        ("MT5 Connected", results.get("MT5 Connected", False)),
        ("Symbol Loaded", results.get("Symbol Loaded", False)),
        ("Historical Data Received", results.get("Historical Data Received", False)),
        ("Live Tick Stream Active", results.get("Live Tick Stream Active", False)),
        ("Normalizer Working", results.get("Normalizer Working", False) and results.get("Candle Normalization", False)),
        ("Validator Working", results.get("Validator Working", False)),
        ("Event Publisher Working", results.get("Event Publisher Working", False)),
        ("Engine Stable", results.get("Engine Stable", False) and results.get("No Exceptions", False)),
    ]
    for label, passed in checks:
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {label}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)

    all_passed = all(passed for _, passed in checks)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

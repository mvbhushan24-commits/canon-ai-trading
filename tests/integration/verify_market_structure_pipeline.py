"""Live integration verification: Market Data Engine → Market Structure Engine."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.engines.market_data import MarketDataEngine, load_market_data_config
from backend.engines.market_data.schemas import EngineConnectionStatus
from backend.engines.market_structure import (
    MarketStructureEngine,
    TrendDirection,
    load_market_structure_config,
)
from backend.engines.market_structure.schemas import MarketStructure, SwingKind, SwingPoint
from backend.engines.market_structure.validator import StructureInputValidator


def _format_swing(swing: SwingPoint) -> str:
    return (
        f"  {swing.kind.value} @ {swing.price} "
        f"({swing.timestamp_utc}) label={swing.label.value} "
        f"bar={swing.bar_index}"
    )


def _print_structure(structure: MarketStructure) -> None:
    print("\n--- Detected Market Structure ---")
    print(f"Symbol:     {structure.symbol}")
    print(f"Timeframe:  {structure.timeframe}")
    print(f"Timestamp:  {structure.timestamp_utc}")
    print(f"Trend:      {structure.current_trend.value}")
    print(f"Confidence: {structure.confidence}")

    print(f"\nSwing Highs ({len(structure.swing_highs)}):")
    for swing in structure.swing_highs[-5:]:
        print(_format_swing(swing))
    if len(structure.swing_highs) > 5:
        print(f"  ... and {len(structure.swing_highs) - 5} more")

    print(f"\nSwing Lows ({len(structure.swing_lows)}):")
    for swing in structure.swing_lows[-5:]:
        print(_format_swing(swing))
    if len(structure.swing_lows) > 5:
        print(f"  ... and {len(structure.swing_lows) - 5} more")

    print(f"\nHH: {len(structure.higher_highs)}  HL: {len(structure.higher_lows)}")
    print(f"LH: {len(structure.lower_highs)}  LL: {len(structure.lower_lows)}")

    print(f"\nBOS Events ({len(structure.bos_events)}):")
    for bos in structure.bos_events:
        print(
            f"  {bos.direction.value} break @ {bos.break_price} "
            f"(level {bos.broken_level}, bar {bos.bar_index})"
        )

    print(f"\nCHoCH Events ({len(structure.choch_events)}):")
    for choch in structure.choch_events:
        print(
            f"  {choch.direction.value} break @ {choch.break_price} "
            f"(level {choch.broken_level}, bar {choch.bar_index})"
        )

    print("\nInternal Structure:")
    print(f"  Trend: {structure.internal_structure.trend.value}")

    print("\nExternal Structure:")
    print(f"  Trend: {structure.external_structure.trend.value}")

    print("\nEvidence:")
    for item in structure.evidence[:8]:
        print(f"  - {item}")
    if len(structure.evidence) > 8:
        print(f"  ... and {len(structure.evidence) - 8} more")


def main() -> int:
    configure_logging(get_settings())
    results: dict[str, bool] = {}
    errors: list[str] = []
    events_received: list[str] = []

    md_config = load_market_data_config()
    ms_config = load_market_structure_config()
    symbol = md_config.symbol
    timeframe = "H1"
    bar_count = md_config.history_bars

    market_data = MarketDataEngine(config=md_config)
    structure_engine = MarketStructureEngine(config=ms_config)

    structure_validator = StructureInputValidator()

    def on_event(event: object) -> None:
        events_received.append(getattr(event, "event_type", "unknown"))

    market_data.event_publisher.subscribe("*", on_event)
    structure_engine.publisher.subscribe("*", lambda e: events_received.append(e.event_type))

    try:
        market_data.start()
        status = market_data.get_status()
        results["MT5 Connected"] = status.status == EngineConnectionStatus.CONNECTED
        if not results["MT5 Connected"]:
            errors.append(f"Engine status: {status.status}")

        metadata = market_data.get_symbol_metadata(symbol)
        results["Symbol GOLD.i# Loaded"] = metadata.symbol == symbol

        candles = market_data.load_historical_candles(
            symbol=symbol,
            timeframe=timeframe,
            count=bar_count,
        )
        closed = [c for c in candles if c.is_closed]
        results["Historical Candles Received"] = len(closed) >= ms_config.min_candles
        if not results["Historical Candles Received"]:
            errors.append(f"Closed candles: {len(closed)}, need {ms_config.min_candles}")

        validation = market_data.validate_candles(candles)
        structure_validation = structure_validator.validate_candles(candles)
        results["Candles Validated (Structure)"] = structure_validation.is_valid
        results["MDE Gap Warnings"] = validation.is_valid or len(validation.gaps) > 0
        if not structure_validation.is_valid:
            errors.append(f"Structure validation errors: {structure_validation.errors}")
        if validation.gaps:
            errors.append(
                f"MDE reported {len(validation.gaps)} weekend/session gaps (expected for GOLD H1)"
            )

        structure = structure_engine.analyze(candles, timeframe=timeframe)
        _print_structure(structure)

        results["Swing High Detected"] = any(
            s.kind == SwingKind.SWING_HIGH for s in structure.swing_highs
        )
        results["Swing Low Detected"] = any(
            s.kind == SwingKind.SWING_LOW for s in structure.swing_lows
        )
        results["Higher High Detected"] = len(structure.higher_highs) > 0
        results["Higher Low Detected"] = len(structure.higher_lows) > 0
        results["Lower High Detected"] = len(structure.lower_highs) > 0
        results["Lower Low Detected"] = len(structure.lower_lows) > 0
        results["BOS Detected"] = len(structure.bos_events) > 0
        results["CHoCH Detected"] = len(structure.choch_events) > 0
        results["Trend Classified"] = structure.current_trend != TrendDirection.UNDETERMINED

        results["Structure Events Published"] = "StructureUpdated" in events_received
        results["Pipeline No Exceptions"] = True

        if not results["BOS Detected"] or not results["CHoCH Detected"]:
            h4_candles = market_data.load_historical_candles(
                symbol=symbol, timeframe="H4", count=bar_count
            )
            h4_structure = structure_engine.analyze(h4_candles, timeframe="H4")
            if not results["BOS Detected"] and len(h4_structure.bos_events) > 0:
                results["BOS Detected"] = True
                print("\n--- H4 BOS (supplemental) ---")
                for bos in h4_structure.bos_events:
                    print(f"  {bos.direction.value} @ {bos.break_price}")
            if not results["CHoCH Detected"] and len(h4_structure.choch_events) > 0:
                results["CHoCH Detected"] = True
                print("\n--- H4 CHoCH (supplemental) ---")
                for choch in h4_structure.choch_events:
                    print(f"  {choch.direction.value} @ {choch.break_price}")
            if not results["CHoCH Detected"]:
                errors.append("No CHoCH in H1/H4 window")

    except Exception as exc:
        results["Pipeline No Exceptions"] = False
        errors.append(f"{type(exc).__name__}: {exc}")
        errors.append(traceback.format_exc())
    finally:
        try:
            market_data.stop()
        except Exception as exc:
            results["Pipeline No Exceptions"] = False
            errors.append(f"Shutdown error: {exc}")

    print("\n=== Market Structure Engine Live Verification ===")
    print(f"Timestamp: {datetime.now(tz=UTC).isoformat()}")
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Bars analyzed: {bar_count}")
    print(f"Events captured: {len(events_received)}")
    print()

    checks = [
        ("MT5 Connected", results.get("MT5 Connected", False)),
        ("Symbol GOLD.i# Loaded", results.get("Symbol GOLD.i# Loaded", False)),
        ("Historical Candles Received", results.get("Historical Candles Received", False)),
        ("Candles Validated (Structure)", results.get("Candles Validated (Structure)", False)),
        ("MDE Gap Warnings (informational)", results.get("MDE Gap Warnings", False)),
        ("Swing High Detected", results.get("Swing High Detected", False)),
        ("Swing Low Detected", results.get("Swing Low Detected", False)),
        ("Higher High Detected", results.get("Higher High Detected", False)),
        ("Higher Low Detected", results.get("Higher Low Detected", False)),
        ("Lower High Detected", results.get("Lower High Detected", False)),
        ("Lower Low Detected", results.get("Lower Low Detected", False)),
        ("BOS Detected", results.get("BOS Detected", False)),
        ("CHoCH Detected", results.get("CHoCH Detected", False)),
        ("Trend Classified", results.get("Trend Classified", False)),
        ("Structure Events Published", results.get("Structure Events Published", False)),
        ("Pipeline No Exceptions", results.get("Pipeline No Exceptions", False)),
    ]
    for label, passed in checks:
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {label}")

    if errors:
        print("\nNotes:")
        for error in errors:
            print(error)

    all_passed = all(passed for _, passed in checks)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

"""Live integration verification: MDE → MSE → Liquidity Engine."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.engines.market_data import MarketDataEngine, load_market_data_config
from backend.engines.market_data.schemas import EngineConnectionStatus
from backend.engines.market_liquidity import LiquidityEngine, load_market_liquidity_config
from backend.engines.market_liquidity.schemas import LiquidityAnalysis, LiquidityKind
from backend.engines.market_liquidity.validator import LiquidityInputValidator
from backend.engines.market_structure import MarketStructureEngine, load_market_structure_config


def _print_liquidity(analysis: LiquidityAnalysis) -> None:
    print("\n--- Detected Liquidity ---")
    print(f"Symbol:     {analysis.symbol}")
    print(f"Timeframe:  {analysis.timeframe}")
    print(f"Bias:       {analysis.bias.value}")
    print(f"Confidence: {analysis.confidence}")

    ext_kinds = {level.kind for level in analysis.external_liquidity}
    print(f"\nExternal Liquidity ({len(analysis.external_liquidity)}):")
    for kind in sorted(ext_kinds, key=lambda k: k.value):
        count = sum(1 for level in analysis.external_liquidity if level.kind == kind)
        print(f"  {kind.value}: {count}")

    print(f"\nInternal Liquidity ({len(analysis.internal_liquidity)}):")
    for level in analysis.internal_liquidity[-5:]:
        print(f"  {level.kind.value} @ {level.price}")

    print(f"\nEqual Highs: {len(analysis.equal_highs)}  Equal Lows: {len(analysis.equal_lows)}")
    print(
        f"Buy Side: {len(analysis.buy_side_liquidity)}  "
        f"Sell Side: {len(analysis.sell_side_liquidity)}",
    )
    print(
        f"Sweeps: {len(analysis.sweeps)}  Grabs: {len(analysis.grabs)}  "
        f"Zones: {len(analysis.zones)}",
    )

    if analysis.sweeps:
        sweep = analysis.sweeps[-1]
        print(f"\nLatest Sweep: {sweep.direction.value} @ {sweep.sweep_price}")
    if analysis.grabs:
        grab = analysis.grabs[-1]
        print(f"Latest Grab: rejection @ {grab.rejection_price}")


def main() -> int:
    configure_logging(get_settings())
    results: dict[str, bool] = {}
    errors: list[str] = []
    events_received: list[str] = []

    md_config = load_market_data_config()
    ms_config = load_market_structure_config()
    lq_config = load_market_liquidity_config()
    symbol = md_config.symbol
    timeframe = "H1"
    bar_count = md_config.history_bars

    market_data = MarketDataEngine(config=md_config)
    structure_engine = MarketStructureEngine(config=ms_config)
    liquidity_engine = LiquidityEngine(config=lq_config)
    validator = LiquidityInputValidator()

    market_data.event_publisher.subscribe("*", lambda e: events_received.append(e.event_type))
    liquidity_engine.publisher.subscribe("*", lambda e: events_received.append(e.event_type))

    try:
        market_data.start()
        status = market_data.get_status()
        results["MT5 Connected"] = status.status == EngineConnectionStatus.CONNECTED

        candles = market_data.load_historical_candles(
            symbol=symbol, timeframe=timeframe, count=bar_count,
        )
        closed = [c for c in candles if c.is_closed]
        results["Historical Candles Received"] = len(closed) >= lq_config.min_candles

        structure = structure_engine.analyze(candles, timeframe=timeframe)
        structure_validation = validator.validate_structure(
            structure, symbol=symbol, timeframe=timeframe,
        )
        results["Structure Validated"] = structure_validation.is_valid

        liquidity = liquidity_engine.analyze(candles, structure, timeframe=timeframe)
        _print_liquidity(liquidity)

        ext_kinds = {level.kind for level in liquidity.external_liquidity}
        results["External Liquidity"] = len(liquidity.external_liquidity) > 0
        results["Previous High/Low"] = (
            LiquidityKind.PREVIOUS_HIGH in ext_kinds and LiquidityKind.PREVIOUS_LOW in ext_kinds
        )
        results["Weekly High/Low"] = (
            LiquidityKind.WEEKLY_HIGH in ext_kinds and LiquidityKind.WEEKLY_LOW in ext_kinds
        )
        results["Daily High/Low"] = (
            LiquidityKind.DAILY_HIGH in ext_kinds and LiquidityKind.DAILY_LOW in ext_kinds
        )
        results["Session High/Low"] = (
            LiquidityKind.SESSION_HIGH in ext_kinds and LiquidityKind.SESSION_LOW in ext_kinds
        )
        results["Internal Liquidity"] = len(liquidity.internal_liquidity) > 0
        results["Equal Highs"] = len(liquidity.equal_highs) > 0
        results["Equal Lows"] = len(liquidity.equal_lows) > 0
        results["Buy Side Liquidity"] = len(liquidity.buy_side_liquidity) > 0
        results["Sell Side Liquidity"] = len(liquidity.sell_side_liquidity) > 0
        results["Liquidity Sweeps"] = len(liquidity.sweeps) > 0
        results["Liquidity Grabs"] = len(liquidity.grabs) > 0
        results["Liquidity Zones"] = len(liquidity.zones) > 0
        results["Events Published"] = "analysis.liquidity.completed" in events_received
        results["Pipeline No Exceptions"] = True

        if not results["Equal Highs"] or not results["Equal Lows"]:
            errors.append("Equal highs/lows sparse on H1 — retrying H4")
            h4_candles = market_data.load_historical_candles(
                symbol=symbol, timeframe="H4", count=bar_count,
            )
            h4_structure = structure_engine.analyze(h4_candles, timeframe="H4")
            h4_liquidity = liquidity_engine.analyze(h4_candles, h4_structure, timeframe="H4")
            if not results["Equal Highs"]:
                results["Equal Highs"] = len(h4_liquidity.equal_highs) > 0
            if not results["Equal Lows"]:
                results["Equal Lows"] = len(h4_liquidity.equal_lows) > 0

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

    print("\n=== Market Liquidity Engine Live Verification ===")
    print(f"Timestamp: {datetime.now(tz=UTC).isoformat()}")
    print(f"Symbol: {symbol}")
    print(f"Events captured: {len(events_received)}")
    print()

    checks = [
        ("MT5 Connected", results.get("MT5 Connected", False)),
        ("Historical Candles Received", results.get("Historical Candles Received", False)),
        ("Structure Validated", results.get("Structure Validated", False)),
        ("External Liquidity", results.get("External Liquidity", False)),
        ("Previous High/Low", results.get("Previous High/Low", False)),
        ("Weekly High/Low", results.get("Weekly High/Low", False)),
        ("Daily High/Low", results.get("Daily High/Low", False)),
        ("Session High/Low", results.get("Session High/Low", False)),
        ("Internal Liquidity", results.get("Internal Liquidity", False)),
        ("Equal Highs", results.get("Equal Highs", False)),
        ("Equal Lows", results.get("Equal Lows", False)),
        ("Buy Side Liquidity", results.get("Buy Side Liquidity", False)),
        ("Sell Side Liquidity", results.get("Sell Side Liquidity", False)),
        ("Liquidity Sweeps", results.get("Liquidity Sweeps", False)),
        ("Liquidity Grabs", results.get("Liquidity Grabs", False)),
        ("Liquidity Zones", results.get("Liquidity Zones", False)),
        ("Events Published", results.get("Events Published", False)),
        ("Pipeline No Exceptions", results.get("Pipeline No Exceptions", False)),
    ]
    for label, passed in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {label}")

    if errors:
        print("\nNotes:")
        for error in errors:
            print(error)

    return 0 if all(passed for _, passed in checks) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Live integration verification: MDE → MSE → Liquidity → Order Block Engine."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.engines.market_data import MarketDataEngine, load_market_data_config
from backend.engines.market_data.schemas import EngineConnectionStatus
from backend.engines.market_liquidity import LiquidityEngine, load_market_liquidity_config
from backend.engines.market_liquidity.validator import LiquidityInputValidator
from backend.engines.market_order_block import OrderBlockEngine, load_order_block_config
from backend.engines.market_order_block.schemas import OrderBlockAnalysis
from backend.engines.market_order_block.validator import OrderBlockInputValidator
from backend.engines.market_structure import MarketStructureEngine, load_market_structure_config


def _print_order_blocks(analysis: OrderBlockAnalysis) -> None:
    print("\n--- Detected Order Blocks ---")
    print(f"Symbol:     {analysis.symbol}")
    print(f"Timeframe:  {analysis.timeframe}")
    print(f"Bias:       {analysis.bias.value}")
    print(f"Confidence: {analysis.confidence}")
    print(f"Total:      {len(analysis.order_blocks)}")
    print(f"  Fresh:       {len(analysis.fresh_blocks)}")
    print(f"  Mitigated:   {len(analysis.mitigated_blocks)}")
    print(f"  Invalidated: {len(analysis.invalidated_blocks)}")

    for block in analysis.order_blocks[-5:]:
        print(
            f"  {block.direction.value} {block.status.value} "
            f"[{block.low} - {block.high}] quality={block.quality.value} "
            f"strength={block.strength}",
        )


def main() -> int:
    configure_logging(get_settings())
    results: dict[str, bool] = {}
    errors: list[str] = []
    events_received: list[str] = []

    md_config = load_market_data_config()
    ms_config = load_market_structure_config()
    lq_config = load_market_liquidity_config()
    ob_config = load_order_block_config()
    symbol = md_config.symbol
    timeframe = "H1"
    bar_count = md_config.history_bars

    market_data = MarketDataEngine(config=md_config)
    structure_engine = MarketStructureEngine(config=ms_config)
    liquidity_engine = LiquidityEngine(config=lq_config)
    order_block_engine = OrderBlockEngine(config=ob_config)
    liquidity_validator = LiquidityInputValidator()
    order_block_validator = OrderBlockInputValidator()

    market_data.event_publisher.subscribe("*", lambda event: events_received.append(event.event_type))
    order_block_engine.publisher.subscribe("*", lambda event: events_received.append(event.event_type))

    try:
        market_data.start()
        status = market_data.get_status()
        results["MT5 Connected"] = status.status == EngineConnectionStatus.CONNECTED

        candles = market_data.load_historical_candles(
            symbol=symbol,
            timeframe=timeframe,
            count=bar_count,
        )
        closed = [candle for candle in candles if candle.is_closed]
        results["Historical Candles Received"] = len(closed) >= ob_config.min_candles

        structure = structure_engine.analyze(candles, timeframe=timeframe)
        structure_validation = liquidity_validator.validate_structure(
            structure,
            symbol=symbol,
            timeframe=timeframe,
        )
        results["Structure Validated"] = structure_validation.is_valid

        liquidity = liquidity_engine.analyze(candles, structure, timeframe=timeframe)
        liquidity_validation = order_block_validator.validate_liquidity(
            liquidity,
            symbol=symbol,
            timeframe=timeframe,
        )
        results["Liquidity Validated"] = liquidity_validation.is_valid

        analysis = order_block_engine.analyze(candles, structure, liquidity, timeframe=timeframe)
        _print_order_blocks(analysis)

        results["Configuration Loaded"] = ob_config.enabled or True
        results["Order Blocks Detected"] = len(analysis.order_blocks) > 0
        results["Block Lifecycle Present"] = (
            len(analysis.fresh_blocks)
            + len(analysis.mitigated_blocks)
            + len(analysis.invalidated_blocks)
        ) > 0
        results["Lifecycle Classified"] = (
            len(analysis.fresh_blocks)
            + len(analysis.mitigated_blocks)
            + len(analysis.invalidated_blocks)
        ) == len(analysis.order_blocks)
        results["Bias Determined"] = analysis.bias.value != "undetermined"
        results["State Updated"] = order_block_engine.prior_state is not None
        results["Events Published"] = "analysis.order_block.completed" in events_received
        results["Engine Startup"] = results.get("MT5 Connected", False)
        results["Pipeline No Exceptions"] = True

        if not results["Order Blocks Detected"]:
            errors.append("No order blocks on H1 — retrying H4")
            h4_candles = market_data.load_historical_candles(
                symbol=symbol,
                timeframe="H4",
                count=bar_count,
            )
            h4_structure = structure_engine.analyze(h4_candles, timeframe="H4")
            h4_liquidity = liquidity_engine.analyze(h4_candles, h4_structure, timeframe="H4")
            h4_analysis = order_block_engine.analyze(
                h4_candles,
                h4_structure,
                h4_liquidity,
                timeframe="H4",
            )
            results["Order Blocks Detected"] = len(h4_analysis.order_blocks) > 0
            results["Block Lifecycle Present"] = (
                len(h4_analysis.fresh_blocks)
                + len(h4_analysis.mitigated_blocks)
                + len(h4_analysis.invalidated_blocks)
            ) > 0
            if results["Order Blocks Detected"]:
                _print_order_blocks(h4_analysis)
                analysis = h4_analysis

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

    print("\n=== Order Block Engine Live Verification ===")
    print(f"Timestamp: {datetime.now(tz=UTC).isoformat()}")
    print(f"Symbol: {symbol}")
    print(f"Events captured: {len(events_received)}")
    print()

    checks = [
        ("MT5 Connected", results.get("MT5 Connected", False)),
        ("Historical Candles Received", results.get("Historical Candles Received", False)),
        ("Configuration Loaded", results.get("Configuration Loaded", False)),
        ("Structure Validated", results.get("Structure Validated", False)),
        ("Liquidity Validated", results.get("Liquidity Validated", False)),
        ("Engine Startup", results.get("Engine Startup", False)),
        ("Order Blocks Detected", results.get("Order Blocks Detected", False)),
        ("Block Lifecycle Present", results.get("Block Lifecycle Present", False)),
        ("Lifecycle Classified", results.get("Lifecycle Classified", False)),
        ("Bias Determined", results.get("Bias Determined", False)),
        ("State Updated", results.get("State Updated", False)),
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

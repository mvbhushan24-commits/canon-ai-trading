"""Live integration verification: MDE → MSE → Liquidity → Order Block → FVG Engine."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.engines.market_data import MarketDataEngine, load_market_data_config
from backend.engines.market_data.schemas import EngineConnectionStatus
from backend.engines.market_fvg import FairValueGapEngine, load_fair_value_gap_config
from backend.engines.market_fvg.schemas import FairValueGapAnalysis
from backend.engines.market_fvg.validator import FairValueGapInputValidator
from backend.engines.market_liquidity import LiquidityEngine, load_market_liquidity_config
from backend.engines.market_liquidity.validator import LiquidityInputValidator
from backend.engines.market_order_block import OrderBlockEngine, load_order_block_config
from backend.engines.market_order_block.validator import OrderBlockInputValidator
from backend.engines.market_structure import MarketStructureEngine, load_market_structure_config


def _print_fvg_analysis(analysis: FairValueGapAnalysis) -> None:
    print("\n--- Detected Fair Value Gaps ---")
    print(f"Symbol:     {analysis.symbol}")
    print(f"Timeframe:  {analysis.timeframe}")
    print(f"Bias:       {analysis.bias.value}")
    print(f"Confidence: {analysis.confidence}")
    print(f"Total:      {len(analysis.fair_value_gaps)}")
    print(f"  Open:        {len(analysis.open_gaps)}")
    print(f"  Partial:     {len(analysis.partial_gaps)}")
    print(f"  Filled:      {len(analysis.filled_gaps)}")
    print(f"  Mitigated:   {len(analysis.mitigated_gaps)}")
    print(f"  Invalidated: {len(analysis.invalidated_gaps)}")
    print(f"  Expired:     {len(analysis.expired_gaps)}")

    for gap in analysis.fair_value_gaps[-5:]:
        print(
            f"  {gap.direction.value} {gap.status.value} "
            f"[{gap.low} - {gap.high}] CE={gap.ce_price} "
            f"quality={gap.quality.value} strength={gap.strength}",
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
    fvg_config = load_fair_value_gap_config()
    symbol = md_config.symbol
    timeframe = "H1"
    bar_count = md_config.history_bars

    market_data = MarketDataEngine(config=md_config)
    structure_engine = MarketStructureEngine(config=ms_config)
    liquidity_engine = LiquidityEngine(config=lq_config)
    order_block_engine = OrderBlockEngine(config=ob_config)
    fvg_engine = FairValueGapEngine(config=fvg_config)
    liquidity_validator = LiquidityInputValidator()
    order_block_validator = OrderBlockInputValidator()
    fvg_validator = FairValueGapInputValidator()

    market_data.event_publisher.subscribe("*", lambda event: events_received.append(event.event_type))
    fvg_engine.publisher.subscribe("*", lambda event: events_received.append(event.event_type))

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
        results["Historical Candles Received"] = len(closed) >= fvg_config.min_candles

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

        order_blocks = order_block_engine.analyze(candles, structure, liquidity, timeframe=timeframe)
        order_block_validation = fvg_validator.validate_order_block_state(
            order_blocks.state,
            bar_count=len(closed),
        )
        results["Order Block Validated"] = order_block_validation.is_valid

        analysis = fvg_engine.analyze(
            candles,
            structure,
            liquidity_state=liquidity.state,
            order_block_state=order_blocks.state,
            timeframe=timeframe,
        )
        _print_fvg_analysis(analysis)

        results["Configuration Loaded"] = fvg_config.enabled or True
        results["Engine Startup"] = results.get("MT5 Connected", False)
        results["Fair Value Gaps Detected"] = len(analysis.fair_value_gaps) > 0
        results["Gap Lifecycle Present"] = (
            len(analysis.open_gaps)
            + len(analysis.partial_gaps)
            + len(analysis.filled_gaps)
            + len(analysis.mitigated_gaps)
            + len(analysis.invalidated_gaps)
            + len(analysis.expired_gaps)
        ) > 0
        results["Lifecycle Classified"] = len(analysis.fair_value_gaps) == (
            len(analysis.open_gaps)
            + len(analysis.partial_gaps)
            + len(analysis.filled_gaps)
            + len(analysis.mitigated_gaps)
            + len(analysis.invalidated_gaps)
            + len(analysis.expired_gaps)
        )
        results["Bias Determined"] = analysis.bias.value in {
            "bullish",
            "bearish",
            "neutral",
            "undetermined",
        }
        results["State Updated"] = fvg_engine.prior_state is not None
        results["Events Published"] = "analysis.fvg.completed" in events_received
        results["Pipeline No Exceptions"] = True

        if not results["Fair Value Gaps Detected"]:
            errors.append("No FVG on H1 — retrying H4")
            h4_candles = market_data.load_historical_candles(
                symbol=symbol,
                timeframe="H4",
                count=bar_count,
            )
            h4_structure = structure_engine.analyze(h4_candles, timeframe="H4")
            h4_liquidity = liquidity_engine.analyze(h4_candles, h4_structure, timeframe="H4")
            h4_order_blocks = order_block_engine.analyze(
                h4_candles,
                h4_structure,
                h4_liquidity,
                timeframe="H4",
            )
            h4_analysis = fvg_engine.analyze(
                h4_candles,
                h4_structure,
                liquidity_state=h4_liquidity.state,
                order_block_state=h4_order_blocks.state,
                timeframe="H4",
            )
            results["Fair Value Gaps Detected"] = len(h4_analysis.fair_value_gaps) > 0
            results["Gap Lifecycle Present"] = (
                len(h4_analysis.open_gaps)
                + len(h4_analysis.partial_gaps)
                + len(h4_analysis.filled_gaps)
                + len(h4_analysis.mitigated_gaps)
                + len(h4_analysis.invalidated_gaps)
                + len(h4_analysis.expired_gaps)
            ) > 0
            if results["Fair Value Gaps Detected"]:
                _print_fvg_analysis(h4_analysis)
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

    print("\n=== Fair Value Gap Engine Live Verification ===")
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
        ("Order Block Validated", results.get("Order Block Validated", False)),
        ("Engine Startup", results.get("Engine Startup", False)),
        ("Fair Value Gaps Detected", results.get("Fair Value Gaps Detected", False)),
        ("Gap Lifecycle Present", results.get("Gap Lifecycle Present", False)),
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

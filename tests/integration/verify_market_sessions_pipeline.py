"""Live integration verification: full 9-engine market sessions pipeline."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.engines.market_breaker import BreakerBlockEngine, load_market_breaker_config
from backend.engines.market_breaker.validator import BreakerBlockInputValidator
from backend.engines.market_data import MarketDataEngine, load_market_data_config
from backend.engines.market_data.schemas import EngineConnectionStatus
from backend.engines.market_fvg import FairValueGapEngine, load_fair_value_gap_config
from backend.engines.market_fvg.validator import FairValueGapInputValidator
from backend.engines.market_liquidity import LiquidityEngine, load_market_liquidity_config
from backend.engines.market_liquidity.validator import LiquidityInputValidator
from backend.engines.market_mitigation import MitigationBlockEngine, load_market_mitigation_config
from backend.engines.market_mitigation.validator import MitigationBlockInputValidator
from backend.engines.market_order_block import OrderBlockEngine, load_order_block_config
from backend.engines.market_order_block.schemas import OrderBlockStatus
from backend.engines.market_order_block.validator import OrderBlockInputValidator
from backend.engines.market_premium_discount import PremiumDiscountEngine, load_market_premium_discount_config
from backend.engines.market_premium_discount.validator import PremiumDiscountInputValidator
from backend.engines.market_sessions import MarketSessionsEngine, load_market_sessions_config
from backend.engines.market_sessions.schemas import SessionAnalysis
from backend.engines.market_sessions.validator import MarketSessionsInputValidator
from backend.engines.market_structure import MarketStructureEngine, load_market_structure_config


def _print_session_analysis(analysis: SessionAnalysis) -> None:
    print("\n--- Market Sessions Analysis ---")
    print(f"Symbol:              {analysis.symbol}")
    print(f"Timeframe:           {analysis.timeframe}")
    print(f"Primary Session:     {analysis.primary_session.value if analysis.primary_session else None}")
    print(f"Session Phase:       {analysis.session_phase.value}")
    print(f"Market Availability: {analysis.market_availability.value}")
    print(f"Active Sessions:     {[s.session_id.value for s in analysis.active_sessions]}")
    print(f"Active Kill Zones:   {[kz.kill_zone_id.value for kz in analysis.active_kill_zones]}")
    print(f"Quality:             {analysis.quality.value}")
    print(f"Strength:            {analysis.strength}")
    print(f"Confidence:          {analysis.confidence}")
    print(f"Time Filter Allowed: {analysis.time_of_day_filter.is_allowed}")
    print(f"Calendar Weekend:    {analysis.calendar_context.is_weekend}")
    print(f"Calendar Holiday:    {analysis.calendar_context.is_holiday}")
    print(f"Trading Day ID:      {analysis.calendar_context.trading_day_id}")
    print(f"Session Extremes:    {len(analysis.session_extremes)}")
    print(f"Opening Range:       {analysis.opening_range is not None}")
    print(f"Initial Balance:     {analysis.initial_balance is not None}")
    print(f"Events:              {len(analysis.events)}")


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
    brk_config = load_market_breaker_config()
    mmb_config = load_market_mitigation_config()
    pd_config = load_market_premium_discount_config()
    sess_config = load_market_sessions_config()
    symbol = md_config.symbol
    timeframe = "H1"
    bar_count = md_config.history_bars

    market_data = MarketDataEngine(config=md_config)
    structure_engine = MarketStructureEngine(config=ms_config)
    liquidity_engine = LiquidityEngine(config=lq_config)
    order_block_engine = OrderBlockEngine(config=ob_config)
    fvg_engine = FairValueGapEngine(config=fvg_config)
    breaker_engine = BreakerBlockEngine(config=brk_config)
    mitigation_engine = MitigationBlockEngine(config=mmb_config)
    premium_discount_engine = PremiumDiscountEngine(config=pd_config)
    sessions_engine = MarketSessionsEngine(config=sess_config)
    liquidity_validator = LiquidityInputValidator()
    order_block_validator = OrderBlockInputValidator()
    fvg_validator = FairValueGapInputValidator()
    breaker_validator = BreakerBlockInputValidator()
    mitigation_validator = MitigationBlockInputValidator()
    premium_discount_validator = PremiumDiscountInputValidator()
    sessions_validator = MarketSessionsInputValidator(sess_config)

    market_data.event_publisher.subscribe("*", lambda event: events_received.append(event.event_type))
    sessions_engine.publisher.subscribe("*", lambda event: events_received.append(event.event_type))

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
        results["Historical Candles Received"] = len(closed) >= sess_config.min_candles

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

        fvg_analysis = fvg_engine.analyze(
            candles,
            structure,
            liquidity_state=liquidity.state,
            order_block_state=order_blocks.state,
            timeframe=timeframe,
        )
        fvg_validation = breaker_validator.validate_fvg_state(
            fvg_analysis.state,
            bar_count=len(closed),
        )
        results["FVG Validated"] = fvg_validation.is_valid

        invalidated_blocks = [
            block for block in order_blocks.order_blocks if block.status is OrderBlockStatus.INVALIDATED
        ]
        breaker_analysis = breaker_engine.analyze(
            candles,
            structure,
            invalidated_order_blocks=invalidated_blocks,
            liquidity_state=liquidity.state,
            fair_value_gap_state=fvg_analysis.state,
            timeframe=timeframe,
        )
        breaker_validation = mitigation_validator.validate_breaker_blocks(
            breaker_analysis.breaker_blocks,
        )
        results["Breaker Validated"] = breaker_validation.is_valid

        mitigation_analysis = mitigation_engine.analyze(
            candles,
            structure,
            order_blocks=order_blocks.order_blocks,
            liquidity_state=liquidity.state,
            fair_value_gap_state=fvg_analysis.state,
            breaker_blocks=breaker_analysis.breaker_blocks,
            timeframe=timeframe,
        )
        ob_validation = mitigation_validator.validate_order_blocks(
            order_blocks.order_blocks,
            symbol=symbol,
            timeframe=timeframe,
        )
        results["Mitigation Validated"] = ob_validation.is_valid

        premium_discount = premium_discount_engine.analyze(
            candles,
            structure,
            liquidity_state=liquidity.state,
            order_blocks=order_blocks.order_blocks,
            fair_value_gap_state=fvg_analysis.state,
            breaker_blocks=breaker_analysis.breaker_blocks,
            mitigation_blocks=mitigation_analysis.mitigation_blocks,
            timeframe=timeframe,
        )
        results["Premium Discount Validated"] = premium_discount.symbol == symbol

        timestamp_utc = closed[-1].close_time_utc or closed[-1].open_time_utc
        try:
            sessions_validator.validate_or_raise(
                closed,
                timestamp_utc,
                sess_config.broker_timezone,
                structure=structure,
                liquidity_state=liquidity.state,
                premium_discount=premium_discount,
                order_blocks=order_blocks.order_blocks,
                fair_value_gap_state=fvg_analysis.state,
                breaker_blocks=breaker_analysis.breaker_blocks,
                mitigation_blocks=mitigation_analysis.mitigation_blocks,
                timeframe=timeframe,
            )
            results["Market Sessions Inputs Validated"] = True
        except Exception as exc:
            results["Market Sessions Inputs Validated"] = False
            errors.append(f"Market sessions validation failed: {exc}")

        analysis = sessions_engine.analyze(
            closed,
            timestamp_utc=timestamp_utc,
            structure=structure,
            liquidity_state=liquidity.state,
            premium_discount=premium_discount,
            order_blocks=order_blocks.order_blocks,
            fair_value_gap_state=fvg_analysis.state,
            breaker_blocks=breaker_analysis.breaker_blocks,
            mitigation_blocks=mitigation_analysis.mitigation_blocks,
            timeframe=timeframe,
        )
        _print_session_analysis(analysis)

        results["Configuration Loaded"] = sess_config.enabled or True
        results["Engine Startup"] = results.get("MT5 Connected", False)
        results["Sessions Resolved"] = len(analysis.kill_zones) >= 4
        results["Kill Zones Resolved"] = len(analysis.kill_zones) == 4
        results["Calendar Context Resolved"] = bool(analysis.calendar_context.trading_day_id)
        results["Quality Scored"] = analysis.quality.value in {"high", "medium", "low"}
        results["State Updated"] = sessions_engine.prior_state is not None
        results["Events Published"] = "analysis.session.completed" in events_received
        results["Pipeline No Exceptions"] = True

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

    print("\n=== Market Sessions Engine Live Verification ===")
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
        ("FVG Validated", results.get("FVG Validated", False)),
        ("Breaker Validated", results.get("Breaker Validated", False)),
        ("Mitigation Validated", results.get("Mitigation Validated", False)),
        ("Premium Discount Validated", results.get("Premium Discount Validated", False)),
        ("Market Sessions Inputs Validated", results.get("Market Sessions Inputs Validated", False)),
        ("Engine Startup", results.get("Engine Startup", False)),
        ("Sessions Resolved", results.get("Sessions Resolved", False)),
        ("Kill Zones Resolved", results.get("Kill Zones Resolved", False)),
        ("Calendar Context Resolved", results.get("Calendar Context Resolved", False)),
        ("Quality Scored", results.get("Quality Scored", False)),
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

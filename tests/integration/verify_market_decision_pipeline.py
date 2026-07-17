"""Live integration verification: full upstream pipeline → Market Decision Engine."""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime

from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.engines.market_breaker import BreakerBlockEngine, load_market_breaker_config
from backend.engines.market_data import MarketDataEngine, load_market_data_config
from backend.engines.market_data.schemas import EngineConnectionStatus
from backend.engines.market_decision import MarketDecisionEngine, load_market_decision_config
from backend.engines.market_decision.schemas import DecisionState
from backend.engines.market_fvg import FairValueGapEngine, load_fair_value_gap_config
from backend.engines.market_liquidity import LiquidityEngine, load_market_liquidity_config
from backend.engines.market_mitigation import MitigationBlockEngine, load_market_mitigation_config
from backend.engines.market_order_block import OrderBlockEngine, load_order_block_config
from backend.engines.market_order_block.schemas import OrderBlockStatus
from backend.engines.market_premium_discount import PremiumDiscountEngine, load_market_premium_discount_config
from backend.engines.market_sessions import MarketSessionsEngine, load_market_sessions_config
from backend.engines.market_structure import MarketStructureEngine, load_market_structure_config


def _print_decision(decision) -> None:
    print("\n--- Trade Decision ---")
    print(f"Symbol:      {decision.symbol}")
    print(f"State:       {decision.state.value}")
    print(f"Direction:   {decision.direction.value}")
    print(f"Confidence:  {decision.confidence}")
    print(f"Quality:     {decision.quality_score} ({decision.quality_tier.value})")
    print(f"Engines:     {decision.metadata.engines_available} available, {decision.metadata.engines_stale} stale")
    if decision.entry.zone_low and decision.entry.zone_high:
        print(f"Entry Zone:  {decision.entry.zone_low} – {decision.entry.zone_high}")
    if decision.stop_loss is not None:
        print(f"Stop Loss:   {decision.stop_loss}")
    if decision.take_profit:
        print(f"Take Profit: {', '.join(str(tp) for tp in decision.take_profit)}")
    if decision.risk_reward_ratio is not None:
        print(f"Risk:Reward: {decision.risk_reward_ratio}")
    if decision.blocking_reasons:
        print(f"Blocking:    {'; '.join(decision.blocking_reasons[:3])}")
    if decision.warnings:
        print(f"Warnings:    {'; '.join(decision.warnings[:3])}")


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
    sessions_config = load_market_sessions_config()
    decision_config = load_market_decision_config()
    decision_config = decision_config.model_copy(update={"enabled": True})

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
    sessions_engine = MarketSessionsEngine(config=sessions_config)
    decision_engine = MarketDecisionEngine(config=decision_config)
    decision_engine.publisher.subscribe("*", lambda event: events_received.append(event.event_type))

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
        results["Historical Candles Received"] = len(closed) >= 10

        structure = structure_engine.analyze(candles, timeframe=timeframe)
        results["Structure Produced"] = structure.symbol == symbol

        liquidity = liquidity_engine.analyze(candles, structure, timeframe=timeframe)
        results["Liquidity Produced"] = liquidity.symbol == symbol

        order_blocks = order_block_engine.analyze(candles, structure, liquidity, timeframe=timeframe)
        results["Order Blocks Produced"] = order_blocks.symbol == symbol

        fvg_analysis = fvg_engine.analyze(
            candles,
            structure,
            liquidity_state=liquidity.state,
            order_block_state=order_blocks.state,
            timeframe=timeframe,
        )
        results["FVG Produced"] = fvg_analysis.symbol == symbol

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
        results["Breaker Produced"] = breaker_analysis.symbol == symbol

        mitigation_analysis = mitigation_engine.analyze(
            candles,
            structure,
            order_blocks=order_blocks.order_blocks,
            liquidity_state=liquidity.state,
            fair_value_gap_state=fvg_analysis.state,
            breaker_blocks=breaker_analysis.breaker_blocks,
            timeframe=timeframe,
        )
        results["Mitigation Produced"] = mitigation_analysis.symbol == symbol

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
        results["Premium Discount Produced"] = premium_discount.symbol == symbol

        latest = closed[-1]
        current_price = (latest.high + latest.low) / 2
        spread = latest.high - latest.low
        sessions = sessions_engine.analyze(
            candles,
            timestamp_utc=latest.open_time_utc,
            structure=structure,
            liquidity_state=liquidity.state,
            premium_discount=premium_discount,
            order_blocks=order_blocks.order_blocks,
            fair_value_gap_state=fvg_analysis.state,
            breaker_blocks=breaker_analysis.breaker_blocks,
            mitigation_blocks=mitigation_analysis.mitigation_blocks,
            timeframe=timeframe,
        )
        results["Sessions Produced"] = sessions.symbol == symbol

        decision = decision_engine.decide(
            symbol,
            latest.open_time_utc,
            current_price,
            spread=spread,
            structure=structure,
            liquidity=liquidity,
            order_blocks=order_blocks,
            fair_value_gaps=fvg_analysis,
            breaker_blocks=breaker_analysis,
            mitigation_blocks=mitigation_analysis,
            premium_discount=premium_discount,
            sessions=sessions,
        )
        _print_decision(decision)

        results["Decision Produced"] = decision.symbol == symbol
        results["Evidence Collected"] = decision.metadata.engines_available >= decision_config.evidence.min_required_engines
        results["Decision State Valid"] = decision.state in DecisionState
        results["Events Published"] = "decision.completed" in events_received
        results["Pipeline No Exceptions"] = True

        if decision.state in {DecisionState.BUY, DecisionState.SELL}:
            results["Signal Published"] = "decision.signal.published" in events_received
            results["Entry Generated"] = decision.entry.zone_low is not None or decision.entry.price is not None
            results["Stop Loss Generated"] = decision.stop_loss is not None
            results["Take Profit Generated"] = len(decision.take_profit) > 0
            results["Risk Reward Validated"] = decision.risk_reward_ratio is not None
        else:
            results["Rejection Published"] = (
                "decision.no_trade.published" in events_received or "decision.error" in events_received
            )

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

    print("\n=== Market Decision Engine Live Verification ===")
    print(f"Timestamp: {datetime.now(tz=UTC).isoformat()}")
    print(f"Symbol: {symbol}")
    print(f"Events captured: {len(events_received)}")
    print()

    checks = list(results.items())
    passed = sum(1 for _, ok in checks if ok)
    failed = len(checks) - passed

    for label, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)

    print(f"\nSummary: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

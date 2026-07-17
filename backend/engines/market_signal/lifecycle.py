"""Signal lifecycle management — operational threshold checks only."""

from datetime import UTC, datetime
from decimal import Decimal

from backend.engines.market_signal.config import MarketSignalConfig
from backend.engines.market_signal.exceptions import SignalNotFoundError
from backend.engines.market_signal.schemas import (
    LifecycleUpdateResult,
    SignalDirection,
    SignalState,
    TERMINAL_SIGNAL_STATES,
    TRADEABLE_SIGNAL_STATES,
    TradingSignal,
)


class SignalLifecycleManager:
    """Track signal states via price-threshold comparison."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def check_entry(
        self,
        signal: TradingSignal,
        current_price: Decimal,
        *,
        timestamp_utc: datetime,
    ) -> tuple[TradingSignal, LifecycleUpdateResult | None]:
        if signal.state is not SignalState.ACTIVE:
            return signal, None
        if not self._config.lifecycle.enabled:
            return signal, None

        tolerance = self._tolerance_pips(self._config.lifecycle.entry_trigger.tolerance_pips)
        if not self._price_reached(signal.direction, current_price, signal.entry_price, tolerance):
            return signal, None

        updated = signal.model_copy(update={"state": SignalState.TRIGGERED})
        result = LifecycleUpdateResult(
            signal_id=signal.signal_id,
            prior_state=SignalState.ACTIVE,
            current_state=SignalState.TRIGGERED,
            transition_reason="Entry price reached",
            current_price=current_price,
            timestamp_utc=timestamp_utc,
        )
        return updated, result

    def check_take_profits(
        self,
        signal: TradingSignal,
        current_price: Decimal,
        *,
        timestamp_utc: datetime,
    ) -> tuple[TradingSignal, LifecycleUpdateResult | None]:
        if signal.state not in {
            SignalState.TRIGGERED,
            SignalState.PARTIALLY_FILLED,
            SignalState.TP1_HIT,
            SignalState.TP2_HIT,
            SignalState.BREAK_EVEN,
            SignalState.TRAILING,
        }:
            return signal, None
        if not self._config.lifecycle.enabled:
            return signal, None

        tolerance = self._tolerance_pips(self._config.lifecycle.tp_trigger.tolerance_pips)
        prior_state = signal.state
        new_state = signal.state

        if signal.state in {
            SignalState.TRIGGERED,
            SignalState.PARTIALLY_FILLED,
            SignalState.BREAK_EVEN,
            SignalState.TRAILING,
        }:
            if self._price_reached(
                signal.direction,
                current_price,
                signal.take_profit_1,
                tolerance,
            ):
                new_state = SignalState.TP1_HIT

        if new_state is SignalState.TP1_HIT and signal.take_profit_2 is not None:
            if self._price_reached(
                signal.direction,
                current_price,
                signal.take_profit_2,
                tolerance,
            ):
                new_state = SignalState.TP2_HIT

        if new_state is SignalState.TP2_HIT and signal.take_profit_3 is not None:
            if self._price_reached(
                signal.direction,
                current_price,
                signal.take_profit_3,
                tolerance,
            ):
                new_state = SignalState.TP3_HIT

        if new_state is prior_state:
            return signal, None

        updated = signal.model_copy(update={"state": new_state})
        result = LifecycleUpdateResult(
            signal_id=signal.signal_id,
            prior_state=prior_state,
            current_state=new_state,
            transition_reason=f"Take profit level reached ({new_state.value})",
            current_price=current_price,
            timestamp_utc=timestamp_utc,
        )
        return updated, result

    def check_stop_loss(
        self,
        signal: TradingSignal,
        current_price: Decimal,
        *,
        timestamp_utc: datetime,
    ) -> tuple[TradingSignal, LifecycleUpdateResult | None]:
        if signal.state in TERMINAL_SIGNAL_STATES:
            return signal, None
        if signal.state not in TRADEABLE_SIGNAL_STATES:
            return signal, None
        if not self._config.lifecycle.enabled:
            return signal, None

        tolerance = self._tolerance_pips(self._config.lifecycle.sl_trigger.tolerance_pips)
        if not self._stop_hit(signal.direction, current_price, signal.stop_loss, tolerance):
            return signal, None

        updated = signal.model_copy(update={"state": SignalState.STOP_LOSS})
        result = LifecycleUpdateResult(
            signal_id=signal.signal_id,
            prior_state=signal.state,
            current_state=SignalState.STOP_LOSS,
            transition_reason=f"Stop loss hit at {signal.stop_loss}",
            current_price=current_price,
            timestamp_utc=timestamp_utc,
        )
        return updated, result

    def apply_break_even(self, signal: TradingSignal) -> TradingSignal:
        if not self._config.lifecycle.break_even.enabled:
            return signal
        trigger = SignalState(self._config.lifecycle.break_even.trigger_after)
        if signal.state is not trigger:
            return signal

        offset = self._tolerance_pips(self._config.lifecycle.break_even.offset_pips)
        if signal.direction is SignalDirection.BUY:
            new_stop = signal.entry_price + offset
        else:
            new_stop = signal.entry_price - offset

        return signal.model_copy(
            update={"state": SignalState.BREAK_EVEN, "stop_loss": new_stop},
        )

    def apply_trailing(
        self,
        signal: TradingSignal,
        current_price: Decimal,
    ) -> TradingSignal:
        trailing = self._config.lifecycle.trailing
        if not trailing.enabled:
            return signal

        trigger = SignalState(trailing.trigger_after)
        if signal.state not in {trigger, SignalState.BREAK_EVEN, SignalState.TRAILING}:
            return signal

        trail_distance = self._tolerance_pips(trailing.trail_distance_pips)
        step = self._tolerance_pips(trailing.step_pips)

        if signal.direction is SignalDirection.BUY:
            candidate = current_price - trail_distance
            if candidate <= signal.stop_loss + step:
                return signal
            new_stop = max(signal.stop_loss, candidate)
        else:
            candidate = current_price + trail_distance
            if candidate >= signal.stop_loss - step:
                return signal
            new_stop = min(signal.stop_loss, candidate)

        return signal.model_copy(
            update={"state": SignalState.TRAILING, "stop_loss": new_stop},
        )

    def expire_signal(
        self,
        signal: TradingSignal,
        *,
        now_utc: datetime,
    ) -> TradingSignal | None:
        if signal.state in TERMINAL_SIGNAL_STATES:
            return None
        if signal.state is not SignalState.ACTIVE:
            return None

        expiry = signal.expiry_time
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        check_now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=UTC)
        if check_now < expiry:
            return None

        return signal.model_copy(update={"state": SignalState.EXPIRED})

    def close_after_stop_loss(self, signal: TradingSignal) -> TradingSignal:
        if signal.state is SignalState.STOP_LOSS:
            return signal.model_copy(update={"state": SignalState.CLOSED})
        return signal

    def cancel_signal(self, signal: TradingSignal, reason: str) -> TradingSignal:
        if signal.state in TERMINAL_SIGNAL_STATES:
            return signal
        return signal.model_copy(update={"state": SignalState.CANCELLED})

    def close_signal(self, signal: TradingSignal, reason: str) -> TradingSignal:
        if signal.state in TERMINAL_SIGNAL_STATES:
            return signal
        return signal.model_copy(update={"state": SignalState.CLOSED})

    def update_lifecycle(
        self,
        signal: TradingSignal,
        current_price: Decimal,
        *,
        timestamp_utc: datetime,
    ) -> tuple[TradingSignal, list[LifecycleUpdateResult]]:
        updates: list[LifecycleUpdateResult] = []
        current = signal

        current, entry_update = self.check_entry(current, current_price, timestamp_utc=timestamp_utc)
        if entry_update:
            updates.append(entry_update)

        current, tp_update = self.check_take_profits(
            current,
            current_price,
            timestamp_utc=timestamp_utc,
        )
        if tp_update:
            updates.append(tp_update)
            if current.state is SignalState.TP1_HIT:
                current = self.apply_break_even(current)
                current = self.apply_trailing(current, current_price)

        current, sl_update = self.check_stop_loss(
            current,
            current_price,
            timestamp_utc=timestamp_utc,
        )
        if sl_update:
            updates.append(sl_update)
            current = self.close_after_stop_loss(current)
            if current.state is SignalState.CLOSED:
                updates.append(
                    LifecycleUpdateResult(
                        signal_id=current.signal_id,
                        prior_state=SignalState.STOP_LOSS,
                        current_state=SignalState.CLOSED,
                        transition_reason="Stop loss terminal close",
                        current_price=current_price,
                        timestamp_utc=timestamp_utc,
                    ),
                )

        if current.state in {SignalState.BREAK_EVEN, SignalState.TRAILING, SignalState.TP1_HIT}:
            current = self.apply_trailing(current, current_price)

        return current, updates

    def require_signal(self, signal: TradingSignal | None, signal_id: str) -> TradingSignal:
        if signal is None:
            raise SignalNotFoundError(
                f"Signal '{signal_id}' not found",
                details={"signal_id": signal_id},
            )
        return signal

    def _tolerance_pips(self, pips: float) -> Decimal:
        return Decimal(str(pips)) * self._config.pip_size_decimal

    def _price_reached(
        self,
        direction: SignalDirection,
        current_price: Decimal,
        target: Decimal,
        tolerance: Decimal,
    ) -> bool:
        if direction is SignalDirection.BUY:
            return current_price >= target - tolerance
        return current_price <= target + tolerance

    def _stop_hit(
        self,
        direction: SignalDirection,
        current_price: Decimal,
        stop_loss: Decimal,
        tolerance: Decimal,
    ) -> bool:
        if direction is SignalDirection.BUY:
            return current_price <= stop_loss + tolerance
        return current_price >= stop_loss - tolerance

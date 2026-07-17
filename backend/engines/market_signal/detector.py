"""Duplicate signal detection."""

from datetime import UTC, datetime, timedelta, timedelta
from decimal import Decimal

from backend.engines.market_decision import DecisionState, TradeDecision
from backend.engines.market_signal.config import MarketSignalConfig
from backend.engines.market_signal.schemas import (
    TERMINAL_SIGNAL_STATES,
    TradingSignal,
    ValidationGateResult,
)


class DuplicateDetector:
    """Detect near-duplicate active signals."""

    def __init__(self, config: MarketSignalConfig) -> None:
        self._config = config

    def detect(
        self,
        decision: TradeDecision,
        *,
        entry_price: Decimal,
        active_signals: dict[str, TradingSignal],
        converted_decision_ids: set[str],
        now_utc: datetime,
    ) -> ValidationGateResult:
        if not self._config.duplicate.enabled:
            return ValidationGateResult(passed=True)

        if decision.state not in {DecisionState.BUY, DecisionState.SELL}:
            return ValidationGateResult(passed=True)

        if (
            self._config.duplicate.reject_same_decision_id
            and decision.decision_id in converted_decision_ids
        ):
            return ValidationGateResult(
                passed=False,
                error_code="DUPLICATE_SIGNAL",
                blocking_reason=(
                    f"Decision '{decision.decision_id}' was already converted to a signal"
                ),
            )

        direction = "BUY" if decision.state is DecisionState.BUY else "SELL"
        window = timedelta(minutes=self._config.duplicate.window_minutes)
        tolerance = Decimal(str(self._config.duplicate.entry_tolerance_pips)) * (
            self._config.pip_size_decimal
        )

        for signal in active_signals.values():
            if signal.state in TERMINAL_SIGNAL_STATES:
                continue
            if signal.symbol != decision.symbol or signal.direction.value != direction:
                continue

            signal_ts = signal.timestamp_utc
            if signal_ts.tzinfo is None:
                signal_ts = signal_ts.replace(tzinfo=UTC)
            if now_utc - signal_ts > window:
                continue

            entry_delta = abs(signal.entry_price - entry_price)
            if entry_delta <= tolerance:
                return ValidationGateResult(
                    passed=False,
                    error_code="DUPLICATE_SIGNAL",
                    blocking_reason=(
                        f"Active {direction} signal exists for {decision.symbol} within "
                        f"{self._config.duplicate.window_minutes}-minute window; "
                        f"entry {entry_price} within "
                        f"{self._config.duplicate.entry_tolerance_pips} pips of "
                        f"active signal {signal.signal_id}"
                    ),
                )

        return ValidationGateResult(passed=True)

    def has_near_duplicate(
        self,
        decision: TradeDecision,
        *,
        entry_price: Decimal,
        active_signals: dict[str, TradingSignal],
        now_utc: datetime,
    ) -> bool:
        """Return True when an active signal is within duplicate proximity."""
        if decision.state not in {DecisionState.BUY, DecisionState.SELL}:
            return False

        direction = "BUY" if decision.state is DecisionState.BUY else "SELL"
        window = timedelta(minutes=self._config.duplicate.window_minutes)
        tolerance = Decimal(str(self._config.duplicate.entry_tolerance_pips)) * (
            self._config.pip_size_decimal
        )

        for signal in active_signals.values():
            if signal.state in TERMINAL_SIGNAL_STATES:
                continue
            if signal.symbol != decision.symbol or signal.direction.value != direction:
                continue

            signal_ts = signal.timestamp_utc
            if signal_ts.tzinfo is None:
                signal_ts = signal_ts.replace(tzinfo=UTC)
            if now_utc - signal_ts > window:
                continue

            if abs(signal.entry_price - entry_price) <= tolerance:
                return True

        return False

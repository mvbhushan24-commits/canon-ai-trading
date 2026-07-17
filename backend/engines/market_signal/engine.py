"""Market Signal Engine orchestrator."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

from backend.engines.market_decision import DecisionState, TradeDecision
from backend.engines.market_signal.config import MarketSignalConfig, load_market_signal_config
from backend.engines.market_signal.detector import DuplicateDetector
from backend.engines.market_signal.exceptions import (
    DuplicateSignalError,
    InvalidDecisionError,
    InvalidRiskError,
    LowConfidenceError,
    SignalEngineError,
    SignalExpiredError,
    SignalValidationError,
)
from backend.engines.market_signal.lifecycle import SignalLifecycleManager
from backend.engines.market_signal.publisher import SignalEventPublisher
from backend.engines.market_signal.quality import SignalQualityScorer
from backend.engines.market_signal.schemas import (
    PIPELINE_VERSION,
    SignalCreationResult,
    SignalDirection,
    SignalMetadata,
    SignalRejection,
    SignalState,
    TERMINAL_SIGNAL_STATES,
    TradingSignal,
    ValidationGateResult,
)
from backend.engines.market_signal.validator import (
    ConfidenceValidator,
    DecisionValidator,
    EntryNormalizer,
    ExpiryValidator,
    RiskValidator,
    SessionValidator,
    SignalInputValidator,
    TakeProfitMapper,
    resolve_expiry_time,
)

logger = logging.getLogger(__name__)


class MarketSignalEngine:
    """Convert validated trade decisions into lifecycle-managed trading signals."""

    def __init__(
        self,
        config: MarketSignalConfig | None = None,
        validator: SignalInputValidator | None = None,
        decision_validator: DecisionValidator | None = None,
        expiry_validator: ExpiryValidator | None = None,
        confidence_validator: ConfidenceValidator | None = None,
        session_validator: SessionValidator | None = None,
        risk_validator: RiskValidator | None = None,
        duplicate_detector: DuplicateDetector | None = None,
        entry_normalizer: EntryNormalizer | None = None,
        take_profit_mapper: TakeProfitMapper | None = None,
        quality_scorer: SignalQualityScorer | None = None,
        lifecycle: SignalLifecycleManager | None = None,
        publisher: SignalEventPublisher | None = None,
    ) -> None:
        self._config = config or load_market_signal_config()
        self._validator = validator or SignalInputValidator()
        self._decision_validator = decision_validator or DecisionValidator(self._config)
        self._expiry_validator = expiry_validator or ExpiryValidator(self._config)
        self._confidence_validator = confidence_validator or ConfidenceValidator(self._config)
        self._session_validator = session_validator or SessionValidator(self._config)
        self._risk_validator = risk_validator or RiskValidator(self._config)
        self._duplicate_detector = duplicate_detector or DuplicateDetector(self._config)
        self._entry_normalizer = entry_normalizer or EntryNormalizer(self._config)
        self._take_profit_mapper = take_profit_mapper or TakeProfitMapper(self._config)
        self._quality_scorer = quality_scorer or SignalQualityScorer(self._config)
        self._lifecycle = lifecycle or SignalLifecycleManager(self._config)
        self._publisher = publisher or SignalEventPublisher()
        self._active_signals: dict[str, TradingSignal] = {}
        self._active_by_symbol: dict[str, list[str]] = {}
        self._converted_decision_ids: set[str] = set()
        self._last_creation_by_symbol: dict[str, datetime] = {}

    @property
    def config(self) -> MarketSignalConfig:
        return self._config

    @property
    def publisher(self) -> SignalEventPublisher:
        return self._publisher

    @property
    def active_signals(self) -> dict[str, TradingSignal]:
        return dict(self._active_signals)

    @property
    def active_by_symbol(self) -> dict[str, list[str]]:
        return {symbol: list(ids) for symbol, ids in self._active_by_symbol.items()}

    def create_signal(
        self,
        decision: TradeDecision,
        *,
        timestamp_utc: datetime | None = None,
    ) -> SignalCreationResult:
        """Run the signal pipeline and return a creation result."""
        started = perf_counter()
        now_utc = timestamp_utc or datetime.now(tz=UTC)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=UTC)

        if not self._config.enabled:
            return SignalCreationResult(
                accepted=False,
                decision_state=decision.state.value,
                duration_ms=int((perf_counter() - started) * 1000),
            )

        try:
            self._validator.validate_or_raise(decision, self._config)
        except SignalValidationError as exc:
            return self._reject(decision, exc, started, now_utc)

        decision_gate = self._decision_validator.validate(decision)
        if not decision_gate.passed:
            if decision_gate.error_code is None:
                logger.info(
                    "No signal for non-tradeable decision",
                    extra={
                        "decision_id": decision.decision_id,
                        "state": decision.state.value,
                    },
                )
                return SignalCreationResult(
                    accepted=False,
                    decision_state=decision.state.value,
                    duration_ms=int((perf_counter() - started) * 1000),
                )
            return self._reject_from_gate(decision, decision_gate, started, now_utc)

        try:
            self._run_validation_pipeline(decision, now_utc=now_utc)
        except SignalEngineError as exc:
            return self._reject(decision, exc, started, now_utc)

        debounce = self._check_debounce(decision.symbol, now_utc)
        if debounce is not None:
            return debounce

        levels = self._take_profit_mapper.map(decision)
        duplicate_gate = self._duplicate_detector.detect(
            decision,
            entry_price=levels.entry_price,
            active_signals=self._active_signals,
            converted_decision_ids=self._converted_decision_ids,
            now_utc=now_utc,
        )
        if not duplicate_gate.passed:
            return self._reject_from_gate(decision, duplicate_gate, started, now_utc)

        near_duplicate = self._duplicate_detector.has_near_duplicate(
            decision,
            entry_price=levels.entry_price,
            active_signals=self._active_signals,
            now_utc=now_utc,
        )

        signal_quality, quality_tier = self._quality_scorer.score(
            decision,
            levels,
            now_utc=now_utc,
            near_duplicate=near_duplicate,
        )
        if not self._quality_scorer.meets_minimum(signal_quality):
            return self._reject_from_gate(
                decision,
                ValidationGateResult(
                    passed=False,
                    error_code="LOW_CONFIDENCE",
                    blocking_reason=(
                        f"Signal quality {signal_quality} below minimum "
                        f"{self._config.quality.min_signal_quality}"
                    ),
                ),
                started,
                now_utc,
            )

        direction = (
            SignalDirection.BUY
            if decision.state is DecisionState.BUY
            else SignalDirection.SELL
        )
        expiry_time = resolve_expiry_time(decision, self._config, now_utc=now_utc)
        duration_ms = int((perf_counter() - started) * 1000)

        metadata = SignalMetadata(
            pipeline_version=PIPELINE_VERSION,
            config_hash=self._config_hash(),
            duration_ms=duration_ms,
            decision_id=decision.decision_id,
            decision_timestamp_utc=decision.timestamp_utc,
            entry_type=levels.entry_type,
            tp_count=levels.tp_count,
            duplicate_check_passed=True,
        )

        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            decision_id=decision.decision_id,
            timestamp_utc=now_utc,
            symbol=decision.symbol,
            timeframe=self._resolve_timeframe(decision),
            direction=direction,
            state=SignalState.CREATED,
            entry_price=levels.entry_price,
            stop_loss=decision.stop_loss,
            take_profit_1=levels.take_profit_1,
            take_profit_2=levels.take_profit_2,
            take_profit_3=levels.take_profit_3,
            risk_reward=decision.risk_reward_ratio,
            confidence=decision.confidence,
            signal_quality=signal_quality,
            quality_tier=quality_tier,
            reasons=list(decision.reasons),
            evidence_summary=list(decision.evidence_summary),
            risk_summary=decision.risk_summary,
            warnings=list(decision.warnings),
            expiry_time=expiry_time,
            metadata=metadata,
        )

        self._publisher.publish_signal_created(signal)

        if self._config.auto_activate:
            signal = self._activate(signal)
        else:
            self._register_signal(signal)

        self._converted_decision_ids.add(decision.decision_id)
        self._last_creation_by_symbol[decision.symbol] = now_utc

        logger.info(
            "Signal created",
            extra={
                "signal_id": signal.signal_id,
                "decision_id": decision.decision_id,
                "symbol": signal.symbol,
                "direction": signal.direction.value,
                "state": signal.state.value,
                "signal_quality": signal.signal_quality,
            },
        )

        return SignalCreationResult(
            accepted=True,
            signal=signal,
            decision_state=decision.state.value,
            duration_ms=duration_ms,
        )

    def activate_signal(self, signal_id: str) -> TradingSignal:
        """Transition a CREATED signal to ACTIVE."""
        signal = self._lifecycle.require_signal(
            self._active_signals.get(signal_id),
            signal_id,
        )
        if signal.state is not SignalState.CREATED:
            return signal
        activated = self._activate(signal)
        return activated

    def get_signal(self, signal_id: str) -> TradingSignal | None:
        return self._active_signals.get(signal_id)

    def get_active_signals(self, symbol: str | None = None) -> list[TradingSignal]:
        if symbol is None:
            return [
                signal
                for signal in self._active_signals.values()
                if signal.state not in TERMINAL_SIGNAL_STATES
            ]
        ids = self._active_by_symbol.get(symbol, [])
        return [
            self._active_signals[sid]
            for sid in ids
            if sid in self._active_signals
            and self._active_signals[sid].state not in TERMINAL_SIGNAL_STATES
        ]

    def update_lifecycle(
        self,
        symbol: str,
        current_price: Decimal,
        timestamp_utc: datetime,
    ) -> list[TradingSignal]:
        """Apply lifecycle threshold checks for active signals on a symbol."""
        if not self._config.lifecycle.enabled:
            return []

        updated_signals: list[TradingSignal] = []
        for signal_id in list(self._active_by_symbol.get(symbol, [])):
            signal = self._active_signals.get(signal_id)
            if signal is None or signal.state in TERMINAL_SIGNAL_STATES:
                continue

            prior_state = signal.state
            updated, transitions = self._lifecycle.update_lifecycle(
                signal,
                current_price,
                timestamp_utc=timestamp_utc,
            )
            self._active_signals[signal_id] = updated
            updated_signals.append(updated)

            if self._config.events.publish_lifecycle_events:
                for transition in transitions:
                    if transition.current_state is SignalState.TRIGGERED:
                        self._publisher.publish_signal_triggered(
                            updated,
                            trigger_price=current_price,
                            timestamp_utc=timestamp_utc,
                        )
                    if transition.current_state is SignalState.CLOSED:
                        self._publisher.publish_signal_closed(
                            updated,
                            reason=transition.transition_reason,
                            exit_price=current_price,
                            closed_at_utc=timestamp_utc,
                            prior_state=prior_state,
                        )

            if updated.state in TERMINAL_SIGNAL_STATES:
                self._unregister_active(signal_id, symbol)

        return updated_signals

    def expire_signals(self, now_utc: datetime) -> list[TradingSignal]:
        """Expire untriggered ACTIVE signals past expiry_time."""
        expired: list[TradingSignal] = []
        check_now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=UTC)

        for signal_id, signal in list(self._active_signals.items()):
            expired_signal = self._lifecycle.expire_signal(signal, now_utc=check_now)
            if expired_signal is None:
                continue

            self._active_signals[signal_id] = expired_signal
            self._unregister_active(signal_id, expired_signal.symbol)
            expired.append(expired_signal)

            if self._config.events.publish_lifecycle_events:
                self._publisher.publish_signal_expired(
                    expired_signal,
                    expired_at_utc=check_now,
                )

        return expired

    def cancel_signal(self, signal_id: str, reason: str) -> TradingSignal:
        signal = self._lifecycle.require_signal(
            self._active_signals.get(signal_id),
            signal_id,
        )
        prior_state = signal.state
        cancelled = self._lifecycle.cancel_signal(signal, reason)
        self._active_signals[signal_id] = cancelled
        self._unregister_active(signal_id, cancelled.symbol)

        if self._config.events.publish_lifecycle_events:
            self._publisher.publish_signal_cancelled(
                cancelled,
                reason=reason,
                prior_state=prior_state,
                cancelled_at_utc=datetime.now(tz=UTC),
            )

        return cancelled

    def close_signal(self, signal_id: str, reason: str) -> TradingSignal:
        signal = self._lifecycle.require_signal(
            self._active_signals.get(signal_id),
            signal_id,
        )
        prior_state = signal.state
        closed = self._lifecycle.close_signal(signal, reason)
        self._active_signals[signal_id] = closed
        self._unregister_active(signal_id, closed.symbol)

        if self._config.events.publish_lifecycle_events:
            self._publisher.publish_signal_closed(
                closed,
                reason=reason,
                exit_price=None,
                closed_at_utc=datetime.now(tz=UTC),
                prior_state=prior_state,
            )

        return closed

    def handle_decision_published(self, event: dict[str, Any] | Any) -> SignalCreationResult:
        """Handle decision.signal.published event payload."""
        payload = event.payload if hasattr(event, "payload") else event
        if not isinstance(payload, dict):
            msg = "Decision event payload must be a mapping"
            raise InvalidDecisionError(msg)

        decision = TradeDecision.model_validate(payload)
        return self.create_signal(decision)

    def handle_tick_received(self, event: dict[str, Any] | Any) -> list[TradingSignal]:
        """Handle market.tick.received for lifecycle updates only."""
        payload = event.payload if hasattr(event, "payload") else event
        if not isinstance(payload, dict):
            return []

        symbol = str(payload.get("symbol", ""))
        price_raw = payload.get("mid") or payload.get("price") or payload.get("current_price")
        timestamp_raw = payload.get("timestamp_utc")
        if not symbol or price_raw is None or timestamp_raw is None:
            return []

        current_price = Decimal(str(price_raw))
        timestamp_utc = datetime.fromisoformat(str(timestamp_raw))
        if timestamp_utc.tzinfo is None:
            timestamp_utc = timestamp_utc.replace(tzinfo=UTC)

        return self.update_lifecycle(symbol, current_price, timestamp_utc)

    def handle_config_updated(
        self,
        settings: dict[str, Any] | None = None,
    ) -> None:
        """Reload configuration from updated settings."""
        self._config = load_market_signal_config(settings=settings)

    def reset_registry(self) -> None:
        """Clear active signal registry (testing)."""
        self._active_signals.clear()
        self._active_by_symbol.clear()
        self._converted_decision_ids.clear()
        self._last_creation_by_symbol.clear()

    def _run_validation_pipeline(
        self,
        decision: TradeDecision,
        *,
        now_utc: datetime,
    ) -> None:
        self._expiry_validator.validate_or_raise(decision, now_utc=now_utc)
        self._confidence_validator.validate_or_raise(decision)
        self._session_validator.validate_or_raise(decision)
        self._risk_validator.validate_or_raise(decision)

    def _activate(self, signal: TradingSignal) -> TradingSignal:
        activated = signal.model_copy(update={"state": SignalState.ACTIVE})
        self._register_signal(activated)
        if self._config.events.publish_lifecycle_events:
            self._publisher.publish_signal_activated(activated)
        return activated

    def _register_signal(self, signal: TradingSignal) -> None:
        self._active_signals[signal.signal_id] = signal
        symbol_ids = self._active_by_symbol.setdefault(signal.symbol, [])
        if signal.signal_id not in symbol_ids:
            symbol_ids.append(signal.signal_id)

    def _unregister_active(self, signal_id: str, symbol: str) -> None:
        symbol_ids = self._active_by_symbol.get(symbol, [])
        if signal_id in symbol_ids:
            symbol_ids.remove(signal_id)

    def _resolve_timeframe(self, decision: TradeDecision) -> str:
        return self._config.timeframe

    def _config_hash(self) -> str:
        payload = self._config.model_dump_json()
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def _check_debounce(
        self,
        symbol: str,
        now_utc: datetime,
    ) -> SignalCreationResult | None:
        last = self._last_creation_by_symbol.get(symbol)
        if last is None:
            return None
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        elapsed = (now_utc - last).total_seconds()
        if elapsed < self._config.debounce_seconds:
            return SignalCreationResult(
                accepted=False,
                decision_state="",
                duration_ms=0,
            )
        return None

    def _reject(
        self,
        decision: TradeDecision,
        exc: SignalEngineError,
        started: float,
        now_utc: datetime,
    ) -> SignalCreationResult:
        if self._config.raise_on_error:
            raise exc

        error_code = exc.code.replace("MSE_", "")
        rejection = self._build_rejection(
            decision,
            [error_code],
            [str(exc)],
            started,
            now_utc,
        )
        if self._config.events.publish_rejections:
            self._publisher.publish_signal_rejected(rejection)

        logger.info(
            "Signal rejected",
            extra={
                "decision_id": decision.decision_id,
                "error_codes": rejection.error_codes,
            },
        )
        return SignalCreationResult(
            accepted=False,
            rejection=rejection,
            decision_state=decision.state.value,
            duration_ms=rejection.metadata.duration_ms,
        )

    def _reject_from_gate(
        self,
        decision: TradeDecision,
        gate: Any,
        started: float,
        now_utc: datetime,
    ) -> SignalCreationResult:
        error_code = gate.error_code or "SIGNAL_VALIDATION_FAILED"
        if self._config.raise_on_error:
            exception_map = {
                "SIGNAL_VALIDATION_FAILED": SignalValidationError,
                "SIGNAL_EXPIRED": SignalExpiredError,
                "LOW_CONFIDENCE": LowConfidenceError,
                "DUPLICATE_SIGNAL": DuplicateSignalError,
                "INVALID_DECISION": InvalidDecisionError,
                "INVALID_RISK": InvalidRiskError,
            }
            exc_cls = exception_map.get(error_code, SignalValidationError)
            raise exc_cls(gate.blocking_reason or "Validation failed")

        rejection = self._build_rejection(
            decision,
            [error_code],
            [gate.blocking_reason or "Validation failed"],
            started,
            now_utc,
        )
        if self._config.events.publish_rejections:
            self._publisher.publish_signal_rejected(rejection)

        return SignalCreationResult(
            accepted=False,
            rejection=rejection,
            decision_state=decision.state.value,
            duration_ms=rejection.metadata.duration_ms,
        )

    def _build_rejection(
        self,
        decision: TradeDecision,
        error_codes: list[str],
        blocking_reasons: list[str],
        started: float,
        now_utc: datetime,
    ) -> SignalRejection:
        duration_ms = int((perf_counter() - started) * 1000)
        metadata = SignalMetadata(
            pipeline_version=PIPELINE_VERSION,
            config_hash=self._config_hash(),
            duration_ms=duration_ms,
            decision_id=decision.decision_id,
            decision_timestamp_utc=decision.timestamp_utc,
        )
        return SignalRejection(
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            timestamp_utc=now_utc,
            error_codes=error_codes,
            blocking_reasons=blocking_reasons,
            decision_state=decision.state.value,
            metadata=metadata,
        )

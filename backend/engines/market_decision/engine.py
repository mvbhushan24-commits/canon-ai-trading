"""Market Decision Engine orchestrator."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any

from backend.engines.market_breaker import BreakerBlockAnalysis
from backend.engines.market_decision.config import (
    MarketDecisionConfig,
    NewsRestrictionHook,
    load_market_decision_config,
)
from backend.engines.market_decision.conflicts import ConflictDetector
from backend.engines.market_decision.entry import EntryGenerator
from backend.engines.market_decision.evidence import (
    EvidenceCollector,
    EvidenceNormalizer,
    resolve_provisional_direction,
)
from backend.engines.market_decision.exceptions import (
    ConfigurationError,
    DecisionEngineError,
    DecisionValidationError,
)
from backend.engines.market_decision.publisher import DecisionEventPublisher
from backend.engines.market_decision.quality import DecisionQualityScorer
from backend.engines.market_decision.risk import RiskValidator
from backend.engines.market_decision.events import DecisionAnalysisEvent
from backend.engines.market_decision.schemas import (
    DecisionMetadata,
    DecisionState,
    EntrySpec,
    EvidenceCache,
    PIPELINE_VERSION,
    QualityTier,
    RiskSummary,
    TradeDecision,
    TradeDirection,
)
from backend.engines.market_decision.stop_loss import StopLossGenerator
from backend.engines.market_decision.take_profit import TakeProfitGenerator
from backend.engines.market_decision.validator import (
    LiquidityValidator,
    PremiumDiscountValidator,
    SessionValidator,
    StructureValidator,
    ZoneValidator,
)
from backend.engines.market_decision.weights import ConfidenceScorer, EvidenceWeighter
from backend.engines.market_decision.validator import DecisionInputValidator
from backend.engines.market_fvg import FairValueGapAnalysis
from backend.engines.market_liquidity import LiquidityAnalysis
from backend.engines.market_mitigation import MitigationBlockAnalysis
from backend.engines.market_order_block import OrderBlockAnalysis
from backend.engines.market_premium_discount import PremiumDiscountAnalysis
from backend.engines.market_sessions import SessionAnalysis
from backend.engines.market_structure import MarketStructure

logger = logging.getLogger(__name__)


class MarketDecisionEngine:
    """Institutional trade decision synthesis orchestrator."""

    def __init__(
        self,
        config: MarketDecisionConfig | None = None,
        validator: DecisionInputValidator | None = None,
        collector: EvidenceCollector | None = None,
        normalizer: EvidenceNormalizer | None = None,
        conflict_detector: ConflictDetector | None = None,
        weighter: EvidenceWeighter | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
        session_validator: SessionValidator | None = None,
        structure_validator: StructureValidator | None = None,
        liquidity_validator: LiquidityValidator | None = None,
        premium_discount_validator: PremiumDiscountValidator | None = None,
        zone_validator: ZoneValidator | None = None,
        entry_generator: EntryGenerator | None = None,
        stop_loss_generator: StopLossGenerator | None = None,
        take_profit_generator: TakeProfitGenerator | None = None,
        risk_validator: RiskValidator | None = None,
        quality_scorer: DecisionQualityScorer | None = None,
        publisher: DecisionEventPublisher | None = None,
        news_restriction_hook: NewsRestrictionHook | None = None,
    ) -> None:
        self._config = config or load_market_decision_config()
        self._validator = validator or DecisionInputValidator()
        self._collector = collector or EvidenceCollector(self._config)
        self._normalizer = normalizer or EvidenceNormalizer()
        self._conflict_detector = conflict_detector or ConflictDetector(self._config)
        self._weighter = weighter or EvidenceWeighter(self._config)
        self._confidence_scorer = confidence_scorer or ConfidenceScorer(self._config)
        self._session_validator = session_validator or SessionValidator(self._config)
        self._structure_validator = structure_validator or StructureValidator(self._config)
        self._liquidity_validator = liquidity_validator or LiquidityValidator(self._config)
        self._premium_discount_validator = PremiumDiscountValidator(self._config)
        self._zone_validator = zone_validator or ZoneValidator(self._config)
        self._entry_generator = entry_generator or EntryGenerator(self._config)
        self._stop_loss_generator = stop_loss_generator or StopLossGenerator(self._config)
        self._take_profit_generator = take_profit_generator or TakeProfitGenerator(self._config)
        self._risk_validator = risk_validator or RiskValidator(
            self._config,
            news_hook=news_restriction_hook,
        )
        self._quality_scorer = quality_scorer or DecisionQualityScorer(self._config)
        self._publisher = publisher or DecisionEventPublisher()
        self._evidence_cache = EvidenceCache()
        self._active_decisions: dict[str, TradeDecision] = {}

    @property
    def config(self) -> MarketDecisionConfig:
        return self._config

    @property
    def publisher(self) -> DecisionEventPublisher:
        return self._publisher

    @property
    def evidence_cache(self) -> EvidenceCache:
        return self._evidence_cache

    @property
    def active_decisions(self) -> dict[str, TradeDecision]:
        return dict(self._active_decisions)

    def decide(
        self,
        symbol: str,
        timestamp_utc: datetime,
        current_price: Decimal,
        *,
        spread: Decimal | None = None,
        structure: MarketStructure | None = None,
        liquidity: LiquidityAnalysis | None = None,
        order_blocks: OrderBlockAnalysis | None = None,
        fair_value_gaps: FairValueGapAnalysis | None = None,
        breaker_blocks: BreakerBlockAnalysis | None = None,
        mitigation_blocks: MitigationBlockAnalysis | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        sessions: SessionAnalysis | None = None,
    ) -> TradeDecision:
        """Run the full decision pipeline and return a trade decision."""
        started = perf_counter()
        decision_id = str(uuid.uuid4())
        reasons: list[str] = []
        blocking_reasons: list[str] = []
        warnings: list[str] = []
        error_codes: list[str] = []

        try:
            if current_price is None or current_price <= 0:
                return self._build_decision(
                    decision_id=decision_id,
                    symbol=symbol,
                    timestamp_utc=timestamp_utc,
                    state=DecisionState.NO_DATA,
                    direction=TradeDirection.NONE,
                    blocking_reasons=["current_price missing or invalid"],
                    started=started,
                )

            self._validator.validate_or_raise(symbol, timestamp_utc, current_price, self._config)
        except DecisionValidationError as exc:
            return self._handle_error(
                decision_id,
                symbol,
                timestamp_utc,
                exc,
                started,
                state=DecisionState.INVALID if current_price and current_price > 0 else DecisionState.NO_DATA,
            )
        except ConfigurationError as exc:
            return self._handle_error(decision_id, symbol, timestamp_utc, exc, started)

        bundle = self._collector.collect(
            symbol,
            timestamp_utc,
            current_price,
            spread=spread,
            structure=structure,
            liquidity=liquidity,
            order_blocks=order_blocks,
            fair_value_gaps=fair_value_gaps,
            breaker_blocks=breaker_blocks,
            mitigation_blocks=mitigation_blocks,
            premium_discount=premium_discount,
            sessions=sessions,
        )

        available = bundle.availability.available_count
        stale_count = bundle.availability.stale_count
        if available < self._config.evidence.min_required_engines:
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                blocking_reasons=[
                    f"Insufficient evidence: {available} engines available, "
                    f"minimum {self._config.evidence.min_required_engines} required",
                ],
                error_codes=["INSUFFICIENT_EVIDENCE"],
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
            )
            self.publish_events(decision)
            return decision

        if available < 8 and available >= self._config.evidence.min_required_engines:
            warnings.append(
                f"Partial evidence: {available}/8 engines available — proceeding with degraded confidence",
            )

        normalized = self._normalizer.normalize(bundle)
        weighted = self._weighter.weight(normalized)
        warnings.extend(weighted.warnings)

        conflict = self._conflict_detector.detect(weighted)
        if self._conflict_detector.should_reject(conflict):
            blocking = [
                "Conflicting evidence exceeds reject threshold",
            ]
            if conflict.conflicting_engines:
                pairs = [
                    f"{a} vs {b}" for a, b in conflict.conflicting_engines[:3]
                ]
                blocking.append(f"Conflicting engines: {', '.join(pairs)}")
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=weighted.confidence,
                blocking_reasons=blocking,
                error_codes=["CONFLICTING_EVIDENCE"],
                evidence_summary=weighted.summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
            )
            self.publish_events(decision)
            return decision

        if self._conflict_detector.should_warn(conflict):
            warnings.append(
                f"Evidence conflict ratio {conflict.conflict_ratio.quantize(Decimal('0.01'))} — confidence reduced",
            )

        provisional = resolve_provisional_direction(
            weighted.bullish_weight,
            weighted.bearish_weight,
            self._config.confidence.min_directional_weight,
        )
        zone_count = self._zone_validator.count_aligned_zones(
            bundle,
            provisional,
            current_price,
        )
        confidence = self._confidence_scorer.score(
            weighted,
            conflict,
            zone_confluence_count=zone_count,
            stale_engine_count=stale_count,
        )

        if not self._confidence_scorer.meets_minimum(confidence):
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=confidence,
                blocking_reasons=[
                    f"Confidence {confidence} below minimum {self._config.confidence.min_confidence}",
                ],
                error_codes=["LOW_CONFIDENCE"],
                evidence_summary=weighted.summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
                zone_confluence_count=zone_count,
            )
            self.publish_events(decision)
            return decision

        if provisional is TradeDirection.NONE:
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=confidence,
                blocking_reasons=["Directional weight insufficient for BUY or SELL"],
                evidence_summary=weighted.summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
                zone_confluence_count=zone_count,
            )
            self.publish_events(decision)
            return decision

        gate_checks = [
            self._session_validator.validate(bundle, provisional),
            self._structure_validator.validate(bundle, provisional),
            self._liquidity_validator.validate(bundle, provisional),
            self._premium_discount_validator.validate(bundle, provisional),
            self._zone_validator.validate(bundle, provisional, zone_count),
        ]
        for gate in gate_checks:
            warnings.extend(gate.warnings)
            if not gate.passed:
                decision = self._build_decision(
                    decision_id=decision_id,
                    symbol=symbol,
                    timestamp_utc=timestamp_utc,
                    state=DecisionState.NO_TRADE,
                    direction=TradeDirection.NONE,
                    confidence=confidence,
                    blocking_reasons=[gate.blocking_reason or "Validation gate failed"],
                    error_codes=[gate.error_code or "NO_TRADE"],
                    evidence_summary=weighted.summary,
                    warnings=warnings,
                    started=started,
                    engines_available=available,
                    engines_stale=stale_count,
                    conflict_severity=conflict.severity.value,
                    zone_confluence_count=zone_count,
                )
                self.publish_events(decision)
                return decision

        entry, entry_gate, _candidates = self._entry_generator.generate(bundle, provisional)
        if entry is None or not entry_gate.passed:
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=confidence,
                blocking_reasons=[entry_gate.blocking_reason or "Entry generation failed"],
                error_codes=[entry_gate.error_code or "INVALID_RISK"],
                evidence_summary=weighted.summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
                zone_confluence_count=zone_count,
            )
            self.publish_events(decision)
            return decision

        entry_price = self._entry_generator.entry_price(entry)
        stop_loss, stop_gate = self._stop_loss_generator.generate(
            bundle,
            provisional,
            entry,
            entry_price,
        )
        if stop_loss is None or not stop_gate.passed:
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=confidence,
                entry=entry,
                blocking_reasons=[stop_gate.blocking_reason or "Stop loss generation failed"],
                error_codes=[stop_gate.error_code or "INVALID_RISK"],
                evidence_summary=weighted.summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
                zone_confluence_count=zone_count,
            )
            self.publish_events(decision)
            return decision

        take_profit = self._take_profit_generator.generate(
            bundle,
            provisional,
            entry_price,
            stop_loss,
        )
        rr, rr_summary, rr_gate = self._risk_validator.validate_risk_reward(
            entry_price,
            stop_loss,
            take_profit,
        )
        if not rr_gate.passed:
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=confidence,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=rr,
                blocking_reasons=[rr_gate.blocking_reason or "Risk-reward validation failed"],
                error_codes=[rr_gate.error_code or "INVALID_RISK"],
                evidence_summary=weighted.summary,
                risk_summary=rr_summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
                zone_confluence_count=zone_count,
            )
            self.publish_events(decision)
            return decision

        stop_size_pips = abs(entry_price - stop_loss) / self._config.pip_size_decimal
        session_gate = self._session_validator.validate(bundle, provisional)
        risk_summary, risk_gate = self._risk_validator.validate(
            direction=provisional,
            confidence=confidence,
            spread=spread,
            stop_size_pips=stop_size_pips,
            session_allowed=session_gate.passed,
            symbol=symbol,
            timestamp_utc=timestamp_utc,
            existing_summary=rr_summary,
        )
        if not risk_gate.passed:
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=confidence,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=rr,
                blocking_reasons=[risk_gate.blocking_reason or "Risk validation failed"],
                error_codes=[risk_gate.error_code or "INVALID_RISK"],
                evidence_summary=weighted.summary,
                risk_summary=risk_summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
                zone_confluence_count=zone_count,
            )
            self.publish_events(decision)
            return decision

        quality_score, quality_tier = self._quality_scorer.score(
            bundle,
            weighted,
            zone_confluence_count=zone_count,
            direction=provisional,
        )
        if not self._quality_scorer.meets_minimum(quality_score):
            decision = self._build_decision(
                decision_id=decision_id,
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                state=DecisionState.NO_TRADE,
                direction=TradeDirection.NONE,
                confidence=confidence,
                quality_score=quality_score,
                quality_tier=quality_tier,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward_ratio=rr,
                blocking_reasons=[
                    f"Quality score {quality_score} below minimum "
                    f"{self._config.quality.min_quality_score}",
                ],
                evidence_summary=weighted.summary,
                risk_summary=risk_summary,
                warnings=warnings,
                started=started,
                engines_available=available,
                engines_stale=stale_count,
                conflict_severity=conflict.severity.value,
                zone_confluence_count=zone_count,
            )
            self.publish_events(decision)
            return decision

        reasons.extend(self._build_reasons(bundle, provisional, weighted))
        state = DecisionState.BUY if provisional is TradeDirection.BUY else DecisionState.SELL

        decision = self._build_decision(
            decision_id=decision_id,
            symbol=symbol,
            timestamp_utc=timestamp_utc,
            state=state,
            direction=provisional,
            confidence=confidence,
            quality_score=quality_score,
            quality_tier=quality_tier,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=rr,
            reasons=reasons,
            evidence_summary=weighted.summary,
            risk_summary=risk_summary,
            warnings=warnings,
            started=started,
            engines_available=available,
            engines_stale=stale_count,
            conflict_severity=conflict.severity.value,
            zone_confluence_count=zone_count,
        )
        self._active_decisions[symbol] = decision
        self.publish_events(decision)
        return decision

    def evaluate_cached(self, symbol: str) -> TradeDecision:
        """Run pipeline on cached evidence."""
        cache = self._evidence_cache
        if cache.current_price is None:
            return self._build_decision(
                decision_id=str(uuid.uuid4()),
                symbol=symbol,
                timestamp_utc=datetime.now(tz=UTC),
                state=DecisionState.NO_DATA,
                direction=TradeDirection.NONE,
                blocking_reasons=["Cached current_price unavailable"],
                started=perf_counter(),
            )
        timestamp = cache.price_timestamp_utc or datetime.now(tz=UTC)
        return self.decide(
            symbol,
            timestamp,
            cache.current_price,
            spread=cache.spread,
            structure=cache.structure,
            liquidity=cache.liquidity,
            order_blocks=cache.order_blocks,
            fair_value_gaps=cache.fair_value_gaps,
            breaker_blocks=cache.breaker_blocks,
            mitigation_blocks=cache.mitigation_blocks,
            premium_discount=cache.premium_discount,
            sessions=cache.sessions,
        )

    def handle_structure_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.structure = MarketStructure.model_validate(payload)
        self._evidence_cache.symbol = self._evidence_cache.structure.symbol

    def handle_liquidity_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.liquidity = LiquidityAnalysis.model_validate(payload)

    def handle_order_block_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.order_blocks = OrderBlockAnalysis.model_validate(payload)

    def handle_fvg_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.fair_value_gaps = FairValueGapAnalysis.model_validate(payload)

    def handle_breaker_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.breaker_blocks = BreakerBlockAnalysis.model_validate(payload)

    def handle_mitigation_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.mitigation_blocks = MitigationBlockAnalysis.model_validate(payload)

    def handle_premium_discount_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.premium_discount = PremiumDiscountAnalysis.model_validate(payload)

    def handle_session_completed(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        self._evidence_cache.sessions = SessionAnalysis.model_validate(payload)

    def handle_tick_received(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", event)
        bid = payload.get("bid")
        ask = payload.get("ask")
        if bid is not None and ask is not None:
            bid_dec = Decimal(str(bid))
            ask_dec = Decimal(str(ask))
            self._evidence_cache.current_price = (bid_dec + ask_dec) / 2
            self._evidence_cache.spread = ask_dec - bid_dec
        elif payload.get("mid") is not None:
            self._evidence_cache.current_price = Decimal(str(payload["mid"]))
            if payload.get("spread") is not None:
                self._evidence_cache.spread = Decimal(str(payload["spread"]))
        self._evidence_cache.symbol = str(payload.get("symbol", self._evidence_cache.symbol))
        ts = payload.get("timestamp_utc")
        if ts:
            self._evidence_cache.price_timestamp_utc = datetime.fromisoformat(str(ts))

    def handle_config_updated(self, config: MarketDecisionConfig) -> None:
        self._config = config
        self._collector = EvidenceCollector(config)
        self._conflict_detector = ConflictDetector(config)
        self._weighter = EvidenceWeighter(config)
        self._confidence_scorer = ConfidenceScorer(config)
        self._session_validator = SessionValidator(config)
        self._structure_validator = StructureValidator(config)
        self._liquidity_validator = LiquidityValidator(config)
        self._premium_discount_validator = PremiumDiscountValidator(config)
        self._zone_validator = ZoneValidator(config)
        self._entry_generator = EntryGenerator(config)
        self._stop_loss_generator = StopLossGenerator(config)
        self._take_profit_generator = TakeProfitGenerator(config)
        self._risk_validator = RiskValidator(config)
        self._quality_scorer = DecisionQualityScorer(config)
        logger.info("Market decision configuration updated")

    def expire_decisions(self, now: datetime) -> list[TradeDecision]:
        """Expire stale active decisions."""
        expired: list[TradeDecision] = []
        for symbol, decision in list(self._active_decisions.items()):
            if decision.valid_until_utc and now >= decision.valid_until_utc:
                self._publisher.publish_decision_expired(decision)
                expired.append(decision)
                del self._active_decisions[symbol]
        return expired

    def publish_events(self, decision: TradeDecision) -> None:
        """Emit lifecycle events for a decision."""
        self._publisher.publish_decision_created(decision)
        if decision.state in {DecisionState.BUY, DecisionState.SELL}:
            self._publisher.publish_decision_published(decision)
        elif decision.state in {DecisionState.NO_TRADE, DecisionState.INVALID}:
            self._publisher.publish_decision_rejected(decision)
        elif decision.state is DecisionState.WAIT and self._config.publish_wait_events:
            self._publisher.publish(
                DecisionAnalysisEvent(
                    "decision.wait.published",
                    symbol=decision.symbol,
                    payload=decision.model_dump(mode="json"),
                    timestamp_utc=decision.timestamp_utc,
                ),
            )

    def reset_cache(self) -> None:
        """Clear evidence cache."""
        self._evidence_cache = EvidenceCache()

    def _build_reasons(self, bundle, direction: TradeDirection, weighted) -> list[str]:
        reasons: list[str] = []
        if bundle.structure is not None:
            reasons.append(f"Structure trend: {bundle.structure.current_trend.value}")
        if bundle.liquidity is not None and bundle.liquidity.sweeps:
            reasons.append(f"Recent liquidity sweep: {bundle.liquidity.sweeps[-1].direction.value}")
        if bundle.order_blocks is not None and bundle.order_blocks.fresh_blocks:
            reasons.append(
                f"Active {bundle.order_blocks.fresh_blocks[0].direction.value} order block",
            )
        if bundle.premium_discount is not None:
            reasons.append(f"Price in {bundle.premium_discount.price_location.value} territory")
        if bundle.sessions is not None and bundle.sessions.active_kill_zones:
            reasons.append(
                f"Kill zone active: {bundle.sessions.active_kill_zones[0].display_name}",
            )
        reasons.append(f"Composite confidence {weighted.confidence} supports {direction.value}")
        return reasons

    def _build_decision(
        self,
        *,
        decision_id: str,
        symbol: str,
        timestamp_utc: datetime,
        state: DecisionState,
        direction: TradeDirection,
        confidence: int = 0,
        quality_score: int = 0,
        quality_tier=None,
        entry: EntrySpec | None = None,
        stop_loss: Decimal | None = None,
        take_profit: list[Decimal] | None = None,
        risk_reward_ratio: Decimal | None = None,
        reasons: list[str] | None = None,
        blocking_reasons: list[str] | None = None,
        error_codes: list[str] | None = None,
        evidence_summary=None,
        risk_summary=None,
        warnings: list[str] | None = None,
        started: float,
        engines_available: int = 0,
        engines_stale: int = 0,
        conflict_severity: str = "none",
        zone_confluence_count: int = 0,
    ) -> TradeDecision:
        valid_until = None
        if state in {DecisionState.BUY, DecisionState.SELL}:
            valid_until = timestamp_utc + timedelta(minutes=self._config.decision_validity_minutes)

        duration_ms = int((perf_counter() - started) * 1000)
        metadata = DecisionMetadata(
            pipeline_version=PIPELINE_VERSION,
            config_hash=self._config_hash(),
            duration_ms=duration_ms,
            engines_available=engines_available,
            engines_stale=engines_stale,
            conflict_severity=conflict_severity,
            zone_confluence_count=zone_confluence_count,
        )

        return TradeDecision(
            decision_id=decision_id,
            symbol=symbol,
            timestamp_utc=timestamp_utc,
            state=state,
            direction=direction,
            entry=entry or EntrySpec(),
            stop_loss=stop_loss,
            take_profit=take_profit or [],
            risk_reward_ratio=risk_reward_ratio,
            confidence=confidence,
            quality_score=quality_score,
            quality_tier=quality_tier or QualityTier.LOW,
            reasons=reasons or [],
            blocking_reasons=blocking_reasons or [],
            evidence_summary=evidence_summary or [],
            risk_summary=risk_summary or RiskSummary(),
            warnings=warnings or [],
            error_codes=error_codes or [],
            valid_until_utc=valid_until,
            metadata=metadata,
        )

    def _config_hash(self) -> str:
        payload = self._config.model_dump_json()
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def _handle_error(
        self,
        decision_id: str,
        symbol: str,
        timestamp_utc: datetime,
        exc: DecisionEngineError,
        started: float,
        *,
        state: DecisionState = DecisionState.INVALID,
    ) -> TradeDecision:
        if self._config.raise_on_error:
            raise exc
        decision = self._build_decision(
            decision_id=decision_id,
            symbol=symbol,
            timestamp_utc=timestamp_utc,
            state=state,
            direction=TradeDirection.NONE,
            blocking_reasons=[str(exc)],
            error_codes=[exc.code.replace("MDE_", "")],
            started=started,
        )
        self.publish_events(decision)
        return decision

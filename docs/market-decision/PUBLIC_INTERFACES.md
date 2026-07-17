# Decision Engine — Public Interfaces

**Engine ID:** `market_decision`  
**Sprint:** 10.1 (Architecture specification)  
**Planned Module:** `backend.engines.market_decision`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_decision.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_decision import (
    MarketDecisionEngine,
    TradeDecision,
    EvidenceBundle,
    EvidenceSummaryItem,
    RiskSummary,
    EntrySpec,
    MarketDecisionConfig,
    load_market_decision_config,
    DecisionEventPublisher,
    DecisionState,
    TradeDirection,
    QualityTier,
    # ... see __all__
)
```

---

## MarketDecisionEngine

**Purpose:** Public orchestrator for institutional trade decision synthesis.

### Constructor

```python
MarketDecisionEngine(
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
    zone_validators: ZoneValidators | None = None,
    entry_generator: EntryGenerator | None = None,
    stop_loss_generator: StopLossGenerator | None = None,
    take_profit_generator: TakeProfitGenerator | None = None,
    risk_validator: RiskValidator | None = None,
    quality_scorer: DecisionQualityScorer | None = None,
    decision_generator: FinalDecisionGenerator | None = None,
    publisher: DecisionEventPublisher | None = None,
    news_restriction_hook: NewsRestrictionHook | None = None,
)
```

Dependency injection follows Sprints 1–9 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `MarketDecisionConfig` | Active configuration |
| `publisher` | `DecisionEventPublisher` | Event publisher instance |
| `evidence_cache` | `EvidenceCache` | Latest upstream envelopes (event mode) |
| `active_decisions` | `dict[str, TradeDecision]` | Non-expired decisions by symbol |

### Primary Method

#### `decide(symbol, timestamp_utc, current_price, *, spread=None, structure=None, liquidity=None, order_blocks=None, fair_value_gaps=None, breaker_blocks=None, mitigation_blocks=None, sessions=None, premium_discount=None) -> TradeDecision`

| | |
|---|---|
| **Input** | `str` — symbol (`XAUUSD` / `GOLD.i#`) |
| | `datetime` — timezone-aware UTC reference time |
| | `Decimal` — current mid price (**required**) |
| | `Decimal \| None` — current spread in price units |
| | `MarketStructure \| None` — Sprint 2 output |
| | `LiquidityAnalysis \| None` — Sprint 3 output |
| | `OrderBlockAnalysis \| None` — Sprint 4 output |
| | `FairValueGapAnalysis \| None` — Sprint 5 output |
| | `BreakerBlockAnalysis \| None` — Sprint 6 output |
| | `MitigationBlockAnalysis \| None` — Sprint 7 output |
| | `PremiumDiscountAnalysis \| None` — Sprint 8 output |
| | `SessionAnalysis \| None` — Sprint 9 output |
| **Output** | `TradeDecision` |
| **Raises** | `ValidationError` → caught internally; returns `INVALID` state |
| | `ConfigurationError` → caught internally; returns `INVALID` state |
| **Events** | `DecisionCreated`, `DecisionPublished` or `DecisionRejected` |
| **Side Effects** | Optional SQLite persistence; cache update |

### Secondary Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `evaluate_cached(symbol)` | Symbol | `TradeDecision` | Run pipeline on cached evidence |
| `handle_structure_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_liquidity_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_order_block_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_fvg_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_breaker_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_mitigation_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_premium_discount_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_session_completed(event)` | Event payload | `None` | Update evidence cache |
| `handle_tick_received(event)` | Event payload | `None` | Update current price |
| `handle_config_updated(config)` | Config | `None` | Reload configuration |
| `expire_decisions(now)` | UTC datetime | `list[TradeDecision]` | Expire stale decisions |
| `publish_events(decision)` | `TradeDecision` | `None` | Emit lifecycle events |
| `reset_cache()` | — | `None` | Clear evidence cache |

---

## TradeDecision

Primary output schema.

| Field | Type | Description |
|-------|------|-------------|
| `decision_id` | `str` | UUID v4 |
| `symbol` | `str` | Instrument identifier |
| `timestamp_utc` | `datetime` | Decision timestamp (UTC) |
| `state` | `DecisionState` | Terminal or interim state |
| `direction` | `TradeDirection` | `BUY`, `SELL`, `NONE` |
| `entry` | `EntrySpec` | Entry specification |
| `stop_loss` | `Decimal \| None` | Protective stop (signal only) |
| `take_profit` | `list[Decimal]` | Ordered profit targets (signal only) |
| `risk_reward_ratio` | `Decimal \| None` | Primary target R:R |
| `confidence` | `int` | 0–100 composite confidence |
| `quality_score` | `int` | 0–100 decision quality |
| `quality_tier` | `QualityTier` | `high`, `medium`, `low` |
| `reasons` | `list[str]` | Full explainability chain |
| `blocking_reasons` | `list[str]` | Why not tradeable |
| `evidence_summary` | `list[EvidenceSummaryItem]` | Per-engine summary |
| `risk_summary` | `RiskSummary` | Risk validation outcomes |
| `warnings` | `list[str]` | Non-blocking concerns |
| `error_codes` | `list[str]` | Error codes when applicable |
| `valid_until_utc` | `datetime \| None` | Decision expiry |
| `metadata` | `DecisionMetadata` | Pipeline metadata |

### DecisionState

```python
class DecisionState(StrEnum):
    NO_DATA = "NO_DATA"
    WAIT = "WAIT"
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"
    INVALID = "INVALID"
```

### TradeDirection

```python
class TradeDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"
```

### QualityTier

```python
class QualityTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

---

## EntrySpec

| Field | Type | Description |
|-------|------|-------------|
| `price` | `Decimal \| None` | Point entry when single price |
| `zone_high` | `Decimal \| None` | Zone upper bound |
| `zone_low` | `Decimal \| None` | Zone lower bound |
| `entry_type` | `EntryType` | `point`, `zone`, `ote` |
| `source_engine` | `str` | Primary zone source engine ID |
| `source_zone_id` | `str \| None` | Source zone identifier |
| `distance_pips` | `Decimal` | Distance from current price |

---

## EvidenceSummaryItem

| Field | Type | Description |
|-------|------|-------------|
| `engine_id` | `str` | Source engine |
| `available` | `bool` | Envelope present |
| `stale` | `bool` | Exceeded max age |
| `direction_bias` | `str` | Normalized bias |
| `confidence` | `Decimal` | Upstream confidence |
| `weight` | `Decimal` | Configured weight |
| `weighted_contribution` | `Decimal` | Computed contribution |
| `quality_tier` | `str \| None` | Upstream quality |
| `key_evidence` | `list[str]` | Top reasoning snippets |

---

## RiskSummary

| Field | Type | Description |
|-------|------|-------------|
| `risk_reward_ratio` | `Decimal \| None` | Computed R:R |
| `stop_size_pips` | `Decimal \| None` | Stop distance in pips |
| `spread_pips` | `Decimal \| None` | Current spread |
| `min_rr_met` | `bool` | Minimum R:R satisfied |
| `max_rr_met` | `bool` | Maximum R:R satisfied |
| `spread_acceptable` | `bool` | Spread within limit |
| `stop_size_acceptable` | `bool` | Stop within limit |
| `confidence_acceptable` | `bool` | Confidence ≥ minimum |
| `session_allowed` | `bool` | Session gate passed |
| `news_blocked` | `bool` | News hook blocked |
| `news_block_reason` | `str \| None` | News block reason |
| `rule_outcomes` | `list[RiskRuleOutcome]` | Per-rule pass/fail |

### RiskRuleOutcome

| Field | Type | Description |
|-------|------|-------------|
| `rule_name` | `str` | Rule identifier |
| `passed` | `bool` | Pass/fail |
| `actual_value` | `Decimal \| None` | Observed value |
| `threshold` | `Decimal \| None` | Configured threshold |
| `message` | `str` | Human-readable outcome |

---

## EvidenceBundle

Internal pipeline type; exposed for testing and diagnostics.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Instrument |
| `timestamp_utc` | `datetime` | Reference time |
| `current_price` | `Decimal` | Mid price |
| `spread` | `Decimal \| None` | Spread |
| `structure` | `MarketStructure \| None` | Sprint 2 |
| `liquidity` | `LiquidityAnalysis \| None` | Sprint 3 |
| `order_blocks` | `OrderBlockAnalysis \| None` | Sprint 4 |
| `fair_value_gaps` | `FairValueGapAnalysis \| None` | Sprint 5 |
| `breaker_blocks` | `BreakerBlockAnalysis \| None` | Sprint 6 |
| `mitigation_blocks` | `MitigationBlockAnalysis \| None` | Sprint 7 |
| `premium_discount` | `PremiumDiscountAnalysis \| None` | Sprint 8 |
| `sessions` | `SessionAnalysis \| None` | Sprint 9 |
| `availability` | `EvidenceAvailability` | Per-engine flags |

---

## DecisionMetadata

| Field | Type | Description |
|-------|------|-------------|
| `pipeline_version` | `str` | Engine version |
| `config_hash` | `str` | Configuration fingerprint |
| `duration_ms` | `int` | Pipeline execution time |
| `engines_available` | `int` | Count of fresh engines |
| `engines_stale` | `int` | Count of stale engines |
| `conflict_severity` | `str` | Conflict report severity |
| `zone_confluence_count` | `int` | Aligned zone count |

---

## Exceptions

| Exception | Code | When |
|-----------|------|------|
| `DecisionValidationError` | `MDE_DECISION_VALIDATION_FAILED` | Input validation failure |
| `InsufficientEvidenceError` | `MDE_INSUFFICIENT_EVIDENCE` | Below minimum engines |
| `ConflictingEvidenceError` | `MDE_CONFLICTING_EVIDENCE` | Conflict exceeds threshold |
| `LowConfidenceError` | `MDE_LOW_CONFIDENCE` | Confidence below minimum |
| `InvalidSessionError` | `MDE_INVALID_SESSION` | Session gate failure |
| `InvalidStructureError` | `MDE_INVALID_STRUCTURE` | Structure gate failure |
| `InvalidLiquidityError` | `MDE_INVALID_LIQUIDITY` | Liquidity gate failure |
| `InvalidOrderBlockError` | `MDE_INVALID_ORDER_BLOCK` | OB gate failure |
| `InvalidFVGError` | `MDE_INVALID_FVG` | FVG gate failure |
| `InvalidBreakerError` | `MDE_INVALID_BREAKER` | Breaker gate failure |
| `InvalidMitigationError` | `MDE_INVALID_MITIGATION` | Mitigation gate failure |
| `InvalidPremiumDiscountError` | `MDE_INVALID_PREMIUM_DISCOUNT` | P/D gate failure |
| `InvalidRiskError` | `MDE_INVALID_RISK` | Risk rule failure |
| `ConfigurationError` | `MDE_CONFIG_INVALID` | Invalid configuration |

**Note:** Public `decide()` catches domain exceptions internally and returns `TradeDecision` with appropriate `state`, `blocking_reasons`, and `error_codes`. Exceptions are raised only when `raise_on_error=True` (testing mode).

---

## Configuration Loader

### `load_market_decision_config(settings=None, yaml_path=None) -> MarketDecisionConfig`

| | |
|---|---|
| **Input** | Optional pre-loaded settings dict or YAML path |
| **Output** | Validated `MarketDecisionConfig` |
| **Raises** | `ConfigurationError` |

---

## DecisionEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | — |
| `publish_decision_created(decision)` | `DecisionCreated` |
| `publish_decision_published(decision)` | `DecisionPublished` |
| `publish_decision_rejected(decision)` | `DecisionRejected` |
| `publish_decision_updated(decision)` | `DecisionUpdated` |
| `publish_decision_expired(decision)` | `DecisionExpired` |

---

## NewsRestrictionHook

```python
class NewsRestrictionResult(BaseModel):
    blocked: bool
    reason: str = ""
    expires_utc: datetime | None = None

NewsRestrictionHook = Callable[[str, datetime], NewsRestrictionResult]
```

Injected via `MarketDecisionConfig.news_restriction_hook` or constructor. Default implementation returns `blocked=False`.

---

## Integration with Telegram Engine

Telegram Engine consumes `DecisionPublished` / `decision.signal.published` events.

Recommended filter:

```python
if decision.state in (DecisionState.BUY, DecisionState.SELL):
    if decision.confidence >= telegram_min_confidence:
        send_signal_alert(decision)
elif decision.state == DecisionState.NO_TRADE:
    # Optional: suppress or send low-priority info alert
    pass
```

See [../engines/telegram-engine.md](../engines/telegram-engine.md).

---

## Integration with Upstream Pipeline

### Recommended Orchestrator Wiring

```python
# After Sprints 1–9 complete for a cycle:
decision = decision_engine.decide(
    symbol=candles[0].symbol,
    timestamp_utc=datetime.now(UTC),
    current_price=latest_tick.mid,
    spread=latest_tick.spread,
    structure=structure_analysis,
    liquidity=liquidity_analysis,
    order_blocks=order_block_analysis,
    fair_value_gaps=fvg_analysis,
    breaker_blocks=breaker_analysis,
    mitigation_blocks=mitigation_analysis,
    premium_discount=premium_discount_analysis,
    sessions=session_analysis,
)
```

### Input Boundary

Decision Engine imports upstream types from public `__init__.py` exports only:

```python
from backend.engines.market_structure import MarketStructure
from backend.engines.market_liquidity import LiquidityAnalysis
from backend.engines.market_order_block import OrderBlockAnalysis
from backend.engines.market_fvg import FairValueGapAnalysis
from backend.engines.market_breaker import BreakerBlockAnalysis
from backend.engines.market_mitigation import MitigationBlockAnalysis
from backend.engines.market_premium_discount import PremiumDiscountAnalysis
from backend.engines.market_sessions import SessionAnalysis
```

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |

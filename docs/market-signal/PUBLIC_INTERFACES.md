# Signal Engine — Public Interfaces

**Engine ID:** `market_signal`  
**Sprint:** 11.1 (Architecture specification)  
**Planned Module:** `backend.engines.market_signal`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_signal.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_signal import (
    MarketSignalEngine,
    TradingSignal,
    SignalRejection,
    SignalCreationResult,
    SignalMetadata,
    MarketSignalConfig,
    load_market_signal_config,
    SignalEventPublisher,
    SignalState,
    SignalDirection,
    QualityTier,
    # ... see __all__
)
```

---

## MarketSignalEngine

**Purpose:** Public orchestrator for decision-to-signal conversion and lifecycle management.

### Constructor

```python
MarketSignalEngine(
    config: MarketSignalConfig | None = None,
    validator: SignalInputValidator | None = None,
    decision_validator: DecisionValidator | None = None,
    expiry_validator: ExpiryValidator | None = None,
    confidence_validator: ConfidenceValidator | None = None,
    session_validator: SignalSessionValidator | None = None,
    risk_validator: SignalRiskValidator | None = None,
    duplicate_detector: DuplicateDetector | None = None,
    entry_normalizer: EntryNormalizer | None = None,
    take_profit_mapper: TakeProfitMapper | None = None,
    quality_scorer: SignalQualityScorer | None = None,
    assembler: SignalAssembler | None = None,
    lifecycle: SignalLifecycleManager | None = None,
    publisher: SignalEventPublisher | None = None,
    store: SignalStore | None = None,
)
```

Dependency injection follows Sprints 1–10 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `MarketSignalConfig` | Active configuration |
| `publisher` | `SignalEventPublisher` | Event publisher instance |
| `active_signals` | `dict[str, TradingSignal]` | Non-terminal signals by `signal_id` |
| `active_by_symbol` | `dict[str, list[str]]` | Active signal IDs indexed by symbol |

### Primary Method

#### `create_signal(decision: TradeDecision, *, timestamp_utc: datetime | None = None) -> SignalCreationResult`

| | |
|---|---|
| **Input** | `TradeDecision` — from Decision Engine (`BUY`, `SELL`, `NO_TRADE`, `WAIT`, etc.) |
| | `datetime \| None` — override signal creation timestamp (default: `now UTC`) |
| **Output** | `SignalCreationResult` with `accepted: bool`, `signal: TradingSignal \| None`, `rejection: SignalRejection \| None` |
| **Raises** | `ValidationError` → caught internally; returns rejection |
| | `ConfigurationError` → caught internally; returns rejection |
| **Events** | `SignalCreated`, `SignalActivated` (when accepted and auto-activated) |
| **Side Effects** | Active registry update; optional SQLite persistence |

**Behavior by decision state:**

| `decision.state` | Result |
|------------------|--------|
| `BUY`, `SELL` | Run validation pipeline; return signal or rejection |
| `NO_TRADE`, `WAIT`, `NO_DATA` | `accepted=False`, no rejection (informational) |
| `INVALID` | `accepted=False`, `rejection` with `INVALID_DECISION` |

### Secondary Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `activate_signal(signal_id)` | Signal ID | `TradingSignal` | Transition `CREATED` → `ACTIVE` |
| `get_signal(signal_id)` | Signal ID | `TradingSignal \| None` | Retrieve signal by ID |
| `get_active_signals(symbol=None)` | Optional symbol | `list[TradingSignal]` | List active signals |
| `update_lifecycle(symbol, current_price, timestamp_utc)` | Symbol, price, time | `list[TradingSignal]` | Apply lifecycle checks |
| `expire_signals(now_utc)` | UTC datetime | `list[TradingSignal]` | Expire untriggered signals |
| `cancel_signal(signal_id, reason)` | ID, reason | `TradingSignal` | Cancel signal |
| `close_signal(signal_id, reason)` | ID, reason | `TradingSignal` | Close signal |
| `handle_decision_published(event)` | Event payload | `SignalCreationResult` | Event handler for `DecisionPublished` |
| `handle_tick_received(event)` | Tick payload | `list[TradingSignal]` | Lifecycle update from tick |
| `handle_config_updated(config)` | Config | `None` | Reload configuration |
| `reset_registry()` | — | `None` | Clear active signal registry (testing) |

---

## TradingSignal

Primary output schema.

| Field | Type | Description |
|-------|------|-------------|
| `signal_id` | `str` | UUID v4 |
| `decision_id` | `str` | Source decision UUID |
| `timestamp_utc` | `datetime` | Signal creation timestamp (UTC) |
| `symbol` | `str` | Instrument identifier |
| `timeframe` | `str` | Primary timeframe (e.g. `M15`, `H1`) |
| `direction` | `SignalDirection` | `BUY` or `SELL` |
| `state` | `SignalState` | Current lifecycle state |
| `entry_price` | `Decimal` | Resolved entry price |
| `stop_loss` | `Decimal` | Protective stop |
| `take_profit_1` | `Decimal` | Primary profit target |
| `take_profit_2` | `Decimal \| None` | Secondary target |
| `take_profit_3` | `Decimal \| None` | Tertiary target |
| `risk_reward` | `Decimal` | Primary target R:R |
| `confidence` | `int` | 0–100 from decision |
| `signal_quality` | `int` | 0–100 composite signal quality |
| `quality_tier` | `QualityTier` | `high`, `medium`, `low` |
| `reasons` | `list[str]` | Signal rationale |
| `evidence_summary` | `list[EvidenceSummaryItem]` | From decision |
| `risk_summary` | `RiskSummary` | From decision |
| `warnings` | `list[str]` | Non-blocking concerns |
| `expiry_time` | `datetime` | Signal validity deadline (UTC) |
| `metadata` | `SignalMetadata` | Pipeline metadata |

### SignalState

```python
class SignalState(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    TP1_HIT = "TP1_HIT"
    TP2_HIT = "TP2_HIT"
    TP3_HIT = "TP3_HIT"
    BREAK_EVEN = "BREAK_EVEN"
    TRAILING = "TRAILING"
    STOP_LOSS = "STOP_LOSS"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
```

### SignalDirection

```python
class SignalDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
```

### QualityTier

```python
class QualityTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

Re-exported from Decision Engine types where shared.

---

## SignalCreationResult

| Field | Type | Description |
|-------|------|-------------|
| `accepted` | `bool` | Whether a signal was created |
| `signal` | `TradingSignal \| None` | Created signal when accepted |
| `rejection` | `SignalRejection \| None` | Rejection details when not accepted |
| `decision_state` | `str` | Source decision state |
| `duration_ms` | `int` | Pipeline execution time |

---

## SignalRejection

| Field | Type | Description |
|-------|------|-------------|
| `decision_id` | `str` | Source decision UUID |
| `symbol` | `str` | Instrument |
| `timestamp_utc` | `datetime` | Rejection timestamp |
| `error_codes` | `list[str]` | Rejection error codes |
| `blocking_reasons` | `list[str]` | Human-readable reasons |
| `decision_state` | `str` | Source decision state |
| `metadata` | `SignalMetadata` | Pipeline metadata |

---

## SignalMetadata

| Field | Type | Description |
|-------|------|-------------|
| `pipeline_version` | `str` | Engine version |
| `config_hash` | `str` | Configuration fingerprint |
| `duration_ms` | `int` | Pipeline execution time |
| `decision_id` | `str` | Source decision reference |
| `decision_timestamp_utc` | `datetime` | Source decision time |
| `entry_type` | `str` | Original `EntrySpec.entry_type` |
| `tp_count` | `int` | Number of mapped take profits |
| `duplicate_check_passed` | `bool` | Duplicate detection outcome |

---

## LifecycleUpdateResult

| Field | Type | Description |
|-------|------|-------------|
| `signal_id` | `str` | Updated signal ID |
| `prior_state` | `SignalState` | State before update |
| `current_state` | `SignalState` | State after update |
| `transition_reason` | `str` | Why transition occurred |
| `current_price` | `Decimal` | Price used for check |
| `timestamp_utc` | `datetime` | Update timestamp |

---

## Exceptions

| Exception | Code | When |
|-----------|------|------|
| `SignalValidationError` | `MSE_SIGNAL_VALIDATION_FAILED` | Input validation failure |
| `SignalExpiredError` | `MSE_SIGNAL_EXPIRED` | Decision or signal expired |
| `LowConfidenceError` | `MSE_LOW_CONFIDENCE` | Confidence/quality below threshold |
| `DuplicateSignalError` | `MSE_DUPLICATE_SIGNAL` | Duplicate active signal |
| `InvalidDecisionError` | `MSE_INVALID_DECISION` | Decision not signal-eligible |
| `InvalidRiskError` | `MSE_INVALID_RISK` | Risk re-validation failure |
| `ConfigurationError` | `MSE_CONFIG_INVALID` | Invalid configuration |
| `SignalNotFoundError` | `MSE_SIGNAL_NOT_FOUND` | Signal ID not in registry |

**Note:** Public `create_signal()` catches domain exceptions internally and returns `SignalCreationResult` with appropriate rejection. Exceptions are raised only when `raise_on_error=True` (testing mode).

---

## Configuration Loader

### `load_market_signal_config(settings=None, yaml_path=None) -> MarketSignalConfig`

| | |
|---|---|
| **Input** | Optional pre-loaded settings dict or YAML path |
| **Output** | Validated `MarketSignalConfig` |
| **Raises** | `ConfigurationError` |

---

## SignalEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | — |
| `publish_signal_created(signal)` | `SignalCreated` |
| `publish_signal_activated(signal)` | `SignalActivated` |
| `publish_signal_triggered(signal)` | `SignalTriggered` |
| `publish_signal_expired(signal)` | `SignalExpired` |
| `publish_signal_cancelled(signal, reason)` | `SignalCancelled` |
| `publish_signal_closed(signal, reason)` | `SignalClosed` |
| `publish_signal_rejected(rejection)` | `SignalRejected` (optional audit) |

---

## Integration with Decision Engine

### Recommended Orchestrator Wiring

```python
# After Decision Engine produces BUY/SELL:
decision = decision_engine.decide(...)

if decision.state in (DecisionState.BUY, DecisionState.SELL):
    result = signal_engine.create_signal(decision)
    if result.accepted:
        # Signal ready for Telegram / Dashboard
        pass
```

### Event-Driven Wiring

```python
event_bus.on("decision.signal.published", signal_engine.handle_decision_published)
```

### Input Boundary

Signal Engine imports decision types from public `__init__.py` exports only:

```python
from backend.engines.market_decision import (
    TradeDecision,
    DecisionState,
    TradeDirection,
    EntrySpec,
    EvidenceSummaryItem,
    RiskSummary,
)
```

**Prohibited imports:** Any module from Sprints 1–9, Decision Engine internals (`collector.py`, `normalizer.py`, etc.), or market data engines.

---

## Integration with Telegram Engine

Telegram Engine will consume `SignalActivated` / `signal.activated` events (future migration).

Recommended filter:

```python
if signal.state == SignalState.ACTIVE:
    if signal.confidence >= telegram_min_confidence:
        if signal.signal_quality >= telegram_min_quality:
            send_signal_alert(signal)
```

Legacy path (until migration):

```python
# Telegram may still consume decision.signal.published directly
# Signal Engine runs in parallel during transition period
```

See [../engines/telegram-engine.md](../engines/telegram-engine.md).

---

## Integration with Dashboard

```python
event_bus.on("signal.created", dashboard.render_signal_card)
event_bus.on("signal.activated", dashboard.highlight_active_signal)
event_bus.on("signal.triggered", dashboard.update_signal_state)
event_bus.on("signal.closed", dashboard.archive_signal)
event_bus.on("signal.expired", dashboard.mark_signal_expired)
```

---

## REST API Surface (Planned — Sprint 11.2+)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/signals` | `GET` | List active and recent signals |
| `/api/v1/signals/{signal_id}` | `GET` | Get signal by ID |
| `/api/v1/signals/active` | `GET` | Active signals only |
| `/api/v1/signals/{signal_id}/cancel` | `POST` | Cancel signal |
| `/api/v1/signals/{signal_id}/close` | `POST` | Close signal |

All endpoints return `TradingSignal` JSON schema. No market analysis endpoints exposed.

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |
| Decision Engine Interfaces | [../market-decision/PUBLIC_INTERFACES.md](../market-decision/PUBLIC_INTERFACES.md) |

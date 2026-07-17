# Kill Zones & Trading Sessions Engine — Public Interfaces

**Engine ID:** `market_sessions`  
**Sprint:** 9.1 (Architecture specification)  
**Planned Module:** `backend/engines/market_sessions`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_sessions.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_sessions import (
    MarketSessionsEngine,
    SessionAnalysis,
    MarketSessionsState,
    MarketSessionsConfig,
    load_market_sessions_config,
    MarketSessionsEventPublisher,
    TradingSessionId,
    KillZoneId,
    SessionPhase,
    # ... see __all__
)
```

---

## MarketSessionsEngine

**Purpose:** Public orchestrator for session resolution, kill zone activation, calendar handling, opens, extremes, OR/IB, time-of-day filters, and quality scoring.

### Constructor

```python
MarketSessionsEngine(
    config: MarketSessionsConfig | None = None,
    detector: MarketSessionsDetector | None = None,
    validator: MarketSessionsInputValidator | None = None,
    publisher: MarketSessionsEventPublisher | None = None,
)
```

Dependency injection follows Sprints 1–8 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `MarketSessionsConfig` | Active configuration |
| `publisher` | `MarketSessionsEventPublisher` | Event publisher instance |
| `prior_state` | `MarketSessionsState \| None` | Persisted continuity state |

### Primary Method

#### `analyze(candles, *, timestamp_utc, structure=None, liquidity_state=None, premium_discount=None, broker_timezone=None, timeframe=None, prior_state=None) -> SessionAnalysis`

| | |
|---|---|
| **Input** | `list[NormalizedCandle]` — closed candles preferred |
| | `datetime` — timezone-aware UTC reference time (**required**) |
| | `MarketStructure \| None` — optional structure context |
| | `LiquidityState \| None` — optional liquidity continuity state |
| | `PremiumDiscountAnalysis \| None` — optional pricing context |
| | `str \| None` — IANA broker timezone override |
| | `str \| None` — timeframe override |
| | `MarketSessionsState \| None` — continuity state |
| **Output** | `SessionAnalysis` |
| **Raises** | `InsufficientDataError`, `ValidationError`, `InvalidTimestampError`, `InvalidTimezoneError`, `UnsupportedTimeframeError`, `InvalidStructureError`, `InvalidLiquidityStateError`, `InvalidPremiumDiscountError`, `StateCorruptError`, `ConfigInvalidError` |
| **Events** | All session lifecycle events via publisher |

### Analysis Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `resolve_sessions(timestamp_utc, broker_timezone=None)` | Timestamp + TZ | `list[TradingSessionState]` | Resolve all session windows |
| `resolve_kill_zones(timestamp_utc, sessions=None)` | Timestamp + sessions | `list[KillZoneState]` | Resolve all kill zones |
| `detect_overlaps(sessions, timestamp_utc)` | Sessions + timestamp | `list[SessionOverlap]` | Detect active overlaps |
| `forecast_transitions(timestamp_utc, horizon_hours=None)` | Timestamp | `list[SessionTransition]` | Forecast upcoming boundaries |
| `resolve_daily_open(candles, broker_timezone=None)` | Candles + TZ | `PeriodOpen \| None` | Daily open resolution |
| `resolve_weekly_open(candles, broker_timezone=None)` | Candles + TZ | `PeriodOpen \| None` | Weekly open resolution |
| `resolve_monthly_open(candles, broker_timezone=None)` | Candles + TZ | `PeriodOpen \| None` | Monthly open resolution |
| `track_session_extremes(candles, sessions, prior_extremes=None)` | Candles + sessions | `list[SessionExtreme]` | Session H/L tracking |
| `compute_opening_range(candles, session_id, timestamp_utc=None)` | Candles + session | `OpeningRange \| None` | Opening range computation |
| `compute_initial_balance(candles, session_id, timestamp_utc=None)` | Candles + session | `InitialBalance \| None` | Initial balance computation |
| `evaluate_time_filter(analysis_context)` | Partial context | `TimeOfDayFilter` | Time-of-day filter evaluation |
| `resolve_calendar(timestamp_utc, broker_timezone=None)` | Timestamp + TZ | `CalendarContext` | Weekend/holiday/DST |
| `score_quality(analysis_parts)` | Sub-results | `tuple[SessionQualityTier, Decimal, Decimal]` | Quality tier, strength, confidence |
| `publish_events(analysis)` | `SessionAnalysis` | `None` | Emit all lifecycle events |

### State Management

| Method | Description |
|--------|-------------|
| `reset_state()` | Clear persisted `prior_state` |
| `handle_config_updated(config)` | Hot reload configuration and rebuild detector |

---

## Input Contracts

### NormalizedCandle (Sprint 1 — Required)

Imported from `backend.engines.market_data`.

| Requirement | Rule |
|-------------|------|
| Minimum count | `>= config.min_candles` (or degraded mode) |
| Ordering | Chronological by `open_time_utc` |
| Scope | Single `symbol` and single `timeframe` per call |
| Integrity | Valid OHLC relationships; no duplicate timestamps |

### timestamp_utc (Required)

| Requirement | Rule |
|-------------|------|
| Timezone | Must be timezone-aware UTC |
| Usage | Primary reference for session/kill zone activation |
| Live analysis | Typically `datetime.now(timezone.utc)` |

### broker_timezone (Recommended)

| Requirement | Rule |
|-------------|------|
| Format | Valid IANA timezone string (e.g. `Europe/Nicosia`, `America/New_York`) |
| Fallback | `config.broker_timezone` when not supplied |
| Usage | Daily/weekly/monthly open boundaries, weekend classification |

### MarketStructure (Sprint 2 — Optional)

Imported from `backend.engines.market_structure`.

| Field | Usage |
|-------|-------|
| `current_trend` | Quality scoring, historical performance alignment |
| `bos_events`, `choch_events` | Volatility spike detection |
| `confidence` | Quality scoring factor |

### LiquidityState (Sprint 3 — Optional)

Imported from `backend.engines.market_liquidity`.

| Field | Usage |
|-------|-------|
| `active_zones` | Session H/L cross-validation |
| `recent_sweeps` | Liquidity availability scoring |
| `bar_count` | Consistency validation |

**Not consumed:** `LiquidityAnalysis` envelope fields.

### PremiumDiscountAnalysis (Sprint 8 — Optional)

Imported from `backend.engines.market_premium_discount`.

| Field | Usage |
|-------|-------|
| `price_location` | Session-open pricing context |
| `dealing_range` | Range comparison vs session range |
| `bias`, `quality` | Quality scoring factors |

---

## Output Contracts

### SessionAnalysis

Primary analysis envelope. See [ARCHITECTURE.md](./ARCHITECTURE.md) for full field reference.

**Decision Engine compatibility:** Maps to `session` input in [decision-engine.md](../engines/decision-engine.md):

| Decision Engine Field | SessionAnalysis Source |
|-----------------------|------------------------|
| `active_sessions` | `active_sessions[].session_id` |
| `primary_session` | `primary_session` |
| `session_phase` | `session_phase` |
| `volatility_profile` | `volatility_profile` |
| `is_high_impact_window` | `any(kz.is_active for kz in active_kill_zones)` |
| `next_transition_utc` | `next_transition.transition_time_utc` |
| `confidence` | `confidence` |
| `evidence` | `evidence` |

### TradingSessionState

Per-session state with window bounds, phase, and quality.

### KillZoneState

Per-kill-zone state with window bounds, quality, liquidity, and historical scores.

### SessionOverlap

Concurrent session overlap with quality scoring.

### SessionTransition

Boundary crossing record with transition type and phase change.

### PeriodOpen

Daily, weekly, or monthly open price and timestamp.

### SessionExtreme

Session high/low for current trading day.

### OpeningRange

Post-open price range with breakout direction.

### InitialBalance

Initial balance range with extension tracking.

### TimeOfDayFilter

Allow/block evaluation for downstream gating.

### CalendarContext

Weekend, holiday, DST, and trading period identifiers.

### MarketSessionsState

Serializable continuity state for incremental analysis.

---

## Configuration Loader

### `load_market_sessions_config(settings_path: Path | None = None) -> MarketSessionsConfig`

| | |
|---|---|
| **Source** | `config/settings.yaml` → `market_sessions` section |
| **Fallback** | Pydantic model defaults |
| **Returns** | Validated `MarketSessionsConfig` |
| **Raises** | `ConfigInvalidError` on unrecoverable misconfiguration |

---

## Event Publisher

### MarketSessionsEventPublisher

```python
class MarketSessionsEventPublisher:
    def publish(self, event: MarketSessionsAnalysisEvent) -> None: ...
    def subscribe(self, handler: Callable[[MarketSessionsAnalysisEvent], None]) -> None: ...
    def unsubscribe(self, handler: Callable[[MarketSessionsAnalysisEvent], None]) -> None: ...
    def clear(self) -> None: ...
    @property
    def events(self) -> list[MarketSessionsAnalysisEvent]: ...
```

Consistent with Sprints 1–8 in-memory pub/sub pattern.

---

## Exception Hierarchy (Planned)

```python
class MarketSessionsError(Exception): ...

class InsufficientDataError(MarketSessionsError):
    code = "MS_INSUFFICIENT_DATA"

class ValidationError(MarketSessionsError):
    code = "MS_VALIDATION_FAILED"

class InvalidTimestampError(MarketSessionsError):
    code = "MS_INVALID_TIMESTAMP"

class InvalidTimezoneError(MarketSessionsError):
    code = "MS_INVALID_TIMEZONE"

class UnsupportedTimeframeError(MarketSessionsError):
    code = "MS_TIMEFRAME_UNSUPPORTED"

class InvalidStructureError(MarketSessionsError):
    code = "MS_INVALID_STRUCTURE"

class InvalidLiquidityStateError(MarketSessionsError):
    code = "MS_INVALID_LIQUIDITY_STATE"

class InvalidPremiumDiscountError(MarketSessionsError):
    code = "MS_INVALID_PREMIUM_DISCOUNT"

class ConfigInvalidError(MarketSessionsError):
    code = "MS_CONFIG_INVALID"

class StateCorruptError(MarketSessionsError):
    code = "MS_STATE_CORRUPT"
```

---

## Public Exports (`__all__`) — Planned

```python
__all__ = [
    # Engine
    "MarketSessionsEngine",
    "MarketSessionsDetector",
    "MarketSessionsInputValidator",
    "MarketSessionsEventPublisher",
    # Config
    "MarketSessionsConfig",
    "load_market_sessions_config",
    # Primary output
    "SessionAnalysis",
    "MarketSessionsState",
    # Session entities
    "TradingSessionState",
    "KillZoneState",
    "SessionOverlap",
    "SessionTransition",
    "PeriodOpen",
    "SessionExtreme",
    "OpeningRange",
    "InitialBalance",
    "TimeOfDayFilter",
    "CalendarContext",
    # Enums
    "TradingSessionId",
    "KillZoneId",
    "SessionPhase",
    "TransitionType",
    "MarketAvailability",
    "VolatilityProfile",
    "LiquidityAvailability",
    "SessionQualityTier",
    "FilterMode",
    "PeriodType",
    "BreakoutDirection",
    "MarketSessionsEventKind",
    # Events
    "MarketSessionsAnalysisEvent",
    # Exceptions
    "MarketSessionsError",
    "InsufficientDataError",
    "ValidationError",
    "InvalidTimestampError",
    "InvalidTimezoneError",
    "UnsupportedTimeframeError",
    "InvalidStructureError",
    "InvalidLiquidityStateError",
    "InvalidPremiumDiscountError",
    "ConfigInvalidError",
    "StateCorruptError",
]
```

---

## REST API (Future — Not Sprint 9.1)

Planned FastAPI endpoint for dashboard consumption:

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/api/v1/analysis/session` | Latest `SessionAnalysis` JSON |
| `GET` | `/api/v1/analysis/session/kill-zones` | Active kill zones only |
| `GET` | `/api/v1/analysis/session/calendar` | `CalendarContext` |

Not implemented in Sprint 9.1 or 9.2 unless explicitly scoped by Product Owner.

---

## Type Signatures (Planned — schemas.py)

```python
class SessionAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    timestamp_utc: datetime
    broker_timezone: str
    market_availability: MarketAvailability
    active_sessions: list[TradingSessionState]
    primary_session: TradingSessionId | None
    session_phase: SessionPhase
    kill_zones: list[KillZoneState]
    active_kill_zones: list[KillZoneState]
    overlaps: list[SessionOverlap]
    next_transition: SessionTransition | None
    recent_transitions: list[SessionTransition]
    daily_open: PeriodOpen | None
    weekly_open: PeriodOpen | None
    monthly_open: PeriodOpen | None
    session_extremes: list[SessionExtreme]
    opening_range: OpeningRange | None
    initial_balance: InitialBalance | None
    time_of_day_filter: TimeOfDayFilter
    calendar_context: CalendarContext
    volatility_profile: VolatilityProfile
    liquidity_availability: LiquidityAvailability
    quality: SessionQualityTier
    confidence: Decimal
    strength: Decimal
    evidence: list[str]
    state: MarketSessionsState
    events: list[MarketSessionsEvent]
```

---

## Integration with Decision Engine

The Decision Engine consumes `SessionAnalysis` via:

1. **Direct call** — orchestrator passes `session_analysis` to `DecisionEngine.decide(...)`
2. **Event bus** — subscribe to `analysis.session.completed`

Recommended gating:

```
if not session_analysis.time_of_day_filter.is_allowed:
    blocking_reasons.append("Outside configured session/kill zone window")
```

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |

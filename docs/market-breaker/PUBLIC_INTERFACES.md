# Breaker Block Engine — Public Interfaces

**Engine ID:** `market_breaker`  
**Sprint:** 6.1 (Architecture specification)  
**Planned Module:** `backend.engines.market_breaker`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_breaker.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_breaker import (
    BreakerBlockEngine,
    BreakerBlockAnalysis,
    BreakerBlock,
    BreakerBlockState,
    BreakerBlockConfig,
    load_market_breaker_config,
    BreakerBlockEventPublisher,
    # ... see __all__
)
```

---

## BreakerBlockEngine

**Purpose:** Public orchestrator for breaker block detection, confirmation, and lifecycle management.

### Constructor

```python
BreakerBlockEngine(
    config: BreakerBlockConfig | None = None,
    detector: BreakerBlockDetector | None = None,
    validator: BreakerBlockInputValidator | None = None,
    publisher: BreakerBlockEventPublisher | None = None,
)
```

Dependency injection follows Sprints 1–5 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `BreakerBlockConfig` | Active configuration |
| `publisher` | `BreakerBlockEventPublisher` | Event publisher instance |
| `prior_state` | `BreakerBlockState \| None` | Persisted continuity state |

### Primary Method

#### `analyze(candles, structure=None, invalidated_order_blocks=None, liquidity_state=None, fair_value_gap_state=None, *, timeframe=None, prior_state=None, invalidated_fvgs=None) -> BreakerBlockAnalysis`

| | |
|---|---|
| **Input** | `list[NormalizedCandle]` — closed candles preferred |
| | `MarketStructure \| None` — structure context |
| | `list[OrderBlock]` — invalidated order blocks from Order Block Engine |
| | `LiquidityState \| None` — liquidity continuity state |
| | `FairValueGapState \| None` — FVG continuity state |
| | `list[FairValueGap] \| None` — invalidated FVGs for optional FVG-derived breakers |
| **Output** | `BreakerBlockAnalysis` |
| **Raises** | `InsufficientDataError`, `ValidationError`, `UnsupportedTimeframeError`, `InvalidStructureError`, `InvalidLiquidityStateError`, `InvalidOrderBlocksError`, `InvalidFVGStateError` |
| **Events** | All breaker lifecycle events via publisher |

### Detection Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `detect_bullish_breakers(candles, invalidated_order_blocks, structure)` | Candles + invalidated blocks + optional structure | `list[BreakerBlock]` | Bullish breakers only |
| `detect_bearish_breakers(candles, invalidated_order_blocks, structure)` | Candles + invalidated blocks + optional structure | `list[BreakerBlock]` | Bearish breakers only |
| `classify_lifecycle(breakers, candles)` | Existing breakers + candles | `list[BreakerBlock]` | Update candidate/confirmed/mitigated/invalidated/expired |
| `validate_confirmation(breaker, candles)` | Breaker + candles | `bool` | Check confirmation rules |
| `score_confluence(breaker, liquidity_state, fvg_state)` | Breaker + optional states | `BreakerBlock` | Enriched confluence fields |
| `publish_events(analysis)` | `BreakerBlockAnalysis` | `None` | Emit all lifecycle events |

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
| Minimum count | `>= config.min_candles` closed candles |
| Ordering | Chronological by `open_time_utc` |
| Scope | Single `symbol` and single `timeframe` per call |
| Integrity | Valid OHLC relationships; no duplicate timestamps |

### MarketStructure (Sprint 2 — Recommended)

Imported from `backend.engines.market_structure`.

| Requirement | Rule |
|-------------|------|
| Symbol/timeframe | Must match candle batch when provided |
| Usage | Premium/discount, structure alignment, BOS confluence |
| Fallback | Analysis proceeds without structure; confidence reduced |

### LiquidityState (Sprint 3 — Optional)

Imported from `backend.engines.market_liquidity`.

| Field | Usage |
|-------|-------|
| `active_zones` | Zone overlap confluence scoring |
| `recent_sweeps` | Post-sweep breaker confluence |
| `bar_count` | Consistency validation |

**Not consumed:** `LiquidityAnalysis` envelope fields. Callers pass `LiquidityState` only.

### OrderBlock (Sprint 4 — Required)

Imported from `backend.engines.market_order_block`.

| Requirement | Rule |
|-------------|------|
| Status filter | All blocks must have `status == invalidated` |
| Scope | Symbol/timeframe consistent with candle batch |
| Extraction | Caller provides `OrderBlockAnalysis.invalidated_blocks` |

**Not consumed:** `OrderBlockAnalysis` envelope fields (bias, confidence, partitioned lists, etc.).

### FairValueGapState (Sprint 5 — Optional)

Imported from `backend.engines.market_fvg`.

| Field | Usage |
|-------|-------|
| `active_gaps` | FVG overlap confluence scoring |
| `bar_count` | Consistency validation |

### FairValueGap (Sprint 5 — Optional)

Imported from `backend.engines.market_fvg`.

| Requirement | Rule |
|-------------|------|
| Status filter | Only `status == invalidated` when used for formation |
| Extraction | Caller provides `FairValueGapAnalysis.invalidated_gaps` |
| Enablement | Only when `config.fvg_breaker_enabled == true` |

### BreakerBlockState (Internal — Optional)

Prior continuity state from previous `analyze()` invocation.

| Field | Usage |
|-------|-------|
| `active_breakers` | Merge with newly formed candidates |
| `bar_count` | Increment on each cycle |
| `last_analysis_utc` | Audit trail |

---

## Output Contracts

### BreakerBlockAnalysis

Primary analysis envelope. See [ARCHITECTURE.md](./ARCHITECTURE.md) for full field list.

| Partition | Filter |
|-----------|--------|
| `candidate_breakers` | `status == candidate` |
| `confirmed_breakers` | `status == confirmed` |
| `mitigated_breakers` | `status == mitigated` |
| `invalidated_breakers` | `status == invalidated` |
| `expired_breakers` | `status == expired` |
| `bullish_breakers` | `direction == bullish` |
| `bearish_breakers` | `direction == bearish` |

### BreakerBlock

Individual breaker entity. Frozen Pydantic model.

**Guaranteed fields on every emitted breaker:**

- `breaker_id`, `direction`, `status`
- `high`, `low`
- `source_type`, `source_id`, `source_direction`
- `invalidation_bar_index`, `invalidation_time_utc`
- `formation_bar_index`, `formation_time_utc`
- `is_confirmed`, `confirmation_reason`
- `quality`, `strength`, `evidence`

**Nullable fields when not applicable:**

- `confirmation_bar_index`, `confirmation_time_utc`
- `mitigation_bar_index`, `invalidation_breaker_bar_index`, `expiration_bar_index`
- `liquidity_confluence_ids`, `fvg_confluence_ids`
- `dealing_range_high`, `dealing_range_low`

### BreakerBlockState

Serializable continuity state for cross-invocation tracking.

```python
{
    "active_breakers": [...],   # candidate and confirmed only
    "last_analysis_utc": "...",
    "bar_count": 482
}
```

---

## Schemas

### BreakerBlockDirection (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Failed supply zone now acting as demand support |
| `bearish` | Failed demand zone now acting as supply resistance |

### BreakerBlockStatus (Enum)

| Value | Description |
|-------|-------------|
| `candidate` | Awaiting retest confirmation |
| `confirmed` | Polarity flip validated |
| `mitigated` | Zone addressed per mitigation rules |
| `invalidated` | Breaker role negated |
| `expired` | Age limit exceeded |

### BreakerBlockQuality (Enum)

| Value | Description |
|-------|-------------|
| `high` | Strong invalidation + confirmation + confluence |
| `medium` | Meets minimum criteria |
| `low` | Marginal — low confidence |

### BreakerBlockBias (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Dominant confirmed bullish breakers |
| `bearish` | Dominant confirmed bearish breakers |
| `neutral` | Balanced or no active confirmed breakers |
| `undetermined` | Insufficient data |

### BreakerSourceType (Enum)

| Value | Description |
|-------|-------------|
| `order_block` | Derived from invalidated order block |
| `fair_value_gap` | Derived from invalidated fair value gap |

### BreakerBlockEventKind (Enum)

| Value | Description |
|-------|-------------|
| `BreakerBlockDetected` | New breaker identified |
| `BullishBreakerBlockDetected` | New bullish breaker |
| `BearishBreakerBlockDetected` | New bearish breaker |
| `CandidateBreakerBlock` | Registered as candidate |
| `ConfirmedBreakerBlock` | Confirmation validated |
| `MitigatedBreakerBlock` | Breaker mitigated |
| `InvalidatedBreakerBlock` | Breaker invalidated |
| `ExpiredBreakerBlock` | Breaker expired |
| `LiquidityConfluenceBreaker` | Liquidity confluence detected |
| `FVGConfluenceBreaker` | FVG confluence detected |
| `BreakerBlockUpdated` | Full analysis complete |

### BreakerBlockEvent

| Field | Type |
|-------|------|
| `kind` | `BreakerBlockEventKind` |
| `timestamp_utc` | `datetime` |
| `timeframe` | `str` |
| `description` | `str` |
| `breaker_id` | `str \| None` |
| `direction` | `BreakerBlockDirection \| None` |
| `status` | `BreakerBlockStatus \| None` |
| `price` | `Decimal \| None` |
| `source_id` | `str \| None` |

---

## Internal Interfaces (Not Public)

These classes are module-internal in Sprint 6.2; documented here for architecture completeness.

### BreakerBlockDetector

| Method | Description |
|--------|-------------|
| `detect(...)` | Full detection pipeline orchestration |

### FormationDetector

| Method | Description |
|--------|-------------|
| `derive_from_order_blocks(blocks)` | Map invalidated OBs to breaker candidates |
| `derive_from_fvgs(gaps)` | Map invalidated FVGs to breaker candidates (optional) |

### ConfirmationValidator

| Method | Description |
|--------|-------------|
| `validate(candidate, candles)` | Evaluate confirmation rules |
| `compute_reason(candidate, candles)` | Human-readable confirmation explanation |

### LifecycleManager

| Method | Description |
|--------|-------------|
| `update_status(breaker, candles)` | Apply lifecycle transitions |

### MitigationTracker

| Method | Description |
|--------|-------------|
| `detect_mitigation(breaker, candles)` | Check mitigation triggers |

### ConfluenceScorer

| Method | Description |
|--------|-------------|
| `score_liquidity(breaker, liquidity_state)` | Liquidity overlap and sweep proximity |
| `score_fvg(breaker, fvg_state)` | FVG overlap and CE proximity |

### QualityScorer

| Method | Description |
|--------|-------------|
| `score(breaker, structure, liquidity_state, fvg_state)` | Composite 0.0–1.0 strength |

### BreakerCandidate (Internal)

| Field | Type | Description |
|-------|------|-------------|
| `source_type` | `BreakerSourceType` | Origin entity type |
| `source_id` | `str` | Origin block/gap ID |
| `source_direction` | `str` | Pre-flip direction |
| `direction` | `BreakerBlockDirection` | Post-flip direction |
| `high`, `low` | `Decimal` | Zone bounds |
| `invalidation_bar_index` | `int` | Source invalidation bar |

---

## BreakerBlockEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | Register handler (`"*"` for all) |
| `publish_breaker_detected(breaker, symbol)` | `BreakerBlockDetected` |
| `publish_bullish_breaker(breaker, symbol)` | `BullishBreakerBlockDetected` |
| `publish_bearish_breaker(breaker, symbol)` | `BearishBreakerBlockDetected` |
| `publish_candidate_breaker(breaker, symbol)` | `CandidateBreakerBlock` |
| `publish_confirmed_breaker(breaker, symbol)` | `ConfirmedBreakerBlock` |
| `publish_mitigated_breaker(breaker, symbol)` | `MitigatedBreakerBlock` |
| `publish_invalidated_breaker(breaker, symbol)` | `InvalidatedBreakerBlock` |
| `publish_expired_breaker(breaker, symbol)` | `ExpiredBreakerBlock` |
| `publish_liquidity_confluence(breaker, symbol)` | `LiquidityConfluenceBreaker` |
| `publish_fvg_confluence(breaker, symbol)` | `FVGConfluenceBreaker` |
| `publish_analysis_completed(analysis)` | `BreakerBlockUpdated` / `analysis.breaker.completed` |

---

## Exceptions

All inherit from `BreakerBlockError` → `CanonTradingError`.

| Exception | Code | When |
|-----------|------|------|
| `BreakerBlockError` | `MBE_ERROR` | Base error |
| `InsufficientDataError` | `MBE_INSUFFICIENT_DATA` | Not enough candles |
| `ValidationError` | `MBE_VALIDATION_FAILED` | Invalid candle batch |
| `InvalidStructureError` | `MBE_INVALID_STRUCTURE` | Bad structure context |
| `InvalidLiquidityStateError` | `MBE_INVALID_LIQUIDITY_STATE` | Bad liquidity state |
| `InvalidOrderBlocksError` | `MBE_INVALID_ORDER_BLOCKS` | Non-invalidated or mismatched blocks |
| `InvalidFVGStateError` | `MBE_INVALID_FVG_STATE` | Bad FVG state |
| `UnsupportedTimeframeError` | `MBE_TIMEFRAME_UNSUPPORTED` | Timeframe not configured |
| `DuplicateBreakerError` | `MBE_DUPLICATE_BREAKER` | Duplicate breaker ID in state |
| `StateCorruptError` | `MBE_STATE_CORRUPT` | Unrecoverable prior state |

---

## Configuration Functions

### `load_market_breaker_config(yaml_path=None) -> BreakerBlockConfig`

Loads from `config/settings.yaml` → `market_breaker` section with `engines.market_breaker` toggle.

---

## Planned `__all__` Export List

```python
__all__ = [
    # Engine
    "BreakerBlockEngine",
    # Schemas
    "BreakerBlockAnalysis",
    "BreakerBlock",
    "BreakerBlockState",
    "BreakerBlockEvent",
    "BreakerBlockDirection",
    "BreakerBlockStatus",
    "BreakerBlockQuality",
    "BreakerBlockBias",
    "BreakerSourceType",
    "BreakerBlockEventKind",
    # Config
    "BreakerBlockConfig",
    "load_market_breaker_config",
    # Events
    "BreakerBlockEventPublisher",
    "BreakerBlockAnalysisEvent",
    # Exceptions
    "BreakerBlockError",
    "InsufficientDataError",
    "ValidationError",
    "InvalidStructureError",
    "InvalidLiquidityStateError",
    "InvalidOrderBlocksError",
    "InvalidFVGStateError",
    "UnsupportedTimeframeError",
    "DuplicateBreakerError",
    "StateCorruptError",
]
```

---

## Boundary Rules

| Rule | Enforcement |
|------|-------------|
| Import `NormalizedCandle` from `market_data` public API only | Required |
| Import `MarketStructure` from `market_structure` public API only | Required |
| Import `LiquidityState` from `market_liquidity` public API only | Required |
| Import `OrderBlock` from `market_order_block` public API only | Required |
| Import `FairValueGap`, `FairValueGapState`, `PremiumDiscountZone` from `market_fvg` public API only | Required |
| No imports from Decision, Risk, Notification engines | Required |
| No modification of Sprint 1–5 public interfaces | Required |
| No trade signal fields in output schemas | Required |
| No full analysis envelope imports from upstream engines | Required |

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
- [EVENTS.md](./EVENTS.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)

# Mitigation Block Engine — Public Interfaces

**Engine ID:** `market_mitigation`  
**Sprint:** 7.1 (Architecture specification)  
**Planned Module:** `backend/engines/market_mitigation`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_mitigation.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_mitigation import (
    MitigationBlockEngine,
    MitigationBlockAnalysis,
    MitigationBlock,
    MitigationBlockState,
    MitigationBlockConfig,
    load_market_mitigation_config,
    MitigationBlockEventPublisher,
    # ... see __all__
)
```

---

## MitigationBlockEngine

**Purpose:** Public orchestrator for mitigation block detection, touch tracking, confirmation, and lifecycle management.

### Constructor

```python
MitigationBlockEngine(
    config: MitigationBlockConfig | None = None,
    detector: MitigationBlockDetector | None = None,
    validator: MitigationBlockInputValidator | None = None,
    publisher: MitigationBlockEventPublisher | None = None,
)
```

Dependency injection follows Sprints 1–6 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `MitigationBlockConfig` | Active configuration |
| `publisher` | `MitigationBlockEventPublisher` | Event publisher instance |
| `prior_state` | `MitigationBlockState \| None` | Persisted continuity state |

### Primary Method

#### `analyze(candles, structure=None, order_blocks=None, liquidity_state=None, fair_value_gap_state=None, breaker_blocks=None, *, timeframe=None, prior_state=None, htf_mitigation_blocks=None) -> MitigationBlockAnalysis`

| | |
|---|---|
| **Input** | `list[NormalizedCandle]` — closed candles preferred |
| | `MarketStructure \| None` — structure context |
| | `list[OrderBlock] \| None` — order blocks from Order Block Engine |
| | `LiquidityState \| None` — liquidity continuity state |
| | `FairValueGapState \| None` — FVG continuity state |
| | `list[BreakerBlock] \| None` — breaker blocks from Breaker Block Engine |
| | `list[MitigationBlock] \| None` — HTF mitigation blocks for alignment |
| **Output** | `MitigationBlockAnalysis` |
| **Raises** | `InsufficientDataError`, `ValidationError`, `UnsupportedTimeframeError`, `InvalidStructureError`, `InvalidLiquidityStateError`, `InvalidOrderBlocksError`, `InvalidFVGStateError`, `InvalidBreakerBlocksError`, `InvalidHTFBlocksError` |
| **Events** | All mitigation lifecycle events via publisher |

### Detection Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `detect_bullish_blocks(candles, structure)` | Candles + optional structure | `list[MitigationBlock]` | Bullish mitigation blocks only |
| `detect_bearish_blocks(candles, structure)` | Candles + optional structure | `list[MitigationBlock]` | Bearish mitigation blocks only |
| `classify_lifecycle(blocks, candles)` | Existing blocks + candles | `list[MitigationBlock]` | Update fresh/partial/confirmed/used/invalidated/expired |
| `track_touches(block, candles)` | Block + candles | `MitigationBlock` | Update touch count and mitigation percent |
| `validate_confirmation(block, candles)` | Block + candles | `bool` | Check confirmation rules |
| `score_confluence(block, liquidity_state, order_blocks, fvg_state, breaker_blocks)` | Block + optional upstream | `MitigationBlock` | Enriched confluence fields |
| `classify_nesting(block, zones)` | Block + upstream zones | `MitigationBlock` | Nested relationship fields |
| `publish_events(analysis)` | `MitigationBlockAnalysis` | `None` | Emit all lifecycle events |

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
| Usage | Premium/discount, structure alignment, internal/external scope, BOS context |
| Fallback | Analysis proceeds without structure; confidence reduced |

### LiquidityState (Sprint 3 — Optional)

Imported from `backend.engines.market_liquidity`.

| Field | Usage |
|-------|-------|
| `active_zones` | Zone overlap confluence scoring |
| `recent_sweeps` | Post-sweep mitigation confluence |
| `bar_count` | Consistency validation |

**Not consumed:** `LiquidityAnalysis` envelope fields. Callers pass `LiquidityState` only.

### OrderBlock (Sprint 4 — Recommended)

Imported from `backend.engines.market_order_block`.

| Requirement | Rule |
|-------------|------|
| Scope | Symbol/timeframe consistent with candle batch |
| Extraction | Caller provides `OrderBlockAnalysis.order_blocks` or partitioned lists |
| Status | All statuses accepted; `fresh` preferred for confluence scoring |

**Not consumed:** `OrderBlockAnalysis` envelope fields (bias, confidence, etc.).

### FairValueGapState (Sprint 5 — Optional)

Imported from `backend.engines.market_fvg`.

| Field | Usage |
|-------|-------|
| `active_gaps` | FVG overlap confluence scoring |
| `bar_count` | Consistency validation |

**Not consumed:** `FairValueGapAnalysis` envelope fields.

### BreakerBlock (Sprint 6 — Optional)

Imported from `backend.engines.market_breaker`.

| Requirement | Rule |
|-------------|------|
| Scope | Symbol/timeframe consistent with candle batch |
| Extraction | Caller provides `BreakerBlockAnalysis.breaker_blocks` or confirmed partition |
| Status | `confirmed` and `candidate` preferred for confluence |

**Not consumed:** `BreakerBlockAnalysis` envelope fields.

### MitigationBlock (HTF Context — Optional)

Prior higher-timeframe mitigation blocks from caller.

| Requirement | Rule |
|-------------|------|
| Direction | Valid `MitigationBlockDirection` |
| Bounds | `high >= low` |
| Status | Prefer `fresh`, `partial`, `confirmed` |
| Timeframe | Must differ from current analysis timeframe |

### MitigationBlockState (Internal — Optional)

Prior continuity state from previous `analyze()` invocation.

| Field | Usage |
|-------|-------|
| `active_blocks` | Merge with newly formed blocks |
| `bar_count` | Increment on each cycle |
| `last_analysis_utc` | Audit trail |

---

## Output Contracts

### MitigationBlockAnalysis

Primary analysis envelope. See [ARCHITECTURE.md](./ARCHITECTURE.md) for full field list.

| Partition | Filter |
|-----------|--------|
| `fresh_blocks` | `status == fresh` |
| `partial_blocks` | `status == partial` |
| `confirmed_blocks` | `status == confirmed` |
| `used_blocks` | `status == used` |
| `invalidated_blocks` | `status == invalidated` |
| `expired_blocks` | `status == expired` |
| `bullish_blocks` | `direction == bullish` |
| `bearish_blocks` | `direction == bearish` |
| `nested_blocks` | `is_nested == true` |
| `internal_blocks` | `structure_scope == internal` |
| `external_blocks` | `structure_scope == external` |
| `htf_aligned_blocks` | `htf_aligned == true` |

### MitigationBlock

Individual mitigation block entity. Frozen Pydantic model.

**Guaranteed fields on every emitted block:**

- `block_id`, `direction`, `status`
- `high`, `low`
- `origin_bar_index`, `origin_time_utc`
- `displacement_bar_index`, `displacement_time_utc`
- `formation_bar_index`, `formation_time_utc`
- `mitigation_percent`, `touch_count`
- `is_confirmed`, `confirmation_reason`
- `structure_scope`, `structure_alignment`
- `quality`, `strength`, `evidence`

**Nullable fields when not applicable:**

- `first_touch_bar_index`, `last_touch_bar_index`
- `confirmation_bar_index`, `confirmation_time_utc`
- `used_bar_index`, `invalidation_bar_index`, `expiration_bar_index`
- `parent_zone_id`, `parent_zone_type`
- `child_block_ids`, `htf_block_ids`, `ltf_block_ids`, `confluence_ids`
- `dealing_range_high`, `dealing_range_low`

### MitigationBlockState

Serializable continuity state for cross-invocation tracking.

```python
{
    "active_blocks": [...],   # fresh, partial, and confirmed only
    "last_analysis_utc": "...",
    "bar_count": 482
}
```

---

## Schemas

### MitigationBlockDirection (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Last bearish candle before bullish displacement |
| `bearish` | Last bullish candle before bearish displacement |

### MitigationBlockStatus (Enum)

| Value | Description |
|-------|-------------|
| `fresh` | No price interaction |
| `partial` | Partially mitigated |
| `confirmed` | Mitigation confirmed |
| `used` | Fully consumed |
| `invalidated` | Zone failed |
| `expired` | Age limit exceeded |

### MitigationBlockQuality (Enum)

| Value | Description |
|-------|-------------|
| `high` | Strong displacement + confluence + confirmation |
| `medium` | Meets minimum criteria |
| `low` | Marginal — low confidence |

### MitigationBlockBias (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Dominant confirmed bullish blocks |
| `bearish` | Dominant confirmed bearish blocks |
| `neutral` | Balanced or no active confirmed blocks |
| `undetermined` | Insufficient data |

### StructureScope (Enum)

| Value | Description |
|-------|-------------|
| `internal` | Within internal structure range |
| `external` | Within external structure range |
| `undetermined` | Structure unavailable |

### MitigationSourceType (Enum)

| Value | Description |
|-------|-------------|
| `displacement` | Standalone displacement-derived |
| `order_block` | Nested within or derived from OB |
| `fair_value_gap` | Nested within or derived from FVG |
| `breaker_block` | Nested within or derived from breaker |
| `mitigation_block` | Nested within another MB |

### MitigationBlockEventKind (Enum)

| Value | Description |
|-------|-------------|
| `MitigationBlockDetected` | New block identified |
| `BullishMitigationBlockDetected` | New bullish block |
| `BearishMitigationBlockDetected` | New bearish block |
| `FreshMitigationBlock` | Registered as fresh |
| `PartialMitigationBlock` | Partial mitigation detected |
| `FullMitigationBlock` | Full mitigation detected |
| `MultiTouchMitigationBlock` | Additional touch recorded |
| `ConfirmedMitigationBlock` | Mitigation confirmed |
| `UsedMitigationBlock` | Zone fully consumed |
| `InvalidatedMitigationBlock` | Block invalidated |
| `ExpiredMitigationBlock` | Block expired |
| `NestedMitigationBlock` | Nested relationship detected |
| `InternalMitigationBlock` | Internal scope classified |
| `ExternalMitigationBlock` | External scope classified |
| `HTFMitigationAligned` | HTF alignment detected |
| `LTFMitigationNested` | LTF nesting detected |
| `LiquidityConfluenceMitigation` | Liquidity confluence |
| `OrderBlockConfluenceMitigation` | OB confluence |
| `FVGConfluenceMitigation` | FVG confluence |
| `BreakerConfluenceMitigation` | Breaker confluence |
| `MitigationBlockUpdated` | Full analysis complete |

### MitigationBlockEvent

| Field | Type |
|-------|------|
| `kind` | `MitigationBlockEventKind` |
| `timestamp_utc` | `datetime` |
| `timeframe` | `str` |
| `description` | `str` |
| `block_id` | `str \| None` |
| `direction` | `MitigationBlockDirection \| None` |
| `status` | `MitigationBlockStatus \| None` |
| `price` | `Decimal \| None` |
| `touch_count` | `int \| None` |
| `mitigation_percent` | `Decimal \| None` |
| `parent_zone_id` | `str \| None` |

### MitigationTouch (Internal)

| Field | Type |
|-------|------|
| `bar_index` | `int` |
| `timestamp_utc` | `datetime` |
| `touch_price` | `Decimal` |
| `touch_mode` | `str` |
| `mitigation_percent_after` | `Decimal` |

### MTFMitigationAlignment

| Field | Type |
|-------|------|
| `aligned_timeframes` | `list[str]` |
| `alignment_direction` | `MitigationBlockDirection` |
| `alignment_score` | `Decimal` |
| `parent_timeframe` | `str` |
| `parent_block_id` | `str` |

---

## Internal Interfaces (Not Public)

These classes are module-internal in Sprint 7.2; documented here for architecture completeness.

### MitigationBlockDetector

| Method | Description |
|--------|-------------|
| `detect(...)` | Full detection pipeline orchestration |

### FormationDetector

| Method | Description |
|--------|-------------|
| `derive_from_displacement(candles, structure)` | Map displacement legs to block candidates |
| `derive_from_confluence(candles, zones)` | Map upstream zone overlap to nested candidates |

### TouchTracker

| Method | Description |
|--------|-------------|
| `record_touch(block, candle)` | Increment touch count and update percent |
| `compute_mitigation_percent(block, candle)` | Calculate cumulative traverse |

### ConfirmationValidator

| Method | Description |
|--------|-------------|
| `validate(block, candles)` | Evaluate confirmation rules |
| `compute_reason(block, candles)` | Human-readable confirmation explanation |

### LifecycleManager

| Method | Description |
|--------|-------------|
| `update_status(block, candles)` | Apply lifecycle transitions |

### NestingClassifier

| Method | Description |
|--------|-------------|
| `detect_nesting(block, zones)` | Parent-child relationship detection |

### StructureScopeClassifier

| Method | Description |
|--------|-------------|
| `classify(block, structure)` | Internal/external scope assignment |

### MTFAligner

| Method | Description |
|--------|-------------|
| `score_htf(block, htf_blocks)` | HTF overlap and direction scoring |
| `detect_ltf_nesting(block, ltf_blocks)` | LTF containment detection |

### ConfluenceScorer

| Method | Description |
|--------|-------------|
| `score_liquidity(block, liquidity_state)` | Liquidity overlap and sweep proximity |
| `score_order_blocks(block, order_blocks)` | OB overlap scoring |
| `score_fvg(block, fvg_state)` | FVG overlap and CE proximity |
| `score_breakers(block, breaker_blocks)` | Breaker overlap scoring |

### QualityScorer

| Method | Description |
|--------|-------------|
| `score(block, structure, confluence)` | Composite 0.0–1.0 strength |

### MitigationCandidate (Internal)

| Field | Type | Description |
|-------|------|-------------|
| `direction` | `MitigationBlockDirection` | Block direction |
| `high`, `low` | `Decimal` | Zone bounds |
| `origin_bar_index` | `int` | Opposing candle bar |
| `displacement_bar_index` | `int` | Displacement start bar |
| `source_type` | `MitigationSourceType` | Formation source |
| `parent_zone_id` | `str \| None` | Parent when nested |

---

## MitigationBlockEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | Register handler (`"*"` for all) |
| `publish_block_detected(block, symbol)` | `MitigationBlockDetected` |
| `publish_bullish_block(block, symbol)` | `BullishMitigationBlockDetected` |
| `publish_bearish_block(block, symbol)` | `BearishMitigationBlockDetected` |
| `publish_fresh_block(block, symbol)` | `FreshMitigationBlock` |
| `publish_partial_mitigation(block, symbol)` | `PartialMitigationBlock` |
| `publish_full_mitigation(block, symbol)` | `FullMitigationBlock` |
| `publish_multi_touch(block, symbol)` | `MultiTouchMitigationBlock` |
| `publish_confirmed(block, symbol)` | `ConfirmedMitigationBlock` |
| `publish_used(block, symbol)` | `UsedMitigationBlock` |
| `publish_invalidated(block, symbol)` | `InvalidatedMitigationBlock` |
| `publish_expired(block, symbol)` | `ExpiredMitigationBlock` |
| `publish_nested(block, symbol)` | `NestedMitigationBlock` |
| `publish_internal_scope(block, symbol)` | `InternalMitigationBlock` |
| `publish_external_scope(block, symbol)` | `ExternalMitigationBlock` |
| `publish_htf_aligned(block, symbol)` | `HTFMitigationAligned` |
| `publish_ltf_nested(block, symbol)` | `LTFMitigationNested` |
| `publish_liquidity_confluence(block, symbol)` | `LiquidityConfluenceMitigation` |
| `publish_ob_confluence(block, symbol)` | `OrderBlockConfluenceMitigation` |
| `publish_fvg_confluence(block, symbol)` | `FVGConfluenceMitigation` |
| `publish_breaker_confluence(block, symbol)` | `BreakerConfluenceMitigation` |
| `publish_analysis_completed(analysis)` | `MitigationBlockUpdated` / `analysis.mitigation.completed` |

---

## Exceptions

All inherit from `MitigationBlockError` → `CanonTradingError`.

| Exception | Code | When |
|-----------|------|------|
| `MitigationBlockError` | `MMBE_ERROR` | Base error |
| `InsufficientDataError` | `MMBE_INSUFFICIENT_DATA` | Not enough candles |
| `ValidationError` | `MMBE_VALIDATION_FAILED` | Invalid candle batch |
| `InvalidStructureError` | `MMBE_INVALID_STRUCTURE` | Bad structure context |
| `InvalidLiquidityStateError` | `MMBE_INVALID_LIQUIDITY_STATE` | Bad liquidity state |
| `InvalidOrderBlocksError` | `MMBE_INVALID_ORDER_BLOCKS` | Mismatched order blocks |
| `InvalidFVGStateError` | `MMBE_INVALID_FVG_STATE` | Bad FVG state |
| `InvalidBreakerBlocksError` | `MMBE_INVALID_BREAKER_BLOCKS` | Mismatched breaker blocks |
| `InvalidHTFBlocksError` | `MMBE_INVALID_HTF_BLOCKS` | Invalid HTF block input |
| `UnsupportedTimeframeError` | `MMBE_TIMEFRAME_UNSUPPORTED` | Timeframe not configured |
| `DuplicateBlockError` | `MMBE_DUPLICATE_BLOCK` | Duplicate block ID in state |
| `StateCorruptError` | `MMBE_STATE_CORRUPT` | Unrecoverable prior state |

---

## Configuration Functions

### `load_market_mitigation_config(yaml_path=None) -> MitigationBlockConfig`

Loads from `config/settings.yaml` → `market_mitigation` section with `engines.market_mitigation` toggle.

---

## Planned `__all__` Export List

```python
__all__ = [
    # Engine
    "MitigationBlockEngine",
    # Schemas
    "MitigationBlockAnalysis",
    "MitigationBlock",
    "MitigationBlockState",
    "MitigationBlockEvent",
    "MitigationTouch",
    "MTFMitigationAlignment",
    "MitigationBlockDirection",
    "MitigationBlockStatus",
    "MitigationBlockQuality",
    "MitigationBlockBias",
    "StructureScope",
    "MitigationSourceType",
    "MitigationBlockEventKind",
    # Config
    "MitigationBlockConfig",
    "load_market_mitigation_config",
    # Events
    "MitigationBlockEventPublisher",
    "MitigationBlockAnalysisEvent",
    # Exceptions
    "MitigationBlockError",
    "InsufficientDataError",
    "ValidationError",
    "InvalidStructureError",
    "InvalidLiquidityStateError",
    "InvalidOrderBlocksError",
    "InvalidFVGStateError",
    "InvalidBreakerBlocksError",
    "InvalidHTFBlocksError",
    "UnsupportedTimeframeError",
    "DuplicateBlockError",
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
| Import `FairValueGapState`, `PremiumDiscountZone` from `market_fvg` public API only | Required |
| Import `BreakerBlock` from `market_breaker` public API only | Required |
| No imports from Decision, Risk, Notification engines | Required |
| No modification of Sprint 1–6 public interfaces | Required |
| No trade signal fields in output schemas | Required |
| No full analysis envelope imports from upstream engines | Required |

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
- [EVENTS.md](./EVENTS.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)

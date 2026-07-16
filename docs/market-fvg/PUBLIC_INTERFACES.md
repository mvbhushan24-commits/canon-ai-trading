# Fair Value Gap Engine — Public Interfaces

**Engine ID:** `fair_value_gap`  
**Sprint:** 5.1 (Architecture specification)  
**Planned Module:** `backend.engines.market_fvg`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_fvg.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_fvg import (
    FairValueGapEngine,
    FairValueGapAnalysis,
    FairValueGap,
    FairValueGapState,
    FairValueGapConfig,
    load_fair_value_gap_config,
    FairValueGapEventPublisher,
    # ... see __all__
)
```

---

## FairValueGapEngine

**Purpose:** Public orchestrator for fair value gap detection and lifecycle management.

### Constructor

```python
FairValueGapEngine(
    config: FairValueGapConfig | None = None,
    detector: FairValueGapDetector | None = None,
    validator: FairValueGapInputValidator | None = None,
    publisher: FairValueGapEventPublisher | None = None,
)
```

Dependency injection follows Sprints 1–4 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `FairValueGapConfig` | Active configuration |
| `publisher` | `FairValueGapEventPublisher` | Event publisher instance |
| `prior_state` | `FairValueGapState \| None` | Persisted continuity state |

### Primary Method

#### `analyze(candles, structure=None, liquidity_state=None, order_block_state=None, *, timeframe=None, prior_state=None, higher_timeframe_gaps=None) -> FairValueGapAnalysis`

| | |
|---|---|
| **Input** | `list[NormalizedCandle]` — closed candles preferred |
| | `MarketStructure \| None` — structure context |
| | `LiquidityState \| None` — liquidity continuity state |
| | `OrderBlockState \| None` — order block continuity state |
| | `list[FairValueGap] \| None` — higher timeframe gaps for MTF alignment |
| **Output** | `FairValueGapAnalysis` |
| **Raises** | `InsufficientDataError`, `ValidationError`, `UnsupportedTimeframeError`, `InvalidStructureError`, `InvalidLiquidityStateError`, `InvalidOrderBlockStateError` |
| **Events** | All FVG lifecycle events via publisher |

### Detection Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `detect_bullish_gaps(candles, structure)` | Candles + optional structure | `list[FairValueGap]` | Bullish FVGs only |
| `detect_bearish_gaps(candles, structure)` | Candles + optional structure | `list[FairValueGap]` | Bearish FVGs only |
| `classify_lifecycle(gaps, candles)` | Existing gaps + candles | `list[FairValueGap]` | Update open/partial/filled/mitigated/invalidated/expired |
| `compute_fill_percent(gap, candles)` | Gap + candles | `Decimal` | Current fill percentage |
| `classify_premium_discount(gap, structure)` | Gap + structure | `PremiumDiscountZone` | Premium/discount/equilibrium |
| `resolve_nesting(gaps)` | All gaps | `list[FairValueGap]` | Parent-child nesting |
| `score_mtf_alignment(gap, higher_timeframe_gaps)` | Gap + HTF gaps | `MTFGapAlignment \| None` | MTF confluence |
| `publish_events(analysis)` | `FairValueGapAnalysis` | `None` | Emit all lifecycle events |

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
| `recent_sweeps` | Post-sweep formation confluence |
| `bar_count` | Consistency validation |

**Not consumed:** `LiquidityAnalysis` envelope fields (sweeps list, bias, confidence, etc.). Callers pass `LiquidityState` only.

### OrderBlockState (Sprint 4 — Optional)

Imported from `backend.engines.market_order_block`.

| Field | Usage |
|-------|-------|
| `active_blocks` | Block zone overlap confluence scoring |
| `last_analysis_utc` | Freshness validation |
| `bar_count` | Consistency validation |

**Not consumed:** `OrderBlockAnalysis` envelope fields (bias, confidence, partitioned lists, etc.). Callers pass `OrderBlockState` only.

### FairValueGapState (Internal — Optional)

Prior continuity state from previous `analyze()` invocation.

| Field | Usage |
|-------|-------|
| `active_gaps` | Merge with newly detected gaps |
| `bar_count` | Increment on each cycle |
| `last_analysis_utc` | Audit trail |

### higher_timeframe_gaps (MTF — Optional)

Pre-computed gaps from higher timeframe analysis. Not an upstream sprint type — produced by prior FVG engine calls.

---

## Output Contracts

### FairValueGapAnalysis

Primary analysis envelope. See [ARCHITECTURE.md](./ARCHITECTURE.md) for full field list.

| Partition | Filter |
|-----------|--------|
| `open_gaps` | `status == open` |
| `partial_gaps` | `status == partial` |
| `filled_gaps` | `status == filled` |
| `mitigated_gaps` | `status == mitigated` |
| `invalidated_gaps` | `status == invalidated` |
| `expired_gaps` | `status == expired` |
| `bullish_gaps` | `direction == bullish` |
| `bearish_gaps` | `direction == bearish` |

### FairValueGap

Individual gap entity. Frozen Pydantic model.

**Guaranteed fields on every emitted gap:**

- `gap_id`, `direction`, `status`
- `high`, `low`, `ce_price`
- `gap_size`, `gap_size_pips`, `fill_percent`
- `is_valid`, `origin_bar_index`, `origin_time_utc`
- `quality`, `strength`, `evidence`

**Nullable fields when not applicable:**

- `fill_bar_index`, `mitigation_bar_index`, `invalidation_bar_index`, `expiration_bar_index`
- `nested_parent_gap_id`, `mtf_alignment`
- `dealing_range_high`, `dealing_range_low`

### FairValueGapState

Serializable continuity state for cross-invocation tracking.

```python
{
    "active_gaps": [...],       # open and partial gaps only
    "last_analysis_utc": "...",
    "bar_count": 482
}
```

### Bias Contract

| Value | Condition |
|-------|-----------|
| `bullish` | Dominant open/partial bullish gaps with discount placement |
| `bearish` | Dominant open/partial bearish gaps with premium placement |
| `neutral` | Balanced gaps or no active gaps |
| `undetermined` | Insufficient data — valid success state per Constitution |

### Confidence Contract

- Range: `0.0` to `1.0` (Decimal)
- Derived from active gap count, average strength, and context availability
- No minimum confidence threshold enforced on output — downstream Decision Engine may apply gates

---

## Schemas

### FairValueGapDirection (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Bullish FVG — imbalance below impulse |
| `bearish` | Bearish FVG — imbalance above impulse |

### FairValueGapStatus (Enum)

| Value | Description |
|-------|-------------|
| `open` | Untested — price has not entered gap |
| `partial` | Price entered; not fully filled |
| `filled` | Gap fully traversed |
| `mitigated` | Imbalance addressed per config |
| `invalidated` | Gap broken in opposing direction |
| `expired` | Gap aged beyond limit |

### FairValueGapQuality (Enum)

| Value | Description |
|-------|-------------|
| `high` | Strong impulse + alignment + confluence |
| `medium` | Meets minimum criteria |
| `low` | Marginal — low confidence |

### FairValueGapBias (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Dominant bullish gap context |
| `bearish` | Dominant bearish gap context |
| `neutral` | Balanced or inactive |
| `undetermined` | Insufficient data |

### PremiumDiscountZone (Enum)

| Value | Description |
|-------|-------------|
| `premium` | Above dealing range equilibrium |
| `discount` | Below dealing range equilibrium |
| `equilibrium` | At or near equilibrium |

### FairValueGapEventKind (Enum)

| Value | Description |
|-------|-------------|
| `FairValueGapDetected` | New gap identified |
| `BullishFairValueGapDetected` | New bullish gap |
| `BearishFairValueGapDetected` | New bearish gap |
| `OpenFairValueGap` | Gap confirmed open |
| `PartialFillFairValueGap` | Partial fill detected |
| `FilledFairValueGap` | Full fill detected |
| `MitigatedFairValueGap` | Gap mitigated |
| `InvalidatedFairValueGap` | Gap invalidated |
| `ExpiredFairValueGap` | Gap expired |
| `CEEncroached` | CE level touched |
| `NestedFairValueGap` | Nesting resolved |
| `MTFAlignedFairValueGap` | MTF alignment confirmed |
| `FairValueGapUpdated` | Full analysis complete |

### MTFGapAlignment

| Field | Type |
|-------|------|
| `aligned_timeframes` | `list[str]` |
| `alignment_direction` | `FairValueGapDirection` |
| `alignment_score` | `Decimal` |
| `parent_timeframe` | `str` |
| `parent_gap_id` | `str` |

### FairValueGapEvent

| Field | Type |
|-------|------|
| `kind` | `FairValueGapEventKind` |
| `timestamp_utc` | `datetime` |
| `timeframe` | `str` |
| `description` | `str` |
| `gap_id` | `str \| None` |
| `direction` | `FairValueGapDirection \| None` |
| `status` | `FairValueGapStatus \| None` |
| `price` | `Decimal \| None` |
| `fill_percent` | `Decimal \| None` |

---

## FairValueGapEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | Register handler (`"*"` for all) |
| `publish_gap_detected(gap, symbol)` | `FairValueGapDetected` |
| `publish_bullish_gap(gap, symbol)` | `BullishFairValueGapDetected` |
| `publish_bearish_gap(gap, symbol)` | `BearishFairValueGapDetected` |
| `publish_open_gap(gap, symbol)` | `OpenFairValueGap` |
| `publish_partial_fill(gap, symbol)` | `PartialFillFairValueGap` |
| `publish_filled(gap, symbol)` | `FilledFairValueGap` |
| `publish_mitigated(gap, symbol)` | `MitigatedFairValueGap` |
| `publish_invalidated(gap, symbol)` | `InvalidatedFairValueGap` |
| `publish_expired(gap, symbol)` | `ExpiredFairValueGap` |
| `publish_ce_encroached(gap, symbol)` | `CEEncroached` |
| `publish_nested(gap, symbol)` | `NestedFairValueGap` |
| `publish_mtf_aligned(gap, symbol)` | `MTFAlignedFairValueGap` |
| `publish_analysis_completed(analysis)` | `FairValueGapUpdated` / `analysis.fvg.completed` |

---

## Exceptions

All inherit from `FairValueGapError` → `CanonTradingError`.

| Exception | Code | When |
|-----------|------|------|
| `FairValueGapError` | `FVE_ERROR` | Base error |
| `InsufficientDataError` | `FVE_INSUFFICIENT_DATA` | Not enough candles |
| `ValidationError` | `FVE_VALIDATION_FAILED` | Invalid candle batch |
| `InvalidStructureError` | `FVE_INVALID_STRUCTURE` | Bad structure context |
| `InvalidLiquidityStateError` | `FVE_INVALID_LIQUIDITY_STATE` | Bad liquidity state |
| `InvalidOrderBlockStateError` | `FVE_INVALID_ORDER_BLOCK_STATE` | Bad order block state |
| `UnsupportedTimeframeError` | `FVE_TIMEFRAME_UNSUPPORTED` | Timeframe not configured |
| `DuplicateGapError` | `FVE_DUPLICATE_GAP` | Duplicate gap ID in state |
| `StateCorruptError` | `FVE_STATE_CORRUPT` | Unrecoverable prior state |

---

## Configuration Functions

### `load_fair_value_gap_config(yaml_path=None) -> FairValueGapConfig`

Loads from `config/settings.yaml` → `fair_value_gap` section with `engines.fair_value_gap` toggle.

---

## Boundary Rules

| Rule | Enforcement |
|------|-------------|
| Import `NormalizedCandle` from `market_data` public API only | Required |
| Import `MarketStructure` from `market_structure` public API only | Required |
| Import `LiquidityState` from `market_liquidity` public API only | Required |
| Import `OrderBlockState` from `market_order_block` public API only | Required |
| Do **not** import `LiquidityAnalysis` or `OrderBlockAnalysis` | Required |
| No imports from Decision, Risk, Notification engines | Required |
| No modification of Sprint 1–4 public interfaces | Required |
| No trade signal fields in output schemas | Required |

---

## Planned `__all__` Exports

```python
__all__ = [
    # Engine
    "FairValueGapEngine",
    "FairValueGapDetector",
    "FairValueGapInputValidator",
    "FairValueGapEventPublisher",
    # Schemas
    "FairValueGapAnalysis",
    "FairValueGap",
    "FairValueGapState",
    "FairValueGapEvent",
    "MTFGapAlignment",
    # Enums
    "FairValueGapDirection",
    "FairValueGapStatus",
    "FairValueGapQuality",
    "FairValueGapBias",
    "PremiumDiscountZone",
    "FairValueGapEventKind",
    # Config
    "FairValueGapConfig",
    "load_fair_value_gap_config",
    # Exceptions
    "FairValueGapError",
    "InsufficientDataError",
    "ValidationError",
    "InvalidStructureError",
    "InvalidLiquidityStateError",
    "InvalidOrderBlockStateError",
    "UnsupportedTimeframeError",
    "DuplicateGapError",
    "StateCorruptError",
]
```

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
- [EVENTS.md](./EVENTS.md)
- [DATA_PIPELINE.md](./DATA_PIPELINE.md)

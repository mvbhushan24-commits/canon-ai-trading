# Premium / Discount Engine — Public Interfaces

**Engine ID:** `market_premium_discount`  
**Sprint:** 8.1 (Architecture specification)  
**Planned Module:** `backend/engines/market_premium_discount`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_premium_discount.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_premium_discount import (
    PremiumDiscountEngine,
    PremiumDiscountAnalysis,
    DealingRange,
    PremiumDiscountState,
    PremiumDiscountConfig,
    load_market_premium_discount_config,
    PremiumDiscountEventPublisher,
    PremiumDiscountZone,
    # ... see __all__
)
```

---

## PremiumDiscountEngine

**Purpose:** Public orchestrator for dealing range construction, premium/discount classification, array assembly, Fibonacci/OTE derivation, MTF alignment, and institutional pricing context.

### Constructor

```python
PremiumDiscountEngine(
    config: PremiumDiscountConfig | None = None,
    detector: PremiumDiscountDetector | None = None,
    validator: PremiumDiscountInputValidator | None = None,
    publisher: PremiumDiscountEventPublisher | None = None,
)
```

Dependency injection follows Sprints 1–7 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `PremiumDiscountConfig` | Active configuration |
| `publisher` | `PremiumDiscountEventPublisher` | Event publisher instance |
| `prior_state` | `PremiumDiscountState \| None` | Persisted continuity state |

### Primary Method

#### `analyze(candles, structure=None, liquidity_state=None, order_blocks=None, fair_value_gap_state=None, breaker_blocks=None, mitigation_blocks=None, *, timeframe=None, current_price=None, prior_state=None, htf_premium_discount_context=None) -> PremiumDiscountAnalysis`

| | |
|---|---|
| **Input** | `list[NormalizedCandle]` — closed candles preferred |
| | `MarketStructure \| None` — structure context |
| | `LiquidityState \| None` — liquidity continuity state |
| | `list[OrderBlock] \| None` — order blocks from Order Block Engine |
| | `FairValueGapState \| None` — FVG continuity state |
| | `list[BreakerBlock] \| None` — breaker blocks from Breaker Block Engine |
| | `list[MitigationBlock] \| None` — mitigation blocks from Mitigation Block Engine |
| | `PremiumDiscountContext \| None` — HTF context for MTF alignment |
| | `Decimal \| None` — current price override (defaults to latest close) |
| **Output** | `PremiumDiscountAnalysis` |
| **Raises** | `InsufficientDataError`, `ValidationError`, `UnsupportedTimeframeError`, `InvalidStructureError`, `InvalidLiquidityStateError`, `InvalidOrderBlocksError`, `InvalidFVGStateError`, `InvalidBreakerBlocksError`, `InvalidMitigationBlocksError`, `InvalidHTFContextError`, `StateCorruptError` |
| **Events** | All premium/discount lifecycle events via publisher |

### Analysis Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `build_dealing_range(structure, scope)` | Structure + scope | `DealingRange` | Construct dealing range for scope |
| `select_swing_anchors(structure, scope)` | Structure + scope | `tuple[SwingAnchor, SwingAnchor]` | Select swing high and low |
| `classify_price(price, dealing_range)` | Price + range | `PremiumDiscountZone` | Classify price location |
| `classify_zone(midpoint, dealing_range)` | Midpoint + range | `PremiumDiscountZone` | Classify zone territory |
| `assemble_premium_arrays(zones, dealing_range)` | Zones + range | `list[InstitutionalArray]` | Build premium arrays |
| `assemble_discount_arrays(zones, dealing_range)` | Zones + range | `list[InstitutionalArray]` | Build discount arrays |
| `project_fibonacci(dealing_range, direction)` | Range + direction | `FibonacciDealingRange` | Fibonacci level projection |
| `derive_ote(dealing_range, fibonacci, zones)` | Range + fib + zones | `OptimalTradeEntryZone \| None` | OTE zone derivation |
| `score_mtf_alignment(ltf_analysis, htf_context)` | LTF + HTF | `MTFPremiumDiscountAlignment \| None` | MTF alignment scoring |
| `build_institutional_context(analysis_parts)` | Sub-results | `InstitutionalPricingContext` | Composite context |
| `publish_events(analysis)` | `PremiumDiscountAnalysis` | `None` | Emit all lifecycle events |

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
| Usage | Swing anchors, dealing ranges, trend context, invalidation |
| Fallback | Analysis proceeds without structure; `bias: undetermined` |

| Field | Usage |
|-------|-------|
| `swing_highs`, `swing_lows` | Swing anchor selection |
| `internal_structure` | Internal dealing range |
| `external_structure` | External dealing range |
| `current_trend` | Bias weighting, Fib direction, institutional context |
| `bos_events`, `choch_events` | Range invalidation and quality |
| `confidence` | Range quality scoring |

### LiquidityState (Sprint 3 — Optional)

Imported from `backend.engines.market_liquidity`.

| Field | Usage |
|-------|-------|
| `active_zones` | Liquidity zone entries in arrays |
| `recent_sweeps` | Liquidity confirmation scoring |
| `bar_count` | Consistency validation |

**Not consumed:** `LiquidityAnalysis` envelope fields.

### OrderBlock (Sprint 4 — Optional)

Imported from `backend.engines.market_order_block`.

| Requirement | Rule |
|-------------|------|
| Scope | Symbol/timeframe consistent with candle batch |
| Extraction | Caller provides `OrderBlockAnalysis.order_blocks` |
| Status filter | Per `zone_filters.order_block_statuses` |

**Not consumed:** `OrderBlockAnalysis` envelope fields.

### FairValueGapState (Sprint 5 — Optional)

Imported from `backend.engines.market_fvg`.

| Field | Usage |
|-------|-------|
| `active_gaps` | FVG entries in arrays and OTE overlap |
| `bar_count` | Consistency validation |

**Not consumed:** `FairValueGapAnalysis` envelope fields.

**Note:** Sprint 8.1 defines the canonical `PremiumDiscountZone` enum in this engine. Upstream engines (Sprint 5–7) currently embed inline classification; a future consolidation sprint may align imports. Sprint 8.2 must not modify upstream public interfaces.

### BreakerBlock (Sprint 6 — Optional)

Imported from `backend.engines.market_breaker`.

| Requirement | Rule |
|-------------|------|
| Scope | Symbol/timeframe consistent with candle batch |
| Status filter | Per `zone_filters.breaker_statuses` |

**Not consumed:** `BreakerBlockAnalysis` envelope fields.

### MitigationBlock (Sprint 7 — Optional)

Imported from `backend.engines.market_mitigation`.

| Requirement | Rule |
|-------------|------|
| Scope | Symbol/timeframe consistent with candle batch |
| Status filter | Per `zone_filters.mitigation_statuses` |

**Not consumed:** `MitigationBlockAnalysis` envelope fields.

### PremiumDiscountContext (HTF — Optional)

Lightweight HTF summary type (defined in this engine's schemas):

| Field | Type | Description |
|-------|------|-------------|
| `timeframe` | `str` | HTF timeframe label |
| `dealing_range` | `DealingRange` | HTF dealing range |
| `price_location` | `PremiumDiscountZone` | HTF price territory |
| `premium_arrays` | `list[InstitutionalArray]` | HTF premium arrays |
| `discount_arrays` | `list[InstitutionalArray]` | HTF discount arrays |
| `equilibrium` | `Decimal` | HTF equilibrium price |

Caller may construct from a prior `PremiumDiscountAnalysis` on a higher timeframe.

---

## Output Schemas

### PremiumDiscountAnalysis

| Field | Type |
|-------|------|
| `symbol` | `str` |
| `timeframe` | `str` |
| `timestamp_utc` | `datetime` |
| `current_price` | `Decimal` |
| `dealing_range` | `DealingRange` |
| `external_range` | `DealingRange` |
| `internal_range` | `DealingRange` |
| `swing_high` | `SwingAnchor` |
| `swing_low` | `SwingAnchor` |
| `premium_zone` | `PriceZoneBand` |
| `discount_zone` | `PriceZoneBand` |
| `equilibrium` | `EquilibriumLevel` |
| `price_location` | `PremiumDiscountZone` |
| `premium_arrays` | `list[InstitutionalArray]` |
| `discount_arrays` | `list[InstitutionalArray]` |
| `internal_premium` | `PriceZoneBand \| None` |
| `internal_discount` | `PriceZoneBand \| None` |
| `htf_premium` | `HTFPricingContext \| None` |
| `htf_discount` | `HTFPricingContext \| None` |
| `mtf_premium_alignment` | `MTFPremiumDiscountAlignment \| None` |
| `mtf_discount_alignment` | `MTFPremiumDiscountAlignment \| None` |
| `nested_premium_zones` | `list[NestedZoneContext]` |
| `nested_discount_zones` | `list[NestedZoneContext]` |
| `fibonacci_range` | `FibonacciDealingRange` |
| `ote_zone` | `OptimalTradeEntryZone \| None` |
| `institutional_context` | `InstitutionalPricingContext` |
| `bias` | `PremiumDiscountBias` |
| `confidence` | `Decimal` |
| `quality` | `PremiumDiscountQuality` |
| `strength` | `Decimal` |
| `evidence` | `list[str]` |
| `state` | `PremiumDiscountState` |
| `events` | `list[PremiumDiscountEvent]` |

### DealingRange

| Field | Type |
|-------|------|
| `range_id` | `str` |
| `scope` | `DealingRangeScope` |
| `high` | `Decimal` |
| `low` | `Decimal` |
| `equilibrium` | `Decimal` |
| `range_size` | `Decimal` |
| `swing_high` | `SwingAnchor` |
| `swing_low` | `SwingAnchor` |
| `formation_bar_index` | `int` |
| `formation_time_utc` | `datetime` |
| `is_valid` | `bool` |
| `invalidation_reason` | `str \| None` |
| `quality` | `PremiumDiscountQuality` |
| `strength` | `Decimal` |
| `evidence` | `list[str]` |

### SwingAnchor

| Field | Type |
|-------|------|
| `price` | `Decimal` |
| `timestamp_utc` | `datetime` |
| `bar_index` | `int` |
| `kind` | `SwingKind` |
| `label` | `SwingLabel` |
| `quality_score` | `Decimal` |

### PriceZoneBand

| Field | Type |
|-------|------|
| `territory` | `PremiumDiscountZone` |
| `high` | `Decimal` |
| `low` | `Decimal` |
| `scope` | `DealingRangeScope` |

### EquilibriumLevel

| Field | Type |
|-------|------|
| `price` | `Decimal` |
| `tolerance_high` | `Decimal` |
| `tolerance_low` | `Decimal` |
| `scope` | `DealingRangeScope` |

### InstitutionalArray

| Field | Type |
|-------|------|
| `array_id` | `str` |
| `territory` | `PremiumDiscountZone` |
| `scope` | `DealingRangeScope` |
| `zone_entries` | `list[ArrayZoneEntry]` |
| `cluster_high` | `Decimal` |
| `cluster_low` | `Decimal` |
| `entry_count` | `int` |
| `dominant_direction` | `str \| None` |
| `confluence_score` | `Decimal` |
| `evidence` | `list[str]` |

### ArrayZoneEntry

| Field | Type |
|-------|------|
| `zone_id` | `str` |
| `zone_type` | `InstitutionalZoneType` |
| `high` | `Decimal` |
| `low` | `Decimal` |
| `midpoint` | `Decimal` |
| `direction` | `str \| None` |
| `status` | `str \| None` |
| `strength` | `Decimal` |
| `distance_from_equilibrium_pips` | `Decimal` |
| `placement_score` | `Decimal` |

### FibonacciDealingRange

| Field | Type |
|-------|------|
| `range_id` | `str` |
| `direction` | `FibDirection` |
| `levels` | `list[FibonacciLevel]` |
| `ote_low_level` | `Decimal` |
| `ote_high_level` | `Decimal` |
| `equilibrium_level` | `Decimal` |

### FibonacciLevel

| Field | Type |
|-------|------|
| `ratio` | `Decimal` |
| `price` | `Decimal` |
| `label` | `str` |

### OptimalTradeEntryZone

| Field | Type |
|-------|------|
| `ote_id` | `str` |
| `territory` | `PremiumDiscountZone` |
| `direction` | `FibDirection` |
| `high` | `Decimal` |
| `low` | `Decimal` |
| `fib_low_ratio` | `Decimal` |
| `fib_high_ratio` | `Decimal` |
| `overlapping_zone_ids` | `list[str]` |
| `quality` | `PremiumDiscountQuality` |
| `strength` | `Decimal` |
| `evidence` | `list[str]` |

### InstitutionalPricingContext

| Field | Type |
|-------|------|
| `narrative` | `list[str]` |
| `current_price_location` | `PremiumDiscountZone` |
| `preferred_buy_territory` | `PremiumDiscountZone` |
| `preferred_sell_territory` | `PremiumDiscountZone` |
| `active_dealing_range_scope` | `DealingRangeScope` |
| `structure_trend` | `TrendDirection \| None` |
| `liquidity_bias` | `str \| None` |
| `dominant_array_territory` | `PremiumDiscountZone \| None` |
| `mtf_aligned` | `bool` |
| `ote_available` | `bool` |
| `confidence` | `Decimal` |

### MTFPremiumDiscountAlignment

| Field | Type |
|-------|------|
| `territory` | `PremiumDiscountZone` |
| `aligned_timeframes` | `list[str]` |
| `alignment_score` | `Decimal` |
| `ltf_timeframe` | `str` |
| `htf_timeframe` | `str` |
| `range_overlap_percent` | `Decimal` |
| `array_overlap_count` | `int` |
| `evidence` | `list[str]` |

### HTFPricingContext

| Field | Type |
|-------|------|
| `timeframe` | `str` |
| `territory` | `PremiumDiscountZone` |
| `dealing_range` | `DealingRange` |
| `array_count` | `int` |
| `equilibrium` | `Decimal` |
| `evidence` | `list[str]` |

### NestedZoneContext

| Field | Type |
|-------|------|
| `child_zone_id` | `str` |
| `child_zone_type` | `InstitutionalZoneType` |
| `parent_zone_id` | `str` |
| `parent_zone_type` | `InstitutionalZoneType` |
| `territory` | `PremiumDiscountZone` |
| `containment_percent` | `Decimal` |
| `evidence` | `list[str]` |

### PremiumDiscountState

| Field | Type |
|-------|------|
| `active_dealing_range` | `DealingRange \| None` |
| `active_external_range` | `DealingRange \| None` |
| `active_internal_range` | `DealingRange \| None` |
| `last_price_location` | `PremiumDiscountZone` |
| `last_analysis_utc` | `datetime \| None` |
| `bar_count` | `int` |

### PremiumDiscountEvent

| Field | Type |
|-------|------|
| `kind` | `PremiumDiscountEventKind` |
| `timestamp_utc` | `datetime` |
| `timeframe` | `str` |
| `description` | `str` |
| `range_id` | `str \| None` |
| `price` | `Decimal \| None` |
| `territory` | `PremiumDiscountZone \| None` |
| `array_id` | `str \| None` |
| `ote_id` | `str \| None` |

---

## Enums

### PremiumDiscountZone

| Value | Description |
|-------|-------------|
| `premium` | Above dealing range equilibrium |
| `discount` | Below dealing range equilibrium |
| `equilibrium` | Within equilibrium tolerance band |

### PremiumDiscountBias

| Value | Description |
|-------|-------------|
| `premium` | Context favors premium-side activity |
| `discount` | Context favors discount-side activity |
| `equilibrium` | Price near equilibrium |
| `neutral` | Balanced arrays |
| `undetermined` | Insufficient dealing range evidence |

### PremiumDiscountQuality

| Value | Description |
|-------|-------------|
| `high` | Strong range and confluence |
| `medium` | Meets minimum criteria |
| `low` | Marginal confidence |

### DealingRangeScope

| Value | Description |
|-------|-------------|
| `external` | External structure range |
| `internal` | Internal structure range |
| `primary` | Active primary range |

### InstitutionalZoneType

| Value | Description |
|-------|-------------|
| `order_block` | Order block |
| `fair_value_gap` | Fair value gap |
| `breaker_block` | Breaker block |
| `mitigation_block` | Mitigation block |
| `liquidity` | Liquidity zone |

### FibDirection

| Value | Description |
|-------|-------------|
| `bullish` | Fib from range low toward high |
| `bearish` | Fib from range high toward low |

### PremiumDiscountEventKind

See [EVENTS.md](./EVENTS.md) for complete event kind catalog.

---

## PremiumDiscountEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | Register handler (`"*"` for all) |
| `publish_dealing_range_established(range, symbol)` | `DealingRangeEstablished` |
| `publish_dealing_range_updated(range, symbol)` | `DealingRangeUpdated` |
| `publish_dealing_range_invalidated(range, symbol)` | `DealingRangeInvalidated` |
| `publish_swing_high_anchored(anchor, symbol)` | `SwingHighAnchored` |
| `publish_swing_low_anchored(anchor, symbol)` | `SwingLowAnchored` |
| `publish_premium_entered(price, symbol)` | `PremiumZoneEntered` |
| `publish_discount_entered(price, symbol)` | `DiscountZoneEntered` |
| `publish_equilibrium_reached(price, symbol)` | `EquilibriumReached` |
| `publish_premium_array(array, symbol)` | `PremiumArrayFormed` |
| `publish_discount_array(array, symbol)` | `DiscountArrayFormed` |
| `publish_internal_premium(band, symbol)` | `InternalPremiumClassified` |
| `publish_internal_discount(band, symbol)` | `InternalDiscountClassified` |
| `publish_htf_premium(context, symbol)` | `HTFPremiumContext` |
| `publish_htf_discount(context, symbol)` | `HTFDiscountContext` |
| `publish_mtf_premium_aligned(alignment, symbol)` | `MTFPremiumAligned` |
| `publish_mtf_discount_aligned(alignment, symbol)` | `MTFDiscountAligned` |
| `publish_nested_premium(context, symbol)` | `NestedPremiumZone` |
| `publish_nested_discount(context, symbol)` | `NestedDiscountZone` |
| `publish_fibonacci_computed(fib, symbol)` | `FibonacciRangeComputed` |
| `publish_ote_derived(ote, symbol)` | `OTEZoneDerived` |
| `publish_institutional_context(context, symbol)` | `InstitutionalContextUpdated` |
| `publish_analysis_completed(analysis)` | `PremiumDiscountUpdated` / `analysis.premium_discount.completed` |

---

## Exceptions

All inherit from `PremiumDiscountError` → `CanonTradingError`.

| Exception | Code | When |
|-----------|------|------|
| `PremiumDiscountError` | `PD_ERROR` | Base error |
| `InsufficientDataError` | `PD_INSUFFICIENT_DATA` | Not enough candles |
| `ValidationError` | `PD_VALIDATION_FAILED` | Invalid candle batch |
| `InvalidStructureError` | `PD_INVALID_STRUCTURE` | Bad structure context |
| `InvalidLiquidityStateError` | `PD_INVALID_LIQUIDITY_STATE` | Bad liquidity state |
| `InvalidOrderBlocksError` | `PD_INVALID_ORDER_BLOCKS` | Mismatched order blocks |
| `InvalidFVGStateError` | `PD_INVALID_FVG_STATE` | Bad FVG state |
| `InvalidBreakerBlocksError` | `PD_INVALID_BREAKER_BLOCKS` | Mismatched breaker blocks |
| `InvalidMitigationBlocksError` | `PD_INVALID_MITIGATION_BLOCKS` | Mismatched mitigation blocks |
| `InvalidHTFContextError` | `PD_INVALID_HTF_CONTEXT` | Invalid HTF context |
| `UnsupportedTimeframeError` | `PD_TIMEFRAME_UNSUPPORTED` | Timeframe not configured |
| `DealingRangeInvalidError` | `PD_DEALING_RANGE_INVALID` | Range construction failed (non-fatal in analyze) |
| `StateCorruptError` | `PD_STATE_CORRUPT` | Unrecoverable prior state |

### Error Code Reference

| Code | HTTP Mapping (Future API) | Severity |
|------|---------------------------|----------|
| `PD_INSUFFICIENT_DATA` | 422 | Error |
| `PD_VALIDATION_FAILED` | 422 | Error |
| `PD_INVALID_STRUCTURE` | 422 | Error |
| `PD_INVALID_LIQUIDITY_STATE` | 422 | Error |
| `PD_INVALID_ORDER_BLOCKS` | 422 | Error |
| `PD_INVALID_FVG_STATE` | 422 | Error |
| `PD_INVALID_BREAKER_BLOCKS` | 422 | Error |
| `PD_INVALID_MITIGATION_BLOCKS` | 422 | Error |
| `PD_INVALID_HTF_CONTEXT` | 422 | Error |
| `PD_TIMEFRAME_UNSUPPORTED` | 422 | Error |
| `PD_DEALING_RANGE_INVALID` | 200 (degraded) | Warning |
| `PD_STATE_CORRUPT` | 422 | Error |
| `PD_ERROR` | 500 | Error |

`PD_DEALING_RANGE_INVALID` is a degraded outcome: `analyze()` returns `PremiumDiscountAnalysis` with `bias: undetermined` rather than raising, unless configured for strict mode in Sprint 8.2.

---

## Configuration Functions

### `load_market_premium_discount_config(yaml_path=None) -> PremiumDiscountConfig`

Loads from `config/settings.yaml` → `market_premium_discount` section with `engines.market_premium_discount` toggle.

---

## Internal Interfaces (Not Public)

These classes are module-internal in Sprint 8.2; documented here for architecture completeness.

### PremiumDiscountDetector

| Method | Description |
|--------|-------------|
| `detect(...)` | Full analysis pipeline orchestration |

### DealingRangeBuilder

| Method | Description |
|--------|-------------|
| `build(scope, structure)` | Construct dealing range for scope |
| `validate(range)` | Range validity checks |
| `invalidate(range, event)` | Apply invalidation rules |

### SwingAnchorSelector

| Method | Description |
|--------|-------------|
| `select_high(structure, scope)` | Select swing high anchor |
| `select_low(structure, scope)` | Select swing low anchor |
| `score_quality(swing)` | Swing quality 0.0–1.0 |

### TerritoryClassifier

| Method | Description |
|--------|-------------|
| `classify(price, range)` | Price territory classification |
| `classify_midpoint(midpoint, range)` | Zone territory classification |

### ArrayAssembler

| Method | Description |
|--------|-------------|
| `collect_zones(...)` | Normalize upstream zones to entries |
| `cluster(entries, territory)` | Cluster into arrays |
| `score_array(array)` | Array confluence scoring |

### MTFAligner

| Method | Description |
|--------|-------------|
| `apply_htf(htf_context)` | HTF premium/discount context |
| `score_premium(ltf, htf)` | Premium alignment score |
| `score_discount(ltf, htf)` | Discount alignment score |

### FibonacciProjector

| Method | Description |
|--------|-------------|
| `project(range, direction)` | Compute Fibonacci levels |

### OTEBuilder

| Method | Description |
|--------|-------------|
| `derive(range, fib, zones)` | Build OTE zone |

### InstitutionalContextBuilder

| Method | Description |
|--------|-------------|
| `build(parts)` | Assemble composite narrative |

### QualityScorer

| Method | Description |
|--------|-------------|
| `score_range(range, structure, confluence)` | Range strength 0.0–1.0 |
| `score_analysis(analysis)` | Overall analysis strength |

---

## Planned `__all__` Export List

```python
__all__ = [
    # Engine
    "PremiumDiscountEngine",
    # Schemas
    "PremiumDiscountAnalysis",
    "DealingRange",
    "SwingAnchor",
    "PriceZoneBand",
    "EquilibriumLevel",
    "InstitutionalArray",
    "ArrayZoneEntry",
    "FibonacciDealingRange",
    "FibonacciLevel",
    "OptimalTradeEntryZone",
    "InstitutionalPricingContext",
    "PremiumDiscountContext",
    "MTFPremiumDiscountAlignment",
    "HTFPricingContext",
    "NestedZoneContext",
    "PremiumDiscountState",
    "PremiumDiscountEvent",
    # Enums
    "PremiumDiscountZone",
    "PremiumDiscountBias",
    "PremiumDiscountQuality",
    "DealingRangeScope",
    "InstitutionalZoneType",
    "FibDirection",
    "PremiumDiscountEventKind",
    # Config
    "PremiumDiscountConfig",
    "PremiumDiscountQualityWeights",
    "ZoneStatusFilters",
    "load_market_premium_discount_config",
    # Events
    "PremiumDiscountEventPublisher",
    "PremiumDiscountAnalysisEvent",
    # Exceptions
    "PremiumDiscountError",
    "InsufficientDataError",
    "ValidationError",
    "InvalidStructureError",
    "InvalidLiquidityStateError",
    "InvalidOrderBlocksError",
    "InvalidFVGStateError",
    "InvalidBreakerBlocksError",
    "InvalidMitigationBlocksError",
    "InvalidHTFContextError",
    "UnsupportedTimeframeError",
    "DealingRangeInvalidError",
    "StateCorruptError",
]
```

---

## Cross-Engine Import Rules

| Rule | Requirement |
|------|-------------|
| Import `NormalizedCandle` from `market_data` public API only | Required |
| Import `MarketStructure`, `SwingPoint`, `TrendDirection` from `market_structure` public API only | Required |
| Import `LiquidityState` from `market_liquidity` public API only | Required |
| Import `OrderBlock` from `market_order_block` public API only | Required |
| Import `FairValueGapState`, `FairValueGap` from `market_fvg` public API only | Required |
| Import `BreakerBlock` from `market_breaker` public API only | Required |
| Import `MitigationBlock` from `market_mitigation` public API only | Required |
| Do not import analysis envelopes from upstream engines | Required |
| Do not import MT5, broker, or normalizer internals | Required |
| Do not import Decision Engine types | Required |

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |

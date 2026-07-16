# Order Block Engine — Public Interfaces

**Engine ID:** `order_block`  
**Sprint:** 4.1 (Architecture specification)  
**Planned Module:** `backend.engines.market_order_block`  
**Status:** Not implemented

All symbols will be exported from `backend.engines.market_order_block.__init__`.

---

## Package Import (Planned)

```python
from backend.engines.market_order_block import (
    OrderBlockEngine,
    OrderBlockAnalysis,
    OrderBlock,
    OrderBlockConfig,
    load_order_block_config,
    OrderBlockEventPublisher,
    # ... see __all__
)
```

---

## OrderBlockEngine

**Purpose:** Public orchestrator for order block detection and lifecycle management.

### Constructor

```python
OrderBlockEngine(
    config: OrderBlockConfig | None = None,
    detector: OrderBlockDetector | None = None,
    validator: OrderBlockInputValidator | None = None,
    publisher: OrderBlockEventPublisher | None = None,
)
```

Dependency injection follows Sprints 1–3 pattern for testability.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `OrderBlockConfig` | Active configuration |
| `publisher` | `OrderBlockEventPublisher` | Event publisher instance |
| `prior_state` | `OrderBlockState \| None` | Persisted continuity state |

### Primary Method

#### `analyze(candles, structure=None, liquidity=None, *, timeframe=None, prior_state=None) -> OrderBlockAnalysis`

| | |
|---|---|
| **Input** | `list[NormalizedCandle]` — closed candles preferred |
| | `MarketStructure \| None` — structure context |
| | `LiquidityAnalysis \| None` — liquidity context |
| **Output** | `OrderBlockAnalysis` |
| **Raises** | `InsufficientDataError`, `ValidationError`, `UnsupportedTimeframeError`, `InvalidStructureError`, `InvalidLiquidityError` |
| **Events** | All order block lifecycle events via publisher |

### Detection Methods

| Method | Input | Returns | Description |
|--------|-------|---------|-------------|
| `detect_bullish_blocks(candles, structure)` | Candles + optional structure | `list[OrderBlock]` | Bullish order blocks only |
| `detect_bearish_blocks(candles, structure)` | Candles + optional structure | `list[OrderBlock]` | Bearish order blocks only |
| `classify_lifecycle(blocks, candles)` | Existing blocks + candles | `list[OrderBlock]` | Update fresh/mitigated/invalidated |
| `publish_events(analysis)` | `OrderBlockAnalysis` | `None` | Emit all lifecycle events |

### State Management

| Method | Description |
|--------|-------------|
| `reset_state()` | Clear persisted `prior_state` |
| `handle_config_updated(config)` | Hot reload configuration and rebuild detector |

---

## Schemas

### OrderBlockDirection (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Demand zone — bullish order block |
| `bearish` | Supply zone — bearish order block |

### OrderBlockStatus (Enum)

| Value | Description |
|-------|-------------|
| `fresh` | Untested — price has not returned to zone |
| `mitigated` | Price re-entered zone without invalidation |
| `invalidated` | Zone broken — no longer valid |

### OrderBlockQuality (Enum)

| Value | Description |
|-------|-------------|
| `high` | Strong displacement + structure alignment |
| `medium` | Meets minimum criteria |
| `low` | Marginal — low confidence |

### OrderBlockBias (Enum)

| Value | Description |
|-------|-------------|
| `bullish` | Dominant fresh bullish blocks |
| `bearish` | Dominant fresh bearish blocks |
| `neutral` | Balanced or no active blocks |
| `undetermined` | Insufficient data |

### OrderBlockEventKind (Enum)

| Value | Description |
|-------|-------------|
| `OrderBlockDetected` | New block identified |
| `BullishOrderBlockDetected` | New bullish block |
| `BearishOrderBlockDetected` | New bearish block |
| `FreshOrderBlock` | Block confirmed fresh |
| `MitigatedOrderBlock` | Block mitigated |
| `InvalidatedOrderBlock` | Block invalidated |
| `OrderBlockUpdated` | Full analysis complete |

### OrderBlock

See [ARCHITECTURE.md](./ARCHITECTURE.md) for full field list.

Frozen Pydantic model (`model_config = ConfigDict(frozen=True)`).

### OrderBlockAnalysis

| Field | Type |
|-------|------|
| `symbol` | `str` |
| `timeframe` | `str` |
| `timestamp_utc` | `datetime` |
| `order_blocks` | `list[OrderBlock]` |
| `fresh_blocks` | `list[OrderBlock]` |
| `mitigated_blocks` | `list[OrderBlock]` |
| `invalidated_blocks` | `list[OrderBlock]` |
| `bias` | `OrderBlockBias` |
| `confidence` | `Decimal` |
| `evidence` | `list[str]` |
| `state` | `OrderBlockState` |
| `events` | `list[OrderBlockEvent]` |

### OrderBlockState

| Field | Type | Description |
|-------|------|-------------|
| `active_blocks` | `list[OrderBlock]` | Currently tracked blocks |
| `last_analysis_utc` | `datetime \| None` | Last analysis timestamp |
| `bar_count` | `int` | Candles processed |

### OrderBlockEvent

| Field | Type |
|-------|------|
| `kind` | `OrderBlockEventKind` |
| `timestamp_utc` | `datetime` |
| `timeframe` | `str` |
| `description` | `str` |
| `block_id` | `str \| None` |
| `direction` | `OrderBlockDirection \| None` |
| `status` | `OrderBlockStatus \| None` |
| `price` | `Decimal \| None` |

---

## OrderBlockEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | Register handler (`"*"` for all) |
| `publish_block_detected(block, symbol)` | `OrderBlockDetected` |
| `publish_bullish_block(block, symbol)` | `BullishOrderBlockDetected` |
| `publish_bearish_block(block, symbol)` | `BearishOrderBlockDetected` |
| `publish_fresh_block(block, symbol)` | `FreshOrderBlock` |
| `publish_mitigated_block(block, symbol)` | `MitigatedOrderBlock` |
| `publish_invalidated_block(block, symbol)` | `InvalidatedOrderBlock` |
| `publish_analysis_completed(analysis)` | `OrderBlockUpdated` / `analysis.order_block.completed` |

---

## Exceptions

All inherit from `OrderBlockError` → `CanonTradingError`.

| Exception | Code | When |
|-----------|------|------|
| `OrderBlockError` | `OBE_ERROR` | Base error |
| `InsufficientDataError` | `OBE_INSUFFICIENT_DATA` | Not enough candles |
| `ValidationError` | `OBE_VALIDATION_FAILED` | Invalid candle batch |
| `InvalidStructureError` | `OBE_INVALID_STRUCTURE` | Bad structure context |
| `InvalidLiquidityError` | `OBE_INVALID_LIQUIDITY` | Bad liquidity context |
| `UnsupportedTimeframeError` | `OBE_TIMEFRAME_UNSUPPORTED` | Timeframe not configured |
| `DuplicateBlockError` | `OBE_DUPLICATE_BLOCK` | Duplicate block ID in state |
| `StateCorruptError` | `OBE_STATE_CORRUPT` | Unrecoverable prior state |

---

## Configuration Functions

### `load_order_block_config(yaml_path=None) -> OrderBlockConfig`

Loads from `config/settings.yaml` → `order_block` section with `engines.order_block` toggle.

---

## Boundary Rules

| Rule | Enforcement |
|------|-------------|
| Import `NormalizedCandle` from `market_data` public API only | Required |
| Import `MarketStructure` from `market_structure` public API only | Required |
| Import `LiquidityAnalysis` from `market_liquidity` public API only | Required |
| No imports from Decision, Risk, Notification engines | Required |
| No modification of Sprint 1–3 public interfaces | Required |
| No trade signal fields in output schemas | Required |

---

## Related Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CONFIGURATION.md](./CONFIGURATION.md)
- [EVENTS.md](./EVENTS.md)

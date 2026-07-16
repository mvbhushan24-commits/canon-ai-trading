# Market Structure Engine — Public Interfaces

All symbols exported from `backend.engines.market_structure`.

---

## MarketStructureEngine

### `__init__(config=None, detector=None, validator=None, publisher=None)`

Dependency injection for config, detector, validator, and publisher.

### Properties

| Property | Type |
|----------|------|
| `config` | `MarketStructureConfig` |
| `publisher` | `StructureEventPublisher` |
| `prior_state` | `StructureState \| None` |

### `analyze(candles, *, timeframe=None, prior_state=None) -> MarketStructure`

| | |
|---|---|
| **Input** | `list[NormalizedCandle]` — closed candles preferred |
| **Output** | `MarketStructure` |
| **Raises** | `ValidationError`, `InsufficientDataError`, `UnsupportedTimeframeError` |
| **Events** | All structure events via publisher |

### `analyze_candle(candle, history, *, prior_state=None) -> MarketStructure`

Analyze with history plus latest candle.

### `reset_state() -> None`

Clear persisted `prior_state`.

### `handle_config_updated(config) -> None`

Replace configuration and rebuild detector.

---

## MarketStructure

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Instrument |
| `timeframe` | `str` | Analysis timeframe |
| `timestamp_utc` | `datetime` | Analysis timestamp |
| `current_trend` | `TrendDirection` | bullish/bearish/range/undetermined |
| `swing_highs` | `list[SwingPoint]` | Labeled swing highs |
| `swing_lows` | `list[SwingPoint]` | Labeled swing lows |
| `higher_highs` | `list[SwingPoint]` | HH swings |
| `higher_lows` | `list[SwingPoint]` | HL swings |
| `lower_highs` | `list[SwingPoint]` | LH swings |
| `lower_lows` | `list[SwingPoint]` | LL swings |
| `bos_events` | `list[BOSEvent]` | BOS detections |
| `choch_events` | `list[CHoCHEvent]` | CHoCH detections |
| `internal_structure` | `StructureState` | Internal layer state |
| `external_structure` | `StructureState` | External layer state |
| `current_structure_state` | `StructureState` | Primary state |
| `structure_events` | `list[StructureEvent]` | Event timeline |
| `evidence` | `list[str]` | Human-readable reasoning |
| `confidence` | `Decimal` | 0.0–1.0 |

---

## SwingPoint

| Field | Type |
|-------|------|
| `price` | `Decimal` |
| `timestamp_utc` | `datetime` |
| `bar_index` | `int` |
| `kind` | `SwingKind` — swing_high / swing_low |
| `label` | `SwingLabel` — HH / HL / LH / LL / none |

---

## BOSEvent / CHoCHEvent

| Field | Type |
|-------|------|
| `direction` | `BOSDirection` or `CHoCHDirection` |
| `broken_level` | `Decimal` |
| `break_price` | `Decimal` |
| `timestamp_utc` | `datetime` |
| `bar_index` | `int` |
| `timeframe` | `str` |

---

## StructureEventPublisher

| Method | Event |
|--------|-------|
| `subscribe(event_type, handler)` | — |
| `publish_swing_detected(swing, symbol, timeframe)` | `SwingDetected` |
| `publish_bos_detected(bos, symbol)` | `BOSDetected` |
| `publish_choch_detected(choch, symbol)` | `CHoCHDetected` |
| `publish_trend_changed(...)` | `TrendChanged` |
| `publish_structure_updated(structure)` | `StructureUpdated` |

Wildcard `"*"` supported for all events.

---

## Enums

### TrendDirection

`bullish`, `bearish`, `range`, `undetermined`

### StructureEventKind

`SwingDetected`, `BOSDetected`, `CHoCHDetected`, `TrendChanged`, `StructureUpdated`

---

## Exceptions

| Exception | Code |
|-----------|------|
| `MarketStructureError` | `MSE_ERROR` |
| `InsufficientDataError` | `MSE_INSUFFICIENT_DATA` |
| `InvalidCandleError` | `MSE_INVALID_CANDLE` |
| `ValidationError` | `MSE_VALIDATION_FAILED` |
| `StateCorruptError` | `MSE_STATE_CORRUPT` |
| `UnsupportedTimeframeError` | `MSE_TIMEFRAME_UNSUPPORTED` |

---

## Configuration Functions

### `load_market_structure_config(settings=None, yaml_path=None) -> MarketStructureConfig`

Loads from `config/settings.yaml` → `market_structure` section.

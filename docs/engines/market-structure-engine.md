# Market Structure Engine — Interface Contract

**Engine ID:** `market_structure`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Analyze XAUUSD price action to identify market structure states including swing points, breaks of structure (BOS), changes of character (CHoCH), and current structural bias.

---

## 2. Responsibilities

- Consume normalized candle data from the Market Data Engine
- Identify swing highs and swing lows per configured timeframe
- Detect BOS and CHoCH events
- Determine current structural bias (`bullish`, `bearish`, `neutral`, `undetermined`)
- Produce explainable evidence for every structural label
- Publish structure analysis events
- Emit no trade signals

**Out of scope:** Liquidity mapping, SMC order blocks, entry/exit decisions, order execution.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `candle` | `NormalizedCandle` | Yes | Closed candle from Market Data Engine |
| `timeframe` | `string` | Yes | Analysis timeframe |
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `swing_lookback` | `integer` | No | Bars used for swing detection (config override) |
| `prior_state` | `StructureState` | No | Previous engine state for continuity |

### NormalizedCandle

Uses schema defined in [Market Data Engine](./market-data-engine.md).

---

## 4. Outputs

### StructureAnalysis

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | `XAUUSD` |
| `timeframe` | `string` | Analysis timeframe |
| `timestamp_utc` | `datetime` | Analysis timestamp (UTC) |
| `bias` | `enum` | `bullish`, `bearish`, `neutral`, `undetermined` |
| `confidence` | `decimal` | 0.0–1.0 structural confidence |
| `last_swing_high` | `SwingPoint` | Most recent confirmed swing high |
| `last_swing_low` | `SwingPoint` | Most recent confirmed swing low |
| `last_event` | `enum` | `bos_bullish`, `bos_bearish`, `choch_bullish`, `choch_bearish`, `none` |
| `evidence` | `string[]` | Human-readable reasoning statements |
| `state` | `StructureState` | Serializable state for next invocation |

### SwingPoint

| Field | Type | Description |
|-------|------|-------------|
| `price` | `decimal` | Swing price level |
| `timestamp_utc` | `datetime` | Time of swing |
| `bar_index` | `integer` | Index in candle series |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Market Data Engine | Upstream | Closed candle events |
| Configuration | Internal | Swing lookback, timeframes |
| Event Bus | Internal | Publish/consume events |

**Does not depend on** Decision Engine, Telegram Engine, or Dashboard directly.

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `analysis.structure.completed` | Analysis cycle complete | `StructureAnalysis` |
| `analysis.structure.bos_detected` | Break of structure detected | Event type, price, timeframe |
| `analysis.structure.choch_detected` | Change of character detected | Event type, price, timeframe |
| `analysis.structure.bias_changed` | Structural bias changed | Previous and new bias |
| `analysis.structure.error` | Analysis failure | Error code and context |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Trigger structure analysis |
| `system.config.updated` | Config service | Reload analysis parameters |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `STRUCTURE_TIMEFRAMES` | YAML | `M15,H1,H4` | Timeframes to analyze |
| `STRUCTURE_SWING_LOOKBACK` | YAML | `5` | Bars for swing detection |
| `STRUCTURE_MIN_CONFIDENCE` | YAML | `0.5` | Minimum confidence to publish bias |
| `STRUCTURE_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `MSE_INSUFFICIENT_DATA` | Not enough candles for lookback | Return `undetermined` bias; emit warning |
| `MSE_INVALID_CANDLE` | Malformed candle input | Reject input; emit error event |
| `MSE_STATE_CORRUPT` | Prior state cannot be deserialized | Reset state; emit warning |
| `MSE_TIMEFRAME_UNSUPPORTED` | Timeframe not in config | Skip analysis; log error |

---

## 10. Success Criteria

- Every output includes `evidence` array with at least one statement when bias is not `undetermined`
- BOS and CHoCH detections reference specific swing points
- Engine is stateless across restarts when `prior_state` is restored from persistence
- No trade direction or entry price is emitted
- Output schema is stable and consumable by Decision Engine
- `undetermined` is returned when evidence is insufficient — this is valid success

---

**Implementation sprint:** TBD by Product Owner

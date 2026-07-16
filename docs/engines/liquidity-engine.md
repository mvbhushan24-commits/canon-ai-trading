# Liquidity Engine — Interface Contract

**Engine ID:** `liquidity`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Identify liquidity zones, equal highs/lows, inducement areas, and liquidity sweep events on XAUUSD to support explainable downstream analysis.

---

## 2. Responsibilities

- Consume normalized candle data and market structure context
- Detect equal highs and equal lows (liquidity pools)
- Identify buy-side and sell-side liquidity levels
- Detect liquidity sweeps (stop hunts) and classify sweep quality
- Map inducement zones relative to structure
- Publish liquidity analysis with evidence
- Emit no trade signals

**Out of scope:** Order block detection (Smart Money Engine), trade decisions, execution.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `candle` | `NormalizedCandle` | Yes | Closed candle from Market Data Engine |
| `timeframe` | `string` | Yes | Analysis timeframe |
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `structure_context` | `StructureAnalysis` | No | Latest output from Market Structure Engine |
| `prior_state` | `LiquidityState` | No | Previous engine state |

### StructureAnalysis

Uses schema defined in [Market Structure Engine](./market-structure-engine.md).

---

## 4. Outputs

### LiquidityAnalysis

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | `XAUUSD` |
| `timeframe` | `string` | Analysis timeframe |
| `timestamp_utc` | `datetime` | Analysis timestamp (UTC) |
| `liquidity_pools` | `LiquidityPool[]` | Identified liquidity zones |
| `recent_sweeps` | `LiquiditySweep[]` | Recent sweep events |
| `bias` | `enum` | `buy_side`, `sell_side`, `balanced`, `undetermined` |
| `confidence` | `decimal` | 0.0–1.0 |
| `evidence` | `string[]` | Human-readable reasoning |
| `state` | `LiquidityState` | Serializable state |

### LiquidityPool

| Field | Type | Description |
|-------|------|-------------|
| `type` | `enum` | `equal_highs`, `equal_lows`, `swing_high`, `swing_low` |
| `price_level` | `decimal` | Pool price |
| `strength` | `decimal` | 0.0–1.0 pool strength |
| `touched_count` | `integer` | Number of price touches |
| `is_active` | `boolean` | Whether pool is untapped |

### LiquiditySweep

| Field | Type | Description |
|-------|------|-------------|
| `direction` | `enum` | `bullish_sweep`, `bearish_sweep` |
| `swept_level` | `decimal` | Liquidity level swept |
| `sweep_price` | `decimal` | Extreme price of sweep |
| `timestamp_utc` | `datetime` | Sweep timestamp |
| `quality` | `enum` | `strong`, `weak`, `indeterminate` |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Market Data Engine | Upstream | Closed candle events |
| Market Structure Engine | Upstream | Optional structure context |
| Configuration | Internal | Tolerance and lookback settings |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `analysis.liquidity.completed` | Analysis cycle complete | `LiquidityAnalysis` |
| `analysis.liquidity.pool_identified` | New pool detected | Pool details |
| `analysis.liquidity.sweep_detected` | Liquidity sweep detected | Sweep details |
| `analysis.liquidity.pool_removed` | Pool invalidated/swept | Pool reference |
| `analysis.liquidity.error` | Analysis failure | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Trigger liquidity analysis |
| `analysis.structure.completed` | Market Structure Engine | Enrich with structure context |
| `system.config.updated` | Config service | Reload parameters |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `LIQUIDITY_TIMEFRAMES` | YAML | `M5,M15,H1` | Timeframes to analyze |
| `LIQUIDITY_EQUAL_TOLERANCE_PIPS` | YAML | `3` | Equal high/low tolerance |
| `LIQUIDITY_LOOKBACK_BARS` | YAML | `100` | Historical lookback |
| `LIQUIDITY_MIN_TOUCHES` | YAML | `2` | Minimum touches for pool |
| `LIQUIDITY_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `LQE_INSUFFICIENT_DATA` | Not enough candles | Return `undetermined`; emit warning |
| `LQE_INVALID_CANDLE` | Malformed input | Reject; emit error |
| `LQE_STRUCTURE_UNAVAILABLE` | Structure context missing | Proceed without enrichment; note in evidence |
| `LQE_TOLERANCE_INVALID` | Config tolerance out of range | Use safe default; emit warning |

---

## 10. Success Criteria

- Liquidity pools include price level, type, and strength
- Sweeps reference the specific pool swept
- Evidence explains why each pool or sweep was identified
- No entry, stop, or target prices are emitted
- `undetermined` bias is valid when pools cannot be confirmed
- Output schema is stable for Decision Engine consumption

---

**Implementation sprint:** TBD by Product Owner

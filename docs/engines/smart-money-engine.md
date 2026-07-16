# Smart Money Engine — Interface Contract

**Engine ID:** `smart_money`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Apply Smart Money Concepts (SMC) analysis to XAUUSD including order blocks, fair value gaps (FVG), breaker blocks, and mitigation zones to produce explainable institutional-style context.

---

## 2. Responsibilities

- Consume normalized candle data and optional structure/liquidity context
- Detect bullish and bearish order blocks
- Identify fair value gaps and track fill/mitigation status
- Detect breaker blocks and mitigation zones
- Classify zone quality and relevance
- Publish SMC analysis with evidence
- Emit no trade signals

**Out of scope:** Trend classification (Trend Engine), risk sizing, trade decisions, execution.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `candle` | `NormalizedCandle` | Yes | Closed candle from Market Data Engine |
| `timeframe` | `string` | Yes | Analysis timeframe |
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `structure_context` | `StructureAnalysis` | No | From Market Structure Engine |
| `liquidity_context` | `LiquidityAnalysis` | No | From Liquidity Engine |
| `prior_state` | `SmartMoneyState` | No | Previous engine state |

---

## 4. Outputs

### SmartMoneyAnalysis

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | `XAUUSD` |
| `timeframe` | `string` | Analysis timeframe |
| `timestamp_utc` | `datetime` | Analysis timestamp (UTC) |
| `order_blocks` | `OrderBlock[]` | Active order blocks |
| `fair_value_gaps` | `FairValueGap[]` | Active FVGs |
| `breaker_blocks` | `BreakerBlock[]` | Active breaker blocks |
| `bias` | `enum` | `bullish`, `bearish`, `neutral`, `undetermined` |
| `confidence` | `decimal` | 0.0–1.0 |
| `evidence` | `string[]` | Human-readable reasoning |
| `state` | `SmartMoneyState` | Serializable state |

### OrderBlock

| Field | Type | Description |
|-------|------|-------------|
| `type` | `enum` | `bullish`, `bearish` |
| `high` | `decimal` | Zone upper bound |
| `low` | `decimal` | Zone lower bound |
| `origin_time_utc` | `datetime` | Formation time |
| `status` | `enum` | `active`, `mitigated`, `invalidated` |
| `quality` | `enum` | `high`, `medium`, `low` |

### FairValueGap

| Field | Type | Description |
|-------|------|-------------|
| `type` | `enum` | `bullish`, `bearish` |
| `high` | `decimal` | Gap upper bound |
| `low` | `decimal` | Gap lower bound |
| `fill_percent` | `decimal` | 0.0–100.0 fill percentage |
| `status` | `enum` | `open`, `partial`, `filled` |

### BreakerBlock

| Field | Type | Description |
|-------|------|-------------|
| `type` | `enum` | `bullish`, `bearish` |
| `high` | `decimal` | Zone upper bound |
| `low` | `decimal` | Zone lower bound |
| `origin_time_utc` | `datetime` | Formation time |
| `status` | `enum` | `active`, `mitigated`, `invalidated` |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Market Data Engine | Upstream | Closed candle events |
| Market Structure Engine | Upstream | Optional structure context |
| Liquidity Engine | Upstream | Optional liquidity context |
| Configuration | Internal | SMC parameters |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `analysis.smart_money.completed` | Analysis cycle complete | `SmartMoneyAnalysis` |
| `analysis.smart_money.ob_detected` | Order block identified | Order block details |
| `analysis.smart_money.fvg_detected` | FVG identified | FVG details |
| `analysis.smart_money.zone_mitigated` | Zone mitigated/filled | Zone reference |
| `analysis.smart_money.error` | Analysis failure | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Trigger SMC analysis |
| `analysis.structure.completed` | Market Structure Engine | Optional context enrichment |
| `analysis.liquidity.completed` | Liquidity Engine | Optional context enrichment |
| `system.config.updated` | Config service | Reload parameters |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `SMC_TIMEFRAMES` | YAML | `M5,M15,H1,H4` | Timeframes to analyze |
| `SMC_OB_LOOKBACK_BARS` | YAML | `50` | Order block lookback |
| `SMC_FVG_MIN_SIZE_PIPS` | YAML | `2` | Minimum FVG size |
| `SMC_MITIGATION_THRESHOLD` | YAML | `0.5` | Fill % for mitigation |
| `SMC_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `SME_INSUFFICIENT_DATA` | Not enough candles | Return `undetermined`; emit warning |
| `SME_INVALID_CANDLE` | Malformed input | Reject; emit error |
| `SME_CONTEXT_UNAVAILABLE` | Upstream context missing | Proceed; note in evidence |
| `SME_STATE_CORRUPT` | State deserialization fails | Reset state; emit warning |

---

## 10. Success Criteria

- All zones include bounds, type, status, and quality
- Evidence references the candle or structure event that formed each zone
- Mitigation status is tracked and updated on subsequent candles
- No trade entry, stop loss, or take profit levels are emitted
- `undetermined` bias is valid when SMC confluence is insufficient
- Output schema is stable for Decision Engine consumption

---

**Implementation sprint:** TBD by Product Owner

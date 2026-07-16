# Trend Engine — Interface Contract

**Engine ID:** `trend`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Determine XAUUSD trend context across configured timeframes including direction, strength, and alignment to support conservative downstream decision-making.

---

## 2. Responsibilities

- Consume normalized multi-timeframe candle data
- Classify trend direction per timeframe
- Measure trend strength and momentum
- Assess multi-timeframe trend alignment
- Detect trend exhaustion or transition signals
- Publish trend analysis with evidence
- Emit no trade signals

**Out of scope:** Market structure breaks, SMC zones, risk sizing, trade decisions.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `candles` | `NormalizedCandle[]` | Yes | Closed candles per timeframe |
| `timeframe` | `string` | Yes | Primary analysis timeframe |
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `structure_context` | `StructureAnalysis` | No | From Market Structure Engine |
| `prior_state` | `TrendState` | No | Previous engine state |

---

## 4. Outputs

### TrendAnalysis

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | `XAUUSD` |
| `timeframe` | `string` | Primary timeframe |
| `timestamp_utc` | `datetime` | Analysis timestamp (UTC) |
| `direction` | `enum` | `bullish`, `bearish`, `sideways`, `undetermined` |
| `strength` | `decimal` | 0.0–1.0 trend strength |
| `momentum` | `enum` | `accelerating`, `steady`, `decelerating`, `undetermined` |
| `mtf_alignment` | `MTFAlignment` | Multi-timeframe alignment summary |
| `confidence` | `decimal` | 0.0–1.0 |
| `evidence` | `string[]` | Human-readable reasoning |
| `state` | `TrendState` | Serializable state |

### MTFAlignment

| Field | Type | Description |
|-------|------|-------------|
| `aligned` | `boolean` | Whether timeframes agree |
| `dominant_direction` | `enum` | `bullish`, `bearish`, `mixed`, `undetermined` |
| `timeframe_directions` | `map` | Direction per timeframe |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Market Data Engine | Upstream | Closed candle events |
| Market Structure Engine | Upstream | Optional structure context |
| Configuration | Internal | Timeframes and parameters |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `analysis.trend.completed` | Analysis cycle complete | `TrendAnalysis` |
| `analysis.trend.direction_changed` | Trend direction changed | Previous and new direction |
| `analysis.trend.alignment_changed` | MTF alignment changed | Alignment details |
| `analysis.trend.exhaustion_detected` | Exhaustion signal detected | Evidence summary |
| `analysis.trend.error` | Analysis failure | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Trigger trend analysis |
| `analysis.structure.completed` | Market Structure Engine | Optional context enrichment |
| `system.config.updated` | Config service | Reload parameters |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `TREND_TIMEFRAMES` | YAML | `M15,H1,H4,D1` | Timeframes for analysis |
| `TREND_PRIMARY_TIMEFRAME` | YAML | `H1` | Primary trend timeframe |
| `TREND_LOOKBACK_BARS` | YAML | `100` | Historical lookback |
| `TREND_MIN_STRENGTH` | YAML | `0.4` | Minimum strength to publish direction |
| `TREND_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `TE_INSUFFICIENT_DATA` | Not enough candles | Return `undetermined`; emit warning |
| `TE_INVALID_CANDLE` | Malformed input | Reject; emit error |
| `TE_TIMEFRAME_MISMATCH` | Missing candles for configured TF | Skip TF; note in evidence |
| `TE_STATE_CORRUPT` | State deserialization fails | Reset state; emit warning |

---

## 10. Success Criteria

- Direction, strength, and momentum are always present in output
- MTF alignment summarizes all configured timeframes
- Evidence explains trend classification rationale
- No entry, stop, or target prices are emitted
- `undetermined` and `sideways` are valid outcomes when evidence is weak
- Output schema is stable for Decision Engine consumption

---

**Implementation sprint:** TBD by Product Owner

# Session Engine — Interface Contract

**Engine ID:** `session`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Determine the active trading session context for XAUUSD (Asian, London, New York, overlaps) and assess session-specific volatility and liquidity characteristics to inform conservative analysis.

---

## 2. Responsibilities

- Identify current active session(s) based on UTC time
- Detect session transitions and overlaps
- Classify session volatility profile (relative, not absolute prediction)
- Flag high-impact session windows (e.g. London open, NY open, overlap)
- Publish session context with evidence
- Emit no trade signals

**Out of scope:** Economic calendar events (News & Macro Engine), trade decisions, execution.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp_utc` | `datetime` | Yes | Current UTC timestamp |
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `recent_candles` | `NormalizedCandle[]` | No | Recent candles for volatility context |
| `timeframe` | `string` | No | Timeframe for volatility measurement (default: `M15`) |

---

## 4. Outputs

### SessionAnalysis

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | `XAUUSD` |
| `timestamp_utc` | `datetime` | Analysis timestamp (UTC) |
| `active_sessions` | `enum[]` | `asian`, `london`, `new_york`, `overlap_london_ny` |
| `primary_session` | `enum` | Dominant active session |
| `session_phase` | `enum` | `opening`, `mid`, `closing`, `inactive` |
| `volatility_profile` | `enum` | `low`, `moderate`, `high`, `undetermined` |
| `is_high_impact_window` | `boolean` | Whether current window is high-impact |
| `next_transition_utc` | `datetime` | Next session transition time |
| `confidence` | `decimal` | 0.0–1.0 |
| `evidence` | `string[]` | Human-readable reasoning |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Market Data Engine | Upstream | Optional recent candles for volatility |
| Configuration | Internal | Session time boundaries |
| Event Bus | Internal | Publish/consume events |

**Does not depend on** analysis engines or Decision Engine.

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `analysis.session.completed` | Analysis cycle complete | `SessionAnalysis` |
| `analysis.session.transition` | Session changed | Previous and new session |
| `analysis.session.high_impact_start` | High-impact window entered | Window details |
| `analysis.session.high_impact_end` | High-impact window exited | Window details |
| `analysis.session.error` | Analysis failure | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Refresh volatility profile |
| `market.tick.received` | Market Data Engine | Optional session tick monitoring |
| `system.config.updated` | Config service | Reload session boundaries |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `SESSION_ASIAN_START_UTC` | YAML | `00:00` | Asian session start (UTC) |
| `SESSION_ASIAN_END_UTC` | YAML | `09:00` | Asian session end (UTC) |
| `SESSION_LONDON_START_UTC` | YAML | `07:00` | London session start (UTC) |
| `SESSION_LONDON_END_UTC` | YAML | `16:00` | London session end (UTC) |
| `SESSION_NY_START_UTC` | YAML | `12:00` | New York session start (UTC) |
| `SESSION_NY_END_UTC` | YAML | `21:00` | New York session end (UTC) |
| `SESSION_HIGH_IMPACT_WINDOWS` | YAML | — | Configurable high-impact windows |
| `SESSION_ENABLED` | YAML | `false` | Engine toggle |

All session times must be configurable. No hardcoded session boundaries in code.

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `SE_INVALID_TIMESTAMP` | Missing or invalid timestamp | Reject input; emit error |
| `SE_CONFIG_INVALID` | Session boundaries misconfigured | Use safe defaults; emit warning |
| `SE_VOLATILITY_DATA_MISSING` | No candles for volatility profile | Return `undetermined` volatility; note in evidence |

---

## 10. Success Criteria

- Active session is correctly derived from UTC time and configured boundaries
- Session transitions are emitted at boundary crossings
- High-impact windows are configurable and documented in evidence
- No trade recommendations are emitted
- `undetermined` volatility profile is valid when candle data is unavailable
- Output schema is stable for Decision Engine consumption

---

**Implementation sprint:** TBD by Product Owner

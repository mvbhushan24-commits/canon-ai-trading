# Risk Engine — Interface Contract

**Engine ID:** `risk`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Assess whether current XAUUSD market conditions meet minimum risk standards for signal consideration, including volatility, spread, event risk, and exposure constraints.

---

## 2. Responsibilities

- Consume outputs from analysis engines and market data
- Measure current spread and volatility conditions
- Evaluate event risk from News & Macro Engine
- Apply account-level risk constraints (when configured)
- Produce a risk verdict with explainable evidence
- Publish risk assessment — does not approve or reject trades directly
- Emit no trade signals

**Out of scope:** Position sizing algorithms for live execution, order placement, signal generation.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `timestamp_utc` | `datetime` | Yes | Assessment timestamp |
| `current_tick` | `NormalizedTick` | Yes | Latest tick from Market Data Engine |
| `trend_context` | `TrendAnalysis` | No | From Trend Engine |
| `session_context` | `SessionAnalysis` | No | From Session Engine |
| `news_macro_context` | `NewsMacroAnalysis` | No | From News & Macro Engine |
| `volatility_candles` | `NormalizedCandle[]` | No | Recent candles for volatility calc |

---

## 4. Outputs

### RiskAssessment

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | `XAUUSD` |
| `timestamp_utc` | `datetime` | Assessment timestamp (UTC) |
| `verdict` | `enum` | `acceptable`, `caution`, `unacceptable`, `undetermined` |
| `spread_current` | `decimal` | Current spread in price units |
| `spread_status` | `enum` | `normal`, `elevated`, `extreme` |
| `volatility_status` | `enum` | `low`, `normal`, `elevated`, `extreme`, `undetermined` |
| `event_risk_status` | `enum` | `none`, `low`, `medium`, `high` |
| `risk_score` | `decimal` | 0.0–1.0 (higher = more risk) |
| `blocking_factors` | `string[]` | Factors preventing acceptable risk |
| `confidence` | `decimal` | 0.0–1.0 |
| `evidence` | `string[]` | Human-readable reasoning |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Market Data Engine | Upstream | Tick and candle data |
| Trend Engine | Upstream | Optional trend context |
| Session Engine | Upstream | Optional session context |
| News & Macro Engine | Upstream | Event risk context |
| Configuration | Internal | Risk thresholds |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `analysis.risk.completed` | Assessment complete | `RiskAssessment` |
| `analysis.risk.verdict_changed` | Verdict changed | Previous and new verdict |
| `analysis.risk.spread_elevated` | Spread exceeds threshold | Spread details |
| `analysis.risk.event_window_active` | High event risk window | Event details |
| `analysis.risk.error` | Assessment failure | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `market.tick.received` | Market Data Engine | Update spread assessment |
| `market.candle.closed` | Market Data Engine | Update volatility assessment |
| `analysis.trend.completed` | Trend Engine | Optional context |
| `analysis.session.completed` | Session Engine | Optional context |
| `analysis.news_macro.completed` | News & Macro Engine | Event risk assessment |
| `analysis.news_macro.window_active` | News & Macro Engine | Immediate risk re-assessment |
| `system.config.updated` | Config service | Reload thresholds |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `RISK_MAX_SPREAD_PIPS` | YAML | `30` | Maximum acceptable spread |
| `RISK_SPREAD_ELEVATED_PIPS` | YAML | `20` | Elevated spread threshold |
| `RISK_VOLATILITY_LOOKBACK_BARS` | YAML | `20` | Bars for volatility calc |
| `RISK_EVENT_BLOCK_WINDOW_MIN` | YAML | `30` | Minutes before/after high-impact events |
| `RISK_MAX_RISK_SCORE` | YAML | `0.7` | Score above which verdict is `unacceptable` |
| `RISK_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `RE_NO_TICK_DATA` | No current tick available | Return `undetermined`; emit warning |
| `RE_INSUFFICIENT_CANDLES` | Not enough candles for volatility | Skip volatility; note in evidence |
| `RE_CONTEXT_UNAVAILABLE` | Upstream context missing | Proceed with available data; note in evidence |
| `RE_THRESHOLD_INVALID` | Config threshold out of range | Use safe default; emit warning |

---

## 10. Success Criteria

- Verdict is always one of the defined enum values
- `blocking_factors` is populated when verdict is `unacceptable` or `caution`
- Evidence explains each factor contributing to the risk score
- No trade signals, entry prices, or position sizes are emitted
- `undetermined` verdict is valid when insufficient data exists
- Output schema is stable for Decision Engine consumption

---

**Implementation sprint:** TBD by Product Owner

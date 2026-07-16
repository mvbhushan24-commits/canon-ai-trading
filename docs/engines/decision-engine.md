# Decision Engine — Interface Contract

**Engine ID:** `decision`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Synthesize all upstream analysis engine outputs into a single explainable trading decision: a qualified signal or an explicit **NO TRADE** outcome.

---

## 2. Responsibilities

- Consume outputs from all analysis engines
- Apply configured confluence rules to weigh evidence
- Produce a `SIGNAL`, `NO_TRADE`, or `WAIT` decision
- Include full reasoning chain for every decision
- Assign confidence score to every outcome
- Publish decision events for Telegram Engine and Dashboard
- Never force a signal when evidence is insufficient

**Out of scope:** Order execution, position management, Telegram delivery (Telegram Engine), UI rendering (Dashboard).

**Constitutional rule:** A `NO_TRADE` decision is a successful outcome whenever evidence is insufficient.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `timestamp_utc` | `datetime` | Yes | Decision timestamp |
| `market_structure` | `StructureAnalysis` | No | From Market Structure Engine |
| `liquidity` | `LiquidityAnalysis` | No | From Liquidity Engine |
| `smart_money` | `SmartMoneyAnalysis` | No | From Smart Money Engine |
| `trend` | `TrendAnalysis` | No | From Trend Engine |
| `session` | `SessionAnalysis` | No | From Session Engine |
| `news_macro` | `NewsMacroAnalysis` | No | From News & Macro Engine |
| `risk` | `RiskAssessment` | Yes | From Risk Engine |
| `current_price` | `decimal` | Yes | Current mid price from Market Data Engine |

---

## 4. Outputs

### TradingDecision

| Field | Type | Description |
|-------|------|-------------|
| `decision_id` | `string` | Unique decision identifier |
| `symbol` | `string` | `XAUUSD` |
| `timestamp_utc` | `datetime` | Decision timestamp (UTC) |
| `decision` | `enum` | `SIGNAL`, `NO_TRADE`, `WAIT` |
| `direction` | `enum` | `BUY`, `SELL`, `NONE` |
| `confidence` | `decimal` | 0.0–1.0 overall confidence |
| `entry_zone` | `PriceZone` | Suggested entry zone (signal only) |
| `stop_loss` | `decimal` | Suggested stop loss (signal only) |
| `take_profit` | `decimal[]` | Suggested take profit levels (signal only) |
| `risk_reward_ratio` | `decimal` | Estimated R:R (signal only) |
| `confluence_score` | `decimal` | 0.0–1.0 engine agreement score |
| `engine_summaries` | `EngineSummary[]` | Per-engine input summary |
| `reasoning` | `string[]` | Full explainability chain |
| `blocking_reasons` | `string[]` | Why NO_TRADE or WAIT was chosen |
| `valid_until_utc` | `datetime` | Decision expiry time |

### PriceZone

| Field | Type | Description |
|-------|------|-------------|
| `high` | `decimal` | Zone upper bound |
| `low` | `decimal` | Zone lower bound |

### EngineSummary

| Field | Type | Description |
|-------|------|-------------|
| `engine_id` | `string` | Source engine identifier |
| `bias` | `string` | Engine bias/direction summary |
| `confidence` | `decimal` | Engine confidence |
| `available` | `boolean` | Whether engine output was present |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Market Data Engine | Upstream | Current price |
| Market Structure Engine | Upstream | Structure analysis |
| Liquidity Engine | Upstream | Liquidity analysis |
| Smart Money Engine | Upstream | SMC analysis |
| Trend Engine | Upstream | Trend analysis |
| Session Engine | Upstream | Session context |
| News & Macro Engine | Upstream | News/macro context |
| Risk Engine | Upstream | Risk assessment (required) |
| Configuration | Internal | Confluence rules and thresholds |
| SQLite | Internal | Decision history persistence |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `decision.completed` | Decision cycle complete | `TradingDecision` |
| `decision.signal.published` | SIGNAL decision made | Full signal with reasoning |
| `decision.no_trade.published` | NO_TRADE decision made | Blocking reasons |
| `decision.wait.published` | WAIT decision made | Wait reasons |
| `decision.expired` | Decision validity expired | Decision reference |
| `decision.error` | Decision failure | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `analysis.structure.completed` | Market Structure Engine | Update structure input |
| `analysis.liquidity.completed` | Liquidity Engine | Update liquidity input |
| `analysis.smart_money.completed` | Smart Money Engine | Update SMC input |
| `analysis.trend.completed` | Trend Engine | Update trend input |
| `analysis.session.completed` | Session Engine | Update session input |
| `analysis.news_macro.completed` | News & Macro Engine | Update news/macro input |
| `analysis.risk.completed` | Risk Engine | Update risk input (required) |
| `market.tick.received` | Market Data Engine | Update current price |
| `system.config.updated` | Config service | Reload confluence rules |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `DECISION_MIN_CONFLUENCE` | YAML | `0.6` | Minimum confluence for SIGNAL |
| `DECISION_MIN_CONFIDENCE` | YAML | `0.65` | Minimum confidence for SIGNAL |
| `DECISION_REQUIRE_RISK_ACCEPTABLE` | YAML | `true` | Block signal if risk not acceptable |
| `DECISION_VALIDITY_MINUTES` | YAML | `60` | Decision expiry duration |
| `DECISION_ENGINE_WEIGHTS` | YAML | — | Per-engine weight map |
| `DECISION_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `DE_RISK_UNAVAILABLE` | Risk assessment missing | Emit `NO_TRADE`; reason: risk unavailable |
| `DE_PRICE_UNAVAILABLE` | No current price | Emit `WAIT`; reason: price unavailable |
| `DE_INSUFFICIENT_CONFLUENCE` | Confluence below threshold | Emit `NO_TRADE`; list blocking reasons |
| `DE_ENGINE_OUTPUT_STALE` | Upstream output exceeds max age | Exclude stale engine; note in reasoning |
| `DE_CONFIG_INVALID` | Confluence config invalid | Emit error; do not decide |

---

## 10. Success Criteria

- Every decision includes a full `reasoning` array
- `NO_TRADE` is emitted when confluence or confidence is below threshold — this is valid success
- `blocking_reasons` is populated for every `NO_TRADE` and `WAIT` decision
- SIGNAL decisions include entry zone, stop loss, take profit, and R:R
- No order is placed — manual execution only (v1.0)
- Decision output schema is stable for Telegram Engine and Dashboard consumption
- Engine summaries document which engines contributed and which were unavailable

---

**Implementation sprint:** TBD by Product Owner

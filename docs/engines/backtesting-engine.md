# Backtesting Engine — Interface Contract

**Engine ID:** `backtesting`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD  
**Version Scope:** Post v1.0 — contract defined for future sprint planning

---

## 1. Purpose

Replay historical XAUUSD data through the analysis and decision pipeline to evaluate signal quality, consistency, and explainability over a defined period — without live market connection or trade execution.

---

## 2. Responsibilities

- Load historical candle data for configured periods
- Feed historical data to analysis engines in chronological order
- Collect Decision Engine outputs for each replay step
- Calculate performance metrics (win rate, R:R achieved, drawdown)
- Produce explainability audit trail for every replayed decision
- Publish backtest results — no live trading

**Out of scope:** Live MT5 connection during backtest, order execution, real capital, Telegram delivery.

**Note:** This engine is outside v1.0 scope. Contract is defined for architectural completeness only.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `from_utc` | `datetime` | Yes | Backtest start date |
| `to_utc` | `datetime` | Yes | Backtest end date |
| `timeframes` | `string[]` | Yes | Timeframes to replay |
| `initial_balance` | `decimal` | No | Simulated account balance |
| `engine_config_override` | `map` | No | Override engine configs for test |
| `decision_rules_override` | `map` | No | Override decision confluence rules |

---

## 4. Outputs

### BacktestResult

| Field | Type | Description |
|-------|------|-------------|
| `backtest_id` | `string` | Unique backtest run identifier |
| `symbol` | `string` | `XAUUSD` |
| `from_utc` | `datetime` | Backtest start |
| `to_utc` | `datetime` | Backtest end |
| `total_decisions` | `integer` | Total decisions generated |
| `signal_count` | `integer` | SIGNAL decisions |
| `no_trade_count` | `integer` | NO_TRADE decisions |
| `wait_count` | `integer` | WAIT decisions |
| `metrics` | `BacktestMetrics` | Performance metrics |
| `decisions` | `TradingDecision[]` | All replayed decisions |
| `audit_trail` | `AuditEntry[]` | Explainability audit log |
| `completed_at_utc` | `datetime` | Run completion time |

### BacktestMetrics

| Field | Type | Description |
|-------|------|-------------|
| `win_rate` | `decimal` | Percentage of winning signals |
| `average_rr` | `decimal` | Average risk:reward achieved |
| `max_drawdown` | `decimal` | Maximum simulated drawdown |
| `profit_factor` | `decimal` | Gross profit / gross loss |
| `no_trade_rate` | `decimal` | Percentage of NO_TRADE decisions |

### AuditEntry

| Field | Type | Description |
|-------|------|-------------|
| `timestamp_utc` | `datetime` | Decision timestamp |
| `decision_id` | `string` | Decision reference |
| `engine_inputs` | `map` | Snapshot of engine inputs |
| `reasoning` | `string[]` | Decision reasoning chain |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Historical Data Store | Internal | SQLite or CSV historical candles |
| All Analysis Engines | Internal | Replayed in chronological order |
| Decision Engine | Internal | Generates replayed decisions |
| Configuration | Internal | Backtest parameters |
| Event Bus | Internal | Internal replay events (not live bus) |

**Does not depend on** MT5 live connection or Telegram Engine.

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `backtest.started` | Backtest run begins | Run configuration |
| `backtest.step.completed` | One replay step complete | Step decision summary |
| `backtest.completed` | Backtest run finished | `BacktestResult` |
| `backtest.failed` | Backtest run failed | Error details |
| `backtest.progress` | Progress update | Percentage complete |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `system.backtest.requested` | Orchestrator / API | Start backtest run |
| `system.config.updated` | Config service | Reload backtest defaults |

During replay, consumes internal simulated versions of analysis engine output events.

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `BACKTEST_DATA_SOURCE` | YAML | `sqlite` | Historical data source |
| `BACKTEST_DEFAULT_BALANCE` | YAML | `10000` | Simulated starting balance |
| `BACKTEST_MAX_DURATION_DAYS` | YAML | `365` | Maximum backtest period |
| `BACKTEST_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `BE_NO_HISTORICAL_DATA` | No data for requested period | Fail run; emit error |
| `BE_PERIOD_INVALID` | from_utc >= to_utc | Reject input; emit error |
| `BE_ENGINE_UNAVAILABLE` | Required engine not available | Fail run; list missing engines |
| `BE_REPLAY_TIMEOUT` | Run exceeds max duration | Abort; emit partial results |
| `BE_METRICS_CALC_FAILED` | Metrics calculation error | Complete run; note metrics unavailable |

---

## 10. Success Criteria

- Replay produces identical decision schema as live Decision Engine
- Every replayed decision has a corresponding audit trail entry
- NO_TRADE rate is reported as a metric — not treated as failure
- No live market connection is made during backtest
- No real orders are placed
- Results are persistable and consumable by Dashboard (future sprint)
- Contract is complete for future implementation planning

---

**Implementation sprint:** Post v1.0 — TBD by Product Owner

# Market Data Engine — Interface Contract

**Engine ID:** `market_data`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD  
**Broker:** XMGlobal via MetaTrader 5

---

## 1. Purpose

Provide normalized, timestamped live and historical XAUUSD market data to all downstream analysis engines through a single authoritative data source.

---

## 2. Responsibilities

- Connect to XMGlobal MetaTrader 5 terminal (when implemented)
- Subscribe to configured symbols and timeframes
- Normalize tick and OHLCV candle data into canonical schemas
- Detect and report data gaps, stale feeds, and connection loss
- Publish market data events to the event bus
- Persist raw and normalized data to SQLite (when enabled)
- Expose no trading or signal logic

**Out of scope:** Analysis, structure detection, signal generation, order execution.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | `string` | Yes | Trading symbol (default: `XAUUSD`) |
| `timeframes` | `string[]` | Yes | Candle timeframes to subscribe (e.g. `M1`, `M5`, `M15`, `H1`, `H4`, `D1`) |
| `tick_enabled` | `boolean` | No | Enable tick-level streaming (default: `true`) |
| `history_bars` | `integer` | No | Initial historical bars to load per timeframe |
| `request_id` | `string` | No | Correlation ID for on-demand history requests |

### On-Demand History Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `symbol` | `string` | Yes | Symbol to fetch |
| `timeframe` | `string` | Yes | Candle timeframe |
| `from_utc` | `datetime` | Yes | Start of range (UTC) |
| `to_utc` | `datetime` | Yes | End of range (UTC) |

---

## 4. Outputs

### Normalized Tick

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | Instrument symbol |
| `bid` | `decimal` | Current bid price |
| `ask` | `decimal` | Current ask price |
| `spread` | `decimal` | Ask minus bid |
| `timestamp_utc` | `datetime` | Tick timestamp (UTC) |
| `source` | `string` | Always `mt5_xmglobal` |

### Normalized Candle

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | Instrument symbol |
| `timeframe` | `string` | Candle period |
| `open` | `decimal` | Open price |
| `high` | `decimal` | High price |
| `low` | `decimal` | Low price |
| `close` | `decimal` | Close price |
| `volume` | `integer` | Tick volume |
| `open_time_utc` | `datetime` | Candle open (UTC) |
| `close_time_utc` | `datetime` | Candle close (UTC) |
| `is_closed` | `boolean` | Whether candle is finalized |

### Engine Status Output

| Field | Type | Description |
|-------|------|-------------|
| `status` | `enum` | `connected`, `disconnected`, `degraded`, `error` |
| `last_tick_utc` | `datetime` | Last received tick timestamp |
| `last_error` | `string` | Most recent error message (if any) |
| `latency_ms` | `integer` | Estimated feed latency |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| MetaTrader 5 | External | XMGlobal terminal and Python MT5 library |
| SQLite | Internal | Optional persistence layer |
| Configuration | Internal | `.env` and YAML settings |
| Event Bus | Internal | Publish market data events |

**Does not depend on** any analysis or decision engine.

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `market.tick.received` | New tick received | Normalized tick object |
| `market.candle.updated` | Forming candle update | Normalized candle (`is_closed: false`) |
| `market.candle.closed` | Candle finalized | Normalized candle (`is_closed: true`) |
| `market.connection.established` | MT5 connection successful | Connection metadata |
| `market.connection.lost` | MT5 connection lost | Error details |
| `market.data.gap_detected` | Missing bars detected | Gap range and timeframe |
| `market.history.loaded` | On-demand history complete | Bar count and range |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `system.config.updated` | Config service | Reload symbol/timeframe subscriptions |
| `system.shutdown.requested` | Orchestrator | Gracefully disconnect MT5 |

This engine does **not** consume analysis or decision events.

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `TRADING_SYMBOL` | `.env` | `XAUUSD` | Primary symbol |
| `BROKER` | `.env` | `XMGlobal` | Broker identifier |
| `MT5_TERMINAL_PATH` | `.env` | — | Path to MT5 terminal |
| `MT5_LOGIN` | `.env` | — | Account login |
| `MT5_PASSWORD` | `.env` | — | Account password |
| `MT5_SERVER` | `.env` | — | Broker server name |
| `MARKET_DATA_TIMEFRAMES` | YAML | `M1,M5,M15,H1,H4,D1` | Subscribed timeframes |
| `MARKET_DATA_TICK_ENABLED` | YAML | `true` | Enable tick stream |
| `MARKET_DATA_HISTORY_BARS` | YAML | `500` | Initial history depth |
| `MARKET_DATA_STALE_THRESHOLD_SEC` | YAML | `30` | Stale feed threshold |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `MDE_CONN_FAILED` | MT5 initialization fails | Emit `market.connection.lost`; status `error` |
| `MDE_AUTH_FAILED` | Invalid login credentials | Emit error event; do not retry indefinitely |
| `MDE_SYMBOL_UNAVAILABLE` | Symbol not found in MT5 | Emit error; halt symbol subscription |
| `MDE_STALE_FEED` | No ticks within threshold | Status `degraded`; emit warning event |
| `MDE_GAP_DETECTED` | Missing candle sequence | Emit `market.data.gap_detected` |
| `MDE_HISTORY_FAILED` | History request fails | Return error in on-demand response |

---

## 10. Success Criteria

- Normalized tick and candle outputs conform to schema for every published event
- All timestamps are UTC and monotonically consistent per symbol/timeframe
- Connection state is accurately reflected in status output
- No analysis or trading logic exists in this engine
- Configuration is fully external with no hardcoded credentials
- Downstream engines can operate using only published events and schemas
- Gap and stale-feed conditions are detected and reported, not silently ignored

---

**Implementation sprint:** TBD by Product Owner

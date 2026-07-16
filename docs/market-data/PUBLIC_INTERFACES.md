# Market Data Engine — Public Interfaces

This document describes every class, method, schema, and exception exported from `backend.engines.market_data` (see `__all__` in `__init__.py`).

Internal classes (`MT5ConnectionManager`, `BrokerValidator`, etc.) are documented in [ARCHITECTURE.md](./ARCHITECTURE.md) but are not part of the public package API.

---

## Package Import

```python
from backend.engines.market_data import (
    MarketDataEngine,
    MarketDataConfig,
    load_market_data_config,
    NormalizedTick,
    NormalizedCandle,
    EventPublisher,
    # ... see __all__
)
```

---

## MarketDataEngine

**Module:** `engine.py`  
**Purpose:** Main orchestrator for all market data operations.

### Constructor

```python
MarketDataEngine(
    config: MarketDataConfig | None = None,
    client: MT5ClientProtocol | None = None,
    event_publisher: EventPublisher | None = None,
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `config` | `load_market_data_config()` | Engine configuration |
| `client` | `create_mt5_client()` | MT5 client (inject mock for tests) |
| `event_publisher` | `EventPublisher()` | Event publisher instance |

**Initializes:** normalizer, validator, connection manager, broker validator, symbol manager, historical loader, live loader.

---

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `MarketDataConfig` | Active configuration |
| `event_publisher` | `EventPublisher` | Event publisher for subscriptions |

---

### Methods

#### `start() -> None`

Connect to MT5, validate broker, load and validate symbol metadata.

| | |
|---|---|
| **Inputs** | None (uses `self._config`) |
| **Outputs** | None |
| **Exceptions** | `MT5ConnectionError`, `MT5AuthenticationError`, `SymbolUnavailableError`, any `MarketDataError` |
| **Events** | `market.connection.established` on success; `market.connection.lost` on init failure |

---

#### `stop() -> None`

Gracefully disconnect MT5 and mark engine as stopped.

| | |
|---|---|
| **Inputs** | None |
| **Outputs** | None |
| **Exceptions** | None (logs if already disconnected) |

---

#### `get_status() -> EngineStatus`

Return current operational status including connection state, last tick, latency.

| | |
|---|---|
| **Inputs** | None |
| **Outputs** | `EngineStatus` |
| **Exceptions** | None (latency errors are swallowed → `latency_ms=None`) |

---

#### `load_historical_candles(symbol=None, timeframe=None, count=None) -> list[NormalizedCandle]`

Load recent historical OHLC bars.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `symbol` | `config.symbol` | Instrument symbol |
| `timeframe` | `config.timeframes[0]` | Candle period |
| `count` | `config.history_bars` | Number of bars |

| | |
|---|---|
| **Outputs** | `list[NormalizedCandle]` |
| **Exceptions** | `SymbolUnavailableError`, `HistoryLoadError`, `InvalidTimeframeError` |
| **Events** | `market.data.gap_detected` if gaps found |

---

#### `load_historical_range(request: HistoryRequest) -> HistoryResponse`

Load historical candles for a UTC date range.

| | |
|---|---|
| **Inputs** | `HistoryRequest` |
| **Outputs** | `HistoryResponse` (includes `error` field on failure instead of raising) |
| **Exceptions** | `SymbolUnavailableError`, `InvalidTimeframeError` |
| **Events** | `market.history.loaded` on success; `market.data.gap_detected` if gaps |

---

#### `get_latest_candle(symbol=None, timeframe=None) -> NormalizedCandle`

Retrieve the current forming candle.

| | |
|---|---|
| **Outputs** | `NormalizedCandle` with `is_closed=False` |
| **Exceptions** | `SymbolUnavailableError`, `InvalidTimeframeError` |
| **Events** | `market.candle.updated` |

---

#### `get_latest_tick(symbol=None) -> NormalizedTick`

Retrieve the latest normalized tick.

| | |
|---|---|
| **Outputs** | `NormalizedTick` |
| **Exceptions** | `SymbolUnavailableError` (includes tick disabled case) |
| **Events** | `market.tick.received` |

---

#### `validate_candles(candles: list[NormalizedCandle]) -> ValidationResult`

Validate a list of normalized candles.

| | |
|---|---|
| **Inputs** | `list[NormalizedCandle]` |
| **Outputs** | `ValidationResult` |
| **Exceptions** | None |

---

#### `check_stale_feed(symbol=None) -> None`

Raise if the latest tick exceeds `stale_threshold_sec`.

| | |
|---|---|
| **Exceptions** | `StaleFeedError`, `SymbolUnavailableError` |

---

#### `get_symbol_metadata(symbol: str) -> SymbolMetadata`

Validate symbol and return metadata.

| | |
|---|---|
| **Exceptions** | `SymbolUnavailableError` |

---

#### `list_symbols() -> list[str]`

Return sorted list of loaded symbol names.

| | |
|---|---|
| **Outputs** | `list[str]` |
| **Exceptions** | None |

---

#### `handle_shutdown_event() -> None`

Handle `system.shutdown.requested` — calls `stop()`.

---

#### `handle_config_updated(config: MarketDataConfig) -> None`

Handle `system.config.updated` — replaces in-memory config (does not reconnect).

---

## MarketDataConfig

**Module:** `config.py`  
**Base:** `pydantic.BaseModel`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | `str` | `"XAUUSD"` | Primary trading symbol |
| `broker` | `str` | `"XMGlobal"` | Broker identifier |
| `timeframes` | `list[str]` | `[M1,M5,M15,H1,H4,D1]` | Subscribed timeframes |
| `tick_enabled` | `bool` | `true` | Enable tick streaming |
| `history_bars` | `int` | `500` | Default historical depth |
| `stale_threshold_sec` | `int` | `30` | Stale feed threshold |
| `mt5_terminal_path` | `str` | `""` | Path to MT5 terminal |
| `mt5_login` | `str` | `""` | Account login |
| `mt5_password` | `str` | `""` | Account password |
| `mt5_server` | `str` | `""` | Broker server name |
| `yaml_config_path` | `str` | `"config/settings.yaml"` | Loaded YAML path |

**Validation errors:** `ValueError` for invalid timeframes, `history_bars < 1`, or `stale_threshold_sec < 1`.

---

## load_market_data_config()

```python
load_market_data_config(
    settings: Settings | None = None,
    yaml_path: Path | None = None,
) -> MarketDataConfig
```

Merges `backend.core.config.Settings` (from `.env`) with `config/settings.yaml` `market_data` section.

---

## Schemas

### EngineConnectionStatus (enum)

| Value | Description |
|-------|-------------|
| `connected` | MT5 session active |
| `disconnected` | Not connected or engine not started |
| `degraded` | Connected with errors or stale conditions |
| `error` | Connection failure state |

### NormalizedTick

See [DATA_PIPELINE.md](./DATA_PIPELINE.md). Frozen Pydantic model.

### NormalizedCandle

See [DATA_PIPELINE.md](./DATA_PIPELINE.md). Frozen Pydantic model.

### EngineStatus

| Field | Type | Description |
|-------|------|-------------|
| `status` | `EngineConnectionStatus` | Connection state |
| `last_tick_utc` | `datetime \| None` | Last tick timestamp |
| `last_error` | `str \| None` | Most recent error message |
| `latency_ms` | `int \| None` | Estimated feed latency |

### SymbolMetadata

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Symbol name |
| `description` | `str` | Broker description |
| `digits` | `int` | Price decimal places |
| `point` | `Decimal` | Minimum price step |
| `trade_mode` | `int` | MT5 trade mode |
| `visible` | `bool` | Visible in terminal |
| `session_deals` | `int` | Session deal count |
| `session_buy_orders` | `int` | Session buy orders |
| `session_sell_orders` | `int` | Session sell orders |

### HistoryRequest

| Field | Type | Required |
|-------|------|----------|
| `symbol` | `str` | Yes |
| `timeframe` | `str` | Yes |
| `from_utc` | `datetime` | Yes |
| `to_utc` | `datetime` | Yes |
| `request_id` | `str \| None` | No |

### HistoryResponse

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | `str \| None` | Correlation ID |
| `symbol` | `str` | Symbol fetched |
| `timeframe` | `str` | Timeframe fetched |
| `candles` | `list[NormalizedCandle]` | Result candles |
| `bar_count` | `int` | Number of bars |
| `from_utc` | `datetime \| None` | Request start |
| `to_utc` | `datetime \| None` | Request end |
| `error` | `str \| None` | Error message if failed |

### GapInfo

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Affected symbol |
| `timeframe` | `str` | Affected timeframe |
| `gap_start_utc` | `datetime` | First missing bar time |
| `gap_end_utc` | `datetime` | Last missing bar time |
| `missing_bars` | `int` | Count of missing bars |

### ValidationResult

| Field | Type | Description |
|-------|------|-------------|
| `is_valid` | `bool` | Overall validity |
| `gaps` | `list[GapInfo]` | Detected gaps |
| `duplicate_count` | `int` | Duplicate timestamps |
| `invalid_timestamp_count` | `int` | Bad timestamps |
| `invalid_ohlc_count` | `int` | OHLC inconsistencies |
| `errors` | `list[str]` | Human-readable error messages |

---

## EventPublisher

**Module:** `events.py`

### Methods

| Method | Inputs | Events Published |
|--------|--------|------------------|
| `subscribe(event_type, handler)` | Event type or `"*"` | — |
| `publish(event: MarketEvent)` | `MarketEvent` | Dispatches to handlers |
| `publish_tick_received(tick)` | `NormalizedTick` | `market.tick.received` |
| `publish_candle_updated(candle)` | `NormalizedCandle` | `market.candle.updated` |
| `publish_candle_closed(candle)` | `NormalizedCandle` | `market.candle.closed` |
| `publish_connection_established(...)` | broker, terminal_name | `market.connection.established` |
| `publish_connection_lost(...)` | error, timestamp | `market.connection.lost` |
| `publish_gap_detected(gap)` | `GapInfo` | `market.data.gap_detected` |
| `publish_history_loaded(...)` | symbol, timeframe, range | `market.history.loaded` |
| `clear_handlers()` | None | Clears all subscriptions |

---

## MarketEvent

**Module:** `events.py`

| Attribute | Type | Description |
|-----------|------|-------------|
| `event_id` | `str` | UUID |
| `timestamp_utc` | `datetime` | Event time (UTC) |
| `symbol` | `str \| None` | Related symbol |
| `source_engine` | `str` | Always `"market_data"` |
| `event_type` | `str` | Contract event name |
| `payload` | `dict` | Event data |

**Method:** `to_dict() -> dict[str, Any]`

---

## Timeframe Utilities

### Timeframe (enum)

`M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`

### SUPPORTED_TIMEFRAMES

`frozenset[str]` of all supported timeframe identifiers.

### validate_timeframe(timeframe: str) -> str

Normalize and validate a timeframe string.

| | |
|---|---|
| **Exceptions** | `InvalidTimeframeError` |

### validate_timeframes(timeframes: list[str]) -> list[str]

Validate a list, preserving order.

### timeframe_duration(timeframe: str) -> timedelta

Return candle duration for a validated timeframe. *(Internal module also exports `resolve_mt5_timeframe` — not in public `__all__`.)*

---

## Exceptions

All inherit from `MarketDataError` → `CanonTradingError`.

| Exception | Code | When Raised |
|-----------|------|-------------|
| `MarketDataError` | `MDE_ERROR` | Base class |
| `MT5ConnectionError` | `MDE_CONN_FAILED` | MT5 init/terminal failure |
| `MT5AuthenticationError` | `MDE_AUTH_FAILED` | Login failure |
| `SymbolUnavailableError` | `MDE_SYMBOL_UNAVAILABLE` | Symbol not found / tick disabled |
| `StaleFeedError` | `MDE_STALE_FEED` | Feed exceeds stale threshold |
| `GapDetectedError` | `MDE_GAP_DETECTED` | Gap condition (reserved) |
| `HistoryLoadError` | `MDE_HISTORY_FAILED` | Historical fetch failure |
| `InvalidTimeframeError` | `MDE_INVALID_TIMEFRAME` | Unsupported timeframe |

**Common attributes:** `message: str`, `code: str`, `details: dict[str, Any]`

---

## FastAPI Integration

The running backend exposes the engine on application state:

```python
# Available during request handling after startup
app.state.market_data_engine  # MarketDataEngine instance
```

No REST routes expose market data yet (future sprint).

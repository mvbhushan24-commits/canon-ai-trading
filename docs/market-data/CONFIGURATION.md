# Market Data Engine — Configuration Guide

All configuration is external. No credentials, symbols, or trading parameters are hardcoded in the engine.

Configuration is loaded from two sources:

1. **Environment variables** (`.env`) — secrets and core trading settings
2. **YAML file** (`config/settings.yaml`) — market data engine parameters

The loader `load_market_data_config()` merges both into a single `MarketDataConfig` object.

---

## Environment Variables (`.env`)

Copy from `.env.example`:

```powershell
copy .env.example .env
```

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `Canon AI Trading` | Application display name |
| `APP_VERSION` | `0.1.0` | Version string |
| `ENVIRONMENT` | `development` | Runtime environment |
| `DEBUG` | `false` | Debug mode |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### API Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |
| `ENABLE_API_DOCS` | `false` | Enable OpenAPI docs |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/canon_ai_trading.db` | SQLite connection (future persistence) |

### Trading / MT5 (required for live operation)

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADING_SYMBOL` | `XAUUSD` | Primary instrument symbol. **XMGlobal often uses `GOLD.i#` for gold.** |
| `BROKER` | `XMGlobal` | Broker identifier (logged, not validated against MT5 company string) |
| `MT5_TERMINAL_PATH` | *(empty)* | Absolute path to `terminal64.exe`. Empty = auto-detect running terminal |
| `MT5_LOGIN` | *(empty)* | Numeric account login. Required if terminal has no active session |
| `MT5_PASSWORD` | *(empty)* | Account password |
| `MT5_SERVER` | *(empty)* | Broker server name (e.g. `XMGlobal-MT5 3`) |

### Other

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Future notification sprint |
| `TELEGRAM_CHAT_ID` | *(empty)* | Future notification sprint |

---

## YAML Configuration (`config/settings.yaml`)

Copy from example:

```powershell
copy config\settings.yaml.example config\settings.yaml
```

### Application Metadata

```yaml
app:
  name: "Canon AI Trading"
  version: "0.1.0"
  symbol: "XAUUSD"      # Informational; engine uses market_data.symbol
  broker: "XMGlobal"
```

### Market Data Engine

```yaml
market_data:
  symbol: "XAUUSD"       # Primary symbol (overrides env default if set)
  broker: "XMGlobal"
  timeframes:
    - M1
    - M5
    - M15
    - M30
    - H1
    - H4
    - D1
  tick_enabled: true     # Enable live tick retrieval
  history_bars: 500      # Default bars per historical load
  stale_threshold_sec: 30  # Seconds before feed considered stale
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | string | from `TRADING_SYMBOL` env | Instrument to trade/load |
| `broker` | string | from `BROKER` env | Broker name |
| `timeframes` | list | `[M1,M5,M15,H1,H4,D1]` | Supported candle periods |
| `tick_enabled` | bool | `true` | When `false`, `get_latest_tick()` raises |
| `history_bars` | int | `500` | Bars fetched when count not specified |
| `stale_threshold_sec` | int | `30` | Max tick age before `StaleFeedError` |

**Alternative timeframes format:** comma-separated string via `MARKET_DATA_TIMEFRAMES` key (legacy contract name).

### Engine Toggles

```yaml
engines:
  market_data: true       # Sprint 1 — implemented
  market_structure: false # Sprint 2+
  # ...
```

Engine toggles are reserved for future orchestrator use. Sprint 1 starts the market data engine unconditionally from `backend/main.py` lifespan.

### Logging

```yaml
logging:
  level: "INFO"
```

Note: FastAPI startup uses `LOG_LEVEL` from `.env` via `configure_logging()`. YAML logging level is not yet wired to the logging module.

---

## Example: XMGlobal Live Configuration

**.env**

```env
TRADING_SYMBOL=GOLD.i#
BROKER=XMGlobal
MT5_TERMINAL_PATH=
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
LOG_LEVEL=INFO
```

When MT5 terminal is already logged in, credentials can remain empty.

**config/settings.yaml**

```yaml
market_data:
  symbol: "GOLD.i#"
  broker: "XMGlobal"
  timeframes:
    - M1
    - M5
    - M15
    - M30
    - H1
    - H4
    - D1
  tick_enabled: true
  history_bars: 500
  stale_threshold_sec: 30
```

---

## Configuration Loading Order

```
1. pydantic-settings loads .env → Settings
2. yaml_loader loads config/settings.yaml
3. load_market_data_config() merges:
     symbol     ← yaml market_data.symbol OR Settings.symbol
     broker     ← yaml market_data.broker OR Settings.broker
     timeframes ← yaml market_data.timeframes OR default list
     mt5_*      ← always from Settings (.env)
```

---

## Validation Rules

| Rule | Error |
|------|-------|
| Unknown timeframe in list | `ValueError` / `InvalidTimeframeError` |
| `history_bars < 1` | `ValueError` |
| `stale_threshold_sec < 1` | `ValueError` |
| Missing YAML file | Empty dict — env defaults used |
| Missing `.env` file | pydantic-settings defaults used |

---

## Security

- **Never commit** `.env` or `config/settings.yaml` with real credentials
- Use `.env.example` and `config/settings.yaml.example` as templates only
- MT5 passwords and Telegram tokens must stay out of version control

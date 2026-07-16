# Market Data Engine

**Status:** Sprint 1 — implemented

**Engine ID:** `market_data`

**Responsibility:** Connect to XMGlobal via MetaTrader 5 and provide normalized live and historical XAUUSD market data.

## Components

| Module | Responsibility |
|--------|----------------|
| `engine.py` | Main orchestrator |
| `connection.py` | MT5 connection manager |
| `broker.py` | Broker validation |
| `symbols.py` | Symbol manager |
| `timeframes.py` | Timeframe manager |
| `historical.py` | Historical OHLC loader |
| `live.py` | Live tick/candle loader |
| `normalizer.py` | MT5 → canonical schema |
| `validator.py` | Gap, duplicate, OHLC validation |
| `events.py` | Contract event publisher |
| `config.py` | External configuration |

## Interface Contract

See `docs/engines/market-data-engine.md`.

## Configuration

Environment (`.env`): `TRADING_SYMBOL`, `BROKER`, `MT5_*`

YAML (`config/settings.yaml`): `market_data.timeframes`, `tick_enabled`, `history_bars`, `stale_threshold_sec`

## Usage

```python
from backend.engines.market_data import MarketDataEngine

engine = MarketDataEngine()
engine.start()
candles = engine.load_historical_candles(timeframe="H1")
engine.stop()
```

**Implementation sprint:** Sprint 1 (complete)

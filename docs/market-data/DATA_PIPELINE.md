# Market Data Engine — Data Pipeline

This document describes the end-to-end flow of market data from MetaTrader 5 through the Canon AI Trading Market Data Engine to future downstream consumers.

---

## Pipeline Overview

```
                    ┌─────────────────────────────────────────┐
                    │           MetaTrader 5 (XMGlobal)      │
                    │  Terminal · Account · Symbol · Ticks   │
                    └───────────────────┬─────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │              MT5Client                   │
                    │   (Python MetaTrader5 library wrapper)   │
                    └───────────────────┬─────────────────────┘
                                        │
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │         MT5ConnectionManager             │
                    │   initialize · verify session · login    │
                    └───────────────────┬─────────────────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
              ┌───────────────────┐       ┌───────────────────┐
              │  BrokerValidator   │       │   SymbolManager    │
              │ connection·symbol  │       │  load · validate   │
              └─────────┬─────────┘       └─────────┬─────────┘
                        │                           │
                        └─────────────┬─────────────┘
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │           MarketDataEngine               │
                    │              (Orchestrator)              │
                    └───────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
        ┌───────────────────┐ ┌───────────────┐ ┌───────────────────┐
        │ HistoricalDataLoader│ │LiveMarketData │ │   DataValidator    │
        │  copy_rates_*()    │ │    Loader     │ │  (on-demand check) │
        └─────────┬─────────┘ └───────┬───────┘ └───────────────────┘
                  │                   │
                  └─────────┬─────────┘
                            ▼
              ┌─────────────────────────┐
              │   MarketDataNormalizer   │
              │  MT5 raw → canonical     │
              └─────────────┬───────────┘
                            ▼
              ┌─────────────────────────┐
              │      DataValidator       │
              │ gaps·dupes·OHLC·time    │
              └─────────────┬───────────┘
                            ▼
              ┌─────────────────────────┐
              │      EventPublisher      │
              │  market.* contract events│
              └─────────────┬───────────┘
                            ▼
              ┌─────────────────────────┐
              │   Future Analysis Engines│
              │  structure·liquidity·SMC │
              │  trend·risk·decision     │
              └─────────────────────────┘
```

---

## Simplified ASCII Pipeline

```
MT5
 ↓
Connection
 ↓
Historical Loader ──┐
 ↓                  │
Live Loader ────────┤
 ↓                  │
Normalizer ←────────┘
 ↓
Validator
 ↓
Events
 ↓
Future Analysis Engines
```

---

## Data Types at Each Stage

| Stage | Input | Output |
|-------|-------|--------|
| MT5 | Broker feed | Raw ticks, numpy OHLCV arrays |
| Connection | Config + credentials | Active MT5 session |
| Historical Loader | Symbol, timeframe, count/range | Raw rate bars |
| Live Loader | Symbol, timeframe | Raw tick / latest bar |
| Normalizer | Raw MT5 objects | `NormalizedTick`, `NormalizedCandle` |
| Validator | `list[NormalizedCandle]` | `ValidationResult` |
| Events | Normalized objects | `MarketEvent` envelopes |
| Future engines | Subscribed events / API | Analysis outputs (Sprint 2+) |

---

## Normalized Output Schemas

### NormalizedTick

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Instrument symbol |
| `bid` | Decimal | Bid price |
| `ask` | Decimal | Ask price |
| `spread` | Decimal | ask − bid |
| `timestamp_utc` | datetime | Tick time (UTC) |
| `source` | string | Always `mt5_xmglobal` |

### NormalizedCandle

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Instrument symbol |
| `timeframe` | string | M1, M5, M15, M30, H1, H4, D1 |
| `open` / `high` / `low` / `close` | Decimal | OHLC prices |
| `volume` | int | Tick volume |
| `open_time_utc` | datetime | Candle open (UTC) |
| `close_time_utc` | datetime | Candle close (UTC) |
| `is_closed` | bool | `false` = forming candle |

---

## Event Bus (Sprint 1)

Sprint 1 uses an **in-memory** `EventPublisher` inside the engine module. There is no global orchestrator event bus yet. Downstream engines in future sprints will subscribe via:

```python
engine.event_publisher.subscribe("market.candle.closed", handler)
engine.event_publisher.subscribe("*", all_events_handler)  # wildcard
```

---

## Operational Notes

- **Broker symbol naming:** XMGlobal may expose gold as `GOLD.i#` rather than `XAUUSD`. Configure `TRADING_SYMBOL` accordingly.
- **Broker clock skew:** MT5 server time may differ from system UTC. The validator adjusts reference time when validating batches.
- **Forming candle:** Historical loads include the current forming bar (`is_closed=False`) as the newest entry.

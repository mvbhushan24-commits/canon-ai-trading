# Market Data Engine — Testing Guide

Sprint 1 includes **46 unit tests**, **2 framework smoke tests**, and **1 live integration verification script**. Total automated tests: **48**.

---

## Running Tests

### Full suite

```powershell
cd "C:\AI Trading"
.\scripts\test.ps1
```

Or directly:

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

### Unit tests only (no MT5 required)

```powershell
.\.venv\Scripts\python -m pytest tests/unit/engines/ -v
```

### With coverage

```powershell
.\.venv\Scripts\python -m pytest tests/ --cov=backend --cov-report=term-missing
```

**Expected:** 48 passed. Sprint 1 market_data modules achieve ~85–98% coverage (excluding live `mt5_client.py`).

---

## Unit Tests

Location: `tests/unit/engines/`

All unit tests use `MockMT5Client` from `tests/conftest.py` — **no live MT5 terminal required**.

| Test Module | Tests | Coverage Area |
|-------------|-------|---------------|
| `test_market_data_timeframes.py` | 5 | Timeframe validation, durations |
| `test_market_data_config.py` | 3 | Config model, YAML loading |
| `test_market_data_connection.py` | 5 | MT5 connection manager |
| `test_market_data_broker_symbols.py` | 5 | Broker + symbol managers |
| `test_market_data_normalizer.py` | 2 | Tick and candle normalization |
| `test_market_data_validator.py` | 5 | Gaps, duplicates, OHLC, timestamps |
| `test_market_data_loaders.py` | 8 | Historical + live loaders |
| `test_market_data_events.py` | 3 | Event publisher |
| `test_market_data_engine.py` | 10 | Full orchestrator |

### Shared Fixtures (`tests/conftest.py`)

| Fixture | Description |
|---------|-------------|
| `mock_mt5_client` | Configurable MT5 mock with seeded XAUUSD data |
| `market_data_config` | Test `MarketDataConfig` instance |
| `event_publisher` | Fresh `EventPublisher` |
| `sample_candles` | Valid H1 candle sequence |
| `sample_symbol` | Returns `"XAUUSD"` |

### Expected Unit Test Output

```
48 passed
```

Warnings from `pytest-asyncio` on Python 3.14 are expected and non-blocking.

---

## Integration Tests

Location: `tests/integration/`

### Live Verification Script

**File:** `tests/integration/verify_market_data_pipeline.py`

**Requires:** Running MT5 terminal with active session and configured symbol.

```powershell
.\.venv\Scripts\python tests/integration/verify_market_data_pipeline.py
```

#### What It Verifies

| Check | Description |
|-------|-------------|
| MT5 Connected | Engine status is `connected` |
| Symbol Loaded | Configured symbol metadata retrieved |
| Historical Data Received | H1 bars downloaded |
| Live Tick Stream Active | Tick with valid bid received |
| Normalizer Working | Tick spread + candle OHLC correct |
| Validator Working | Historical batch passes validation |
| Event Publisher Working | Connection + tick events captured |
| Engine Stable | 2-minute continuous polling without exceptions |

#### Expected Output

```
=== Market Data Engine Integration Verification ===
Timestamp: 2026-07-16T12:24:21.284234+00:00
Symbol: GOLD.i#
Events captured: 53

[PASS] MT5 Connected
[PASS] Symbol Loaded
[PASS] Historical Data Received
[PASS] Live Tick Stream Active
[PASS] Normalizer Working
[PASS] Validator Working
[PASS] Event Publisher Working
[PASS] Engine Stable
```

**Exit code:** `0` = all passed, `1` = one or more failures.

#### Prerequisites

1. MetaTrader 5 installed and running
2. `.env` with correct `TRADING_SYMBOL` (e.g. `GOLD.i#` for XMGlobal)
3. `config/settings.yaml` present
4. Stop any other process using MT5 if conflicts occur

---

## Backend Startup Verification

Verify FastAPI + engine integration:

```powershell
.\scripts\run-backend.ps1
```

**Expected log sequence:**

```
Market Data configuration loaded
Market Data Engine components initialized
Starting Market Data Engine
MT5 connection established
Broker validation passed
Market Data Engine started
Application startup complete
Uvicorn running on http://0.0.0.0:8000
```

---

## Linting and Type Checking

```powershell
.\scripts\lint.ps1
```

Or:

```powershell
.\.venv\Scripts\ruff check backend tests
.\.venv\Scripts\mypy backend/engines/market_data
```

**Expected:** All checks passed, no mypy issues.

---

## Test Design Principles

1. **Mock MT5 for unit tests** — fast, deterministic, CI-safe
2. **Live script for integration** — validates real broker pipeline
3. **No trivial assertions** — each test verifies meaningful behavior
4. **One test module per component** — mirrors engine module structure

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Symbol 'XAUUSD' is not available` | Wrong broker symbol | Set `TRADING_SYMBOL=GOLD.i#` in `.env` |
| `MT5 initialization failed` | Terminal not running | Start MetaTrader 5 |
| `Validator Working` fails | Clock skew / bad data | Ensure latest code; check broker time |
| All zeros in candles | numpy field access | Fixed in Sprint 1 (normalizer `_field()`) |
| Integration script Unicode error | Windows cp1252 | Script uses `[PASS]`/`[FAIL]` markers |

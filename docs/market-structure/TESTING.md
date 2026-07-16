# Market Structure Engine — Testing Guide

**Total tests (Sprint 1 + 2):** 69

---

## Run Tests

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

### Structure unit tests only

```powershell
.\.venv\Scripts\python -m pytest tests/unit/engines/test_market_structure*.py -v
```

### Integration pipeline

```powershell
.\.venv\Scripts\python -m pytest tests/integration/test_market_structure_pipeline.py -v
```

---

## Unit Tests

| Module | File | Tests |
|--------|------|-------|
| Swings | `test_market_structure_swings.py` | 3 |
| Trend/BOS/CHoCH | `test_market_structure_trend_bos.py` | 3 |
| Validator | `test_market_structure_validator.py` | 4 |
| Engine | `test_market_structure_engine.py` | 9 |

### Coverage Areas

- Swing high/low fractal detection
- HH, HL, LH, LL labeling
- Duplicate swing removal
- Bullish/bearish trend classification
- BOS bullish break detection
- CHoCH bearish in bullish trend
- Input validation (OHLC, duplicates, order)
- Full engine orchestration
- Event publishing
- State continuity and reset
- Unsupported timeframe handling
- Regression: flat market → undetermined

---

## Integration Tests

**File:** `tests/integration/test_market_structure_pipeline.py`

Verifies:
1. `NormalizedCandle` from Market Data schema flows into structure engine
2. `MarketStructure` output contains swings and valid trend
3. Symbol and timeframe preserved

No live MT5 required — uses synthetic candles from `tests/unit/engines/conftest.py`.

---

## Fixtures

Located in `tests/unit/engines/conftest.py`:

| Fixture | Description |
|---------|-------------|
| `structure_config` | Test `MarketStructureConfig` |
| `structure_publisher` | Event publisher with capture |
| `bullish_candles` | 30 synthetic H1 candles |
| `make_candle()` | Factory helper |
| `build_bullish_structure_candles()` | Wave pattern generator |

---

## Expected Output

```
69 passed
```

---

## Edge Cases Tested

| Case | Expected |
|------|----------|
| Empty candle list | `InsufficientDataError` |
| Invalid OHLC | `ValidationError` |
| Wrong timeframe | `UnsupportedTimeframeError` |
| Flat price action | `TrendDirection.UNDETERMINED` |
| Duplicate timestamps | Validation failure |

---

## Regression Tests

`test_regression_undetermined_with_few_swings` — ensures flat markets do not force false trend signals.

---

## Sprint 1 Compatibility

All 48 Sprint 1 tests continue to pass unchanged. Structure tests are additive.

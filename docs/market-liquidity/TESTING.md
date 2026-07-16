# Market Liquidity Engine — Testing Guide

**Total tests (Sprint 1–3):** 92

## Run Tests

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

### Liquidity tests only

```powershell
.\.venv\Scripts\python -m pytest tests/unit/engines/test_market_liquidity*.py tests/integration/test_market_liquidity_pipeline.py -v
```

### Live verification

```powershell
.\.venv\Scripts\python tests/integration/verify_market_liquidity_pipeline.py
```

## Test Coverage

| Area | File | Tests |
|------|------|-------|
| Equal highs/lows | `test_market_liquidity_equal.py` | 4 |
| Sweeps/grabs | `test_market_liquidity_sweep.py` | 2 |
| Zones | `test_market_liquidity_zones.py` | 1 |
| External | `test_market_liquidity_external.py` | 1 |
| Engine | `test_market_liquidity_engine.py` | 8 |
| Validator | `test_market_liquidity_validator.py` | 4 |
| Config | `test_market_liquidity_config.py` | 1 |
| Pipeline | `test_market_liquidity_pipeline.py` | 2 |

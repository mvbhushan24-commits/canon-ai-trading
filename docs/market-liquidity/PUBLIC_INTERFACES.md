# Market Liquidity Engine — Public Interfaces

## LiquidityEngine

### `analyze(candles, structure=None, *, timeframe=None) -> LiquidityAnalysis`

### Detection Methods

| Method | Returns |
|--------|---------|
| `detect_equal_highs(structure, swing_highs=None)` | `list[EqualLevelCluster]` |
| `detect_equal_lows(structure, swing_lows=None)` | `list[EqualLevelCluster]` |
| `detect_buy_side(equal_highs)` | `list[LiquidityLevel]` |
| `detect_sell_side(equal_lows)` | `list[LiquidityLevel]` |
| `detect_sweeps(candles, levels, timeframe)` | `list[LiquiditySweep]` |
| `detect_grabs(candles, sweeps, timeframe)` | `list[LiquidityGrab]` |
| `publish_events(analysis)` | `None` |

## LiquidityAnalysis Fields

`external_liquidity`, `internal_liquidity`, `equal_highs`, `equal_lows`, `buy_side_liquidity`, `sell_side_liquidity`, `sweeps`, `grabs`, `zones`, `bias`, `confidence`, `evidence`, `state`

## Exceptions

| Exception | Code |
|-----------|------|
| `InsufficientDataError` | `LQE_INSUFFICIENT_DATA` |
| `InvalidStructureError` | `LQE_INVALID_STRUCTURE` |
| `UnsupportedTimeframeError` | `LQE_TIMEFRAME_UNSUPPORTED` |
| `ValidationError` | `LQE_VALIDATION_FAILED` |
| `DuplicateZoneError` | `LQE_DUPLICATE_ZONE` |

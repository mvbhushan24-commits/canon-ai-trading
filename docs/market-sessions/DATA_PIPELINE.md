# Kill Zones & Trading Sessions Engine — Data Pipeline

**Engine ID:** `market_sessions`  
**Sprint:** 9.1 (Architecture specification)  
**Status:** Not implemented

---

## Pipeline Overview

```
NormalizedCandles (Market Data Engine)
        │
        ├──────────────────────────────────────────────────────────┐
        │              │              │                              │
        ▼              ▼              ▼                              │
MarketStructure  LiquidityState  PremiumDiscountAnalysis              │
(Market Structure) (Market Liquidity) (Premium / Discount)           │
        │              │              │                              │
        │              │              │    timestamp_utc             │
        │              │              │    broker_timezone           │
        └──────────────┴──────────────┴──────────────────────────────┘
                                   │
                                   ▼
                        Kill Zones & Sessions Input Validator
                                   │
                                   ▼
                        Kill Zones & Sessions Detector
                          ├── Timezone Normalization
                          ├── Calendar Resolution (weekend/holiday/DST)
                          ├── Session Window Resolution
                          ├── Kill Zone Activation
                          ├── Overlap Detection
                          ├── Transition Forecast
                          ├── Daily / Weekly / Monthly Open Resolution
                          ├── Session Extreme Tracking
                          ├── Opening Range Computation
                          ├── Initial Balance Computation
                          ├── Time-of-Day Filter Evaluation
                          └── Quality Scoring
                                   │
                                   ▼
                        SessionAnalysis
                                   │
                                   ▼
                        Kill Zones & Sessions Event Publisher
                                   │
                                   ▼
                        Decision Engine (future)
```

---

## Stage 1 — Market Data Input

**Source:** `MarketDataEngine.load_historical_candles()` or `market.candle.closed` event

**Type:** `list[NormalizedCandle]`

| Field Used | Purpose |
|------------|---------|
| `open`, `high`, `low`, `close` | Opens, session extremes, OR/IB, volatility |
| `open_time_utc`, `close_time_utc` | Session window membership, period boundaries |
| `is_closed` | Only closed candles used for extremes, OR, IB |
| `symbol`, `timeframe` | Analysis scope validation |
| `volume` | Liquidity availability proxy |
| `spread` | Liquidity availability proxy (when available) |

**Boundary rule:** Kill Zones & Sessions Engine imports `NormalizedCandle` from `backend.engines.market_data` public API only.

---

## Stage 2 — Reference Timestamp and Broker Timezone

**Source:** Caller / system clock / `market.tick.received` event

| Input | Purpose |
|-------|---------|
| `timestamp_utc` | Primary reference for session/kill zone activation |
| `broker_timezone` | IANA timezone for day/week/month boundaries |

**Normalization flow:**

```
1. Validate timestamp_utc is timezone-aware UTC
2. Load broker_timezone from config if not supplied by caller
3. Convert: broker_local = timestamp_utc.astimezone(ZoneInfo(broker_timezone))
4. Derive trading_day_id from broker_local date + broker_day_start_hour
```

**When broker_timezone missing:** Engine uses `config.broker_timezone` default (`Europe/Nicosia` — common MT5/XM server zone). Evidence notes `"Broker timezone from configuration default"`.

---

## Stage 3 — Market Structure Context (Optional)

**Source:** `MarketStructureEngine.analyze(candles)` or `analysis.structure.completed` event

**Type:** `MarketStructure`

| Field Used | Purpose |
|------------|---------|
| `current_trend` | Historical performance bias weighting |
| `bos_events`, `choch_events` | Volatility spike detection near session opens |
| `confidence` | Quality scoring factor |

**When missing:** Engine proceeds without structure-enhanced quality scoring; structure factor defaults to neutral.

---

## Stage 4 — Liquidity Context (Optional)

**Source:** `LiquidityEngine.analyze(candles, structure)` or `analysis.liquidity.completed` event

**Type:** `LiquidityState` (extracted by caller)

| Field Used | Purpose |
|------------|---------|
| `active_zones` | Cross-validate session H/L against liquidity levels |
| `recent_sweeps` | Liquidity availability scoring near session opens |
| `bar_count` | Consistency validation |

**When missing:** Liquidity availability derived from candle volume/spread proxies only.

---

## Stage 5 — Premium / Discount Context (Optional)

**Source:** `PremiumDiscountEngine.analyze(...)` or `analysis.premium_discount.completed` event

**Type:** `PremiumDiscountAnalysis`

| Field Used | Purpose |
|------------|---------|
| `price_location` | Contextual quality — premium/discount at session open |
| `dealing_range` | Range expansion comparison vs session range |
| `bias` | Historical performance alignment |
| `quality` | Composite quality weighting |

**When missing:** Premium/discount alignment factor defaults to neutral.

---

## Stage 6 — Input Validation

**Component:** `MarketSessionsInputValidator`

| Check | Action on Failure |
|-------|-------------------|
| Candle batch non-empty | Raise `MS_VALIDATION_FAILED` |
| Single symbol/timeframe | Raise `MS_VALIDATION_FAILED` |
| Chronological ordering | Raise `MS_VALIDATION_FAILED` |
| Valid OHLC relationships | Raise `MS_VALIDATION_FAILED` |
| `timestamp_utc` timezone-aware UTC | Raise `MS_INVALID_TIMESTAMP` |
| Valid IANA `broker_timezone` | Raise `MS_INVALID_TIMEZONE` |
| Timeframe in config | Raise `MS_TIMEFRAME_UNSUPPORTED` |
| Candle count ≥ `min_candles` | Raise `MS_INSUFFICIENT_DATA` (when strict) |
| Optional upstream consistency | Raise domain-specific errors |

**Degraded mode:** When `config.allow_partial_analysis: true`, insufficient candles skip OR/IB/volatility features but still resolve sessions from timestamp.

---

## Stage 7 — Calendar Resolution

**Component:** `CalendarResolver`

| Step | Input | Output |
|------|-------|--------|
| 7.1 | `broker_local` | `is_weekend` flag |
| 7.2 | Holiday calendar + `broker_local` | `is_holiday`, `holiday_name` |
| 7.3 | `broker_timezone`, `timestamp_utc` | `is_dst_transition`, `dst_offset_minutes` |
| 7.4 | Calendar flags | `market_availability`, `trading_day_id`, `week_id`, `month_id` |

**Weekend logic:**

```
if broker_local.weekday() in config.weekend_days and not config.weekend_trading_enabled:
    market_availability = closed
    skip session/kill zone activation
```

**Holiday logic:**

```
if broker_local.date() in config.holidays.dates:
    market_availability = closed  # unless partial_holiday_sessions configured
```

---

## Stage 8 — Session Window Resolution

**Component:** `SessionResolver`

| Step | Action |
|------|--------|
| 8.1 | For each configured session, compute UTC window for current trading day |
| 8.2 | Apply DST offset via IANA timezone anchor |
| 8.3 | Mark `is_active` when `window_start_utc <= timestamp_utc < window_end_utc` |
| 8.4 | Classify `phase` per session (pre_open, opening, mid, closing, inactive) |
| 8.5 | Select `primary_session` by configured priority order |
| 8.6 | Score session quality |

**Session priority default:** `london` > `new_york` > `tokyo` > `sydney` (when multiple active).

---

## Stage 9 — Kill Zone Activation

**Component:** `KillZoneResolver`

| Step | Action |
|------|--------|
| 9.1 | For each configured kill zone, compute UTC window |
| 9.2 | Mark `is_active` at reference timestamp |
| 9.3 | Link `parent_session` |
| 9.4 | Score kill zone quality (timing, volatility, liquidity, historical) |
| 9.5 | Populate `active_kill_zones` subset |

**Overlap note:** Kill zones are independent of session `is_active` unless `config.kill_zones.require_active_session: true`.

---

## Stage 10 — Overlap Detection

**Component:** `OverlapDetector`

| Step | Action |
|------|--------|
| 10.1 | Evaluate configured overlap pairs |
| 10.2 | Compute intersection windows in UTC |
| 10.3 | Mark active overlaps at reference timestamp |
| 10.4 | Score overlap quality |

---

## Stage 11 — Transition Detection and Forecast

**Component:** `TransitionTracker`

| Step | Action |
|------|--------|
| 11.1 | Compare `prior_state` session/kill zone flags with current |
| 11.2 | Emit transition events on boundary crossings |
| 11.3 | Compute `next_transition` within forecast horizon (`config.transition_forecast_hours`) |
| 11.4 | Populate `recent_transitions` from lookback window |

---

## Stage 12 — Period Open Resolution

**Component:** `OpenResolver`

### 12.1 Daily Open

```
boundary_utc = broker_day_start_hour converted to UTC for trading_day_id
daily_open_candle = first closed candle where open_time_utc >= boundary_utc
```

### 12.2 Weekly Open

```
week_start = configured weekday (default Monday) in broker timezone
weekly_open_candle = first closed candle of current week
```

### 12.3 Monthly Open

```
month_start = first day of month in broker timezone
monthly_open_candle = first closed candle of current month
```

**When candle not yet closed:** Return open with `is_confirmed: false`.

---

## Stage 13 — Session Extreme Tracking

**Component:** `ExtremesTracker`

| Step | Action |
|------|--------|
| 13.1 | Filter candles to each session window for current trading day |
| 13.2 | Compute running high/low |
| 13.3 | Merge with `prior_state.session_extremes_cache` |
| 13.4 | Cross-validate with liquidity session H/L when available |
| 13.5 | Emit `SessionHighUpdated` / `SessionLowUpdated` on revision |

---

## Stage 14 — Opening Range Computation

**Component:** `OpeningRangeBuilder`

| Step | Action |
|------|--------|
| 14.1 | Identify session open time for primary (or each enabled) session |
| 14.2 | Collect closed candles within `[open, open + duration_minutes)` |
| 14.3 | Compute high/low/midpoint |
| 14.4 | Set `is_complete` when formation window elapsed |
| 14.5 | Detect breakout vs current price |
| 14.6 | Score OR quality |

**When insufficient candles:** Return `opening_range: null`; evidence notes `"Opening range undetermined — insufficient candles"`.

---

## Stage 15 — Initial Balance Computation

**Component:** `InitialBalanceBuilder`

| Step | Action |
|------|--------|
| 15.1 | Collect closed candles within IB formation window |
| 15.2 | Compute high/low/midpoint |
| 15.3 | Track extensions after `is_complete` |
| 15.4 | Score IB quality |

---

## Stage 16 — Time-of-Day Filter Evaluation

**Component:** `TimeOfDayFilterEvaluator`

| Step | Action |
|------|--------|
| 16.1 | Load filter mode and window lists from config |
| 16.2 | Evaluate against active sessions, kill zones, calendar context |
| 16.3 | Set `is_allowed` and `blocked_reasons` |
| 16.4 | Compute `next_allowed_utc` when blocked |

---

## Stage 17 — Quality Scoring

**Component:** `QualityScorer`

| Factor | Computation |
|--------|-------------|
| Session quality | Phase weighting + calendar cleanliness + primary session strength |
| Kill zone quality | Active kill zone scores; best-of or weighted average |
| Overlap quality | Best active overlap score |
| Volatility | Current range vs rolling session baseline from candles |
| Liquidity availability | Volume/spread + LiquidityState sweep density |
| Historical performance | Rolling OR/IB expansion stats when enabled |

Composite:

```
strength = Σ (factor_score × weight) / Σ weights
quality_tier = high if strength >= high_threshold else medium if >= min_threshold else low
confidence = f(evidence_count, calendar_certainty, candle_coverage)
```

---

## Stage 18 — Output Assembly

**Type:** `SessionAnalysis`

| Assembly Rule | Description |
|---------------|-------------|
| Primary session | Highest-priority active session |
| Active kill zones | All kill zones with `is_active == true` |
| Events timeline | Ordered list of events detected this cycle |
| State | Updated `MarketSessionsState` for next cycle |
| Evidence | Consolidated human-readable reasoning chain |

---

## Stage 19 — Event Publishing

**Component:** `MarketSessionsEventPublisher`

| Trigger | Event |
|---------|-------|
| Session boundary crossed | `SessionStarted`, `SessionEnded` |
| Kill zone entered/exited | `KillZoneEntered`, `KillZoneExited` |
| Overlap change | `OverlapStarted`, `OverlapEnded` |
| Open resolved | `DailyOpenResolved`, `WeeklyOpenResolved`, `MonthlyOpenResolved` |
| Extreme revised | `SessionHighUpdated`, `SessionLowUpdated` |
| OR/IB lifecycle | `OpeningRangeComplete`, `InitialBalanceComplete`, etc. |
| Filter block | `TimeFilterBlocked` |
| Calendar change | `WeekendDetected`, `HolidayDetected`, `DSTTransition` |
| Cycle complete | `SessionAnalysisUpdated` |

Contract bus name: `analysis.session.completed` (Decision Engine compatibility).

---

## Data Flow Summary Table

| Stage | Input | Output | Required |
|-------|-------|--------|----------|
| 1 | Candles | Validated OHLC series | Yes |
| 2 | Timestamp + TZ | Broker-local reference | Yes |
| 3 | Structure | Trend/volatility factors | No |
| 4 | LiquidityState | Liquidity scoring | No |
| 5 | PremiumDiscountAnalysis | Contextual scoring | No |
| 6 | All inputs | Validated bundle | Yes |
| 7 | Broker-local time | CalendarContext | Yes |
| 8 | UTC time + config | TradingSessionState[] | Yes |
| 9 | UTC time + config | KillZoneState[] | Yes |
| 10 | Active sessions | SessionOverlap[] | Yes |
| 11 | Prior + current state | Transitions | Yes |
| 12 | Candles + boundaries | PeriodOpen × 3 | Recommended |
| 13 | Candles + windows | SessionExtreme[] | Recommended |
| 14 | Candles + session | OpeningRange | Optional |
| 15 | Candles + session | InitialBalance | Optional |
| 16 | Full context | TimeOfDayFilter | Yes |
| 17 | All factors | quality, strength, confidence | Yes |
| 18 | All stages | SessionAnalysis | Yes |
| 19 | SessionAnalysis | Published events | Yes |

---

## Pipeline Wiring Example (Planned)

```python
# Orchestrator pseudocode — Sprint 9.2
candles = market_data.load_historical_candles(symbol, timeframe, count=500)
structure = market_structure.analyze(candles)
liquidity = market_liquidity.analyze(candles, structure).state
premium_discount = market_premium_discount.analyze(
    candles, structure=structure, liquidity_state=liquidity, ...
)

session_analysis = market_sessions.analyze(
    candles,
    timestamp_utc=datetime.now(timezone.utc),
    structure=structure,
    liquidity_state=liquidity,
    premium_discount=premium_discount,
    broker_timezone=settings.broker_timezone,
    timeframe=timeframe,
)
```

---

## Failure and Degradation Matrix

| Condition | Pipeline Behavior |
|-----------|-------------------|
| Weekend (trading disabled) | Sessions inactive; `market_availability: closed`; no error |
| Holiday | Same as weekend |
| Insufficient candles for OR/IB | Skip OR/IB; sessions still resolved |
| Missing broker timezone | Use config default; evidence note |
| DST transition | Windows recalculated; `DSTTransition` event |
| Missing all optional upstream | Time-only analysis with reduced confidence |
| Invalid config boundaries | Safe defaults + `MS_CONFIG_INVALID` warning event |

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Events | [EVENTS.md](./EVENTS.md) |

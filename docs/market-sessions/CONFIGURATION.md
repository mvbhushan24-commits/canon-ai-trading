# Kill Zones & Trading Sessions Engine — Configuration

**Engine ID:** `market_sessions`  
**Sprint:** 9.1 (Architecture specification)  
**Status:** Not implemented

---

## Configuration Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | Constructor injection | Tests and custom wiring |
| 2 | `config/settings.yaml` → `market_sessions` | Primary runtime config |
| 3 | `engines.market_sessions` toggle | Enable/disable flag |
| 4 | Pydantic model defaults | Code fallbacks |

Secrets remain in `.env` only (Constitution rule). No credentials in YAML.

---

## Configuration Hierarchy

```
config/settings.yaml
├── engines.market_sessions              # Global enable toggle
└── market_sessions                      # Engine parameters
    ├── enabled
    ├── timeframes
    ├── min_candles
    ├── broker_timezone
    ├── broker_day_start_hour
    ├── weekend_trading_enabled
    ├── allow_partial_analysis
    ├── sessions.*                        # Sydney, Tokyo, London, New York
    ├── kill_zones.*                      # Asian, London Open, NY, London Close
    ├── overlaps.*                        # Session overlap pairs
    ├── session_phases.*                  # Phase duration rules
    ├── session_priority.*                # Primary session selection
    ├── opens.*                           # Daily, weekly, monthly
    ├── session_extremes.*                # Session H/L tracking
    ├── opening_range.*                   # OR parameters
    ├── initial_balance.*                 # IB parameters
    ├── time_of_day_filter.*              # Allow/block windows
    ├── calendar.*                        # Weekend, holiday, DST
    ├── transitions.*                     # Transition detection
    ├── volatility.*                      # Volatility profiling
    ├── liquidity.*                       # Liquidity scoring
    ├── historical_performance.*          # Rolling stats
    └── quality.*                         # Scoring weights and thresholds
```

Nested keys are flattened into `MarketSessionsConfig` fields in Sprint 9.2.

---

## YAML Schema (Planned)

```yaml
# Kill Zones & Trading Sessions Engine configuration (Sprint 9.2+)
market_sessions:
  enabled: true
  timeframes:
    - M5
    - M15
    - H1
  min_candles: 20
  lookback: 500
  pip_size: 0.1

  # Broker timezone normalization
  broker_timezone: Europe/Nicosia          # IANA — common MT5/XM server
  broker_day_start_hour: 0                 # Hour in broker TZ when trading day starts
  weekend_trading_enabled: true            # XAUUSD trades through most weekends
  allow_partial_analysis: true             # Resolve sessions without full candle features

  # ── Trading Sessions ──────────────────────────────────────────────
  sessions:
    sydney:
      enabled: true
      timezone: Australia/Sydney
      local_start: "07:00"                 # Local session open
      local_end: "16:00"                   # Local session close
      # Resolves to ~21:00–06:00 UTC (standard time) after normalization

    tokyo:
      enabled: true
      timezone: Asia/Tokyo
      local_start: "09:00"
      local_end: "18:00"
      # Resolves to ~00:00–09:00 UTC (standard time)

    london:
      enabled: true
      timezone: Europe/London
      local_start: "08:00"
      local_end: "17:00"
      # Resolves to ~07:00–16:00 UTC (standard time)

    new_york:
      enabled: true
      timezone: America/New_York
      local_start: "08:00"
      local_end: "17:00"
      # Resolves to ~12:00–21:00 UTC (standard time)

  # ── Kill Zones (ICT-style) ────────────────────────────────────────
  kill_zones:
    require_active_session: false          # Kill zones independent of session flag

    asian:
      enabled: true
      parent_session: tokyo
      utc_start: "00:00"                   # Fixed UTC (configurable)
      utc_end: "03:00"
      use_dst_adjustment: false            # Fixed UTC window

    london_open:
      enabled: true
      parent_session: london
      utc_start: "07:00"
      utc_end: "10:00"
      use_dst_adjustment: false

    new_york:
      enabled: true
      parent_session: new_york
      utc_start: "12:00"
      utc_end: "15:00"
      use_dst_adjustment: false

    london_close:
      enabled: true
      parent_session: london
      utc_start: "15:00"
      utc_end: "17:00"
      use_dst_adjustment: false

  # ── Session Overlaps ────────────────────────────────────────────────
  overlaps:
    sydney_tokyo:
      enabled: true
      sessions: [sydney, tokyo]
    london_new_york:
      enabled: true
      sessions: [london, new_york]

  # ── Session Phases ────────────────────────────────────────────────
  session_phases:
    pre_open_minutes: 30
    opening_phase_minutes: 60
    closing_phase_minutes: 30

  # ── Primary Session Priority ──────────────────────────────────────
  session_priority:
    order: [london, new_york, tokyo, sydney]

  # ── Period Opens ──────────────────────────────────────────────────
  opens:
    daily:
      enabled: true
      require_closed_candle: true
    weekly:
      enabled: true
      week_start_day: monday               # Broker-local weekday
      require_closed_candle: true
    monthly:
      enabled: true
      require_closed_candle: true

  # ── Session Extremes ──────────────────────────────────────────────
  session_extremes:
    enabled: true
    reset_at_daily_open: true
    cross_validate_liquidity: true         # When LiquidityState provided

  # ── Opening Range ─────────────────────────────────────────────────
  opening_range:
    enabled: true
    duration_minutes: 30
    min_candles: 2
    breakout_buffer_pips: 2.0
    sessions: [london, new_york]           # Sessions to compute OR for

  # ── Initial Balance ───────────────────────────────────────────────
  initial_balance:
    enabled: true
    duration_minutes: 60
    min_candles: 4
    extension_threshold_pips: 5.0
    sessions: [london, new_york]

  # ── Time-of-Day Filter ────────────────────────────────────────────
  time_of_day_filter:
    mode: kill_zone_only                   # allow_list | block_list | kill_zone_only | disabled
    allow_list: []                         # Session/kill zone IDs when mode=allow_list
    block_list: [sydney]                   # IDs to block when mode=block_list
    block_weekends: false                  # Block when is_weekend (if weekend_trading_enabled)
    block_holidays: true
    block_outside_sessions: false

  # ── Calendar ──────────────────────────────────────────────────────
  calendar:
    weekend_days: [saturday, sunday]
    holidays:
      enabled: true
      dates: []                            # ISO dates: "2026-12-25"
      file: null                           # Optional path to holiday calendar file
    partial_holiday_sessions: []           # Sessions still active on partial holidays
    dst:
      enabled: true
      transition_window_hours: 24          # Flag DST transitions within this window

  # ── Transitions ───────────────────────────────────────────────────
  transitions:
    forecast_hours: 24
    imminent_minutes: 15
    recent_lookback_hours: 4

  # ── Volatility Profiling ──────────────────────────────────────────
  volatility:
    enabled: true
    baseline_lookback_sessions: 20
    low_percentile: 33
    high_percentile: 67
    min_candles_for_profile: 10

  # ── Liquidity Scoring ─────────────────────────────────────────────
  liquidity:
    use_volume: true
    use_spread: true
    use_liquidity_engine: true             # When LiquidityState provided
    low_volume_percentile: 25
    high_volume_percentile: 75

  # ── Historical Performance ────────────────────────────────────────
  historical_performance:
    enabled: false                         # Requires SQLite stats — future enhancement
    lookback_days: 30
    min_samples: 10
    metrics:
      - or_breakout_rate
      - ib_extension_rate
      - session_range_expansion

  # ── Quality & Filtering ───────────────────────────────────────────
  min_quality_score: 0.4
  high_quality_threshold: 0.7
  quality_weights:
    session_quality: 0.20
    kill_zone_quality: 0.20
    overlap_quality: 0.15
    volatility: 0.15
    liquidity_availability: 0.15
    historical_performance: 0.15

engines:
  market_sessions: true
```

---

## Parameter Reference

### Core

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Engine master toggle |
| `timeframes` | `list[str]` | `M5, M15, H1` | Supported analysis timeframes |
| `min_candles` | `int` | `20` | Minimum candles for full analysis |
| `lookback` | `int` | `500` | Maximum candles processed |
| `pip_size` | `decimal` | `0.1` | Pip size for XAUUSD |
| `broker_timezone` | `str` | `Europe/Nicosia` | IANA broker server timezone |
| `broker_day_start_hour` | `int` | `0` | Trading day start hour in broker TZ |
| `weekend_trading_enabled` | `bool` | `true` | Allow session resolution on weekends |
| `allow_partial_analysis` | `bool` | `true` | Degrade gracefully when candles insufficient |

### Sessions (per session: sydney, tokyo, london, new_york)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Session toggle |
| `timezone` | `str` | *(see YAML)* | IANA anchor timezone |
| `local_start` | `str` | *(see YAML)* | Local session start (`HH:MM`) |
| `local_end` | `str` | *(see YAML)* | Local session end (`HH:MM`) |

**Default UTC windows (standard time, derived from local anchors):**

| Session | UTC Start | UTC End |
|---------|-----------|---------|
| Sydney | 21:00 | 06:00 |
| Tokyo | 00:00 | 09:00 |
| London | 07:00 | 16:00 |
| New York | 12:00 | 21:00 |

### Kill Zones (per zone: asian, london_open, new_york, london_close)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Kill zone toggle |
| `parent_session` | `str` | *(see YAML)* | Parent session ID |
| `utc_start` | `str` | *(see YAML)* | Kill zone UTC start (`HH:MM`) |
| `utc_end` | `str` | *(see YAML)* | Kill zone UTC end (`HH:MM`) |
| `use_dst_adjustment` | `bool` | `false` | Apply DST shift to UTC window |
| `require_active_session` | `bool` | `false` | Global — require parent session active |

**Default kill zone UTC windows:**

| Kill Zone | UTC Start | UTC End |
|-----------|-----------|---------|
| Asian | 00:00 | 03:00 |
| London Open | 07:00 | 10:00 |
| New York | 12:00 | 15:00 |
| London Close | 15:00 | 17:00 |

### Overlaps (per overlap: sydney_tokyo, london_new_york)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Overlap toggle |
| `sessions` | `list[str]` | *(see YAML)* | Participating session IDs |

### Session Phases

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pre_open_minutes` | `int` | `30` | Minutes before session start classified as pre_open |
| `opening_phase_minutes` | `int` | `60` | Opening phase duration after session start |
| `closing_phase_minutes` | `int` | `30` | Closing phase before session end |

### Session Priority

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `order` | `list[str]` | `[london, new_york, tokyo, sydney]` | Primary session selection priority |

### Period Opens

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `daily.enabled` | `bool` | `true` | Compute daily open |
| `daily.require_closed_candle` | `bool` | `true` | Require closed candle at boundary |
| `weekly.enabled` | `bool` | `true` | Compute weekly open |
| `weekly.week_start_day` | `str` | `monday` | Broker-local week start |
| `weekly.require_closed_candle` | `bool` | `true` | Require closed candle |
| `monthly.enabled` | `bool` | `true` | Compute monthly open |
| `monthly.require_closed_candle` | `bool` | `true` | Require closed candle |

### Session Extremes

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Track session H/L |
| `reset_at_daily_open` | `bool` | `true` | Reset extremes at daily open |
| `cross_validate_liquidity` | `bool` | `true` | Cross-validate with LiquidityState |

### Opening Range

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Compute opening range |
| `duration_minutes` | `int` | `30` | OR formation window |
| `min_candles` | `int` | `2` | Minimum closed candles |
| `breakout_buffer_pips` | `decimal` | `2.0` | Breakout confirmation buffer |
| `sessions` | `list[str]` | `[london, new_york]` | Sessions to compute OR for |

### Initial Balance

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Compute initial balance |
| `duration_minutes` | `int` | `60` | IB formation window |
| `min_candles` | `int` | `4` | Minimum closed candles |
| `extension_threshold_pips` | `decimal` | `5.0` | Minimum extension to record |
| `sessions` | `list[str]` | `[london, new_york]` | Sessions to compute IB for |

### Time-of-Day Filter

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `mode` | `str` | `kill_zone_only` | `allow_list`, `block_list`, `kill_zone_only`, `disabled` |
| `allow_list` | `list[str]` | `[]` | Permitted session/kill zone IDs |
| `block_list` | `list[str]` | `[sydney]` | Blocked session/kill zone IDs |
| `block_weekends` | `bool` | `false` | Block analysis on weekends |
| `block_holidays` | `bool` | `true` | Block analysis on holidays |
| `block_outside_sessions` | `bool` | `false` | Block when no session active |

### Calendar

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `weekend_days` | `list[str]` | `[saturday, sunday]` | Weekend days in broker TZ |
| `holidays.enabled` | `bool` | `true` | Enable holiday calendar |
| `holidays.dates` | `list[str]` | `[]` | ISO date strings |
| `holidays.file` | `str \| null` | `null` | External holiday file path |
| `partial_holiday_sessions` | `list[str]` | `[]` | Active sessions on partial holidays |
| `dst.enabled` | `bool` | `true` | Enable DST detection |
| `dst.transition_window_hours` | `int` | `24` | DST transition flag window |

### Transitions

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `forecast_hours` | `int` | `24` | Transition forecast horizon |
| `imminent_minutes` | `int` | `15` | Minutes before transition flagged imminent |
| `recent_lookback_hours` | `int` | `4` | Recent transition lookback |

### Volatility

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable volatility profiling |
| `baseline_lookback_sessions` | `int` | `20` | Sessions for baseline range |
| `low_percentile` | `int` | `33` | Below = low volatility |
| `high_percentile` | `int` | `67` | Above = high volatility |
| `min_candles_for_profile` | `int` | `10` | Minimum candles for profile |

### Liquidity

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `use_volume` | `bool` | `true` | Use candle volume in scoring |
| `use_spread` | `bool` | `true` | Use spread when available |
| `use_liquidity_engine` | `bool` | `true` | Use LiquidityState when provided |
| `low_volume_percentile` | `int` | `25` | Below = low liquidity |
| `high_volume_percentile` | `int` | `75` | Above = high liquidity |

### Historical Performance

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable historical stats (future) |
| `lookback_days` | `int` | `30` | Rolling lookback period |
| `min_samples` | `int` | `10` | Minimum samples before scoring |
| `metrics` | `list[str]` | OR/IB/range metrics | Tracked performance metrics |

### Quality

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `min_quality_score` | `decimal` | `0.4` | Minimum tier threshold |
| `high_quality_threshold` | `decimal` | `0.7` | High tier threshold |
| `quality_weights.session_quality` | `decimal` | `0.20` | Session quality weight |
| `quality_weights.kill_zone_quality` | `decimal` | `0.20` | Kill zone quality weight |
| `quality_weights.overlap_quality` | `decimal` | `0.15` | Overlap quality weight |
| `quality_weights.volatility` | `decimal` | `0.15` | Volatility weight |
| `quality_weights.liquidity_availability` | `decimal` | `0.15` | Liquidity weight |
| `quality_weights.historical_performance` | `decimal` | `0.15` | Historical performance weight |

Quality weights must sum to `1.0` (validated at load time).

---

## Timezone Handling

### Design Principles

1. **UTC is canonical** — all internal windows, events, and schemas use UTC
2. **IANA timezones only** — no fixed-offset shortcuts in configuration
3. **Broker timezone for calendar** — day/week/month boundaries use broker-local time
4. **Session anchors use local time** — converted to UTC dynamically each cycle
5. **Kill zones default to fixed UTC** — institutional convention; optionally DST-adjusted

### Conversion Rules

| Operation | Timezone |
|-----------|----------|
| Session window resolution | Session anchor TZ → UTC |
| Kill zone activation | UTC (config) or anchor TZ if `use_dst_adjustment: true` |
| Daily open boundary | Broker TZ → UTC |
| Weekend detection | Broker-local weekday |
| Holiday matching | Broker-local date |
| Event timestamps | Always UTC |
| Evidence strings | UTC with optional broker-local display |

### Supported Broker Timezones (Common)

| Broker / Platform | Default IANA |
|-------------------|--------------|
| XM Global / MT5 | `Europe/Nicosia` |
| Generic UTC+2 | `Europe/Nicosia` |
| Generic UTC+3 | `Europe/Moscow` |
| US Eastern | `America/New_York` |

Override via `broker_timezone` — never hardcode in implementation.

---

## DST Handling

### Mechanism

```
1. Load session.timezone via zoneinfo.ZoneInfo
2. Compute local_start/local_end for reference date in anchor TZ
3. Convert boundary datetimes to UTC
4. Detect offset changes within dst.transition_window_hours
5. Set calendar_context.is_dst_transition and dst_offset_minutes
```

### Kill Zone DST Options

| Setting | Behavior |
|---------|----------|
| `use_dst_adjustment: false` | Fixed UTC window year-round (default for ICT kill zones) |
| `use_dst_adjustment: true` | Shift UTC window when anchor TZ offset changes |

### DST Transition Behavior

| Condition | Engine Behavior |
|-----------|-----------------|
| Transition within window | Emit `DSTTransition` event; evidence note |
| Session boundary shift | Windows recalculated automatically |
| Ambiguous local time | Use `fold=0` (first occurrence) per Python zoneinfo convention |
| Missing timezone data | Raise `MS_INVALID_TIMEZONE` |

---

## Holiday Handling

### Configuration Modes

| Mode | Configuration |
|------|---------------|
| Inline dates | `calendar.holidays.dates: ["2026-01-01", "2026-12-25"]` |
| External file | `calendar.holidays.file: "config/holidays.yaml"` |
| Disabled | `calendar.holidays.enabled: false` |

### Holiday Behavior

| Setting | Behavior |
|---------|----------|
| Full holiday | `market_availability: closed`; sessions inactive |
| Partial holiday | Only `partial_holiday_sessions` remain active |
| `time_of_day_filter.block_holidays: true` | Filter blocks analysis |

---

## Environment Variables

No engine-specific secrets. Optional overrides (future):

| Variable | Description |
|----------|-------------|
| `MARKET_SESSIONS_ENABLED` | Override `engines.market_sessions` toggle |
| `BROKER_TIMEZONE` | Override `broker_timezone` |

Secrets (MT5 credentials) remain in `.env` per Constitution — not used by this engine directly.

---

## Configuration Validation Rules (Sprint 9.2)

| Rule | On Violation |
|------|--------------|
| Quality weights sum to 1.0 ± 0.001 | `ConfigInvalidError` |
| Session local_start ≠ local_end | `ConfigInvalidError` |
| Kill zone utc_start ≠ utc_end | `ConfigInvalidError` |
| Valid IANA timezone strings | `ConfigInvalidError` |
| `min_candles` ≥ 1 | `ConfigInvalidError` |
| OR/IB duration > 0 | `ConfigInvalidError` |
| Unknown session ID in overlap | Warning + skip overlap |
| Recoverable boundary overlap | Warning + use safe defaults |

---

## Example settings.yaml.example (Planned)

Sprint 9.2 will ship `backend/engines/market_sessions/settings.yaml.example` mirroring this document.

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Events | [EVENTS.md](./EVENTS.md) |

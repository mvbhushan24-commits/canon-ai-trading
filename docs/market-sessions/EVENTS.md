# Kill Zones & Trading Sessions Engine — Events

**Engine ID:** `market_sessions`  
**Sprint:** 9.1 (Architecture specification)  
**Status:** Not implemented

---

## Event Envelope

All events use the `MarketSessionsAnalysisEvent` envelope (consistent with Sprints 1–8):

```python
{
    "event_id": "uuid",
    "timestamp_utc": "ISO-8601",
    "symbol": "GOLD.i#",
    "source_engine": "market_sessions",
    "event_type": "SessionStarted",
    "payload": { ... }
}
```

---

## Published Events

### Session Lifecycle Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `SessionStarted` | Trading session window entered | Session ID, window bounds, phase |
| `SessionEnded` | Trading session window exited | Session ID, final phase, session extremes summary |

### Kill Zone Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `KillZoneEntered` | Kill zone window entered | Kill zone ID, parent session, window bounds, quality score |
| `KillZoneExited` | Kill zone window exited | Kill zone ID, elapsed duration, final quality score |

### Overlap Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `OverlapStarted` | Session overlap window entered | Overlap ID, participating sessions, window bounds |
| `OverlapEnded` | Session overlap window exited | Overlap ID, duration, final quality score |

### Period Open Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `DailyOpenResolved` | Daily open candle identified | Open price, open time UTC, trading day ID |
| `WeeklyOpenResolved` | Weekly open candle identified | Open price, open time UTC, week ID |
| `MonthlyOpenResolved` | Monthly open candle identified | Open price, open time UTC, month ID |

### Session Extreme Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `SessionHighUpdated` | Session high revised | Session ID, new high, previous high, timestamp |
| `SessionLowUpdated` | Session low revised | Session ID, new low, previous low, timestamp |

### Opening Range Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `OpeningRangeComplete` | OR formation window closed | Session ID, OR high/low, range size pips |
| `OpeningRangeBreakout` | Price broke OR boundary | Session ID, direction, breakout price, buffer used |

### Initial Balance Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `InitialBalanceComplete` | IB formation window closed | Session ID, IB high/low, range size pips |
| `InitialBalanceExtension` | Price extended beyond IB | Session ID, extension direction, extension size pips |

### Filter Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `TimeFilterBlocked` | Time-of-day filter rejected current window | Filter mode, blocked reasons, next allowed UTC |

### Calendar Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `WeekendDetected` | Weekend state entered | Broker-local date, weekend days config |
| `HolidayDetected` | Holiday state entered | Holiday name, date, partial session list |
| `DSTTransition` | DST offset change detected | Timezone, old offset, new offset, transition time |

### Analysis Completion Events

| Event Type | Trigger | Payload Summary |
|------------|---------|-----------------|
| `SessionAnalysisUpdated` | Full analysis cycle complete | Full `SessionAnalysis` summary |

---

## Contract Events (Event Bus Names)

These names maintain compatibility with the legacy Session Engine contract ([session-engine.md](../engines/session-engine.md)) and Decision Engine subscriptions ([decision-engine.md](../engines/decision-engine.md)).

| Contract Name | Maps To | Trigger |
|---------------|---------|---------|
| `analysis.session.completed` | `SessionAnalysisUpdated` | Analysis finished |
| `analysis.session.transition` | `SessionStarted` / `SessionEnded` | Session boundary crossed |
| `analysis.session.high_impact_start` | `KillZoneEntered` | Kill zone entered (high-impact window) |
| `analysis.session.high_impact_end` | `KillZoneExited` | Kill zone exited |
| `analysis.session.overlap_started` | `OverlapStarted` | Overlap began |
| `analysis.session.overlap_ended` | `OverlapEnded` | Overlap ended |
| `analysis.session.daily_open` | `DailyOpenResolved` | Daily open resolved |
| `analysis.session.weekly_open` | `WeeklyOpenResolved` | Weekly open resolved |
| `analysis.session.monthly_open` | `MonthlyOpenResolved` | Monthly open resolved |
| `analysis.session.high_updated` | `SessionHighUpdated` | Session high revised |
| `analysis.session.low_updated` | `SessionLowUpdated` | Session low revised |
| `analysis.session.or_complete` | `OpeningRangeComplete` | Opening range complete |
| `analysis.session.or_breakout` | `OpeningRangeBreakout` | Opening range breakout |
| `analysis.session.ib_complete` | `InitialBalanceComplete` | Initial balance complete |
| `analysis.session.ib_extension` | `InitialBalanceExtension` | IB extension detected |
| `analysis.session.filter_blocked` | `TimeFilterBlocked` | Time filter blocked |
| `analysis.session.weekend` | `WeekendDetected` | Weekend detected |
| `analysis.session.holiday` | `HolidayDetected` | Holiday detected |
| `analysis.session.dst_transition` | `DSTTransition` | DST transition detected |
| `analysis.session.error` | — | Analysis failure |

### High-Impact Window Mapping

`analysis.session.high_impact_start` / `high_impact_end` map to kill zone enter/exit events. Any active kill zone qualifies as a high-impact window. Downstream engines may further filter by kill zone ID or quality score.

---

## Event Payload Schemas

### SessionStarted Payload

```json
{
  "session_id": "london",
  "display_name": "London Session",
  "window_start_utc": "2026-07-16T07:00:00+00:00",
  "window_end_utc": "2026-07-16T16:00:00+00:00",
  "phase": "opening",
  "broker_timezone": "Europe/Nicosia",
  "trading_day_id": "2026-07-16"
}
```

### SessionEnded Payload

```json
{
  "session_id": "london",
  "window_end_utc": "2026-07-16T16:00:00+00:00",
  "final_phase": "closing",
  "session_high": "2678.40",
  "session_low": "2665.10",
  "range_size_pips": "133.0"
}
```

### KillZoneEntered Payload

```json
{
  "kill_zone_id": "london_open",
  "display_name": "London Open Kill Zone",
  "parent_session": "london",
  "window_start_utc": "2026-07-16T07:00:00+00:00",
  "window_end_utc": "2026-07-16T10:00:00+00:00",
  "quality_score": "0.78",
  "quality_tier": "high",
  "volatility_profile": "high"
}
```

### KillZoneExited Payload

```json
{
  "kill_zone_id": "london_open",
  "window_end_utc": "2026-07-16T10:00:00+00:00",
  "elapsed_minutes": 180,
  "final_quality_score": "0.72"
}
```

### OverlapStarted Payload

```json
{
  "overlap_id": "london_new_york",
  "sessions": ["london", "new_york"],
  "window_start_utc": "2026-07-16T12:00:00+00:00",
  "window_end_utc": "2026-07-16T16:00:00+00:00",
  "quality_score": "0.85",
  "quality_tier": "high"
}
```

### OverlapEnded Payload

```json
{
  "overlap_id": "london_new_york",
  "window_end_utc": "2026-07-16T16:00:00+00:00",
  "duration_minutes": 240
}
```

### DailyOpenResolved Payload

```json
{
  "period_type": "daily",
  "open_price": "2668.50",
  "open_time_utc": "2026-07-16T00:00:00+00:00",
  "trading_day_id": "2026-07-16",
  "is_confirmed": true,
  "broker_midnight_utc": "2026-07-15T21:00:00+00:00"
}
```

### WeeklyOpenResolved Payload

```json
{
  "period_type": "weekly",
  "open_price": "2655.20",
  "open_time_utc": "2026-07-14T00:00:00+00:00",
  "week_id": "2026-W29",
  "is_confirmed": true
}
```

### MonthlyOpenResolved Payload

```json
{
  "period_type": "monthly",
  "open_price": "2640.00",
  "open_time_utc": "2026-07-01T00:00:00+00:00",
  "month_id": "2026-07",
  "is_confirmed": true
}
```

### SessionHighUpdated Payload

```json
{
  "session_id": "london",
  "session_high": "2678.40",
  "previous_high": "2675.80",
  "high_time_utc": "2026-07-16T09:45:00+00:00",
  "trading_day_id": "2026-07-16"
}
```

### SessionLowUpdated Payload

```json
{
  "session_id": "london",
  "session_low": "2665.10",
  "previous_low": "2666.50",
  "low_time_utc": "2026-07-16T08:15:00+00:00",
  "trading_day_id": "2026-07-16"
}
```

### OpeningRangeComplete Payload

```json
{
  "range_id": "or-london-2026-07-16",
  "session_id": "london",
  "high": "2672.30",
  "low": "2668.90",
  "midpoint": "2670.60",
  "range_size_pips": "34.0",
  "duration_minutes": 30,
  "formation_end_utc": "2026-07-16T07:30:00+00:00"
}
```

### OpeningRangeBreakout Payload

```json
{
  "range_id": "or-london-2026-07-16",
  "session_id": "london",
  "breakout_direction": "bullish",
  "breakout_price": "2674.50",
  "or_high": "2672.30",
  "or_low": "2668.90",
  "buffer_pips": "2.0"
}
```

### InitialBalanceComplete Payload

```json
{
  "balance_id": "ib-london-2026-07-16",
  "session_id": "london",
  "high": "2675.00",
  "low": "2667.50",
  "midpoint": "2671.25",
  "range_size_pips": "75.0",
  "duration_minutes": 60,
  "formation_end_utc": "2026-07-16T08:00:00+00:00"
}
```

### InitialBalanceExtension Payload

```json
{
  "balance_id": "ib-london-2026-07-16",
  "session_id": "london",
  "extension_direction": "bullish",
  "extension_size_pips": "12.0",
  "ib_high": "2675.00",
  "ib_low": "2667.50",
  "extension_price": "2676.20"
}
```

### TimeFilterBlocked Payload

```json
{
  "filter_mode": "kill_zone_only",
  "is_allowed": false,
  "blocked_reasons": ["No active kill zone at reference time"],
  "active_sessions": ["tokyo"],
  "active_kill_zones": [],
  "next_allowed_utc": "2026-07-16T07:00:00+00:00"
}
```

### WeekendDetected Payload

```json
{
  "is_weekend": true,
  "broker_local_date": "2026-07-18",
  "weekend_days": ["saturday", "sunday"],
  "weekend_trading_enabled": true,
  "market_availability": "open"
}
```

### HolidayDetected Payload

```json
{
  "is_holiday": true,
  "holiday_name": "Christmas Day",
  "broker_local_date": "2026-12-25",
  "market_availability": "closed",
  "partial_holiday_sessions": []
}
```

### DSTTransition Payload

```json
{
  "timezone": "Europe/London",
  "is_dst_transition": true,
  "previous_offset_minutes": 0,
  "new_offset_minutes": 60,
  "transition_time_utc": "2026-03-29T01:00:00+00:00",
  "affected_sessions": ["london"]
}
```

### SessionAnalysisUpdated Payload

```json
{
  "symbol": "GOLD.i#",
  "timeframe": "M15",
  "timestamp_utc": "2026-07-16T08:30:00+00:00",
  "primary_session": "london",
  "session_phase": "opening",
  "active_sessions": ["london", "tokyo"],
  "active_kill_zones": ["london_open"],
  "market_availability": "open",
  "volatility_profile": "high",
  "liquidity_availability": "moderate",
  "quality": "high",
  "confidence": "0.82",
  "strength": "0.76",
  "time_of_day_filter_allowed": true,
  "daily_open": "2668.50",
  "session_high": "2675.00",
  "session_low": "2667.50",
  "evidence_summary": [
    "London session active — opening phase",
    "London Open kill zone active — high quality",
    "London/New York overlap in 3h 30m"
  ]
}
```

### Error Event Payload (`analysis.session.error`)

```json
{
  "error_code": "MS_INVALID_TIMESTAMP",
  "message": "timestamp_utc must be timezone-aware UTC",
  "symbol": "GOLD.i#",
  "timeframe": "M15",
  "timestamp_utc": "2026-07-16T08:30:00+00:00"
}
```

---

## Consumed Events

| Event | Source | Action |
|-------|--------|--------|
| `market.candle.closed` | Market Data Engine | Trigger analysis refresh; update extremes, OR, IB |
| `market.tick.received` | Market Data Engine | Optional live session phase monitoring |
| `analysis.structure.completed` | Market Structure Engine | Cache structure for quality scoring |
| `analysis.liquidity.completed` | Market Liquidity Engine | Cache liquidity state for scoring |
| `analysis.premium_discount.completed` | Premium / Discount Engine | Cache pricing context for scoring |
| `system.config.updated` | Config service | Reload session boundaries and kill zone windows |

---

## Event Emission Rules

### Transition Detection

Events emit on **state change** compared to `prior_state`:

```
if not prior_state.london_active and current.london_active:
    emit SessionStarted(london)
if prior_state.london_active and not current.london_active:
    emit SessionEnded(london)
```

Same pattern applies to kill zones, overlaps, weekend/holiday, and filter state.

### Deduplication

| Rule | Description |
|------|-------------|
| Same event type + entity ID within same analysis cycle | Emit once |
| Extreme updates | Emit only when price actually changes |
| OR/IB complete | Emit once per session per trading day |
| Analysis complete | Emit every cycle |

### Event Ordering

Within a single analysis cycle, events publish in causal order:

1. Calendar events (`WeekendDetected`, `HolidayDetected`, `DSTTransition`)
2. Period open events (`DailyOpenResolved`, etc.)
3. Session lifecycle (`SessionStarted`, `SessionEnded`)
4. Kill zone lifecycle (`KillZoneEntered`, `KillZoneExited`)
5. Overlap lifecycle (`OverlapStarted`, `OverlapEnded`)
6. Extreme updates (`SessionHighUpdated`, `SessionLowUpdated`)
7. OR/IB lifecycle
8. Filter events (`TimeFilterBlocked`)
9. Analysis completion (`SessionAnalysisUpdated`)

---

## Subscriber Integration Examples (Planned)

### Decision Engine

```python
publisher.subscribe(lambda e: (
    decision_engine.update_session(e.payload)
    if e.event_type == "SessionAnalysisUpdated"
    else None
))
```

### Dashboard (Future)

```python
# Subscribe to contract bus names
event_bus.on("analysis.session.completed", dashboard.render_session_panel)
event_bus.on("analysis.session.high_impact_start", dashboard.highlight_kill_zone)
```

---

## Event Enum Reference

### MarketSessionsEventKind

| Value | Contract Bus Name |
|-------|-------------------|
| `SessionStarted` | `analysis.session.transition` |
| `SessionEnded` | `analysis.session.transition` |
| `KillZoneEntered` | `analysis.session.high_impact_start` |
| `KillZoneExited` | `analysis.session.high_impact_end` |
| `OverlapStarted` | `analysis.session.overlap_started` |
| `OverlapEnded` | `analysis.session.overlap_ended` |
| `DailyOpenResolved` | `analysis.session.daily_open` |
| `WeeklyOpenResolved` | `analysis.session.weekly_open` |
| `MonthlyOpenResolved` | `analysis.session.monthly_open` |
| `SessionHighUpdated` | `analysis.session.high_updated` |
| `SessionLowUpdated` | `analysis.session.low_updated` |
| `OpeningRangeComplete` | `analysis.session.or_complete` |
| `OpeningRangeBreakout` | `analysis.session.or_breakout` |
| `InitialBalanceComplete` | `analysis.session.ib_complete` |
| `InitialBalanceExtension` | `analysis.session.ib_extension` |
| `TimeFilterBlocked` | `analysis.session.filter_blocked` |
| `WeekendDetected` | `analysis.session.weekend` |
| `HolidayDetected` | `analysis.session.holiday` |
| `DSTTransition` | `analysis.session.dst_transition` |
| `SessionAnalysisUpdated` | `analysis.session.completed` |

---

## Related Documents

| Document | Path |
|----------|------|
| Architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Data Pipeline | [DATA_PIPELINE.md](./DATA_PIPELINE.md) |
| Public Interfaces | [PUBLIC_INTERFACES.md](./PUBLIC_INTERFACES.md) |
| Configuration | [CONFIGURATION.md](./CONFIGURATION.md) |
| Legacy Session Engine | [../engines/session-engine.md](../engines/session-engine.md) |
| Decision Engine | [../engines/decision-engine.md](../engines/decision-engine.md) |

# News & Macro Engine — Interface Contract

**Engine ID:** `news_macro`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Monitor news and macroeconomic events that affect XAUUSD, assess their impact severity, and provide explainable context about whether external catalysts support or conflict with technical analysis.

---

## 2. Responsibilities

- Ingest macroeconomic event calendar data from approved free sources
- Ingest gold-relevant news headlines from approved free sources
- Classify events by impact level (`low`, `medium`, `high`)
- Assess directional bias impact on gold (`bullish`, `bearish`, `neutral`, `undetermined`)
- Flag active and upcoming high-impact windows
- Publish news/macro context with evidence
- Emit no trade signals

**Out of scope:** Paid news APIs, trade decisions, execution, technical analysis.

**Constraint:** Only free or already-approved data sources may be used per Constitution.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp_utc` | `datetime` | Yes | Current UTC timestamp |
| `symbol` | `string` | Yes | Must be `XAUUSD` |
| `lookback_hours` | `integer` | No | Hours of recent news to include |
| `lookahead_hours` | `integer` | No | Hours of upcoming events to include |
| `session_context` | `SessionAnalysis` | No | From Session Engine |

---

## 4. Outputs

### NewsMacroAnalysis

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `string` | `XAUUSD` |
| `timestamp_utc` | `datetime` | Analysis timestamp (UTC) |
| `upcoming_events` | `MacroEvent[]` | Scheduled macro events |
| `recent_news` | `NewsItem[]` | Recent gold-relevant news |
| `active_event_window` | `boolean` | Whether a high-impact event is active |
| `impact_bias` | `enum` | `bullish`, `bearish`, `neutral`, `undetermined` |
| `impact_level` | `enum` | `none`, `low`, `medium`, `high` |
| `confidence` | `decimal` | 0.0–1.0 |
| `evidence` | `string[]` | Human-readable reasoning |
| `sources` | `string[]` | Data sources used |

### MacroEvent

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `string` | Unique event identifier |
| `name` | `string` | Event name (e.g. `US CPI`, `FOMC`) |
| `currency` | `string` | Primary currency affected |
| `scheduled_utc` | `datetime` | Scheduled release time |
| `impact` | `enum` | `low`, `medium`, `high` |
| `actual` | `string` | Actual value (if released) |
| `forecast` | `string` | Forecast value |
| `previous` | `string` | Previous value |

### NewsItem

| Field | Type | Description |
|-------|------|-------------|
| `news_id` | `string` | Unique news identifier |
| `headline` | `string` | News headline |
| `published_utc` | `datetime` | Publication time |
| `source` | `string` | Approved source name |
| `relevance` | `enum` | `low`, `medium`, `high` |
| `sentiment` | `enum` | `bullish`, `bearish`, `neutral`, `undetermined` |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Approved free data sources | External | Calendar and news feeds |
| Session Engine | Upstream | Optional session context |
| Configuration | Internal | Source URLs, filters, refresh intervals |
| SQLite | Internal | Optional event/news cache |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `analysis.news_macro.completed` | Analysis cycle complete | `NewsMacroAnalysis` |
| `analysis.news_macro.event_upcoming` | High-impact event approaching | Event details and countdown |
| `analysis.news_macro.event_released` | Macro event data released | Event with actual values |
| `analysis.news_macro.news_received` | Relevant news ingested | News item details |
| `analysis.news_macro.window_active` | High-impact window active | Window details |
| `analysis.news_macro.error` | Analysis failure | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `analysis.session.completed` | Session Engine | Optional session enrichment |
| `system.config.updated` | Config service | Reload sources and filters |
| `system.scheduled.tick` | Orchestrator | Periodic refresh trigger |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `NEWS_MACRO_SOURCES` | YAML | — | Approved source list |
| `NEWS_MACRO_REFRESH_INTERVAL_SEC` | YAML | `300` | Polling interval |
| `NEWS_MACRO_LOOKBACK_HOURS` | YAML | `24` | Recent news window |
| `NEWS_MACRO_LOOKAHEAD_HOURS` | YAML | `48` | Upcoming events window |
| `NEWS_MACRO_HIGH_IMPACT_EVENTS` | YAML | — | Event filter list |
| `NEWS_MACRO_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `NME_SOURCE_UNAVAILABLE` | Data source unreachable | Emit error; use cached data if available |
| `NME_PARSE_FAILED` | Source response unparseable | Skip source; emit warning |
| `NME_NO_APPROVED_SOURCES` | No sources configured | Return `undetermined`; emit error |
| `NME_CACHE_STALE` | Cache exceeds max age | Emit warning; attempt refresh |
| `NME_PAID_SOURCE_BLOCKED` | Paid API detected in config | Reject config; emit error |

---

## 10. Success Criteria

- Only approved free sources are used
- High-impact events are flagged before and during release windows
- Evidence cites specific events or headlines affecting the assessment
- No trade entry, stop, or target prices are emitted
- `undetermined` impact bias is valid when news context is ambiguous
- Output schema is stable for Decision Engine consumption

---

**Implementation sprint:** TBD by Product Owner

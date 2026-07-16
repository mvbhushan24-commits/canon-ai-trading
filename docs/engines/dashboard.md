# Dashboard — Interface Contract

**Component ID:** `dashboard`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD  
**Layer:** Presentation (React + Vite + TypeScript)

---

## 1. Purpose

Provide a web-based visualization layer for XAUUSD market data, engine status, analysis outputs, trading decisions, and delivery history — supporting transparency and explainability for manual traders.

---

## 2. Responsibilities

- Display live XAUUSD price chart using Lightweight Charts
- Show current and historical trading decisions with full reasoning
- Display engine status and last analysis outputs
- Show risk assessment and session context
- Display Telegram delivery log
- Consume backend API data only — no analysis logic in frontend
- Reflect NO TRADE decisions as valid outcomes in the UI

**Out of scope:** Analysis algorithms, signal generation, trade execution, Telegram sending, MT5 connection.

---

## 3. Inputs

All inputs are consumed via the FastAPI backend API (future sprints). The Dashboard does not connect directly to MT5, Telegram, or analysis engines.

| Input | Type | Source | Description |
|-------|------|--------|-------------|
| `candles` | `NormalizedCandle[]` | API `/api/v1/market/candles` | OHLCV data for chart |
| `current_price` | `NormalizedTick` | API `/api/v1/market/tick` | Live price display |
| `decisions` | `TradingDecision[]` | API `/api/v1/decisions` | Decision history |
| `latest_decision` | `TradingDecision` | API `/api/v1/decisions/latest` | Most recent decision |
| `engine_statuses` | `EngineStatus[]` | API `/api/v1/engines/status` | All engine statuses |
| `risk_assessment` | `RiskAssessment` | API `/api/v1/analysis/risk` | Latest risk output |
| `session_analysis` | `SessionAnalysis` | API `/api/v1/analysis/session` | Latest session output |
| `delivery_log` | `TelegramDeliveryResult[]` | API `/api/v1/notifications/telegram` | Delivery history |

### EngineStatus

| Field | Type | Description |
|-------|------|-------------|
| `engine_id` | `string` | Engine identifier |
| `status` | `enum` | `active`, `inactive`, `error`, `degraded` |
| `last_run_utc` | `datetime` | Last analysis timestamp |
| `last_error` | `string` | Most recent error (if any) |

---

## 4. Outputs

The Dashboard produces **UI state and user interactions** only — no backend events.

### UI Actions (User-Initiated)

| Action | Description |
|--------|-------------|
| `timeframe.selected` | User selects chart timeframe |
| `decision.selected` | User views decision detail |
| `engine.expanded` | User expands engine detail panel |
| `refresh.requested` | User manually refreshes data |

### UI State

| State | Description |
|-------|-------------|
| `chart_state` | Current timeframe, visible range, overlays |
| `selected_decision_id` | Currently viewed decision |
| `connection_status` | API connectivity indicator |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| FastAPI Backend | Upstream | All data via REST API |
| Lightweight Charts | External | Chart rendering library |
| React + Vite + TypeScript | Internal | Frontend framework |
| Configuration | Internal | `VITE_API_BASE_URL` and UI settings |

**Does not depend on** any backend engine directly.

---

## 6. Events Produced

The Dashboard is a presentation component. It does **not** produce backend event bus events.

UI telemetry (optional, future sprint):

| Event | Trigger | Destination |
|-------|---------|-------------|
| `ui.page.viewed` | Page load | Analytics (if approved) |
| `ui.decision.viewed` | Decision detail opened | Analytics (if approved) |

---

## 7. Events Consumed

The Dashboard consumes data via **API polling or WebSocket** (future sprint decision). It does not subscribe to the internal event bus directly.

| Data Stream | Source | Refresh Strategy |
|-------------|--------|-----------------|
| Live price | API | Poll or WebSocket |
| Candles | API | On timeframe change + periodic refresh |
| Decisions | API | On new decision + periodic refresh |
| Engine status | API | Periodic refresh |
| Delivery log | API | Periodic refresh |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `VITE_API_BASE_URL` | `.env` | `http://localhost:8000` | Backend API base URL |
| `DASHBOARD_DEFAULT_TIMEFRAME` | YAML | `M15` | Default chart timeframe |
| `DASHBOARD_REFRESH_INTERVAL_MS` | YAML | `5000` | Data refresh interval |
| `DASHBOARD_DECISIONS_LIMIT` | YAML | `50` | Max decisions in history view |
| `DASHBOARD_THEME` | YAML | `dark` | UI theme |

---

## 9. Error Conditions

| Code | Condition | UI Behavior |
|------|-----------|-------------|
| `DB_API_UNAVAILABLE` | Backend API unreachable | Show connection error banner |
| `DB_DATA_STALE` | Data exceeds stale threshold | Show stale data warning |
| `DB_CHART_RENDER_FAILED` | Lightweight Charts error | Show chart error state |
| `DB_DECISION_LOAD_FAILED` | Decision API error | Show error in decision panel |
| `DB_ENGINE_STATUS_FAILED` | Engine status API error | Show degraded status view |

---

## 10. Success Criteria

- Chart renders XAUUSD candles from API data using Lightweight Charts
- Every decision displays full reasoning chain and engine summaries
- NO TRADE decisions are displayed clearly as valid outcomes — not as errors
- Engine status panel shows all configured engines
- No analysis, signal generation, or trading logic exists in frontend code
- API base URL is configured via environment variable only
- UI is responsive and readable on desktop viewport (v1.0)

---

**Implementation sprint:** TBD by Product Owner

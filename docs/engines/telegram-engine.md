# Telegram Engine — Interface Contract

**Engine ID:** `telegram`  
**Version:** 0.1.0  
**Status:** Contract only — not implemented  
**Symbol:** XAUUSD

---

## 1. Purpose

Deliver explainable trading decisions and alerts from the Decision Engine to configured Telegram recipients via the Telegram Bot API.

---

## 2. Responsibilities

- Consume decision events from the Decision Engine
- Format decisions into human-readable Telegram messages
- Deliver SIGNAL, NO_TRADE, and system status alerts
- Track delivery status and retry failed messages
- Respect rate limits and message length constraints
- Never modify decision content or generate signals

**Out of scope:** Signal generation, analysis, trade execution, message content decisions.

---

## 3. Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `decision` | `TradingDecision` | Yes | From Decision Engine |
| `alert_type` | `enum` | Yes | `signal`, `no_trade`, `system`, `error` |
| `recipients` | `string[]` | No | Override chat IDs (default from config) |
| `priority` | `enum` | No | `normal`, `high` (default: `normal`) |

### TradingDecision

Uses schema defined in [Decision Engine](./decision-engine.md).

---

## 4. Outputs

### TelegramDeliveryResult

| Field | Type | Description |
|-------|------|-------------|
| `delivery_id` | `string` | Unique delivery identifier |
| `decision_id` | `string` | Reference to source decision |
| `chat_id` | `string` | Target Telegram chat ID |
| `status` | `enum` | `sent`, `failed`, `rate_limited`, `skipped` |
| `message_id` | `string` | Telegram message ID (if sent) |
| `sent_at_utc` | `datetime` | Delivery timestamp |
| `retry_count` | `integer` | Number of retry attempts |
| `error_message` | `string` | Error details (if failed) |
| `message_preview` | `string` | First 200 chars of sent message |

### FormattedMessage

| Field | Type | Description |
|-------|------|-------------|
| `text` | `string` | Formatted Telegram message (Markdown) |
| `parse_mode` | `string` | `Markdown` or `HTML` |
| `char_count` | `integer` | Message character count |

---

## 5. Dependencies

| Dependency | Type | Description |
|------------|------|-------------|
| Decision Engine | Upstream | Decision events |
| Telegram Bot API | External | Message delivery |
| Configuration | Internal | Bot token, chat IDs, templates |
| SQLite | Internal | Delivery log persistence |
| Event Bus | Internal | Publish/consume events |

---

## 6. Events Produced

| Event | Trigger | Payload Summary |
|-------|---------|-----------------|
| `notification.telegram.sent` | Message delivered | `TelegramDeliveryResult` |
| `notification.telegram.failed` | Delivery failed | Error and retry info |
| `notification.telegram.rate_limited` | Rate limit hit | Retry scheduled time |
| `notification.telegram.skipped` | Message skipped | Skip reason |
| `notification.telegram.error` | Engine error | Error code |

---

## 7. Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| `decision.signal.published` | Decision Engine | Format and send signal alert |
| `decision.no_trade.published` | Decision Engine | Send NO_TRADE notification (if enabled) |
| `decision.wait.published` | Decision Engine | Send WAIT notification (if enabled) |
| `system.status.changed` | Orchestrator | Send system status alert |
| `market.connection.lost` | Market Data Engine | Send connectivity alert |
| `system.config.updated` | Config service | Reload bot config |

---

## 8. Configuration

| Key | Source | Default | Description |
|-----|--------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | `.env` | — | Bot API token (secret) |
| `TELEGRAM_CHAT_ID` | `.env` | — | Default recipient chat ID |
| `TELEGRAM_SEND_NO_TRADE` | YAML | `false` | Send NO_TRADE notifications |
| `TELEGRAM_SEND_WAIT` | YAML | `false` | Send WAIT notifications |
| `TELEGRAM_MAX_RETRIES` | YAML | `3` | Max delivery retries |
| `TELEGRAM_RETRY_DELAY_SEC` | YAML | `5` | Delay between retries |
| `TELEGRAM_PARSE_MODE` | YAML | `Markdown` | Message parse mode |
| `TELEGRAM_ENABLED` | YAML | `false` | Engine toggle |

---

## 9. Error Conditions

| Code | Condition | Engine Behavior |
|------|-----------|-----------------|
| `TGE_TOKEN_MISSING` | Bot token not configured | Skip delivery; emit error |
| `TGE_CHAT_ID_MISSING` | No chat ID configured | Skip delivery; emit error |
| `TGE_API_ERROR` | Telegram API returns error | Retry per config; emit failed event |
| `TGE_RATE_LIMITED` | Telegram rate limit hit | Schedule retry; emit rate_limited event |
| `TGE_MESSAGE_TOO_LONG` | Message exceeds Telegram limit | Truncate with summary; note in delivery result |
| `TGE_INVALID_DECISION` | Malformed decision input | Skip; emit error |

---

## 10. Success Criteria

- SIGNAL alerts include direction, confidence, entry zone, SL, TP, and reasoning summary
- NO_TRADE alerts include blocking reasons when enabled
- Delivery status is logged for every attempt
- No decision content is altered — formatting only
- Bot token and chat ID are loaded from environment only
- Failed deliveries are retried per configuration
- Output schema supports Dashboard delivery log display

---

**Implementation sprint:** TBD by Product Owner

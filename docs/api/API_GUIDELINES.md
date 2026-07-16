# API Guidelines

Guidelines for the FastAPI API layer (implementation begins in future sprints).

## Principles

1. **RESTful design** — resource-oriented endpoints
2. **Explicit schemas** — Pydantic models for request/response
3. **No business logic in routes** — delegate to services/engines
4. **Consistent error responses** — structured error payloads
5. **Version prefix** — `/api/v1/` for all endpoints

## Planned Structure

```
backend/api/
├── routes/
│   ├── health.py       # Health check (future)
│   ├── signals.py      # Signal history (future)
│   ├── market.py       # Market data proxy (future)
│   └── engines.py      # Engine status (future)
└── schemas/
    ├── signal.py
    └── market.py
```

## Endpoint Conventions

| Method | Usage |
|--------|-------|
| GET | Read-only queries |
| POST | Create or trigger actions |
| PUT/PATCH | Updates (if needed) |
| DELETE | Removal (if needed) |

## Response Format

Success:

```json
{
  "data": {},
  "meta": {}
}
```

Error:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message"
  }
}
```

## Authentication

TBD by Product Owner for v1.0. Sprint 0 does not implement auth.

## CORS

Configured via `CORS_ORIGINS` environment variable.

## OpenAPI

FastAPI auto-generates OpenAPI docs at `/docs` when `ENABLE_API_DOCS=true`.

## Sprint 0 Status

No API routes implemented. Application shell only (`backend/main.py`).

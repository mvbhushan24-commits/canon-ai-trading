# Canon AI Trading

AI-powered Gold (XAUUSD) Trading Intelligence Platform.

Version 1.0 provides **analysis and Telegram alerts only**. Trade execution remains manual.

## Mission

Continuously analyze live market data, Smart Money Concepts, market structure, liquidity, trend, price action, macroeconomic events, news, volatility, and risk to generate high-quality, explainable trading signals.

A **NO TRADE** decision is a successful outcome when evidence is insufficient.

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Backend | FastAPI |
| Frontend | React + Vite + TypeScript |
| Database | SQLite |
| Charts | Lightweight Charts |
| Broker | XMGlobal (MetaTrader 5) |
| Notifications | Telegram Bot API |
| DevOps | Docker, Git |

## Project Structure

```
canon-ai-trading/
├── backend/           # FastAPI application and engine placeholders
│   ├── api/           # HTTP API layer (future sprints)
│   ├── core/          # Config, logging, error handling
│   ├── db/            # SQLite persistence (future sprints)
│   └── engines/       # Independent analysis engines (placeholders)
├── frontend/          # React + Vite + TypeScript (initialized)
├── config/            # External configuration templates
├── docs/              # Architecture, standards, sprint plan
├── prompts/           # Engine prompt templates (future sprints)
├── scripts/           # Development scripts
├── tests/             # Unit and integration tests
└── data/              # SQLite database (gitignored)
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional)
- Git

### Setup

```powershell
cd "C:\AI Trading"
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cd frontend
npm install
cd ..
```

### Development Scripts

```powershell
.\scripts\run-backend.ps1
.\scripts\run-frontend.ps1
.\scripts\test.ps1
.\scripts\lint.ps1
.\scripts\format.ps1
.\scripts\docker-build.ps1
```

### Docker

```powershell
copy .env.example .env
docker compose up --build
```

## Sprint Status

| Sprint | Status | Description |
|--------|--------|-------------|
| Sprint 0 | Complete | Project foundation |
| Sprint 1+ | Pending | Awaiting Product Owner approval |

## Documentation

- [Constitution](docs/CONSTITUTION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Sprint Plan](docs/SPRINT_PLAN.md)
- [Coding Standards](docs/CODING_STANDARDS.md)
- [API Guidelines](docs/API_GUIDELINES.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## License

Proprietary — Canon AI Trading project.

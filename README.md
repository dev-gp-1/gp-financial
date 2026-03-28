# gp-financial

**Ghost Protocol Financial Platform** — AR/AP evaluation, HITL agent orchestration, and multi-client portfolio dashboard.

> Migrated from [`dev-gp-1/gp-homelab`](https://github.com/dev-gp-1/gp-homelab) to its own focused repo for cleaner CI/CD, better autonomous agent (Jules) context, and GCP deployment independence.

## Architecture

```
gp-financial/
├── backend/
│   ├── agents/
│   │   ├── ar_ap_evaluator.py        # AR/AP/Txn classification engine
│   │   ├── financial_orchestrator.py  # 6-hour HITL agent cycle
│   │   ├── financial_agents.py        # Multi-agent financial runners
│   │   └── financial_agent_tools.py   # Tool definitions for agent loop
│   ├── integrations/
│   │   ├── mercury_service.py         # Mercury Bank API
│   │   ├── quickbooks_service.py      # QuickBooks Online sync
│   │   ├── stripe_service.py          # Stripe payments
│   │   ├── plaid_service.py           # Plaid bank feeds
│   │   └── financial_enrichment.py    # AI-powered data enrichment
│   └── routers/                       # FastAPI route handlers
├── dashboard/                         # React/Vite frontend (Firebase Auth)
├── tests/                             # pytest unit + integration tests
├── deploy/                            # Cloud Run Dockerfile + config
└── .github/workflows/                 # CI: pytest + vitest
```

## Clients

| ID | Client | Integrations |
|----|--------|-------------|
| `hugga` | Hugga | QuickBooks, Mercury |
| `cacoon` | Cacoon | QuickBooks |
| `gaa` | GAA | QuickBooks |
| `ghost-protocol` | Ghost Protocol LLC | Mercury, QuickBooks |

## Quick Start

```bash
# Backend
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend
cd dashboard && npm install && npm run dev
```

## Running Tests

```bash
# Python backend
python -m pytest tests/ -v

# Frontend unit tests
cd dashboard && npx vitest run

# E2E tests
cd dashboard && npx playwright test
```

## Phases

- **Phase 2 (Current):** Unit test hardening — 153 tests passing
- **Phase 3:** Jules E2E + integration test delegation
- **Phase 4:** Live Mercury/QBO connectivity
- **Phase 5:** Cloud Run production deployment

## Deployment

Target: **Google Cloud Run** + **Cloud SQL (PostgreSQL)** + **Firebase Auth**

See [`deploy/`](deploy/) for Dockerfile and Cloud Build config.

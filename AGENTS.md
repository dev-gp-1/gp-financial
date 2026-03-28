# Repository Overview

## Project Description
**gp-financial** is the Ghost Protocol Financial Platform — a multi-client AR/AP evaluation engine, HITL (Human-in-the-Loop) agent orchestration system, and interactive portfolio dashboard.

**Key Purposes:**
- **AR/AP Evaluation:** Classifies financial transactions as Accounts Receivable, Accounts Payable, or operational using AI and heuristic rules.
- **HITL Agent Orchestration:** Runs a 6-hour autonomous review cycle that evaluates financial health across all clients, flags anomalies, and queues items for human approval.
- **Multi-Client Dashboard:** A React/Vite frontend with Firebase Authentication for real-time financial portfolio analytics.
- **Platform Integrations:** Mercury Bank, QuickBooks Online, Stripe, and Plaid connectivity.

**Key Technologies:**
- **Backend:** Python (FastAPI), asyncpg (Cloud SQL PostgreSQL), Gemini API
- **Frontend:** React, Vite, TypeScript, Recharts
- **Auth:** Firebase Authentication
- **Integrations:** Mercury API, QuickBooks Online, Stripe, Plaid
- **Deployment:** Cloud Run + Cloud SQL on GCP
- **Testing:** pytest (backend), Vitest (frontend), Playwright (E2E)

## Architecture Overview

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
│   ├── src/                           # Components, API, auth
│   ├── e2e/                           # Playwright E2E tests
│   └── schema/                        # SQL schema definitions
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

## Development Workflow

- **Environment Setup:**
  - Requires Python 3.11+, Node.js 20+
  - Backend: `pip install -r backend/requirements.txt`
  - Frontend: `cd dashboard && npm install`

- **Running the Project:**
  - Backend: `uvicorn backend.main:app --reload --port 8000`
  - Frontend: `cd dashboard && npm run dev` (port 5173)

- **Testing:**
  - Backend: `python -m pytest tests/ -v`
  - Frontend: `cd dashboard && npx vitest run`
  - E2E: `cd dashboard && npx playwright test`

- **Deployment:**
  - Target: Cloud Run (GCP)
  - Database: Cloud SQL (PostgreSQL)
  - Auth: Firebase

## Phases

- **Phase 2 (Current):** Unit test hardening — 153 tests passing
- **Phase 3:** Jules E2E + integration test delegation
- **Phase 4:** Live Mercury/QBO connectivity
- **Phase 5:** Cloud Run production deployment

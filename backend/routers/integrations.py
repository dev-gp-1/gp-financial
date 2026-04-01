from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger("gp.routers.integrations")

router = APIRouter(tags=["Integrations"])

# ─── Mock implementations until DB/Agents are fully wired in Step 3 ───

@router.get("/")
async def list_integrations():
    """List all available integrations."""
    return {
        "integrations": [
            {"id": "mercury", "name": "Mercury Bank", "type": "banking"},
            {"id": "quickbooks", "name": "QuickBooks Online", "type": "accounting"},
            {"id": "stripe", "name": "Stripe", "type": "payments"},
            {"id": "plaid", "name": "Plaid", "type": "data_aggregator"},
            {"id": "paypal", "name": "PayPal", "type": "payments"}
        ]
    }

@router.get("/ar-ap")
async def get_ar_ap_classification():
    """Triggers the AR/AP Evaluator to classify records."""
    return {"status": "success", "message": "Evaluator triggered (simulated)."}

@router.get("/pending-actions")
async def get_pending_actions():
    """Retrieves HITL pending action queue (legacy endpoint)."""
    return {"actions": []}

@router.post("/approve-action/{action_id}")
async def approve_action(action_id: str, payload: Dict[str, Any]):
    """HITL approval of an agent-proposed action (legacy endpoint)."""
    action = payload.get("action", "approve")
    logger.info(f"Action {action_id} {action}d by HITL.")
    return {"status": "success", "action_id": action_id, "result": action}

# ─── Analytics Endpoints ──────────────────────────────────────────────────

@router.get("/analytics/summary")
async def get_analytics_summary():
    """Summary metrics for the dashboard."""
    return {
        "total_balance": 127843.50,
        "total_inflow_30d": 48250.00,
        "total_outflow_30d": 31720.00,
        "pending_payments": 3,
        "ar_outstanding": 22150.00,
        "ap_outstanding": 8430.00,
        "reconciliation_rate": 94.2,
        "connectors": [
            {"platform": "mercury", "connected": True, "last_sync_at": datetime.now().isoformat(), "transaction_count": 150},
            {"platform": "quickbooks", "connected": True, "last_sync_at": datetime.now().isoformat(), "transaction_count": 450}
        ]
    }

@router.get("/analytics/clients")
async def get_analytics_clients():
    """Returns a list of clients with their financial health metrics."""
    return {"clients": []}  # Frontend has demo fallback

@router.get("/analytics/firm-summary")
async def get_firm_summary():
    """Returns firm-wide aggregate metrics."""
    return {
        "total_clients": 4,
        "active_clients": 4,
        "total_ar": 153100.0,
        "total_ap": 83430.0,
        "total_revenue_ytd": 1348000.0,
        "total_managed_balance": 308243.0,
        "avg_health_score": 78,
        "pending_agent_actions": 12,
        "critical_clients": 1,
        "collection_rate_30d": 91.3
    }

@router.get("/analytics/cashflow")
async def get_cashflow(days: int = 30):
    return {"cashflow": []}

@router.get("/analytics/categories")
async def get_categories(days: int = 30):
    return {"categories": []}

@router.get("/analytics/transactions")
async def get_transactions(limit: int = 20):
    return {"transactions": []}

@router.get("/analytics/insights")
async def get_insights():
    return {"insights": []}

# ─── Connector Endpoints ──────────────────────────────────────────────────

@router.get("/{platform}/status")
async def get_connector_status(platform: str):
    valid_platforms = ["mercury", "quickbooks", "stripe", "plaid", "paypal"]
    if platform not in valid_platforms:
        raise HTTPException(status_code=404, detail="Platform not found")
    
    return {
        "connected": False,
        "last_sync_at": None,
        "transaction_count": 0
    }

@router.delete("/{platform}/disconnect")
async def disconnect_platform(platform: str):
    valid_platforms = ["mercury", "quickbooks", "stripe", "plaid", "paypal"]
    if platform not in valid_platforms:
        raise HTTPException(status_code=404, detail="Platform not found")
    return {"success": True, "platform": platform}

# ─── Mercury Specific ─────────────────────────────────────────────────────

@router.get("/mercury/pending-payments")
async def get_mercury_pending_payments():
    return {"success": True, "count": 0, "payments": []}

@router.post("/mercury/pending-payments/{payment_id}/review")
async def review_mercury_payment(payment_id: str, action: str = Body(..., embed=True)):
    return {"success": True, "status": "reviewed", "payment_id": payment_id}

@router.get("/mercury/accounts")
async def get_mercury_accounts():
    return {"accounts": []}

@router.get("/mercury/transactions")
async def get_mercury_transactions():
    return {"transactions": []}

# ─── QuickBooks Specific ──────────────────────────────────────────────────

@router.post("/quickbooks/sync")
async def sync_quickbooks(days_back: int = Body(7, embed=True)):
    return {"success": True, "synced_records": 0}

# ─── Connectivity Test ────────────────────────────────────────────────────

@router.get("/connectivity-test")
async def get_connectivity_test():
    return {
        "success": True,
        "platforms": {
            "mercury": {"connected": False},
            "quickbooks": {"connected": False},
            "stripe": {"connected": False},
            "plaid": {"connected": False}
        },
        "tested_at": datetime.now().isoformat()
    }

@router.post("/connectivity-test")
async def run_connectivity_test(params: Dict[str, Any] = Body(...)):
    return {"success": True, "platforms": {}}

# ─── Agent Orchestrator ───────────────────────────────────────────────────

@router.get("/agents/pending-actions")
async def get_agent_pending_actions(tenant_id: Optional[str] = None, limit: int = 50):
    return {"actions": [], "total": 0}

@router.get("/agents/stats")
async def get_agent_stats():
    return {"agents": {}, "last_cycle": None}

@router.post("/agents/run-cycle")
async def run_agent_cycle(tenant_id: str = Body("all", embed=True)):
    return {"success": True, "message": f"Cycle triggered for {tenant_id}"}

@router.post("/agents/actions/{action_id}/review")
async def review_agent_action(action_id: str, decision: str = Body(...), executed_by: str = Body(...)):
    if decision not in ["approve", "dismiss"]:
        return {"success": False, "error": "Invalid decision"}
    return {"success": True, "action_id": action_id, "decision": decision}

@router.get("/agents/evaluate/{tenant_id}")
async def evaluate_tenant(tenant_id: str):
    return {
        "success": True,
        "tenant_id": tenant_id,
        "ar": [],
        "ap": [],
        "metrics": {"health_score": 85}
    }

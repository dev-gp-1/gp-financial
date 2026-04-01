from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
import logging

logger = logging.getLogger("gp.routers.integrations")

router = APIRouter(tags=["Integrations"])

# ─── Mock implementations until DB/Agents are fully wired in Step 3 ───

@router.get("/ar-ap")
async def get_ar_ap_classification():
    """Triggers the AR/AP Evaluator to classify records."""
    # Placeholder for: return ArapEvaluator().evaluate_all()
    return {"status": "success", "message": "Evaluator triggered (simulated)."}

@router.get("/pending-actions")
async def get_pending_actions():
    """Retrieves HITL pending action queue."""
    return {"actions": []}

@router.post("/approve-action/{action_id}")
async def approve_action(action_id: str, payload: Dict[str, Any]):
    """HITL approval of an agent-proposed action."""
    action = payload.get("action", "approve")
    logger.info(f"Action {action_id} {action}d by HITL.")
    return {"status": "success", "action_id": action_id, "result": action}

@router.get("/analytics/summary")
async def get_analytics_summary():
    """Summary metrics for the dashboard."""
    # This falls back gracefully in the frontend script `api.ts` if not deployed,
    # but since it's now deployed, we'll return a basic structure to prevent 404s.
    return {
        "total_balance": 127843.50,
        "total_inflow_30d": 48250.00,
        "total_outflow_30d": 31720.00,
        "pending_payments": 3,
        "ar_outstanding": 22150.00,
        "ap_outstanding": 8430.00,
        "reconciliation_rate": 94.2,
        "connectors": []
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

# Simple status endpoints for the connectors
@router.get("/{platform}/status")
async def get_connector_status(platform: str):
    valid_platforms = ["mercury", "quickbooks", "stripe", "plaid"]
    if platform not in valid_platforms:
        raise HTTPException(status_code=404, detail="Platform not found")
    
    return {
        "connected": False,
        "last_sync_at": None,
        "transaction_count": 0
    }

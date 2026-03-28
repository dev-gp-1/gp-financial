"""
Financial Agent Tools — Tool definitions for the AgentLoop financial sub-agents.

Provides read-only data retrieval tools that agents use to evaluate AR/AP health,
bank balances, reconciliation gaps, and collection velocity.

Tools:
    - get_ar_aging_report(tenant_id)
    - get_ap_due_report(tenant_id)
    - get_bank_balance(tenant_id)
    - get_unmatched_transactions(tenant_id)
    - get_vendor_payment_history(vendor_name)
    - get_client_collection_velocity(client_name)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger("gp.financial_tools")


# ── Tool Definitions (schemas for AgentLoop) ─────────────────────────────

FINANCIAL_TOOL_SCHEMAS = [
    {
        "name": "get_ar_aging_report",
        "description": (
            "Get accounts receivable aging report for a tenant. "
            "Returns all open invoices bucketed by age: current (0-30), overdue_30 (31-60), "
            "overdue_60 (61-90), overdue_90 (90+), and totals. Use this to identify "
            "collection priorities and overdue invoices."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "The tenant/client ID"},
            },
            "required": ["tenant_id"],
        },
    },
    {
        "name": "get_ap_due_report",
        "description": (
            "Get accounts payable report for a tenant. "
            "Returns all open bills with due dates, amounts, and overdue status. "
            "Use this to identify bills that need payment and evaluate AP aging."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "The tenant/client ID"},
            },
            "required": ["tenant_id"],
        },
    },
    {
        "name": "get_bank_balance",
        "description": (
            "Get current bank account balances from Mercury Bank for a tenant. "
            "Returns account names, current balances, and available balances."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "The tenant/client ID"},
            },
            "required": ["tenant_id"],
        },
    },
    {
        "name": "get_unmatched_transactions",
        "description": (
            "Get transactions from Mercury that haven't been matched to QuickBooks entries. "
            "Returns bank transactions without a corresponding ledger entry, useful for "
            "identifying reconciliation gaps."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "The tenant/client ID"},
                "days_back": {"type": "integer", "description": "Number of days to look back (default 30)", "default": 30},
            },
            "required": ["tenant_id"],
        },
    },
    {
        "name": "get_vendor_payment_history",
        "description": (
            "Get payment history for a specific vendor. Returns recent payments, "
            "average payment terms, and any overdue patterns."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string", "description": "Vendor name to look up"},
                "tenant_id": {"type": "string", "description": "The tenant/client ID"},
            },
            "required": ["vendor_name", "tenant_id"],
        },
    },
    {
        "name": "get_client_collection_velocity",
        "description": (
            "Calculate days-sales-outstanding (DSO) and collection velocity for a client. "
            "Returns average time to collect, current open AR, and trend data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Client/customer name"},
                "tenant_id": {"type": "string", "description": "The tenant/client ID"},
            },
            "required": ["client_name", "tenant_id"],
        },
    },
]


# ── Tool Implementations ─────────────────────────────────────────────────

class FinancialToolExecutor:
    """Executes financial tools against the database and API integrations."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Route tool calls to the appropriate handler."""
        handlers = {
            "get_ar_aging_report": self._ar_aging_report,
            "get_ap_due_report": self._ap_due_report,
            "get_bank_balance": self._bank_balance,
            "get_unmatched_transactions": self._unmatched_transactions,
            "get_vendor_payment_history": self._vendor_payment_history,
            "get_client_collection_velocity": self._collection_velocity,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = await handler(**args)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return json.dumps({"error": str(e)})

    async def _ar_aging_report(self, tenant_id: str) -> Dict:
        """Pull AR aging from transactions table."""
        now = datetime.now(timezone.utc).date()
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, entity_name, amount, date, due_date, status,
                       metadata, items
                FROM transactions
                WHERE type = 'receivable' AND status NOT IN ('paid', 'written_off')
                  AND (metadata->>'tenant_id' = $1 OR $1 = 'all')
                ORDER BY due_date ASC
            """, tenant_id)

        buckets = {
            "current": [],       # Not yet due or 0-30 days past
            "overdue_30": [],    # 31-60 days past due
            "overdue_60": [],    # 61-90 days past due
            "overdue_90": [],    # 90+ days past due
        }
        totals = {"current": 0, "overdue_30": 0, "overdue_60": 0, "overdue_90": 0}

        for row in rows:
            due = row["due_date"] or row["date"] or now
            days_past = (now - due).days if due else 0

            entry = {
                "id": row["id"],
                "entity": row["entity_name"],
                "amount": float(row["amount"]),
                "due_date": str(due),
                "days_past_due": max(0, days_past),
                "status": row["status"],
            }

            if days_past <= 30:
                buckets["current"].append(entry)
                totals["current"] += entry["amount"]
            elif days_past <= 60:
                buckets["overdue_30"].append(entry)
                totals["overdue_30"] += entry["amount"]
            elif days_past <= 90:
                buckets["overdue_60"].append(entry)
                totals["overdue_60"] += entry["amount"]
            else:
                buckets["overdue_90"].append(entry)
                totals["overdue_90"] += entry["amount"]

        total_ar = sum(totals.values())
        return {
            "tenant_id": tenant_id,
            "total_ar_outstanding": total_ar,
            "buckets": {k: {"count": len(v), "total": totals[k], "invoices": v[:10]} for k, v in buckets.items()},
            "overdue_percentage": round((totals["overdue_30"] + totals["overdue_60"] + totals["overdue_90"]) / max(total_ar, 1) * 100, 1),
            "critical_count": len(buckets["overdue_90"]),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _ap_due_report(self, tenant_id: str) -> Dict:
        """Pull AP aging from transactions table."""
        now = datetime.now(timezone.utc).date()
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, entity_name, amount, date, due_date, status, metadata
                FROM transactions
                WHERE type = 'payable' AND status NOT IN ('paid', 'rejected')
                  AND (metadata->>'tenant_id' = $1 OR $1 = 'all')
                ORDER BY due_date ASC
            """, tenant_id)

        due_soon = []   # Due within 7 days
        overdue = []    # Past due
        scheduled = []  # Not yet near due

        for row in rows:
            due = row["due_date"] or row["date"] or now
            days_until = (due - now).days if due else 0
            entry = {
                "id": row["id"],
                "vendor": row["entity_name"],
                "amount": float(row["amount"]),
                "due_date": str(due),
                "days_until_due": days_until,
                "status": row["status"],
            }
            if days_until < 0:
                overdue.append(entry)
            elif days_until <= 7:
                due_soon.append(entry)
            else:
                scheduled.append(entry)

        return {
            "tenant_id": tenant_id,
            "total_ap_outstanding": sum(float(r["amount"]) for r in rows),
            "overdue": {"count": len(overdue), "total": sum(e["amount"] for e in overdue), "bills": overdue[:10]},
            "due_soon": {"count": len(due_soon), "total": sum(e["amount"] for e in due_soon), "bills": due_soon[:10]},
            "scheduled": {"count": len(scheduled), "total": sum(e["amount"] for e in scheduled)},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _bank_balance(self, tenant_id: str) -> Dict:
        """Get Mercury bank balances via the stored config."""
        async with self.db_pool.acquire() as conn:
            config = await conn.fetchrow(
                "SELECT settings FROM integration_configs WHERE platform = 'mercury' AND (tenant_id = $1 OR tenant_id IS NULL)",
                tenant_id,
            )
        if not config:
            return {"error": "Mercury not connected for this tenant", "tenant_id": tenant_id}

        settings = json.loads(config["settings"]) if isinstance(config["settings"], str) else dict(config["settings"])
        token = settings.get("api_token", "")
        if not token:
            return {"error": "No Mercury API token stored"}

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{MERCURY_API_BASE}/accounts",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return {"error": f"Mercury API returned {resp.status}"}
                data = await resp.json()

        accounts = data.get("accounts", [])
        return {
            "tenant_id": tenant_id,
            "accounts": [
                {
                    "name": a.get("name", "Unknown"),
                    "type": a.get("type", "checking"),
                    "current_balance": float(a.get("currentBalance", 0)),
                    "available_balance": float(a.get("availableBalance", 0)),
                }
                for a in accounts
            ],
            "total_balance": sum(float(a.get("currentBalance", 0)) for a in accounts),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _unmatched_transactions(self, tenant_id: str, days_back: int = 30) -> Dict:
        """Find Mercury transactions not matched to ledger entries."""
        async with self.db_pool.acquire() as conn:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()
            rows = await conn.fetch("""
                SELECT id, entity_name, amount, date, status, metadata
                FROM transactions
                WHERE date >= $1
                  AND (metadata->>'bank_confirmed') IS NULL
                  AND (metadata->>'tenant_id' = $2 OR $2 = 'all')
                ORDER BY date DESC
            """, cutoff, tenant_id)

        unmatched = [
            {
                "id": r["id"],
                "entity": r["entity_name"],
                "amount": float(r["amount"]),
                "date": str(r["date"]),
                "status": r["status"],
            }
            for r in rows
        ]

        return {
            "tenant_id": tenant_id,
            "unmatched_count": len(unmatched),
            "total_unmatched_value": sum(e["amount"] for e in unmatched),
            "transactions": unmatched[:20],
            "days_back": days_back,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _vendor_payment_history(self, vendor_name: str, tenant_id: str) -> Dict:
        """Get payment history for a vendor."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, amount, date, due_date, status, metadata
                FROM transactions
                WHERE type = 'payable' AND LOWER(entity_name) LIKE LOWER($1)
                  AND (metadata->>'tenant_id' = $2 OR $2 = 'all')
                ORDER BY date DESC
                LIMIT 20
            """, f"%{vendor_name}%", tenant_id)

        payments = []
        total_paid = 0
        days_to_pay = []

        for r in rows:
            entry = {
                "amount": float(r["amount"]),
                "date": str(r["date"]),
                "due_date": str(r["due_date"]) if r["due_date"] else None,
                "status": r["status"],
            }
            payments.append(entry)
            if r["status"] == "paid" and r["date"] and r["due_date"]:
                total_paid += float(r["amount"])
                days_to_pay.append((r["date"] - r["due_date"]).days)

        avg_dtp = round(sum(days_to_pay) / max(len(days_to_pay), 1), 1) if days_to_pay else None

        return {
            "vendor": vendor_name,
            "tenant_id": tenant_id,
            "total_payments": len(payments),
            "total_paid": total_paid,
            "avg_days_to_pay": avg_dtp,
            "recent_payments": payments[:10],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _collection_velocity(self, client_name: str, tenant_id: str) -> Dict:
        """Calculate DSO and collection velocity for a client."""
        async with self.db_pool.acquire() as conn:
            all_invoices = await conn.fetch("""
                SELECT id, amount, date, due_date, status, metadata
                FROM transactions
                WHERE type = 'receivable' AND LOWER(entity_name) LIKE LOWER($1)
                  AND (metadata->>'tenant_id' = $2 OR $2 = 'all')
                ORDER BY date DESC
                LIMIT 50
            """, f"%{client_name}%", tenant_id)

        total_ar = 0
        total_revenue_90d = 0
        collection_times = []
        open_invoices = []

        cutoff_90d = (datetime.now(timezone.utc) - timedelta(days=90)).date()

        for inv in all_invoices:
            amount = float(inv["amount"])
            if inv["status"] in ("paid",):
                if inv["date"] and inv.get("due_date"):
                    # Estimate collection time
                    meta = json.loads(inv["metadata"]) if isinstance(inv["metadata"], str) else (inv["metadata"] or {})
                    reconciled_at = meta.get("reconciled_at")
                    if reconciled_at:
                        try:
                            collected = datetime.fromisoformat(reconciled_at.replace("Z", "+00:00")).date()
                            days = (collected - inv["date"]).days
                            collection_times.append(days)
                        except Exception:
                            pass
                if inv["date"] and inv["date"] >= cutoff_90d:
                    total_revenue_90d += amount
            else:
                total_ar += amount
                open_invoices.append({
                    "id": inv["id"],
                    "amount": amount,
                    "date": str(inv["date"]),
                    "due_date": str(inv["due_date"]) if inv["due_date"] else None,
                    "status": inv["status"],
                })

        avg_dso = round(sum(collection_times) / max(len(collection_times), 1), 1) if collection_times else None

        return {
            "client": client_name,
            "tenant_id": tenant_id,
            "dso_days": avg_dso,
            "open_ar": total_ar,
            "open_invoice_count": len(open_invoices),
            "revenue_90d": total_revenue_90d,
            "collection_samples": len(collection_times),
            "open_invoices": open_invoices[:10],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


MERCURY_API_BASE = "https://api.mercury.com/api/v1"

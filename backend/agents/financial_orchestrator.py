"""
Financial Agent Orchestrator — Scheduled evaluation + HITL action pipeline.

Wraps the existing financial_agents.py MQTT-based agents with a higher-level
orchestrator that runs on a cron schedule (6-hour default) and writes
proposed actions to `pending_agent_actions` for HITL approval.

Architecture:
    Agent Orchestrator  (this file)
    ├── Collector     — AR aging -> collection actions
    ├── Paymaster     — AP due -> payment scheduling
    └── Reconciler    — Bank vs books -> match suggestions

Each cycle:
1. Runs ArapEvaluator to classify all AR/AP/Txn records
2. Generates proposed actions with priority + estimated impact
3. Writes to `pending_agent_actions` table
4. Dashboard HITL modal displays for approval
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("gp.financial_orchestrator")


# ── Constants ────────────────────────────────────────────────────────────

DEFAULT_LOOP_INTERVAL_HOURS = 6

AGENT_CONFIGS = {
    "collector": {
        "name": "Collector",
        "label": "COL",
        "description": "Monitors accounts receivable aging and automates collection workflows",
        "focus": "AR invoices overdue > 30 days",
        "tools": ["get_ar_aging_report", "get_client_collection_velocity"],
    },
    "paymaster": {
        "name": "Paymaster",
        "label": "PAY",
        "description": "Manages accounts payable scheduling and payment queue",
        "focus": "AP bills approaching or past due date",
        "tools": ["get_ap_due_report", "get_bank_balance", "get_vendor_payment_history"],
    },
    "reconciler": {
        "name": "Reconciler",
        "label": "REC",
        "description": "Matches bank transactions against ledger entries for clean books",
        "focus": "Unmatched transactions between Mercury and QuickBooks",
        "tools": ["get_unmatched_transactions", "get_bank_balance"],
    },
}


# ── Agent Orchestrator ───────────────────────────────────────────────────

class FinancialAgentOrchestrator:
    """Coordinates all financial sub-agents on a recurring schedule."""

    def __init__(self, db_pool, gemini_api_key: str = None):
        self.db_pool = db_pool
        self.gemini_api_key = gemini_api_key

    async def run_cycle(self, tenant_id: str = "all") -> Dict[str, Any]:
        """Execute a full agent cycle for a tenant."""
        logger.info(f"Starting financial agent cycle for tenant={tenant_id}")
        start = datetime.now(timezone.utc)

        from .ar_ap_evaluator import ArapEvaluator
        evaluator = ArapEvaluator(self.db_pool)
        report = await evaluator.evaluate(tenant_id)

        results = {
            "tenant_id": tenant_id,
            "cycle_start": start.isoformat(),
            "evaluation": {
                "health_score": report.health_score,
                "ar_total": report.ar_total,
                "ap_total": report.ap_total,
                "reconciliation_rate": report.reconciliation_rate,
                "txn_unmatched": report.txn_unmatched,
            },
            "agents": {},
            "actions_generated": 0,
            "actions_by_priority": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        }

        actions_written = 0
        for action in report.recommended_actions:
            try:
                await self._write_pending_action(
                    tenant_id=tenant_id,
                    agent=action["agent"],
                    action=action["action"],
                    priority=action["priority"],
                    title=action["title"],
                    description=action.get("description", ""),
                    estimated_impact=action.get("estimated_impact"),
                    params={"automatable": action.get("automatable", False)},
                )
                actions_written += 1
                priority = action.get("priority", "medium")
                results["actions_by_priority"][priority] = results["actions_by_priority"].get(priority, 0) + 1
            except Exception as e:
                logger.error(f"Failed to write action: {e}")

        results["actions_generated"] = actions_written

        for agent_key, config in AGENT_CONFIGS.items():
            agent_actions = [a for a in report.recommended_actions if a["agent"] == agent_key]
            results["agents"][agent_key] = {
                "name": config["name"],
                "label": config.get("label", agent_key.upper()[:3]),
                "actions_generated": len(agent_actions),
                "actions": agent_actions,
            }

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 1)
        results["cycle_end"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Agent cycle complete: {actions_written} actions generated "
            f"(health={report.health_score}, elapsed={elapsed:.1f}s)"
        )

        return results

    async def _write_pending_action(
        self,
        tenant_id: str,
        agent: str,
        action: str,
        priority: str,
        title: str,
        description: str = "",
        estimated_impact: float = None,
        params: Dict = None,
    ) -> str:
        """Write a proposed action to the pending_agent_actions table."""
        action_id = str(uuid.uuid4())
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO pending_agent_actions
                    (id, tenant_id, agent, action, priority, title, description,
                     estimated_impact, params, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, 'pending')
                ON CONFLICT DO NOTHING
            """, action_id, tenant_id, agent, action, priority, title,
                description, estimated_impact, json.dumps(params or {}))

        return action_id

    async def get_pending_actions(
        self,
        tenant_id: str = "all",
        status: str = "pending",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Retrieve pending agent actions for HITL review."""
        async with self.db_pool.acquire() as conn:
            if tenant_id == "all":
                rows = await conn.fetch("""
                    SELECT * FROM pending_agent_actions
                    WHERE status = $1
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END,
                        created_at DESC
                    LIMIT $2
                """, status, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM pending_agent_actions
                    WHERE tenant_id = $1 AND status = $2
                    ORDER BY
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                        END,
                        created_at DESC
                    LIMIT $3
                """, tenant_id, status, limit)

        actions = []
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            actions.append(d)

        return {
            "success": True,
            "actions": actions,
            "total": len(actions),
            "tenant_id": tenant_id,
        }

    async def review_action(
        self,
        action_id: str,
        decision: str,
        executed_by: str = "operator",
    ) -> Dict[str, Any]:
        """Approve, dismiss, or reject a pending agent action."""
        valid_decisions = {"approve", "dismiss", "reject"}
        if decision not in valid_decisions:
            return {"success": False, "error": f"Invalid decision. Valid: {valid_decisions}"}

        status_map = {
            "approve": "approved",
            "dismiss": "dismissed",
            "reject": "rejected",
        }
        new_status = status_map[decision]

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pending_agent_actions WHERE id = $1", action_id
            )
            if not row:
                return {"success": False, "error": "Action not found"}

            await conn.execute("""
                UPDATE pending_agent_actions
                SET status = $1, executed_at = CURRENT_TIMESTAMP, executed_by = $2
                WHERE id = $3
            """, new_status, executed_by, action_id)

        action = dict(row)
        agent_key = action.get("agent", "")
        config = AGENT_CONFIGS.get(agent_key, {})

        result = {
            "success": True,
            "action_id": action_id,
            "decision": decision,
            "new_status": new_status,
            "agent": config.get("name", agent_key),
            "title": action.get("title", ""),
        }

        if decision == "approve":
            result["execution_note"] = (
                f"[{config.get('label', agent_key.upper()[:3])}] Action approved. "
                f"Execution of '{action.get('action', '')}' is staged for next agent cycle."
            )
            logger.info(f"Action {action_id} approved by {executed_by}: {action.get('title', '')}")
        else:
            logger.info(f"Action {action_id} {decision}ed by {executed_by}")

        return result

    async def get_agent_stats(self, tenant_id: str = "all") -> Dict[str, Any]:
        """Get aggregate stats on agent activity."""
        async with self.db_pool.acquire() as conn:
            if tenant_id == "all":
                stats = await conn.fetch("""
                    SELECT
                        agent,
                        status,
                        COUNT(*) as count,
                        SUM(estimated_impact) FILTER (WHERE estimated_impact IS NOT NULL) as total_impact
                    FROM pending_agent_actions
                    GROUP BY agent, status
                    ORDER BY agent, status
                """)
                last_cycle = await conn.fetchval(
                    "SELECT MAX(created_at) FROM pending_agent_actions"
                )
            else:
                stats = await conn.fetch("""
                    SELECT
                        agent,
                        status,
                        COUNT(*) as count,
                        SUM(estimated_impact) FILTER (WHERE estimated_impact IS NOT NULL) as total_impact
                    FROM pending_agent_actions
                    WHERE tenant_id = $1
                    GROUP BY agent, status
                    ORDER BY agent, status
                """, tenant_id)
                last_cycle = await conn.fetchval(
                    "SELECT MAX(created_at) FROM pending_agent_actions WHERE tenant_id = $1",
                    tenant_id,
                )

        summary = {}
        for s in stats:
            agent = s["agent"]
            if agent not in summary:
                config = AGENT_CONFIGS.get(agent, {})
                summary[agent] = {
                    "name": config.get("name", agent),
                    "label": config.get("label", agent.upper()[:3]),
                    "by_status": {},
                    "total_impact": 0,
                }
            summary[agent]["by_status"][s["status"]] = {
                "count": s["count"],
                "total_impact": float(s["total_impact"] or 0),
            }
            summary[agent]["total_impact"] += float(s["total_impact"] or 0)

        return {
            "success": True,
            "agents": summary,
            "last_cycle": last_cycle.isoformat() if last_cycle else None,
            "tenant_id": tenant_id,
        }

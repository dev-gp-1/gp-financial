#!/usr/bin/env python3
"""
Ghost Protocol Financial Agents — Collector, Paymaster, Auditor
TRON v18.0 | Autonomous AR/AP agents with MQTT triggers.

Architecture:
  - 3 agents powered by AgentLoop (Gemini function-calling)
  - MQTT event triggers: tron/ledger/{invoice.created, payment.received, sync.complete, ...}
  - Tools call invoice-cli.js via subprocess for ledger operations
  - SOUL identities loaded from backend/agents/souls/

Usage:
    # As standalone daemon (MQTT listener)
    python3 financial_agents.py

    # Programmatic (from backend API)
    from agents.financial_agents import FinancialAgents
    fa = FinancialAgents()
    result = fa.run_collector()
    result = fa.run_paymaster()
    result = fa.run_auditor()
"""

import json
import logging
import os
import subprocess
import sys
import time
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add parent paths
sys.path.insert(0, os.path.dirname(__file__))

try:
    from agent_loop import AgentLoop
except ImportError:
    AgentLoop = None

try:
    from soul_loader import SoulLoader
except ImportError:
    SoulLoader = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

logger = logging.getLogger("tron.financial_agents")

# ─── Configuration ────────────────────────────────────────────────────────────

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.86.20")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CLI_DIR = os.path.join(os.path.dirname(__file__), "..", "integrations", "invoice_generator")
NODE = "node"

# MQTT Topics
TOPIC_PREFIX = "tron/ledger"
TOPIC_INVOICE_CREATED = f"{TOPIC_PREFIX}/invoice.created"
TOPIC_PAYMENT_RECEIVED = f"{TOPIC_PREFIX}/payment.received"
TOPIC_PAYMENT_OVERDUE = f"{TOPIC_PREFIX}/payment.overdue"
TOPIC_AP_CREATED = f"{TOPIC_PREFIX}/ap.created"
TOPIC_SYNC_COMPLETE = f"{TOPIC_PREFIX}/sync.complete"
TOPIC_AGENT_RESULT = f"{TOPIC_PREFIX}/agent.result"
TOPIC_INBOX_SCANNED = f"{TOPIC_PREFIX}/inbox.scanned"
TOPIC_BILL_DUE = f"{TOPIC_PREFIX}/bill.due"
TOPIC_FORECAST_REQUEST = f"{TOPIC_PREFIX}/forecast.request"

# Journal path for MetricsTracker integration
JOURNAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'journals')
LEDGER_JOURNAL = os.path.join(JOURNAL_DIR, "ledger_activity.jsonl")

# Escalation thresholds (days)
POLITE_THRESHOLD = 1
FORMAL_THRESHOLD = 8
URGENT_THRESHOLD = 15
HOLD_THRESHOLD = 30

MAX_ACTIONS_PER_CYCLE = 5


# ─── Shared Tool Executors ───────────────────────────────────────────────────

def _run_cli(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Run an invoice-cli.js command and return parsed output."""
    try:
        result = subprocess.run(
            [NODE, "invoice-cli.js"] + command.split(),
            capture_output=True, text=True, timeout=timeout,
            cwd=CLI_DIR
        )
        return {
            "stdout": result.stdout.strip()[-2000:],
            "stderr": result.stderr.strip()[-500:] if result.stderr else "",
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {"error": str(e)}


def tool_get_overdue_invoices() -> dict:
    """Get all overdue receivable invoices."""
    return _run_cli("remind")


def tool_get_payable_invoices() -> dict:
    """Get all payable (AP) invoices."""
    result = _run_cli("sub:list")
    return result


def tool_get_ledger_stats() -> dict:
    """Get current AR/AP summary and net position."""
    result = _run_cli("digest")
    return result


def tool_get_entity_history(entity_name: str) -> dict:
    """Get invoice history for a specific entity."""
    result = _run_cli(f"status --entity {entity_name}")
    return result


def stage_action(agent: str, tool_name: str, params: dict, description: str = "") -> dict:
    url = "http://127.0.0.1:5000/api/v1/agents/pending_actions"
    payload = {
        "agent": agent,
        "action": tool_name,
        "params": params,
        "description": description or f"Agent {agent} requested {tool_name}."
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 200:
            return {"status": "ok", "message": "Action staged for HITL review. Execution paused until approved."}
    except Exception as e:
        logger.error(f"Failed to stage action: {e}")
    return {"status": "error", "message": "Failed to stage action."}


def tool_update_invoice_status(invoice_id: str, new_status: str, reason: str = "") -> dict:
    """Stage an invoice status update for HITL review."""
    valid = {"paid", "pending", "overdue", "sent", "included", "draft"}
    if new_status not in valid:
        return {"error": f"Invalid status '{new_status}'. Valid: {valid}"}
    res = stage_action("paymaster", "update_invoice_status",
                        {"invoice_id": invoice_id, "new_status": new_status, "reason": reason},
                        f"Change {invoice_id} to '{new_status}'. Reason: {reason}")
    res.update({"invoice_id": invoice_id, "new_status": new_status, "reason": reason})
    return res


def tool_send_payment_reminder(invoice_id: str, tier: str = "polite") -> dict:
    """Stage a payment reminder for HITL review."""
    if tier not in {"polite", "formal", "urgent"}:
        return {"error": f"Invalid tier '{tier}'. Valid: polite, formal, urgent"}
    res = stage_action("collector", "send_payment_reminder",
                        {"invoice_id": invoice_id, "tier": tier},
                        f"Send {tier} payment reminder for {invoice_id}.")
    res.update({"invoice_id": invoice_id, "tier": tier})
    return res


def tool_run_enrichment() -> dict:
    """Run AI enrichment: duplicates, amount validation, risk scoring."""
    return _run_cli("enrich")


def tool_generate_invoice(client: str, hours: Optional[int] = None, days_off: Optional[int] = None, send: bool = False) -> dict:
    """Generate a PDF invoice using the ADK skill wrapper."""
    script_path = os.path.join(os.path.dirname(__file__), '../../.agents/skills/generate_invoice/scripts/run.sh')
    
    args = ["--client", client]
    if hours is not None: args.extend(["--hours", str(hours)])
    if days_off is not None: args.extend(["--days-off", str(days_off)])
    if send: args.append("--send")
    
    if os.path.exists(script_path):
        try:
            result = subprocess.run(["bash", script_path] + args, capture_output=True, text=True, timeout=60, cwd=CLI_DIR)
            return {"stdout": result.stdout[-500:], "stderr": result.stderr[-500:], "exit_code": result.returncode}
        except Exception as e:
            return {"error": str(e)}
    else:
        # Fallback to direct raw CLI if ADK script is missing
        cmd = f"generate --yes {' '.join(args)}"
        return _run_cli(cmd, timeout=60)


def tool_get_all_transactions() -> dict:
    """Get all transactions from the ledger."""
    return _run_cli("status")


def tool_get_audit_trail(invoice_id: str) -> dict:
    """Get the audit trail for a specific invoice."""
    return _run_cli(f"sub:list --id {invoice_id}")


def tool_check_parent_invoice(parent_id: str) -> dict:
    """Check parent AR invoice status for AP cascade."""
    return _run_cli(f"sub:list --parent {parent_id}")


# ─── Tool Declarations ──────────────────────────────────────────────────────

COLLECTOR_TOOLS = [
    {
        "name": "get_overdue_invoices",
        "description": "Pull all receivable invoices that are past their due date. Shows aging and amounts.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_entity_history",
        "description": "Review payment history and all invoices for a specific client or vendor.",
        "parameters": {
            "type": "object",
            "properties": {"entity_name": {"type": "string", "description": "Client/vendor name"}},
            "required": ["entity_name"]
        }
    },
    {
        "name": "get_ledger_stats",
        "description": "Get current AR/AP summary: total receivables, total payables, net position, overdue count.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "send_payment_reminder",
        "description": "Send a payment reminder email for an overdue invoice. Tier controls urgency: polite (1-7d), formal (8-14d), urgent (15-30d).",
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "Invoice ID to remind about"},
                "tier": {"type": "string", "enum": ["polite", "formal", "urgent"], "description": "Escalation tier"}
            },
            "required": ["invoice_id", "tier"]
        }
    },
    {
        "name": "update_invoice_status",
        "description": "Update an invoice's status. Valid: paid, pending, overdue, sent, included, draft.",
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "Invoice ID"},
                "new_status": {"type": "string", "description": "New status"},
                "reason": {"type": "string", "description": "Reason for status change"}
            },
            "required": ["invoice_id", "new_status"]
        }
    },
    {
        "name": "run_enrichment",
        "description": "Run AI risk scoring: detects duplicates, amount anomalies, period gaps, and assigns risk levels (LOW/MEDIUM/HIGH).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "generate_invoice",
        "description": "Generate a professional PDF invoice using the ADK general_invoice skill. You can optionally send it directly.",
        "parameters": {
            "type": "object",
            "properties": {
                "client": {"type": "string", "description": "The client ID or name"},
                "hours": {"type": "number", "description": "Set hours billed (optional)"},
                "days_off": {"type": "number", "description": "Days off to deduct (optional)"},
                "send": {"type": "boolean", "description": "Whether to auto-send the email"}
            },
            "required": ["client"]
        }
    },
]

PAYMASTER_TOOLS = [
    {
        "name": "get_payable_invoices",
        "description": "Pull all AP (accounts payable) transactions — subcontractor invoices.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_entity_history",
        "description": "Review all invoices for a specific vendor.",
        "parameters": {
            "type": "object",
            "properties": {"entity_name": {"type": "string", "description": "Vendor name"}},
            "required": ["entity_name"]
        }
    },
    {
        "name": "get_ledger_stats",
        "description": "Get current AR/AP summary.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "update_invoice_status",
        "description": "Update an AP invoice's status.",
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "Invoice ID"},
                "new_status": {"type": "string", "description": "New status"},
                "reason": {"type": "string", "description": "Reason"}
            },
            "required": ["invoice_id", "new_status"]
        }
    },
    {
        "name": "check_parent_invoice",
        "description": "Check the status of the parent AR invoice to determine if AP cascade should trigger.",
        "parameters": {
            "type": "object",
            "properties": {"parent_id": {"type": "string", "description": "Parent AR invoice ID"}},
            "required": ["parent_id"]
        }
    },
]

AUDITOR_TOOLS = [
    {
        "name": "run_enrichment",
        "description": "Full AI enrichment pass: duplicate detection, amount validation, period gap detection, and risk scoring.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_ledger_stats",
        "description": "Pull current financial summary.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_all_transactions",
        "description": "Get the full list of all ledger transactions.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_audit_trail",
        "description": "Get the audit trail (status change history) for a specific invoice.",
        "parameters": {
            "type": "object",
            "properties": {"invoice_id": {"type": "string", "description": "Invoice ID"}},
            "required": ["invoice_id"]
        }
    },
]

# ─── Tool Executor Maps ─────────────────────────────────────────────────────

COLLECTOR_EXECUTORS = {
    "get_overdue_invoices": lambda: tool_get_overdue_invoices(),
    "get_entity_history": lambda entity_name: tool_get_entity_history(entity_name),
    "get_ledger_stats": lambda: tool_get_ledger_stats(),
    "send_payment_reminder": lambda invoice_id, tier="polite": tool_send_payment_reminder(invoice_id, tier),
    "update_invoice_status": lambda invoice_id, new_status, reason="": tool_update_invoice_status(invoice_id, new_status, reason),
    "run_enrichment": lambda: tool_run_enrichment(),
    "generate_invoice": lambda client, hours=None, days_off=None, send=False: tool_generate_invoice(client, hours, days_off, send),
}

PAYMASTER_EXECUTORS = {
    "get_payable_invoices": lambda: tool_get_payable_invoices(),
    "get_entity_history": lambda entity_name: tool_get_entity_history(entity_name),
    "get_ledger_stats": lambda: tool_get_ledger_stats(),
    "update_invoice_status": lambda invoice_id, new_status, reason="": tool_update_invoice_status(invoice_id, new_status, reason),
    "check_parent_invoice": lambda parent_id: tool_check_parent_invoice(parent_id),
}

AUDITOR_EXECUTORS = {
    "run_enrichment": lambda: tool_run_enrichment(),
    "get_ledger_stats": lambda: tool_get_ledger_stats(),
    "get_all_transactions": lambda: tool_get_all_transactions(),
    "get_audit_trail": lambda invoice_id: tool_get_audit_trail(invoice_id),
}


# ─── Financial Agents Engine ────────────────────────────────────────────────

class FinancialAgents:
    """Orchestrates the 3 financial agents with MQTT triggers."""

    def __init__(self, enable_mqtt: bool = True):
        self.mqtt_client = None
        self.results_log: List[Dict] = []

        if enable_mqtt and mqtt:
            self._setup_mqtt()

    def _setup_mqtt(self):
        """Connect to MQTT and subscribe to ledger events."""
        try:
            self.mqtt_client = mqtt.Client(client_id="tron-financial-agents")
            user = os.getenv("MQTT_USER")
            pwd = os.getenv("MQTT_PASS")
            if user and pwd:
                self.mqtt_client.username_pw_set(user, pwd)

            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            logger.info("📡 Financial Agents MQTT: Connected")
        except Exception as e:
            logger.warning("⚠️ Financial Agents MQTT failed: %s", e)

    def _on_connect(self, client, userdata, flags, rc):
        """Subscribe to all ledger topics on connect."""
        topics = [
            (TOPIC_INVOICE_CREATED, 1),
            (TOPIC_PAYMENT_RECEIVED, 1),
            (TOPIC_PAYMENT_OVERDUE, 1),
            (TOPIC_AP_CREATED, 1),
            (TOPIC_SYNC_COMPLETE, 1),
            (TOPIC_INBOX_SCANNED, 1),
            (TOPIC_BILL_DUE, 1),
            (TOPIC_FORECAST_REQUEST, 1),
            ("tron/ledger/approved_actions", 1)
        ]
        client.subscribe(topics)
        logger.info("📡 Subscribed to %d ledger topics", len(topics))

    def _on_message(self, client, userdata, msg):
        """Route MQTT events to the appropriate agent."""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode()) if msg.payload else {}
        except json.JSONDecodeError:
            payload = {"raw": msg.payload.decode()}

        logger.info("📨 MQTT Event: %s → %s", topic, json.dumps(payload, default=str)[:200])

        try:
            if topic == "tron/ledger/approved_actions":
                action_name = payload.get("action")
                params = payload.get("params", {})
                logger.info(f"⚡ Executing approved action: {action_name} with {params}")
                if action_name == "send_payment_reminder":
                    _run_cli("remind --send")
                elif action_name == "update_invoice_status":
                    _run_cli(f"sub:status --id {params.get('invoice_id')} --set {params.get('new_status')}")
                    
            elif topic == TOPIC_INVOICE_CREATED:
                self._log_ledger_activity("collector", topic, payload)
                self._log_ledger_activity("auditor", topic, payload)
                self.run_collector(context=f"MQTT Trigger: {topic} with {json.dumps(payload)}")
            elif topic == TOPIC_PAYMENT_RECEIVED:
                self._log_ledger_activity("paymaster", topic, payload)
                self._log_ledger_activity("collector", topic, payload)
                self.run_paymaster(context=f"MQTT Trigger: {topic} with {json.dumps(payload)}")
                self.run_collector(context=f"MQTT Trigger: {topic} with {json.dumps(payload)}")
            elif topic == TOPIC_PAYMENT_OVERDUE:
                self._log_ledger_activity("collector", topic, payload)
                self.run_collector(context=f"MQTT Trigger: {topic} with {json.dumps(payload)}")
            elif topic == TOPIC_AP_CREATED:
                self._log_ledger_activity("paymaster", topic, payload)
                self.run_paymaster(context=f"MQTT Trigger: {topic} with {json.dumps(payload)}")
            elif topic == TOPIC_SYNC_COMPLETE:
                self._log_ledger_activity("auditor", topic, payload)
                self.run_auditor(context=f"MQTT Trigger: {topic} with {json.dumps(payload)}")
            elif topic == TOPIC_INBOX_SCANNED:
                self._log_ledger_activity("sentinel", topic, payload)
            elif topic == TOPIC_BILL_DUE:
                self._log_ledger_activity("sentinel", topic, payload)
            elif topic == TOPIC_FORECAST_REQUEST:
                self._log_ledger_activity("sentinel", topic, payload)
        except Exception as e:
            logger.error("❌ Agent trigger failed: %s", e)

    def _publish_result(self, agent_name: str, result_data: Dict):
        """Publish agent result to MQTT for dashboard consumption."""
        if self.mqtt_client:
            try:
                payload = {
                    "agent": agent_name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **result_data,
                }
                self.mqtt_client.publish(TOPIC_AGENT_RESULT, json.dumps(payload, default=str), qos=1)
            except Exception:
                pass

    def _log_ledger_activity(self, agent: str, topic: str, payload: dict):
        """Log agent activity to ledger_activity.jsonl for MetricsTracker."""
        try:
            os.makedirs(JOURNAL_DIR, exist_ok=True)
            entry = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent,
                "topic": topic,
                "event_type": topic.split("/")[-1],
                "payload_summary": json.dumps(payload, default=str)[:500],
            }
            with open(LEDGER_JOURNAL, "a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info("📝 [%s] Activity logged to ledger journal", agent.upper())
        except Exception as e:
            logger.warning("⚠️ Ledger journal error: %s", e)

    def _load_soul(self, agent_name: str, base_prompt: str) -> str:
        """Load SOUL identity and inject into prompt."""
        if SoulLoader:
            return SoulLoader.load_and_inject(agent_name, base_prompt)
        return base_prompt

    # ─── Collector (AR Agent) ────────────────────────────────────────────

    def run_collector(self, context: str = "") -> Dict[str, Any]:
        """Run the AR Collection agent."""
        if not AgentLoop or not GEMINI_API_KEY:
            return self._fallback_collector()

        skill_path = os.path.join(os.path.dirname(__file__), '../../.agents/skills/accounts_receivable/SKILL.md')
        try:
            with open(skill_path, 'r') as f:
                prompt = f.read()
        except IOError:
            prompt = (
                "You are the Collector — Ghost Protocol's AR agent. "
                "Analyze the current receivables situation. For each overdue invoice, "
                "determine the appropriate escalation tier based on days overdue: "
                "1-7d=polite, 8-14d=formal, 15-30d=urgent, 30+=OPERATOR_REVIEW. "
                "Use your tools to check the ledger, then report findings."
            )

        loop = AgentLoop(
            system_prompt=self._load_soul("collector", prompt),
            tool_declarations=COLLECTOR_TOOLS,
            tool_executors=COLLECTOR_EXECUTORS,
            max_turns=3,
        )

        task = "Review all overdue AR invoices and determine escalation actions."
        if context:
            task = context

        result = loop.run_sync(task)
        result_data = {
            "text": result.text,
            "tools_used": result.tools_used,
            "turns": result.turns,
            "success": result.success,
        }

        self.results_log.append({"agent": "collector", **result_data})
        self._publish_result("collector", result_data)
        logger.info("💰 Collector: %s (tools: %s)", result.text[:100], result.tools_used)
        return result_data

    def _fallback_collector(self) -> Dict[str, Any]:
        """Non-AI fallback: run CLI commands directly."""
        overdue = _run_cli("remind")
        stats = _run_cli("digest")
        result_data = {
            "text": f"Fallback Collector Run:\n{overdue.get('stdout', '')}\n{stats.get('stdout', '')}",
            "tools_used": ["remind", "digest"],
            "turns": 0,
            "success": True,
            "fallback": True,
        }
        self.results_log.append({"agent": "collector", **result_data})
        return result_data

    # ─── Paymaster (AP Agent) ────────────────────────────────────────────

    def run_paymaster(self, context: str = "") -> Dict[str, Any]:
        """Run the AP Reconciliation agent."""
        if not AgentLoop or not GEMINI_API_KEY:
            return self._fallback_paymaster()

        skill_path = os.path.join(os.path.dirname(__file__), '../../.agents/skills/accounts_payable/SKILL.md')
        try:
            with open(skill_path, 'r') as f:
                prompt = f.read()
        except IOError:
            prompt = (
                "You are the Paymaster — Ghost Protocol's AP agent. "
                "Check all payable invoices. For each, verify if the parent AR invoice "
                "has been paid. If so, cascade the status to 'paid'. "
                "Report the reconciliation summary."
            )

        loop = AgentLoop(
            system_prompt=self._load_soul("paymaster", prompt),
            tool_declarations=PAYMASTER_TOOLS,
            tool_executors=PAYMASTER_EXECUTORS,
            max_turns=3,
        )

        task = "Reconcile all AP invoices against their parent AR invoices."
        if context:
            task = context

        result = loop.run_sync(task)
        result_data = {
            "text": result.text,
            "tools_used": result.tools_used,
            "turns": result.turns,
            "success": result.success,
        }

        self.results_log.append({"agent": "paymaster", **result_data})
        self._publish_result("paymaster", result_data)
        logger.info("📋 Paymaster: %s (tools: %s)", result.text[:100], result.tools_used)
        return result_data

    def _fallback_paymaster(self) -> Dict[str, Any]:
        """Non-AI fallback."""
        payables = _run_cli("sub:list")
        result_data = {
            "text": f"Fallback Paymaster Run:\n{payables.get('stdout', '')}",
            "tools_used": ["sub:list"],
            "turns": 0,
            "success": True,
            "fallback": True,
        }
        self.results_log.append({"agent": "paymaster", **result_data})
        return result_data

    # ─── Auditor (Watchdog Agent) ────────────────────────────────────────

    def run_auditor(self, context: str = "") -> Dict[str, Any]:
        """Run the Ledger Watchdog/Enrichment agent."""
        if not AgentLoop or not GEMINI_API_KEY:
            return self._fallback_auditor()

        prompt = (
            "You are the Auditor — Ghost Protocol's financial watchdog. "
            "Run the full enrichment pass to detect duplicates, amount anomalies, "
            "period gaps, and risk scores. Report all findings with severity levels. "
            "If the ledger is clean, confirm integrity."
        )

        loop = AgentLoop(
            system_prompt=self._load_soul("auditor", prompt),
            tool_declarations=AUDITOR_TOOLS,
            tool_executors=AUDITOR_EXECUTORS,
            max_turns=3,
        )

        task = "Run a full audit sweep on the financial ledger."
        if context:
            task = context

        result = loop.run_sync(task)
        result_data = {
            "text": result.text,
            "tools_used": result.tools_used,
            "turns": result.turns,
            "success": result.success,
        }

        self.results_log.append({"agent": "auditor", **result_data})
        self._publish_result("auditor", result_data)
        logger.info("🔍 Auditor: %s (tools: %s)", result.text[:100], result.tools_used)
        return result_data

    def _fallback_auditor(self) -> Dict[str, Any]:
        """Non-AI fallback."""
        enrich = _run_cli("enrich")
        result_data = {
            "text": f"Fallback Auditor Run:\n{enrich.get('stdout', '')}",
            "tools_used": ["enrich"],
            "turns": 0,
            "success": True,
            "fallback": True,
        }
        self.results_log.append({"agent": "auditor", **result_data})
        return result_data

    # ── Sentinel (Household Finance Guardian) ────────────────────────────

    def run_sentinel(self, context: str = "") -> Dict[str, Any]:
        """Run the Household Finance Guardian agent."""
        if not AgentLoop or not GEMINI_API_KEY:
            return self._fallback_sentinel()

        prompt = (
            "You are the Sentinel — Ghost Protocol's Household Finance Guardian. "
            "Monitor family bills, forecast upcoming expenses, and protect the household budget. "
            "Check for bills due in the next 7 days, scan inbox scan results for new invoices, "
            "and provide a summary of the household financial outlook."
        )

        # Sentinel reuses Auditor/Collector tools for ledger access
        loop = AgentLoop(
            system_prompt=self._load_soul("sentinel", prompt),
            tool_declarations=AUDITOR_TOOLS + COLLECTOR_TOOLS[:3],  # Stats + overdue + entity history
            tool_executors={**AUDITOR_EXECUTORS, **{k: COLLECTOR_EXECUTORS[k] for k in ["get_overdue_invoices", "get_entity_history", "get_ledger_stats"]}},
            max_turns=3,
        )

        task = "Review household finances: upcoming bills, balance forecast, and budget health."
        if context:
            task = context

        result = loop.run_sync(task)
        result_data = {
            "text": result.text,
            "tools_used": result.tools_used,
            "turns": result.turns,
            "success": result.success,
        }

        self.results_log.append({"agent": "sentinel", **result_data})
        self._publish_result("sentinel", result_data)
        logger.info("🛡️ Sentinel: %s (tools: %s)", result.text[:100], result.tools_used)
        return result_data

    def _fallback_sentinel(self) -> Dict[str, Any]:
        """Non-AI fallback for Sentinel."""
        stats = _run_cli("digest")
        result_data = {
            "text": f"Fallback Sentinel Run:\n{stats.get('stdout', '')}",
            "tools_used": ["digest"],
            "turns": 0,
            "success": True,
            "fallback": True,
        }
        self.results_log.append({"agent": "sentinel", **result_data})
        return result_data

    # ── Run All ─────────────────────────────────────────────────────────

    def run_all(self) -> Dict[str, Any]:
        """Run all 4 agents in sequence (for cron/manual trigger)."""
        sentinel = self.run_sentinel()
        collector = self.run_collector()
        paymaster = self.run_paymaster()
        auditor = self.run_auditor()
        return {
            "sentinel": sentinel,
            "collector": collector,
            "paymaster": paymaster,
            "auditor": auditor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ─── MQTT Daemon Mode ───────────────────────────────────────────────────────

def run_daemon():
    """Run as a persistent MQTT listener daemon."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logger.info("═══════════════════════════════════════════════")
    logger.info("  💰 Ghost Protocol Financial Agents — Online")
    logger.info("═══════════════════════════════════════════════")

    fa = FinancialAgents(enable_mqtt=True)

    # Initial run on startup
    logger.info("  Running initial scan...")
    fa.run_all()

    # 6-hour interval loop
    try:
        while True:
            # 6 hours = 21600 seconds
            time.sleep(21600)
            logger.info("⏰ 6-Hour Cycle: Running Financial Agents Sweep")
            fa.run_all()
    except KeyboardInterrupt:
        logger.info("  Financial Agents shutting down...")
        if fa.mqtt_client:
            fa.mqtt_client.loop_stop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run financial agents')
    parser.add_argument('agent', nargs='?', help='Agent to run: collector, paymaster, auditor, sentinel, all')
    args = parser.parse_args()

    if args.agent:
        fa = FinancialAgents(enable_mqtt=False)
        agent = args.agent.lower()
        if agent == 'collector':
            print(json.dumps(fa.run_collector(), indent=2))
        elif agent == 'paymaster':
            print(json.dumps(fa.run_paymaster(), indent=2))
        elif agent == 'auditor':
            print(json.dumps(fa.run_auditor(), indent=2))
        elif agent == 'sentinel':
            print(json.dumps(fa.run_sentinel(), indent=2))
        elif agent == 'all':
            print(json.dumps(fa.run_all(), indent=2))
        else:
            print(f"Unknown agent: {agent}")
            sys.exit(1)
    else:
        run_daemon()

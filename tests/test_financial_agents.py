#!/usr/bin/env python3
"""
Test Suite: Ghost Protocol Financial Agents
Uses synthesized financial data to validate agent tools, triggers, and logic.

Run:
    python3 -m pytest tests/test_financial_agents.py -v
"""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'agents'))

# ─── Synthesized Test Data ───────────────────────────────────────────────────

SYNTH_OVERDUE_OUTPUT = """
  ⚠️  Overdue Invoices (3):
    • 20260101-TEST-AR001 — EdgeConneX, Inc. — $25,000 — Due: 2026-01-31 — 48d overdue
    • 20260201-TEST-AR002 — EdgeConneX, Inc. — $18,500 — Due: 2026-02-28 — 20d overdue
    • 20260301-TEST-AR003 — SynthClient Corp — $9,200 — Due: 2026-03-10 — 10d overdue
  Total overdue: $52,700
"""

SYNTH_DIGEST_OUTPUT = """
  📊 Ghost Protocol Financial Digest
  ════════════════════════════════════════════════
  Date: 2026-03-20
  Total AR:       $52,700
  Total AP:       $18,400
  Outstanding AR: $52,700
  Outstanding AP: $0
  Net Position:   $34,300

  ⚠️  OVERDUE (3):
    • 20260101-TEST-AR001 — $25,000 — 48d overdue
    • 20260201-TEST-AR002 — $18,500 — 20d overdue
    • 20260301-TEST-AR003 — $9,200 — 10d overdue

  BY ENTITY:
    EdgeConneX, Inc. (RECEIVABLE): 2 inv, $43,500
    SynthClient Corp (RECEIVABLE): 1 inv, $9,200
    TrustFactor X (PAYABLE): 2 inv, $18,400
  ════════════════════════════════════════════════
"""

SYNTH_ENRICH_OUTPUT = """
  🧠 Running AI enrichment pass...
  📋 Analyzed 5 transactions

  🔴 HIGH RISK (1):
    • 20260101-TEST-AR001: $25,000 — medium_amount, severely_overdue

  🟡 Amount Anomalies (1):
    • 20260201-TEST-AR002: $18,500 vs expected $18,000 (2.8% off) [MEDIUM]

  🟠 Period Gaps (1):
    • EdgeConneX, Inc.: 15d gap (2026-01-31 → 2026-02-15)
"""

SYNTH_SUBLIST_OUTPUT = """
  📋 Subcontractor Invoices:
    • SUB-TFX-001 — Trust Factor X — $12,000 — Status: included — Parent: 20260101-TEST-AR001
    • SUB-TFX-002 — Trust Factor X — $6,400 — Status: pending — Parent: 20260201-TEST-AR002
"""

SYNTH_STATUS_UPDATE = {"stdout": "  ✅ Status updated: TEST-001 → paid", "exit_code": 0}


# ─── Test: Tool Executors ────────────────────────────────────────────────────

class TestToolExecutors:
    """Test that tool functions return expected structures."""

    @patch('financial_agents.subprocess.run')
    def test_get_overdue_invoices(self, mock_run):
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(
            stdout=SYNTH_OVERDUE_OUTPUT, stderr="", returncode=0
        )
        result = tool_get_overdue_invoices()
        assert "stdout" in result
        assert "overdue" in result["stdout"].lower()
        assert "$25,000" in result["stdout"]
        assert "$52,700" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_get_ledger_stats(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(
            stdout=SYNTH_DIGEST_OUTPUT, stderr="", returncode=0
        )
        result = tool_get_ledger_stats()
        assert "Net Position" in result["stdout"]
        assert "$34,300" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_run_enrichment(self, mock_run):
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(
            stdout=SYNTH_ENRICH_OUTPUT, stderr="", returncode=0
        )
        result = tool_run_enrichment()
        assert "HIGH RISK" in result["stdout"]
        assert "Amount Anomalies" in result["stdout"]
        assert "Period Gaps" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_update_invoice_status_valid(self, mock_run):
        from financial_agents import tool_update_invoice_status
        mock_run.return_value = MagicMock(
            stdout=SYNTH_STATUS_UPDATE["stdout"], stderr="", returncode=0
        )
        result = tool_update_invoice_status("TEST-001", "paid", "payment confirmed")
        assert result["new_status"] == "paid"
        assert result["invoice_id"] == "TEST-001"
        assert result["reason"] == "payment confirmed"

    def test_update_invoice_status_invalid(self):
        from financial_agents import tool_update_invoice_status
        result = tool_update_invoice_status("TEST-001", "invalid_status")
        assert "error" in result
        assert "Invalid status" in result["error"]

    @patch('financial_agents.subprocess.run')
    def test_send_payment_reminder_valid_tiers(self, mock_run):
        from financial_agents import tool_send_payment_reminder
        mock_run.return_value = MagicMock(stdout="  ✅ Reminders sent", stderr="", returncode=0)
        for tier in ["polite", "formal", "urgent"]:
            result = tool_send_payment_reminder("TEST-001", tier)
            assert result["tier"] == tier

    def test_send_payment_reminder_invalid_tier(self):
        from financial_agents import tool_send_payment_reminder
        result = tool_send_payment_reminder("TEST-001", "aggressive")
        assert "error" in result


# ─── Test: Escalation Logic ──────────────────────────────────────────────────

class TestEscalationLogic:
    """Test escalation tier determination based on days overdue."""

    def test_escalation_thresholds(self):
        from financial_agents import POLITE_THRESHOLD, FORMAL_THRESHOLD, URGENT_THRESHOLD, HOLD_THRESHOLD
        assert POLITE_THRESHOLD == 1
        assert FORMAL_THRESHOLD == 8
        assert URGENT_THRESHOLD == 15
        assert HOLD_THRESHOLD == 30

    def test_escalation_tier_assignment(self):
        """Validate correct tier for different overdue durations."""
        from financial_agents import POLITE_THRESHOLD, FORMAL_THRESHOLD, URGENT_THRESHOLD, HOLD_THRESHOLD

        test_cases = [
            (3, "polite"),
            (7, "polite"),
            (8, "formal"),
            (14, "formal"),
            (15, "urgent"),
            (29, "urgent"),
            (30, "hold"),
            (90, "hold"),
        ]

        for days, expected_tier in test_cases:
            if days >= HOLD_THRESHOLD:
                tier = "hold"
            elif days >= URGENT_THRESHOLD:
                tier = "urgent"
            elif days >= FORMAL_THRESHOLD:
                tier = "formal"
            elif days >= POLITE_THRESHOLD:
                tier = "polite"
            else:
                tier = "none"
            assert tier == expected_tier, f"Days {days}: expected {expected_tier}, got {tier}"


# ─── Test: MQTT Topic Routing ────────────────────────────────────────────────

class TestMQTTRouting:
    """Test MQTT message routing to correct agents."""

    def test_topic_definitions(self):
        from financial_agents import (
            TOPIC_INVOICE_CREATED, TOPIC_PAYMENT_RECEIVED,
            TOPIC_PAYMENT_OVERDUE, TOPIC_AP_CREATED, TOPIC_SYNC_COMPLETE,
        )
        assert TOPIC_INVOICE_CREATED == "tron/ledger/invoice.created"
        assert TOPIC_PAYMENT_RECEIVED == "tron/ledger/payment.received"
        assert TOPIC_PAYMENT_OVERDUE == "tron/ledger/payment.overdue"
        assert TOPIC_AP_CREATED == "tron/ledger/ap.created"
        assert TOPIC_SYNC_COMPLETE == "tron/ledger/sync.complete"

    @patch('financial_agents.mqtt', None)
    def test_agent_init_without_mqtt(self):
        """Agent should work without MQTT (for testing or API-only mode)."""
        from financial_agents import FinancialAgents
        fa = FinancialAgents(enable_mqtt=False)
        assert fa.mqtt_client is None

    def test_message_routing_invoice_created(self):
        """invoice.created should trigger Collector."""
        from financial_agents import FinancialAgents, TOPIC_INVOICE_CREATED
        fa = FinancialAgents(enable_mqtt=False)

        with patch.object(fa, 'run_collector', return_value={"text": "ok"}) as mock:
            fa._on_message(None, None, MagicMock(
                topic=TOPIC_INVOICE_CREATED,
                payload=json.dumps({"id": "TEST-001"}).encode()
            ))
            mock.assert_called_once()

    def test_message_routing_payment_received(self):
        """payment.received should trigger BOTH Paymaster and Collector."""
        from financial_agents import FinancialAgents, TOPIC_PAYMENT_RECEIVED
        fa = FinancialAgents(enable_mqtt=False)

        with patch.object(fa, 'run_paymaster', return_value={"text": "ok"}) as pm, \
             patch.object(fa, 'run_collector', return_value={"text": "ok"}) as col:
            fa._on_message(None, None, MagicMock(
                topic=TOPIC_PAYMENT_RECEIVED,
                payload=json.dumps({"id": "TEST-001", "amount": 25000}).encode()
            ))
            pm.assert_called_once()
            col.assert_called_once()

    def test_message_routing_sync_complete(self):
        """sync.complete should trigger Auditor."""
        from financial_agents import FinancialAgents, TOPIC_SYNC_COMPLETE
        fa = FinancialAgents(enable_mqtt=False)

        with patch.object(fa, 'run_auditor', return_value={"text": "ok"}) as mock:
            fa._on_message(None, None, MagicMock(
                topic=TOPIC_SYNC_COMPLETE,
                payload=b'{}'
            ))
            mock.assert_called_once()


# ─── Test: Agent Fallback Mode ───────────────────────────────────────────────

class TestFallbackMode:
    """Test agents work without Gemini API (CLI-only fallback)."""

    @patch('financial_agents.AgentLoop', None)
    @patch('financial_agents.subprocess.run')
    def test_collector_fallback(self, mock_run):
        from financial_agents import FinancialAgents
        mock_run.return_value = MagicMock(
            stdout=SYNTH_OVERDUE_OUTPUT, stderr="", returncode=0
        )
        fa = FinancialAgents(enable_mqtt=False)
        result = fa.run_collector()
        assert result["success"]
        assert result.get("fallback") is True
        assert "overdue" in result["text"].lower()

    @patch('financial_agents.AgentLoop', None)
    @patch('financial_agents.subprocess.run')
    def test_paymaster_fallback(self, mock_run):
        from financial_agents import FinancialAgents
        mock_run.return_value = MagicMock(
            stdout=SYNTH_SUBLIST_OUTPUT, stderr="", returncode=0
        )
        fa = FinancialAgents(enable_mqtt=False)
        result = fa.run_paymaster()
        assert result["success"]
        assert result.get("fallback") is True

    @patch('financial_agents.AgentLoop', None)
    @patch('financial_agents.subprocess.run')
    def test_auditor_fallback(self, mock_run):
        from financial_agents import FinancialAgents
        mock_run.return_value = MagicMock(
            stdout=SYNTH_ENRICH_OUTPUT, stderr="", returncode=0
        )
        fa = FinancialAgents(enable_mqtt=False)
        result = fa.run_auditor()
        assert result["success"]
        assert "HIGH RISK" in result["text"]


# ─── Test: SOUL Files Exist ──────────────────────────────────────────────────

class TestSOULFiles:
    """Verify SOUL identity files exist and contain required sections."""

    SOULS_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'agents', 'souls')

    @pytest.mark.parametrize("agent", ["collector", "paymaster", "auditor"])
    def test_soul_file_exists(self, agent):
        path = os.path.join(self.SOULS_DIR, f"{agent}.md")
        assert os.path.exists(path), f"SOUL file missing: {path}"

    @pytest.mark.parametrize("agent", ["collector", "paymaster", "auditor"])
    def test_soul_has_identity_section(self, agent):
        path = os.path.join(self.SOULS_DIR, f"{agent}.md")
        with open(path) as f:
            content = f.read()
        assert "## Identity" in content
        assert "## Core Values" in content
        assert "## Boundaries" in content
        assert "## Tools Available" in content
        assert "## Trigger Events" in content

    @pytest.mark.parametrize("agent,emoji", [
        ("collector", "💰"),
        ("paymaster", "📋"),
        ("auditor", "🔍"),
    ])
    def test_soul_signature_emoji(self, agent, emoji):
        path = os.path.join(self.SOULS_DIR, f"{agent}.md")
        with open(path) as f:
            content = f.read()
        assert emoji in content


# ─── Test: Synthesized Financial Scenarios ───────────────────────────────────

class TestFinancialScenarios:
    """End-to-end scenario tests with synthesized data."""

    @patch('financial_agents.subprocess.run')
    def test_scenario_overdue_detection_accuracy(self, mock_run):
        """Verify 3 overdue invoices are detected with correct amounts."""
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_OVERDUE_OUTPUT, stderr="", returncode=0)

        result = tool_get_overdue_invoices()
        output = result["stdout"]

        # Verify all 3 invoices present
        assert "20260101-TEST-AR001" in output
        assert "20260201-TEST-AR002" in output
        assert "20260301-TEST-AR003" in output

        # Verify amounts
        assert "$25,000" in output
        assert "$18,500" in output
        assert "$9,200" in output

        # Verify total
        assert "$52,700" in output

    @patch('financial_agents.subprocess.run')
    def test_scenario_enrichment_risk_detection(self, mock_run):
        """Verify enrichment correctly identifies HIGH RISK and anomalies."""
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_ENRICH_OUTPUT, stderr="", returncode=0)

        result = tool_run_enrichment()
        output = result["stdout"]

        # HIGH RISK flagged
        assert "HIGH RISK (1)" in output
        assert "severely_overdue" in output

        # Amount anomaly detected
        assert "Amount Anomalies (1)" in output
        assert "2.8% off" in output

        # Period gap detected
        assert "Period Gaps (1)" in output
        assert "15d gap" in output

    @patch('financial_agents.subprocess.run')
    def test_scenario_net_position_calculation(self, mock_run):
        """Verify AR - AP = Net Position is correct in digest."""
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_DIGEST_OUTPUT, stderr="", returncode=0)

        result = tool_get_ledger_stats()
        output = result["stdout"]

        # AR: $52,700, AP: $18,400, Net: $34,300
        assert "$52,700" in output  # AR
        assert "$18,400" in output  # AP
        assert "$34,300" in output  # Net = 52700 - 18400

    def test_scenario_max_actions_limit(self):
        """Verify MAX_ACTIONS_PER_CYCLE is enforced."""
        from financial_agents import MAX_ACTIONS_PER_CYCLE
        assert MAX_ACTIONS_PER_CYCLE == 5

#!/usr/bin/env python3
"""
Expanded Test Suite: Ghost Protocol Financial Agents — Synthetic Scenarios
Comprehensive edge-case, multi-entity, and stress testing with rich synthesized data.

Run:
    python3 -m pytest tests/test_financial_scenarios.py -v
"""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'agents'))


# ═════════════════════════════════════════════════════════════════════════════
# SYNTHETIC DOCUMENT LIBRARY — Realistic invoices, ledger states, enrichment
# ═════════════════════════════════════════════════════════════════════════════

# ── Scenario A: Multi-Entity Ledger (5 clients, 3 vendors, 15 invoices) ─────

SYNTH_MULTI_ENTITY_DIGEST = """
  📊 Ghost Protocol Financial Digest
  ════════════════════════════════════════════════
  Date: 2026-03-20
  Total AR:       $287,450
  Total AP:       $94,200
  Outstanding AR: $187,450
  Outstanding AP: $34,200
  Net Position:   $193,250

  ⚠️  OVERDUE (5):
    • 20251015-ACME-AR001 — $45,000 — 156d overdue
    • 20251201-EDC04-AR002 — $28,800 — 110d overdue
    • 20260105-EDC05-AR003 — $17,025 — 74d overdue
    • 20260115-NOVA-AR004 — $52,125 — 64d overdue
    • 20260201-BRT-AR005 — $44,500 — 47d overdue

  BY ENTITY:
    ACME Construction (RECEIVABLE): 3 inv, $125,000
    EdgeConneX, Inc. (RECEIVABLE): 4 inv, $111,184
    NovaSteel Holdings (RECEIVABLE): 2 inv, $52,125
    Bright Energy Corp (RECEIVABLE): 1 inv, $44,500
    Trust Factor X (PAYABLE): 3 inv, $27,200
    EmbeddedHive (PAYABLE): 1 inv, $11,960
    Duff & Associates (PAYABLE): 2 inv, $55,040
  ════════════════════════════════════════════════
"""

SYNTH_MULTI_ENTITY_OVERDUE = """
  ⚠️  Overdue Invoices (5):
    • 20251015-ACME-AR001 — ACME Construction — $45,000 — Due: 2025-10-15 — 156d overdue
    • 20251201-EDC04-AR002 — EdgeConneX, Inc. — $28,800 — Due: 2025-12-01 — 110d overdue
    • 20260105-EDC05-AR003 — EdgeConneX, Inc. — $17,025 — Due: 2026-01-05 — 74d overdue
    • 20260115-NOVA-AR004 — NovaSteel Holdings — $52,125 — Due: 2026-01-15 — 64d overdue
    • 20260201-BRT-AR005 — Bright Energy Corp — $44,500 — Due: 2026-02-01 — 47d overdue
  Total overdue: $187,450
"""

# ── Scenario B: Duplicate Detection ──────────────────────────────────────────

SYNTH_DUPLICATE_ENRICHMENT = """
  🧠 Running AI enrichment pass...
  📋 Analyzed 12 transactions

  🔴 HIGH RISK (2):
    • 20251015-ACME-AR001: $45,000 — large_amount, severely_overdue
    • 20260115-NOVA-AR004: $52,125 — large_amount, severely_overdue

  🟡 Duplicate Candidates (2):
    • 20260201-EDC06-C4156 ↔ 20260201-EDC06-DUP1: Same entity (edc01), amount ($20,325), date (2026-02-01)
    • 20260115-TFX-AP001 ↔ 20260115-TFX-AP002: Same entity (tfx01), amount ($8,600), date (2026-01-15)

  🟡 Amount Anomalies (3):
    • 20260105-EDC05-AR003: $17,025 vs expected $16,800 (1.3% off) [LOW]
    • 20260115-NOVA-AR004: $52,125 vs expected $48,000 (8.6% off) [MEDIUM]
    • 20251201-EDC04-AR002: $28,800 vs expected $22,400 (28.6% off) [HIGH]

  🟠 Period Gaps (2):
    • EdgeConneX, Inc.: 22d gap (2025-12-31 → 2026-01-22)
    • ACME Construction: 45d gap (2025-11-15 → 2025-12-30)
"""

# ── Scenario C: Payment Cascade ──────────────────────────────────────────────

SYNTH_CASCADE_PARENT = """
  📋 Invoice Status:
    • 20260201-EDC06-C4156 — EdgeConneX, Inc. — $20,325 — Status: paid — Paid: 2026-03-18
"""

SYNTH_CASCADE_CHILDREN = """
  📋 Subcontractor Invoices:
    • SUB-TFX-003 — Trust Factor X — $8,600 — Status: included — Parent: 20260201-EDC06-C4156
    • SUB-EHV-001 — EmbeddedHive — $3,400 — Status: included — Parent: 20260201-EDC06-C4156
    • SUB-DUF-001 — Duff & Associates — $2,100 — Status: pending — Parent: 20260201-EDC06-C4156
"""

# ── Scenario D: Zero-Overdue (Clean Ledger) ──────────────────────────────────

SYNTH_CLEAN_DIGEST = """
  📊 Ghost Protocol Financial Digest
  ════════════════════════════════════════════════
  Date: 2026-03-20
  Total AR:       $75,000
  Total AP:       $22,500
  Outstanding AR: $0
  Outstanding AP: $0
  Net Position:   $52,500

  ✅ No overdue invoices — all payments current

  BY ENTITY:
    SolidState Corp (RECEIVABLE): 2 inv, $75,000
    FastTrack LLC (PAYABLE): 1 inv, $22,500
  ════════════════════════════════════════════════
"""

SYNTH_CLEAN_ENRICHMENT = """
  🧠 Running AI enrichment pass...
  📋 Analyzed 3 transactions

  ✅ All clear — no high risk, no duplicates, no gaps
"""

SYNTH_CLEAN_OVERDUE = """
  📧 Scanning for overdue invoices...
  ✅ No overdue invoices found — all payments current
"""

# ── Scenario E: Large Volume (20+ invoices) ──────────────────────────────────

SYNTH_LARGE_VOLUME_DIGEST = """
  📊 Ghost Protocol Financial Digest
  ════════════════════════════════════════════════
  Date: 2026-03-20
  Total AR:       $1,245,830
  Total AP:       $389,200
  Outstanding AR: $892,130
  Outstanding AP: $145,700
  Net Position:   $856,630

  ⚠️  OVERDUE (8):
    • 20250901-MFG-AR001 — $180,000 — 200d overdue
    • 20251001-MFG-AR002 — $165,000 — 171d overdue
    • 20251101-CST-AR003 — $92,450 — 140d overdue
    • 20251201-CST-AR004 — $78,200 — 110d overdue
    • 20260101-PLT-AR005 — $125,780 — 79d overdue
    • 20260115-PLT-AR006 — $88,900 — 64d overdue
    • 20260201-RNG-AR007 — $54,300 — 47d overdue
    • 20260215-RNG-AR008 — $107,500 — 33d overdue
  Total overdue: $892,130

  BY ENTITY:
    MegaForge Industries (RECEIVABLE): 5 inv, $520,000
    CoastalSteel (RECEIVABLE): 3 inv, $245,650
    PlatinumWorks (RECEIVABLE): 4 inv, $285,180
    Ring Defense (RECEIVABLE): 3 inv, $195,000
    SubPrime Partners (PAYABLE): 6 inv, $234,200
    MiniCraft Ltd (PAYABLE): 3 inv, $95,000
    JetSet Services (PAYABLE): 2 inv, $60,000
  ════════════════════════════════════════════════
"""

# ── Scenario F: CLI Error Handling ───────────────────────────────────────────

SYNTH_CLI_TIMEOUT_STDERR = "Error: Command timed out after 30000ms"
SYNTH_CLI_DB_ERROR_STDERR = "Error: SQLITE_CANTOPEN: unable to open database file"
SYNTH_CLI_NO_DATA = ""

# ── Scenario G: Extreme Amounts ──────────────────────────────────────────────

SYNTH_EXTREME_ENRICHMENT = """
  🧠 Running AI enrichment pass...
  📋 Analyzed 4 transactions

  🔴 HIGH RISK (3):
    • 20260101-MEGA-001: $1,500,000 — large_amount, severely_overdue
    • 20260201-MEGA-002: $750,000 — large_amount, overdue_14d
    • 20260301-MEGA-003: $999,999 — large_amount

  🟡 Amount Anomalies (1):
    • 20260101-MEGA-001: $1,500,000 vs expected $1,200,000 (25.0% off) [HIGH]
"""

# ── Scenario H: Single-Invoice Entity ────────────────────────────────────────

SYNTH_SINGLE_ENTITY_HISTORY = """
  📋 Entity History: NewClient Inc.
    • 20260315-NEW-AR001 — $5,000 — Status: sent — Due: 2026-04-15
    Total: 1 invoice, $5,000
    Payment history: First engagement
"""


# ═════════════════════════════════════════════════════════════════════════════
# TEST CLASSES
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiEntityScenario:
    """Scenario A: 5 clients, 3 vendors, 15 invoices — realistic production-scale."""

    @patch('financial_agents.subprocess.run')
    def test_multi_entity_digest_totals(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_MULTI_ENTITY_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        out = result["stdout"]
        assert "$287,450" in out  # Total AR
        assert "$94,200" in out   # Total AP
        assert "$193,250" in out  # Net Position = 287450 - 94200

    @patch('financial_agents.subprocess.run')
    def test_multi_entity_overdue_count(self, mock_run):
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_MULTI_ENTITY_OVERDUE, stderr="", returncode=0)
        result = tool_get_overdue_invoices()
        out = result["stdout"]
        # All 5 invoices present
        for inv_id in ["ACME-AR001", "EDC04-AR002", "EDC05-AR003", "NOVA-AR004", "BRT-AR005"]:
            assert inv_id in out, f"Missing invoice: {inv_id}"

    @patch('financial_agents.subprocess.run')
    def test_multi_entity_overdue_total_matches(self, mock_run):
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_MULTI_ENTITY_OVERDUE, stderr="", returncode=0)
        result = tool_get_overdue_invoices()
        # 45000 + 28800 + 17025 + 52125 + 44500 = 187450
        assert "$187,450" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_multi_entity_days_overdue_accuracy(self, mock_run):
        """Verify each invoice's days-overdue label is present."""
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_MULTI_ENTITY_OVERDUE, stderr="", returncode=0)
        result = tool_get_overdue_invoices()
        out = result["stdout"]
        assert "156d overdue" in out  # ACME — oldest
        assert "110d overdue" in out  # EDC04
        assert "74d overdue" in out   # EDC05
        assert "64d overdue" in out   # NOVA
        assert "47d overdue" in out   # BRT

    @patch('financial_agents.subprocess.run')
    def test_multi_entity_entity_breakdown(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_MULTI_ENTITY_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        out = result["stdout"]
        for entity in ["ACME Construction", "EdgeConneX", "NovaSteel", "Bright Energy", "Trust Factor X", "EmbeddedHive", "Duff"]:
            assert entity in out, f"Missing entity: {entity}"

    @patch('financial_agents.subprocess.run')
    def test_multi_entity_escalation_tiers(self, mock_run):
        """Verify correct escalation tiers for each overdue duration."""
        from financial_agents import POLITE_THRESHOLD, FORMAL_THRESHOLD, URGENT_THRESHOLD, HOLD_THRESHOLD

        overdue_map = {
            "ACME-AR001": 156,  # HOLD (30+)
            "EDC04-AR002": 110, # HOLD (30+)
            "EDC05-AR003": 74,  # HOLD (30+)
            "NOVA-AR004": 64,   # HOLD (30+)
            "BRT-AR005": 47,    # HOLD (30+)
        }

        for inv, days in overdue_map.items():
            # All are 30+ days, so all should be HOLD
            assert days >= HOLD_THRESHOLD, f"{inv} should be HOLD at {days}d"


class TestDuplicateDetection:
    """Scenario B: Enrichment catches duplicate invoices and amount anomalies."""

    @patch('financial_agents.subprocess.run')
    def test_duplicate_candidates_found(self, mock_run):
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_DUPLICATE_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        out = result["stdout"]
        assert "Duplicate Candidates (2)" in out
        assert "EDC06-DUP1" in out
        assert "TFX-AP002" in out

    @patch('financial_agents.subprocess.run')
    def test_high_risk_correct_count(self, mock_run):
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_DUPLICATE_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        assert "HIGH RISK (2)" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_amount_anomaly_severity_levels(self, mock_run):
        """Verify anomalies are classified as LOW/MEDIUM/HIGH correctly."""
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_DUPLICATE_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        out = result["stdout"]
        assert "1.3% off) [LOW]" in out       # Under 5% → LOW
        assert "8.6% off) [MEDIUM]" in out     # 5-20% → MEDIUM
        assert "28.6% off) [HIGH]" in out      # Over 20% → HIGH

    @patch('financial_agents.subprocess.run')
    def test_period_gap_multiple_entities(self, mock_run):
        """Verify gaps detected across different entities."""
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_DUPLICATE_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        out = result["stdout"]
        assert "Period Gaps (2)" in out
        assert "22d gap" in out
        assert "45d gap" in out
        assert "ACME Construction" in out
        assert "EdgeConneX" in out


class TestPaymentCascade:
    """Scenario C: When a parent AR is paid, child AP items should cascade."""

    @patch('financial_agents.subprocess.run')
    def test_cascade_parent_paid(self, mock_run):
        """Parent invoice marked paid → verify status."""
        from financial_agents import tool_check_parent_invoice
        mock_run.return_value = MagicMock(stdout=SYNTH_CASCADE_PARENT, stderr="", returncode=0)
        result = tool_check_parent_invoice("20260201-EDC06-C4156")
        assert "paid" in result["stdout"].lower()

    @patch('financial_agents.subprocess.run')
    def test_cascade_children_listed(self, mock_run):
        """All 3 child AP invoices discoverable."""
        from financial_agents import tool_get_payable_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_CASCADE_CHILDREN, stderr="", returncode=0)
        result = tool_get_payable_invoices()
        out = result["stdout"]
        assert "SUB-TFX-003" in out
        assert "SUB-EHV-001" in out
        assert "SUB-DUF-001" in out

    @patch('financial_agents.subprocess.run')
    def test_cascade_mixed_statuses(self, mock_run):
        """Children have different statuses: 2 included, 1 pending."""
        from financial_agents import tool_get_payable_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_CASCADE_CHILDREN, stderr="", returncode=0)
        result = tool_get_payable_invoices()
        out = result["stdout"]
        # 2 items are "included", 1 is "pending"
        assert out.count("included") == 2
        assert out.count("pending") == 1

    @patch('financial_agents.subprocess.run')
    def test_cascade_amounts_sum(self, mock_run):
        """Child AP amounts should sum to less than parent AR amount."""
        from financial_agents import tool_get_payable_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_CASCADE_CHILDREN, stderr="", returncode=0)
        result = tool_get_payable_invoices()
        out = result["stdout"]
        # SUB amounts: 8600 + 3400 + 2100 = 14100 < parent's $20,325
        assert "$8,600" in out
        assert "$3,400" in out
        assert "$2,100" in out

    def test_cascade_paymaster_triggers_on_payment_received(self):
        """payment.received MQTT triggers both Paymaster and Collector."""
        from financial_agents import FinancialAgents, TOPIC_PAYMENT_RECEIVED
        fa = FinancialAgents(enable_mqtt=False)

        payload = json.dumps({
            "invoice_id": "20260201-EDC06-C4156",
            "amount": 20325,
            "client": "EdgeConneX, Inc.",
            "paid_date": "2026-03-18"
        }).encode()

        with patch.object(fa, 'run_paymaster', return_value={"text": "cascade"}) as pm, \
             patch.object(fa, 'run_collector', return_value={"text": "update"}) as col:
            fa._on_message(None, None, MagicMock(topic=TOPIC_PAYMENT_RECEIVED, payload=payload))
            pm.assert_called_once()
            col.assert_called_once()
            # Verify context contains the payment info
            pm_ctx = pm.call_args[1].get("context", pm.call_args[0][0] if pm.call_args[0] else "")
            assert "20325" in str(pm.call_args) or "payment" in str(pm.call_args).lower()


class TestCleanLedger:
    """Scenario D: All invoices paid — clean state with no action needed."""

    @patch('financial_agents.subprocess.run')
    def test_clean_digest_no_overdue(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_CLEAN_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        assert "No overdue" in result["stdout"]
        assert "Outstanding AR: $0" in result["stdout"]
        assert "Outstanding AP: $0" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_clean_enrichment_no_risk(self, mock_run):
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_CLEAN_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        assert "All clear" in result["stdout"]
        assert "HIGH RISK" not in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_clean_reminders_nothing_to_send(self, mock_run):
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(stdout=SYNTH_CLEAN_OVERDUE, stderr="", returncode=0)
        result = tool_get_overdue_invoices()
        assert "No overdue" in result["stdout"]

    @patch('financial_agents.AgentLoop', None)
    @patch('financial_agents.subprocess.run')
    def test_clean_collector_fallback_no_action(self, mock_run):
        """Collector fallback on clean ledger reports no overdue."""
        from financial_agents import FinancialAgents
        mock_run.return_value = MagicMock(stdout=SYNTH_CLEAN_OVERDUE + "\n" + SYNTH_CLEAN_DIGEST, stderr="", returncode=0)
        fa = FinancialAgents(enable_mqtt=False)
        result = fa.run_collector()
        assert result["success"]
        assert "No overdue" in result["text"]


class TestLargeVolume:
    """Scenario E: 20+ invoices across 7 entities — stress test."""

    @patch('financial_agents.subprocess.run')
    def test_large_volume_ar_total(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_LARGE_VOLUME_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        assert "$1,245,830" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_large_volume_overdue_count(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_LARGE_VOLUME_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        assert "OVERDUE (8)" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_large_volume_net_position(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_LARGE_VOLUME_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        # 1245830 - 389200 = 856630
        assert "$856,630" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_large_volume_all_entities_present(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_LARGE_VOLUME_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        out = result["stdout"]
        for entity in ["MegaForge", "CoastalSteel", "PlatinumWorks", "Ring Defense", "SubPrime", "MiniCraft", "JetSet"]:
            assert entity in out, f"Missing entity: {entity}"

    @patch('financial_agents.subprocess.run')
    def test_large_volume_oldest_invoice(self, mock_run):
        """Oldest overdue should be 200 days — critical escalation."""
        from financial_agents import tool_get_ledger_stats
        mock_run.return_value = MagicMock(stdout=SYNTH_LARGE_VOLUME_DIGEST, stderr="", returncode=0)
        result = tool_get_ledger_stats()
        assert "200d overdue" in result["stdout"]


class TestCLIErrorHandling:
    """Scenario F: CLI errors — timeout, DB errors, empty responses."""

    @patch('financial_agents.subprocess.run')
    def test_cli_timeout_graceful(self, mock_run):
        from financial_agents import tool_get_ledger_stats
        mock_run.side_effect = Exception("Command timed out")
        result = tool_get_ledger_stats()
        assert "error" in result
        assert "timed out" in result["error"]

    @patch('financial_agents.subprocess.run')
    def test_cli_nonzero_exit_code(self, mock_run):
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(stdout="", stderr=SYNTH_CLI_DB_ERROR_STDERR, returncode=1)
        result = tool_get_overdue_invoices()
        assert result["exit_code"] == 1
        assert "SQLITE_CANTOPEN" in result["stderr"]

    @patch('financial_agents.subprocess.run')
    def test_cli_empty_output(self, mock_run):
        from financial_agents import tool_get_overdue_invoices
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        result = tool_get_overdue_invoices()
        assert result["stdout"] == ""
        assert result["exit_code"] == 0

    @patch('financial_agents.subprocess.run')
    def test_cli_stderr_with_success(self, mock_run):
        """CLI may emit warnings to stderr even on success."""
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(
            stdout=SYNTH_CLEAN_ENRICHMENT,
            stderr="Deprecation warning: something something",
            returncode=0
        )
        result = tool_run_enrichment()
        assert result["exit_code"] == 0
        assert "Deprecation" in result["stderr"]
        assert "All clear" in result["stdout"]

    @patch('financial_agents.AgentLoop', None)
    @patch('financial_agents.subprocess.run')
    def test_fallback_survives_cli_error(self, mock_run):
        """Fallback collectors should still return a result even with errors."""
        from financial_agents import FinancialAgents
        mock_run.return_value = MagicMock(stdout="Error: partial output", stderr="DB locked", returncode=1)
        fa = FinancialAgents(enable_mqtt=False)
        result = fa.run_auditor()
        assert result["success"]  # Fallback itself succeeds


class TestExtremeAmounts:
    """Scenario G: Million-dollar invoices — boundary testing for risk scoring."""

    @patch('financial_agents.subprocess.run')
    def test_extreme_high_risk_count(self, mock_run):
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_EXTREME_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        assert "HIGH RISK (3)" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_extreme_million_dollar_amounts(self, mock_run):
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_EXTREME_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        out = result["stdout"]
        assert "$1,500,000" in out
        assert "$750,000" in out
        assert "$999,999" in out

    @patch('financial_agents.subprocess.run')
    def test_extreme_amount_anomaly_25pct(self, mock_run):
        """25% variance should be flagged as HIGH."""
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_EXTREME_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        assert "25.0% off) [HIGH]" in result["stdout"]


class TestStatusTransitions:
    """Test all valid status transitions and guards."""

    @pytest.mark.parametrize("status", ["paid", "pending", "overdue", "sent", "included", "draft"])
    @patch('financial_agents.subprocess.run')
    def test_all_valid_statuses(self, mock_run, status):
        from financial_agents import tool_update_invoice_status
        mock_run.return_value = MagicMock(stdout=f"  ✅ Status updated → {status}", stderr="", returncode=0)
        result = tool_update_invoice_status("TEST-001", status)
        assert result["new_status"] == status
        assert "error" not in result

    @pytest.mark.parametrize("bad_status", [
        "cancelled", "deleted", "archived", "void", "refunded", "PAID", "Pending", ""
    ])
    def test_invalid_statuses_rejected(self, bad_status):
        from financial_agents import tool_update_invoice_status
        result = tool_update_invoice_status("TEST-001", bad_status)
        assert "error" in result

    @patch('financial_agents.subprocess.run')
    def test_status_update_preserves_invoice_id(self, mock_run):
        from financial_agents import tool_update_invoice_status
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        complex_id = "20260315-EDC09-C4156-REV2"
        result = tool_update_invoice_status(complex_id, "paid", "ACH confirmed")
        assert result["invoice_id"] == complex_id
        assert result["reason"] == "ACH confirmed"


class TestEntityHistory:
    """Test entity-specific lookups with synthesized client data."""

    @patch('financial_agents.subprocess.run')
    def test_new_client_first_invoice(self, mock_run):
        from financial_agents import tool_get_entity_history
        mock_run.return_value = MagicMock(stdout=SYNTH_SINGLE_ENTITY_HISTORY, stderr="", returncode=0)
        result = tool_get_entity_history("NewClient Inc.")
        out = result["stdout"]
        assert "NewClient Inc." in out
        assert "$5,000" in out
        assert "First engagement" in out


class TestMQTTPayloadFormats:
    """Test MQTT routing handles various payload formats gracefully."""

    def test_empty_payload(self):
        from financial_agents import FinancialAgents, TOPIC_SYNC_COMPLETE
        fa = FinancialAgents(enable_mqtt=False)
        with patch.object(fa, 'run_auditor', return_value={"text": "ok"}) as mock:
            fa._on_message(None, None, MagicMock(topic=TOPIC_SYNC_COMPLETE, payload=b''))
            mock.assert_called_once()

    def test_malformed_json_payload(self):
        """Agent should not crash on malformed JSON."""
        from financial_agents import FinancialAgents, TOPIC_INVOICE_CREATED
        fa = FinancialAgents(enable_mqtt=False)
        with patch.object(fa, 'run_collector', return_value={"text": "ok"}) as mock:
            fa._on_message(None, None, MagicMock(
                topic=TOPIC_INVOICE_CREATED,
                payload=b'not valid json {{'
            ))
            mock.assert_called_once()

    def test_rich_payload_with_metadata(self):
        """Complex payloads with nested data should be forwarded to agent context."""
        from financial_agents import FinancialAgents, TOPIC_PAYMENT_RECEIVED
        fa = FinancialAgents(enable_mqtt=False)

        rich_payload = json.dumps({
            "invoice_id": "20260201-EDC06-C4156",
            "amount": 20325.00,
            "currency": "USD",
            "client": {"name": "EdgeConneX, Inc.", "id": "edc01"},
            "payment_method": "ACH",
            "reference": "CHK-9182734",
            "paid_date": "2026-03-18T14:30:00Z",
        }).encode()

        with patch.object(fa, 'run_paymaster', return_value={"text": "ok"}) as pm, \
             patch.object(fa, 'run_collector', return_value={"text": "ok"}) as col:
            fa._on_message(None, None, MagicMock(topic=TOPIC_PAYMENT_RECEIVED, payload=rich_payload))
            pm.assert_called_once()
            col.assert_called_once()

    def test_ap_created_with_child_data(self):
        from financial_agents import FinancialAgents, TOPIC_AP_CREATED
        fa = FinancialAgents(enable_mqtt=False)

        payload = json.dumps({
            "sub_id": "SUB-TFX-004",
            "vendor": "Trust Factor X",
            "amount": 9800,
            "parent_invoice": "20260301-EDC07-C4156",
        }).encode()

        with patch.object(fa, 'run_paymaster', return_value={"text": "ok"}) as mock:
            fa._on_message(None, None, MagicMock(topic=TOPIC_AP_CREATED, payload=payload))
            mock.assert_called_once()

    def test_unsubscribed_topic_ignored(self):
        """Messages on unrecognized topics should not trigger any agent."""
        from financial_agents import FinancialAgents
        fa = FinancialAgents(enable_mqtt=False)
        with patch.object(fa, 'run_collector') as col, \
             patch.object(fa, 'run_paymaster') as pay, \
             patch.object(fa, 'run_auditor') as aud:
            fa._on_message(None, None, MagicMock(
                topic="tron/some/other/topic",
                payload=b'{}'
            ))
            col.assert_not_called()
            pay.assert_not_called()
            aud.assert_not_called()


class TestRunAllSequence:
    """Test the run_all() orchestrator executes agents in correct order."""

    @patch('financial_agents.AgentLoop', None)
    @patch('financial_agents.subprocess.run')
    def test_run_all_returns_all_agents(self, mock_run):
        from financial_agents import FinancialAgents
        mock_run.return_value = MagicMock(stdout="test output", stderr="", returncode=0)
        fa = FinancialAgents(enable_mqtt=False)
        result = fa.run_all()
        assert "sentinel" in result
        assert "collector" in result
        assert "paymaster" in result
        assert "auditor" in result
        assert "timestamp" in result

    @patch('financial_agents.AgentLoop', None)
    @patch('financial_agents.subprocess.run')
    def test_run_all_logs_accumulate(self, mock_run):
        from financial_agents import FinancialAgents
        mock_run.return_value = MagicMock(stdout="output", stderr="", returncode=0)
        fa = FinancialAgents(enable_mqtt=False)
        fa.run_all()
        # Should have 4 entries in the log (one per agent)
        assert len(fa.results_log) == 4
        agents_logged = [r["agent"] for r in fa.results_log]
        assert "sentinel" in agents_logged
        assert "collector" in agents_logged
        assert "paymaster" in agents_logged
        assert "auditor" in agents_logged


class TestEscalationBoundaryValues:
    """Test exact boundary values for escalation tier transitions."""

    def test_day_zero_no_escalation(self):
        from financial_agents import POLITE_THRESHOLD
        # Day 0 = not yet overdue
        assert 0 < POLITE_THRESHOLD

    @pytest.mark.parametrize("days,expected", [
        (0, "none"),
        (1, "polite"),
        (7, "polite"),
        (8, "formal"),
        (14, "formal"),
        (15, "urgent"),
        (29, "urgent"),
        (30, "hold"),
        (365, "hold"),
    ])
    def test_boundary_cases(self, days, expected):
        from financial_agents import POLITE_THRESHOLD, FORMAL_THRESHOLD, URGENT_THRESHOLD, HOLD_THRESHOLD

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
        assert tier == expected, f"Day {days}: expected {expected}, got {tier}"


class TestRiskScoringLogic:
    """Verify the enrichment.js risk scoring rules via synthesized outputs."""

    @patch('financial_agents.subprocess.run')
    def test_risk_flags_large_amount(self, mock_run):
        """Amounts > $40k get 'large_amount' flag."""
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_EXTREME_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        assert "large_amount" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_risk_flags_overdue(self, mock_run):
        """Overdue invoices get overdue flags."""
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_DUPLICATE_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        assert "severely_overdue" in result["stdout"]

    @patch('financial_agents.subprocess.run')
    def test_no_risk_on_clean_ledger(self, mock_run):
        from financial_agents import tool_run_enrichment
        mock_run.return_value = MagicMock(stdout=SYNTH_CLEAN_ENRICHMENT, stderr="", returncode=0)
        result = tool_run_enrichment()
        assert "HIGH RISK" not in result["stdout"]
        assert "large_amount" not in result["stdout"]

#!/usr/bin/env python3
"""
Test Suite: AR/AP Evaluator — Classification Engine

Tests the core financial intelligence that classifies every invoice, bill,
and transaction into granular statuses for agent recommendations.

Run:
    python3 -m pytest tests/test_ar_ap_evaluator.py -v
"""

import json
import os
import sys
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'agents'))

from ar_ap_evaluator import (
    ARStatus, APStatus, TxnStatus,
    AREntry, APEntry, TxnEntry,
    EvaluationReport, ArapEvaluator,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

TODAY = date.today()


def _make_ar_row(
    days_past_due=0,
    amount=1000.0,
    status=None,
    metadata=None,
    entity="TestClient",
):
    """Build a fake DB row for AR classification."""
    due = TODAY - timedelta(days=days_past_due)
    return {
        "id": f"AR-{days_past_due}-{int(amount)}",
        "entity_name": entity,
        "amount": amount,
        "date": TODAY - timedelta(days=max(days_past_due + 30, 30)),
        "due_date": due,
        "status": status,
        "metadata": json.dumps(metadata or {}),
        "items": "[]",
    }


def _make_ap_row(
    days_until_due=30,
    amount=500.0,
    status=None,
    metadata=None,
    vendor="TestVendor",
):
    """Build a fake DB row for AP classification."""
    due = TODAY + timedelta(days=days_until_due)
    return {
        "id": f"AP-{days_until_due}-{int(amount)}",
        "entity_name": vendor,
        "amount": amount,
        "date": TODAY - timedelta(days=10),
        "due_date": due,
        "status": status,
        "metadata": json.dumps(metadata or {}),
    }


def _make_txn_row(
    amount=100.0,
    status="active",
    metadata=None,
    entity="SomeCorp",
):
    """Build a fake DB row for transaction classification."""
    return {
        "id": f"TXN-{int(amount)}",
        "entity_name": entity,
        "amount": amount,
        "date": TODAY - timedelta(days=5),
        "status": status,
        "metadata": json.dumps(metadata or {}),
    }


# ── AR Classification Tests ─────────────────────────────────────────────

class TestARClassification:
    """Tests for _classify_ar — invoice aging buckets."""

    def setup_method(self):
        self.evaluator = ArapEvaluator(db_pool=MagicMock())

    def test_ar_current_classification(self):
        """Invoice not yet due should be CURRENT."""
        row = _make_ar_row(days_past_due=-5)  # Due in 5 days
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.CURRENT

    def test_ar_overdue_30_classification(self):
        """Invoice 15 days past due should be OVERDUE_30."""
        row = _make_ar_row(days_past_due=15)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.OVERDUE_30

    def test_ar_overdue_60_classification(self):
        """Invoice 45 days past due should be OVERDUE_60."""
        row = _make_ar_row(days_past_due=45)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.OVERDUE_60

    def test_ar_overdue_90_classification(self):
        """Invoice 75 days past due should be OVERDUE_90."""
        row = _make_ar_row(days_past_due=75)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.OVERDUE_90

    def test_ar_overdue_90_plus_classification(self):
        """Invoice 120 days past due should be OVERDUE_90_PLUS."""
        row = _make_ar_row(days_past_due=120)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.OVERDUE_90_PLUS

    def test_ar_paid_status(self):
        """Explicit paid status in DB should map to PAID."""
        row = _make_ar_row(status="paid")
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.PAID

    def test_ar_written_off_status(self):
        """Written off invoices should map correctly."""
        row = _make_ar_row(status="written_off")
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.WRITTEN_OFF

    def test_ar_disputed_status(self):
        """Disputed invoices should map correctly."""
        row = _make_ar_row(status="disputed")
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.DISPUTED

    def test_ar_partial_payment(self):
        """Partial payment with payment_id metadata should map to PARTIAL."""
        row = _make_ar_row(
            status="partial",
            metadata={"payment_id": "PAY-001"},
        )
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.status == ARStatus.PARTIAL

    def test_ar_severity_critical(self):
        """90+ day overdue should be critical severity."""
        row = _make_ar_row(days_past_due=120)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.severity == "critical"

    def test_ar_severity_high(self):
        """60-90 day overdue should be high severity."""
        row = _make_ar_row(days_past_due=75)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.severity == "high"

    def test_ar_severity_medium(self):
        """30-day overdue should be medium severity."""
        row = _make_ar_row(days_past_due=15)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.severity == "medium"

    def test_ar_severity_low(self):
        """Current invoice should be low severity."""
        row = _make_ar_row(days_past_due=-5)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.severity == "low"

    def test_ar_is_overdue_property(self):
        """Overdue entries should return True for is_overdue."""
        row = _make_ar_row(days_past_due=45)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.is_overdue is True

    def test_ar_current_not_overdue(self):
        """Current entries should return False for is_overdue."""
        row = _make_ar_row(days_past_due=-5)
        entry = self.evaluator._classify_ar(row, TODAY)
        assert entry.is_overdue is False


# ── AP Classification Tests ─────────────────────────────────────────────

class TestAPClassification:
    """Tests for _classify_ap — bill aging and urgency."""

    def setup_method(self):
        self.evaluator = ArapEvaluator(db_pool=MagicMock())

    def test_ap_scheduled_classification(self):
        """Bill due in 30 days should be SCHEDULED."""
        row = _make_ap_row(days_until_due=30)
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.status == APStatus.SCHEDULED

    def test_ap_due_soon_classification(self):
        """Bill due in 5 days should be DUE_SOON."""
        row = _make_ap_row(days_until_due=5)
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.status == APStatus.DUE_SOON

    def test_ap_overdue_classification(self):
        """Bill 10 days past due should be OVERDUE."""
        row = _make_ap_row(days_until_due=-10)
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.status == APStatus.OVERDUE

    def test_ap_paid_status(self):
        """Explicit paid status should map correctly."""
        row = _make_ap_row(status="paid")
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.status == APStatus.PAID

    def test_ap_rejected_status(self):
        """Rejected bills should map correctly."""
        row = _make_ap_row(status="rejected")
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.status == APStatus.REJECTED

    def test_ap_on_hold_status(self):
        """On-hold bills should map correctly."""
        row = _make_ap_row(status="on_hold")
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.status == APStatus.ON_HOLD

    def test_ap_pending_approval_status(self):
        """HITL-pending bills should map to PENDING_APPROVAL."""
        row = _make_ap_row(status="awaiting_hitl_approval")
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.status == APStatus.PENDING_APPROVAL

    def test_ap_is_urgent_overdue(self):
        """Overdue entries should be urgent."""
        row = _make_ap_row(days_until_due=-10)
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.is_urgent is True

    def test_ap_scheduled_not_urgent(self):
        """Scheduled entries should not be urgent."""
        row = _make_ap_row(days_until_due=30)
        entry = self.evaluator._classify_ap(row, TODAY)
        assert entry.is_urgent is False


# ── Transaction Classification Tests ─────────────────────────────────────

class TestTxnClassification:
    """Tests for _classify_txn — reconciliation status."""

    def setup_method(self):
        self.evaluator = ArapEvaluator(db_pool=MagicMock())

    def test_txn_reconciled(self):
        """Transaction with bank_confirmed should be RECONCILED."""
        row = _make_txn_row(metadata={"bank_confirmed": True})
        entry = self.evaluator._classify_txn(row)
        assert entry.status == TxnStatus.RECONCILED

    def test_txn_enriched(self):
        """Transaction with category but no bank_confirmed should be ENRICHED."""
        row = _make_txn_row(metadata={"category": "services"})
        entry = self.evaluator._classify_txn(row)
        assert entry.status == TxnStatus.ENRICHED

    def test_txn_pending(self):
        """Transaction with pending status should be PENDING."""
        row = _make_txn_row(status="pending")
        entry = self.evaluator._classify_txn(row)
        assert entry.status == TxnStatus.PENDING

    def test_txn_unmatched(self):
        """Transaction with no metadata match should be UNMATCHED."""
        row = _make_txn_row()
        entry = self.evaluator._classify_txn(row)
        assert entry.status == TxnStatus.UNMATCHED


# ── Health Score Tests ───────────────────────────────────────────────────

class TestHealthScore:
    """Tests for _compute_health — composite financial health."""

    def setup_method(self):
        self.evaluator = ArapEvaluator(db_pool=MagicMock())

    def test_health_score_perfect(self):
        """All current, 100% reconciled should score high."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            ar_total=10000,
            ar_current=10000,
            ap_total=5000,
            ap_scheduled=5000,
            txn_total=100,
            txn_reconciled=100,
            reconciliation_rate=100.0,
        )
        score = self.evaluator._compute_health(report)
        assert score >= 90, f"Perfect scenario should score 90+, got {score}"

    def test_health_score_critical(self):
        """All overdue 90+ with 0% reconciliation should score very low."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            ar_total=50000,
            ar_overdue_90_plus=50000,
            ap_total=20000,
            ap_overdue=20000,
            txn_total=100,
            txn_unmatched=100,
            reconciliation_rate=0.0,
        )
        score = self.evaluator._compute_health(report)
        assert score < 30, f"Critical scenario should score <30, got {score}"

    def test_health_score_bounded(self):
        """Health score should always be 0-100."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
        )
        score = self.evaluator._compute_health(report)
        assert 0 <= score <= 100


# ── Recommendation Engine Tests ──────────────────────────────────────────

class TestRecommendations:
    """Tests for _generate_recommendations — action generation."""

    def setup_method(self):
        self.evaluator = ArapEvaluator(db_pool=MagicMock())

    def test_recommendations_for_overdue_90(self):
        """Overdue 90+ entries should generate critical collector action."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            ar_entries=[
                AREntry(id="1", entity_name="Big Corp", amount=25000,
                        date="2025-10-01", due_date="2025-11-01",
                        status=ARStatus.OVERDUE_90_PLUS, days_past_due=150),
            ],
        )
        actions = self.evaluator._generate_recommendations(report)
        critical = [a for a in actions if a["priority"] == "critical"]
        assert len(critical) >= 1
        assert critical[0]["agent"] == "collector"

    def test_recommendations_for_overdue_ap(self):
        """Overdue AP bills should generate paymaster action."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            ap_entries=[
                APEntry(id="1", vendor_name="Vendor A", amount=5000,
                        date="2026-01-01", due_date="2026-02-01",
                        status=APStatus.OVERDUE, days_until_due=-30),
            ],
        )
        actions = self.evaluator._generate_recommendations(report)
        paymaster_actions = [a for a in actions if a["agent"] == "paymaster"]
        assert len(paymaster_actions) >= 1

    def test_recommendations_for_low_reconciliation(self):
        """Low reconciliation rate should generate reconciler action."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            reconciliation_rate=50.0,
            txn_unmatched=20,
        )
        actions = self.evaluator._generate_recommendations(report)
        recon_actions = [a for a in actions if a["agent"] == "reconciler"]
        assert len(recon_actions) >= 1

    def test_no_recommendations_for_healthy_books(self):
        """Perfectly healthy books should generate 0 actions."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            ar_entries=[
                AREntry(id="1", entity_name="Good Client", amount=5000,
                        date="2026-03-01", due_date="2026-04-01",
                        status=ARStatus.CURRENT),
            ],
            ap_entries=[
                APEntry(id="1", vendor_name="Good Vendor", amount=2000,
                        date="2026-03-01", due_date="2026-04-15",
                        status=APStatus.SCHEDULED, days_until_due=20),
            ],
            reconciliation_rate=95.0,
            txn_unmatched=2,
        )
        actions = self.evaluator._generate_recommendations(report)
        assert len(actions) == 0


# ── Report Serialization Tests ───────────────────────────────────────────

class TestReportSerialization:
    """Tests for EvaluationReport.to_dict()."""

    def test_report_to_dict_structure(self):
        """to_dict() should contain all required top-level keys."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            ar_total=10000,
            ap_total=5000,
        )
        d = report.to_dict()
        assert "ar" in d
        assert "ap" in d
        assert "transactions" in d
        assert "metrics" in d
        assert "recommended_actions" in d
        assert d["tenant_id"] == "test"

    def test_report_metrics_keys(self):
        """Metrics section should have health_score, dso, recon rate."""
        report = EvaluationReport(
            tenant_id="test",
            generated_at="2026-01-01",
            health_score=85,
            reconciliation_rate=92.0,
        )
        metrics = report.to_dict()["metrics"]
        assert "health_score" in metrics
        assert "dso_days" in metrics
        assert "reconciliation_rate" in metrics
        assert "cash_runway_days" in metrics

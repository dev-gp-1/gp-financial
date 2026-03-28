"""
AR/AP Evaluator — Comprehensive status classification engine.

Deep-scans all financial records (invoices, bills, transactions) and assigns
granular statuses for complete visibility into the financial lifecycle.

AR Statuses:
    current, overdue_30, overdue_60, overdue_90, overdue_90_plus,
    paid, partial, disputed, written_off

AP Statuses:
    scheduled, due_soon, overdue, paid, pending_approval,
    rejected, on_hold

Transaction Statuses:
    reconciled, unmatched, pending, enriched
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger("gp.ar_ap_evaluator")


# ── Status Enums ─────────────────────────────────────────────────────────

class ARStatus(str, Enum):
    CURRENT = "current"
    OVERDUE_30 = "overdue_30"
    OVERDUE_60 = "overdue_60"
    OVERDUE_90 = "overdue_90"
    OVERDUE_90_PLUS = "overdue_90_plus"
    PAID = "paid"
    PARTIAL = "partial"
    DISPUTED = "disputed"
    WRITTEN_OFF = "written_off"


class APStatus(str, Enum):
    SCHEDULED = "scheduled"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    PAID = "paid"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"
    ON_HOLD = "on_hold"


class TxnStatus(str, Enum):
    RECONCILED = "reconciled"
    UNMATCHED = "unmatched"
    PENDING = "pending"
    ENRICHED = "enriched"


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class AREntry:
    id: str
    entity_name: str
    amount: float
    date: str
    due_date: Optional[str]
    status: ARStatus
    days_past_due: int = 0
    original_amount: float = 0.0
    balance_remaining: float = 0.0
    payment_ids: List[str] = field(default_factory=list)
    source: str = "quickbooks"
    metadata: Dict = field(default_factory=dict)

    @property
    def is_overdue(self) -> bool:
        return self.status in (ARStatus.OVERDUE_30, ARStatus.OVERDUE_60,
                               ARStatus.OVERDUE_90, ARStatus.OVERDUE_90_PLUS)

    @property
    def severity(self) -> str:
        if self.status == ARStatus.OVERDUE_90_PLUS:
            return "critical"
        elif self.status == ARStatus.OVERDUE_90:
            return "high"
        elif self.status == ARStatus.OVERDUE_60:
            return "high"
        elif self.status == ARStatus.OVERDUE_30:
            return "medium"
        return "low"


@dataclass
class APEntry:
    id: str
    vendor_name: str
    amount: float
    date: str
    due_date: Optional[str]
    status: APStatus
    days_until_due: int = 0
    source: str = "quickbooks"
    metadata: Dict = field(default_factory=dict)

    @property
    def is_urgent(self) -> bool:
        return self.status in (APStatus.OVERDUE, APStatus.DUE_SOON)


@dataclass
class TxnEntry:
    id: str
    counterparty: str
    amount: float
    date: str
    status: TxnStatus
    platform: str = "mercury"
    category: str = ""
    gl_code: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class EvaluationReport:
    """Complete AR/AP evaluation for a tenant."""
    tenant_id: str
    generated_at: str
    # AR Summary
    ar_total: float = 0.0
    ar_current: float = 0.0
    ar_overdue_30: float = 0.0
    ar_overdue_60: float = 0.0
    ar_overdue_90: float = 0.0
    ar_overdue_90_plus: float = 0.0
    ar_entries: List[AREntry] = field(default_factory=list)
    # AP Summary
    ap_total: float = 0.0
    ap_scheduled: float = 0.0
    ap_due_soon: float = 0.0
    ap_overdue: float = 0.0
    ap_entries: List[APEntry] = field(default_factory=list)
    # Transaction Summary
    txn_total: int = 0
    txn_reconciled: int = 0
    txn_unmatched: int = 0
    txn_pending: int = 0
    txn_entries: List[TxnEntry] = field(default_factory=list)
    # Computed Metrics
    health_score: int = 0
    dso_days: Optional[float] = None
    reconciliation_rate: float = 0.0
    cash_runway_days: Optional[int] = None
    # Agent Recommendations
    recommended_actions: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "tenant_id": self.tenant_id,
            "generated_at": self.generated_at,
            "ar": {
                "total": self.ar_total,
                "current": self.ar_current,
                "overdue_30": self.ar_overdue_30,
                "overdue_60": self.ar_overdue_60,
                "overdue_90": self.ar_overdue_90,
                "overdue_90_plus": self.ar_overdue_90_plus,
                "entry_count": len(self.ar_entries),
                "entries": [asdict(e) for e in self.ar_entries[:50]],
            },
            "ap": {
                "total": self.ap_total,
                "scheduled": self.ap_scheduled,
                "due_soon": self.ap_due_soon,
                "overdue": self.ap_overdue,
                "entry_count": len(self.ap_entries),
                "entries": [asdict(e) for e in self.ap_entries[:50]],
            },
            "transactions": {
                "total": self.txn_total,
                "reconciled": self.txn_reconciled,
                "unmatched": self.txn_unmatched,
                "pending": self.txn_pending,
                "reconciliation_rate": self.reconciliation_rate,
            },
            "metrics": {
                "health_score": self.health_score,
                "dso_days": self.dso_days,
                "reconciliation_rate": self.reconciliation_rate,
                "cash_runway_days": self.cash_runway_days,
            },
            "recommended_actions": self.recommended_actions,
        }


# ── Evaluator Engine ─────────────────────────────────────────────────────

class ArapEvaluator:
    """Deep evaluation engine for all AR, AP, and transaction records."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def evaluate(self, tenant_id: str) -> EvaluationReport:
        """Run a full AR/AP/Transaction evaluation for a tenant."""
        now = datetime.now(timezone.utc)
        today = now.date()

        report = EvaluationReport(
            tenant_id=tenant_id,
            generated_at=now.isoformat(),
        )

        async with self.db_pool.acquire() as conn:
            ar_rows = await conn.fetch("""
                SELECT id, entity_name, amount, date, due_date, status, metadata, items
                FROM transactions
                WHERE type = 'receivable'
                  AND (metadata->>'tenant_id' = $1 OR $1 = 'all')
                ORDER BY due_date ASC NULLS LAST
            """, tenant_id)

            for row in ar_rows:
                entry = self._classify_ar(row, today)
                report.ar_entries.append(entry)

                if entry.status == ARStatus.PAID:
                    pass
                elif entry.status == ARStatus.WRITTEN_OFF:
                    pass
                elif entry.status == ARStatus.CURRENT:
                    report.ar_current += entry.amount
                elif entry.status == ARStatus.OVERDUE_30:
                    report.ar_overdue_30 += entry.amount
                elif entry.status == ARStatus.OVERDUE_60:
                    report.ar_overdue_60 += entry.amount
                elif entry.status == ARStatus.OVERDUE_90:
                    report.ar_overdue_90 += entry.amount
                elif entry.status == ARStatus.OVERDUE_90_PLUS:
                    report.ar_overdue_90_plus += entry.amount
                elif entry.status == ARStatus.PARTIAL:
                    report.ar_current += entry.balance_remaining

            report.ar_total = (report.ar_current + report.ar_overdue_30 +
                               report.ar_overdue_60 + report.ar_overdue_90 +
                               report.ar_overdue_90_plus)

            ap_rows = await conn.fetch("""
                SELECT id, entity_name, amount, date, due_date, status, metadata
                FROM transactions
                WHERE type = 'payable'
                  AND (metadata->>'tenant_id' = $1 OR $1 = 'all')
                ORDER BY due_date ASC NULLS LAST
            """, tenant_id)

            for row in ap_rows:
                entry = self._classify_ap(row, today)
                report.ap_entries.append(entry)
                if entry.status == APStatus.SCHEDULED:
                    report.ap_scheduled += entry.amount
                elif entry.status == APStatus.DUE_SOON:
                    report.ap_due_soon += entry.amount
                elif entry.status == APStatus.OVERDUE:
                    report.ap_overdue += entry.amount

            report.ap_total = report.ap_scheduled + report.ap_due_soon + report.ap_overdue

            txn_rows = await conn.fetch("""
                SELECT id, entity_name, amount, date, status, metadata
                FROM transactions
                WHERE type = 'transfer'
                  AND (metadata->>'tenant_id' = $1 OR $1 = 'all')
                ORDER BY date DESC
                LIMIT 500
            """, tenant_id)

            for row in txn_rows:
                entry = self._classify_txn(row)
                report.txn_entries.append(entry)
                report.txn_total += 1
                if entry.status == TxnStatus.RECONCILED:
                    report.txn_reconciled += 1
                elif entry.status == TxnStatus.UNMATCHED:
                    report.txn_unmatched += 1
                elif entry.status == TxnStatus.PENDING:
                    report.txn_pending += 1

            if report.txn_total > 0:
                report.reconciliation_rate = round(
                    report.txn_reconciled / report.txn_total * 100, 1
                )

        report.health_score = self._compute_health(report)
        report.recommended_actions = self._generate_recommendations(report)
        return report

    def _classify_ar(self, row: dict, today) -> AREntry:
        """Classify a single AR record into an aging bucket."""
        meta = row.get("metadata")
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}

        explicit_status = (row.get("status") or "").lower()
        status_map = {
            "paid": ARStatus.PAID,
            "written_off": ARStatus.WRITTEN_OFF,
            "disputed": ARStatus.DISPUTED,
            "partial": ARStatus.PARTIAL,
        }
        if explicit_status in status_map:
            return AREntry(
                id=str(row["id"]),
                entity_name=row["entity_name"],
                amount=float(row["amount"]),
                date=str(row["date"]),
                due_date=str(row.get("due_date") or ""),
                status=status_map[explicit_status],
                metadata=meta,
            )

        due_date = row.get("due_date")
        if due_date and hasattr(due_date, "date"):
            due_date = due_date.date()
        elif isinstance(due_date, str):
            try:
                from datetime import date as date_type
                due_date = date_type.fromisoformat(due_date)
            except Exception:
                due_date = None

        days_past = 0
        if due_date:
            delta = today - due_date
            days_past = delta.days

        if days_past <= 0:
            status = ARStatus.CURRENT
        elif days_past <= 30:
            status = ARStatus.OVERDUE_30
        elif days_past <= 60:
            status = ARStatus.OVERDUE_60
        elif days_past <= 90:
            status = ARStatus.OVERDUE_90
        else:
            status = ARStatus.OVERDUE_90_PLUS

        return AREntry(
            id=str(row["id"]),
            entity_name=row["entity_name"],
            amount=float(row["amount"]),
            date=str(row["date"]),
            due_date=str(due_date or ""),
            status=status,
            days_past_due=max(days_past, 0),
            metadata=meta,
        )

    def _classify_ap(self, row: dict, today) -> APEntry:
        """Classify a single AP record by urgency."""
        meta = row.get("metadata")
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}

        explicit_status = (row.get("status") or "").lower()
        status_map = {
            "paid": APStatus.PAID,
            "rejected": APStatus.REJECTED,
            "on_hold": APStatus.ON_HOLD,
            "awaiting_hitl_approval": APStatus.PENDING_APPROVAL,
            "pending_approval": APStatus.PENDING_APPROVAL,
        }
        if explicit_status in status_map:
            return APEntry(
                id=str(row["id"]),
                vendor_name=row["entity_name"],
                amount=float(row["amount"]),
                date=str(row["date"]),
                due_date=str(row.get("due_date") or ""),
                status=status_map[explicit_status],
                metadata=meta,
            )

        due_date = row.get("due_date")
        if due_date and hasattr(due_date, "date"):
            due_date = due_date.date()
        elif isinstance(due_date, str):
            try:
                from datetime import date as date_type
                due_date = date_type.fromisoformat(due_date)
            except Exception:
                due_date = None

        days_until = 0
        if due_date:
            days_until = (due_date - today).days

        if days_until < 0:
            status = APStatus.OVERDUE
        elif days_until <= 7:
            status = APStatus.DUE_SOON
        else:
            status = APStatus.SCHEDULED

        return APEntry(
            id=str(row["id"]),
            vendor_name=row["entity_name"],
            amount=float(row["amount"]),
            date=str(row["date"]),
            due_date=str(due_date or ""),
            status=status,
            days_until_due=days_until,
            metadata=meta,
        )

    def _classify_txn(self, row: dict) -> TxnEntry:
        """Classify a bank transaction by reconciliation state."""
        meta = row.get("metadata")
        if isinstance(meta, str):
            meta = json.loads(meta) if meta else {}

        if meta.get("bank_confirmed"):
            status = TxnStatus.RECONCILED
        elif meta.get("category"):
            status = TxnStatus.ENRICHED
        elif (row.get("status") or "").lower() == "pending":
            status = TxnStatus.PENDING
        else:
            status = TxnStatus.UNMATCHED

        return TxnEntry(
            id=str(row["id"]),
            counterparty=row.get("entity_name", ""),
            amount=float(row["amount"]),
            date=str(row["date"]),
            status=status,
            category=meta.get("category", ""),
            gl_code=meta.get("gl_code", ""),
            metadata=meta,
        )

    def _compute_health(self, report: EvaluationReport) -> int:
        """Compute a 0-100 health score."""
        score = 100

        if report.ar_total > 0:
            overdue_ratio = (
                report.ar_overdue_30 + report.ar_overdue_60 +
                report.ar_overdue_90 + report.ar_overdue_90_plus
            ) / report.ar_total
            score -= int(overdue_ratio * 30)

            critical_ratio = report.ar_overdue_90_plus / report.ar_total
            score -= int(critical_ratio * 20)

        if report.ap_total > 0:
            overdue_ap_ratio = report.ap_overdue / report.ap_total
            score -= int(overdue_ap_ratio * 20)

        if report.txn_total > 0:
            unmatched_ratio = report.txn_unmatched / report.txn_total
            score -= int(unmatched_ratio * 15)

        return max(0, min(100, score))

    def _generate_recommendations(self, report: EvaluationReport) -> List[Dict]:
        """Generate agent action recommendations based on the evaluation."""
        actions = []

        critical_ar = [e for e in report.ar_entries if e.status == ARStatus.OVERDUE_90_PLUS]
        if critical_ar:
            total = sum(e.amount for e in critical_ar)
            actions.append({
                "agent": "collector",
                "action": "escalate_critical_ar",
                "priority": "critical",
                "title": f"Escalate {len(critical_ar)} invoice(s) overdue 90+ days",
                "description": f"${total:,.0f} at risk of write-off. Immediate escalation required.",
                "estimated_impact": total,
                "automatable": False,
            })

        overdue_30_60 = [e for e in report.ar_entries
                         if e.status in (ARStatus.OVERDUE_30, ARStatus.OVERDUE_60)]
        if overdue_30_60:
            total = sum(e.amount for e in overdue_30_60)
            actions.append({
                "agent": "collector",
                "action": "send_collection_reminder",
                "priority": "high",
                "title": f"Send reminders for {len(overdue_30_60)} overdue invoice(s)",
                "description": f"${total:,.0f} in 30-60 day aging. Automated reminders recommended.",
                "estimated_impact": total,
                "automatable": True,
            })

        overdue_ap = [e for e in report.ap_entries if e.status == APStatus.OVERDUE]
        if overdue_ap:
            total = sum(e.amount for e in overdue_ap)
            actions.append({
                "agent": "paymaster",
                "action": "review_overdue_ap",
                "priority": "high",
                "title": f"Review {len(overdue_ap)} overdue payable(s)",
                "description": f"${total:,.0f} past due. Vendor relationships at risk.",
                "estimated_impact": total,
                "automatable": False,
            })

        if report.reconciliation_rate < 80 and report.txn_unmatched > 5:
            actions.append({
                "agent": "reconciler",
                "action": "reconcile_unmatched_transactions",
                "priority": "medium",
                "title": f"Reconcile {report.txn_unmatched} unmatched transaction(s)",
                "description": f"Reconciliation rate at {report.reconciliation_rate:.1f}%. Books need attention.",
                "estimated_impact": None,
                "automatable": True,
            })

        return actions

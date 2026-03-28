"""
Mercury Bank Integration Service
Real-time transaction feeds, account balances, and auto-reconciliation with the GP ledger.
"""

import aiohttp
import json
import os
import uuid
import time as _t
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import logging

logger = logging.getLogger("tron.mercury")

# Lazy imports — these may not be installed in every environment
_FinancialEnrichmentService = None
_bigquery = None

def _get_enricher():
    global _FinancialEnrichmentService
    if _FinancialEnrichmentService is None:
        try:
            import sys, os
            _svc_dir = os.path.join(os.path.dirname(__file__), "..", "services")
            if _svc_dir not in sys.path:
                sys.path.insert(0, _svc_dir)
            from financial_enrichment import FinancialEnrichmentService
            _FinancialEnrichmentService = FinancialEnrichmentService
        except ImportError:
            logger.warning("FinancialEnrichmentService not available — enrichment disabled")
            return None
    return _FinancialEnrichmentService()

def _get_bq_client():
    global _bigquery
    if _bigquery is None:
        try:
            from google.cloud import bigquery
            _bigquery = bigquery
        except ImportError:
            logger.warning("google-cloud-bigquery not installed — BQ ingestion disabled")
            return None
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "tron-cloud")
    return _bigquery.Client(project=project)


MERCURY_API_BASE = "https://api.mercury.com/api/v1"


class MercuryService:
    """Async service for Mercury Bank API integration."""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._config = None
        self._enricher = None
        self._bq_client = None

    # ── Config Management ────────────────────────────────────────────────

    async def _load_config(self):
        """Load Mercury config from integration_configs table."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM integration_configs WHERE platform = 'mercury'"
            )
            if row:
                self._config = dict(row)
                if isinstance(self._config.get("settings"), str):
                    self._config["settings"] = json.loads(self._config["settings"])
            return self._config

    async def _save_config(self, settings: dict, status: str = "connected"):
        """Persist Mercury config to integration_configs table."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO integration_configs (id, platform, status, settings, updated_at)
                VALUES ('mercury-primary', 'mercury', $1, $2::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    settings = $2::jsonb,
                    status = $1,
                    updated_at = CURRENT_TIMESTAMP
            """, status, json.dumps(settings))
        self._config = {"settings": settings, "status": status}

    # ── Connection ───────────────────────────────────────────────────────

    async def connect(self, api_token: str) -> dict:
        """Validate and store Mercury API token."""
        # Validate by calling the accounts endpoint
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{MERCURY_API_BASE}/accounts",
                headers={"Authorization": f"Bearer {api_token}", "Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    return {"success": False, "error": f"Invalid token or API error: {error_body}"}

                data = await resp.json()
                accounts = data.get("accounts", [])
                account_ids = [a["id"] for a in accounts]

                settings = {
                    "api_token": api_token,
                    "account_ids": account_ids,
                    "primary_account_id": account_ids[0] if account_ids else "",
                }
                await self._save_config(settings)

                return {
                    "success": True,
                    "accounts": len(accounts),
                    "account_names": [a.get("name", "Unknown") for a in accounts],
                }

    async def _mercury_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Make an authenticated request to the Mercury API."""
        if not self._config:
            await self._load_config()
        if not self._config:
            raise ValueError("Mercury not connected. Run connect flow first.")

        token = self._config["settings"]["api_token"]
        url = f"{MERCURY_API_BASE}/{endpoint}"

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(
                    url,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    params=params,
                ) as resp:
                    if resp.status != 200:
                        return {"error": f"Mercury API error: {resp.status}", "body": await resp.text()}
                    return await resp.json()
            elif method == "POST":
                async with session.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=params,
                ) as resp:
                    return await resp.json()

    # ── Account Operations ───────────────────────────────────────────────

    async def get_accounts(self) -> dict:
        """Return all Mercury account balances."""
        data = await self._mercury_request("GET", "accounts")
        accounts = data.get("accounts", [])
        return {
            "success": True,
            "accounts": [
                {
                    "id": a["id"],
                    "name": a.get("name", "Unknown"),
                    "type": a.get("type", "checking"),
                    "current_balance": float(a.get("currentBalance", 0)),
                    "available_balance": float(a.get("availableBalance", 0)),
                    "account_number": a.get("accountNumber", "")[-4:] if a.get("accountNumber") else "",
                }
                for a in accounts
            ],
        }

    # ── Transaction Operations ───────────────────────────────────────────

    async def get_transactions(
        self, days_back: int = 30, limit: int = 500, account_id: str = None
    ) -> dict:
        """Pull transactions from Mercury for a given period."""
        if not self._config:
            await self._load_config()

        acct_id = account_id or self._config["settings"].get("primary_account_id", "")
        if not acct_id:
            return {"success": False, "error": "No account ID configured"}

        start = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        data = await self._mercury_request(
            "GET",
            f"account/{acct_id}/transactions",
            params={"start": start, "end": end, "limit": limit},
        )

        if "error" in data:
            return data

        transactions = data.get("transactions", [])
        return {
            "success": True,
            "count": len(transactions),
            "transactions": [
                {
                    "id": t["id"],
                    "amount": float(t.get("amount", 0)),
                    "counterparty": t.get("counterpartyName", "Unknown"),
                    "date": t.get("createdAt", ""),
                    "status": t.get("status", "unknown"),
                    "kind": t.get("kind", ""),
                    "note": t.get("note", ""),
                }
                for t in transactions
            ],
        }

    async def sync_transactions(self, days_back: int = 7) -> dict:
        """Pull Mercury transactions and auto-reconcile against the GP ledger."""
        txn_result = await self.get_transactions(days_back=days_back)
        if not txn_result.get("success"):
            return txn_result

        bank_txns = txn_result["transactions"]
        exact_matches = 0
        fuzzy_matches = 0
        unmatched = 0
        skipped = 0

        async with self.db_pool.acquire() as conn:
            for txn in bank_txns:
                external_ref = f"MRC-{txn['id']}"

                # Dedup: skip if already reconciled
                existing = await conn.fetchrow(
                    "SELECT id FROM transactions WHERE metadata->>'external_ref' = $1",
                    external_ref,
                )
                if existing:
                    skipped += 1
                    continue

                amount = abs(txn["amount"])
                counterparty = txn.get("counterparty", txn.get("counterpartyName", "Unknown"))
                raw_date = txn.get("date", txn.get("createdAt", ""))
                txn_date = raw_date[:10] if raw_date else None

                match_type = None

                # Tier 1: Exact match (amount + entity name + date ±2 days)
                match = await conn.fetchrow("""
                    SELECT id, entity_name, amount, date FROM transactions
                    WHERE ABS(amount - $1) < 0.01
                      AND LOWER(entity_name) = LOWER($2)
                      AND ABS(date - $3::date) <= 2
                      AND (metadata->>'bank_confirmed') IS NULL
                    ORDER BY date DESC LIMIT 1
                """, amount, counterparty, txn_date)
                
                if match:
                    match_type = "exact"

                if not match:
                    # Tier 2: Fuzzy match (amount exact + date ±5 days)
                    match = await conn.fetchrow("""
                        SELECT id, entity_name, amount, date FROM transactions
                        WHERE ABS(amount - $1) < 0.01
                          AND ABS(date - $2::date) <= 5
                          AND (metadata->>'bank_confirmed') IS NULL
                        ORDER BY date DESC LIMIT 1
                    """, amount, txn_date)
                    if match:
                        match_type = "fuzzy"

                if match:
                    # Update ledger entry as bank-confirmed
                    current_meta = await conn.fetchval(
                        "SELECT metadata FROM transactions WHERE id = $1", match["id"]
                    )
                    meta = json.loads(current_meta) if isinstance(current_meta, str) else (current_meta or {})
                    meta["bank_confirmed"] = True
                    meta["external_ref"] = external_ref
                    meta["bank_date"] = txn_date
                    meta["reconciled_at"] = datetime.now(timezone.utc).isoformat()
                    meta["match_type"] = "exact" if match_type == "exact" else "fuzzy"

                    await conn.execute(
                        "UPDATE transactions SET metadata = $1::jsonb, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                        json.dumps(meta), match["id"],
                    )
                    if match_type == "exact":
                        exact_matches += 1
                    else:
                        fuzzy_matches += 1
                else:
                    unmatched += 1

        # Update last sync
        await self._update_sync_time()

        # -- Phase 2: AI Enrichment & BigQuery Ingestion ------------------
        enriched_count = 0
        enricher = _get_enricher()
        bq_client = _get_bq_client()
        if enricher and bq_client:
            try:
                to_enrich = list(bank_txns)
                enriched_txns = await enricher.batch_enrich(to_enrich)

                bq_rows = []
                for et in enriched_txns:
                    bq_rows.append({
                        "entry_id": f"mrc_{et['id']}",
                        "tenant_id": et.get("tenant_id", "ghost-protocol"),
                        "date": et["date"][:10],
                        "amount": float(et["amount"]),
                        "counterparty_raw": et.get("counterparty", "Unknown"),
                        "counterparty_normalized": et.get("normalized_name", ""),
                        "category": et.get("category", ""),
                        "gl_code": et.get("gl_code", ""),
                        "platform": "mercury",
                        "platform_ref": et["id"],
                        "status": "processed",
                        "is_ap": et.get("is_ap", False),
                        "is_ar": et.get("is_ar", False),
                        "metadata": json.dumps({
                            "kind": et.get("kind", ""),
                            "note": et.get("note", ""),
                            "mercury_status": et.get("status", "")
                        }),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })

                if bq_rows:
                    project = os.getenv("GOOGLE_CLOUD_PROJECT", "tron-cloud")
                    table_id = f"{project}.gaa_financial.ledger_entries"
                    errors = bq_client.insert_rows_json(table_id, bq_rows)
                    if errors:
                        logger.error(f"BigQuery ingestion errors: {errors}")
                    else:
                        enriched_count = len(bq_rows)
            except Exception as e:
                logger.error(f"Enrichment/BigQuery phase failed: {e}")

        total_matched = exact_matches + fuzzy_matches
        return {
            "success": True,
            "total": len(bank_txns),
            "exact_matches": exact_matches,
            "fuzzy_matches": fuzzy_matches,
            "unmatched": unmatched,
            "enriched_and_logged": enriched_count,
            "skipped": skipped,
            "match_rate": f"{(total_matched / max(total_matched + unmatched, 1)) * 100:.1f}%",
            "source": "mercury",
        }

    async def get_recipients(self) -> dict:
        """List Mercury payment recipients."""
        if not self._config:
            await self._load_config()
        if not self._config:
            return {"success": False, "error": "Mercury not connected"}

        data = await self._mercury_request("GET", "recipients")
        if "error" in data:
            return data
        recipients = data.get("recipients", [])
        return {
            "success": True,
            "recipients": [
                {
                    "id": r["id"],
                    "name": r.get("name", "Unknown"),
                    "emails": r.get("emails", []),
                    "payment_method": r.get("paymentMethod", ""),
                }
                for r in recipients
            ],
        }

    async def send_payment(
        self, recipient_id: str, amount: float, payment_method: str = "ach",
        idempotency_key: str = None, note: str = "", hitl_approved: bool = False
    ) -> dict:
        """Send a payment to an existing Mercury recipient.

        When hitl_approved is False, the payment is staged in the pending_payments
        table for review in the HITL dashboard. Mercury remains the source of truth
        for actual ACH execution — we only call their API when explicitly approved.
        """
        if not self._config:
            await self._load_config()
        if not self._config:
            return {"success": False, "error": "Mercury not connected"}

        acct_id = self._config["settings"].get("primary_account_id", "")
        if not acct_id:
            return {"success": False, "error": "No account ID configured"}

        idem_key = idempotency_key or f"gp-pay-{int(_t.time())}"

        if not hitl_approved:
            # ── Stage payment in DB for dashboard review ──────────────
            payment_id = str(uuid.uuid4())
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO pending_payments
                        (id, recipient_id, amount, payment_method, idempotency_key, note, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'awaiting_hitl_approval')
                """, payment_id, recipient_id, amount, payment_method, idem_key, note)

            return {
                "success": True,
                "status": "awaiting_hitl_approval",
                "payment_id": payment_id,
                "message": "Payment staged for HITL dashboard approval.",
                "staged_amount": amount,
                "recipient_id": recipient_id,
                "idempotency_key": idem_key,
            }

        # ── Execute the real ACH via Mercury's API ────────────────────
        payload = {
            "recipientId": recipient_id,
            "amount": amount,
            "paymentMethod": payment_method,
            "idempotencyKey": idem_key,
            "note": note,
        }

        result = await self._mercury_request("POST", f"account/{acct_id}/transactions", params=payload)
        if "error" in result:
            return {"success": False, **result}

        return {
            "success": True,
            "transaction_id": result.get("id", ""),
            "status": result.get("status", "pending"),
            "amount": amount,
        }

    # ── HITL Dashboard Endpoints ─────────────────────────────────────────

    async def get_pending_payments(self) -> dict:
        """Return all payments awaiting HITL approval from the staging table."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, recipient_id, amount, payment_method,
                       idempotency_key, note, status, created_at
                FROM pending_payments
                WHERE status = 'awaiting_hitl_approval'
                ORDER BY created_at DESC
            """)
        payments = [
            {
                "id": r["id"],
                "recipient_id": r["recipient_id"],
                "amount": float(r["amount"]),
                "payment_method": r["payment_method"],
                "idempotency_key": r["idempotency_key"],
                "note": r["note"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"success": True, "count": len(payments), "payments": payments}

    async def review_payment(self, payment_id: str, action: str) -> dict:
        """Approve or reject a staged payment.

        On approval, executes the real Mercury ACH transfer.
        Mercury remains the source of truth for the payment lifecycle.
        """
        if action not in ("approve", "reject"):
            return {"success": False, "error": f"Invalid action: {action}. Must be 'approve' or 'reject'."}

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pending_payments WHERE id = $1", payment_id
            )

        if not row:
            return {"success": False, "error": f"Payment {payment_id} not found."}
        if row["status"] != "awaiting_hitl_approval":
            return {"success": False, "error": f"Payment already processed (status: {row['status']})."}

        if action == "reject":
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE pending_payments SET status = 'rejected' WHERE id = $1",
                    payment_id,
                )
            return {"success": True, "status": "rejected", "payment_id": payment_id}

        # ── Approve: execute the real ACH via Mercury ─────────────────
        result = await self.send_payment(
            recipient_id=row["recipient_id"],
            amount=float(row["amount"]),
            payment_method=row["payment_method"],
            idempotency_key=row["idempotency_key"],
            note=row["note"] or "",
            hitl_approved=True,
        )

        new_status = "executed" if result.get("success") else "failed"
        txn_id = result.get("transaction_id", "")

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE pending_payments SET status = $1, transaction_id = $2 WHERE id = $3",
                new_status, txn_id, payment_id,
            )

        return {
            "success": result.get("success", False),
            "status": new_status,
            "payment_id": payment_id,
            "mercury_result": result,
        }

    async def full_sync(self, days_back: int = 7) -> dict:
        """Run a complete Mercury sync: transactions + reconciliation."""
        results = {}

        try:
            results["transactions"] = await self.sync_transactions(days_back=days_back)
        except Exception as e:
            results["transactions"] = {"success": False, "error": str(e)}

        try:
            results["accounts"] = await self.get_accounts()
        except Exception as e:
            results["accounts"] = {"success": False, "error": str(e)}

        return {
            "success": all(r.get("success") for r in results.values()),
            "results": results,
            "source": "mercury",
        }

    async def _update_sync_time(self):
        """Update the last_sync_at timestamp."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE integration_configs SET last_sync_at = CURRENT_TIMESTAMP
                WHERE platform = 'mercury'
            """)

    async def get_status(self) -> dict:
        """Return connection status with capabilities."""
        config = await self._load_config()
        if not config:
            return {"connected": False, "platform": "mercury"}
        return {
            "connected": config.get("status") == "connected",
            "platform": "mercury",
            "last_sync_at": str(config.get("last_sync_at", "")),
            "accounts": len(config.get("settings", {}).get("account_ids", [])),
            "capabilities": {
                "read": ["accounts", "transactions", "recipients"],
                "write": ["send_payment"],
                "sync": ["full_sync", "sync_transactions", "get_accounts", "get_recipients"],
            },
        }

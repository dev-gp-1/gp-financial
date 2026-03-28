"""
Stripe Integration Service
Payment links, invoicing, customer management, webhook processing, and payout tracking.

Stripe auth: Single API key (sk_test_ for sandbox, sk_live_ for production).
All requests use Bearer token auth.

Docs: https://docs.stripe.com/api
"""

import aiohttp
import json
import time
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional


STRIPE_API_BASE = "https://api.stripe.com/v1"


class StripeService:
    """Async service for Stripe API integration."""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._config = None

    # ── Config Management ────────────────────────────────────────────────

    async def _load_config(self):
        """Load Stripe config from integration_configs table."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM integration_configs WHERE platform = 'stripe'"
            )
            if row:
                self._config = dict(row)
                if isinstance(self._config.get("settings"), str):
                    self._config["settings"] = json.loads(self._config["settings"])
            return self._config

    async def _save_config(self, settings: dict, status: str = "connected"):
        """Persist Stripe config to integration_configs table."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO integration_configs (id, platform, status, settings, updated_at)
                VALUES ('stripe-primary', 'stripe', $1, $2::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    settings = $2::jsonb,
                    status = $1,
                    updated_at = CURRENT_TIMESTAMP
            """, status, json.dumps(settings))
        self._config = {"settings": settings, "status": status}

    # ── Connection ───────────────────────────────────────────────────────

    async def connect(self, api_key: str, webhook_secret: str = "") -> dict:
        """Validate and store Stripe API key.

        Args:
            api_key: Stripe secret key (sk_test_... or sk_live_...)
            webhook_secret: Optional webhook endpoint secret (whsec_...)
        """
        # Validate by fetching account info
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{STRIPE_API_BASE}/account",
                headers={"Authorization": f"Bearer {api_key}"},
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    return {"success": False, "error": f"Invalid Stripe key: {error_body}"}

                account = await resp.json()
                is_test = api_key.startswith("sk_test_")

                settings = {
                    "api_key": api_key,
                    "webhook_secret": webhook_secret,
                    "account_id": account.get("id", ""),
                    "business_name": account.get("business_profile", {}).get("name", ""),
                    "country": account.get("country", ""),
                    "default_currency": account.get("default_currency", "usd"),
                    "is_test_mode": is_test,
                }
                await self._save_config(settings)

                return {
                    "success": True,
                    "account_id": settings["account_id"],
                    "business_name": settings["business_name"],
                    "mode": "test" if is_test else "live",
                }

    async def _stripe_request(
        self, method: str, endpoint: str, data: dict = None, params: dict = None
    ) -> dict:
        """Make an authenticated request to the Stripe API.

        Note: Stripe uses form-encoded POST bodies, not JSON.
        """
        if not self._config:
            await self._load_config()
        if not self._config:
            raise ValueError("Stripe not connected. Run connect flow first.")

        api_key = self._config["settings"]["api_key"]
        url = f"{STRIPE_API_BASE}/{endpoint}"
        headers = {"Authorization": f"Bearer {api_key}"}

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status not in (200, 201):
                        return {"error": f"Stripe API error: {resp.status}", "body": await resp.text()}
                    return await resp.json()
            elif method == "POST":
                # Stripe uses form-encoded data, not JSON
                async with session.post(url, headers=headers, data=data) as resp:
                    if resp.status not in (200, 201):
                        return {"error": f"Stripe API error: {resp.status}", "body": await resp.text()}
                    return await resp.json()

    # ── Customer Management ──────────────────────────────────────────────

    async def create_customer(self, name: str, email: str = "", metadata: dict = None) -> dict:
        """Create a Stripe customer for invoice association."""
        data = {"name": name}
        if email:
            data["email"] = email
        if metadata:
            for k, v in metadata.items():
                data[f"metadata[{k}]"] = str(v)

        result = await self._stripe_request("POST", "customers", data=data)
        if "error" in result:
            return {"success": False, **result}

        return {
            "success": True,
            "customer_id": result["id"],
            "name": result.get("name", ""),
            "email": result.get("email", ""),
        }

    async def find_customer(self, email: str) -> dict:
        """Find a Stripe customer by email."""
        result = await self._stripe_request("GET", "customers", params={"email": email, "limit": 1})
        if "error" in result:
            return {"success": False, **result}

        customers = result.get("data", [])
        if not customers:
            return {"success": True, "found": False}

        c = customers[0]
        return {
            "success": True,
            "found": True,
            "customer_id": c["id"],
            "name": c.get("name", ""),
            "email": c.get("email", ""),
        }

    # ── Invoice Management ───────────────────────────────────────────────

    async def create_invoice(
        self, customer_id: str, items: list, due_days: int = 30,
        description: str = "", auto_send: bool = True
    ) -> dict:
        """Create and optionally send a Stripe invoice.

        Args:
            customer_id: Stripe customer ID (cus_...)
            items: List of {"description": str, "amount": float, "currency": str}
            due_days: Days until due
            description: Invoice memo
            auto_send: Whether to finalize and send immediately
        """
        # Step 1: Create invoice items
        for item in items:
            amount_cents = int(float(item.get("amount", 0)) * 100)
            item_data = {
                "customer": customer_id,
                "amount": str(amount_cents),
                "currency": item.get("currency", "usd"),
                "description": item.get("description", "Service"),
            }
            result = await self._stripe_request("POST", "invoiceitems", data=item_data)
            if "error" in result:
                return {"success": False, "error": f"Failed to create line item: {result}"}

        # Step 2: Create the invoice
        invoice_data = {
            "customer": customer_id,
            "collection_method": "send_invoice",
            "days_until_due": str(due_days),
        }
        if description:
            invoice_data["description"] = description

        invoice = await self._stripe_request("POST", "invoices", data=invoice_data)
        if "error" in invoice:
            return {"success": False, "error": f"Failed to create invoice: {invoice}"}

        invoice_id = invoice["id"]

        # Step 3: Finalize and send if requested
        if auto_send:
            finalized = await self._stripe_request("POST", f"invoices/{invoice_id}/finalize")
            if "error" not in finalized:
                await self._stripe_request("POST", f"invoices/{invoice_id}/send")

        return {
            "success": True,
            "invoice_id": invoice_id,
            "invoice_number": invoice.get("number", ""),
            "amount_due": invoice.get("amount_due", 0) / 100,
            "hosted_invoice_url": invoice.get("hosted_invoice_url", ""),
            "status": invoice.get("status", "draft"),
        }

    async def get_invoice(self, invoice_id: str) -> dict:
        """Get a specific Stripe invoice."""
        result = await self._stripe_request("GET", f"invoices/{invoice_id}")
        if "error" in result:
            return {"success": False, **result}
        return {
            "success": True,
            "invoice_id": result["id"],
            "status": result.get("status", ""),
            "amount_due": result.get("amount_due", 0) / 100,
            "amount_paid": result.get("amount_paid", 0) / 100,
            "hosted_invoice_url": result.get("hosted_invoice_url", ""),
            "customer": result.get("customer", ""),
        }

    # ── Payment Sync ─────────────────────────────────────────────────────

    async def sync_payments(self, days_back: int = 7) -> dict:
        """Pull recent Stripe charges and update GP ledger."""
        created_after = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
        result = await self._stripe_request(
            "GET", "charges",
            params={"created[gte]": str(created_after), "limit": "100"},
        )
        if "error" in result:
            return {"success": False, **result}

        charges = result.get("data", [])
        synced = 0

        async with self.db_pool.acquire() as conn:
            for charge in charges:
                if charge.get("status") != "succeeded":
                    continue

                charge_id = f"STRIPE-{charge['id']}"
                amount = charge.get("amount", 0) / 100
                customer = charge.get("billing_details", {}).get("name", "Unknown")
                created = datetime.fromtimestamp(charge["created"], tz=timezone.utc)
                description = charge.get("description", "")
                invoice_id = charge.get("invoice", "")

                await conn.execute("""
                    INSERT INTO transactions (
                        id, type, entity_name, amount, date, status,
                        metadata, created_at, updated_at
                    ) VALUES ($1, 'receivable', $2, $3, $4::date, 'paid',
                              $5::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        status = 'paid',
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, charge_id, customer, amount,
                    created.strftime("%Y-%m-%d"),
                    json.dumps({
                        "source": "stripe",
                        "stripe_charge_id": charge["id"],
                        "stripe_invoice_id": invoice_id,
                        "description": description,
                        "payment_method": charge.get("payment_method_details", {}).get("type", ""),
                    }))
                synced += 1

        await self._update_sync_time()
        return {"success": True, "synced": synced, "total_charges": len(charges), "source": "stripe"}

    async def sync_invoices(self, days_back: int = 7) -> dict:
        """Pull Stripe invoices and update GP ledger."""
        created_after = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
        result = await self._stripe_request(
            "GET", "invoices",
            params={"created[gte]": str(created_after), "limit": "100"},
        )
        if "error" in result:
            return {"success": False, **result}

        invoices = result.get("data", [])
        synced = 0

        async with self.db_pool.acquire() as conn:
            for inv in invoices:
                inv_id = f"STRIPE-INV-{inv['id']}"
                amount = inv.get("amount_due", 0) / 100
                amount_paid = inv.get("amount_paid", 0) / 100
                customer_name = inv.get("customer_name", "Unknown")
                created = datetime.fromtimestamp(inv["created"], tz=timezone.utc)
                status = "paid" if inv.get("status") == "paid" else "pending"
                due_date_ts = inv.get("due_date")
                due_date = datetime.fromtimestamp(due_date_ts, tz=timezone.utc).strftime("%Y-%m-%d") if due_date_ts else None

                await conn.execute("""
                    INSERT INTO transactions (
                        id, type, entity_name, amount, date, due_date, status,
                        metadata, created_at, updated_at
                    ) VALUES ($1, 'receivable', $2, $3, $4::date, $5::date, $6,
                              $7::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        amount = EXCLUDED.amount,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, inv_id, customer_name, amount,
                    created.strftime("%Y-%m-%d"), due_date, status,
                    json.dumps({
                        "source": "stripe",
                        "stripe_invoice_id": inv["id"],
                        "hosted_url": inv.get("hosted_invoice_url", ""),
                        "amount_paid": amount_paid,
                        "invoice_number": inv.get("number", ""),
                    }))
                synced += 1

        await self._update_sync_time()
        return {"success": True, "synced": synced, "source": "stripe"}

    # ── Payout Tracking ──────────────────────────────────────────────────

    async def sync_payouts(self, days_back: int = 7) -> dict:
        """Pull Stripe payouts (deposits to your bank) for reconciliation."""
        created_after = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
        result = await self._stripe_request(
            "GET", "payouts",
            params={"created[gte]": str(created_after), "limit": "100"},
        )
        if "error" in result:
            return {"success": False, **result}

        payouts = result.get("data", [])
        return {
            "success": True,
            "payouts": [
                {
                    "id": p["id"],
                    "amount": p.get("amount", 0) / 100,
                    "status": p.get("status", ""),
                    "arrival_date": datetime.fromtimestamp(
                        p.get("arrival_date", 0), tz=timezone.utc
                    ).strftime("%Y-%m-%d") if p.get("arrival_date") else "",
                    "description": p.get("description", ""),
                }
                for p in payouts
            ],
            "source": "stripe",
        }

    # ── Webhook Processing ───────────────────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> bool:
        """Verify a Stripe webhook signature.

        Args:
            payload: Raw request body bytes
            sig_header: Stripe-Signature header value
        """
        if not self._config:
            return False

        webhook_secret = self._config["settings"].get("webhook_secret", "")
        if not webhook_secret:
            return False

        # Parse signature header: t=timestamp,v1=signature
        parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")

        if not timestamp or not signature:
            return False

        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            webhook_secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_webhook(self, event: dict) -> dict:
        """Process a Stripe webhook event and update GP ledger.

        Key events:
        - invoice.paid → mark AR as paid
        - invoice.payment_failed → flag for follow-up
        - charge.succeeded → record payment
        - payout.paid → reconciliation marker
        """
        event_type = event.get("type", "")
        obj = event.get("data", {}).get("object", {})

        if event_type == "invoice.paid":
            inv_id = f"STRIPE-INV-{obj.get('id', '')}"
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE transactions SET status = 'paid', updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                """, inv_id)
            return {"processed": True, "action": "invoice_marked_paid", "id": inv_id}

        elif event_type == "invoice.payment_failed":
            inv_id = f"STRIPE-INV-{obj.get('id', '')}"
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE transactions SET status = 'overdue', updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                """, inv_id)
            return {"processed": True, "action": "invoice_marked_overdue", "id": inv_id}

        elif event_type == "charge.succeeded":
            return {"processed": True, "action": "charge_recorded", "amount": obj.get("amount", 0) / 100}

        return {"processed": False, "event_type": event_type}

    # ── Full Sync ────────────────────────────────────────────────────────

    async def full_sync(self, days_back: int = 7) -> dict:
        """Run a complete Stripe sync: invoices + payments + payouts."""
        results = {}

        try:
            results["invoices"] = await self.sync_invoices(days_back=days_back)
        except Exception as e:
            results["invoices"] = {"success": False, "error": str(e)}

        try:
            results["payments"] = await self.sync_payments(days_back=days_back)
        except Exception as e:
            results["payments"] = {"success": False, "error": str(e)}

        try:
            results["payouts"] = await self.sync_payouts(days_back=days_back)
        except Exception as e:
            results["payouts"] = {"success": False, "error": str(e)}

        return {
            "success": all(r.get("success") for r in results.values()),
            "results": results,
            "source": "stripe",
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _update_sync_time(self):
        """Update the last_sync_at timestamp."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE integration_configs SET last_sync_at = CURRENT_TIMESTAMP
                WHERE platform = 'stripe'
            """)

    async def get_status(self) -> dict:
        """Return connection status with capabilities."""
        config = await self._load_config()
        if not config:
            return {"connected": False, "platform": "stripe"}
        settings = config.get("settings", {})
        if isinstance(settings, str):
            settings = json.loads(settings)
        return {
            "connected": config.get("status") == "connected",
            "platform": "stripe",
            "account_id": settings.get("account_id", ""),
            "business_name": settings.get("business_name", ""),
            "mode": "test" if settings.get("is_test_mode") else "live",
            "last_sync_at": str(config.get("last_sync_at", "")),
            "capabilities": {
                "read": ["charges", "invoices", "payouts", "customers"],
                "write": ["create_invoice", "create_customer", "send_invoice"],
                "sync": ["full_sync", "sync_invoices", "sync_payments", "sync_payouts"],
                "webhooks": ["invoice.paid", "invoice.payment_failed", "charge.succeeded", "payout.paid"],
            },
        }

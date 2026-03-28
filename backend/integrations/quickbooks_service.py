"""
QuickBooks Online Integration Service
Bi-directional sync of invoices, bills, customers, and vendors between GP and QBO.
"""

import aiohttp
import json
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional


QBO_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

import os
IS_QBO_SANDBOX = os.getenv("QBO_ENV", "sandbox").lower() == "sandbox"
QBO_API_BASE = (
    "https://sandbox-quickbooks.api.intuit.com/v3/company"
    if IS_QBO_SANDBOX
    else "https://quickbooks.api.intuit.com/v3/company"
)
QBO_SCOPE = "com.intuit.quickbooks.accounting"


class QuickBooksService:
    """Async service for QuickBooks Online API integration."""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._config = None

    # ── Config Management ────────────────────────────────────────────────

    async def _load_config(self):
        """Load QBO config from integration_configs table."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM integration_configs WHERE platform = 'quickbooks'"
            )
            if row:
                self._config = dict(row)
                if isinstance(self._config.get("settings"), str):
                    self._config["settings"] = json.loads(self._config["settings"])
            return self._config

    async def _save_config(self, settings: dict, status: str = "connected"):
        """Persist QBO config to integration_configs table."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO integration_configs (id, platform, status, settings, updated_at)
                VALUES ('qbo-primary', 'quickbooks', $1, $2::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    settings = $2::jsonb,
                    status = $1,
                    updated_at = CURRENT_TIMESTAMP
            """, status, json.dumps(settings))
        self._config = {"settings": settings, "status": status}

    # ── OAuth Flow ───────────────────────────────────────────────────────

    def get_auth_url(self, client_id: str, redirect_uri: str, state: str = "") -> str:
        """Generate the QBO OAuth authorization URL."""
        import urllib.parse
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": QBO_SCOPE,
            "state": state or f"gp-{int(time.time())}",
        }
        return f"{QBO_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code(
        self, code: str, client_id: str, client_secret: str, redirect_uri: str
    ) -> dict:
        """Exchange authorization code for access + refresh tokens."""
        import base64
        auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                QBO_TOKEN_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_header}",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            ) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    return {"success": False, "error": f"Token exchange failed: {error_body}"}

                token_data = await resp.json()
                settings = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "access_token": token_data["access_token"],
                    "refresh_token": token_data["refresh_token"],
                    "token_expires_at": time.time() + token_data.get("expires_in", 3600),
                    "realm_id": token_data.get("realmId", ""),
                }
                await self._save_config(settings)
                return {"success": True, "realm_id": settings["realm_id"]}

    async def refresh_token(self) -> bool:
        """Refresh the OAuth access token using the refresh token."""
        if not self._config:
            await self._load_config()
        if not self._config:
            return False

        settings = self._config["settings"]
        import base64
        auth_header = base64.b64encode(
            f"{settings['client_id']}:{settings['client_secret']}".encode()
        ).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                QBO_TOKEN_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_header}",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": settings["refresh_token"],
                },
            ) as resp:
                if resp.status != 200:
                    return False
                token_data = await resp.json()
                settings["access_token"] = token_data["access_token"]
                settings["refresh_token"] = token_data["refresh_token"]
                settings["token_expires_at"] = time.time() + token_data.get("expires_in", 3600)
                await self._save_config(settings)
                return True

    async def _ensure_token(self):
        """Ensure we have a valid access token, refreshing if needed."""
        if not self._config:
            await self._load_config()
        if not self._config:
            raise ValueError("QuickBooks not connected. Run connect flow first.")

        settings = self._config["settings"]
        if time.time() > settings.get("token_expires_at", 0) - 300:
            refreshed = await self.refresh_token()
            if not refreshed:
                raise ValueError("Failed to refresh QBO token. Re-authorization required.")

    async def _qbo_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make an authenticated request to the QBO API."""
        await self._ensure_token()
        settings = self._config["settings"]
        realm_id = settings["realm_id"]
        url = f"{QBO_API_BASE}/{realm_id}/{endpoint}"

        headers = {
            "Authorization": f"Bearer {settings['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers) as resp:
                    return await resp.json()
            elif method == "POST":
                async with session.post(url, headers=headers, json=data) as resp:
                    return await resp.json()

    # ── Sync Operations ──────────────────────────────────────────────────

    async def sync_invoices(self, days_back: int = 7) -> dict:
        """Pull invoices from QBO and upsert into transactions table."""
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
        query = f"SELECT * FROM Invoice WHERE MetaData.LastUpdatedTime > '{since}'"
        result = await self._qbo_request("GET", f"query?query={urllib.parse.quote(query)}")

        invoices = result.get("QueryResponse", {}).get("Invoice", [])
        synced = 0

        async with self.db_pool.acquire() as conn:
            for inv in invoices:
                inv_id = f"QBO-{inv['Id']}"
                entity_name = inv.get("CustomerRef", {}).get("name", "Unknown")
                amount = float(inv.get("TotalAmt", 0))
                date_str = inv.get("TxnDate", "")
                due_date = inv.get("DueDate", "")
                balance = float(inv.get("Balance", 0))
                status = "pending" if balance > 0 else "paid"

                # Build line items
                items = []
                for line in inv.get("Line", []):
                    if line.get("DetailType") == "SalesItemLineDetail":
                        items.append({
                            "description": line.get("Description", ""),
                            "amount": float(line.get("Amount", 0)),
                        })

                await conn.execute("""
                    INSERT INTO transactions (
                        id, type, entity_name, amount, date, due_date, status,
                        items, metadata, created_at, updated_at
                    ) VALUES ($1, 'receivable', $2, $3, $4::date, $5::date, $6,
                              $7::jsonb, $8::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        amount = EXCLUDED.amount,
                        items = EXCLUDED.items,
                        updated_at = CURRENT_TIMESTAMP
                """, inv_id, entity_name, amount,
                    date_str or None, due_date or None, status,
                    json.dumps(items), json.dumps({"source": "quickbooks", "qbo_id": inv["Id"]}))
                synced += 1

        # Update last sync timestamp
        await self._update_sync_time()
        return {"success": True, "synced": synced, "source": "quickbooks"}

    async def sync_bills(self, days_back: int = 7) -> dict:
        """Pull bills (AP) from QBO and upsert into transactions table."""
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
        query = f"SELECT * FROM Bill WHERE MetaData.LastUpdatedTime > '{since}'"
        result = await self._qbo_request("GET", f"query?query={urllib.parse.quote(query)}")

        bills = result.get("QueryResponse", {}).get("Bill", [])
        synced = 0

        async with self.db_pool.acquire() as conn:
            for bill in bills:
                bill_id = f"QBO-BILL-{bill['Id']}"
                entity_name = bill.get("VendorRef", {}).get("name", "Unknown")
                amount = float(bill.get("TotalAmt", 0))
                date_str = bill.get("TxnDate", "")
                due_date = bill.get("DueDate", "")
                balance = float(bill.get("Balance", 0))
                status = "pending" if balance > 0 else "paid"

                await conn.execute("""
                    INSERT INTO transactions (
                        id, type, entity_name, amount, date, due_date, status,
                        metadata, created_at, updated_at
                    ) VALUES ($1, 'payable', $2, $3, $4::date, $5::date, $6,
                              $7::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        amount = EXCLUDED.amount,
                        updated_at = CURRENT_TIMESTAMP
                """, bill_id, entity_name, amount,
                    date_str or None, due_date or None, status,
                    json.dumps({"source": "quickbooks", "qbo_bill_id": bill["Id"]}))
                synced += 1

        await self._update_sync_time()
        return {"success": True, "synced": synced, "source": "quickbooks"}

    async def sync_customers(self) -> dict:
        """Pull QBO customers → upsert into client_patterns."""
        result = await self._qbo_request("GET", f"query?query={urllib.parse.quote('SELECT * FROM Customer')}")
        customers = result.get("QueryResponse", {}).get("Customer", [])
        synced = 0

        async with self.db_pool.acquire() as conn:
            for cust in customers:
                client_id = f"QBO-{cust['Id']}"
                name = cust.get("DisplayName", cust.get("CompanyName", "Unknown"))
                email = cust.get("PrimaryEmailAddr", {}).get("Address", "")

                await conn.execute("""
                    INSERT INTO client_patterns (client_id, client_name, created_at, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (client_id) DO UPDATE SET
                        client_name = EXCLUDED.client_name,
                        updated_at = CURRENT_TIMESTAMP
                """, client_id, name)
                synced += 1

        return {"success": True, "synced": synced, "type": "customers"}

    async def sync_vendors(self) -> dict:
        """Pull QBO vendors → upsert into vendor_patterns."""
        result = await self._qbo_request("GET", f"query?query={urllib.parse.quote('SELECT * FROM Vendor')}")
        vendors = result.get("QueryResponse", {}).get("Vendor", [])
        synced = 0

        async with self.db_pool.acquire() as conn:
            for vendor in vendors:
                vendor_id = f"QBO-{vendor['Id']}"
                name = vendor.get("DisplayName", vendor.get("CompanyName", "Unknown"))

                await conn.execute("""
                    INSERT INTO vendor_patterns (vendor_id, vendor_name, created_at, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (vendor_id) DO UPDATE SET
                        vendor_name = EXCLUDED.vendor_name,
                        updated_at = CURRENT_TIMESTAMP
                """, vendor_id, name)
                synced += 1

        return {"success": True, "synced": synced, "type": "vendors"}

    async def push_invoice(self, invoice_id: str) -> dict:
        """Create a QBO invoice from a GP transaction record."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM transactions WHERE id = $1 AND type = 'receivable'",
                invoice_id,
            )
            if not row:
                return {"success": False, "error": f"Invoice {invoice_id} not found"}

        current_meta = json.loads(row.get("metadata") or "{}")
        if "qbo_invoice_id" in current_meta:
            return {"success": True, "qbo_invoice_id": current_meta["qbo_invoice_id"], "message": "Idempotent: Invoice already synced to QBO"}

        items_data = row["items"] if isinstance(row["items"], list) else json.loads(row["items"] or "[]")
        lines = []
        for item in items_data:
            lines.append({
                "Amount": float(item.get("amount", row["amount"])),
                "DetailType": "SalesItemLineDetail",
                "SalesItemLineDetail": {
                    "ItemRef": {"value": "1", "name": "Services"},
                },
                "Description": item.get("description", f"Invoice {invoice_id}"),
            })

        if not lines:
            lines = [{
                "Amount": float(row["amount"]),
                "DetailType": "SalesItemLineDetail",
                "SalesItemLineDetail": {"ItemRef": {"value": "1", "name": "Services"}},
                "Description": f"Invoice {invoice_id}",
            }]

        qbo_invoice = {"Line": lines}

        # Try to find a QBO customer reference
        if row.get("entity_id"):
            async with self.db_pool.acquire() as conn:
                client = await conn.fetchrow(
                    "SELECT * FROM client_patterns WHERE client_id = $1", row["entity_id"]
                )
                # If there's a QBO customer ID stored, use it
                # For now, just include the display name
                qbo_invoice["CustomerRef"] = {"name": row["entity_name"]}

        result = await self._qbo_request("POST", "invoice", qbo_invoice)
        qbo_id = result.get("Invoice", {}).get("Id")
        if qbo_id:
            async with self.db_pool.acquire() as conn:
                current_meta = json.loads(row.get("metadata") or "{}")
                current_meta["qbo_invoice_id"] = qbo_id
                await conn.execute(
                    "UPDATE transactions SET metadata = $1::jsonb WHERE id = $2",
                    json.dumps(current_meta), invoice_id,
                )
            return {"success": True, "qbo_invoice_id": qbo_id}
        return {"success": False, "error": "Failed to create QBO invoice", "response": result}

    async def sync_payments(self, days_back: int = 7) -> dict:
        """Pull QBO Payment objects (customer payments received) → mark invoices paid."""
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
        query = f"SELECT * FROM Payment WHERE MetaData.LastUpdatedTime > '{since}'"
        result = await self._qbo_request("GET", f"query?query={urllib.parse.quote(query)}")

        payments = result.get("QueryResponse", {}).get("Payment", [])
        reconciled = 0

        async with self.db_pool.acquire() as conn:
            for pmt in payments:
                pmt_amount = float(pmt.get("TotalAmt", 0))
                pmt_date = pmt.get("TxnDate", "")
                customer = pmt.get("CustomerRef", {}).get("name", "Unknown")

                # Find linked invoices from Line items
                for line in pmt.get("Line", []):
                    linked_txns = line.get("LinkedTxn", [])
                    for linked in linked_txns:
                        if linked.get("TxnType") == "Invoice":
                            inv_id = f"QBO-{linked['TxnId']}"
                            await conn.execute("""
                                UPDATE transactions
                                SET status = 'paid',
                                    metadata = jsonb_set(
                                        COALESCE(metadata, '{}'),
                                        '{payment_id}',
                                        $1::jsonb
                                    ),
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = $2 AND status != 'paid'
                            """, json.dumps(pmt["Id"]), inv_id)
                            reconciled += 1

        return {"success": True, "synced": reconciled, "total_payments": len(payments), "source": "quickbooks"}

    async def full_sync(self, days_back: int = 7) -> dict:
        """Run a complete QBO sync: invoices + bills + customers + vendors + payments."""
        results = {}

        try:
            results["invoices"] = await self.sync_invoices(days_back=days_back)
        except Exception as e:
            results["invoices"] = {"success": False, "error": str(e)}

        try:
            results["bills"] = await self.sync_bills(days_back=days_back)
        except Exception as e:
            results["bills"] = {"success": False, "error": str(e)}

        try:
            results["customers"] = await self.sync_customers()
        except Exception as e:
            results["customers"] = {"success": False, "error": str(e)}

        try:
            results["vendors"] = await self.sync_vendors()
        except Exception as e:
            results["vendors"] = {"success": False, "error": str(e)}

        try:
            results["payments"] = await self.sync_payments(days_back=days_back)
        except Exception as e:
            results["payments"] = {"success": False, "error": str(e)}

        return {
            "success": all(r.get("success") for r in results.values()),
            "results": results,
            "source": "quickbooks",
        }

    async def _update_sync_time(self):
        """Update the last_sync_at timestamp."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE integration_configs SET last_sync_at = CURRENT_TIMESTAMP
                WHERE platform = 'quickbooks'
            """)

    async def process_webhook(self, payload: dict) -> dict:
        """Process inbound QBO webhooks to update local ledger state."""
        processed = 0
        events = payload.get("eventNotifications", [])
        
        async with self.db_pool.acquire() as conn:
            for event in events:
                data_event = event.get("dataChangeEvent", {})
                for entity in data_event.get("entities", []):
                    entity_name = entity.get("name")
                    entity_id = entity.get("id")
                    operation = entity.get("operation")
                    
                    if entity_name == "Payment" and operation in ["Create", "Update"]:
                        # Fetch the payment to see which invoices it paid
                        query = f"SELECT * FROM Payment WHERE Id = '{entity_id}'"
                        result = await self._qbo_request("GET", f"query?query={urllib.parse.quote(query)}")
                        payments = result.get("QueryResponse", {}).get("Payment", [])
                        
                        for pmt in payments:
                            for line in pmt.get("Line", []):
                                linked_txns = line.get("LinkedTxn", [])
                                for linked in linked_txns:
                                    if linked.get("TxnType") == "Invoice":
                                        inv_id = f"QBO-{linked['TxnId']}"
                                        await conn.execute("""
                                            UPDATE transactions
                                            SET status = 'paid',
                                            metadata = jsonb_set(
                                                COALESCE(metadata, '{}'),
                                                '{payment_id}',
                                                $1::jsonb
                                            ),
                                            updated_at = CURRENT_TIMESTAMP
                                            WHERE id = $2 AND status != 'paid'
                                        """, json.dumps(pmt["Id"]), inv_id)
                                        processed += 1

        return {"success": True, "processed_events": processed, "source": "quickbooks_webhook"}

    async def get_status(self) -> dict:
        """Return connection status with capabilities."""
        config = await self._load_config()
        if not config:
            return {"connected": False, "platform": "quickbooks"}
        return {
            "connected": config.get("status") == "connected",
            "platform": "quickbooks",
            "last_sync_at": str(config.get("last_sync_at", "")),
            "realm_id": config.get("settings", {}).get("realm_id", ""),
            "capabilities": {
                "read": ["Invoice", "Bill", "Customer", "Vendor", "Payment"],
                "write": ["Invoice"],
                "sync": ["full_sync", "sync_invoices", "sync_bills", "sync_customers", "sync_vendors", "sync_payments"],
            },
        }

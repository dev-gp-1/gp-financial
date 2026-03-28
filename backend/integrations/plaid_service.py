"""
Plaid Integration Service
Universal bank feeds from any US bank, multi-bank reconciliation, and balance checking.

Auth: Client ID + Secret + public_token exchange (Link flow)
Sandbox: Free with test credentials (user_good / pass_good)

Docs: https://plaid.com/docs/api/
"""

import aiohttp
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Optional


PLAID_SANDBOX_URL = "https://sandbox.plaid.com"
PLAID_DEVELOPMENT_URL = "https://development.plaid.com"
PLAID_PRODUCTION_URL = "https://production.plaid.com"


class PlaidService:
    """Async service for Plaid API integration — universal bank feeds."""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._config = None

    # ── Config Management ────────────────────────────────────────────────

    async def _load_config(self):
        """Load Plaid config from integration_configs table."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM integration_configs WHERE platform = 'plaid'"
            )
            if row:
                self._config = dict(row)
                if isinstance(self._config.get("settings"), str):
                    self._config["settings"] = json.loads(self._config["settings"])
            return self._config

    async def _save_config(self, settings: dict, status: str = "connected"):
        """Persist Plaid config to integration_configs table."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO integration_configs (id, platform, status, settings, updated_at)
                VALUES ('plaid-primary', 'plaid', $1, $2::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    settings = $2::jsonb,
                    status = $1,
                    updated_at = CURRENT_TIMESTAMP
            """, status, json.dumps(settings))
        self._config = {"settings": settings, "status": status}

    # ── Connection (Link Flow) ───────────────────────────────────────────

    def _get_base_url(self) -> str:
        """Return correct Plaid URL based on environment."""
        if not self._config:
            return PLAID_SANDBOX_URL
        env = self._config["settings"].get("environment", "sandbox")
        return {
            "sandbox": PLAID_SANDBOX_URL,
            "development": PLAID_DEVELOPMENT_URL,
            "production": PLAID_PRODUCTION_URL,
        }.get(env, PLAID_SANDBOX_URL)

    async def connect(self, client_id: str, secret: str, environment: str = "sandbox") -> dict:
        """Store Plaid credentials. Actual bank linking happens via Link UI + public_token exchange."""
        settings = {
            "client_id": client_id,
            "secret": secret,
            "environment": environment,
            "access_tokens": [],  # Populated after link_token exchange
            "item_ids": [],  # Plaid Item IDs (one per bank connection)
        }
        await self._save_config(settings)
        return {
            "success": True,
            "environment": environment,
            "message": "Credentials saved. Use create_link_token to start bank linking.",
        }

    async def _plaid_request(self, endpoint: str, data: dict = None) -> dict:
        """Make an authenticated request to the Plaid API.

        Plaid uses POST for all endpoints with client_id + secret in the body.
        """
        if not self._config:
            await self._load_config()
        if not self._config:
            raise ValueError("Plaid not connected. Run connect flow first.")

        settings = self._config["settings"]
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint}"

        payload = {
            "client_id": settings["client_id"],
            "secret": settings["secret"],
        }
        if data:
            payload.update(data)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers={"Content-Type": "application/json"}, json=payload
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    return {"error": f"Plaid API error: {resp.status}", "body": body}
                return body

    # ── Link Token (for frontend) ────────────────────────────────────────

    async def create_link_token(self, user_id: str = "ghost-protocol-user") -> dict:
        """Create a Link token for the frontend Plaid Link UI.

        The frontend uses this token to open the Plaid Link UI where the user
        connects their bank account. After linking, the frontend sends back
        a public_token which we exchange for an access_token.
        """
        result = await self._plaid_request("link/token/create", {
            "user": {"client_user_id": user_id},
            "client_name": "Ghost Protocol",
            "products": ["transactions"],
            "country_codes": ["US"],
            "language": "en",
        })
        if "error" in result:
            return {"success": False, **result}

        return {
            "success": True,
            "link_token": result.get("link_token", ""),
            "expiration": result.get("expiration", ""),
        }

    async def exchange_public_token(self, public_token: str) -> dict:
        """Exchange a public_token from Plaid Link for a persistent access_token."""
        result = await self._plaid_request("item/public_token/exchange", {
            "public_token": public_token,
        })
        if "error" in result:
            return {"success": False, **result}

        access_token = result.get("access_token", "")
        item_id = result.get("item_id", "")

        # Store the new access token
        settings = self._config["settings"]
        if access_token not in settings.get("access_tokens", []):
            settings.setdefault("access_tokens", []).append(access_token)
        if item_id not in settings.get("item_ids", []):
            settings.setdefault("item_ids", []).append(item_id)
        await self._save_config(settings)

        return {
            "success": True,
            "item_id": item_id,
            "access_token_stored": True,
            "total_linked_banks": len(settings["access_tokens"]),
        }

    # ── Accounts & Balances ──────────────────────────────────────────────

    async def get_accounts(self, access_token: str = None) -> dict:
        """Get all accounts for a linked bank."""
        token = access_token or self._get_primary_token()
        if not token:
            return {"success": False, "error": "No bank linked. Complete Plaid Link flow first."}

        result = await self._plaid_request("accounts/get", {"access_token": token})
        if "error" in result:
            return {"success": False, **result}

        accounts = result.get("accounts", [])
        return {
            "success": True,
            "accounts": [
                {
                    "account_id": a["account_id"],
                    "name": a.get("name", ""),
                    "official_name": a.get("official_name", ""),
                    "type": a.get("type", ""),
                    "subtype": a.get("subtype", ""),
                    "mask": a.get("mask", ""),
                    "current_balance": a.get("balances", {}).get("current"),
                    "available_balance": a.get("balances", {}).get("available"),
                    "currency": a.get("balances", {}).get("iso_currency_code", "USD"),
                }
                for a in accounts
            ],
        }

    async def get_balances(self, access_token: str = None) -> dict:
        """Get real-time balances for all linked accounts."""
        token = access_token or self._get_primary_token()
        if not token:
            return {"success": False, "error": "No bank linked."}

        result = await self._plaid_request("accounts/balance/get", {"access_token": token})
        if "error" in result:
            return {"success": False, **result}

        accounts = result.get("accounts", [])
        return {
            "success": True,
            "balances": [
                {
                    "account_id": a["account_id"],
                    "name": a.get("name", ""),
                    "current": a.get("balances", {}).get("current"),
                    "available": a.get("balances", {}).get("available"),
                }
                for a in accounts
            ],
        }

    # ── Transaction Sync ─────────────────────────────────────────────────

    async def sync_transactions(self, days_back: int = 7, access_token: str = None) -> dict:
        """Pull transactions via Plaid's transaction sync endpoint and write to GP ledger."""
        token = access_token or self._get_primary_token()
        if not token:
            return {"success": False, "error": "No bank linked."}

        # Use transactions/sync for incremental sync
        cursor = self._config["settings"].get("sync_cursor", "")
        all_added = []
        has_more = True

        while has_more:
            payload = {"access_token": token}
            if cursor:
                payload["cursor"] = cursor
            result = await self._plaid_request("transactions/sync", payload)
            if "error" in result:
                return {"success": False, **result}

            added = result.get("added", [])
            all_added.extend(added)
            cursor = result.get("next_cursor", "")
            has_more = result.get("has_more", False)

        # Save cursor for next incremental sync
        settings = self._config["settings"]
        settings["sync_cursor"] = cursor
        await self._save_config(settings)

        # Write transactions to GP ledger
        synced = 0
        async with self.db_pool.acquire() as conn:
            for txn in all_added:
                txn_id = f"PLAID-{txn.get('transaction_id', '')}"
                amount = abs(txn.get("amount", 0))
                # Plaid: positive = debit (money out), negative = credit (money in)
                txn_type = "payable" if txn.get("amount", 0) > 0 else "receivable"
                date_str = txn.get("date", "")
                merchant = txn.get("merchant_name") or txn.get("name", "Unknown")
                category = ", ".join(txn.get("category", []))

                await conn.execute("""
                    INSERT INTO transactions (
                        id, type, entity_name, amount, date, status,
                        metadata, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5::date, 'paid',
                              $6::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, txn_id, txn_type, merchant, amount,
                    date_str if date_str else None,
                    json.dumps({
                        "source": "plaid",
                        "plaid_txn_id": txn.get("transaction_id", ""),
                        "account_id": txn.get("account_id", ""),
                        "category": category,
                        "pending": txn.get("pending", False),
                    }))
                synced += 1

        await self._update_sync_time()
        return {
            "success": True,
            "synced": synced,
            "total_new": len(all_added),
            "source": "plaid",
        }

    # ── Full Sync ────────────────────────────────────────────────────────

    async def full_sync(self, days_back: int = 7) -> dict:
        """Run a complete Plaid sync: transactions + balances across all linked banks."""
        results = {}

        try:
            results["transactions"] = await self.sync_transactions(days_back=days_back)
        except Exception as e:
            results["transactions"] = {"success": False, "error": str(e)}

        try:
            results["balances"] = await self.get_balances()
        except Exception as e:
            results["balances"] = {"success": False, "error": str(e)}

        return {
            "success": all(r.get("success") for r in results.values()),
            "results": results,
            "source": "plaid",
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_primary_token(self) -> Optional[str]:
        """Get the first stored access token."""
        if not self._config:
            return None
        tokens = self._config["settings"].get("access_tokens", [])
        return tokens[0] if tokens else None

    async def _update_sync_time(self):
        """Update the last_sync_at timestamp."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE integration_configs SET last_sync_at = CURRENT_TIMESTAMP
                WHERE platform = 'plaid'
            """)

    async def get_status(self) -> dict:
        """Return connection status with capabilities."""
        config = await self._load_config()
        if not config:
            return {"connected": False, "platform": "plaid"}
        settings = config.get("settings", {})
        if isinstance(settings, str):
            settings = json.loads(settings)
        return {
            "connected": config.get("status") == "connected",
            "platform": "plaid",
            "environment": settings.get("environment", "sandbox"),
            "linked_banks": len(settings.get("access_tokens", [])),
            "last_sync_at": str(config.get("last_sync_at", "")),
            "capabilities": {
                "read": ["accounts", "balances", "transactions", "categories"],
                "write": [],  # Plaid is read-only
                "sync": ["full_sync", "sync_transactions", "get_balances"],
                "link": ["create_link_token", "exchange_public_token"],
            },
        }

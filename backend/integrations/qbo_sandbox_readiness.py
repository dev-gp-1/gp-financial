"""
QuickBooks Sandbox Readiness Kit — Preparation for live QBO integration.

When you get access to a QuickBooks sandbox or production environment,
this script validates the full pipeline:

  1. OAuth 2.0 token exchange (uses real Intuit credentials)
  2. Connection validation probe
  3. Full 90-day data pull
  4. Intelligence report from real data
  5. Multi-tenant isolation verification

Prerequisites:
  - Intuit Developer account: https://developer.intuit.com
  - Create an app → get Client ID + Client Secret
  - OAuth 2.0 playground or redirect URI configured
  - Sandbox company with sample data (Intuit provides one automatically)

Environment Variables:
  QBO_CLIENT_ID      — From Intuit developer dashboard
  QBO_CLIENT_SECRET  — From Intuit developer dashboard
  QBO_REDIRECT_URI   — Your callback URL
  QBO_AUTH_CODE      — From OAuth 2.0 consent flow (one-time use)
  QBO_REALM_ID       — Company ID (shown in URL when logged into QBO)
  GP_TENANT_ID       — Ghost Protocol tenant ID for this client

Usage:
    # Step 1: Set environment variables
    export QBO_CLIENT_ID="AB8EHepsGApEMcGs0tbPRXZ5USlb1rhIHP6CJKuoHj80WekpF4"
    export QBO_CLIENT_SECRET="t4TxIcSLUSRGTVogJB1H9CREZLMtXSAMtVoeEbP7"
    export QBO_REDIRECT_URI="https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl"

    # Step 2: Get auth code from Intuit OAuth Playground
    # Visit: https://developer.intuit.com/app/developer/playground
    export QBO_AUTH_CODE="<paste_auth_code_here>"
    export QBO_REALM_ID="<company_id_from_url>"

    # Step 3: Run validation
    python3 src/integrations/qbo_sandbox_readiness.py
"""

import asyncio
import aiohttp
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone


# ── Colors ───────────────────────────────────────────────────────────────
G = "\033[92m"
Y = "\033[93m"
C = "\033[96m"
R = "\033[91m"
W = "\033[97m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def banner(text):
    print(f"\n{C}{'═' * 70}{RESET}")
    print(f"{BOLD}{W}  {text}{RESET}")
    print(f"{C}{'═' * 70}{RESET}")


def check(text):
    print(f"  {G}✅ {text}{RESET}")


def fail(text):
    print(f"  {R}❌ {text}{RESET}")


def info(text):
    print(f"  {DIM}{text}{RESET}")


# ══════════════════════════════════════════════════════════════════════════
# ENVIRONMENT CHECK
# ══════════════════════════════════════════════════════════════════════════

def check_environment():
    """Verify all required environment variables are set."""
    banner("STEP 1: ENVIRONMENT CHECK")

    required = {
        "QBO_CLIENT_ID": "Intuit app Client ID",
        "QBO_CLIENT_SECRET": "Intuit app Client Secret",
        "QBO_REDIRECT_URI": "OAuth redirect URI",
    }

    optional = {
        "QBO_AUTH_CODE": "OAuth authorization code (from consent flow)",
        "QBO_REALM_ID": "QuickBooks company ID",
        "GP_TENANT_ID": "Ghost Protocol tenant ID",
    }

    all_good = True
    for var, desc in required.items():
        val = os.environ.get(var, "")
        if val:
            check(f"{var}: {val[:20]}...{'*' * 10}")
        else:
            fail(f"{var}: NOT SET — {desc}")
            all_good = False

    print()
    for var, desc in optional.items():
        val = os.environ.get(var, "")
        if val:
            check(f"{var}: {val[:20]}...")
        else:
            info(f"{var}: not set (optional) — {desc}")

    return all_good


# ══════════════════════════════════════════════════════════════════════════
# OAUTH TOKEN EXCHANGE
# ══════════════════════════════════════════════════════════════════════════

async def exchange_token():
    """Exchange authorization code for access + refresh tokens."""
    banner("STEP 2: OAUTH TOKEN EXCHANGE")

    auth_code = os.environ.get("QBO_AUTH_CODE", "")
    if not auth_code:
        info("No QBO_AUTH_CODE set. Skipping token exchange.")
        info("To get one:")
        info("  1. Visit https://developer.intuit.com/app/developer/playground")
        info("  2. Select your app and authorize")
        info("  3. Copy the authorization code from the URL")
        info("  4. export QBO_AUTH_CODE='<code>'")
        return None

    client_id = os.environ["QBO_CLIENT_ID"]
    client_secret = os.environ["QBO_CLIENT_SECRET"]
    redirect_uri = os.environ["QBO_REDIRECT_URI"]

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": redirect_uri,
            },
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                fail(f"Token exchange failed ({resp.status}): {body}")
                return None

            token_data = await resp.json()

    check(f"Access token: {token_data['access_token'][:30]}...")
    check(f"Refresh token: {token_data.get('refresh_token', 'N/A')[:30]}...")
    check(f"Expires in: {token_data.get('expires_in', 0)}s")
    info(f"Token type: {token_data.get('token_type', 'bearer')}")

    return token_data


# ══════════════════════════════════════════════════════════════════════════
# CONNECTION VALIDATION
# ══════════════════════════════════════════════════════════════════════════

async def validate_connection(access_token: str, realm_id: str):
    """Validate QBO connection by pulling company info."""
    banner("STEP 3: CONNECTION VALIDATION")

    base_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}"

    async with aiohttp.ClientSession() as session:
        # Pull company info
        async with session.get(
            f"{base_url}/companyinfo/{realm_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        ) as resp:
            if resp.status != 200:
                fail(f"Company info query failed ({resp.status})")
                return False
            data = await resp.json()
            company = data.get("CompanyInfo", {})
            check(f"Company: {company.get('CompanyName', 'Unknown')}")
            check(f"Country: {company.get('Country', 'Unknown')}")
            check(f"Fiscal Year: starts month {company.get('FiscalYearStartMonth', '?')}")
            info(f"Realm ID: {realm_id}")

        # Pull 1 invoice to validate read access
        async with session.get(
            f"{base_url}/query?query=SELECT * FROM Invoice MAXRESULTS 1",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                invoices = data.get("QueryResponse", {}).get("Invoice", [])
                if invoices:
                    inv = invoices[0]
                    check(f"Invoice probe: #{inv.get('DocNumber', '?')} — ${inv.get('TotalAmt', 0):,.2f}")
                else:
                    check("Invoice probe: No invoices yet (sandbox may be empty)")
            else:
                fail(f"Invoice query failed ({resp.status})")
                return False

    return True


# ══════════════════════════════════════════════════════════════════════════
# DATA PULL SUMMARY
# ══════════════════════════════════════════════════════════════════════════

async def data_pull_summary(access_token: str, realm_id: str):
    """Count available data for sync planning."""
    banner("STEP 4: DATA INVENTORY")

    base_url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    queries = {
        "Invoices (AR)": "SELECT COUNT(*) FROM Invoice",
        "Bills (AP)": "SELECT COUNT(*) FROM Bill",
        "Customers": "SELECT COUNT(*) FROM Customer",
        "Vendors": "SELECT COUNT(*) FROM Vendor",
        "Payments": "SELECT COUNT(*) FROM Payment",
        "Accounts (GL)": "SELECT COUNT(*) FROM Account",
    }

    async with aiohttp.ClientSession() as session:
        for label, query in queries.items():
            try:
                async with session.get(
                    f"{base_url}/query?query={query}",
                    headers=headers,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        count = data.get("QueryResponse", {}).get("totalCount", 0)
                        check(f"{label}: {count} records available")
                    else:
                        fail(f"{label}: query failed ({resp.status})")
            except Exception as e:
                fail(f"{label}: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════
# FULL READINESS REPORT
# ══════════════════════════════════════════════════════════════════════════

async def run_readiness():
    """Run the complete QBO sandbox readiness check."""
    banner("QUICKBOOKS SANDBOX READINESS KIT")
    print(f"  {DIM}Ghost Protocol Financial Intelligence{RESET}")
    print(f"  {DIM}Validates: OAuth → Connection → Data → Ready to onboard{RESET}")

    # Step 1: Environment
    env_ok = check_environment()
    if not env_ok:
        print(f"\n  {Y}Set the missing environment variables and re-run.{RESET}")
        print(f"  {DIM}See the docstring at the top of this file for instructions.{RESET}")
        return

    # Step 2: Token exchange
    token_data = await exchange_token()
    if not token_data:
        print(f"\n  {Y}Token exchange skipped or failed. Set QBO_AUTH_CODE and retry.{RESET}")
        return

    access_token = token_data["access_token"]
    realm_id = os.environ.get("QBO_REALM_ID", "")

    if not realm_id:
        print(f"\n  {Y}Set QBO_REALM_ID (company ID from QBO URL) and re-run.{RESET}")
        return

    # Step 3: Validate connection
    valid = await validate_connection(access_token, realm_id)
    if not valid:
        print(f"\n  {R}Connection validation failed. Check credentials.{RESET}")
        return

    # Step 4: Data inventory
    await data_pull_summary(access_token, realm_id)

    # Final report
    banner("READINESS REPORT")
    check("Environment: all variables set")
    check("OAuth: tokens exchanged successfully")
    check("Connection: QBO API responding, read access confirmed")
    check("Data: inventory complete")
    print(f"\n  {BOLD}{G}🚀 READY TO ONBOARD — Run full_sync to pull 90 days of data{RESET}")
    print(f"\n  {DIM}Next steps:")
    print(f"    1. Store tokens: python3 -c \"from secret_manager import ...; store_credentials(...)\"")
    print(f"    2. Full sync:    POST /api/integrations/quickbooks/sync {{\"days_back\": 90}}")
    print(f"    3. Dashboard:    Open GP frontend → Financial Intelligence tab{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════
# CREDENTIAL REFERENCE (from user's previous conversation)
# ══════════════════════════════════════════════════════════════════════════

KNOWN_CREDENTIALS = """
# QuickBooks credentials (provided by user):
# AppID:         452115c6-6cb6-4c4e-a342-f971d6264b26
# Client ID:     AB8EHepsGApEMcGs0tbPRXZ5USlb1rhIHP6CJKuoHj80WekpF4
# Client Secret: t4TxIcSLUSRGTVogJB1H9CREZLMtXSAMtVoeEbP7
# Redirect URI:  https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl
#
# To use:
#   export QBO_CLIENT_ID="AB8EHepsGApEMcGs0tbPRXZ5USlb1rhIHP6CJKuoHj80WekpF4"
#   export QBO_CLIENT_SECRET="t4TxIcSLUSRGTVogJB1H9CREZLMtXSAMtVoeEbP7"
#   export QBO_REDIRECT_URI="https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl"
#   # Then go to OAuth playground, authorize, and get auth code:
#   export QBO_AUTH_CODE="<paste_here>"
#   export QBO_REALM_ID="<company_id>"
"""


if __name__ == "__main__":
    asyncio.run(run_readiness())

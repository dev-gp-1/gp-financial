"""
Financial Enrichment Service
============================
Uses Gemini 3.1 Pro to:
1. Normalize counterparty names (e.g. "GOOGLE *GCP" -> "Google Cloud")
2. Categorize transactions (e.g. "Software", "Travel", "Payroll")
3. Assign GL codes based on category
4. Tag with tenant_id for multi-tenant reporting
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from agents.agent_loop import AgentLoop
except ImportError:
    # Handle if run from different path
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from agents.agent_loop import AgentLoop

logger = logging.getLogger("tron.financial_enrichment")

# ─── Configuration ────────────────────────────────────────────────────────────

GL_MAP = {
    "Software / SaaS": "6010",
    "Infrastructure / Cloud": "6020",
    "Payroll / Subcontractors": "5010",
    "Office Supplies": "6100",
    "Travel / Meals": "6200",
    "Marketing / Advertising": "6300",
    "Rent / Utilities": "6400",
    "Professional Services": "6500",
    "Taxes / Fees": "7000",
    "Other Expense": "9999",
    "Revenue / Sales": "4000",
    "Refund / Credit": "4100"
}

TENANT_RULES = {
    "Ghost Protocol": ["GAA", "GHOST", "DEAN BARRETT", "AMZN MKTP"],
    "Managed Property A": ["COMCAST", "CONED", "VERIZON"],
    # Add more rules as needed
}

DEFAULT_TENANT = "ghost-protocol"

# ─── Enrichment Service ───────────────────────────────────────────────────────

class FinancialEnrichmentService:
    """Service to clean and enrich financial data before BigQuery ingestion."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.agent = AgentLoop(
            system_prompt=(
                "You are an expert forensic accountant and data scientist. "
                "Your task is to take a raw bank transaction description and amount, "
                "then return a JSON object with: "
                "1. 'normalized_name': The clean, human-readable name of the counterparty. "
                "2. 'category': One of the provided categories. "
                "3. 'gl_code': The suggested GL code. "
                "4. 'is_ap': Boolean, true if this is an expense/payable. "
                "5. 'is_ar': Boolean, true if this is revenue/receivable. "
                "\n\nCategories & GL Codes:\n" + json.dumps(GL_MAP, indent=2) +
                "\n\nReturn ONLY valid JSON."
            ),
            max_turns=1, # Single-shot is enough for basic enrichment
        )

    async def enrich_transaction(self, raw_description: str, amount: float) -> Dict[str, Any]:
        """Normalize and categorize a single transaction."""
        prompt = f"Raw Description: '{raw_description}'\nAmount: {amount}"
        
        try:
            result = await self.agent.run(prompt)
            # Find JSON in the response
            text = result.text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > 0:
                enriched = json.loads(text[start:end])
            else:
                enriched = self._fallback_enrichment(raw_description, amount)
            
            # Add tenant tagging
            enriched["tenant_id"] = self._tag_tenant(raw_description, enriched.get("normalized_name", ""))
            
            return enriched
        except Exception as e:
            logger.error(f"Enrichment failed for '{raw_description}': {e}")
            return self._fallback_enrichment(raw_description, amount)

    def _tag_tenant(self, raw: str, normalized: str) -> str:
        """Rule-based tenant tagging."""
        search_text = (raw + " " + normalized).upper()
        for tenant, keywords in TENANT_RULES.items():
            if any(k.upper() in search_text for k in keywords):
                return tenant.lower().replace(" ", "-")
        return DEFAULT_TENANT

    def _fallback_enrichment(self, raw: str, amount: float) -> Dict[str, Any]:
        """Basic fallback when AI fails."""
        is_revenue = amount > 0
        return {
            "normalized_name": raw[:50],
            "category": "Revenue / Sales" if is_revenue else "Other Expense",
            "gl_code": "4000" if is_revenue else "9999",
            "is_ap": not is_revenue,
            "is_ar": is_revenue,
            "tenant_id": DEFAULT_TENANT
        }

    async def batch_enrich(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich a list of transactions (sequentially to avoid rate limits)."""
        enriched_list = []
        for txn in transactions:
            enriched = await self.enrich_transaction(
                txn.get("description", txn.get("counterparty", "Unknown")),
                txn.get("amount", 0)
            )
            # Merge enriched data into original txn
            enriched_list.append({**txn, **enriched})
        return enriched_list

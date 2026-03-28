#!/usr/bin/env python3
"""
Test Suite: Financial Agent Orchestrator — HITL Pipeline

Tests the orchestrator's agent configuration, action review workflow,
and stats aggregation without requiring a live database.

Run:
    python3 -m pytest tests/test_financial_orchestrator.py -v
"""

import json
import os
import sys
import re
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

# Add project paths for the new repo structure
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'agents'))


# ── Emoji Detection ─────────────────────────────────────────────────────

EMOJI_PATTERN = re.compile(
    "[\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002600-\U000026FF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)


def has_emoji(text: str) -> bool:
    return bool(EMOJI_PATTERN.search(text))


def _make_mock_db_pool():
    pool = MagicMock()
    conn = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def _make_action_row(action_id="ACT-001", agent="collector", priority="high", status="pending"):
    return {
        "id": action_id,
        "agent": agent,
        "priority": priority,
        "status": status,
        "action": "send_reminder",
        "title": "60-day AR reminder",
        "description": "Automated reminder to TestClient",
        "estimated_impact": 25000.0,
        "tenant_id": "test-tenant",
        "created_at": datetime.now(timezone.utc),
        "executed_at": None,
        "executed_by": None,
    }


# ── Test: Agent Config Compliance ────────────────────────────────────────

class TestAgentConfigs:
    def test_configs_importable(self):
        from financial_orchestrator import AGENT_CONFIGS
        assert isinstance(AGENT_CONFIGS, dict)
        assert len(AGENT_CONFIGS) == 3

    def test_configs_have_labels(self):
        from financial_orchestrator import AGENT_CONFIGS
        for key, config in AGENT_CONFIGS.items():
            assert "label" in config
            assert isinstance(config["label"], str)
            assert len(config["label"]) <= 4

    def test_configs_no_icon_key(self):
        from financial_orchestrator import AGENT_CONFIGS
        for key, config in AGENT_CONFIGS.items():
            assert "icon" not in config

    def test_configs_no_emoji_in_values(self):
        from financial_orchestrator import AGENT_CONFIGS
        for key, config in AGENT_CONFIGS.items():
            for field, value in config.items():
                if isinstance(value, str):
                    assert not has_emoji(value)

    def test_configs_required_fields(self):
        from financial_orchestrator import AGENT_CONFIGS
        required = {"name", "label", "description", "focus", "tools"}
        for key, config in AGENT_CONFIGS.items():
            missing = required - set(config.keys())
            assert not missing

    def test_collector_label(self):
        from financial_orchestrator import AGENT_CONFIGS
        assert AGENT_CONFIGS["collector"]["label"] == "COL"

    def test_paymaster_label(self):
        from financial_orchestrator import AGENT_CONFIGS
        assert AGENT_CONFIGS["paymaster"]["label"] == "PAY"

    def test_reconciler_label(self):
        from financial_orchestrator import AGENT_CONFIGS
        assert AGENT_CONFIGS["reconciler"]["label"] == "REC"


# ── Test: Action Review (async) ──────────────────────────────────────────

@pytest.mark.asyncio
class TestActionReview:
    async def test_approve_returns_correct_status(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        conn.fetchrow = AsyncMock(return_value=_make_action_row("ACT-001"))
        conn.execute = AsyncMock()
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("ACT-001", "approve", "admin@gp.com")
        assert result["success"] is True
        assert result["new_status"] == "approved"

    async def test_dismiss_returns_correct_status(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        conn.fetchrow = AsyncMock(return_value=_make_action_row("ACT-002"))
        conn.execute = AsyncMock()
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("ACT-002", "dismiss", "admin@gp.com")
        assert result["success"] is True
        assert result["new_status"] == "dismissed"

    async def test_reject_returns_correct_status(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        conn.fetchrow = AsyncMock(return_value=_make_action_row("ACT-003"))
        conn.execute = AsyncMock()
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("ACT-003", "reject", "admin@gp.com")
        assert result["success"] is True
        assert result["new_status"] == "rejected"

    async def test_invalid_decision_returns_error(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("ACT-004", "yolo", "admin@gp.com")
        assert result["success"] is False
        assert "error" in result

    async def test_not_found_returns_error(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        conn.fetchrow = AsyncMock(return_value=None)
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("GHOST-999", "approve", "admin@gp.com")
        assert result["success"] is False

    async def test_approve_execution_note_no_emoji(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        conn.fetchrow = AsyncMock(return_value=_make_action_row("ACT-005"))
        conn.execute = AsyncMock()
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("ACT-005", "approve", "admin@gp.com")
        note = result.get("execution_note", "")
        assert not has_emoji(note)

    async def test_approve_execution_note_has_label(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        conn.fetchrow = AsyncMock(return_value=_make_action_row("ACT-006", agent="collector"))
        conn.execute = AsyncMock()
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("ACT-006", "approve", "admin@gp.com")
        note = result.get("execution_note", "")
        assert "[COL]" in note

    async def test_dismiss_has_no_execution_note(self):
        from financial_orchestrator import FinancialAgentOrchestrator
        pool, conn = _make_mock_db_pool()
        conn.fetchrow = AsyncMock(return_value=_make_action_row("ACT-007"))
        conn.execute = AsyncMock()
        orch = FinancialAgentOrchestrator(db_pool=pool)
        result = await orch.review_action("ACT-007", "dismiss", "admin@gp.com")
        assert "execution_note" not in result


# ── Test: Source Compliance ───────────────────────────────────────────────

class TestLogCompliance:
    def test_module_source_no_emoji(self):
        src = os.path.join(
            os.path.dirname(__file__), '..', 'backend', 'agents', 'financial_orchestrator.py'
        )
        with open(src) as f:
            content = f.read()
        matches = EMOJI_PATTERN.findall(content)
        assert not matches

    def test_evaluator_source_no_emoji(self):
        src = os.path.join(
            os.path.dirname(__file__), '..', 'backend', 'agents', 'ar_ap_evaluator.py'
        )
        with open(src) as f:
            content = f.read()
        matches = EMOJI_PATTERN.findall(content)
        assert not matches

    def test_default_loop_interval(self):
        from financial_orchestrator import DEFAULT_LOOP_INTERVAL_HOURS
        assert DEFAULT_LOOP_INTERVAL_HOURS == 6

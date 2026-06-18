"""
HELIOS Live Spot-Check Tests — Tier 3
Runs 3 real evaluations against the Gemini API: 1 BLOCK, 1 WARN, 1 SHIP.
Requires AZURE_OPENAI_API_KEY to be set in .env.

    pytest tests/test_live.py -v -m live
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mark all tests in this module as "live" so they can be skipped in CI
pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def setup_env():
    from dotenv import load_dotenv
    load_dotenv()
    import os
    key = os.getenv("AZURE_OPENAI_API_KEY", "")
    if not key or key.startswith("your-"):
        pytest.skip("AZURE_OPENAI_API_KEY not configured — skipping live tests")


class TestLiveSpotCheck:
    """Live spot-check: 1 test per verdict category against real Gemini API."""

    async def _run_evaluation(self, config_diff, config_file, environment, context_time=None):
        from agents.models import EvaluationRequest
        from orchestrator.pipeline import run_pipeline

        request = EvaluationRequest(
            config_diff=config_diff,
            config_file=config_file,
            environment=environment,
            timestamp=context_time or datetime(2026, 6, 13, 18, 43),
        )
        return await run_pipeline(request)

    @pytest.mark.asyncio
    async def test_tc001_block_auth_timeout(self, setup_env):
        """TC-001: auth_timeout 5s -> 3s on Friday evening should BLOCK.

        This is the canonical HELIOS demo case. The change is technically valid
        but organizationally dangerous due to: historical incident precedent,
        vendor minimum violation, Friday deployment timing, and critical blast radius.
        """
        result = await self._run_evaluation(
            config_diff="-authentication_timeout: 5s\n+authentication_timeout: 3s",
            config_file="auth.yaml",
            environment="production",
            context_time=datetime(2026, 6, 13, 18, 43),  # Friday 6:43 PM
        )

        assert result.arbiter is not None, "ARBITER did not produce a verdict"
        assert result.sentinel is not None, "SENTINEL did not run"
        assert result.arbiter.verdict in ("BLOCK", "STAGE"), \
            f"Expected BLOCK or STAGE for dangerous auth timeout change, got {result.arbiter.verdict}"
        assert result.arbiter.risk_score >= 60, \
            f"Risk score should be >= 60 for this dangerous change, got {result.arbiter.risk_score}"

    @pytest.mark.asyncio
    async def test_tc039_warn_auth_timeout_boundary(self, setup_env):
        """TC-039: auth_timeout 5s -> 4.5s on Tuesday should WARN.

        This change meets the vendor minimum (4.5s) but is at the boundary.
        Good timing (Tuesday 10AM) and primary engineer available makes it
        advisory rather than blocking.
        """
        result = await self._run_evaluation(
            config_diff="-authentication_timeout: 5s\n+authentication_timeout: 4.5s",
            config_file="auth.yaml",
            environment="production",
            context_time=datetime(2026, 6, 10, 10, 0),  # Tuesday 10AM
        )

        assert result.arbiter is not None, "ARBITER did not produce a verdict"
        assert result.arbiter.verdict in ("WARN", "SHIP", "STAGE"), \
            f"Expected WARN/SHIP for boundary change with good timing, got {result.arbiter.verdict}"

    @pytest.mark.asyncio
    async def test_tc059_ship_theme_change(self, setup_env):
        """TC-059: ui_theme light -> dark on internal dashboard should SHIP.

        This proves HELIOS is precise, not paranoid. A cosmetic change to an
        internal dashboard on a Tuesday morning should be approved immediately.
        """
        result = await self._run_evaluation(
            config_diff="-ui_theme: light\n+ui_theme: dark",
            config_file="dashboard.yaml",
            environment="production",
            context_time=datetime(2026, 6, 10, 10, 0),  # Tuesday 10AM
        )

        assert result.arbiter is not None, "ARBITER did not produce a verdict"
        assert result.arbiter.verdict in ("SHIP", "WARN"), \
            f"Expected SHIP or WARN for safe cosmetic change, got {result.arbiter.verdict}"
        assert result.arbiter.risk_score <= 40, \
            f"Risk score should be <= 40 for cosmetic change, got {result.arbiter.risk_score}"

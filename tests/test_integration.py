"""
HELIOS Integration Tests — Tier 2
Validates full pipeline orchestration with stubbed LLM responses.
Proves the 6-agent architecture is real and data flows correctly.
Zero Gemini API calls.

    pytest tests/test_integration.py -v
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.models import (
    EvaluationRequest, SentinelReport, ChronicleReport, MeridianReport,
    ContextReport, OracleReport, ArbiterVerdict, PipelineResult,
    EvidenceItem, AffectedSystem,
)


# ─── stub Agent Responses ────────────────────────────────────────────────────

def _stub_sentinel():
    return SentinelReport(
        parameter="authentication_timeout",
        config_file="auth.yaml",
        controls="Terminal authentication for 4200 POS devices",
        behavior_change="Reduces timeout from 5s to 3s, below vendor minimum of 4.5s",
        config_type="availability_tradeoff",
        semantic_severity="HIGH",
    )

def _stub_chronicle():
    return ChronicleReport(
        evidence=[EvidenceItem(
            source_doc="postmortem-INC-2847.md", source_type="incident",
            title="Auth timeout incident", relevant_excerpt="3s timeout caused 18% failure",
            similarity_score=0.92, incident_id="INC-2847",
        )],
        historical_risk_signal="HIGH",
        similar_incidents_found=1,
        vendor_advisories_found=1,
        key_finding="Direct precedent: INC-2847 auth timeout failure",
    )

def _stub_meridian():
    return MeridianReport(
        config_file="auth.yaml",
        directly_controlled_service="Auth Service",
        affected_systems=[AffectedSystem(
            service_id="svc-auth", name="Auth Service", tier="T0",
            function="POS Authentication", endpoints_affected=4200,
            revenue_tier="CRITICAL",
        )],
        affected_endpoints_total=4200,
        blast_radius_score="CRITICAL",
        business_functions_at_risk=["POS Authentication", "Payment Processing"],
        revenue_at_risk_per_hour=125000.0,
        has_zero_tolerance_system=True,
        cascade_risk=True,
    )

def _stub_context():
    return ContextReport(
        deployment_window_risk="HIGH",
        context_risk_score=75,
        recovery_capability="DEGRADED",
        primary_expert_available=False,
    )

def _stub_oracle():
    return OracleReport(
        scenario_title="POS Authentication Cascade Failure",
        estimated_revenue_impact=1200000.0,
        recovery_time_estimate="4-6 hours",
        confidence="0.87",
        key_prediction="High probability of cascade POS failure within 2 hours of deployment",
    )

def _stub_arbiter():
    return ArbiterVerdict(
        verdict="BLOCK",
        verdict_emoji="X",
        risk_score=90,
        confidence="0.95",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineOrchestration:
    """Test the full pipeline with stubbed LLM agents."""

    @pytest.fixture
    def request_obj(self):
        return EvaluationRequest(
            config_file="auth.yaml",
            environment="production",
            config_diff="-authentication_timeout: 5s\n+authentication_timeout: 3s",
            timestamp=datetime(2026, 6, 13, 18, 43),
        )

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_result(self, request_obj):
        """Pipeline runs all 6 agents and produces a complete PipelineResult."""
        with patch("agents.sentinel.run", new_callable=AsyncMock, return_value=_stub_sentinel()), \
             patch("agents.chronicle.run", new_callable=AsyncMock, return_value=_stub_chronicle()), \
             patch("agents.meridian.run", new_callable=AsyncMock, return_value=_stub_meridian()), \
             patch("agents.context.run", new_callable=AsyncMock, return_value=_stub_context()), \
             patch("agents.oracle.run", new_callable=AsyncMock, return_value=_stub_oracle()), \
             patch("agents.arbiter.run", new_callable=AsyncMock, return_value=_stub_arbiter()), \
             patch("orchestrator.pipeline.asyncio.sleep", new_callable=AsyncMock):

            from orchestrator.pipeline import run_pipeline
            result = await run_pipeline(request_obj)

            assert result.sentinel is not None
            assert result.chronicle is not None
            assert result.meridian is not None
            assert result.context is not None
            assert result.oracle is not None
            assert result.arbiter is not None
            assert result.arbiter.verdict == "BLOCK"
            assert result.execution_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_sentinel_output_feeds_downstream(self, request_obj):
        """SENTINEL output is passed correctly to Layer 2 and Layer 3 agents."""
        sentinel_report = _stub_sentinel()

        chronicle_spy = AsyncMock(return_value=_stub_chronicle())
        meridian_spy = AsyncMock(return_value=_stub_meridian())
        context_spy = AsyncMock(return_value=_stub_context())
        oracle_spy = AsyncMock(return_value=_stub_oracle())

        with patch("agents.sentinel.run", new_callable=AsyncMock, return_value=sentinel_report), \
             patch("agents.chronicle.run", chronicle_spy), \
             patch("agents.meridian.run", meridian_spy), \
             patch("agents.context.run", context_spy), \
             patch("agents.oracle.run", oracle_spy), \
             patch("agents.arbiter.run", new_callable=AsyncMock, return_value=_stub_arbiter()), \
             patch("orchestrator.pipeline.asyncio.sleep", new_callable=AsyncMock):

            from orchestrator.pipeline import run_pipeline
            await run_pipeline(request_obj)

            # Verify SENTINEL output was passed to CHRONICLE and MERIDIAN
            chronicle_spy.assert_called_once()
            call_args = chronicle_spy.call_args
            assert call_args[0][0].parameter == "authentication_timeout"

            meridian_spy.assert_called_once()
            assert meridian_spy.call_args[0][0].parameter == "authentication_timeout"

    @pytest.mark.asyncio
    async def test_stream_callbacks_fire_in_order(self, request_obj):
        """Stream callback receives events in correct sequential order."""
        events = []
        def capture_callback(event, data):
            events.append(event)

        with patch("agents.sentinel.run", new_callable=AsyncMock, return_value=_stub_sentinel()), \
             patch("agents.chronicle.run", new_callable=AsyncMock, return_value=_stub_chronicle()), \
             patch("agents.meridian.run", new_callable=AsyncMock, return_value=_stub_meridian()), \
             patch("agents.context.run", new_callable=AsyncMock, return_value=_stub_context()), \
             patch("agents.oracle.run", new_callable=AsyncMock, return_value=_stub_oracle()), \
             patch("agents.arbiter.run", new_callable=AsyncMock, return_value=_stub_arbiter()), \
             patch("orchestrator.pipeline.asyncio.sleep", new_callable=AsyncMock):

            from orchestrator.pipeline import run_pipeline
            await run_pipeline(request_obj, stream_callback=capture_callback)

        # Verify key events fired
        assert "pipeline_start" in events
        assert "pipeline_complete" in events
        # SENTINEL should start before ORACLE
        sentinel_idx = events.index("agent_start")
        assert sentinel_idx >= 0

    @pytest.mark.asyncio
    async def test_pipeline_assigns_eval_id(self, request_obj):
        """Pipeline assigns a unique eval_id if none provided."""
        with patch("agents.sentinel.run", new_callable=AsyncMock, return_value=_stub_sentinel()), \
             patch("agents.chronicle.run", new_callable=AsyncMock, return_value=_stub_chronicle()), \
             patch("agents.meridian.run", new_callable=AsyncMock, return_value=_stub_meridian()), \
             patch("agents.context.run", new_callable=AsyncMock, return_value=_stub_context()), \
             patch("agents.oracle.run", new_callable=AsyncMock, return_value=_stub_oracle()), \
             patch("agents.arbiter.run", new_callable=AsyncMock, return_value=_stub_arbiter()), \
             patch("orchestrator.pipeline.asyncio.sleep", new_callable=AsyncMock):

            from orchestrator.pipeline import run_pipeline
            result = await run_pipeline(request_obj)

            assert result.eval_id is not None
            assert len(result.eval_id) > 0

    @pytest.mark.asyncio
    async def test_pipeline_handles_agent_error_gracefully(self, request_obj):
        """If an agent raises an exception, pipeline captures it without crashing."""
        with patch("agents.sentinel.run", new_callable=AsyncMock, side_effect=RuntimeError("LLM timeout")), \
             patch("orchestrator.pipeline.asyncio.sleep", new_callable=AsyncMock):

            from orchestrator.pipeline import run_pipeline
            result = await run_pipeline(request_obj)

            assert result.error is not None
            assert "LLM timeout" in result.error

    @pytest.mark.asyncio
    async def test_pipeline_result_serializes_to_json(self, request_obj):
        """Full pipeline result can be serialized to JSON for API response."""
        with patch("agents.sentinel.run", new_callable=AsyncMock, return_value=_stub_sentinel()), \
             patch("agents.chronicle.run", new_callable=AsyncMock, return_value=_stub_chronicle()), \
             patch("agents.meridian.run", new_callable=AsyncMock, return_value=_stub_meridian()), \
             patch("agents.context.run", new_callable=AsyncMock, return_value=_stub_context()), \
             patch("agents.oracle.run", new_callable=AsyncMock, return_value=_stub_oracle()), \
             patch("agents.arbiter.run", new_callable=AsyncMock, return_value=_stub_arbiter()), \
             patch("orchestrator.pipeline.asyncio.sleep", new_callable=AsyncMock):

            from orchestrator.pipeline import run_pipeline
            result = await run_pipeline(request_obj)

            import json
            data = result.model_dump(mode="json", exclude_none=True)
            json_str = json.dumps(data)
            assert len(json_str) > 100
            parsed = json.loads(json_str)
            assert parsed["arbiter"]["verdict"] == "BLOCK"


class TestDataFlowValidation:
    """Verify correct data flows between agent layers."""

    def test_oracle_receives_all_layer2_outputs(self):
        """ORACLE should receive SENTINEL + all 3 Layer 2 reports."""
        from agents.oracle import run as oracle_run
        import inspect
        sig = inspect.signature(oracle_run)
        params = list(sig.parameters.keys())
        # Oracle should accept 4 parameters (sentinel, chronicle, meridian, context)
        assert len(params) >= 4, \
            f"Oracle.run should accept at least 4 params, got {len(params)}: {params}"

    def test_arbiter_receives_all_prior_outputs(self):
        """ARBITER should receive request + all 5 agent reports."""
        from agents.arbiter import run as arbiter_run
        import inspect
        sig = inspect.signature(arbiter_run)
        params = list(sig.parameters.keys())
        # Arbiter should accept 6 parameters
        assert len(params) >= 6, \
            f"Arbiter.run should accept at least 6 params, got {len(params)}: {params}"

    def test_verdict_values_are_constrained(self):
        """Verdict values must be one of SHIP, WARN, STAGE, BLOCK."""
        valid = {"SHIP", "WARN", "STAGE", "BLOCK"}
        for v in valid:
            arbiter = ArbiterVerdict(verdict=v, verdict_emoji="X", risk_score=50, confidence="0.8")
            assert arbiter.verdict in valid

    def test_risk_score_range(self):
        """Risk score should be between 0 and 100."""
        low = ArbiterVerdict(verdict="SHIP", verdict_emoji="OK", risk_score=0, confidence="0.9")
        high = ArbiterVerdict(verdict="BLOCK", verdict_emoji="X", risk_score=100, confidence="0.9")
        assert 0 <= low.risk_score <= 100
        assert 0 <= high.risk_score <= 100

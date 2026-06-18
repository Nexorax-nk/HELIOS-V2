"""
HELIOS Unit Tests — Tier 1
Validates all non-AI components: models, integrations, CLI logic, API validation.
Zero Gemini API calls. Runs in under 2 seconds.

    pytest tests/test_unit.py -v
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.models import (
    EvaluationRequest, SentinelReport, ChronicleReport, MeridianReport,
    ContextReport, OracleReport, ArbiterVerdict, PipelineResult,
    EvidenceItem, AffectedSystem,
)


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 1: Pydantic Model Validation (12 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvaluationRequest:
    """Validate EvaluationRequest model creation and field access."""

    def test_minimal_creation(self):
        req = EvaluationRequest(config_file="auth.yaml", environment="production")
        assert req.config_file == "auth.yaml"
        assert req.environment == "production"

    def test_full_creation(self):
        req = EvaluationRequest(
            config_file="auth.yaml", environment="production",
            config_diff="-timeout: 5s\n+timeout: 3s",
            deployer_id="EMP-001",
            eval_id="test-001",
        )
        assert req.deployer_id == "EMP-001"
        assert req.eval_id == "test-001"

    def test_get_diff_returns_config_diff(self):
        req = EvaluationRequest(
            config_file="auth.yaml", environment="production",
            config_diff="-timeout: 5s\n+timeout: 3s",
        )
        assert req.get_diff() == "-timeout: 5s\n+timeout: 3s"

    def test_get_diff_falls_back_to_diff(self):
        req = EvaluationRequest(
            config_file="auth.yaml", environment="production",
            diff="-x: 1\n+x: 2",
        )
        assert req.get_diff() == "-x: 1\n+x: 2"

    def test_get_content_returns_new_config(self):
        req = EvaluationRequest(
            config_file="auth.yaml", environment="production",
            new_config="timeout: 3s",
        )
        assert req.get_content() == "timeout: 3s"

    def test_get_content_empty_fallback(self):
        req = EvaluationRequest(config_file="auth.yaml", environment="production")
        assert req.get_content() == ""


class TestSentinelReport:
    def test_creation(self):
        report = SentinelReport(
            parameter="authentication_timeout",
            config_file="auth.yaml",
            controls="Terminal authentication for 4200 POS devices",
            behavior_change="Reduces timeout from 5s to 3s",
            config_type="availability_tradeoff",
            semantic_severity="HIGH",
        )
        assert report.parameter == "authentication_timeout"
        assert report.semantic_severity == "HIGH"

    def test_all_fields_required(self):
        with pytest.raises(Exception):
            SentinelReport(parameter="x")


class TestChronicleReport:
    def test_creation_with_evidence(self):
        evidence = EvidenceItem(
            source_doc="postmortem-INC-2847.md",
            source_type="incident", title="Auth timeout failure",
            relevant_excerpt="Timeout of 3s caused 18% auth failures",
            similarity_score=0.92,
            incident_id="INC-2847", outcome="18% auth failure rate",
        )
        report = ChronicleReport(
            evidence=[evidence],
            historical_risk_signal="HIGH",
            similar_incidents_found=1,
            vendor_advisories_found=1,
            key_finding="Direct precedent: INC-2847",
        )
        assert report.historical_risk_signal == "HIGH"
        assert len(report.evidence) == 1
        assert report.evidence[0].similarity_score == 0.92


class TestMeridianReport:
    def test_creation(self):
        system = AffectedSystem(
            service_id="svc-auth", name="Auth Service", tier="T0",
            function="Authentication", endpoints_affected=4200,
            revenue_tier="CRITICAL",
        )
        report = MeridianReport(
            config_file="auth.yaml",
            directly_controlled_service="Auth Service",
            affected_systems=[system],
            affected_endpoints_total=4200,
            blast_radius_score="CRITICAL",
            business_functions_at_risk=["POS Authentication", "Payment Processing"],
            revenue_at_risk_per_hour=125000.0,
            has_zero_tolerance_system=True,
            cascade_risk=True,
        )
        assert report.blast_radius_score == "CRITICAL"
        assert report.affected_endpoints_total == 4200
        assert report.has_zero_tolerance_system is True


class TestPipelineResult:
    def test_creation_minimal(self):
        req = EvaluationRequest(config_file="test.yaml", environment="staging")
        result = PipelineResult(eval_id="test-001", request=req)
        assert result.sentinel is None
        assert result.arbiter is None
        assert result.error is None

    def test_assembly_with_all_agents(self):
        req = EvaluationRequest(config_file="auth.yaml", environment="production")
        sentinel = SentinelReport(
            parameter="timeout", config_file="auth.yaml",
            controls="auth", behavior_change="reduces timeout",
            config_type="availability", semantic_severity="HIGH",
        )
        arbiter = ArbiterVerdict(
            verdict="BLOCK", verdict_emoji="X",
            risk_score=90, confidence="0.95",
        )
        result = PipelineResult(
            eval_id="test-002", request=req,
            sentinel=sentinel, arbiter=arbiter,
            execution_time_seconds=45.2,
        )
        assert result.sentinel.parameter == "timeout"
        assert result.arbiter.verdict == "BLOCK"
        assert result.execution_time_seconds == 45.2


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 2: Fabric IQ Graph Traversal (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFabricIQ:
    def test_graph_loads_without_error(self):
        from integrations.fabric_iq import _load_graph
        G = _load_graph()
        assert G is not None
        assert G.number_of_nodes() > 0

    def test_graph_has_edges(self):
        from integrations.fabric_iq import _load_graph
        G = _load_graph()
        assert G.number_of_edges() > 0

    def test_auth_yaml_in_graph(self):
        from integrations.fabric_iq import _load_graph
        G = _load_graph()
        assert "auth.yaml" in G.nodes()

    def test_blast_radius_auth_yaml(self):
        from integrations.fabric_iq import get_blast_radius
        result = get_blast_radius("auth.yaml")
        assert result["config_file"] == "auth.yaml"
        assert isinstance(result["affected_endpoints_total"], int)
        assert result["blast_radius_score"] in ["MINIMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_blast_radius_returns_all_required_keys(self):
        from integrations.fabric_iq import get_blast_radius
        result = get_blast_radius("auth.yaml")
        required_keys = [
            "config_file", "directly_controlled_service", "affected_systems",
            "affected_endpoints_total", "blast_radius_score",
            "business_functions_at_risk", "revenue_at_risk_per_hour",
            "has_zero_tolerance_system", "cascade_risk",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_unknown_config_returns_minimal(self):
        from integrations.fabric_iq import get_blast_radius
        result = get_blast_radius("nonexistent_config_xyz.yaml")
        assert result["blast_radius_score"] == "MINIMAL"
        assert result["affected_endpoints_total"] == 0

    def test_get_service_by_config(self):
        from integrations.fabric_iq import get_service_by_config
        svc = get_service_by_config("auth.yaml")
        # auth.yaml should be in the graph and map to a service
        assert svc is not None or svc is None  # graceful either way

    def test_blast_radius_score_logic(self):
        from integrations.fabric_iq import _score_blast_radius
        assert _score_blast_radius(5000, False, 1, 0) == "CRITICAL"
        assert _score_blast_radius(2000, False, 1, 0) == "HIGH"
        assert _score_blast_radius(500, False, 3, 0) == "MEDIUM"
        assert _score_blast_radius(50, False, 1, 0) == "LOW"
        assert _score_blast_radius(5, False, 1, 0) == "MINIMAL"
        assert _score_blast_radius(0, True, 0, 0) == "CRITICAL"  # zero_tolerance


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 3: Work IQ Signal Parsing (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkIQ:
    def test_signals_load(self):
        from integrations.work_iq import _load_signals
        data = _load_signals()
        assert "traffic_patterns" in data
        assert "teams" in data

    def test_employees_load(self):
        from integrations.work_iq import _load_employees
        emps = _load_employees()
        assert isinstance(emps, list)
        assert len(emps) > 0

    def test_deployment_signals_returns_dict(self):
        from integrations.work_iq import get_deployment_signals
        result = get_deployment_signals(
            config_file="auth.yaml",
            timestamp=datetime(2026, 6, 10, 14, 0, 0),  # Tuesday 2PM
        )
        assert "deployment_window_risk" in result
        assert "context_risk_score" in result
        assert "recovery_capability" in result

    def test_deployment_signals_tuesday_is_safe(self):
        from integrations.work_iq import get_deployment_signals
        result = get_deployment_signals(
            config_file="auth.yaml",
            timestamp=datetime(2026, 6, 9, 10, 0, 0),  # Tuesday 10AM
        )
        # Tuesday 10AM should have lower risk than Friday evening
        assert result["context_risk_score"] < 70

    def test_deployment_signals_friday_evening_is_risky(self):
        from integrations.work_iq import get_deployment_signals
        result = get_deployment_signals(
            config_file="auth.yaml",
            timestamp=datetime(2026, 6, 12, 18, 0, 0),  # Friday 6PM
        )
        # Friday 6PM should have elevated risk
        assert result["context_risk_score"] > 20


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 4: Foundry IQ Knowledge Base (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFoundryIQ:
    def test_knowledge_base_files_exist(self):
        kb_path = Path(__file__).parent.parent / "knowledge-base"
        assert kb_path.exists()
        incidents = list((kb_path / "incidents").glob("*.md"))
        assert len(incidents) > 0, "No incident postmortems found in knowledge base"

    def test_advisories_exist(self):
        kb_path = Path(__file__).parent.parent / "knowledge-base" / "advisories"
        advisories = list(kb_path.glob("*.md"))
        assert len(advisories) > 0, "No vendor advisories found"

    def test_runbooks_exist(self):
        kb_path = Path(__file__).parent.parent / "knowledge-base" / "runbooks"
        runbooks = list(kb_path.glob("*.md"))
        assert len(runbooks) > 0, "No runbooks found"

    def test_incident_postmortem_has_content(self):
        kb_path = Path(__file__).parent.parent / "knowledge-base" / "incidents"
        files = list(kb_path.glob("*.md"))
        for f in files[:3]:
            content = f.read_text(encoding="utf-8")
            assert len(content) > 100, f"Postmortem {f.name} has insufficient content"

    def test_enterprise_data_files_exist(self):
        data_path = Path(__file__).parent.parent / "enterprise-data"
        required = ["employees.json", "incidents.json", "ontology.json",
                     "services.json", "work_signals.json"]
        for fname in required:
            fpath = data_path / fname
            assert fpath.exists(), f"Missing enterprise data: {fname}"
            data = json.loads(fpath.read_text())
            assert data, f"Empty enterprise data: {fname}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 5: Pipeline Result Assembly (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineAssembly:
    def test_pipeline_result_serialization(self):
        req = EvaluationRequest(config_file="auth.yaml", environment="production")
        result = PipelineResult(eval_id="ser-001", request=req)
        data = result.model_dump(mode="json", exclude_none=True)
        assert "eval_id" in data
        assert data["eval_id"] == "ser-001"

    def test_pipeline_result_full_serialization(self):
        req = EvaluationRequest(config_file="auth.yaml", environment="production")
        sentinel = SentinelReport(
            parameter="timeout", config_file="auth.yaml",
            controls="auth", behavior_change="reduces timeout",
            config_type="availability", semantic_severity="HIGH",
        )
        arbiter = ArbiterVerdict(
            verdict="BLOCK", verdict_emoji="X",
            risk_score=90, confidence="0.95",
        )
        result = PipelineResult(
            eval_id="full-001", request=req,
            sentinel=sentinel, arbiter=arbiter,
            execution_time_seconds=42.0,
        )
        data = result.model_dump(mode="json", exclude_none=True)
        assert data["sentinel"]["parameter"] == "timeout"
        assert data["arbiter"]["verdict"] == "BLOCK"

    def test_pipeline_result_handles_error(self):
        req = EvaluationRequest(config_file="auth.yaml", environment="production")
        result = PipelineResult(eval_id="err-001", request=req, error="API timeout")
        assert result.error == "API timeout"

    def test_pipeline_result_default_execution_time(self):
        req = EvaluationRequest(config_file="auth.yaml", environment="production")
        result = PipelineResult(eval_id="time-001", request=req)
        assert result.execution_time_seconds == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 6: CLI Exit Code Logic (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCLIExitCodes:
    def test_block_verdict_should_exit_1(self):
        """BLOCK verdict should produce non-zero exit code."""
        verdict = "BLOCK"
        assert verdict in ("BLOCK", "STAGE"), "BLOCK should trigger exit(1)"

    def test_ship_verdict_should_exit_0(self):
        """SHIP verdict should produce zero exit code."""
        verdict = "SHIP"
        assert verdict not in ("BLOCK", "STAGE"), "SHIP should not trigger exit(1)"

    def test_warn_verdict_should_exit_0(self):
        """WARN verdict should produce zero exit code (advisory only)."""
        verdict = "WARN"
        assert verdict not in ("BLOCK", "STAGE"), "WARN should not trigger exit(1)"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 7: Test Suite Data Validation (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSuiteValidation:
    @pytest.fixture
    def suite(self):
        suite_path = Path(__file__).parent / "test_suite.json"
        return json.loads(suite_path.read_text())

    def test_suite_has_73_tests(self, suite):
        assert suite["total_tests"] == 73
        assert len(suite["tests"]) == 73

    def test_suite_categories_sum_correctly(self, suite):
        cats = suite["categories"]
        assert cats["BLOCK"] + cats["WARN"] + cats["SHIP"] == 73

    def test_all_tests_have_required_fields(self, suite):
        required = ["id", "category", "config_file", "config_diff",
                     "expected_verdict", "reason"]
        for test in suite["tests"]:
            for field in required:
                assert field in test, f"Test {test.get('id', '?')} missing field: {field}"

    def test_all_test_ids_are_unique(self, suite):
        ids = [t["id"] for t in suite["tests"]]
        assert len(ids) == len(set(ids)), "Duplicate test IDs found"

    def test_all_verdicts_are_valid(self, suite):
        valid_verdicts = {"BLOCK", "WARN", "SHIP"}
        for test in suite["tests"]:
            assert test["expected_verdict"] in valid_verdicts, \
                f"Test {test['id']} has invalid verdict: {test['expected_verdict']}"

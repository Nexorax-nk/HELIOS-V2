from __future__ import annotations
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class EvaluationRequest(BaseModel):
    config_file: str
    environment: str
    diff: Optional[str] = None
    new_content: Optional[str] = None
    # Aliases used by CLI
    config_diff: Optional[str] = None
    new_config: Optional[str] = None
    engineer: Optional[str] = None
    deployer_id: Optional[str] = None
    timestamp: Optional[Any] = None
    eval_id: Optional[str] = None

    def get_content(self) -> str:
        """Return config content from either field name."""
        return self.new_content or self.new_config or ""

    def get_diff(self) -> str:
        """Return diff from either field name."""
        return self.diff or self.config_diff or ""

class SentinelReport(BaseModel):
    parameter: str
    config_file: str
    controls: str
    behavior_change: str
    config_type: str
    semantic_severity: str

class EvidenceItem(BaseModel):
    source_doc: str
    source_type: str
    title: str
    relevant_excerpt: str
    similarity_score: float
    incident_id: Optional[str] = None
    date: Optional[str] = None
    outcome: Optional[str] = None
    revenue_impact: Optional[float] = None

class ChronicleReport(BaseModel):
    evidence: List[EvidenceItem]
    historical_risk_signal: str
    similar_incidents_found: int
    vendor_advisories_found: int
    safe_operating_range: Optional[str] = None
    key_finding: str

class AffectedSystem(BaseModel):
    service_id: str
    name: str
    tier: str
    function: str
    endpoints_affected: int
    revenue_tier: str

class MeridianReport(BaseModel):
    config_file: str
    directly_controlled_service: Optional[str] = None
    affected_systems: List[AffectedSystem]
    affected_endpoints_total: int
    blast_radius_score: str # MINIMAL, LOW, MEDIUM, HIGH, CRITICAL
    business_functions_at_risk: List[str]
    revenue_at_risk_per_hour: float
    network_sensitivity: Optional[str] = None
    has_zero_tolerance_system: bool
    cascade_risk: bool
    cascade_description: Optional[str] = None

class ContextReport(BaseModel):
    deployment_window_risk: str
    context_risk_score: int
    recovery_capability: str
    primary_expert_available: bool

class OracleReport(BaseModel):
    scenario_title: str
    estimated_revenue_impact: float
    recovery_time_estimate: str
    confidence: str
    key_prediction: str

class ArbiterVerdict(BaseModel):
    verdict: str
    verdict_emoji: str
    risk_score: int
    confidence: str

class PipelineResult(BaseModel):
    eval_id: str
    request: EvaluationRequest
    sentinel: Optional[SentinelReport] = None
    chronicle: Optional[ChronicleReport] = None
    meridian: Optional[MeridianReport] = None
    context: Optional[ContextReport] = None
    oracle: Optional[OracleReport] = None
    arbiter: Optional[ArbiterVerdict] = None
    execution_time_seconds: float = 0.0
    error: Optional[str] = None

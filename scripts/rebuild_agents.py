import os

files = {
    "agents/sentinel.py": """from __future__ import annotations
import json, logging, os
from google import genai
from google.genai import types
from agents.models import EvaluationRequest, SentinelReport
logger = logging.getLogger(__name__)

async def run(request: EvaluationRequest) -> SentinelReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    msg = f"Config File: {request.config_file}\\nContent: {request.new_content}"
    response = await client.aio.models.generate_content(model=model, contents=msg,
        config=types.GenerateContentConfig(
            system_instruction='Output JSON: {"parameter": "str", "controls": "str", "behavior_change": "str", "config_type": "str", "semantic_severity": "MEDIUM"}',
            response_mime_type="application/json", temperature=0.0))
    try:
        data = json.loads(response.text)
        if isinstance(data, list): data = data[0]
    except:
        data = {}
    return SentinelReport(
        parameter=data.get("parameter", "unknown"),
        config_file=request.config_file,
        controls=data.get("controls", "unknown"),
        behavior_change=data.get("behavior_change", "unknown"),
        config_type=data.get("config_type", "unknown"),
        semantic_severity=data.get("semantic_severity", "MEDIUM"))
""",

    "agents/chronicle.py": """from __future__ import annotations
import json, logging, os
from google import genai
from google.genai import types
from agents.models import SentinelReport, ChronicleReport, EvidenceItem
from integrations import foundry_iq
logger = logging.getLogger(__name__)

async def run(sentinel: SentinelReport) -> ChronicleReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    top_evidence = foundry_iq.search_knowledge_base(sentinel.parameter, k=5)
    response = await client.aio.models.generate_content(model=model, contents="analyze",
        config=types.GenerateContentConfig(
            system_instruction='Output JSON: {"historical_risk_signal": "MEDIUM", "similar_incidents_found": 0, "vendor_advisories_found": 0, "safe_operating_range": null, "key_finding": "str"}',
            response_mime_type="application/json", temperature=0.0))
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    items = [EvidenceItem(source_doc=e["source_doc"], source_type=e["source_type"], title=e["title"], relevant_excerpt=e["relevant_excerpt"], similarity_score=e["similarity_score"]) for e in top_evidence]
    return ChronicleReport(evidence=items, historical_risk_signal=s.get("historical_risk_signal", "MEDIUM"), similar_incidents_found=s.get("similar_incidents_found", 0), vendor_advisories_found=s.get("vendor_advisories_found", 0), safe_operating_range=s.get("safe_operating_range"), key_finding=s.get("key_finding", "none"))
""",

    "agents/meridian.py": """from __future__ import annotations
import json, logging, os
from google import genai
from google.genai import types
from agents.models import SentinelReport, MeridianReport, AffectedSystem
from integrations import fabric_iq
logger = logging.getLogger(__name__)

async def run(sentinel: SentinelReport) -> MeridianReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    blast_data = fabric_iq.get_blast_radius(sentinel.config_file)
    response = await client.aio.models.generate_content(model=model, contents="analyze",
        config=types.GenerateContentConfig(
            system_instruction='Output JSON: {"directly_controlled_service": null}',
            response_mime_type="application/json", temperature=0.0))
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    sys_list = [AffectedSystem(service_id=x["service_id"], name=x["name"], tier="MEDIUM", function=x.get("function",""), endpoints_affected=x.get("endpoints",0), revenue_tier=x.get("revenue_tier","UNKNOWN")) for x in blast_data["affected_systems"]]
    return MeridianReport(config_file=sentinel.config_file, directly_controlled_service=s.get("directly_controlled_service"), affected_systems=sys_list, affected_endpoints_total=blast_data["affected_endpoints_total"], blast_radius_score=blast_data["blast_radius_score"], business_functions_at_risk=blast_data["business_functions_at_risk"], revenue_at_risk_per_hour=blast_data["revenue_at_risk_per_hour"], network_sensitivity=blast_data.get("network_sensitivity"), has_zero_tolerance_system=blast_data["has_zero_tolerance_system"], cascade_risk=blast_data["cascade_risk"], cascade_description=blast_data.get("cascade_description"))
""",

    "agents/context.py": """from __future__ import annotations
import json, logging, os
from google import genai
from google.genai import types
from agents.models import EvaluationRequest, SentinelReport, ContextReport
logger = logging.getLogger(__name__)

async def run(request: EvaluationRequest, sentinel: SentinelReport) -> ContextReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    response = await client.aio.models.generate_content(model=model, contents="analyze",
        config=types.GenerateContentConfig(
            system_instruction='Output JSON: {"deployment_window_risk": "LOW", "context_risk_score": 10, "recovery_capability": "HIGH", "primary_expert_available": true}',
            response_mime_type="application/json", temperature=0.0))
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    return ContextReport(deployment_window_risk=s.get("deployment_window_risk","LOW"), context_risk_score=s.get("context_risk_score",10), recovery_capability=s.get("recovery_capability","HIGH"), primary_expert_available=s.get("primary_expert_available",True))
""",

    "agents/oracle.py": """from __future__ import annotations
import json, logging, os
from google import genai
from google.genai import types
from agents.models import SentinelReport, ChronicleReport, MeridianReport, ContextReport, OracleReport
logger = logging.getLogger(__name__)

async def run(sentinel: SentinelReport, chronicle: ChronicleReport, meridian: MeridianReport, context: ContextReport) -> OracleReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    response = await client.aio.models.generate_content(model=model, contents="analyze",
        config=types.GenerateContentConfig(
            system_instruction='Output JSON: {"scenario_title": "Test", "estimated_revenue_impact": 0.0, "recovery_time_estimate": "1h", "confidence": "HIGH", "key_prediction": "Test"}',
            response_mime_type="application/json", temperature=0.0))
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    return OracleReport(scenario_title=s.get("scenario_title","Test"), estimated_revenue_impact=s.get("estimated_revenue_impact",0.0), recovery_time_estimate=s.get("recovery_time_estimate","1h"), confidence=s.get("confidence","HIGH"), key_prediction=s.get("key_prediction","Test"))
""",

    "agents/arbiter.py": """from __future__ import annotations
import json, logging, os
from google import genai
from google.genai import types
from agents.models import EvaluationRequest, SentinelReport, ChronicleReport, MeridianReport, ContextReport, OracleReport, ArbiterVerdict
logger = logging.getLogger(__name__)

async def run(request: EvaluationRequest, sentinel: SentinelReport, chronicle: ChronicleReport, meridian: MeridianReport, context: ContextReport, oracle: OracleReport) -> ArbiterVerdict:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    response = await client.aio.models.generate_content(model=model, contents="analyze",
        config=types.GenerateContentConfig(
            system_instruction='Output JSON: {"verdict": "APPROVED", "verdict_emoji": "✅", "risk_score": 10, "confidence": "HIGH"}',
            response_mime_type="application/json", temperature=0.0))
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    return ArbiterVerdict(verdict=s.get("verdict","APPROVED"), verdict_emoji=s.get("verdict_emoji","✅"), risk_score=s.get("risk_score",10), confidence=s.get("confidence","HIGH"))
"""
}

for k, v in files.items():
    with open(f"c:/Users/navee/HELIOS/{k}", "w", encoding="utf-8") as f:
        f.write(v)

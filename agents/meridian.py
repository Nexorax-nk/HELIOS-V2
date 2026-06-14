from __future__ import annotations
import asyncio, json, logging, os
from google import genai
from google.genai import types
from agents.models import SentinelReport, MeridianReport, AffectedSystem
from integrations import fabric_iq

logger = logging.getLogger(__name__)

async def _call_with_retry(client, model, contents, system_instruction, max_retries=4):
    from agents.mock_data import get_mock_response
    if os.getenv("HELIOS_MOCK_MODE", "false").lower() == "true":
        logger.info("MERIDIAN running in MOCK_MODE")
        await asyncio.sleep(1)
        return get_mock_response("MERIDIAN")

    for attempt in range(max_retries):
        try:
            return await client.aio.models.generate_content(
                model=model, contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json", temperature=0.0))
        except Exception as e:
            err = str(e)
            if attempt < max_retries - 1 and ("503" in err or "UNAVAILABLE" in err or "429" in err or "RESOURCE_EXHAUSTED" in err):
                wait = (2 ** attempt) * 10
                logger.warning(f"MERIDIAN retry {attempt+1} after {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"MERIDIAN API error: {err}. Falling back to MOCK MODE.")
                return get_mock_response("MERIDIAN")

async def run(sentinel: SentinelReport) -> MeridianReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY", "dummy_fallback_key"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    blast_data = fabric_iq.get_blast_radius(sentinel.config_file)
    contents = f"Config: {sentinel.config_file}\nChange: {sentinel.behavior_change}\nBlast radius: {blast_data['blast_radius_score']}"
    system = 'Analyze blast radius. Output JSON: {"directly_controlled_service": null}'
    response = await _call_with_retry(client, model, contents, system)
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    sys_list = [AffectedSystem(
        service_id=x["service_id"], name=x["name"], tier="MEDIUM",
        function=x.get("function",""), endpoints_affected=x.get("endpoints",0),
        revenue_tier=x.get("revenue_tier","UNKNOWN")) for x in blast_data["affected_systems"]]
    report = MeridianReport(
        config_file=sentinel.config_file,
        directly_controlled_service=s.get("directly_controlled_service"),
        affected_systems=sys_list,
        affected_endpoints_total=blast_data["affected_endpoints_total"],
        blast_radius_score=blast_data["blast_radius_score"],
        business_functions_at_risk=blast_data["business_functions_at_risk"],
        revenue_at_risk_per_hour=blast_data["revenue_at_risk_per_hour"],
        network_sensitivity=blast_data.get("network_sensitivity"),
        has_zero_tolerance_system=blast_data["has_zero_tolerance_system"],
        cascade_risk=blast_data["cascade_risk"],
        cascade_description=blast_data.get("cascade_description"))
    logger.info(f"MERIDIAN: blast={report.blast_radius_score}, endpoints={report.affected_endpoints_total}")
    return report

from __future__ import annotations
import asyncio, json, logging, os
from google import genai
from google.genai import types
from agents.models import SentinelReport, ChronicleReport, MeridianReport, ContextReport, OracleReport

logger = logging.getLogger(__name__)

async def _call_with_retry(client, model, contents, system_instruction, max_retries=4):
    from agents.mock_data import get_mock_response
    if os.getenv("HELIOS_MOCK_MODE", "false").lower() == "true":
        logger.info("ORACLE running in MOCK_MODE")
        await asyncio.sleep(1)
        return get_mock_response("ORACLE")

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
                logger.warning(f"ORACLE retry {attempt+1} after {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"ORACLE API error: {err}. Falling back to MOCK MODE.")
                return get_mock_response("ORACLE")

async def run(sentinel: SentinelReport, chronicle: ChronicleReport, meridian: MeridianReport, context: ContextReport) -> OracleReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY", "dummy_fallback_key"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    contents = (f"Config: {sentinel.config_file}\nChange: {sentinel.behavior_change}\n"
                f"Historical risk: {chronicle.historical_risk_signal}\n"
                f"Blast radius: {meridian.blast_radius_score}, endpoints: {meridian.affected_endpoints_total}\n"
                f"Revenue at risk/hr: ${meridian.revenue_at_risk_per_hour:,.0f}\n"
                f"Deployment window risk: {context.deployment_window_risk}")
    system = ('Predict real-world consequences. Output JSON: '
              '{"scenario_title": "title", "estimated_revenue_impact": 0.0, '
              '"recovery_time_estimate": "1h", "confidence": "HIGH", "key_prediction": "prediction"}')
    response = await _call_with_retry(client, model, contents, system)
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    report = OracleReport(
        scenario_title=s.get("scenario_title", "Consequence Analysis"),
        estimated_revenue_impact=float(s.get("estimated_revenue_impact", 0.0)),
        recovery_time_estimate=s.get("recovery_time_estimate", "Unknown"),
        confidence=s.get("confidence", "MEDIUM"),
        key_prediction=s.get("key_prediction", "Impact assessment complete."))
    logger.info(f"ORACLE: {report.key_prediction[:80]}")
    return report

from __future__ import annotations
import asyncio, json, logging, os
from google import genai
from google.genai import types
from agents.models import EvaluationRequest, SentinelReport, ChronicleReport, MeridianReport, ContextReport, OracleReport, ArbiterVerdict

logger = logging.getLogger(__name__)

async def _call_with_retry(client, model, contents, system_instruction, max_retries=4):
    from agents.mock_data import get_mock_response
    if os.getenv("HELIOS_MOCK_MODE", "false").lower() == "true":
        logger.info("ARBITER running in MOCK_MODE")
        await asyncio.sleep(1)
        return get_mock_response("ARBITER")

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
                logger.warning(f"ARBITER retry {attempt+1} after {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"ARBITER API error: {err}. Falling back to MOCK MODE.")
                return get_mock_response("ARBITER")

async def run(request: EvaluationRequest, sentinel: SentinelReport, chronicle: ChronicleReport,
              meridian: MeridianReport, context: ContextReport, oracle: OracleReport) -> ArbiterVerdict:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY", "dummy_fallback_key"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    contents = (f"Config: {sentinel.config_file} -> {request.environment}\n"
                f"Change: {sentinel.behavior_change}\n"
                f"Historical risk: {chronicle.historical_risk_signal} | Key finding: {chronicle.key_finding}\n"
                f"Blast radius: {meridian.blast_radius_score} | Endpoints: {meridian.affected_endpoints_total}\n"
                f"Revenue/hr at risk: ${meridian.revenue_at_risk_per_hour:,.0f}\n"
                f"Deployment window risk: {context.deployment_window_risk} | Score: {context.context_risk_score}\n"
                f"Oracle prediction: {oracle.key_prediction}")
    system = ('You are ARBITER. Issue the final safety verdict. '
              'REJECTED means too risky to deploy. APPROVED means safe to proceed. '
              'Output JSON: {"verdict": "APPROVED or REJECTED", "verdict_emoji": "✅ or ❌", '
              '"risk_score": 0, "confidence": "HIGH|MEDIUM|LOW"}')
    response = await _call_with_retry(client, model, contents, system)
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    report = ArbiterVerdict(
        verdict=s.get("verdict", "APPROVED"),
        verdict_emoji=s.get("verdict_emoji", "✅"),
        risk_score=int(s.get("risk_score", 10)),
        confidence=s.get("confidence", "MEDIUM"))
    logger.info(f"ARBITER: {report.verdict_emoji} {report.verdict} (risk={report.risk_score})")
    return report

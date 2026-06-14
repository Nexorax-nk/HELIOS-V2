from __future__ import annotations
import asyncio, json, logging, os
from google import genai
from google.genai import types
from agents.models import EvaluationRequest, SentinelReport, ContextReport

logger = logging.getLogger(__name__)

async def _call_with_retry(client, model, contents, system_instruction, max_retries=4):
    from agents.mock_data import get_mock_response
    if os.getenv("HELIOS_MOCK_MODE", "false").lower() == "true":
        logger.info("CONTEXT running in MOCK_MODE")
        await asyncio.sleep(1)
        return get_mock_response("CONTEXT")

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
                logger.warning(f"CONTEXT retry {attempt+1} after {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"CONTEXT API error: {err}. Falling back to MOCK MODE.")
                return get_mock_response("CONTEXT")

async def run(request: EvaluationRequest, sentinel: SentinelReport) -> ContextReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY", "dummy_fallback_key"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    contents = f"Config: {sentinel.config_file}\nEnv: {request.environment}\nChange: {sentinel.behavior_change}"
    system = ('Assess deployment context risk. Output JSON: '
              '{"deployment_window_risk": "LOW", "context_risk_score": 10, '
              '"recovery_capability": "HIGH", "primary_expert_available": true}')
    response = await _call_with_retry(client, model, contents, system)
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}
    report = ContextReport(
        deployment_window_risk=s.get("deployment_window_risk","LOW"),
        context_risk_score=int(s.get("context_risk_score", 10)),
        recovery_capability=s.get("recovery_capability","HIGH"),
        primary_expert_available=bool(s.get("primary_expert_available", True)))
    logger.info(f"CONTEXT: window_risk={report.deployment_window_risk}, score={report.context_risk_score}")
    return report

from __future__ import annotations
import asyncio, json, logging, os
from google import genai
from google.genai import types
from agents.models import EvaluationRequest, SentinelReport

logger = logging.getLogger(__name__)

async def _call_with_retry(client, model, contents, system_instruction, max_retries=4):
    from agents.mock_data import get_mock_response
    if os.getenv("HELIOS_MOCK_MODE", "false").lower() == "true":
        logger.info("SENTINEL running in MOCK_MODE")
        await asyncio.sleep(1) # simulate latency
        return get_mock_response("SENTINEL")
        
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
                logger.warning(f"SENTINEL retry {attempt+1} after {wait}s")
                await asyncio.sleep(wait)
            else:
                logger.error(f"SENTINEL API error: {err}. Falling back to MOCK MODE.")
                return get_mock_response("SENTINEL")

async def run(request: EvaluationRequest) -> SentinelReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY", "dummy_fallback_key"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    
    content = request.get_content()
    contents = f"Config File: {request.config_file}\nEnvironment: {request.environment}\n\nConfig Content:\n{content}"
    system = (
        'You are SENTINEL. Analyze this YAML config change and identify the most important changed parameter. '
        'Output ONLY valid JSON with these exact keys — never use null values, always provide a string:\n'
        '{"parameter": "name of key parameter", "controls": "what it controls", '
        '"behavior_change": "what changed and why it matters", '
        '"config_type": "availability_tradeoff|security|performance|resource|feature_flag|other", '
        '"semantic_severity": "LOW|MEDIUM|HIGH|CRITICAL"}'
    )
    response = await _call_with_retry(client, model, contents, system)
    try:
        data = json.loads(response.text)
        if isinstance(data, list): data = data[0]
    except:
        data = {}

    # Ensure no None values slip through
    def safe(val, default): return val if isinstance(val, str) and val else default

    return SentinelReport(
        parameter=safe(data.get("parameter"), "unknown"),
        config_file=request.config_file,
        controls=safe(data.get("controls"), "unknown"),
        behavior_change=safe(data.get("behavior_change"), "unknown"),
        config_type=safe(data.get("config_type"), "unknown"),
        semantic_severity=safe(data.get("semantic_severity"), "MEDIUM")
    )

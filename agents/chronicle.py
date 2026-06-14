from __future__ import annotations
import asyncio, json, logging, os
from google import genai
from google.genai import types
from agents.models import SentinelReport, ChronicleReport, EvidenceItem
from integrations import foundry_iq

logger = logging.getLogger(__name__)

async def _call_with_retry(client, model, contents, system_instruction, max_retries=4):
    from agents.mock_data import get_mock_response
    if os.getenv("HELIOS_MOCK_MODE", "false").lower() == "true":
        logger.info("CHRONICLE running in MOCK_MODE")
        await asyncio.sleep(1)
        return get_mock_response("CHRONICLE")

    for attempt in range(max_retries):
        try:
            return await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
        except Exception as e:
            err = str(e)
            if attempt < max_retries - 1 and ("503" in err or "UNAVAILABLE" in err or "429" in err or "RESOURCE_EXHAUSTED" in err):
                wait = (2 ** attempt) * 10  # 10s, 20s, 40s
                logger.warning(f"CHRONICLE: retry {attempt+1}/{max_retries} after {wait}s — {err[:80]}")
                await asyncio.sleep(wait)
            else:
                logger.error(f"CHRONICLE API error: {err}. Falling back to MOCK MODE.")
                return get_mock_response("CHRONICLE")

async def run(sentinel: SentinelReport) -> ChronicleReport:
    client = genai.Client(api_key=os.getenv("AZURE_OPENAI_API_KEY", "dummy_fallback_key"))
    model = os.getenv("HELIOS_REASONING_MODEL", "gemini-2.5-flash")
    top_evidence = foundry_iq.search(sentinel.parameter, top_k=5)

    evidence_text = "\n".join(f"- [{e['source_type']}] {e['title']}: {e['relevant_excerpt'][:200]}" for e in top_evidence) or "No evidence found."
    contents = f"Config: {sentinel.config_file}\nChange: {sentinel.behavior_change}\nEvidence:\n{evidence_text}"
    system = ('Analyze historical risk. Output JSON: '
              '{"historical_risk_signal": "MEDIUM", "similar_incidents_found": 0, '
              '"vendor_advisories_found": 0, "safe_operating_range": null, "key_finding": "string"}')

    response = await _call_with_retry(client, model, contents, system)
    try:
        s = json.loads(response.text)
        if isinstance(s, list): s = s[0]
    except:
        s = {}

    items = [EvidenceItem(
        source_doc=e["source_doc"], source_type=e["source_type"], title=e["title"],
        relevant_excerpt=e["relevant_excerpt"], similarity_score=e["similarity_score"],
        incident_id=e.get("incident_id"), date=e.get("date"), outcome=e.get("outcome"),
        revenue_impact=float(e["revenue_impact"]) if e.get("revenue_impact") else None,
    ) for e in top_evidence]

    report = ChronicleReport(
        evidence=items,
        historical_risk_signal=s.get("historical_risk_signal", "MEDIUM"),
        similar_incidents_found=s.get("similar_incidents_found", 0),
        vendor_advisories_found=s.get("vendor_advisories_found", 0),
        safe_operating_range=s.get("safe_operating_range"),
        key_finding=s.get("key_finding", "Historical evidence analyzed."),
    )
    logger.info(f"CHRONICLE: risk={report.historical_risk_signal}, {report.similar_incidents_found} incidents")
    return report

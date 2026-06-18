"""
Mock fallback data for the HELIOS pipeline.
Used when the Gemini API is unreachable or keys are missing (e.g., in CI environments).
"""
import json

class MockResponse:
    def __init__(self, text: str):
        self.text = text

MOCK_SENTINEL_JSON = json.dumps({
    "parameter": "authentication_timeout",
    "controls": "Duration before idle auth tokens expire.",
    "behavior_change": "Timeout drastically reduced, which may cause widespread sudden session terminations across the platform.",
    "config_type": "security",
    "semantic_severity": "HIGH"
})

MOCK_CHRONICLE_JSON = json.dumps({
    "historical_risk_signal": "HIGH",
    "similar_incidents_found": 3,
    "vendor_advisories_found": 1,
    "key_finding": "Identical timeout reductions caused complete user lockout incidents in Q2 2024."
})

MOCK_MERIDIAN_JSON = json.dumps({
    "blast_radius_score": 8.5,
    "affected_endpoints_total": 45000,
    "business_functions_at_risk": ["user_login", "checkout", "api_gateway"],
    "revenue_at_risk_per_hour": 150000.0
})

MOCK_CONTEXT_JSON = json.dumps({
    "deployment_window_risk": "HIGH",
    "context_risk_score": 85,
    "recovery_capability": "SLOW",
    "primary_expert_available": False
})

MOCK_ORACLE_JSON = json.dumps({
    "scenario_title": "Platform-Wide Authentication Collapse",
    "estimated_revenue_impact": 450000,
    "recovery_time_estimate": "3 hours",
    "confidence": "HIGH",
    "key_prediction": "Aggressive timeout coupled with absent primary engineer during peak traffic will trigger cascading token expirations and a massive spike in DB reconnects, taking down the auth gateway."
})

MOCK_ARBITER_JSON = json.dumps({
    "verdict": "BLOCK",
    "verdict_emoji": "🛑",
    "risk_score": 92,
    "confidence": "HIGH",
    "summary": "This configuration change critically reduces the authentication timeout to an unsafe level. In low-bandwidth network environments, this will result in cascading session expirations and completely lock users out of the platform.",
    "reasoning_sentinel": "Detected a dangerous reduction in `authentication_timeout` from 5s to 1s, directly impacting the core security and availability layer.",
    "reasoning_chronicle": "Found identical historical incidents (INC-2847) where a sub-3s timeout caused 22% auth failure rates and an $840k revenue loss.",
    "reasoning_meridian": "Blast radius covers all 45,000 endpoint terminals, jeopardizing $150k/hr in top-line revenue.",
    "reasoning_context": "Change proposed during a peak Friday deployment window while the primary network engineer is unavailable.",
    "reasoning_oracle": "Predicts a massive spike in database reconnects due to cascading timeouts, likely taking down the authentication gateway entirely within 3 hours.",
    "remediation_steps": [
        {
            "step_number": 1,
            "action": "Revert `authentication_timeout` to minimum safe threshold of 4.5s",
            "who": "Platform Engineering",
            "rationale": "Vendor advisory CSA-2024-001 strictly requires 4.5s minimum for mixed-network retail deployments."
        },
        {
            "step_number": 2,
            "action": "Delay deployment to Monday morning",
            "who": "Release Manager",
            "rationale": "Avoid deploying critical network boundary changes right before weekend peak traffic."
        }
    ]
})

def get_mock_response(agent_name: str) -> MockResponse:
    mocks = {
        "SENTINEL": MOCK_SENTINEL_JSON,
        "CHRONICLE": MOCK_CHRONICLE_JSON,
        "MERIDIAN": MOCK_MERIDIAN_JSON,
        "CONTEXT": MOCK_CONTEXT_JSON,
        "ORACLE": MOCK_ORACLE_JSON,
        "ARBITER": MOCK_ARBITER_JSON
    }
    return MockResponse(mocks.get(agent_name.upper(), "{}"))

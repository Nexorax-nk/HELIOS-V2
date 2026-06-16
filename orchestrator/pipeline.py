from __future__ import annotations
import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Callable, Optional

from agents.models import (
    EvaluationRequest, PipelineResult,
    SentinelReport, ChronicleReport, MeridianReport,
    ContextReport, OracleReport, ArbiterVerdict
)
from agents import sentinel, chronicle, meridian, context, oracle, arbiter
from orchestrator.band_shim import BandRoom

logger = logging.getLogger(__name__)

# SSE event broadcaster — callers register a callback to receive events
StreamCallback = Callable[[str, dict], None]


async def run_pipeline(
    request: EvaluationRequest,
    stream_callback: Optional[StreamCallback] = None,
) -> PipelineResult:
    """
    Execute the full HELIOS 6-agent pipeline using Band Multi-Agent Orchestration.
    """
    eval_id = request.eval_id or str(uuid.uuid4())[:8]
    request.eval_id = eval_id
    start_time = time.time()

    result = PipelineResult(eval_id=eval_id, request=request)
    room = BandRoom(room_id=eval_id)

    def emit(event: str, data: dict):
        if stream_callback:
            try:
                stream_callback(event, {"eval_id": eval_id, **data})
            except Exception as e:
                logger.warning(f"Stream callback error: {e}")

    logger.info(f"[{eval_id}] HELIOS pipeline starting: {request.config_file} ({request.environment})")
    emit("pipeline_start", {
        "config_file": request.config_file,
        "environment": request.environment,
        "message": f"HELIOS evaluation started for {request.config_file} via Band SDK"
    })

    # Event Handlers simulating Band Agent Subscriptions
    async def on_config_requested(req: EvaluationRequest):
        emit("agent_start", {"agent": "SENTINEL", "layer": 1, "message": "Analyzing semantic meaning of the config change..."})
        sentinel_report = await sentinel.run(req)
        result.sentinel = sentinel_report
        
        emit("agent_complete", {
            "agent": "SENTINEL", "layer": 1,
            "result": {
                "parameter": sentinel_report.parameter,
                "config_type": sentinel_report.config_type,
                "behavior_change": sentinel_report.behavior_change,
                "semantic_severity": sentinel_report.semantic_severity,
            },
            "message": f"SENTINEL: {sentinel_report.parameter} is a {sentinel_report.config_type} change."
        })
        await room.publish("SemanticAnalysisCompleted", sentinel_report)

    async def on_semantic_analysis_completed(sentinel_report: SentinelReport):
        emit("layer_start", {"layer": 2, "message": "Layer 2: Band Room broadcasting context to Layer 2 agents..."})
        
        emit("agent_start", {"agent": "CHRONICLE", "layer": 2, "message": "Querying Foundry IQ knowledge base..."})
        chronicle_report = await chronicle.run(sentinel_report)
        result.chronicle = chronicle_report
        emit("agent_complete", {
            "agent": "CHRONICLE", "layer": 2,
            "result": {"historical_risk_signal": chronicle_report.historical_risk_signal, "key_finding": chronicle_report.key_finding},
            "message": f"CHRONICLE: {chronicle_report.historical_risk_signal} historical risk"
        })
        await asyncio.sleep(15)  # Rate limit safety

        emit("agent_start", {"agent": "MERIDIAN", "layer": 2, "message": "Traversing Fabric IQ graph..."})
        meridian_report = await meridian.run(sentinel_report)
        result.meridian = meridian_report
        emit("agent_complete", {
            "agent": "MERIDIAN", "layer": 2,
            "result": {"blast_radius_score": meridian_report.blast_radius_score, "revenue_at_risk_per_hour": meridian_report.revenue_at_risk_per_hour},
            "message": f"MERIDIAN: {meridian_report.blast_radius_score} blast radius"
        })
        await asyncio.sleep(15)

        emit("agent_start", {"agent": "CONTEXT", "layer": 2, "message": "Reading Work IQ signals..."})
        context_report = await context.run(request, sentinel_report)
        result.context = context_report
        emit("agent_complete", {
            "agent": "CONTEXT", "layer": 2,
            "result": {"deployment_window_risk": context_report.deployment_window_risk, "context_risk_score": context_report.context_risk_score},
            "message": f"CONTEXT: {context_report.deployment_window_risk} deployment window"
        })
        await asyncio.sleep(15)

        await room.publish("EvidenceGathered", "All evidence collected")

    async def on_evidence_gathered(_):
        emit("agent_start", {"agent": "ORACLE", "layer": 3, "message": "Predicting real-world organizational consequences..."})
        oracle_report = await oracle.run(result.sentinel, result.chronicle, result.meridian, result.context)
        result.oracle = oracle_report
        emit("agent_complete", {
            "agent": "ORACLE", "layer": 3,
            "result": {"scenario_title": oracle_report.scenario_title, "key_prediction": oracle_report.key_prediction},
            "message": f"ORACLE: {oracle_report.key_prediction}"
        })
        await room.publish("ConsequencePredicted", oracle_report)

    async def on_consequence_predicted(_):
        emit("agent_start", {"agent": "ARBITER", "layer": 4, "message": "Synthesizing all evidence — issuing final verdict..."})
        arbiter_verdict = await arbiter.run(request, result.sentinel, result.chronicle, result.meridian, result.context, result.oracle)
        result.arbiter = arbiter_verdict
        
        execution_time = time.time() - start_time
        result.execution_time_seconds = round(execution_time, 2)
        
        emit("agent_complete", {
            "agent": "ARBITER", "layer": 4,
            "result": {"verdict": arbiter_verdict.verdict, "verdict_emoji": arbiter_verdict.verdict_emoji, "risk_score": arbiter_verdict.risk_score},
            "message": f"ARBITER: {arbiter_verdict.verdict_emoji} {arbiter_verdict.verdict} (risk={arbiter_verdict.risk_score}/100)"
        })
        await room.publish("EvaluationVerdictIssued", arbiter_verdict)

    # Register Agents to Band Room
    room.subscribe("ConfigChangeRequested", on_config_requested)
    room.subscribe("SemanticAnalysisCompleted", on_semantic_analysis_completed)
    room.subscribe("EvidenceGathered", on_evidence_gathered)
    room.subscribe("ConsequencePredicted", on_consequence_predicted)

    try:
        # Trigger the Band workflow
        await room.publish("ConfigChangeRequested", request)
        
        # Wait for the room to reach final state
        # In a real event-driven system, this would be a future/promise
        while room.get_context("EvaluationVerdictIssued") is None:
            await asyncio.sleep(0.5)

        emit("pipeline_complete", {
            "verdict": result.arbiter.verdict,
            "verdict_emoji": result.arbiter.verdict_emoji,
            "risk_score": result.arbiter.risk_score,
            "execution_time_seconds": result.execution_time_seconds,
            "message": f"Band workflow complete — Verdict: {result.arbiter.verdict_emoji} {result.arbiter.verdict}"
        })

    except Exception as e:
        result.error = str(e)
        logger.exception(f"[{eval_id}] Band pipeline error: {e}")
        emit("pipeline_error", {"error": str(e), "message": f"Band pipeline error: {e}"})

    return result

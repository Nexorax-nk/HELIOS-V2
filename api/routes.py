"""
HELIOS API Routes
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.models import EvaluationRequest, PipelineResult
from orchestrator.pipeline import run_pipeline

logger = logging.getLogger("helios.routes")
router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ──────────────────────────────────────────────────────────────────────────────

class EvaluatePayload(BaseModel):
    config_diff: str
    config_file: str
    environment: str = "production"
    current_config: Optional[str] = None
    new_config: Optional[str] = None
    deployer_id: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    repo_full_name: Optional[str] = None
    stream: bool = False  # If True, return SSE stream URL instead of waiting


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check endpoint."""
    from integrations import foundry_iq
    kb_stats = foundry_iq.collection_stats()
    return {
        "status": "ok",
        "version": "1.0.0",
        "knowledge_base": kb_stats,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# EVALUATE ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate(payload: EvaluatePayload, background_tasks: BackgroundTasks):
    """
    Run HELIOS pipeline on a config change.
    Returns the full evaluation result synchronously (use /stream/{eval_id} for live updates).
    """
    import uuid
    from api.server import broadcast_event, add_to_history

    eval_id = str(uuid.uuid4())[:8]

    request = EvaluationRequest(
        config_diff=payload.config_diff,
        config_file=payload.config_file,
        environment=payload.environment,
        current_config=payload.current_config,
        new_config=payload.new_config,
        deployer_id=payload.deployer_id,
        pr_url=payload.pr_url,
        pr_number=payload.pr_number,
        repo_full_name=payload.repo_full_name,
        eval_id=eval_id,
        timestamp=datetime.utcnow(),
    )

    result = await run_pipeline(request, stream_callback=broadcast_event)

    # Store in history
    result_dict = result.model_dump(mode="json", exclude_none=True)
    add_to_history(result_dict)

    return result_dict


# ──────────────────────────────────────────────────────────────────────────────
# SSE STREAMING
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/stream/{eval_id}")
async def stream_eval(eval_id: str):
    """
    Server-Sent Events stream for real-time pipeline progress.
    Connect before starting an evaluation to get live agent updates.
    """
    from api.server import get_event_queue

    queue = get_event_queue(eval_id)

    async def event_generator():
        yield "data: {\"event\": \"connected\", \"eval_id\": \"" + eval_id + "\"}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
                data_str = json.dumps(event)
                yield f"data: {data_str}\n\n"

                # Stop streaming when pipeline is done
                if event.get("event") in ("pipeline_complete", "pipeline_error"):
                    break
            except asyncio.TimeoutError:
                yield "data: {\"event\": \"heartbeat\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# HISTORY
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/history")
async def history():
    """Return the last 50 evaluations."""
    from api.server import _evaluation_history
    return {
        "count": len(_evaluation_history),
        "evaluations": [
            {
                "eval_id": e.get("eval_id"),
                "config_file": e.get("request", {}).get("config_file"),
                "environment": e.get("request", {}).get("environment"),
                "verdict": e.get("arbiter", {}).get("verdict") if e.get("arbiter") else None,
                "risk_score": e.get("arbiter", {}).get("risk_score") if e.get("arbiter") else None,
                "execution_time_seconds": e.get("execution_time_seconds"),
                "timestamp": e.get("request", {}).get("timestamp"),
            }
            for e in _evaluation_history
        ]
    }


# ──────────────────────────────────────────────────────────────────────────────
# GITHUB WEBHOOK
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    GitHub App webhook receiver.
    Handles pull_request events, runs HELIOS, posts PR comment.
    """
    from integrations.github_app import handle_webhook

    body = await request.body()
    headers = dict(request.headers)

    # Validate webhook signature
    signature = headers.get("x-hub-signature-256", "")

    # Process in background to return 200 immediately to GitHub
    background_tasks.add_task(handle_webhook, body, headers, signature)

    return {"status": "accepted"}

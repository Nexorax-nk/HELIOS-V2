"""
HELIOS API Server
FastAPI application with:
- POST /api/v1/evaluate — main pipeline endpoint
- POST /api/v1/webhook/github — GitHub App webhook
- GET  /api/v1/stream/{eval_id} — SSE real-time stream
- GET  /api/v1/history — recent evaluations
- GET  /api/v1/health — health check
- Static dashboard at /dashboard
"""
from __future__ import annotations
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("helios.server")

# In-memory event bus for SSE streaming
# Maps eval_id → asyncio.Queue of events
_event_queues: dict[str, asyncio.Queue] = {}
# Recent evaluations cache (last 50)
_evaluation_history: list[dict] = []


def get_event_queue(eval_id: str) -> asyncio.Queue:
    if eval_id not in _event_queues:
        _event_queues[eval_id] = asyncio.Queue()
    return _event_queues[eval_id]


def broadcast_event(event_name: str, data: dict):
    """Broadcast an SSE event to any subscriber for this eval_id."""
    eval_id = data.get("eval_id")
    if eval_id and eval_id in _event_queues:
        q = _event_queues[eval_id]
        try:
            q.put_nowait({"event": event_name, "data": data})
        except asyncio.QueueFull:
            pass  # Drop if consumer is slow


def add_to_history(result_dict: dict):
    """Add a completed evaluation to history."""
    _evaluation_history.insert(0, result_dict)
    if len(_evaluation_history) > 50:
        _evaluation_history.pop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: pre-warm ChromaDB connection."""
    logger.info("HELIOS server starting...")
    try:
        from integrations import foundry_iq
        stats = foundry_iq.collection_stats()
        logger.info(f"Foundry IQ (ChromaDB): {stats}")
    except Exception as e:
        logger.warning(f"Foundry IQ pre-warm failed: {e} — run seed_knowledge_base.py")
    yield
    logger.info("HELIOS server shutting down.")


app = FastAPI(
    title="HELIOS — Config Intelligence API",
    description="Heuristic Evaluation & Launch Intelligence for Operational Safety",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routes
from api.routes import router
app.include_router(router, prefix="/api/v1")

# Serve dashboard
dashboard_path = Path(__file__).parent.parent / "dashboard"
if dashboard_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")

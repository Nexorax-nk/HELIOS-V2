import asyncio
import logging
import os
from typing import Any
from pathlib import Path

# Fix dotenv path before importing pipeline
from dotenv import load_dotenv
load_dotenv()

from band import Agent
from band.core.simple_adapter import SimpleAdapter
from band.core.types import PlatformMessage
from band.core.protocols import AgentToolsProtocol
from band.config import load_agent_config

from agents.models import EvaluationRequest
from orchestrator.pipeline import run_pipeline
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# Suppress noisy logs for the demo
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("band").setLevel(logging.WARNING)
logging.getLogger("phoenix_channels_python_client").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

class HeliosAdapter(SimpleAdapter[Any]):
    def __init__(self):
        super().__init__()

    async def on_message(
        self,
        msg: PlatformMessage,
        tools: AgentToolsProtocol,
        history: Any,
        participants_msg: str | None,
        contacts_msg: str | None,
        *,
        is_session_bootstrap: bool,
        room_id: str,
    ) -> None:
        logger.info(f"Received message: {msg.content}")
        
        # Simple command parser
        content_lower = msg.content.lower()
        if "evaluate" in content_lower:
            filename = "demo/config_b.yaml" # default
            for word in msg.content.split():
                if word.endswith(".yaml"):
                    filename = word

            filepath = Path(filename)
            if not filepath.exists():
                await tools.send_message(f"Error: {filename} not found.", mentions=["@naveenkumarat24"])
                return

            await tools.send_message(f"Starting HELIOS evaluation for `{filename}`...", mentions=["@naveenkumarat24"])
            
            try:
                diff = filepath.read_text(encoding="utf-8")
                request = EvaluationRequest(
                    config_diff=diff,
                    config_file=filename,
                    environment="production",
                    new_config=diff,
                    deployer_id="demo-user",
                )
                
                # Run the pipeline
                result = await run_pipeline(request)
                
                # Format response
                verdict = result.arbiter.verdict if result.arbiter else "ERROR"
                score = result.arbiter.risk_score if result.arbiter else 0
                emoji = result.arbiter.verdict_emoji if result.arbiter else "❌"
                
                response = f"## HELIOS Config Safety\n\n**Verdict**: {emoji} {verdict}\n**Risk Score**: {score}/100\n\n"
                
                response += "**Agent Insights**:\n"
                if result.sentinel:
                    response += f"- **SENTINEL**: {result.sentinel.behavior_change}\n"
                if result.chronicle:
                    response += f"- **CHRONICLE**: {result.chronicle.key_finding}\n"
                if result.meridian:
                    response += f"- **MERIDIAN**: Blast Radius: {result.meridian.blast_radius_score}, Endpoints: {result.meridian.affected_endpoints_total}\n"
                if result.context:
                    response += f"- **CONTEXT**: Window Risk: {result.context.deployment_window_risk}\n"
                if result.oracle:
                    response += f"- **ORACLE**: {result.oracle.key_prediction}\n"
                    
                await tools.send_message(response, mentions=["@naveenkumarat24"])
                
            except Exception as e:
                await tools.send_message(f"Error running pipeline: {str(e)}", mentions=["@naveenkumarat24"])
                
        elif "hello" in content_lower or "hi" in content_lower:
            await tools.send_message("Hello! I am the HELIOS Orchestrator. Mention me with `evaluate demo/config_b.yaml` to run a safety evaluation on a config file.", mentions=["@naveenkumarat24"])

async def main():
    agent_id, api_key = load_agent_config("helios_orchestrator")
    adapter = HeliosAdapter()
    
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
    )
    
    logger.info("HELIOS Orchestrator is running and connected to Band! Press Ctrl+C to stop.")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())

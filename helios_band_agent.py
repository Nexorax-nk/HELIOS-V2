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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                await tools.send_message(f"@naveenkumarat24 Error: {filename} not found.")
                return

            await tools.send_message(f"@naveenkumarat24 Starting HELIOS evaluation for `{filename}`...")
            
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
                
                if result.arbiter and result.arbiter.summary:
                    response += f"**Summary**: {result.arbiter.summary}\n\n"
                    
                response += "**Reasoning Chain**:\n"
                if result.sentinel:
                    response += f"- **SENTINEL**: {result.arbiter.reasoning_sentinel if result.arbiter else ''}\n"
                if result.chronicle:
                    response += f"- **CHRONICLE**: {result.arbiter.reasoning_chronicle if result.arbiter else ''}\n"
                if result.meridian:
                    response += f"- **MERIDIAN**: {result.arbiter.reasoning_meridian if result.arbiter else ''}\n"
                if result.context:
                    response += f"- **CONTEXT**: {result.arbiter.reasoning_context if result.arbiter else ''}\n"
                if result.oracle:
                    response += f"- **ORACLE**: {result.arbiter.reasoning_oracle if result.arbiter else ''}\n"
                    
                await tools.send_message(f"@naveenkumarat24\n\n{response}")
                
            except Exception as e:
                await tools.send_message(f"@naveenkumarat24 Error running pipeline: {str(e)}")
                
        elif "hello" in content_lower or "hi" in content_lower:
            await tools.send_message("@naveenkumarat24 Hello! I am the HELIOS Orchestrator. Mention me with `evaluate demo/config_b.yaml` to run a safety evaluation on a config file.")

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

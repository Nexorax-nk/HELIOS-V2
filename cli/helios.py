"""
HELIOS CLI — Local config evaluation
Usage:
    helios evaluate ./configs/auth.yaml --env production
    helios evaluate ./configs/auth.yaml --env production --engineer EMP-001
    helios evaluate ./configs/auth.yaml --json          # raw JSON output
    helios status                                        # server health check
    helios history                                       # recent evaluations
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box

import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(highlight=False)


HELIOS_SERVER = "http://localhost:8000"


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _make_diff(old_path: Path, new_path: Path, filename: str) -> str:
    """Generate a simple unified diff from two files."""
    if not old_path.exists() or not new_path.exists():
        return new_path.read_text() if new_path.exists() else ""

    old_lines = old_path.read_text().splitlines(keepends=True)
    new_lines = new_path.read_text().splitlines(keepends=True)

    import difflib
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}"))
    return "".join(diff)


def _print_verdict(result: dict):
    """Print a rich formatted verdict report."""
    arbiter = result.get("arbiter", {})
    sentinel_data = result.get("sentinel", {})
    chronicle_data = result.get("chronicle", {})
    meridian_data = result.get("meridian", {})
    context_data = result.get("context", {})
    oracle_data = result.get("oracle", {})

    verdict = arbiter.get("verdict", "UNKNOWN")
    emoji = ""
    risk_score = arbiter.get("risk_score", 0)

    verdict_colors = {
        "SHIP": "green",
        "WARN": "yellow",
        "STAGE": "orange1",
        "BLOCK": "red",
    }
    color = verdict_colors.get(verdict, "white")

    # Header panel
    header = Text()
    header.append(f"{emoji} HELIOS VERDICT: ", style=f"bold {color}")
    header.append(verdict, style=f"bold {color}")
    header.append(f"\n\nConfig: ", style="dim")
    header.append(result.get("request", {}).get("config_file", "unknown"), style="bold")
    header.append(f"\nEnvironment: ", style="dim")
    header.append(result.get("request", {}).get("environment", "unknown"))
    header.append(f"\nRisk Score: ", style="dim")
    header.append(f"{risk_score}/100", style=f"bold {color}")
    header.append(f"\nExecution: ", style="dim")
    header.append(f"{result.get('execution_time_seconds', 0):.1f}s")

    console.print(Panel(header, title="[bold white]HELIOS Config Safety[/]", border_style=color, padding=(1, 2)))

    # Reasoning chain table
    if any([sentinel_data, chronicle_data, meridian_data, context_data, oracle_data]):
        console.print("\n[bold]Reasoning Chain[/bold]")
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("Agent", style="bold", width=12)
        table.add_column("Finding", ratio=1)

        if sentinel_data:
            table.add_row("SENTINEL", arbiter.get("reasoning_sentinel", ""))
        if chronicle_data:
            risk_emoji = {"NONE": "[OK]", "LOW": "[!]", "MEDIUM": "[!!]", "HIGH": "[WARN]", "CRITICAL": "[CRITICAL]"}.get(
                chronicle_data.get("historical_risk_signal", ""), "")
            table.add_row("CHRONICLE", f"{risk_emoji} {arbiter.get('reasoning_chronicle', '')}")
        if meridian_data:
            table.add_row("MERIDIAN", arbiter.get("reasoning_meridian", ""))
        if context_data:
            table.add_row("CONTEXT", arbiter.get("reasoning_context", ""))
        if oracle_data:
            table.add_row("ORACLE", arbiter.get("reasoning_oracle", ""))

        console.print(table)

    # Summary
    summary = arbiter.get("summary", "")
    if summary:
        console.print(f"\n[bold]Summary[/bold]")
        console.print(Panel(summary, border_style="dim"))

    # Remediation
    steps = arbiter.get("remediation_steps", [])
    if steps:
        console.print(f"\n[bold]Remediation Plan[/bold]")
        for step in steps:
            who = f" [dim](Owner: {step['who']})[/dim]" if step.get("who") else ""
            console.print(f"  [bold]{step['step_number']}.[/bold] {step['action']}{who}")
            console.print(f"     [dim]{step['rationale']}[/dim]")

    # Safe window
    safe_window = arbiter.get("safe_deployment_window")
    if safe_window:
        console.print(f"\n[bold green]Safe deployment window:[/bold green] {safe_window}")

    # Monitoring
    monitoring = arbiter.get("monitoring_recommendations", [])
    if monitoring:
        console.print(f"\n[bold]Monitor:[/bold]")
        for rec in monitoring:
            console.print(f"  * {rec}")

    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# CLI COMMANDS
# ──────────────────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0", prog_name="helios")
def cli():
    """HELIOS — Config Intelligence CLI
    
    Evaluate configuration changes for organizational safety before deployment.
    """
    pass


@cli.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--env", "-e", default="production", type=click.Choice(["production", "staging", "development"]),
              help="Target environment")
@click.option("--engineer", "-u", default=None, help="Engineer ID (e.g. EMP-001)")
@click.option("--old-config", "-o", type=click.Path(), default=None,
              help="Previous config file for diff (optional)")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
@click.option("--server", default=None, help=f"HELIOS server URL (default: {HELIOS_SERVER})")
@click.option("--local", is_flag=True, help="Run pipeline locally (no server required)")
def evaluate(config_file, env, engineer, old_config, output_json, server, local):
    """Evaluate a config file for deployment safety.
    
    CONFIG_FILE: Path to the new config file to evaluate.
    
    Examples:
    
        helios evaluate ./configs/auth.yaml --env production
        
        helios evaluate ./configs/auth.yaml --old-config ./configs/auth.yaml.bak
        
        helios evaluate ./configs/auth.yaml --json
    """
    config_path = Path(config_file)
    new_content = config_path.read_text(encoding="utf-8", errors="ignore")
    filename = config_path.name

    # Generate diff
    if old_config:
        diff = _make_diff(Path(old_config), config_path, filename)
    else:
        # Treat full file as the diff (new file or unknown baseline)
        diff = "\n".join(f"+{line}" for line in new_content.splitlines())
        diff = f"--- /dev/null\n+++ b/{filename}\n@@ -0,0 +1,{len(new_content.splitlines())} @@\n" + diff

    if local:
        asyncio.run(_run_local(filename, diff, new_content, env, engineer, output_json))
    else:
        server_url = server or HELIOS_SERVER
        asyncio.run(_run_remote(server_url, filename, diff, new_content, env, engineer, output_json))


async def _run_local(filename, diff, new_content, env, engineer, output_json):
    """Run pipeline locally without server."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from dotenv import load_dotenv
    load_dotenv()

    from agents.models import EvaluationRequest
    from orchestrator.pipeline import run_pipeline
    from datetime import datetime

    request = EvaluationRequest(
        config_diff=diff,
        config_file=filename,
        environment=env,
        new_config=new_content,
        deployer_id=engineer,
        timestamp=datetime.utcnow(),
    )

    if not output_json:
        console.print(f"\n[bold cyan]HELIOS[/bold cyan] evaluating [bold]{filename}[/bold] -> [bold]{env}[/bold]\n")

    agents_done = []
    def stream(event, data):
        if not output_json and event == "agent_complete":
            agents_done.append(data.get("agent", ""))
            console.print(f"  [dim]+ {data.get('agent', '')}:[/dim] {data.get('message', '')[:80]}")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as progress:
        if not output_json:
            task = progress.add_task("Running 6-agent pipeline...", total=None)

        result = await run_pipeline(request, stream_callback=stream)

    if output_json:
        click.echo(json.dumps(result.model_dump(mode="json", exclude_none=True), indent=2))
    else:
        _print_verdict(result.model_dump(mode="json", exclude_none=True))

    # Exit code based on verdict
    verdict = result.arbiter.verdict if result.arbiter else "WARN"
    if verdict in ("BLOCK", "STAGE"):
        sys.exit(1)


async def _run_remote(server_url, filename, diff, new_content, env, engineer, output_json):
    """Call HELIOS server API."""
    import httpx

    payload = {
        "config_diff": diff,
        "config_file": filename,
        "environment": env,
        "new_config": new_content,
        "deployer_id": engineer,
    }

    if not output_json:
        console.print(f"\n[bold cyan]HELIOS[/bold cyan] → [dim]{server_url}[/dim]")
        console.print(f"  Evaluating [bold]{filename}[/bold] ({env})...\n")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=not output_json) as progress:
        task = progress.add_task("Running HELIOS pipeline...", total=None)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{server_url}/api/v1/evaluate", json=payload)
                response.raise_for_status()
                result = response.json()
        except httpx.ConnectError:
            console.print(f"[red]Error: Cannot connect to HELIOS server at {server_url}[/red]")
            console.print("  Run locally with: [bold]helios evaluate --local ...[/bold]")
            sys.exit(2)

    if output_json:
        click.echo(json.dumps(result, indent=2))
    else:
        _print_verdict(result)

    verdict = result.get("arbiter", {}).get("verdict", "WARN")
    if verdict in ("BLOCK", "STAGE"):
        sys.exit(1)


@cli.command()
@click.option("--server", default=HELIOS_SERVER, help="HELIOS server URL")
def status(server):
    """Check HELIOS server health and knowledge base status."""
    import httpx
    try:
        response = httpx.get(f"{server}/api/v1/health", timeout=5.0)
        data = response.json()
        kb = data.get("knowledge_base", {})
        console.print(f"[green]✅ HELIOS server online[/green] — {server}")
        console.print(f"  Knowledge base: [bold]{kb.get('document_count', 0)}[/bold] chunks ({kb.get('status', 'unknown')})")
        console.print(f"  Version: {data.get('version', 'unknown')}")
    except Exception as e:
        console.print(f"[red]❌ HELIOS server offline[/red] — {server}")
        console.print(f"  Error: {e}")
        sys.exit(1)


@cli.command()
@click.option("--server", default=HELIOS_SERVER, help="HELIOS server URL")
@click.option("--limit", default=10, help="Number of evaluations to show")
def history(server, limit):
    """Show recent HELIOS evaluations."""
    import httpx
    response = httpx.get(f"{server}/api/v1/history", timeout=5.0)
    data = response.json()

    table = Table(title="Recent HELIOS Evaluations", box=box.ROUNDED)
    table.add_column("ID", style="dim")
    table.add_column("Config File")
    table.add_column("Env")
    table.add_column("Verdict")
    table.add_column("Risk")
    table.add_column("Time")

    colors = {"SHIP": "green", "WARN": "yellow", "STAGE": "orange1", "BLOCK": "red"}
    emojis = {"SHIP": "[SHIP]", "WARN": "[WARN]", "STAGE": "[STAGE]", "BLOCK": "[BLOCK]"}

    for ev in data.get("evaluations", [])[:limit]:
        verdict = ev.get("verdict", "-")
        color = colors.get(verdict, "white")
        emoji = emojis.get(verdict, "")
        table.add_row(
            ev.get("eval_id", "-"),
            ev.get("config_file", "-"),
            ev.get("environment", "-"),
            f"[{color}]{emoji} {verdict}[/]",
            f"{ev.get('risk_score', '-')}/100",
            f"{ev.get('execution_time_seconds', '-')}s",
        )

    console.print(table)


if __name__ == "__main__":
    cli()

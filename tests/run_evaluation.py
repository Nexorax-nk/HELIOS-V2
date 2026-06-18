"""
HELIOS Evaluation Runner — Accuracy Scoring Against 73-Test Suite
Run this after starting the HELIOS server to validate accuracy:

    python tests/run_evaluation.py
    python tests/run_evaluation.py --server http://localhost:8000
    python tests/run_evaluation.py --local                   # no server needed
    python tests/run_evaluation.py --category BLOCK          # single category
    python tests/run_evaluation.py --limit 10                # first N tests only
"""
from __future__ import annotations
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich import box

sys.path.insert(0, str(Path(__file__).parent.parent))

console = Console()

HELIOS_SERVER = "http://localhost:8000"
TEST_SUITE_PATH = Path(__file__).parent / "test_suite.json"


async def run_single_test(test: dict, server: Optional[str] = None, local: bool = False) -> dict:
    """Run a single test case and return result dict."""
    from datetime import datetime

    if local:
        from dotenv import load_dotenv
        load_dotenv()
        from agents.models import EvaluationRequest
        from orchestrator.pipeline import run_pipeline

        request = EvaluationRequest(
            config_diff=test["config_diff"],
            config_file=test["config_file"],
            environment="production",
            timestamp=datetime.utcnow(),
        )
        result = await run_pipeline(request)
        verdict = result.arbiter.verdict if result.arbiter else "UNKNOWN"
        risk_score = result.arbiter.risk_score if result.arbiter else 50
        exec_time = result.execution_time_seconds or 0
    else:
        import httpx
        payload = {
            "config_diff": test["config_diff"],
            "config_file": test["config_file"],
            "environment": "production",
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            t0 = time.time()
            response = await client.post(f"{server}/api/v1/evaluate", json=payload)
            exec_time = time.time() - t0
            response.raise_for_status()
            result_data = response.json()
        verdict = result_data.get("arbiter", {}).get("verdict", "UNKNOWN")
        risk_score = result_data.get("arbiter", {}).get("risk_score", 50)

    expected = test["expected_verdict"]
    passed = verdict == expected

    return {
        "id": test["id"],
        "category": test["category"],
        "config_file": test["config_file"],
        "expected": expected,
        "actual": verdict,
        "risk_score": risk_score,
        "passed": passed,
        "exec_time": exec_time,
        "reason": test["reason"],
    }


async def run_all_tests(
    tests: list[dict],
    server: Optional[str] = None,
    local: bool = False,
    concurrency: int = 3,
) -> list[dict]:
    """Run all tests with bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def bounded_run(test):
        async with semaphore:
            try:
                return await run_single_test(test, server=server, local=local)
            except Exception as e:
                return {
                    "id": test["id"],
                    "category": test["category"],
                    "config_file": test["config_file"],
                    "expected": test["expected_verdict"],
                    "actual": "ERROR",
                    "risk_score": 0,
                    "passed": False,
                    "exec_time": 0,
                    "reason": test["reason"],
                    "error": str(e),
                }

    with Progress(
        TextColumn("[bold cyan]Running tests[/]"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[dim]{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("", total=len(tests))

        tasks = [bounded_run(t) for t in tests]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            progress.advance(task)

    # Sort by test ID
    results.sort(key=lambda r: r["id"])
    return results


def print_results(results: list[dict]):
    """Print detailed results table and accuracy summary."""
    # Per-category accuracy
    categories = ["BLOCK", "WARN", "SHIP"]
    cat_stats = {}
    for cat in categories:
        cat_results = [r for r in results if r["category"] == cat]
        passed = sum(1 for r in cat_results if r["passed"])
        total = len(cat_results)
        cat_stats[cat] = {"passed": passed, "total": total, "pct": (passed / total * 100) if total else 0}

    # Overall
    total_passed = sum(1 for r in results if r["passed"])
    total = len(results)
    overall_pct = (total_passed / total * 100) if total else 0

    # False positives and negatives
    false_positives = [r for r in results if r["expected"] == "SHIP" and r["actual"] == "BLOCK"]
    false_negatives = [r for r in results if r["expected"] == "BLOCK" and r["actual"] == "SHIP"]
    wrong_verdict = [r for r in results if not r["passed"]]

    # Header
    console.print()
    console.print(Panel(
        f"[bold]HELIOS Test Suite Results[/bold]\n"
        f"[dim]73 config changes evaluated across BLOCK, WARN, and SHIP categories[/dim]",
        style="cyan"
    ))
    console.print()

    # Results table (failures only for brevity)
    if wrong_verdict:
        console.print("[bold yellow]⚠️  Incorrect Verdicts[/bold yellow]")
        fail_table = Table(box=box.ROUNDED, show_header=True, header_style="bold yellow")
        fail_table.add_column("ID", style="dim")
        fail_table.add_column("Config")
        fail_table.add_column("Expected")
        fail_table.add_column("Actual")
        fail_table.add_column("Reason")
        for r in wrong_verdict:
            fail_table.add_row(
                r["id"],
                r["config_file"],
                f"[green]{r['expected']}[/green]" if r["expected"] == "SHIP" else f"[red]{r['expected']}[/red]",
                f"[red]{r['actual']}[/red]" if r["actual"] != r["expected"] else r["actual"],
                r["reason"][:60] + "..." if len(r["reason"]) > 60 else r["reason"],
            )
        console.print(fail_table)
        console.print()

    # Accuracy summary
    summary_table = Table(title="Accuracy Summary", box=box.DOUBLE_EDGE, header_style="bold white")
    summary_table.add_column("Category", style="bold")
    summary_table.add_column("Passed", justify="center")
    summary_table.add_column("Total", justify="center")
    summary_table.add_column("Accuracy", justify="center")
    summary_table.add_column("Status", justify="center")

    for cat in categories:
        st = cat_stats[cat]
        pct = st["pct"]
        color = "green" if pct >= 90 else "yellow" if pct >= 75 else "red"
        status = "✅ PASS" if pct >= 90 else "⚠️  WARN" if pct >= 75 else "❌ FAIL"
        summary_table.add_row(
            cat,
            str(st["passed"]),
            str(st["total"]),
            f"[{color}]{pct:.1f}%[/]",
            f"[{color}]{status}[/]",
        )

    # Overall row
    overall_color = "green" if overall_pct >= 90 else "yellow" if overall_pct >= 80 else "red"
    summary_table.add_row(
        "[bold]OVERALL[/bold]",
        f"[bold]{total_passed}[/bold]",
        f"[bold]{total}[/bold]",
        f"[bold {overall_color}]{overall_pct:.1f}%[/bold {overall_color}]",
        f"[bold {overall_color}]{'✅ TARGET MET' if overall_pct >= 90 else '❌ BELOW TARGET'}[/bold {overall_color}]",
    )

    console.print(summary_table)
    console.print()

    # False positive / negative analysis
    console.print(f"[bold]Safety Analysis:[/bold]")
    console.print(f"  False positives (blocked safe changes): [{'green' if not false_positives else 'red'}]{len(false_positives)}[/] "
                  f"— HELIOS incorrectly blocked a safe change")
    console.print(f"  False negatives (shipped dangerous changes): [{'green' if not false_negatives else 'red bold'}]{len(false_negatives)}[/] "
                  f"— HELIOS incorrectly approved a dangerous change")

    avg_exec = sum(r["exec_time"] for r in results) / len(results) if results else 0
    console.print(f"\n  Average evaluation time: [bold]{avg_exec:.1f}s[/bold] per config")

    # Final verdict
    console.print()
    if overall_pct >= 94:
        console.print(Panel(
            f"[bold green]🏆 HELIOS ACCURACY: {overall_pct:.1f}%[/bold green]\n\n"
            f"Target: 94.0% | Result: {overall_pct:.1f}% | Status: EXCEEDS TARGET\n\n"
            f"False positives: {len(false_positives)} | False negatives: {len(false_negatives)}",
            border_style="green",
            title="Test Suite Complete"
        ))
    else:
        console.print(Panel(
            f"[bold yellow]⚠️  HELIOS ACCURACY: {overall_pct:.1f}%[/bold yellow]\n\n"
            f"Target: 94.0% | Result: {overall_pct:.1f}% | Status: BELOW TARGET\n\n"
            f"False positives: {len(false_positives)} | False negatives: {len(false_negatives)}\n"
            f"Review incorrect verdicts above and adjust agent prompts.",
            border_style="yellow",
            title="Test Suite Complete"
        ))


@click.command()
@click.option("--server", default=HELIOS_SERVER, help="HELIOS server URL")
@click.option("--local", is_flag=True, help="Run locally without server")
@click.option("--category", type=click.Choice(["BLOCK", "WARN", "SHIP", "ALL"]), default="ALL")
@click.option("--limit", default=0, help="Limit to first N tests (0 = all)")
@click.option("--concurrency", default=3, help="Concurrent test runs")
@click.option("--output-json", is_flag=True, help="Output raw JSON results")
def main(server, local, category, limit, concurrency, output_json):
    """Run the HELIOS 73-test evaluation suite."""
    suite = json.loads(TEST_SUITE_PATH.read_text())
    tests = suite["tests"]

    if category != "ALL":
        tests = [t for t in tests if t["category"] == category]

    if limit > 0:
        tests = tests[:limit]

    console.print(f"\n[bold cyan]HELIOS Evaluation Suite[/bold cyan]")
    console.print(f"  Tests: [bold]{len(tests)}[/bold] | Mode: [bold]{'local' if local else server}[/bold] | Concurrency: {concurrency}\n")

    t0 = time.time()
    results = asyncio.run(run_all_tests(tests, server=server if not local else None, local=local, concurrency=concurrency))
    total_time = time.time() - t0

    if output_json:
        click.echo(json.dumps(results, indent=2))
    else:
        print_results(results)
        console.print(f"  Total evaluation time: [bold]{total_time:.1f}s[/bold] for {len(tests)} tests\n")


if __name__ == "__main__":
    main()

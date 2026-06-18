"""
HELIOS Results Report Generator
Generates a professional markdown accuracy report from saved test results.

    python tests/generate_results_report.py
    python tests/generate_results_report.py --output README  # Update README directly
"""
import json
import sys
from pathlib import Path
from datetime import datetime

import click

RESULTS_PATH = Path(__file__).parent / "results" / "full_suite_results.json"
README_PATH = Path(__file__).parent.parent / "README.md"


def generate_report(results: dict) -> str:
    """Generate a markdown accuracy report from test results."""
    tests = results["results"]
    timestamp = results.get("timestamp", "Unknown")

    # Per-category stats
    categories = ["BLOCK", "WARN", "SHIP"]
    cat_stats = {}
    for cat in categories:
        cat_tests = [t for t in tests if t["category"] == cat]
        passed = sum(1 for t in cat_tests if t["passed"])
        total = len(cat_tests)
        cat_stats[cat] = {"passed": passed, "total": total,
                          "pct": (passed / total * 100) if total else 0}

    total_passed = sum(1 for t in tests if t["passed"])
    total = len(tests)
    overall_pct = (total_passed / total * 100) if total else 0

    false_positives = [t for t in tests if t["expected"] == "SHIP" and t["actual"] == "BLOCK"]
    false_negatives = [t for t in tests if t["expected"] == "BLOCK" and t["actual"] == "SHIP"]

    avg_time = sum(t.get("exec_time", 0) for t in tests) / len(tests) if tests else 0

    lines = [
        f"## Test Suite — {overall_pct:.1f}% Accuracy",
        f"",
        f"```bash",
        f"# Run the full 73-test evaluation suite",
        f"python tests/run_evaluation.py --local",
        f"",
        f"# Results (generated {timestamp}):",
        f"# ╔══════════════════════════════════════╗",
        f"# ║  HELIOS TEST SUITE RESULTS           ║",
        f"# ╠══════════════════════════════════════╣",
    ]

    for cat in categories:
        st = cat_stats[cat]
        lines.append(f"# ║  {cat:<6} accuracy: {st['pct']:>7.1f}% ({st['passed']}/{st['total']}) ║")

    lines.extend([
        f"# ║  Overall accuracy: {overall_pct:>7.1f}%         ║",
        f"# ╚══════════════════════════════════════╝",
        f"```",
        f"",
        f"The SHIP tests prove HELIOS is **precise, not paranoid** — it correctly approves safe changes.",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total tests | {total} |",
        f"| Overall accuracy | {overall_pct:.1f}% |",
        f"| False positives (blocked safe changes) | {len(false_positives)} |",
        f"| False negatives (shipped dangerous changes) | {len(false_negatives)} |",
        f"| Average eval time | {avg_time:.1f}s |",
        f"",
    ])

    # Incorrect verdicts
    wrong = [t for t in tests if not t["passed"]]
    if wrong:
        lines.append(f"<details>")
        lines.append(f"<summary>Incorrect verdicts ({len(wrong)} tests)</summary>")
        lines.append(f"")
        lines.append(f"| ID | Config | Expected | Actual | Reason |")
        lines.append(f"|-----|--------|----------|--------|--------|")
        for t in wrong:
            lines.append(f"| {t['id']} | {t['config_file']} | {t['expected']} | {t['actual']} | {t['reason'][:60]} |")
        lines.append(f"")
        lines.append(f"</details>")
        lines.append(f"")

    lines.append(f"> Full raw results: [`tests/results/full_suite_results.json`](tests/results/full_suite_results.json)")

    return "\n".join(lines)


@click.command()
@click.option("--output", type=click.Choice(["stdout", "README"]), default="stdout")
def main(output):
    if not RESULTS_PATH.exists():
        print(f"Error: {RESULTS_PATH} not found. Run the test suite first.")
        sys.exit(1)

    results = json.loads(RESULTS_PATH.read_text())
    report = generate_report(results)

    if output == "stdout":
        print(report)
    elif output == "README":
        readme = README_PATH.read_text()
        # Replace the test suite section
        marker_start = "## Test Suite"
        marker_end = "---"
        start_idx = readme.find(marker_start)
        if start_idx == -1:
            print("Could not find '## Test Suite' section in README.md")
            sys.exit(1)
        end_idx = readme.find(marker_end, start_idx + len(marker_start))
        if end_idx == -1:
            end_idx = len(readme)
        new_readme = readme[:start_idx] + report + "\n\n" + readme[end_idx:]
        README_PATH.write_text(new_readme)
        print(f"README.md updated with latest test results.")


if __name__ == "__main__":
    main()

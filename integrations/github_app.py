"""
HELIOS GitHub App Integration
Real GitHub App that:
1. Validates webhook signatures (HMAC-SHA256)
2. Parses PR events and extracts config file diffs
3. Runs HELIOS pipeline on the diff
4. Posts a formatted verdict comment on the PR
5. Creates a GitHub Check Run (can gate merging on BLOCK)

Setup:
1. Register a GitHub App at https://github.com/settings/apps/new
2. Set webhook URL to: https://<your-server>/api/v1/webhook/github
3. Generate a private key and set GITHUB_APP_PRIVATE_KEY_PATH
4. Set permissions: Pull requests (read/write), Checks (write), Contents (read)
5. Subscribe to events: Pull request
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os
import time
import jwt
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("helios.github_app")

GITHUB_API = "https://api.github.com"
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".ini", ".env", ".conf", ".cfg", ".properties"}


def _load_private_key() -> Optional[str]:
    """Load GitHub App private key from file or env var."""
    key_path = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "./github-app.private-key.pem")
    if Path(key_path).exists():
        return Path(key_path).read_text()
    # Also check env var directly (useful for cloud deployments)
    return os.getenv("GITHUB_APP_PRIVATE_KEY")


def _generate_jwt() -> str:
    """Generate a JWT for GitHub App authentication."""
    app_id = os.getenv("GITHUB_APP_ID")
    private_key = _load_private_key()

    if not app_id or not private_key:
        raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_PATH must be set")

    now = int(time.time())
    payload = {
        "iat": now - 60,  # issued at (60s ago to handle clock skew)
        "exp": now + (10 * 60),  # 10 minute expiry
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def _get_installation_token(installation_id: int) -> str:
    """Exchange a GitHub App JWT for an installation access token."""
    jwt_token = _generate_jwt()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github.v3+json",
            }
        )
        response.raise_for_status()
        return response.json()["token"]


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True

    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _get_pr_config_diff(
    token: str,
    repo_full_name: str,
    pr_number: int
) -> list[dict]:
    """
    Get all config file changes from a PR.
    Returns list of: {filename, status, patch, sha}
    """
    async with httpx.AsyncClient() as client:
        # Get PR files
        response = await client.get(
            f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/files",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={"per_page": 100}
        )
        response.raise_for_status()
        files = response.json()

    config_files = []
    for f in files:
        filename = f.get("filename", "")
        ext = Path(filename).suffix.lower()
        # Also catch files named like "Dockerfile", ".env", "config"
        is_config = (
            ext in CONFIG_EXTENSIONS
            or any(kw in filename.lower() for kw in ["config", ".env", "settings", "manifest"])
        )
        if is_config:
            config_files.append({
                "filename": filename,
                "status": f.get("status", "modified"),  # added, removed, modified
                "patch": f.get("patch", ""),  # Git diff patch
                "sha": f.get("sha", ""),
            })

    logger.info(f"GitHub: PR #{pr_number} has {len(config_files)} config file changes")
    return config_files


async def _post_pr_comment(
    token: str,
    repo_full_name: str,
    pr_number: int,
    body: str
) -> dict:
    """Post a comment on a GitHub PR."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/issues/{pr_number}/comments",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"body": body}
        )
        response.raise_for_status()
        return response.json()


async def _create_check_run(
    token: str,
    repo_full_name: str,
    head_sha: str,
    verdict: str,
    name: str,
    summary: str,
    details: str,
) -> dict:
    """Create a GitHub Check Run — can block merging if BLOCK verdict."""
    conclusion_map = {
        "SHIP": "success",
        "WARN": "success",  # Warn doesn't block, just annotates
        "STAGE": "neutral",
        "BLOCK": "failure",
    }
    conclusion = conclusion_map.get(verdict, "neutral")
    emoji_map = {"SHIP": "🟢", "WARN": "🟡", "STAGE": "🟠", "BLOCK": "🔴"}
    emoji = emoji_map.get(verdict, "⚪")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/check-runs",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "name": f"HELIOS Config Safety {emoji}",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": conclusion,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "output": {
                    "title": f"{emoji} HELIOS: {verdict}",
                    "summary": summary,
                    "text": details,
                }
            }
        )
        response.raise_for_status()
        return response.json()


def _format_pr_comment(result) -> str:
    """Format the HELIOS verdict as a beautiful GitHub PR comment (Markdown)."""
    if not result.arbiter:
        return "❌ **HELIOS evaluation failed** — check server logs."

    v = result.arbiter
    s = result.sentinel
    c = result.chronicle
    m = result.meridian
    ctx = result.context
    o = result.oracle

    verdict_headers = {
        "SHIP": "## 🟢 HELIOS: SHIP — Safe to Deploy",
        "WARN": "## 🟡 HELIOS: WARN — Deploy with Monitoring",
        "STAGE": "## 🟠 HELIOS: STAGE — Staged Rollout Required",
        "BLOCK": "## 🔴 HELIOS: BLOCK — Do Not Deploy",
    }

    lines = [
        verdict_headers.get(v.verdict, f"## HELIOS: {v.verdict}"),
        "",
        f"> {v.summary}",
        "",
        f"**Risk Score:** `{v.risk_score}/100` &nbsp;|&nbsp; **Confidence:** `{v.confidence:.0%}` &nbsp;|&nbsp; **Config:** `{result.request.config_file}`",
        "",
        "---",
        "",
        "### 🔍 Reasoning Chain",
        "",
        f"| Agent | Finding |",
        f"|-------|---------|",
    ]

    if s:
        lines.append(f"| **SENTINEL** | {v.reasoning_sentinel} |")
    if c:
        lines.append(f"| **CHRONICLE** | {v.reasoning_chronicle} |")
    if m:
        lines.append(f"| **MERIDIAN** | {v.reasoning_meridian} |")
    if ctx:
        lines.append(f"| **CONTEXT** | {v.reasoning_context} |")
    if o:
        lines.append(f"| **ORACLE** | {v.reasoning_oracle} |")

    if o and o.compounding_factors:
        lines += ["", "**⚠️ Compounding Risk Factors:**"]
        for factor in o.compounding_factors[:3]:
            lines.append(f"- {factor}")

    if v.remediation_steps:
        lines += ["", "---", "", "### 🔧 Remediation Plan", ""]
        for step in v.remediation_steps:
            who = f" *(Owner: {step.who})*" if step.who else ""
            lines.append(f"{step.step_number}. **{step.action}**{who}")
            lines.append(f"   > {step.rationale}")

    if v.staged_rollout_plan:
        sp = v.staged_rollout_plan
        lines += ["", "**Staged Rollout:**"]
        lines.append(f"- Stage 1: {sp.stage_1} ({sp.stage_1_duration}) — Success: {sp.stage_1_success_criteria}")
        if sp.stage_2:
            lines.append(f"- Stage 2: {sp.stage_2} ({sp.stage_2_duration})")
        if sp.full_rollout:
            lines.append(f"- Full rollout: {sp.full_rollout}")

    if v.monitoring_recommendations:
        lines += ["", "**📊 Monitor these metrics:**"]
        for rec in v.monitoring_recommendations:
            lines.append(f"- {rec}")

    if v.safe_deployment_window:
        lines += ["", f"**✅ Safe deployment window:** {v.safe_deployment_window}"]

    exec_time = result.execution_time_seconds or 0
    lines += [
        "",
        "---",
        f"<sub>*HELIOS evaluated in {exec_time:.1f}s — [View full report](https://github.com/your-org/helios) | Powered by HELIOS v1.0*</sub>"
    ]

    return "\n".join(lines)


async def handle_webhook(body: bytes, headers: dict, signature: str):
    """
    Main webhook handler — called in background from the API route.
    Processes GitHub PR events and runs HELIOS.
    """
    # Verify signature
    if not _verify_webhook_signature(body, signature):
        logger.warning("GitHub webhook: invalid signature — rejected")
        return

    try:
        import json
        payload = json.loads(body)
    except Exception as e:
        logger.error(f"GitHub webhook: JSON parse error: {e}")
        return

    event_type = headers.get("x-github-event", "")

    # Only handle pull_request events
    if event_type != "pull_request":
        logger.debug(f"GitHub webhook: ignoring event type '{event_type}'")
        return

    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        logger.debug(f"GitHub webhook: ignoring PR action '{action}'")
        return

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    installation = payload.get("installation", {})

    pr_number = pr.get("number")
    repo_full_name = repo.get("full_name")
    head_sha = pr.get("head", {}).get("sha")
    installation_id = installation.get("id")

    logger.info(f"GitHub webhook: PR #{pr_number} in {repo_full_name} ({action})")

    try:
        # Get installation token
        token = await _get_installation_token(installation_id)

        # Get config file changes
        config_changes = await _get_pr_config_diff(token, repo_full_name, pr_number)

        if not config_changes:
            logger.info(f"GitHub webhook: PR #{pr_number} has no config file changes — skipping HELIOS")
            return

        # Run HELIOS on each config file change (or the most significant one)
        # For demo/hackathon: evaluate the first/most significant change
        primary_change = config_changes[0]

        from agents.models import EvaluationRequest
        from orchestrator.pipeline import run_pipeline
        from api.server import broadcast_event, add_to_history

        request = EvaluationRequest(
            config_diff=primary_change["patch"],
            config_file=primary_change["filename"],
            environment="production",
            pr_url=pr.get("html_url"),
            pr_number=pr_number,
            repo_full_name=repo_full_name,
            deployer_id=pr.get("user", {}).get("login"),
            timestamp=datetime.utcnow(),
        )

        logger.info(f"GitHub webhook: running HELIOS on {primary_change['filename']}")
        result = await run_pipeline(request, stream_callback=broadcast_event)

        # Add to history
        add_to_history(result.model_dump(mode="json", exclude_none=True))

        # Format and post PR comment
        comment_body = _format_pr_comment(result)
        await _post_pr_comment(token, repo_full_name, pr_number, comment_body)
        logger.info(f"GitHub webhook: posted verdict comment on PR #{pr_number}")

        # Create Check Run (for required status checks)
        if result.arbiter and head_sha:
            await _create_check_run(
                token=token,
                repo_full_name=repo_full_name,
                head_sha=head_sha,
                verdict=result.arbiter.verdict,
                name=primary_change["filename"],
                summary=result.arbiter.summary,
                details=comment_body,
            )
            logger.info(f"GitHub webhook: created Check Run — {result.arbiter.verdict}")

    except Exception as e:
        logger.exception(f"GitHub webhook handler error: {e}")

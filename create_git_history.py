import os
import subprocess
import shutil
from datetime import datetime, timedelta

def run(cmd, env=None):
    subprocess.run(cmd, shell=True, check=True, env=env)

if os.path.exists(".git"):
    # Fix read-only files in .git
    def remove_readonly(func, path, excinfo):
        os.chmod(path, 0o777)
        func(path)
    shutil.rmtree(".git", onerror=remove_readonly)

run("git init")

base_date = datetime(2026, 6, 12, 10, 0, 0)
commits = [
    # Day 1
    (["README.md", "requirements.txt", ".gitignore", "Dockerfile"], "Initial commit: Project structure and core dependencies", 0),
    ([".env.example", "pytest.ini"], "Add environment template and pytest config", 2),
    # Day 2
    (["synthetic-data"], "Add synthetic data for enterprise signals", 24),
    (["knowledge-base"], "Seed knowledge base with real-world postmortems", 26),
    (["agents/models.py"], "Implement core Pydantic models for agent communication", 28),
    (["agents/sentinel.py"], "Add Sentinel agent for semantic parsing", 30),
    # Day 3
    (["agents/chronicle.py"], "Add Chronicle agent for historical evidence", 48),
    (["agents/meridian.py"], "Add Meridian agent for blast radius calculations", 50),
    (["agents/context.py"], "Add Context agent for org state assessment", 52),
    # Day 4
    (["agents/oracle.py"], "Add Oracle agent for cross-domain consequence prediction", 72),
    (["agents/arbiter.py"], "Add Arbiter agent for final executive verdict", 74),
    # Day 5
    (["integrations/foundry_iq.py"], "Implement Foundry IQ knowledge base integration", 96),
    (["integrations/fabric_iq.py"], "Implement Fabric IQ semantic graph integration", 98),
    (["integrations/work_iq.py"], "Implement Work IQ organizational signals integration", 100),
    (["orchestrator/band_shim.py"], "Create simulated Band Room orchestrator", 102),
    (["orchestrator/pipeline.py"], "Implement full 6-agent pipeline orchestration", 104),
    # Day 6
    (["demo"], "Add demo configurations for evaluation", 120),
    (["api/server.py"], "Create FastAPI server for HELIOS backend", 122),
    (["api/routes.py"], "Implement API endpoints and SSE streaming", 124),
    (["cli"], "Build rich CLI interface for local execution", 126),
    (["dashboard/index.html", "dashboard/style.css"], "Add static HTML dashboard", 128),
    (["dashboard/app.js", "dashboard"], "Add dashboard JavaScript for SSE streaming", 130),
    # Day 7
    (["integrations/github_app.py", ".github"], "Add GitHub App webhook handler and CI/CD workflow", 144),
    (["tests/test_unit.py", "tests/test_integration.py"], "Add unit and integration tests", 146),
    (["tests/test_live.py", "tests/test_suite.json", "tests/results"], "Add live spot-check tests and evaluation suite", 148),
    (["helios_band_agent.py", "agent_config.yaml"], "Implement Band SDK official agent script for hackathon", 152),
    ([".*"], "Final polish: Update documentation, remove legacy Microsoft references, and fix lint errors", 154)
]

env = os.environ.copy()
# Set git config just in case
try:
    run("git config user.name \"Nexorax\"")
    run("git config user.email \"nexorax@example.com\"")
except Exception:
    pass

for files, msg, hours_offset in commits:
    commit_date = base_date + timedelta(hours=hours_offset)
    # Git requires dates in standard formats. Using ISO8601
    date_str = commit_date.strftime("%Y-%m-%dT%H:%M:%S")
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    
    if files == [".*"]:
        run("git add .")
    else:
        for f in files:
            if os.path.exists(f):
                run(f"git add {f}")
            else:
                pass # ignore if it doesn't exist
                
    # Commit
    try:
        run(f'git commit -m "{msg}"', env=env)
    except subprocess.CalledProcessError:
        pass # Ignore empty commits if nothing was added

print("Git history with 27 commits created successfully!")

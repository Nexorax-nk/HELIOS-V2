/* HELIOS Dashboard — Live Pipeline App
   Handles: evaluation submission, SSE streaming, live agent updates,
   verdict rendering, history, and health checks.
*/

const API_BASE = window.location.origin + '/api/v1';

// Demo config payloads
const DEMO_A = {
  diff: `-authentication_timeout: 5s\n+authentication_timeout: 3s`,
  file: 'auth.yaml',
  env: 'production',
  note: '// The deceptive one — every traditional tool says SHIP. HELIOS says BLOCK.',
};
const DEMO_B = {
  diff: `-ui_theme: light\n+ui_theme: dark\n-log_retention_days: 14\n+log_retention_days: 30`,
  file: 'dashboard.yaml',
  env: 'production',
  note: '// The false alarm — junior engineer flagged this. HELIOS says SHIP.',
};

// ─── Health Check ────────────────────────────────────────────────────────────
async function checkHealth() {
  const dot = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      const data = await res.json();
      dot.className = 'status-dot online';
      const count = data.knowledge_base?.document_count ?? 0;
      text.textContent = `Online · ${count} KB chunks`;
    } else {
      throw new Error('Non-OK');
    }
  } catch {
    dot.className = 'status-dot error';
    text.textContent = 'Server offline';
  }
}

// ─── Demo Loaders ────────────────────────────────────────────────────────────
function loadDemoA() {
  document.getElementById('configDiff').value = DEMO_A.diff;
  document.getElementById('configFile').value = DEMO_A.file;
  document.getElementById('environment').value = DEMO_A.env;
  flashField('configDiff');
}

function loadDemoB() {
  document.getElementById('configDiff').value = DEMO_B.diff;
  document.getElementById('configFile').value = DEMO_B.file;
  document.getElementById('environment').value = DEMO_B.env;
  flashField('configDiff');
}

function flashField(id) {
  const el = document.getElementById(id);
  el.style.borderColor = '#6366f1';
  el.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.2)';
  setTimeout(() => {
    el.style.borderColor = '';
    el.style.boxShadow = '';
  }, 800);
}

// ─── Pipeline Reset ──────────────────────────────────────────────────────────
function resetPipeline() {
  const agents = ['SENTINEL', 'CHRONICLE', 'MERIDIAN', 'CONTEXT', 'ORACLE', 'ARBITER'];
  agents.forEach(name => {
    const card = document.getElementById(`agent-${name}`);
    const output = document.getElementById(`output-${name}`);
    if (card) { card.classList.remove('active', 'done'); }
    if (output) { output.classList.add('hidden'); output.innerHTML = ''; }
  });
  const log = document.getElementById('logEntries');
  log.innerHTML = '<div class="log-entry log-dim">Starting pipeline...</div>';

  // Reset verdict
  document.getElementById('verdictPlaceholder').classList.remove('hidden');
  document.getElementById('verdictResult').classList.add('hidden');
  const gauge = document.getElementById('gaugeProgress');
  if (gauge) { gauge.style.strokeDashoffset = '251.2'; gauge.style.stroke = 'var(--text-dim)'; }
}

// ─── Log Entry ────────────────────────────────────────────────────────────────
function addLog(message, type = '') {
  const log = document.getElementById('logEntries');
  const entry = document.createElement('div');
  const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
  entry.className = `log-entry log-${type || 'dim'}`;
  entry.innerHTML = `<span class="log-timestamp">${ts}</span>${message}`;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
}

// ─── Agent State ─────────────────────────────────────────────────────────────
function setAgentActive(name) {
  const card = document.getElementById(`agent-${name}`);
  if (card) { card.classList.add('active'); card.classList.remove('done'); }
  addLog(`${name}: analyzing...`, 'start');
}

function setAgentDone(name, result) {
  const card = document.getElementById(`agent-${name}`);
  const output = document.getElementById(`output-${name}`);
  if (card) { card.classList.remove('active'); card.classList.add('done'); }

  if (output && result) {
    output.classList.remove('hidden');
    output.innerHTML = formatAgentOutput(name, result);
    // Stagger animation
    output.style.animationDelay = '0ms';
  }

  const verdictEmoji = {
    SHIP: '🟢', WARN: '🟡', STAGE: '🟠', BLOCK: '🔴'
  };
  const msg = result?.message || `${name} complete`;
  const logType = name === 'ARBITER' ? (result?.verdict === 'BLOCK' ? 'error' : 'done') : 'done';
  addLog(`${name}: ${msg}`, logType);
}

function formatAgentOutput(name, result) {
  const kv = (k, v) => `<span class="agent-output-key">${k}:</span> <span class="agent-output-val">${v}</span>`;

  switch (name) {
    case 'SENTINEL':
      return [
        kv('param', result.parameter || '—'),
        kv('type', result.config_type || '—'),
        kv('severity', result.semantic_severity || '—'),
      ].join('\n');
    case 'CHRONICLE':
      return [
        kv('risk', result.historical_risk_signal || '—'),
        kv('incidents', result.similar_incidents_found ?? '—'),
        kv('advisories', result.vendor_advisories_found ?? '—'),
      ].join('\n');
    case 'MERIDIAN':
      return [
        kv('blast', result.blast_radius_score || '—'),
        kv('endpoints', (result.affected_endpoints_total ?? '—').toLocaleString?.() ?? result.affected_endpoints_total),
        kv('rev/hr', result.revenue_at_risk_per_hour != null ? `$${Math.round(result.revenue_at_risk_per_hour).toLocaleString()}` : '—'),
      ].join('\n');
    case 'CONTEXT':
      return [
        kv('window', result.deployment_window_risk || '—'),
        kv('score', result.context_risk_score != null ? `${result.context_risk_score}/100` : '—'),
        kv('recovery', result.recovery_capability || '—'),
      ].join('\n');
    case 'ORACLE':
      return [
        kv('impact', result.estimated_revenue_impact || '—'),
        kv('recovery', result.recovery_time_estimate || '—'),
        kv('confidence', result.confidence != null ? `${(result.confidence * 100).toFixed(0)}%` : '—'),
      ].join('\n');
    case 'ARBITER':
      return [
        kv('verdict', `${result.verdict_emoji || ''} ${result.verdict || '—'}`),
        kv('risk', result.risk_score != null ? `${result.risk_score}/100` : '—'),
        kv('confidence', result.confidence != null ? `${(result.confidence * 100).toFixed(0)}%` : '—'),
      ].join('\n');
    default:
      return JSON.stringify(result, null, 2).slice(0, 200);
  }
}

// ─── Render Final Verdict ────────────────────────────────────────────────────
function renderVerdict(pipelineResult) {
  const arbiter = pipelineResult.arbiter;
  if (!arbiter) return;

  const placeholder = document.getElementById('verdictPlaceholder');
  const result = document.getElementById('verdictResult');
  placeholder.classList.add('hidden');
  result.classList.remove('hidden');

  // Badge
  const badge = document.getElementById('verdictBadge');
  badge.className = `verdict-badge ${arbiter.verdict}`;
  badge.textContent = `${arbiter.verdict_emoji} ${arbiter.verdict}`;

  // Score
    // SVG Gauge Update
  const score = arbiter.risk_score;
  document.getElementById('verdictScore').textContent = score;
  const gauge = document.getElementById('gaugeProgress');
  if (gauge) {
    const circumference = 251.2; // 2 * pi * 40
    const offset = circumference - (score / 100) * circumference;
    gauge.style.strokeDashoffset = offset;
    if (score < 40) gauge.style.stroke = 'var(--ship)';
    else if (score < 70) gauge.style.stroke = 'var(--warn)';
    else gauge.style.stroke = 'var(--block)';
  }
  document.getElementById('verdictTime').textContent =
    `Evaluated in ${pipelineResult.execution_time_seconds?.toFixed(1) ?? '?'}s`;

  // Summary
  document.getElementById('verdictSummary').textContent = arbiter.summary;

  // Reasoning chain
  const chain = document.getElementById('reasoningChain');
  chain.innerHTML = '';
  const agents = ['SENTINEL', 'CHRONICLE', 'MERIDIAN', 'CONTEXT', 'ORACLE'];
  const reasons = [
    arbiter.reasoning_sentinel,
    arbiter.reasoning_chronicle,
    arbiter.reasoning_meridian,
    arbiter.reasoning_context,
    arbiter.reasoning_oracle,
  ];
  agents.forEach((name, i) => {
    if (!reasons[i]) return;
    const item = document.createElement('div');
    item.className = 'reasoning-item';
    item.style.animationDelay = `${i * 80}ms`;
    item.innerHTML = `
      <span class="reasoning-agent">${name}</span>
      <span class="reasoning-text">${reasons[i]}</span>
    `;
    chain.appendChild(item);
  });

  // Remediation
  const remSection = document.getElementById('remediationSection');
  const remSteps = document.getElementById('remediationSteps');
  if (arbiter.remediation_steps?.length) {
    remSection.classList.remove('hidden');
    remSteps.innerHTML = '';
    arbiter.remediation_steps.forEach(step => {
      const div = document.createElement('div');
      div.className = 'remediation-step';
      div.innerHTML = `
        <div class="step-num">${step.step_number}</div>
        <div class="step-content">
          <div class="step-action">${step.action}${step.who ? ` <em style="color:var(--text-dim);font-weight:400">(${step.who})</em>` : ''}</div>
          <div class="step-rationale">${step.rationale}</div>
        </div>
      `;
      remSteps.appendChild(div);
    });
  } else {
    remSection.classList.add('hidden');
  }

  // Monitoring
  const monSection = document.getElementById('monitoringSection');
  const monRecs = document.getElementById('monitoringRecs');
  if (arbiter.monitoring_recommendations?.length) {
    monSection.classList.remove('hidden');
    monRecs.innerHTML = '';
    arbiter.monitoring_recommendations.forEach(rec => {
      const div = document.createElement('div');
      div.className = 'monitoring-rec';
      div.textContent = rec;
      monRecs.appendChild(div);
    });
  } else {
    monSection.classList.add('hidden');
  }

  // Safe window
  const swSection = document.getElementById('safeWindowSection');
  if (arbiter.safe_deployment_window) {
    swSection.classList.remove('hidden');
    document.getElementById('safeWindowText').textContent = arbiter.safe_deployment_window;
  } else {
    swSection.classList.add('hidden');
  }
}

// ─── Main Evaluation ──────────────────────────────────────────────────────────
async function startEvaluation() {
  const btn = document.getElementById('evaluateBtn');
  const diff = document.getElementById('configDiff').value.trim();
  const file = document.getElementById('configFile').value.trim();
  const env = document.getElementById('environment').value;
  const engineer = document.getElementById('engineerId').value.trim();

  if (!diff) {
    addLog('Error: config diff is required', 'error');
    return;
  }

  btn.disabled = true;
  btn.querySelector('span:last-child').textContent = 'Running...';

  resetPipeline();

  const payload = {
    config_diff: diff,
    config_file: file || 'config.yaml',
    environment: env,
    deployer_id: engineer || undefined,
  };

  try {
    // POST to evaluate endpoint — this runs the full pipeline
    const res = await fetch(`${API_BASE}/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.text();
      addLog(`Server error: ${err}`, 'error');
      return;
    }

    // Stream the response as we read it for live feel,
    // but also parse the full result when done
    const pipelineResult = await res.json();
    handlePipelineResult(pipelineResult);

  } catch (err) {
    addLog(`Error: ${err.message}`, 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    btn.querySelector('span:last-child').textContent = 'Run HELIOS Pipeline';
  }
}

function handlePipelineResult(result) {
  // Animate agents in sequence based on the result data
  const sequence = [
    { name: 'SENTINEL', data: result.sentinel },
    { name: 'CHRONICLE', data: result.chronicle },
    { name: 'MERIDIAN', data: result.meridian },
    { name: 'CONTEXT', data: result.context },
    { name: 'ORACLE', data: result.oracle },
    { name: 'ARBITER', data: result.arbiter },
  ];

  let delay = 0;
  sequence.forEach(({ name, data }) => {
    if (!data) return;

    setTimeout(() => {
      setAgentActive(name);
    }, delay);

    delay += 600;

    setTimeout(() => {
      const resultForLog = {
        ...data,
        message: buildAgentMessage(name, data),
      };
      setAgentDone(name, resultForLog);
    }, delay);

    // CHRONICLE, MERIDIAN, CONTEXT run in parallel (shorter delay between them)
    if (name === 'CHRONICLE') delay -= 400;
    if (name === 'MERIDIAN') delay -= 400;

    delay += 400;
  });

  // Render full verdict after all animations
  const totalDelay = delay + 200;
  setTimeout(() => {
    renderVerdict(result);
    addLog(`Pipeline complete — ${result.arbiter?.verdict_emoji} ${result.arbiter?.verdict} (risk=${result.arbiter?.risk_score}/100)`, 'done');
    loadHistory(); // Refresh history
  }, totalDelay);
}

function buildAgentMessage(name, data) {
  switch (name) {
    case 'SENTINEL':
      return `${data.parameter} → ${data.config_type} change (${data.semantic_severity} severity)`;
    case 'CHRONICLE':
      return `${data.historical_risk_signal} historical risk — ${data.similar_incidents_found} incidents, ${data.vendor_advisories_found} advisories`;
    case 'MERIDIAN':
      return `${data.blast_radius_score} blast radius — ${(data.affected_endpoints_total ?? 0).toLocaleString()} endpoints`;
    case 'CONTEXT':
      return `${data.deployment_window_risk} window (score: ${data.context_risk_score}/100), recovery: ${data.recovery_capability}`;
    case 'ORACLE':
      return data.key_prediction;
    case 'ARBITER':
      return `${data.verdict_emoji} ${data.verdict} (risk=${data.risk_score}/100, confidence=${Math.round(data.confidence * 100)}%)`;
    default:
      return '';
  }
}

// ─── History ─────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/history`);
    const data = await res.json();
    renderHistory(data.evaluations || []);
  } catch {
    // Silently fail
  }
}

function renderHistory(evaluations) {
  const container = document.getElementById('historyContainer');
  if (!evaluations.length) {
    container.innerHTML = '<div class="history-empty">No evaluations yet. Run your first config change above.</div>';
    return;
  }

  container.innerHTML = '';
  evaluations.forEach(ev => {
    const item = document.createElement('div');
    item.className = 'history-item';
    const verdict = ev.verdict || '—';
    const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '—';
    item.innerHTML = `
      <div class="history-verdict ${verdict}">${verdict}</div>
      <div class="history-file">${ev.config_file || '—'}</div>
      <div class="history-env">${ev.environment || '—'}</div>
      <div class="history-risk">${ev.risk_score != null ? `${ev.risk_score}/100` : '—'}</div>
      <div class="history-time">${ev.execution_time_seconds ? `${ev.execution_time_seconds?.toFixed(1)}s` : '—'} · ${ts}</div>
    `;
    container.appendChild(item);
  });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
(async function init() {
  await checkHealth();
  setInterval(checkHealth, 15000);
  await loadHistory();
})();

// --- Max Level UI: Glow Tracking & 3D Tilt -----------------------------------
document.addEventListener("mousemove", (e) => {
  document.querySelectorAll(".card, .agent-card, .arch-card").forEach((card) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    card.style.setProperty("--mouse-x", ${x}px);
    card.style.setProperty("--mouse-y", ${y}px);
  });
});

document.querySelectorAll(".arch-card").forEach((card) => {
  card.addEventListener("mousemove", (e) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateX = ((y - centerY) / centerY) * -5;
    const rotateY = ((x - centerX) / centerX) * 5;
    card.style.transform = perspective(1000px) rotateX(deg) rotateY(deg) translateY(-2px);
  });
  card.addEventListener("mouseleave", () => {
    card.style.transform = perspective(1000px) rotateX(0) rotateY(0) translateY(0);
  });
});



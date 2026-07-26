(() => {
  'use strict';

  const OWNER = 'weihaochiu';
  const REPO = 'weihaochiu.github.io';
  const API_ROOT = `https://api.github.com/repos/${OWNER}/${REPO}`;
  const CACHE_KEY = 'weihaochiu-actions-monitor-v1';
  const CACHE_TTL_MS = 5 * 60 * 1000;
  const MAX_RUN_PAGES = 3;

  const FAILURE_CONCLUSIONS = new Set(['failure', 'timed_out', 'action_required', 'startup_failure']);
  const RUNNING_STATUSES = new Set(['queued', 'requested', 'waiting', 'pending', 'in_progress']);

  function safeDate(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function durationSeconds(start, end) {
    const a = safeDate(start);
    const b = safeDate(end);
    if (!a || !b) return null;
    return Math.max(0, Math.round((b.getTime() - a.getTime()) / 1000));
  }

  function median(values) {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  function getStatus(run) {
    if (!run) return { key: 'never-run', label: 'Never run', priority: 5 };
    if (RUNNING_STATUSES.has(run.status)) {
      return {
        key: run.status === 'in_progress' ? 'running' : 'queued',
        label: run.status === 'in_progress' ? 'Running' : 'Queued',
        priority: 1
      };
    }
    if (FAILURE_CONCLUSIONS.has(run.conclusion)) {
      return {
        key: 'failure',
        label: run.conclusion === 'timed_out' ? 'Timed out' : 'Failed',
        priority: 0
      };
    }
    if (run.conclusion === 'success') return { key: 'success', label: 'Success', priority: 4 };
    if (run.conclusion === 'cancelled') return { key: 'cancelled', label: 'Cancelled', priority: 2 };
    if (run.conclusion === 'skipped') return { key: 'skipped', label: 'Skipped', priority: 4 };
    return { key: run.conclusion || run.status || 'unknown', label: run.conclusion || run.status || 'Unknown', priority: 3 };
  }

  function estimateOverdue(runs, latest) {
    if (!latest || latest.status !== 'completed') return { overdue: false, expectedIntervalSeconds: null };
    const completed = runs
      .filter(run => run.status === 'completed' && run.created_at)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 8);
    if (completed.length < 3) return { overdue: false, expectedIntervalSeconds: null };

    const intervals = [];
    for (let index = 1; index < completed.length; index += 1) {
      const newer = safeDate(completed[index - 1].created_at);
      const older = safeDate(completed[index].created_at);
      if (newer && older) intervals.push((newer.getTime() - older.getTime()) / 1000);
    }
    const expected = median(intervals.filter(value => value > 0));
    if (!expected) return { overdue: false, expectedIntervalSeconds: null };

    const latestDate = safeDate(latest.created_at || latest.run_started_at);
    if (!latestDate) return { overdue: false, expectedIntervalSeconds: expected };
    const ageSeconds = (Date.now() - latestDate.getTime()) / 1000;
    const threshold = Math.max(expected * 1.75, 36 * 60 * 60);
    return { overdue: ageSeconds > threshold, expectedIntervalSeconds: expected };
  }

  async function apiFetch(path) {
    const response = await fetch(`${API_ROOT}${path}`, {
      headers: {
        Accept: 'application/vnd.github+json'
      }
    });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        if (payload && payload.message) message = payload.message;
      } catch (_) {
        // Keep the HTTP status when the response is not JSON.
      }
      const remaining = response.headers.get('x-ratelimit-remaining');
      if (response.status === 403 && remaining === '0') {
        message = 'GitHub API rate limit reached. Try again after the reset time.';
      }
      throw new Error(message);
    }
    return response.json();
  }

  async function fetchScheduledRuns() {
    const runs = [];
    let totalCount = 0;
    for (let page = 1; page <= MAX_RUN_PAGES; page += 1) {
      const payload = await apiFetch(`/actions/runs?event=schedule&exclude_pull_requests=true&per_page=100&page=${page}`);
      totalCount = Number(payload.total_count) || 0;
      const batch = Array.isArray(payload.workflow_runs) ? payload.workflow_runs : [];
      runs.push(...batch);
      if (batch.length < 100 || runs.length >= totalCount) break;
    }
    return { runs, totalCount };
  }

  async function fetchWorkflows() {
    const payload = await apiFetch('/actions/workflows?per_page=100');
    return Array.isArray(payload.workflows) ? payload.workflows : [];
  }

  function buildModel(workflows, scheduledRuns, totalScheduledRunCount) {
    const workflowById = new Map(workflows.map(workflow => [workflow.id, workflow]));
    const grouped = new Map();
    scheduledRuns.forEach(run => {
      if (!grouped.has(run.workflow_id)) grouped.set(run.workflow_id, []);
      grouped.get(run.workflow_id).push(run);
    });

    const rows = [...grouped.entries()].map(([workflowId, runs]) => {
      runs.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
      const workflow = workflowById.get(workflowId) || {};
      const latest = runs[0] || null;
      const status = getStatus(latest);
      const completed = runs.filter(run => run.status === 'completed').slice(0, 10);
      const successful = completed.filter(run => run.conclusion === 'success');
      const previousSuccess = runs.find((run, index) => index > 0 && run.status === 'completed' && run.conclusion === 'success') || null;
      const overdueInfo = estimateOverdue(runs, latest);

      return {
        workflowId,
        name: workflow.name || latest?.name || `Workflow ${workflowId}`,
        path: workflow.path || latest?.path || '',
        state: workflow.state || 'active',
        workflowUrl: workflow.html_url || '',
        latest,
        status,
        overdue: overdueInfo.overdue,
        expectedIntervalSeconds: overdueInfo.expectedIntervalSeconds,
        recentCompleted: completed.length,
        recentSuccessful: successful.length,
        successRate: completed.length ? Math.round((successful.length / completed.length) * 100) : null,
        durationSeconds: latest ? durationSeconds(latest.run_started_at || latest.created_at, latest.updated_at) : null,
        previousSuccess,
        history: runs.slice(0, 10)
      };
    });

    rows.sort((a, b) => {
      const aPriority = a.status.key === 'failure' ? 0 : a.overdue ? 1 : a.status.priority + 1;
      const bPriority = b.status.key === 'failure' ? 0 : b.overdue ? 1 : b.status.priority + 1;
      if (aPriority !== bPriority) return aPriority - bPriority;
      return String(a.name).localeCompare(String(b.name));
    });

    const summary = {
      total: rows.length,
      success: rows.filter(row => row.status.key === 'success' && !row.overdue).length,
      failed: rows.filter(row => row.status.key === 'failure').length,
      running: rows.filter(row => row.status.key === 'running' || row.status.key === 'queued').length,
      overdue: rows.filter(row => row.overdue).length,
      other: rows.filter(row => !['success', 'failure', 'running', 'queued'].includes(row.status.key) && !row.overdue).length
    };

    return {
      repository: `${OWNER}/${REPO}`,
      generatedAt: new Date().toISOString(),
      source: 'GitHub REST API',
      scope: 'scheduled-runs-only',
      totalScheduledRunCount,
      summary,
      workflows: rows
    };
  }

  function readCache() {
    try {
      const raw = sessionStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const cached = JSON.parse(raw);
      if (!cached || !cached.savedAt || !cached.model) return null;
      if (Date.now() - cached.savedAt > CACHE_TTL_MS) return null;
      return cached.model;
    } catch (_) {
      return null;
    }
  }

  function writeCache(model) {
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), model }));
    } catch (_) {
      // The dashboard still works if storage is disabled.
    }
  }

  async function load(options = {}) {
    if (!options.force) {
      const cached = readCache();
      if (cached) return cached;
    }
    const [workflows, runResult] = await Promise.all([fetchWorkflows(), fetchScheduledRuns()]);
    const model = buildModel(workflows, runResult.runs, runResult.totalCount);
    writeCache(model);
    return model;
  }

  async function loadFailureDetails(runId) {
    const payload = await apiFetch(`/actions/runs/${encodeURIComponent(runId)}/jobs?filter=latest&per_page=100`);
    const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
    const failedJobs = jobs.filter(job => FAILURE_CONCLUSIONS.has(job.conclusion));
    const details = failedJobs.map(job => ({
      id: job.id,
      name: job.name,
      conclusion: job.conclusion,
      url: job.html_url,
      failedSteps: (job.steps || [])
        .filter(step => FAILURE_CONCLUSIONS.has(step.conclusion))
        .map(step => ({ name: step.name, number: step.number, conclusion: step.conclusion }))
    }));
    return {
      jobs: details,
      primaryJob: details[0]?.name || '',
      primaryStep: details[0]?.failedSteps?.[0]?.name || ''
    };
  }

  window.ActionsData = {
    OWNER,
    REPO,
    API_ROOT,
    CACHE_TTL_MS,
    load,
    loadFailureDetails,
    getStatus
  };
})();

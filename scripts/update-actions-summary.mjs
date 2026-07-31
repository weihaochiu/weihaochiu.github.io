import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const repository = process.env.GITHUB_REPOSITORY || 'weihaochiu/weihaochiu.github.io';
const [owner, repo] = repository.split('/');
const token = process.env.GITHUB_TOKEN || '';
const outputPath = process.env.SNAPSHOT_OUTPUT || 'data/actions-summary.json';
const apiRoot = `https://api.github.com/repos/${owner}/${repo}`;
const maxRunPages = 5;
const excludedEvents = new Set([
  'workflow_dispatch',
  'pull_request',
  'pull_request_target',
  'merge_group'
]);
const excludedWorkflowPaths = new Set([
  '.github/workflows/update-actions-summary.yml'
]);
const failureConclusions = new Set([
  'failure',
  'timed_out',
  'action_required',
  'startup_failure'
]);
const runningStatuses = new Set([
  'queued',
  'requested',
  'waiting',
  'pending',
  'in_progress'
]);

async function apiFetch(apiPath) {
  const headers = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'weihaochiu-actions-summary'
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${apiRoot}${apiPath}`, { headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.message || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function safeDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

function isAutomatedRun(run) {
  return Boolean(
    run &&
    run.event &&
    !excludedEvents.has(run.event) &&
    !excludedWorkflowPaths.has(run.path)
  );
}

function statusKey(run) {
  if (!run) return 'never-run';
  if (runningStatuses.has(run.status)) {
    return run.status === 'in_progress' ? 'running' : 'queued';
  }
  if (failureConclusions.has(run.conclusion)) return 'failure';
  return run.conclusion || run.status || 'unknown';
}

function isScheduledOverdue(runs, now = Date.now()) {
  const scheduledRuns = runs.filter(run => run.event === 'schedule');
  const completed = scheduledRuns
    .filter(run => run.status === 'completed' && run.created_at)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 8);
  const latest = [...scheduledRuns]
    .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))[0];

  if (!latest || runningStatuses.has(latest.status) || completed.length < 3) return false;
  const intervals = [];
  for (let index = 1; index < completed.length; index += 1) {
    const newer = safeDate(completed[index - 1].created_at);
    const older = safeDate(completed[index].created_at);
    if (newer && older) intervals.push((newer.getTime() - older.getTime()) / 1000);
  }
  const expected = median(intervals.filter(value => value > 0));
  const latestDate = safeDate(latest.created_at || latest.run_started_at);
  if (!expected || !latestDate) return false;
  const threshold = Math.max(expected * 1.75, 36 * 60 * 60);
  return (now - latestDate.getTime()) / 1000 > threshold;
}

async function fetchRepositoryRuns() {
  const first = await apiFetch('/actions/runs?exclude_pull_requests=true&per_page=100&page=1');
  const totalCount = Number(first.total_count) || 0;
  const pageCount = Math.min(maxRunPages, Math.max(1, Math.ceil(totalCount / 100)));
  const remaining = pageCount > 1
    ? await Promise.all(
        Array.from({ length: pageCount - 1 }, (_, index) =>
          apiFetch(`/actions/runs?exclude_pull_requests=true&per_page=100&page=${index + 2}`)
        )
      )
    : [];
  return {
    runs: [
      ...(Array.isArray(first.workflow_runs) ? first.workflow_runs : []),
      ...remaining.flatMap(payload =>
        Array.isArray(payload.workflow_runs) ? payload.workflow_runs : []
      )
    ],
    totalCount
  };
}

async function existingSnapshot() {
  try {
    return JSON.parse(await readFile(outputPath, 'utf8'));
  } catch (_) {
    return null;
  }
}

const [{ runs, totalCount }, previous] = await Promise.all([
  fetchRepositoryRuns(),
  existingSnapshot()
]);
const automatedRuns = runs.filter(isAutomatedRun);
const grouped = new Map();
for (const run of automatedRuns) {
  if (!grouped.has(run.workflow_id)) grouped.set(run.workflow_id, []);
  grouped.get(run.workflow_id).push(run);
}

const rows = [...grouped.values()].map(workflowRuns => {
  workflowRuns.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  const latest = workflowRuns[0] || null;
  return {
    status: statusKey(latest),
    overdue: isScheduledOverdue(workflowRuns)
  };
});
const summary = {
  total: rows.length,
  success: rows.filter(row => row.status === 'success' && !row.overdue).length,
  failed: rows.filter(row => row.status === 'failure').length,
  running: rows.filter(row => row.status === 'running' || row.status === 'queued').length,
  overdue: rows.filter(row => row.overdue).length,
  other: rows.filter(row =>
    !['success', 'failure', 'running', 'queued'].includes(row.status) && !row.overdue
  ).length
};
const snapshot = {
  schemaVersion: 1,
  repository,
  generatedAt: new Date().toISOString(),
  source: 'GitHub Actions scheduled snapshot',
  scope: 'automated-runs-manual-pr-and-summary-updater-excluded',
  totalRepositoryRunCount: totalCount,
  inspectedRunCount: runs.length,
  automatedRunCount: automatedRuns.length,
  excludedRunCount: runs.length - automatedRuns.length,
  runHistoryTruncated: runs.length < totalCount,
  summary
};

if (
  previous &&
  JSON.stringify({ ...previous, generatedAt: null }) ===
    JSON.stringify({ ...snapshot, generatedAt: null })
) {
  console.log('Actions summary is unchanged.');
  process.exit(0);
}

await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(snapshot, null, 2)}\n`, 'utf8');
console.log(`Updated ${outputPath}.`);

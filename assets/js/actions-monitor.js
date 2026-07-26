(() => {
  'use strict';

  const REFRESH_WHILE_RUNNING_MS = 10 * 60 * 1000;
  const failureDetails = new Map();
  let model = null;
  let visibleRows = [];
  let timer = null;

  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  function formatDateTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Taipei',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false
    }).format(date).replace(',', '');
  }

  function formatDuration(seconds) {
    if (!Number.isFinite(seconds)) return '—';
    const total = Math.max(0, Math.round(seconds));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours) return `${hours}h ${minutes}m`;
    if (minutes) return `${minutes}m ${secs}s`;
    return `${secs}s`;
  }

  function formatTrigger(value) {
    const labels = {
      schedule: 'Schedule',
      push: 'Push',
      workflow_run: 'Workflow run',
      workflow_call: 'Workflow call',
      repository_dispatch: 'Repository dispatch',
      pages_build: 'Pages build',
      dynamic: 'GitHub internal'
    };
    return labels[value] || String(value || 'Unknown').replaceAll('_', ' ');
  }

  function rowState(row) {
    if (row.status.key === 'failure') return 'failure';
    if (row.overdue) return 'overdue';
    if (row.status.key === 'running' || row.status.key === 'queued') return 'running';
    return row.status.key;
  }

  function badge(row) {
    const state = rowState(row);
    const label = row.overdue && row.status.key === 'success' ? 'Overdue' : row.status.label;
    return `<span class="action-status-badge status-${esc(state)}">${esc(label)}</span>`;
  }

  function successRate(row) {
    if (row.successRate === null) return '—';
    return `${row.successRate}% (${row.recentSuccessful}/${row.recentCompleted})`;
  }

  function failedStep(row) {
    if (row.status.key !== 'failure') return '—';
    const detail = failureDetails.get(row.latest.id);
    if (!detail) return '<span class="muted-text">Loading…</span>';
    return esc(detail.primaryStep || detail.primaryJob || 'See GitHub run');
  }

  function renderSummary() {
    if (!model) return;
    const values = {
      monitorTotal: model.summary.total,
      monitorFailed: model.summary.failed,
      monitorRunning: model.summary.running,
      monitorOverdue: model.summary.overdue
    };
    Object.entries(values).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) element.textContent = String(value);
    });
    const updated = $('#monitorUpdated');
    if (updated) updated.textContent = formatDateTime(model.generatedAt);
  }

  function applyFilters() {
    if (!model) return;
    const query = ($('#actionsSearch')?.value || '').trim().toLowerCase();
    const status = $('#actionsStatusFilter')?.value || 'all';
    visibleRows = model.workflows.filter(row => {
      const state = rowState(row);
      const matchesStatus = status === 'all' || state === status;
      const haystack = `${row.name} ${row.path} ${row.latest?.head_branch || ''} ${row.latest?.conclusion || ''} ${row.latest?.event || ''} ${row.triggerEvents.join(' ')}`.toLowerCase();
      return matchesStatus && (!query || haystack.includes(query));
    });
    renderTable();
  }

  function renderTable() {
    const body = $('#actionsTableBody');
    if (!body) return;
    if (!visibleRows.length) {
      body.innerHTML = '<tr><td colspan="9" class="empty-cell">No automated workflows match the current filter.</td></tr>';
      const count = $('#actionsTableCount');
      if (count) count.textContent = '0 workflows';
      return;
    }

    body.innerHTML = visibleRows.map((row, index) => {
      const run = row.latest || {};
      const detailId = `action-detail-${index}`;
      const runUrl = run.html_url || row.workflowUrl || '#';
      return `
        <tr data-workflow-id="${esc(row.workflowId)}">
          <td>${badge(row)}</td>
          <td><strong class="workflow-name">${esc(row.name)}</strong><br><span class="workflow-path">${esc(row.path || 'Workflow path unavailable')}</span></td>
          <td>${esc(formatTrigger(run.event))}</td>
          <td>${esc(formatDateTime(run.updated_at || run.created_at))}</td>
          <td class="numeric-cell">${esc(formatDuration(row.durationSeconds))}</td>
          <td>${esc(successRate(row))}</td>
          <td>${failedStep(row)}</td>
          <td>${esc(run.head_branch || '—')}</td>
          <td class="action-links">
            <a href="${esc(runUrl)}" target="_blank" rel="noopener noreferrer">View run</a>
            <button type="button" data-detail="${esc(detailId)}">Details</button>
            <button type="button" data-copy="${esc(row.workflowId)}">Copy diagnostics</button>
          </td>
        </tr>
        <tr class="action-detail-row" id="${esc(detailId)}" hidden>
          <td colspan="9">${detailMarkup(row)}</td>
        </tr>`;
    }).join('');

    body.querySelectorAll('[data-detail]').forEach(button => {
      button.addEventListener('click', () => {
        const target = document.getElementById(button.dataset.detail);
        if (!target) return;
        target.hidden = !target.hidden;
        button.textContent = target.hidden ? 'Details' : 'Hide';
      });
    });
    body.querySelectorAll('[data-copy]').forEach(button => {
      button.addEventListener('click', () => copyDiagnostics(Number(button.dataset.copy), button));
    });
    const count = $('#actionsTableCount');
    if (count) count.textContent = `${visibleRows.length} workflow${visibleRows.length === 1 ? '' : 's'}`;
  }

  function detailMarkup(row) {
    const run = row.latest || {};
    const detail = failureDetails.get(run.id) || { primaryJob: '', primaryStep: '', jobs: [] };
    const jobHtml = detail.jobs?.length ? detail.jobs.map(job => `
      <div class="failure-job"><strong>${esc(job.name)}</strong>${job.failedSteps.length
        ? `<ul>${job.failedSteps.map(step => `<li>${esc(step.name)} <span>(${esc(step.conclusion)})</span></li>`).join('')}</ul>`
        : '<p>No failed step summary was returned by the API.</p>'}</div>`).join('') : '';
    const cadence = row.hasScheduledRuns
      ? (row.expectedIntervalSeconds ? `About ${esc(formatDuration(row.expectedIntervalSeconds))}` : 'Not enough scheduled history')
      : 'Not applicable to event-based workflow';
    return `<div class="diagnostic-grid">
      <div><span>Workflow file</span><strong>${esc(row.path || '—')}</strong></div>
      <div><span>Run ID / attempt</span><strong>${esc(run.id || '—')} / ${esc(run.run_attempt || 1)}</strong></div>
      <div><span>Head SHA</span><strong class="mono-text">${esc(run.head_sha || '—')}</strong></div>
      <div><span>Trigger</span><strong>${esc(formatTrigger(run.event))}</strong></div>
      <div><span>Started</span><strong>${esc(formatDateTime(run.run_started_at || run.created_at))}</strong></div>
      <div><span>Completed</span><strong>${esc(formatDateTime(run.updated_at))}</strong></div>
      <div><span>Previous success</span><strong>${row.previousSuccess?.html_url ? `<a href="${esc(row.previousSuccess.html_url)}" target="_blank" rel="noopener noreferrer">View run</a>` : '—'}</strong></div>
      <div><span>Observed schedule cadence</span><strong>${cadence}</strong></div>
    </div>${jobHtml ? `<div class="failure-details"><h3>Failed job and step</h3>${jobHtml}</div>` : ''}`;
  }

  async function loadFailureRows() {
    if (!model) return;
    const failed = model.workflows.filter(row => row.status.key === 'failure' && row.latest?.id);
    await Promise.allSettled(failed.map(async row => {
      if (!failureDetails.has(row.latest.id)) {
        const details = await window.ActionsData.loadFailureDetails(row.latest.id);
        failureDetails.set(row.latest.id, details);
      }
    }));
  }

  function diagnosticText(row) {
    const run = row.latest || {};
    const detail = failureDetails.get(run.id) || {};
    return [
      `Repository: ${model.repository}`,
      `Workflow: ${row.name}`,
      `Workflow file: ${row.path || 'Unavailable'}`,
      `Trigger: ${run.event || 'Unavailable'}`,
      `Status: ${run.status || 'Unavailable'}`,
      `Conclusion: ${run.conclusion || 'Unavailable'}`,
      `Run ID: ${run.id || 'Unavailable'}`,
      `Run attempt: ${run.run_attempt || 1}`,
      `Run URL: ${run.html_url || 'Unavailable'}`,
      `Branch: ${run.head_branch || 'Unavailable'}`,
      `Head SHA: ${run.head_sha || 'Unavailable'}`,
      `Started: ${formatDateTime(run.run_started_at || run.created_at)} Asia/Taipei`,
      `Completed: ${formatDateTime(run.updated_at)} Asia/Taipei`,
      `Duration: ${formatDuration(row.durationSeconds)}`,
      `Failed job: ${detail.primaryJob || 'Not returned by API'}`,
      `Failed step: ${detail.primaryStep || 'Not returned by API'}`,
      `Previous successful run: ${row.previousSuccess?.html_url || 'Unavailable'}`
    ].join('\n');
  }

  async function copyDiagnostics(workflowId, button) {
    const row = model?.workflows.find(item => item.workflowId === workflowId);
    if (!row) return;
    try {
      if (row.status.key === 'failure' && row.latest?.id && !failureDetails.has(row.latest.id)) {
        button.disabled = true;
        button.textContent = 'Loading…';
        failureDetails.set(row.latest.id, await window.ActionsData.loadFailureDetails(row.latest.id));
      }
      await navigator.clipboard.writeText(diagnosticText(row));
      button.textContent = 'Copied';
      window.setTimeout(() => { button.textContent = 'Copy diagnostics'; }, 1800);
    } catch (_) {
      button.textContent = 'Copy failed';
      window.setTimeout(() => { button.textContent = 'Copy diagnostics'; }, 1800);
    } finally {
      button.disabled = false;
    }
  }

  function setInitialFilterFromUrl() {
    const value = new URLSearchParams(window.location.search).get('status');
    const select = $('#actionsStatusFilter');
    if (select && ['all', 'failure', 'running', 'overdue', 'success', 'cancelled'].includes(value)) select.value = value;
  }

  async function load(force = false) {
    const status = $('#actionsMonitorStatus');
    const refresh = $('#refreshActionsMonitor');
    if (status) {
      status.className = 'monitor-status';
      status.textContent = force ? 'Refreshing automated Actions…' : 'Loading automated Actions…';
    }
    if (refresh) refresh.disabled = true;
    try {
      model = await window.ActionsData.load({ force });
      renderSummary();
      applyFilters();
      await loadFailureRows();
      applyFilters();
      if (status) {
        const partial = model.runHistoryTruncated ? ' · history limited to the most recent 500 runs' : '';
        status.textContent = `Automated runs · manual and PR runs excluded · ${model.automatedRunCount} runs inspected${partial} · Cached for 5 minutes`;
      }
      if (timer) window.clearTimeout(timer);
      if (model.summary.running > 0) timer = window.setTimeout(() => load(true), REFRESH_WHILE_RUNNING_MS);
    } catch (error) {
      if (status) {
        status.className = 'monitor-status monitor-status-error';
        status.textContent = `Unable to load GitHub Actions status: ${error.message}`;
      }
    } finally {
      if (refresh) refresh.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    setInitialFilterFromUrl();
    $('#actionsSearch')?.addEventListener('input', applyFilters);
    $('#actionsStatusFilter')?.addEventListener('change', applyFilters);
    $('#refreshActionsMonitor')?.addEventListener('click', () => load(true));
    load(false);
  });
})();

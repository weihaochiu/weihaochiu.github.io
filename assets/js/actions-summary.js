(() => {
  'use strict';

  const SNAPSHOT_URL = 'data/actions-summary.json';
  const FALLBACK_CACHE_KEY = 'weihaochiu-actions-summary-snapshot-v1';

  const $ = selector => document.querySelector(selector);

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

  function setCard(id, value, note) {
    const card = document.getElementById(id);
    if (!card) return;
    const number = card.querySelector('[data-card-value]');
    const small = card.querySelector('small');
    if (number) number.textContent = String(value ?? '—');
    if (small && note) small.textContent = note;
  }

  function render(model) {
    const { summary } = model;
    setCard('actionsTotalCard', summary.total, 'Automated workflows observed');
    setCard('actionsSuccessCard', summary.success, 'Latest automated run succeeded');
    setCard('actionsFailedCard', summary.failed, summary.failed ? 'Review required' : 'No current failures');
    setCard('actionsRunningCard', summary.running, summary.running ? 'Automatic recheck in 10 minutes' : 'Nothing queued or running');
    setCard('actionsOverdueCard', summary.overdue, summary.overdue ? 'Scheduled cadence appears late' : 'No scheduled workflow overdue');

    const updated = $('#actionsSummaryUpdated');
    if (updated) updated.textContent = formatDateTime(model.generatedAt);
    const scope = $('#actionsSummaryScope');
    if (scope) {
      const partial = model.runHistoryTruncated ? ' · partial history' : '';
      scope.textContent = `Automated runs · manual and PR runs excluded · ${model.automatedRunCount} runs inspected${partial}`;
    }
    const status = $('#actionsSummaryStatus');
    if (status) {
      status.className = 'admin-status';
      status.textContent = 'Loaded instantly from the latest scheduled status snapshot.';
    }
  }

  function readFallback() {
    try {
      const raw = localStorage.getItem(FALLBACK_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function writeFallback(model) {
    try {
      localStorage.setItem(FALLBACK_CACHE_KEY, JSON.stringify(model));
    } catch (_) {
      // The page remains usable when localStorage is unavailable.
    }
  }

  async function load() {
    const status = $('#actionsSummaryStatus');
    if (status) {
      status.className = 'admin-status';
      status.textContent = 'Loading the latest automated Actions snapshot…';
    }
    try {
      const response = await fetch(SNAPSHOT_URL, { cache: 'no-cache' });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const model = await response.json();
      if (!model || !model.summary) throw new Error('Snapshot data is incomplete.');
      writeFallback(model);
      render(model);
    } catch (error) {
      const fallback = readFallback();
      if (fallback && fallback.summary) {
        render(fallback);
        if (status) {
          status.className = 'admin-status admin-status-error';
          status.textContent = `Showing the last saved snapshot because the latest file could not be loaded: ${error.message}`;
        }
        return;
      }
      if (status) {
        status.className = 'admin-status admin-status-error';
        status.textContent = `Unable to load the automated Actions snapshot: ${error.message}`;
      }
    }
  }

  document.addEventListener('DOMContentLoaded', load);
})();

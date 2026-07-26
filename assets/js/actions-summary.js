(() => {
  'use strict';

  const REFRESH_WHILE_RUNNING_MS = 10 * 60 * 1000;
  let timer = null;

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
    setCard('actionsTotalCard', summary.total, 'Scheduled workflows observed');
    setCard('actionsSuccessCard', summary.success, 'Latest scheduled run succeeded');
    setCard('actionsFailedCard', summary.failed, summary.failed ? 'Review required' : 'No current failures');
    setCard('actionsRunningCard', summary.running, summary.running ? 'Automatic recheck in 10 minutes' : 'Nothing queued or running');
    setCard('actionsOverdueCard', summary.overdue, summary.overdue ? 'Later than observed cadence' : 'No overdue workflows');

    const updated = $('#actionsSummaryUpdated');
    if (updated) updated.textContent = formatDateTime(model.generatedAt);
    const scope = $('#actionsSummaryScope');
    if (scope) scope.textContent = `Scheduled runs only · ${model.totalScheduledRunCount} recent runs inspected`;
    const status = $('#actionsSummaryStatus');
    if (status) {
      status.className = 'admin-status';
      status.textContent = 'Loaded from the GitHub Actions API. Results are cached in this tab for 5 minutes.';
    }

    if (timer) window.clearTimeout(timer);
    if (summary.running > 0) {
      timer = window.setTimeout(() => load(true), REFRESH_WHILE_RUNNING_MS);
    }
  }

  async function load(force = false) {
    const status = $('#actionsSummaryStatus');
    if (status) {
      status.className = 'admin-status';
      status.textContent = force ? 'Refreshing scheduled Actions status…' : 'Loading scheduled Actions status…';
    }
    const button = $('#refreshActionsSummary');
    if (button) button.disabled = true;
    try {
      render(await window.ActionsData.load({ force }));
    } catch (error) {
      if (status) {
        status.className = 'admin-status admin-status-error';
        status.textContent = `Unable to load GitHub Actions status: ${error.message}`;
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    $('#refreshActionsSummary')?.addEventListener('click', () => load(true));
    load(false);
  });
})();

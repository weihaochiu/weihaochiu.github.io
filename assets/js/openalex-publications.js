(() => {
  'use strict';

  const DATA_URL = 'data/openalex_publication_metrics.json';
  const CONTAINER_ID = 'collectionContainer';

  function normalizeDoi(value) {
    return String(value || '')
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\/(dx\.)?doi\.org\//, '')
      .replace(/^doi:/, '');
  }

  function doiFromCard(card) {
    const doiLink = [...card.querySelectorAll('.card-actions a')].find(link => {
      try {
        return /(^|\.)doi\.org$/i.test(new URL(link.href).hostname);
      } catch (error) {
        return false;
      }
    });
    return normalizeDoi(doiLink?.href);
  }

  function validOpenAlexUrl(value) {
    try {
      const url = new URL(String(value || ''));
      return url.protocol === 'https:' && url.hostname === 'openalex.org' && /^\/W\d+\/?$/.test(url.pathname)
        ? url.toString()
        : '';
    } catch (error) {
      return '';
    }
  }

  function makeCitationLink(record) {
    const count = Number(record?.citationCount);
    const url = validOpenAlexUrl(record?.url);
    if (record?.status !== 'verified' || !Number.isInteger(count) || count < 0 || !url) return null;

    const link = document.createElement('a');
    link.className = 'action openalex-citation-action';
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.dataset.openalexCitation = '';
    link.textContent = `${count.toLocaleString()} OpenAlex citation${count === 1 ? '' : 's'} ↗`;
    link.setAttribute(
      'aria-label',
      `${count.toLocaleString()} OpenAlex citation${count === 1 ? '' : 's'}; open the OpenAlex work record`
    );
    return link;
  }

  function applyMetrics(records) {
    const container = document.getElementById(CONTAINER_ID);
    if (!container) return;

    container.querySelectorAll('.publication-card').forEach(card => {
      const actions = card.querySelector('.card-actions');
      if (!actions || actions.querySelector('[data-openalex-citation]')) return;

      const doi = doiFromCard(card);
      const link = makeCitationLink(records[doi]);
      if (!link) return;

      const scholarAction = [...actions.children].find(element =>
        /Google Scholar citation/i.test(element.textContent || '')
      );
      if (scholarAction) scholarAction.insertAdjacentElement('afterend', link);
      else actions.appendChild(link);
    });
  }

  async function loadMetrics() {
    const response = await fetch(DATA_URL, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Unable to load OpenAlex publication metrics (${response.status})`);
    const payload = await response.json();
    return payload?.records && typeof payload.records === 'object' ? payload.records : {};
  }

  document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById(CONTAINER_ID);
    if (!container) return;

    try {
      const records = await loadMetrics();
      let scheduled = false;
      const refresh = () => {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {
          scheduled = false;
          applyMetrics(records);
        });
      };

      const observer = new MutationObserver(refresh);
      observer.observe(container, { childList: true, subtree: true });
      refresh();
    } catch (error) {
      console.warn('OpenAlex publication citations are unavailable:', error);
    }
  });
})();

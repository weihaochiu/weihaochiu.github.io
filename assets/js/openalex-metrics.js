(() => {
  'use strict';

  const DATA_PATH = 'data/openalex_metrics.json';
  const REMOTE_DATA_PATH = 'https://weihaochiu.github.io/data/openalex_metrics.json';

  const setText = (selector, value, formatter = String) => {
    if (value === undefined || value === null || value === '') return;
    document.querySelectorAll(selector).forEach((element) => {
      element.textContent = formatter(value);
    });
  };

  const loadJson = async (url) => {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Unable to load ${url}`);
    return response.json();
  };

  const loadMetrics = async () => {
    try {
      return await loadJson(DATA_PATH);
    } catch (localError) {
      return loadJson(REMOTE_DATA_PATH);
    }
  };

  const validCount = (value) => Number.isInteger(Number(value)) && Number(value) >= 0;

  const initialize = async () => {
    try {
      const metrics = await loadMetrics();
      if (!metrics || metrics.status !== 'success') return;

      if (validCount(metrics.citations)) {
        setText('[data-openalex-citations]', Number(metrics.citations), (value) => value.toLocaleString());
      }
      if (validCount(metrics.hIndex)) setText('[data-openalex-h]', Number(metrics.hIndex));
      if (validCount(metrics.i10Index)) setText('[data-openalex-i10]', Number(metrics.i10Index));

      if (typeof metrics.profileUrl === 'string' && /^https:\/\/openalex\.org\/A\d+$/i.test(metrics.profileUrl)) {
        document.querySelectorAll('[data-openalex-profile-link]').forEach((link) => {
          link.href = metrics.profileUrl;
        });
      }

      const card = document.querySelector('[data-openalex-profile-link]');
      if (card && metrics.lastSuccessfulUpdate) {
        card.title = `OpenAlex metrics updated ${metrics.lastSuccessfulUpdate}`;
      }
    } catch (error) {
      // Keep the static em-dash fallback. Other website functions remain unaffected.
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();

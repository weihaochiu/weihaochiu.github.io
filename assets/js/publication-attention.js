/* DOI-based official widgets. No metric values are stored or inferred locally. */
(() => {
  'use strict';
  const source = document.currentScript.src;
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = new URL('../css/publication-attention.css?v=20261023-3', source).href;
  document.head.appendChild(css);
  const mobile = window.matchMedia('(max-width:760px)');
  const plumConfig = () => JSON.stringify({printSize:'medium', popupDirection:mobile.matches ? 'top' : 'left', hideWhenEmpty:true});
  mobile.addEventListener('change', () => {
    document.querySelectorAll('.publication-attention plumx-widget').forEach(widget => widget.setAttribute('config', plumConfig()));
  });
  let started = false;
  function loadScript(src, onload) {
    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    if (onload) script.onload = onload;
    document.head.appendChild(script);
  }
  function enhance() {
    let added = false;
    document.querySelectorAll('.publication-card:not([data-attention-ready])').forEach(card => {
      card.dataset.attentionReady = 'true';
      if (card.classList.contains('thesis-publication-card') || card.classList.contains('thesis-detail')) return;
      const link = card.querySelector('.card-actions a[href^="https://doi.org/"], .card-actions a[href^="http://doi.org/"], .card-actions a[href^="https://dx.doi.org/"]');
      if (!link) return;
      let doi;
      try { doi = decodeURIComponent(new URL(link.href).pathname.slice(1)); } catch { return; }
      if (!/^10\.\d{4,9}\/\S+$/i.test(doi)) return;
      const rail = document.createElement('aside');
      rail.className = 'publication-attention';
      rail.setAttribute('aria-label', 'Research attention: PlumX and Altmetric');
      let plum = document.createElement('plumx-widget');
      Object.entries({type:'artifact', 'identifier-type':'doi', identifier:doi, display:'plumprint', config:plumConfig()}).forEach(([key,value]) => plum.setAttribute(key,value));
      let retries = 0;
      const bindPlum = () => {
        plum.addEventListener('plumx:load', () => {
          plum.hidden = false;
          card.classList.add('has-attention');
        });
        plum.addEventListener('plumx:empty', () => { plum.hidden = true; });
        plum.addEventListener('plumx:error', event => {
          plum.hidden = true;
          // The provider caches aborted/failed requests for five seconds. A list
          // filter can disconnect a pending widget; remount after that cache expires.
          if (event.detail?.code === 'ARTIFACT_NOT_FOUND' || retries++ >= 1) return;
          setTimeout(() => {
            if (!plum.isConnected) return;
            const replacement = document.createElement('plumx-widget');
            for (const attribute of plum.attributes) {
              if (attribute.name !== 'hidden') replacement.setAttribute(attribute.name, attribute.value);
            }
            const previous = plum;
            plum = replacement;
            bindPlum();
            previous.replaceWith(plum);
          }, 5500);
        });
      };
      bindPlum();
      const alt = document.createElement('div');
      alt.className = 'altmetric-embed';
      Object.entries({doi, 'badge-type':'donut', 'badge-popover':'top', 'hide-no-mentions':'true', 'link-target':'_blank'}).forEach(([key,value]) => alt.setAttribute('data-'+key,value));
      rail.append(plum, alt);
      if (card.classList.contains('publication-detail')) {
        const overview = document.createElement('div');
        overview.className = 'publication-detail-overview';
        const information = document.createElement('div');
        information.className = 'publication-detail-information';
        // Keep metrics beside bibliographic information, leaving the full body width.
        while (card.firstElementChild && !card.firstElementChild.matches('.publication-detail-section, .publication-detail-actions, .publication-return')) {
          information.appendChild(card.firstElementChild);
        }
        overview.append(information, rail);
        card.prepend(overview);
      } else card.appendChild(rail);
      added = true;
    });
    if (!added) return;
    if (!started) {
      started = true;
      loadScript('https://plumx.elsevier.com/widget/plumx-widget.js');
      loadScript('https://d1bxh8uas1mnw7.cloudfront.net/assets/embed.js', () => window._altmetric_embed_init?.());
    } else window._altmetric_embed_init?.();
  }
  let queued = false;
  const observer = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; enhance(); });
  });
  async function start() {
    // Do not start provider requests on static cards that initCollection replaces.
    await window.publicationCollectionReady;
    enhance();
    observer.observe(document.body, {childList:true,subtree:true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();

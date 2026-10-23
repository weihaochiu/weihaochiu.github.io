/* DOI-based official widgets. No metric values are stored or inferred locally. */
(() => {
  'use strict';
  const source = document.currentScript.src;
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = new URL('../css/publication-attention.css?v=20261023-2', source).href;
  document.head.appendChild(css);
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
      const plum = document.createElement('plumx-widget');
      Object.entries({type:'artifact', 'identifier-type':'doi', identifier:doi, display:'plumprint', config:JSON.stringify({printSize:'medium',popupDirection:'left',hideWhenEmpty:true})}).forEach(([key,value]) => plum.setAttribute(key,value));
      plum.addEventListener('plumx:load', () => card.classList.add('has-attention'));
      const hidePlum = () => { plum.hidden = true; };
      plum.addEventListener('plumx:empty', hidePlum);
      plum.addEventListener('plumx:error', hidePlum);
      const alt = document.createElement('div');
      alt.className = 'altmetric-embed';
      Object.entries({doi, 'badge-type':'donut', 'badge-popover':'left', 'hide-no-mentions':'true', 'link-target':'_blank'}).forEach(([key,value]) => alt.setAttribute('data-'+key,value));
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
  function start() {
    enhance();
    observer.observe(document.body, {childList:true,subtree:true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();

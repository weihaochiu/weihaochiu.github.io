(() => {
'use strict';

const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[ch]);

const labels = {
  publications: '新論文',
  patents: '新專利',
  projects: '新 GRB 計畫'
};

let payload = null;

function formatDate(value) {
  if (!value) return '尚未執行';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) :
    new Intl.DateTimeFormat('zh-TW', {dateStyle:'medium', timeStyle:'short'}).format(date);
}

function titleOf(item) {
  return item.title || item.titleZh || item.titleEn || item.number || item.grbId || '未命名資料';
}

function fieldLines(type, item) {
  if (type === 'publications') return [
    ['DOI', item.doi],
    ['期刊', item.journal],
    ['發表日期', item.publicationDate],
    ['作者', (item.authors || []).join('; ')],
    ['出版者', item.publisher]
  ];
  if (type === 'patents') return [
    ['專利號／公開號', item.number],
    ['中文名稱', item.titleZh],
    ['英文名稱', item.titleEn],
    ['發明人', (item.inventorsEn || []).join('; ') || item.inventorsZh],
    ['申請人', item.assigneeEn || item.assigneeZh],
    ['狀態', item.status]
  ];
  return [
    ['GRB ID', item.grbId],
    ['計畫編號', item.number],
    ['中文名稱', item.titleZh],
    ['英文名稱', item.titleEn],
    ['角色', item.roleZh || item.role],
    ['執行期間', item.period],
    ['核定金額', item.fundingAmountTwd ? `NT$${Number(item.fundingAmountTwd).toLocaleString('zh-TW')}` : '']
  ];
}

function sourceText(sources) {
  return (sources || []).map(source => `- ${source.name}: ${source.url}`).join('\n');
}

function copyText(type, items) {
  const heading = labels[type];
  const blocks = items.map((item, index) => {
    const fields = fieldLines(type, item)
      .filter(([, value]) => Array.isArray(value) ? value.length : String(value ?? '').trim())
      .map(([name, value]) => `${name}:\n${Array.isArray(value) ? value.join('; ') : value}`)
      .join('\n\n');
    const notes = (item.detectionNotes || []).map(note => `- ${note}`).join('\n');
    return `【${heading} ${index + 1}】\n${fields}\n\n資料來源：\n${sourceText(item.sources)}\n\n偵測說明：\n${notes}`;
  }).join('\n\n------------------------------\n\n');

  return `請更新我的學術網站：\nRepository: ${payload.repository}\n資料取得時間：${payload.generatedAt || '尚未執行'}\n監測類型：${heading}\n\n${blocks}\n\n${payload.copyInstructions?.finalLine || ''}`.trim();
}

async function writeClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    textarea.remove();
  }
}

function showCopyStatus(message) {
  const status = document.getElementById('copyStatus');
  status.textContent = message;
  window.clearTimeout(showCopyStatus.timer);
  showCopyStatus.timer = window.setTimeout(() => status.textContent = '', 3500);
}

function renderItem(type, item, index) {
  const fields = fieldLines(type, item)
    .filter(([, value]) => Array.isArray(value) ? value.length : String(value ?? '').trim())
    .slice(0, 5)
    .map(([name, value]) => `<div><strong>${esc(name)}：</strong>${esc(Array.isArray(value) ? value.join('; ') : value)}</div>`)
    .join('');
  const sources = (item.sources || []).map(source =>
    `<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.name)} ↗</a>`
  ).join('');
  const notes = (item.detectionNotes || []).map(note => `<li>${esc(note)}</li>`).join('');
  return `<article class="record-card">
    <span class="record-type">${esc(item.confidence || 'possible')}</span>
    <h3>${esc(titleOf(item))}</h3>
    <div class="record-meta">${fields}</div>
    ${notes ? `<ul class="record-note">${notes}</ul>` : ''}
    <div class="record-sources">${sources}</div>
    <div class="record-actions">
      <button class="monitor-button" type="button" data-copy-one="${type}" data-index="${index}">複製此筆</button>
    </div>
  </article>`;
}

function renderPanel(type) {
  const items = payload[type] || [];
  document.getElementById(`${type}Count`).textContent = items.length;
  const host = document.getElementById(`${type}List`);
  host.innerHTML = items.length
    ? items.map((item, index) => renderItem(type, item, index)).join('')
    : '<div class="empty-state">目前沒有待確認資料。若來源檢查失敗，請查看下方「資料來源狀態」，不能將此狀態解讀為確定沒有新資料。</div>';
  const button = document.querySelector(`[data-copy-group="${type}"]`);
  button.disabled = !items.length;
}

function renderSources() {
  const host = document.getElementById('sourceGrid');
  const sources = payload.sources || [];
  host.innerHTML = sources.length ? sources.map(source => {
    const status = source.status || 'not-run';
    return `<div class="source-card">
      <strong>${esc(source.name)}</strong>
      <a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.url)}</a>
      <div>${esc(source.message || `候選結果：${source.candidateCount ?? '—'}`)}</div>
      <span class="status-pill status-${esc(status)}">${esc(status)}</span>
    </div>`;
  }).join('') : '<div class="empty-state">尚未執行監測 Action。</div>';
}

function bindActions() {
  document.addEventListener('click', async event => {
    const one = event.target.closest('[data-copy-one]');
    if (one) {
      const type = one.dataset.copyOne;
      const item = payload[type][Number(one.dataset.index)];
      await writeClipboard(copyText(type, [item]));
      showCopyStatus('已複製 1 筆資料，可直接貼到 ChatGPT。');
      return;
    }
    const group = event.target.closest('[data-copy-group]');
    if (group) {
      const type = group.dataset.copyGroup;
      await writeClipboard(copyText(type, payload[type] || []));
      showCopyStatus(`已複製 ${(payload[type] || []).length} 筆資料，可直接貼到 ChatGPT。`);
      return;
    }
    if (event.target.closest('#copyAll')) {
      const sections = ['publications','patents','projects']
        .filter(type => (payload[type] || []).length)
        .map(type => copyText(type, payload[type]));
      if (!sections.length) return;
      await writeClipboard(sections.join('\n\n================================\n\n'));
      showCopyStatus(`已複製 ${payload.summary.totalCandidates} 筆待確認資料。`);
    }
  });
}

async function init() {
  bindActions();
  try {
    const response = await fetch('data/academic-monitor.json', {cache:'no-store'});
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    payload = await response.json();
    document.getElementById('generatedAt').textContent = formatDate(payload.generatedAt);
    document.getElementById('monitorStatus').textContent = payload.status || 'unknown';
    document.getElementById('summaryPublications').textContent = payload.summary?.publications ?? 0;
    document.getElementById('summaryPatents').textContent = payload.summary?.patents ?? 0;
    document.getElementById('summaryProjects').textContent = payload.summary?.projects ?? 0;
    document.getElementById('summaryErrors').textContent =
      (payload.summary?.sourceErrors ?? 0) + (payload.summary?.sourceWarnings ?? 0);
    document.getElementById('summaryTotal').textContent = payload.summary?.totalCandidates ?? 0;
    ['publications','patents','projects'].forEach(renderPanel);
    renderSources();
    document.getElementById('copyAll').disabled = !(payload.summary?.totalCandidates);
  } catch (error) {
    document.getElementById('loadStatus').textContent = `無法載入監測資料：${error.message}`;
    document.getElementById('loadStatus').className = 'copy-status status-error';
  }
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
else init();
})();

(() => {
'use strict';

const STORAGE_KEY = 'academicMonitorReviews.v2';
const TYPES = ['publications', 'patents', 'projects'];
const labels = {
  publications: '新論文',
  patents: '新專利',
  projects: '新 GRB 計畫'
};
const targetFiles = {
  publications: 'data/publications.json',
  patents: 'data/patents.json',
  projects: 'data/projects.json'
};
const statuses = {
  confirmed_mine: '已確認是本人的',
  confirmed_not_mine: '已確認非本人的',
  unconfirmed: '尚未確認'
};

const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
})[ch]);

let payload = null;
let reviews = loadReviews();

function loadReviews() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch (_) {
    return {};
  }
}

function saveReviews() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(reviews));
  } catch (_) {
    showCopyStatus('瀏覽器無法保存確認狀態；本頁仍可複製，但重新整理後可能遺失。');
  }
}

function normalize(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function keyOf(type, item) {
  if (item.reviewKey) return item.reviewKey;
  if (type === 'publications') {
    return item.doi
      ? `publication:doi:${String(item.doi).toLowerCase().replace(/^https?:\/\/(?:dx\.)?doi\.org\//, '')}`
      : `publication:title:${normalize(item.title)}`;
  }
  if (type === 'patents') {
    return item.canonicalId || item.number
      ? `patent:number:${String(item.canonicalId || item.number).toUpperCase().replace(/[^A-Z0-9]/g, '')}`
      : `patent:title:${normalize(item.titleEn || item.titleZh)}`;
  }
  return item.grbId
    ? `project:grb-id:${item.grbId}`
    : item.number
      ? `project:number:${String(item.number).toUpperCase().replace(/[^A-Z0-9]/g, '')}`
      : `project:title:${normalize(item.titleEn || item.titleZh)}`;
}

function reviewOf(type, item) {
  return reviews[keyOf(type, item)] || {status: 'unconfirmed', note: '', reviewedAt: ''};
}

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
    ['標準專利號', item.canonicalId],
    ['專利號／公開號', item.number],
    ['中文名稱', item.titleZh],
    ['英文名稱', item.titleEn],
    ['發明人', (item.inventorsEn || []).join('; ') || item.inventorsZh],
    ['申請人', item.assigneeEn || item.assigneeZh],
    ['管轄區', item.jurisdiction],
    ['申請日', item.filingDate],
    ['公開日', item.publicationDate],
    ['核准日', item.grantDate],
    ['文件階段', item.documentStage || item.status],
    ['法律狀態', item.legalStatus],
    ['可信度', item.confidence]
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

function decisionEntry(type, item) {
  const review = reviewOf(type, item);
  return {
    reviewKey: keyOf(type, item),
    status: review.status || 'unconfirmed',
    statusLabel: statuses[review.status] || statuses.unconfirmed,
    recordType: type.replace(/s$/, ''),
    targetFile: targetFiles[type],
    userNote: review.note || '',
    reviewedAt: review.reviewedAt || '',
    record: item
  };
}

function copyText(entries, includeInstructions = true) {
  const body = {
    schemaVersion: 1,
    repository: payload.repository,
    monitorGeneratedAt: payload.generatedAt || '',
    copiedAt: new Date().toISOString(),
    decisionRegistry: 'data/academic_monitor_review_decisions.json',
    decisions: entries
  };
  const instructions = includeInstructions
    ? [
        '請依下方確認結果更新網站 JSON：',
        '1. 所有 confirmed_mine 與 confirmed_not_mine 都寫入 data/academic_monitor_review_decisions.json，保留 reviewKey、完整 record、userNote 與時間。',
        '2. confirmed_mine：先查核來源，再更新 targetFile；只補空白或明確經使用者確認的欄位，不猜測資料。',
        '3. confirmed_not_mine：不要寫入成果 JSON；以 reviewKey 建立永久排除紀錄，後續監控不得再次要求確認。',
        '4. unconfirmed：不可修改成果 JSON，也不可建立永久排除。',
        '5. 同一 reviewKey 若已有紀錄，以這次結果更新；不要產生重複紀錄。',
        payload.copyInstructions?.finalLine || ''
      ].join('\n')
    : '';
  return `${instructions}\n\n【ACADEMIC_MONITOR_REVIEW_JSON】\n${JSON.stringify(body, null, 2)}`.trim();
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
  showCopyStatus.timer = window.setTimeout(() => status.textContent = '', 4500);
}

function allEntries() {
  return TYPES.flatMap(type => (payload[type] || []).map(item => decisionEntry(type, item)));
}

function updateReviewSummary() {
  const entries = allEntries();
  const mine = entries.filter(row => row.status === 'confirmed_mine').length;
  const notMine = entries.filter(row => row.status === 'confirmed_not_mine').length;
  const confirmed = mine + notMine;
  document.getElementById('summaryMine').textContent = mine;
  document.getElementById('summaryNotMine').textContent = notMine;
  document.getElementById('summaryUnconfirmed').textContent = entries.length - confirmed;
  document.getElementById('copyReviewed').disabled = !confirmed;
  document.getElementById('clearReviews').disabled = !confirmed &&
    !entries.some(row => row.userNote);
}

function reviewControls(type, item, index) {
  const review = reviewOf(type, item);
  const key = keyOf(type, item);
  const buttons = Object.entries(statuses).map(([status, label]) => {
    const selected = review.status === status;
    return `<button class="review-choice status-${esc(status)}${selected ? ' is-selected' : ''}"
      type="button" data-review-status="${esc(status)}" data-review-type="${esc(type)}"
      data-index="${index}" aria-pressed="${selected}">${esc(label)}</button>`;
  }).join('');
  return `<div class="review-block" data-review-key="${esc(key)}">
    <div class="review-label">這筆資料是否屬於您？</div>
    <div class="review-choices" role="group" aria-label="資料確認狀態">${buttons}</div>
    <label class="review-note-label">
      補充說明（選填）
      <textarea class="review-note" data-review-note="${esc(type)}" data-index="${index}"
        rows="2" placeholder="例如：同名不同人、確認的機構或需要補查的資訊">${esc(review.note || '')}</textarea>
    </label>
  </div>`;
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
  const review = reviewOf(type, item);
  return `<article class="record-card review-${esc(review.status)}">
    <div class="record-topline">
      <span class="record-type">${esc(item.confidence || 'possible')}</span>
      <span class="record-review-status">${esc(statuses[review.status] || statuses.unconfirmed)}</span>
    </div>
    <h3>${esc(titleOf(item))}</h3>
    <div class="record-meta">${fields}</div>
    ${notes ? `<ul class="record-note">${notes}</ul>` : ''}
    <div class="record-sources">${sources}</div>
    ${reviewControls(type, item, index)}
    <div class="record-actions">
      <button class="monitor-button" type="button" data-copy-one="${type}" data-index="${index}">複製此筆含確認狀態</button>
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
    const summary = status === 'success'
      ? `檢查完成；候選結果：${source.candidateCount ?? '—'}`
      : status === 'not-run'
        ? '尚未執行這項來源檢查。'
        : '這項來源目前未能完成檢查。';
    const diagnostic = source.message
      ? `<details class="source-diagnostic"><summary>顯示技術診斷</summary><div>${esc(source.message)}</div></details>`
      : '';
    return `<div class="source-card">
      <strong>${esc(source.name)}</strong>
      <a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.url)}</a>
      <div>${esc(summary)}</div>
      ${diagnostic}
      <span class="status-pill status-${esc(status)}">${esc(status)}</span>
    </div>`;
  }).join('') : '<div class="empty-state">尚未執行監測 Action。</div>';
}

function setReview(type, index, status) {
  const item = payload[type][index];
  const key = keyOf(type, item);
  const existing = reviewOf(type, item);
  if (status === 'unconfirmed' && !existing.note) {
    delete reviews[key];
  } else {
    reviews[key] = {
      status,
      note: existing.note || '',
      reviewedAt: status === 'unconfirmed' ? '' : new Date().toISOString()
    };
  }
  saveReviews();
  renderPanel(type);
  updateReviewSummary();
}

function setReviewNote(type, index, note) {
  const item = payload[type][index];
  const key = keyOf(type, item);
  const existing = reviewOf(type, item);
  if (!note.trim() && existing.status === 'unconfirmed') {
    delete reviews[key];
  } else {
    reviews[key] = {...existing, note};
  }
  saveReviews();
  updateReviewSummary();
}

function bindActions() {
  document.addEventListener('click', async event => {
    const choice = event.target.closest('[data-review-status]');
    if (choice) {
      setReview(choice.dataset.reviewType, Number(choice.dataset.index), choice.dataset.reviewStatus);
      return;
    }
    const one = event.target.closest('[data-copy-one]');
    if (one) {
      const type = one.dataset.copyOne;
      const item = payload[type][Number(one.dataset.index)];
      await writeClipboard(copyText([decisionEntry(type, item)]));
      showCopyStatus('已複製 1 筆資料與確認狀態，可直接貼到 ChatGPT。');
      return;
    }
    const group = event.target.closest('[data-copy-group]');
    if (group) {
      const type = group.dataset.copyGroup;
      const entries = (payload[type] || []).map(item => decisionEntry(type, item));
      await writeClipboard(copyText(entries));
      showCopyStatus(`已複製 ${entries.length} 筆資料與確認狀態。`);
      return;
    }
    if (event.target.closest('#copyReviewed')) {
      const entries = allEntries().filter(row => row.status !== 'unconfirmed');
      if (!entries.length) return;
      await writeClipboard(copyText(entries));
      showCopyStatus(`已複製 ${entries.length} 筆已確認結果，可直接貼到 ChatGPT。`);
      return;
    }
    if (event.target.closest('#copyAll')) {
      const entries = allEntries();
      if (!entries.length) return;
      await writeClipboard(copyText(entries));
      showCopyStatus(`已複製 ${entries.length} 筆候選資料（含尚未確認項目）。`);
      return;
    }
    if (event.target.closest('#clearReviews')) {
      if (!window.confirm('要清除這個瀏覽器中目前候選資料的所有確認狀態與備註嗎？')) return;
      allEntries().forEach(row => delete reviews[row.reviewKey]);
      saveReviews();
      TYPES.forEach(renderPanel);
      updateReviewSummary();
      showCopyStatus('已清除本機確認狀態；伺服器端判定 JSON 不受影響。');
    }
  });

  document.addEventListener('input', event => {
    const note = event.target.closest('[data-review-note]');
    if (!note) return;
    setReviewNote(note.dataset.reviewNote, Number(note.dataset.index), note.value);
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
    TYPES.forEach(renderPanel);
    renderSources();
    document.getElementById('copyAll').disabled = !(payload.summary?.totalCandidates);
    updateReviewSummary();
  } catch (error) {
    document.getElementById('loadStatus').textContent = `無法載入監測資料：${error.message}`;
    document.getElementById('loadStatus').className = 'copy-status status-error';
  }
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
else init();
})();

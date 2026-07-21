const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function loadData(name){
  const local=`data/${name}.json`;
  try{const r=await fetch(local,{cache:'no-store'});if(r.ok)return r.json()}catch(e){}
  const remote=`https://weihaochiu.github.io/data/${name}.json`;
  const r=await fetch(remote,{cache:'no-store'});
  if(!r.ok)throw new Error(`Unable to load ${name}`);
  return r.json();
}

function yearOf(x){return Number(x.year||x.startYear||String(x.sortDate||x.date||'').slice(0,4)||0)}
function highlightAuthor(name){return /Chiu, Wei-Hao|Wei-Hao Chiu/.test(name)?`<strong class="me">${esc(name)}</strong>`:esc(name)}
function fillSelect(el,vals,label='All',mode='numeric-desc'){
  if(!el)return;
  let items=[...new Set(vals.filter(v=>v!==undefined&&v!==null&&v!==''))];
  items.sort(mode==='alpha'?(a,b)=>String(a).localeCompare(String(b),'en',{sensitivity:'base'}):(a,b)=>Number(b)-Number(a));
  el.innerHTML=`<option value="">${label}</option>`+items.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');
}
function formatDate(x){
  if(!x)return 'Not available';
  const d=new Date(x);
  return Number.isNaN(d.valueOf())?x:new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'Asia/Taipei'}).format(d);
}

function setNavigation(){
  const nav=$('.site-nav');if(!nav)return;
  const links=[['about.html','About'],['research.html','Research'],['publications.html','Publications'],['patents.html','Patents'],['projects.html','Projects']];
  const p=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  const aboutPages=new Set(['about.html','experience.html','education.html','awards.html']);
  nav.innerHTML=links.map(([href,label])=>{const active=(href===p)||(href==='about.html'&&aboutPages.has(p));return `<a ${active?'aria-current="page" ':''}href="${href}">${label}</a>`}).join('');
}

async function initMeta(){
  const [m,s,md,cr]=await Promise.all([
    loadData('site_meta').catch(()=>({})),
    loadData('scholar_metrics').catch(()=>({})),
    loadData('mendeley_metrics').catch(()=>({})),
    loadData('crossref_publication_metrics').catch(()=>({}))
  ]);
  $$('[data-site-updated]').forEach(e=>e.textContent=formatDate(m.lastUpdated));
  $$('[data-site-version]').forEach(e=>e.textContent=m.version||'v20');
  $$('[data-scholar-updated]').forEach(e=>e.textContent=formatDate(s.lastSuccessfulUpdate));
  if(s.citations!==undefined&&s.citations!==null)$$('[data-scholar-citations]').forEach(e=>e.textContent=Number(s.citations).toLocaleString());
  if(s.hIndex!==undefined&&s.hIndex!==null)$$('[data-scholar-h]').forEach(e=>e.textContent=s.hIndex);
  if(s.i10Index!==undefined&&s.i10Index!==null)$$('[data-scholar-i10]').forEach(e=>e.textContent=s.i10Index);
  if(md.totalReaders!==undefined&&md.totalReaders!==null){
    $$('[data-mendeley-readers]').forEach(e=>e.textContent=Number(md.totalReaders).toLocaleString());
  }
  const crossrefCounts=Object.values(cr.records||{})
    .filter(record=>record?.status==='verified'&&Number.isInteger(Number(record.citationCount))&&Number(record.citationCount)>=0)
    .map(record=>Number(record.citationCount))
    .sort((a,b)=>b-a);
  if(crossrefCounts.length){
    const citations=crossrefCounts.reduce((sum,count)=>sum+count,0);
    const hIndex=crossrefCounts.reduce((h,count,index)=>count>=index+1?index+1:h,0);
    const i10Index=crossrefCounts.filter(count=>count>=10).length;
    $$('[data-crossref-citations]').forEach(e=>e.textContent=citations.toLocaleString());
    $$('[data-crossref-h]').forEach(e=>e.textContent=hIndex);
    $$('[data-crossref-i10]').forEach(e=>e.textContent=i10Index);
    $$('[data-crossref-metrics-link]').forEach(e=>{
      if(cr.lastSuccessfulUpdate)e.title=`Crossref metrics updated ${formatDate(cr.lastSuccessfulUpdate)}`;
    });
  }
}

const FALLBACK_CATEGORY_LABELS={
  DSSC:'Dye-Sensitized Solar Cells (DSSC)',
  PSC:'Perovskite Solar Cells (PSC)',
  RFB:'Redox Flow Batteries (RFB)',
  Other:'Other Research'
};

function publicationKey(p){return String(p.doi||'').trim().toLowerCase()}
function publicationAnchor(p){
  const source=publicationKey(p)||String(p.title||'publication').toLowerCase();
  const slug=source.replace(/^https?:\/\/(dx\.)?doi\.org\//,'').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
  return `pub-${slug||'record'}`;
}
function normalizeExternalUrl(value){
  const url=String(value||'').trim();
  if(!url)return '';
  try{
    const parsed=new URL(url);
    return /^(https?:)$/.test(parsed.protocol)?parsed.toString():'';
  }catch(e){return ''}
}
function publicationShareUrl(anchor){
  const slug=String(anchor||'').replace(/^pub-/,'');
  return new URL(`publications/${slug}.html`,window.location.href).toString();
}
function inferPublicationCategory(p){
  const text=`${p.topic||''} ${p.title||''} ${(p.tags||[]).join(' ')}`.toLowerCase();
  if(/redox flow|flow batter|vrfb/.test(text))return 'RFB';
  if(/perovskite|hole-transport|space pv/.test(text))return 'PSC';
  if(/dye-sensitized|dssc/.test(text))return 'DSSC';
  return 'Other';
}
function enrichPublications(rows,taxonomy={},mendeley={},unpaywall={},crossref={}){
  const map=taxonomy.publications||{};
  const metricMap=mendeley.records||{};
  const oaMap=unpaywall.records||{};
  const crossrefMap=crossref.records||{};
  const labels={...FALLBACK_CATEGORY_LABELS,...(taxonomy.categoryLabels||{})};
  return rows.map(p=>{
    const key=publicationKey(p);
    const entry=map[key]||{};
    const category=entry.category||inferPublicationCategory(p);
    const subtopics=Array.isArray(entry.subtopics)?[...new Set(entry.subtopics)]:[];
    return {...p,category,categoryLabel:labels[category]||category,subtopics,mendeley:metricMap[key]||null,openAccess:oaMap[key]||null,crossref:crossrefMap[key]||null};
  });
}
function fillPublicationThemeSelect(el,taxonomy={}){
  if(!el)return;
  const options=Array.isArray(taxonomy.themeOptions)&&taxonomy.themeOptions.length?taxonomy.themeOptions:[
    {value:'',label:'All'},
    ...Object.entries(FALLBACK_CATEGORY_LABELS).map(([key,label])=>({value:`category:${key}`,label}))
  ];
  el.innerHTML=options.map(o=>`<option value="${esc(o.value||'')}">${esc(o.label||'')}</option>`).join('');
}
function publicationMatchesTheme(p,value){
  if(!value)return true;
  if(value.startsWith('category:'))return p.category===value.slice('category:'.length);
  if(value.startsWith('subtopic:'))return (p.subtopics||[]).includes(value.slice('subtopic:'.length));
  return false;
}

function normalizeScholarUrl(value){
  let url=String(value||'').trim();
  if(!url)return '';
  const secondHttps=url.indexOf('https://',8);
  const secondHttp=url.indexOf('http://',7);
  const second=[secondHttps,secondHttp].filter(i=>i>0).sort((a,b)=>a-b)[0];
  if(second)url=url.slice(second);
  if(url.startsWith('//'))url=`https:${url}`;
  else if(url.startsWith('/'))url=`https://scholar.google.com${url}`;
  try{
    const parsed=new URL(url,'https://scholar.google.com');
    if(!/^scholar\.google\./i.test(parsed.hostname))return '';
    parsed.protocol='https:';
    parsed.hostname='scholar.google.com';
    return parsed.toString();
  }catch(e){return ''}
}

function normalizeMendeleyUrl(value){
  const url=String(value||'').trim();
  if(!url)return '';
  try{
    const parsed=new URL(url);
    const host=parsed.hostname.toLowerCase();
    if(parsed.protocol!=='https:'||!(host==='mendeley.com'||host.endsWith('.mendeley.com')))return '';
    return parsed.toString();
  }catch(e){return ''}
}
const MENDELEY_READER_ICON='<svg class="metric-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11a2 2 0 0 1 2 2v15a3.8 3.8 0 0 0-3.2-1.7H6.5A2.5 2.5 0 0 1 4 15.8Z"></path><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13a2 2 0 0 0-2 2v15a3.8 3.8 0 0 1 3.2-1.7h3.3a2.5 2.5 0 0 0 2.5-2.5Z"></path></svg>';
const OPEN_ACCESS_ICON='<svg class="action-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M7 10V7a5 5 0 0 1 9.7-1.7"></path><rect x="5" y="10" width="14" height="10" rx="2"></rect><path d="M12 14v2"></path></svg>';
const SHARE_ICON='<svg class="action-icon" aria-hidden="true" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><path d="m8.7 10.7 6.6-4.1M8.7 13.3l6.6 4.1"></path></svg>';

function publicationCard(p){
  const authors=(p.authors||[]).map(highlightAuthor).join(', ');
  const n=Number(p.citationCount||0);
  const scholarUrl=normalizeScholarUrl(p.scholarCitedByUrl)||normalizeScholarUrl(p.citedByUrl);
  const cited=n>0&&scholarUrl
    ?`<a class="action" href="${esc(scholarUrl)}" target="_blank" rel="noopener noreferrer">${n} Google Scholar citation${n===1?'':'s'} ↗</a>`
    :`<span class="action">${n} Google Scholar citation${n===1?'':'s'}</span>`;
  const crossref=p.crossref||{};
  const crossrefCount=Number(crossref.citationCount);
  const crossrefUrl=normalizeExternalUrl(crossref.url);
  const crossrefAction=crossref.status==='verified'&&Number.isFinite(crossrefCount)&&crossrefCount>=0&&crossrefUrl
    ?`<a class="action" href="${esc(crossrefUrl)}" target="_blank" rel="noopener noreferrer">Crossref (${crossrefCount.toLocaleString()}) ↗</a>`
    :'';
  const metric=p.mendeley||{};
  const readerCount=Number(metric.readerCount);
  const mendeleyUrl=normalizeMendeleyUrl(metric.url);
  const readers=metric.status==='verified'&&Number.isFinite(readerCount)&&readerCount>=0&&mendeleyUrl
    ?`<a class="action metric-action" href="${esc(mendeleyUrl)}" target="_blank" rel="noopener noreferrer" aria-label="${readerCount} Mendeley reader${readerCount===1?'':'s'}; open Mendeley record">${MENDELEY_READER_ICON}<span>${readerCount} Mendeley reader${readerCount===1?'':'s'} ↗</span></a>`
    :'';
  const oa=p.openAccess||{};
  const pdfUrl=normalizeExternalUrl(oa.urlForPdf);
  const versionUrl=normalizeExternalUrl(oa.landingPageUrl||oa.url);
  const oaAction=oa.isOa&&pdfUrl
    ?`<a class="action oa-action" href="${esc(pdfUrl)}" target="_blank" rel="noopener noreferrer" title="Legal open-access PDF identified by Unpaywall">${OPEN_ACCESS_ICON}<span>Open Access PDF ↗</span></a>`
    :oa.isOa&&versionUrl
      ?`<a class="action oa-action" href="${esc(versionUrl)}" target="_blank" rel="noopener noreferrer" title="Legal open-access version identified by Unpaywall">${OPEN_ACCESS_ICON}<span>Open Access Version ↗</span></a>`
      :'';
  const labels=[p.categoryLabel,...(p.subtopics||[])].filter(Boolean);
  const anchor=publicationAnchor(p);
  const shareUrl=publicationShareUrl(anchor);
  const detailAction=`<a class="action publication-detail-link" href="${esc(shareUrl)}">Abstract, Highlights, GA &amp; Keywords →</a>`;
  const shareText=`${p.title}\n${p.journal||''}${p.year?`, ${p.year}`:''}\nDOI: ${p.doi||''}`;
  const emailUrl=`mailto:?subject=${encodeURIComponent(p.title||'Publication')}&body=${encodeURIComponent(`${shareText}\n\n${shareUrl}`)}`;
  const linkedinUrl=`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`;
  const xUrl=`https://twitter.com/intent/tweet?text=${encodeURIComponent(`${p.title}${p.doi?` | DOI: ${p.doi}`:''}`)}&url=${encodeURIComponent(shareUrl)}`;
  const facebookUrl=`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
  const shareMenuId=`share-menu-${anchor}`;
  const share=`<span class="share-wrap"><button class="action action-button share-trigger" type="button" aria-haspopup="menu" aria-expanded="false" aria-controls="${esc(shareMenuId)}" data-share-title="${esc(p.title)}" data-share-text="${esc(shareText)}" data-share-url="${esc(shareUrl)}">${SHARE_ICON}<span>Share</span></button><span class="share-menu" id="${esc(shareMenuId)}" role="menu" hidden><button type="button" role="menuitem" data-copy-share-url="${esc(shareUrl)}">Copy link</button><a role="menuitem" href="${esc(emailUrl)}">Email</a><a role="menuitem" href="${esc(linkedinUrl)}" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a><a role="menuitem" href="${esc(xUrl)}" target="_blank" rel="noopener noreferrer">X (Twitter) ↗</a><a role="menuitem" href="${esc(facebookUrl)}" target="_blank" rel="noopener noreferrer">Facebook ↗</a></span></span>`;
  return `<article class="collection-card publication-card" id="${esc(anchor)}"><div class="card-heading"><h4><a href="${esc(shareUrl)}">${esc(p.title)}</a></h4><span class="date-badge">${esc(p.date)}</span></div><p class="authors">${authors}</p><p class="journal"><em>${esc(p.journal)}</em>${p.volume?`, ${esc(p.volume)}`:''}${p.pages?`, ${esc(p.pages)}`:''} (${p.year}).</p><div class="card-labels">${labels.map(label=>`<span class="card-label">${esc(label)}</span>`).join('')}</div><div class="card-actions">${detailAction}<a class="action" href="${esc(p.doiUrl)}" target="_blank" rel="noopener">DOI ↗</a>${oaAction}${cited}${crossrefAction}${readers}${share}</div></article>`;
}
function patentCard(p){return `<article class="collection-card"><div class="card-heading"><h4><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titleEn)}</a></h4><span class="date-badge">${esc(p.date)}</span></div>${p.titleZh?`<div class="local-title" lang="zh-Hant">${esc(p.titleZh)}</div>`:''}<div class="card-labels"><span class="card-label">${esc(p.number)}</span><span class="card-label">${esc(p.jurisdiction)}</span><span class="card-label">${esc(p.status)}</span></div><div class="meta-row">Inventors: ${(p.inventorsEn||[]).map(highlightAuthor).join(', ')}</div>${p.inventorsZh?`<div class="meta-row" lang="zh-Hant">發明人／創作人：${esc(p.inventorsZh)}</div>`:''}<div class="meta-row">Assignee: ${esc(p.assigneeEn)}</div><div class="card-actions"><a class="action" href="${esc(p.url)}" target="_blank" rel="noopener">Patent record ↗</a></div></article>`}
function projectCard(p){return `<article class="collection-card"><div class="card-heading"><h4>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titleEn)}</a>`:esc(p.titleEn)}</h4><span class="date-badge">${esc(p.period||p.startYear)}</span></div><div class="local-title" lang="zh-Hant">${esc(p.titleZh)}</div><div class="card-labels"><span class="card-label">${esc(p.status)}</span><span class="card-label">${esc(p.role)} · ${esc(p.roleZh)}</span>${p.number?`<span class="card-label">${esc(p.number)}</span>`:''}</div><p>${esc(p.agencyEn)}</p><p class="summary">${esc(p.scopeEn)}</p>${p.url?`<div class="card-actions"><a class="action" href="${esc(p.url)}" target="_blank" rel="noopener">Project record ↗</a></div>`:''}</article>`}
function awardCard(a){return `<article class="collection-card"><div class="card-heading"><h4>${esc(a.titleEn)}</h4><span class="date-badge">${esc(a.date)}</span></div>${a.titleZh?`<div class="award-title-zh" lang="zh-Hant">${esc(a.titleZh)}</div>`:''}<p><strong>${esc(a.organizationEn)}</strong></p><p>${esc(a.workEn)}</p><p>${esc(a.recipientsEn)}</p><div class="card-labels"><span class="award-type">${esc(a.type)}</span></div>${a.url?`<div class="card-actions"><a class="action" href="${esc(a.url)}" target="_blank" rel="noopener">Award record ↗</a></div>`:''}</article>`}

function counts(rows){return rows.reduce((a,x)=>{const y=yearOf(x);if(y)a[y]=(a[y]||0)+1;return a},{})}
function niceMax(v){if(v<=4)return 4;if(v<=6)return 6;if(v<=10)return 10;return Math.ceil(v/5)*5}
function renderBarChart(el,series,onYear){
  if(!el)return;
  const years=[...new Set(series.flatMap(s=>Object.keys(s.values).map(Number)))].sort((a,b)=>a-b);
  const rawMax=Math.max(1,...series.flatMap(s=>Object.values(s.values)));
  const max=niceMax(rawMax);
  const ticks=[max,Math.round(max*2/3),Math.round(max/3),0];
  el.classList.toggle('all-series',series.length>1);
  el.innerHTML=`<div class="chart-scroll"><div class="chart-layout"><div class="chart-yaxis">${ticks.map(t=>`<span>${t}</span>`).join('')}</div><div class="chart-stage"><div class="chart-gridlines">${ticks.map(()=>'<span></span>').join('')}</div><div class="chart-columns">${years.map(y=>`<div class="chart-column"><div class="bar-group">${series.map(s=>{const v=s.values[y]||0;const h=v?Math.max(3,v/max*100):0;return `<button ${v===0?'disabled ':''}class="chart-bar bar-${s.key}" data-year="${y}" style="height:${h}%" title="${y}: ${v} ${esc(s.label.toLowerCase())}" type="button" aria-label="${y}, ${v} ${esc(s.label.toLowerCase())}">${v?`<span class="bar-value">${v}</span>`:''}</button>`}).join('')}</div><span class="chart-year">${y}</span></div>`).join('')}</div></div></div></div>`;
  if(onYear)$$('.chart-bar:not([disabled])',el).forEach(b=>b.addEventListener('click',()=>onYear(b.dataset.year)));
}
function singleChart(el,rows,onYear){renderBarChart(el,[{key:'publications',label:'records',values:counts(rows)}],onYear)}

function renderPublicationStackedChart(el,rows,onSelection,taxonomy={}){
  if(!el)return;
  const labels={...FALLBACK_CATEGORY_LABELS,...(taxonomy.categoryLabels||{})};
  const series=[
    {key:'DSSC',css:'dssc',label:labels.DSSC},
    {key:'PSC',css:'psc',label:labels.PSC},
    {key:'RFB',css:'rfb',label:labels.RFB},
    {key:'Other',css:'other',label:labels.Other}
  ];
  const publicationYears=rows.map(yearOf).filter(Boolean);
  if(!publicationYears.length){el.innerHTML='';return}
  const minYear=Math.min(...publicationYears),maxYear=Math.max(...publicationYears);
  const years=Array.from({length:maxYear-minYear+1},(_,i)=>minYear+i);
  const values={};
  years.forEach(y=>{values[y]={DSSC:0,PSC:0,RFB:0,Other:0,total:0}});
  rows.forEach(p=>{const y=yearOf(p);if(!values[y])return;const key=values[y][p.category]===undefined?'Other':p.category;values[y][key]+=1;values[y].total+=1});
  const max=niceMax(Math.max(1,...years.map(y=>values[y].total)));
  const ticks=[max,Math.round(max*2/3),Math.round(max/3),0];
  el.classList.add('publication-stacked-chart');
  el.innerHTML=`<div class="chart-scroll"><div class="chart-layout"><div class="chart-yaxis">${ticks.map(t=>`<span>${t}</span>`).join('')}</div><div class="chart-stage"><div class="chart-gridlines">${ticks.map(()=>'<span></span>').join('')}</div><div class="chart-columns">${years.map(y=>{
    const total=values[y].total;
    const totalHeight=total/max*100;
    const segments=series.map(s=>{
      const v=values[y][s.key];
      if(!v)return '';
      const pct=total?v/total*100:0;
      const showValue=pct>=16;
      return `<button class="stacked-segment segment-${s.css}" data-year="${y}" data-category="${s.key}" style="flex:${v}" type="button" title="${y}: ${v} ${esc(s.label)} (${pct.toFixed(1)}%)" aria-label="${y}, ${v} ${esc(s.label)}, ${pct.toFixed(1)} percent">${showValue?`<span>${v}</span>`:''}</button>`;
    }).join('');
    return `<div class="chart-column"><div class="stacked-column-area">${total?`<span class="stacked-total" style="bottom:calc(${totalHeight}% + 3px)">${total}</span>`:''}<div class="stacked-bar" style="height:${totalHeight}%">${segments}</div></div><span class="chart-year">${y}</span></div>`;
  }).join('')}</div></div></div></div>`;
  const legend=$('#publicationChartLegend');
  if(legend)legend.innerHTML=series.map(s=>`<span class="legend-${s.css}">${esc(s.label)}</span>`).join('');
  if(onSelection)$$('.stacked-segment',el).forEach(b=>b.addEventListener('click',()=>onSelection(b.dataset.year,b.dataset.category)));
}

async function combinedChart(){
  const el=$('#combinedYearChart');if(!el)return;
  const [p,pa,pr,a]=await Promise.all(['publications','patents','projects','awards'].map(loadData));
  const all=[{key:'publications',label:'Publications',values:counts(p)},{key:'patents',label:'Patents',values:counts(pa)},{key:'projects',label:'Projects',values:counts(pr)},{key:'awards',label:'Awards',values:counts(a)}];
  const legend=$('#combinedChartLegend'),caption=$('#combinedChartCaption');
  function draw(mode){
    const selected=mode==='all'?all:[all[0]];
    renderBarChart(el,selected);
    el.setAttribute('aria-label',mode==='all'?'Publications, patents, projects and awards by year':'Publications by year');
    legend.innerHTML=selected.map(s=>`<span class="legend-${s.key}">${s.label}</span>`).join('');
    caption.textContent=mode==='all'?'Grouped annual counts for publications, patents, projects and awards.':'Publication counts by year. Switch to “All outputs” to compare publications, patents, projects and awards.';
    $$('[data-chart-mode]').forEach(b=>{const active=b.dataset.chartMode===mode;b.classList.toggle('is-active',active);b.setAttribute('aria-pressed',active)});
  }
  $$('[data-chart-mode]').forEach(b=>b.addEventListener('click',()=>draw(b.dataset.chartMode)));
  draw('publications');
}

async function researchCharts(){
  if(!$('#yearChart'))return;
  const [raw,taxonomy]=await Promise.all([loadData('publications'),loadData('publication_taxonomy').catch(()=>({}))]);
  const p=enrichPublications(raw,taxonomy);
  singleChart($('#yearChart'),p);
  const t=p.reduce((a,x)=>(a[x.categoryLabel]=(a[x.categoryLabel]||0)+1,a),{}),max=Math.max(...Object.values(t),1);
  $('#topicList').innerHTML=Object.entries(t).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([n,v])=>`<div class="topic-row"><span>${esc(n)}</span><span class="topic-track"><span class="topic-fill" style="display:block;width:${v/max*100}%"></span></span><strong>${v}</strong></div>`).join('');
}

async function initCollection(){
  const root=$('[data-collection]');if(!root)return;
  const name=root.dataset.collection;
  const rawRows=await loadData(name);
  const [taxonomy,mendeley,unpaywall,crossref]=name==='publications'
    ?await Promise.all([loadData('publication_taxonomy').catch(()=>({})),loadData('mendeley_metrics').catch(()=>({})),loadData('unpaywall').catch(()=>({})),loadData('crossref_publication_metrics').catch(()=>({}))])
    :[{},{},{},{}];
  const rows=name==='publications'?enrichPublications(rawRows,taxonomy,mendeley,unpaywall,crossref):rawRows;
  const search=$('#searchInput'),year=$('#yearFilter'),topic=$('#topicFilter'),sort=$('#sortFilter'),count=$('#resultCount'),container=$('#collectionContainer'),empty=$('#emptyState');
  fillSelect(year,rows.map(yearOf),'All years','numeric-desc');
  if(topic){
    if(name==='publications')fillPublicationThemeSelect(topic,taxonomy);
    else fillSelect(topic,rows.map(x=>x.topic).filter(Boolean),'All themes','alpha');
  }
  const card={publications:publicationCard,patents:patentCard,projects:projectCard,awards:awardCard}[name];
  function applyChartSelection(selectedYear,category){
    if(year)year.value=String(selectedYear);
    if(topic&&category)topic.value=`category:${category}`;
    render();
    $('.filter-bar')?.scrollIntoView({behavior:'smooth',block:'center'});
  }
  if(name==='publications')renderPublicationStackedChart($('#collectionYearChart'),rows,applyChartSelection,taxonomy);
  else singleChart($('#collectionYearChart'),rows,y=>applyChartSelection(y,''));
  function render(){
    const q=(search?.value||'').trim().toLowerCase();
    let list=rows.filter(x=>{
      const searchMatch=!q||JSON.stringify(x).toLowerCase().includes(q);
      const yearMatch=!year?.value||String(yearOf(x))===year.value;
      const topicMatch=!topic||!topic.value||(name==='publications'?publicationMatchesTheme(x,topic.value):x.topic===topic.value);
      return searchMatch&&yearMatch&&topicMatch;
    });
    const mode=sort?.value||'date-desc';
    list.sort((a,b)=>mode==='date-asc'?String(a.sortDate||a.date).localeCompare(String(b.sortDate||b.date)):mode==='title-asc'?String(a.title||a.titleEn).localeCompare(String(b.title||b.titleEn)):mode==='citations-desc'?Number(b.citationCount||0)-Number(a.citationCount||0):String(b.sortDate||b.date).localeCompare(String(a.sortDate||a.date)));
    if(count)count.textContent=list.length;
    if(empty)empty.hidden=!!list.length;
    const g=list.reduce((o,x)=>((o[yearOf(x)]??=[]).push(x),o),{});
    container.innerHTML=Object.keys(g).sort((a,b)=>mode==='date-asc'?a-b:b-a).map(y=>`<section class="year-group"><div class="year-heading"><h3>${y}</h3><span>${g[y].length} record${g[y].length===1?'':'s'}</span></div><div class="collection-list">${g[y].map(card).join('')}</div></section>`).join('');
    if(name==='publications')requestAnimationFrame(focusHashPublication);
  }
  [search,year,topic,sort].filter(Boolean).forEach(e=>e.addEventListener(e===search?'input':'change',render));
  $('#clearFilters')?.addEventListener('click',()=>{if(search)search.value='';if(year)year.value='';if(topic)topic.value='';if(sort)sort.value='date-desc';render()});
  render();
}

async function copyText(value){
  if(navigator.clipboard&&window.isSecureContext){
    await navigator.clipboard.writeText(value);
    return;
  }
  const area=document.createElement('textarea');
  area.value=value;
  area.setAttribute('readonly','');
  area.style.position='fixed';
  area.style.opacity='0';
  document.body.appendChild(area);
  area.select();
  const ok=document.execCommand('copy');
  area.remove();
  if(!ok)throw new Error('Copy failed');
}
function closeShareMenus(except=null){
  $$('.share-menu:not([hidden])').forEach(menu=>{
    if(menu===except)return;
    menu.hidden=true;
    menu.closest('.share-wrap')?.querySelector('.share-trigger')?.setAttribute('aria-expanded','false');
  });
}
function publicationInteractions(){
  document.addEventListener('click',async event=>{
    const trigger=event.target.closest('[data-share-url]');
    if(trigger){
      event.preventDefault();
      const title=trigger.dataset.shareTitle||document.title;
      const text=trigger.dataset.shareText||'';
      const url=trigger.dataset.shareUrl||window.location.href;
      if(typeof navigator.share==='function'){
        try{await navigator.share({title,text,url});return}
        catch(error){if(error?.name==='AbortError')return}
      }
      const menu=document.getElementById(trigger.getAttribute('aria-controls'));
      if(!menu)return;
      const opening=menu.hidden;
      closeShareMenus(menu);
      menu.hidden=!opening;
      trigger.setAttribute('aria-expanded',String(opening));
      if(opening)menu.querySelector('[role="menuitem"]')?.focus();
      return;
    }
    const copyButton=event.target.closest('[data-copy-share-url]');
    if(copyButton){
      event.preventDefault();
      const original=copyButton.textContent;
      try{
        await copyText(copyButton.dataset.copyShareUrl||window.location.href);
        copyButton.textContent='✓ Link copied';
      }catch(error){
        copyButton.textContent='Copy failed';
      }
      setTimeout(()=>{copyButton.textContent=original;closeShareMenus()},1500);
      return;
    }
    if(!event.target.closest('.share-wrap'))closeShareMenus();
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    const open=$('.share-menu:not([hidden])');
    const trigger=open?.closest('.share-wrap')?.querySelector('.share-trigger');
    closeShareMenus();
    trigger?.focus();
  });
  window.addEventListener('hashchange',focusHashPublication);
}
function focusHashPublication(){
  let id='';
  try{id=decodeURIComponent(window.location.hash.slice(1))}catch(error){return}
  if(!id||!id.startsWith('pub-'))return;
  const target=document.getElementById(id);
  if(!target)return;
  $$('.publication-card.shared-target').forEach(card=>card.classList.remove('shared-target'));
  target.classList.add('shared-target');
  target.scrollIntoView({behavior:'smooth',block:'center'});
  window.setTimeout(()=>target.classList.remove('shared-target'),5000);
}

function navigationInteractions(){
  const toggle=$('.nav-toggle'),nav=$('.site-nav');
  toggle?.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',open)});
  $$('.site-nav a').forEach(a=>a.addEventListener('click',()=>{nav.classList.remove('open');toggle?.setAttribute('aria-expanded','false')}));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){nav?.classList.remove('open');toggle?.setAttribute('aria-expanded','false')}});
}

document.addEventListener('DOMContentLoaded',()=>{
  setNavigation();
  navigationInteractions();
  publicationInteractions();
  initMeta();
  combinedChart().catch(console.error);
  researchCharts().catch(console.error);
  initCollection().catch(console.error);
});

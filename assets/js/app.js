const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function sendAnalyticsEvent(eventName,link){
  if(typeof window.gtag!=='function'||!eventName)return;
  const href=link?.getAttribute?.('href')||'';
  window.gtag('event',eventName,{
    link_text:String(link?.textContent||'').trim().slice(0,100),
    link_url:/^mailto:/i.test(href)?'mailto:':href,
    page_path:window.location.pathname
  });
}
function analyticsEventFor(target){
  const explicit=target?.closest?.('[data-ga-event]');
  if(explicit)return {name:explicit.dataset.gaEvent,element:explicit};
  const element=target?.closest?.('a,button');
  if(!element)return null;
  const href=String(element.getAttribute('href')||'');
  const text=String(element.textContent||'').trim().toLowerCase();
  let name='';
  if(/search\.crossref\.org|crossref\.org/i.test(href)||text.includes('crossref'))name='crossref_click';
  else if(/openalex\.org/i.test(href)||text.includes('openalex'))name='openalex_click';
  else if(/scholar\.google\./i.test(href)||text.includes('google scholar'))name='scholar_click';
  else if(/doi\.org/i.test(href)||text==='doi ↗')name='doi_click';
  else if(text.includes('open access pdf'))name='oa_pdf_click';
  else if(/orcid\.org/i.test(href)||text==='orcid')name='orcid_click';
  else if(/^mailto:/i.test(href))name='email_click';
  else if(/\.pdf(?:$|[?#])/i.test(href)&&/cv|curriculum/i.test(`${href} ${text}`))name='cv_download';
  else if(element.matches('[data-share-url],[data-copy-share-url]')||element.closest('.share-menu'))name='share_action';
  else if(/patent|tipo|patentscope|google\.com\/patents/i.test(`${href} ${text}`))name='patent_click';
  return name?{name,element}:null;
}

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
const authorDirectory=new Map();
const authorIdDirectory=new Map();
const patentContributionDirectory=new Map();
function normalizeAuthorName(name){return String(name||'').normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,'').trim()}
function authorHasInformation(author){return Boolean(author&&(author.role||author.currentPosition||author.affiliation||author.affiliationZh||(author.email||[]).length||author.telephone||author.orcid||Object.values(author.links||{}).some(Boolean)||(author.contributionTypes||[]).length))}
function buildAuthorDirectory(authors=[]){
  authorDirectory.clear();
  authorIdDirectory.clear();
  authors.forEach(author=>{
    if(!authorHasInformation(author))return;
    if(author.id)authorIdDirectory.set(String(author.id),author);
    [author.name,author.displayName,author.nameZh,...(author.aliases||[])].filter(Boolean).forEach(name=>{
      const key=normalizeAuthorName(name);
      if(key)authorDirectory.set(key,author);
    });
  });
}
function renderAuthor(name){
  const author=authorDirectory.get(normalizeAuthorName(name));
  if(!author)return highlightAuthor(name);
  const me=/Chiu, Wei-Hao|Wei-Hao Chiu/.test(name)?' me':'';
  return `<button class="author-trigger${me}" type="button" data-author-name="${esc(name)}" aria-haspopup="dialog" aria-expanded="false">${esc(name)}</button>`;
}
function renderPersonReference(personId,name){
  const author=authorIdDirectory.get(String(personId||''));
  if(!author)return highlightAuthor(name);
  const me=personId==='wei-hao-chiu'?' me':'';
  return `<button class="author-trigger${me}" type="button" data-author-id="${esc(personId)}" data-author-name="${esc(name)}" aria-haspopup="dialog" aria-expanded="false">${esc(name)}</button>`;
}
function buildPatentContributions(rows=[]){
  patentContributionDirectory.clear();
  rows.forEach(patent=>(patent.inventors||[]).forEach(inventor=>{
    const personId=String(inventor.personId||'');
    if(!personId)return;
    const entry=patentContributionDirectory.get(personId)||{documents:new Set(),families:new Set()};
    entry.documents.add(patent.canonicalId||patent.number);
    entry.families.add(patent.familyId||patent.canonicalId||patent.number);
    patentContributionDirectory.set(personId,entry);
  }));
}
function authorCardHtml(author){
  const emails=(author.email||[]).map(item=>typeof item==='string'?{address:item,label:'Email'}:item).filter(item=>item.address);
  const telephone=typeof author.telephone==='string'?{display:author.telephone}:author.telephone;
  const phoneAction=telephone?.display?`<a${telephone.href?` href="${esc(telephone.href)}"`:''}>Phone: ${esc(telephone.display)}</a>`:'';
  const links={ORCID:author.links?.orcid||(author.orcid?`https://orcid.org/${author.orcid}`:''),LinkedIn:author.links?.linkedin,'Google Scholar':author.links?.googleScholar,OpenAlex:author.links?.openAlex,Scopus:author.links?.scopus,'Web of Science':author.links?.webOfScience,Institution:author.links?.institution,'Personal website':author.links?.personalWebsite};
  const actions=[...emails.map(item=>`<a href="mailto:${esc(item.address)}">${esc(item.label||'Email')}</a>`),phoneAction,...Object.entries(links).filter(([,url])=>url).map(([label,url])=>`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`)].filter(Boolean).join('');
  const position=author.currentPosition&&author.currentPosition!==author.role?`<p class="author-role">Current position: ${esc(author.currentPosition)}</p>`:'';
  const patents=patentContributionDirectory.get(String(author.id||''));
  const patentSummary=patents?`<p class="author-contribution">Patent inventor · ${patents.documents.size} document${patents.documents.size===1?'':'s'} · ${patents.families.size} famil${patents.families.size===1?'y':'ies'}</p>`:'';
  const pending=author.status==='pending'?'<p class="author-verification-note">Patent-record identity only; profile details pending verification.</p>':'';
  return `<button class="author-popover-close" type="button" aria-label="Close author information">×</button><h2>${esc(author.displayName||author.name)}</h2>${author.nameZh?`<p class="author-name-zh">${esc(author.nameZh)}</p>`:''}${author.role?`<p class="author-role">${esc(author.role)}</p>`:''}${position}${author.affiliation?`<p class="author-affiliation">${esc(author.affiliation)}</p>`:''}${author.affiliationZh?`<p class="author-affiliation">${esc(author.affiliationZh)}</p>`:''}${patentSummary}${pending}${actions?`<div class="author-popover-links">${actions}</div>`:''}`;
}
function initAuthorPopover(){
  if(document.documentElement.dataset.authorPopoverReady==='true')return;
  document.documentElement.dataset.authorPopoverReady='true';
  let popover=document.getElementById('authorPopover');
  if(!popover){popover=document.createElement('div');popover.id='authorPopover';popover.className='author-popover';popover.setAttribute('role','dialog');popover.setAttribute('aria-label','Author information');popover.hidden=true;document.body.append(popover)}
  let active=null;
  const close=()=>{if(popover.hidden)return null;const previous=active;popover.hidden=true;active?.setAttribute('aria-expanded','false');active=null;return previous};
  const open=trigger=>{const author=authorIdDirectory.get(String(trigger.dataset.authorId||''))||authorDirectory.get(normalizeAuthorName(trigger.dataset.authorName));if(!author)return;active?.setAttribute('aria-expanded','false');active=trigger;active.setAttribute('aria-expanded','true');popover.innerHTML=authorCardHtml(author);popover.hidden=false;const r=trigger.getBoundingClientRect(),w=Math.min(360,window.innerWidth-24),left=Math.max(12,Math.min(window.innerWidth-w-12,r.left));popover.style.width=`${w}px`;popover.style.left=`${left}px`;popover.style.top=`${Math.min(window.scrollY+r.bottom+8,window.scrollY+window.innerHeight-popover.offsetHeight-12)}px`;popover.querySelector('.author-popover-close')?.focus({preventScroll:true})};
  document.addEventListener('click',event=>{const trigger=event.target.closest('.author-trigger[data-author-name],.author-trigger[data-author-id]');if(trigger){event.preventDefault();active===trigger&&!popover.hidden?close():open(trigger);return}if(event.target.closest('.author-popover-close')||(!popover.hidden&&!event.target.closest('#authorPopover')))close()});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!popover.hidden)close()?.focus()});
}
window.AuthorCards={build:buildAuthorDirectory,render:renderAuthor,renderPerson:renderPersonReference,init:initAuthorPopover,has:author=>authorHasInformation(author)};
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
  const detailSection=location.pathname.toLowerCase().match(/\/(publications|patents)\//)?.[1]||'';
  const prefix=detailSection?'../':'';
  const aboutPages=new Set(['about.html','experience.html','education.html','awards.html']);
  nav.innerHTML=links.map(([href,label])=>{const active=(href===p)||(href===`${detailSection}.html`)||(href==='about.html'&&aboutPages.has(p));return `<a ${active?'aria-current="page" ':''}href="${prefix}${href}">${label}</a>`}).join('');
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

async function initOutputCounts(){
  const names=['publications','patents','projects','awards'];
  const [rows,families]=await Promise.all([
    Promise.all(names.map(name=>loadData(name).catch(()=>null))),
    loadData('patent_families').catch(()=>[])
  ]);
  rows.forEach((records,index)=>{
    if(!Array.isArray(records))return;
    $$(`[data-output-count="${names[index]}"]`).forEach(element=>{
      element.textContent=records.length.toLocaleString();
    });
  });
  if(Array.isArray(families))$$('[data-patent-family-count]').forEach(element=>{element.textContent=families.length.toLocaleString()});
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
function enrichPublications(rows,taxonomy={},mendeley={},unpaywall={},crossref={},openalex={}){
  const map=taxonomy.publications||{};
  const metricMap=mendeley.records||{};
  const oaMap=unpaywall.records||{};
  const crossrefMap=crossref.records||{};
  const openalexMap=openalex.records||{};
  const labels={...FALLBACK_CATEGORY_LABELS,...(taxonomy.categoryLabels||{})};
  return rows.map(p=>{
    const key=publicationKey(p);
    const entry=map[key]||{};
    const category=entry.category||inferPublicationCategory(p);
    const subtopics=Array.isArray(entry.subtopics)?[...new Set(entry.subtopics)]:[];
    return {...p,category,categoryLabel:labels[category]||category,subtopics,mendeley:metricMap[key]||null,openAccess:oaMap[key]||null,crossref:crossrefMap[key]||null,openalex:openalexMap[key]||null};
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

function openAlexImpactMetrics(record={}){
  const items=[];
  const fwci=record.fwci;
  if(fwci!==null&&fwci!==undefined&&Number.isFinite(Number(fwci))&&Number(fwci)>=0){
    items.push(`<span class="action openalex-impact" title="Field-Weighted Citation Impact; world average = 1.00">FWCI ${Number(fwci).toFixed(2)}</span>`);
  }
  const percentile=record.citationPercentile;
  if(percentile!==null&&percentile!==undefined&&Number.isFinite(Number(percentile))&&Number(percentile)>=0&&Number(percentile)<=1){
    const topShare=Math.max(0,100*(1-Number(percentile)));
    const digits=topShare<1?2:1;
    items.push(`<span class="action openalex-impact" title="OpenAlex field-normalized citation percentile">Top ${topShare.toFixed(digits)}% normalized citations</span>`);
  }else if(record.isTop1Percent===true){
    items.push('<span class="action openalex-impact openalex-impact-strong">Top 1% normalized citations</span>');
  }else if(record.isTop10Percent===true){
    items.push('<span class="action openalex-impact openalex-impact-strong">Top 10% normalized citations</span>');
  }
  return items.join('');
}

function publicationCard(p){
  const authors=(p.authors||[]).map(renderAuthor).join(', ');
  const n=Number(p.citationCount||0);
  const scholarUrl=normalizeScholarUrl(p.scholarCitedByUrl)||normalizeScholarUrl(p.citedByUrl);
  const cited=n>0&&scholarUrl
    ?`<a class="action" href="${esc(scholarUrl)}" target="_blank" rel="noopener noreferrer">${n} Google Scholar citation${n===1?'':'s'} ↗</a>`
    :`<span class="action">${n} Google Scholar citation${n===1?'':'s'}</span>`;
  const openalex=p.openalex||{};
  const openalexCount=Number(openalex.citationCount);
  const openalexUrl=normalizeExternalUrl(openalex.url);
  const openalexAction=openalex.status==='verified'&&Number.isFinite(openalexCount)&&openalexCount>=0&&openalexUrl
    ?`<a class="action" href="${esc(openalexUrl)}" target="_blank" rel="noopener noreferrer">${openalexCount.toLocaleString()} OpenAlex citation${openalexCount===1?'':'s'} ↗</a>`
    :'';
  const openalexImpact=openalex.status==='verified'?openAlexImpactMetrics(openalex):'';
  const crossref=p.crossref||{};
  const crossrefCount=Number(crossref.citationCount);
  const crossrefUrl=p.doi?`https://search.crossref.org/search/works?q=${encodeURIComponent(p.doi)}&from_ui=yes`:'';
  const crossrefAction=crossref.status==='verified'&&Number.isFinite(crossrefCount)&&crossrefCount>=0&&crossrefUrl
    ?`<a class="action" href="${esc(crossrefUrl)}" target="_blank" rel="noopener noreferrer">${crossrefCount.toLocaleString()} Crossref citation${crossrefCount===1?'':'s'} ↗</a>`
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
  return `<article class="collection-card publication-card" id="${esc(anchor)}"><div class="card-heading"><h4><a href="${esc(shareUrl)}">${esc(p.title)}</a></h4><span class="date-badge">${esc(p.date)}</span></div><p class="authors">${authors}</p><p class="journal"><em>${esc(p.journal)}</em>${p.volume?`, ${esc(p.volume)}`:''}${p.pages?`, ${esc(p.pages)}`:''} (${p.year}).</p><div class="card-labels">${labels.map(label=>`<span class="card-label">${esc(label)}</span>`).join('')}</div><div class="card-actions">${detailAction}<a class="action" href="${esc(p.doiUrl)}" target="_blank" rel="noopener">DOI ↗</a>${oaAction}${cited}${openalexAction}${openalexImpact}${crossrefAction}${readers}${share}</div></article>`;
}
function patentSlug(p){return String(p.canonicalId||p.number||'patent').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')}
function enrichPatents(rows,metadata={},families=[]){
  const records=metadata.records||{};
  const familyMap=new Map((families||[]).map(family=>[family.familyId,family]));
  const protectedFields=new Set(['titleEn','titleZh','inventors','assigneeEn','assigneeZh','number','canonicalId','aliases','familyId']);
  const enriched=rows.map(p=>{
    const automatic=records[p.canonicalId]||{};
    const merged={...p};
    Object.entries(automatic).forEach(([key,value])=>{
      if(protectedFields.has(key)||value===null||value===''||(Array.isArray(value)&&!value.length))return;
      merged[key]=value;
    });
    merged.family=familyMap.get(p.familyId)||null;
    merged.metadataUpdatedAt=automatic.updatedAt||metadata.lastSuccessfulUpdate||'';
    return merged;
  });
  buildPatentContributions(enriched);
  return enriched;
}
function patentInventors(p){
  const structured=Array.isArray(p.inventors)?p.inventors:[];
  if(structured.length)return structured.map(inventor=>{
    const name=inventor.nameEn||inventor.nameZh||'';
    const trigger=renderPersonReference(inventor.personId,name);
    return inventor.nameZh?`${trigger} <span lang="zh-Hant">(${esc(inventor.nameZh)})</span>`:trigger;
  }).join(', ');
  return (p.inventorsEn||[]).map(renderAuthor).join(', ');
}
function patentDateRows(p){
  const fields=[['Priority date',p.priorityDate],['Filing date',p.filingDate],['Publication date',p.publicationDate],['Grant date',p.grantDate]];
  return fields.filter(([,value])=>value).map(([label,value])=>`<div><dt>${label}</dt><dd>${esc(formatDate(value))}</dd></div>`).join('');
}
function patentDetails(p){
  const dates=patentDateRows(p);
  const classifications=(p.classifications||[]).filter(Boolean);
  const abstract=String(p.abstract||'').trim();
  const application=p.applicationNumber?`<p><strong>Application number:</strong> ${esc(p.applicationNumber)}</p>`:'';
  const legal=p.legalStatus?`<p><strong>Source-reported legal status:</strong> ${esc(p.legalStatus)}</p>`:'';
  const checked=p.metadataUpdatedAt?`<p class="patent-source-note">Metadata last checked ${esc(formatDate(p.metadataUpdatedAt))}. Source-reported status is informational and is not legal advice.</p>`:'<p class="patent-source-note">Automatic metadata has not yet been successfully checked. Manually verified identity fields remain displayed.</p>';
  if(!dates&&!application&&!legal&&!classifications.length&&!abstract&&!checked)return '';
  return `<details class="patent-details"><summary>Patent metadata and abstract</summary><div class="patent-detail-body">${application}${dates?`<dl class="patent-date-grid">${dates}</dl>`:''}${legal}${classifications.length?`<div class="patent-classifications">${classifications.map(item=>`<span>${esc(item)}</span>`).join('')}</div>`:''}${abstract?`<section><h5>Abstract</h5><p>${esc(abstract)}</p></section>`:''}${checked}</div></details>`;
}
function patentCard(p){
  const detailUrl=`patents/${patentSlug(p)}.html`;
  const stage=p.documentStage||p.status||'Status unavailable';
  const family=p.family?`<span class="card-label">${esc(p.family.titleEn||p.familyId)}</span>`:'';
  return `<article class="collection-card patent-card" id="patent-${esc(patentSlug(p))}"><div class="card-heading"><h4><a href="${esc(detailUrl)}">${esc(p.titleEn)}</a></h4><span class="date-badge">${esc(p.date||formatDate(p.publicationDate||p.grantDate))}</span></div>${p.titleZh?`<div class="local-title" lang="zh-Hant">${esc(p.titleZh)}</div>`:''}<div class="card-labels"><span class="card-label">${esc(p.number)}</span><span class="card-label">${esc(p.jurisdiction)}</span><span class="card-label">${esc(stage)}</span>${p.patentType?`<span class="card-label">${esc(p.patentType)}</span>`:''}${family}</div><div class="meta-row">Inventors: ${patentInventors(p)}</div><div class="meta-row">Assignee: ${esc(p.assigneeEn)}${p.assigneeZh?` <span lang="zh-Hant">(${esc(p.assigneeZh)})</span>`:''}</div>${patentDetails(p)}<div class="card-actions"><a class="action" href="${esc(detailUrl)}">Patent details →</a><a class="action" href="${esc(p.url)}" target="_blank" rel="noopener">Patent record ↗</a></div></article>`;
}
function patentFamilyCard(group){
  const family=group[0].family||{};
  const title=family.titleEn||group[0].titleEn;
  const titleZh=family.titleZh||group[0].titleZh;
  const jurisdictions=[...new Set(group.map(p=>p.jurisdiction).filter(Boolean))];
  const latest=[...group].sort((a,b)=>String(b.sortDate).localeCompare(String(a.sortDate)))[0];
  return `<article class="collection-card patent-family-card"><div class="card-heading"><h4>${esc(title)}</h4><span class="date-badge">${esc(latest.year)}</span></div>${titleZh?`<div class="local-title" lang="zh-Hant">${esc(titleZh)}</div>`:''}<div class="card-labels"><span class="card-label">${group.length} document${group.length===1?'':'s'}</span>${jurisdictions.map(value=>`<span class="card-label">${esc(value)}</span>`).join('')}</div><details class="patent-family-documents"><summary>View family documents</summary><div class="patent-family-list">${group.map(patentCard).join('')}</div></details></article>`;
}
/* GRB_PROJECT_FUNDING_START */
function formatProjectFunding(p){
  const amount=Number(p.fundingAmountTwd);
  if(!Number.isFinite(amount)||amount<=0)return '';
  return new Intl.NumberFormat('en-US',{style:'currency',currency:'TWD',maximumFractionDigits:0}).format(amount);
}
function normalizeProjectKeywords(value){
  const rows=Array.isArray(value)?value:String(value||'').split(/[;；、,，\n]+/);
  return [...new Set(rows.map(item=>String(item||'').trim()).filter(Boolean))];
}
function projectResearchDetails(p){
  const abstractZh=String(p.abstractZh||'').trim();
  const abstractEn=String(p.abstractEn||'').trim();
  const keywordsZh=normalizeProjectKeywords(p.keywordsZh);
  const keywordsEn=normalizeProjectKeywords(p.keywordsEn);
  if(!abstractZh&&!abstractEn&&!keywordsZh.length&&!keywordsEn.length)return '';
  const sections=[];
  if(abstractZh)sections.push(`<section class="project-detail-section" lang="zh-Hant"><h5>中文摘要</h5><p>${esc(abstractZh)}</p></section>`);
  if(abstractEn)sections.push(`<section class="project-detail-section" lang="en"><h5>English Abstract</h5><p>${esc(abstractEn)}</p></section>`);
  if(keywordsZh.length)sections.push(`<section class="project-detail-section" lang="zh-Hant"><h5>中文關鍵字</h5><div class="project-keywords">${keywordsZh.map(item=>`<span>${esc(item)}</span>`).join('')}</div></section>`);
  if(keywordsEn.length)sections.push(`<section class="project-detail-section" lang="en"><h5>English Keywords</h5><div class="project-keywords">${keywordsEn.map(item=>`<span>${esc(item)}</span>`).join('')}</div></section>`);
  const sourceUrl=normalizeExternalUrl(p.grbContentSourceUrl||p.grbSourceUrl||p.url);
  const source=sourceUrl?`<p class="project-detail-source">Source: <a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">Government Research Bulletin (GRB) ↗</a></p>`:'<p class="project-detail-source">Source: Government Research Bulletin (GRB)</p>';
  return `<details class="project-research-details"><summary>Project abstracts and keywords <span lang="zh-Hant">／計畫摘要與關鍵字</span></summary><div class="project-detail-body">${sections.join('')}${source}</div></details>`;
}
function projectCard(p){
  const funding=formatProjectFunding(p);
  const fundingRow=funding?`<p class="meta-row"><strong>GRB-reported funding:</strong> ${esc(funding)}${p.fundingAmountK?` <span lang="zh-Hant">（本期經費 ${esc(Number(p.fundingAmountK).toLocaleString())} 千元）</span>`:''}</p>`:'';
  const agency=p.agencyEn||p.agencyZh||'';
  const summary=p.scopeEn?`<p class="summary">${esc(p.scopeEn)}</p>`:'';
  const autoAdded=p.autoAddedFromGRB?'<span class="card-label">GRB auto-synced</span>':'';
  const details=projectResearchDetails(p);
  return `<article class="collection-card project-card"><div class="card-heading"><h4>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titleEn||p.titleZh)}</a>`:esc(p.titleEn||p.titleZh)}</h4><span class="date-badge">${esc(p.period||p.startYear)}</span></div>${p.titleZh?`<div class="local-title" lang="zh-Hant">${esc(p.titleZh)}</div>`:''}<div class="card-labels"><span class="card-label">${esc(p.status)}</span><span class="card-label">${esc(p.role)} · ${esc(p.roleZh)}</span>${p.number?`<span class="card-label">${esc(p.number)}</span>`:''}${autoAdded}</div>${agency?`<p>${esc(agency)}</p>`:''}${fundingRow}${summary}${details}${p.url?`<div class="card-actions"><a class="action" href="${esc(p.url)}" target="_blank" rel="noopener">Project record ↗</a></div>`:''}</article>`;
}
/* GRB_PROJECT_FUNDING_END */
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
  let taxonomy={},rows=rawRows;
  if(name==='publications'){
    const [loadedTaxonomy,mendeley,unpaywall,crossref,openalex]=await Promise.all([loadData('publication_taxonomy').catch(()=>({})),loadData('mendeley_metrics').catch(()=>({})),loadData('unpaywall').catch(()=>({})),loadData('crossref_publication_metrics').catch(()=>({})),loadData('openalex_publication_metrics').catch(()=>({}))]);
    taxonomy=loadedTaxonomy;
    rows=enrichPublications(rawRows,taxonomy,mendeley,unpaywall,crossref,openalex);
  }else if(name==='patents'){
    const [metadata,families]=await Promise.all([loadData('patent_metadata').catch(()=>({})),loadData('patent_families').catch(()=>[])]);
    rows=enrichPatents(rawRows,metadata,families);
    const granted=rows.filter(p=>(p.documentStage||p.status||'').toLowerCase().startsWith('granted')).length;
    const applications=rows.filter(p=>(p.documentStage||p.status||'').toLowerCase().includes('application')).length;
    const familyCount=new Set(rows.map(p=>p.familyId).filter(Boolean)).size;
    $('#patentDocumentTotal')?.replaceChildren(document.createTextNode(String(rows.length)));
    $('#patentFamilyTotal')?.replaceChildren(document.createTextNode(String(familyCount)));
    $('#patentGrantedTotal')?.replaceChildren(document.createTextNode(String(granted)));
    $('#patentApplicationTotal')?.replaceChildren(document.createTextNode(String(applications)));
    const checked=$('#patentMetadataUpdated');
    if(checked)checked.textContent=metadata.lastSuccessfulUpdate?`Automatic metadata last successfully checked ${formatDate(metadata.lastSuccessfulUpdate)}.`:'Automatic metadata has not yet completed a successful full check.';
  }
  const search=$('#searchInput'),year=$('#yearFilter'),topic=$('#topicFilter'),sort=$('#sortFilter'),count=$('#resultCount'),countUnit=$('#resultUnit'),container=$('#collectionContainer'),empty=$('#emptyState');
  const jurisdiction=$('#jurisdictionFilter'),stage=$('#statusFilter'),assignee=$('#assigneeFilter'),view=$('#patentViewFilter');
  fillSelect(year,rows.map(yearOf),'All years','numeric-desc');
  if(topic){
    if(name==='publications')fillPublicationThemeSelect(topic,taxonomy);
    else fillSelect(topic,rows.map(x=>x.topic).filter(Boolean),'All themes','alpha');
  }
  if(name==='patents'){
    fillSelect(jurisdiction,rows.map(x=>x.jurisdiction),'All jurisdictions','alpha');
    fillSelect(stage,rows.map(x=>x.documentStage||x.status),'All stages','alpha');
    fillSelect(assignee,rows.map(x=>x.assigneeEn||x.assigneeZh),'All assignees','alpha');
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
      const jurisdictionMatch=!jurisdiction?.value||x.jurisdiction===jurisdiction.value;
      const stageMatch=!stage?.value||(x.documentStage||x.status)===stage.value;
      const assigneeMatch=!assignee?.value||(x.assigneeEn||x.assigneeZh)===assignee.value;
      return searchMatch&&yearMatch&&topicMatch&&jurisdictionMatch&&stageMatch&&assigneeMatch;
    });
    const mode=sort?.value||'date-desc';
    list.sort((a,b)=>mode==='date-asc'?String(a.sortDate||a.date).localeCompare(String(b.sortDate||b.date)):mode==='title-asc'?String(a.title||a.titleEn).localeCompare(String(b.title||b.titleEn)):mode==='citations-desc'?Number(b.citationCount||0)-Number(a.citationCount||0):String(b.sortDate||b.date).localeCompare(String(a.sortDate||a.date)));
    if(empty)empty.hidden=!!list.length;
    if(name==='patents'&&view?.value==='families'){
      const groups=[...list.reduce((map,item)=>{
        const key=item.familyId||item.canonicalId||item.number;
        if(!map.has(key))map.set(key,[]);
        map.get(key).push(item);
        return map;
      },new Map()).values()];
      groups.sort((a,b)=>{
        const dateA=[...a].sort((x,y)=>String(y.sortDate).localeCompare(String(x.sortDate)))[0]?.sortDate||'';
        const dateB=[...b].sort((x,y)=>String(y.sortDate).localeCompare(String(x.sortDate)))[0]?.sortDate||'';
        return mode==='date-asc'?String(dateA).localeCompare(String(dateB)):mode==='title-asc'?String(a[0].family?.titleEn||a[0].titleEn).localeCompare(String(b[0].family?.titleEn||b[0].titleEn)):String(dateB).localeCompare(String(dateA));
      });
      if(count)count.textContent=groups.length;
      if(countUnit)countUnit.textContent='families shown';
      container.innerHTML=`<div class="collection-list patent-family-results">${groups.map(patentFamilyCard).join('')}</div>`;
      return;
    }
    if(count)count.textContent=list.length;
    if(countUnit)countUnit.textContent=name==='patents'?'documents shown':'shown';
    const g=list.reduce((o,x)=>((o[yearOf(x)]??=[]).push(x),o),{});
    container.innerHTML=Object.keys(g).sort((a,b)=>mode==='date-asc'?a-b:b-a).map(y=>`<section class="year-group"><div class="year-heading"><h3>${y}</h3><span>${g[y].length} record${g[y].length===1?'':'s'}</span></div><div class="collection-list">${g[y].map(card).join('')}</div></section>`).join('');
    if(name==='publications')requestAnimationFrame(focusHashPublication);
  }
  [search,year,topic,sort,jurisdiction,stage,assignee,view].filter(Boolean).forEach(e=>e.addEventListener(e===search?'input':'change',render));
  $('#clearFilters')?.addEventListener('click',()=>{if(search)search.value='';if(year)year.value='';if(topic)topic.value='';if(jurisdiction)jurisdiction.value='';if(stage)stage.value='';if(assignee)assignee.value='';if(view)view.value='families';if(sort)sort.value='date-desc';render()});
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
    const analytics=analyticsEventFor(event.target);
    if(analytics)sendAnalyticsEvent(analytics.name,analytics.element);
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

document.addEventListener('DOMContentLoaded',async()=>{
  setNavigation();
  navigationInteractions();
  publicationInteractions();
  initMeta();
  initOutputCounts().catch(console.error);
  combinedChart().catch(console.error);
  researchCharts().catch(console.error);
  const [authors,patents]=await Promise.all([loadData('authors').catch(()=>[]),loadData('patents').catch(()=>[])]);
  buildAuthorDirectory(authors);
  buildPatentContributions(patents);
  initAuthorPopover();
  initCollection().catch(console.error);
});

/* PUBLICATION_AUTHORSHIP_APP_START */
(() => {
  'use strict';
  if (window.__publicationAuthorshipsLoaded) return;
  window.__publicationAuthorshipsLoaded = true;

  const scriptUrl = document.currentScript?.src || new URL('assets/js/publication-authorships.js', document.baseURI).toString();
  const publicationsUrl = new URL('../../data/publications.json', scriptUrl).toString();
  const normalize = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, '');
  const slugify = value => String(value || 'publication').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'publication';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const escapeAttr = escapeHtml;

  let publications = [];
  let bySlug = new Map();

  function affiliationText(row) {
    const address = row?.address || row?.raw;
    const values = [row?.department, row?.institution, address, ...(!address ? [row?.city, row?.countryCode] : [])]
      .map(value => String(value || '').trim())
      .filter(Boolean);
    const seen = new Set();
    return values.filter(value => {
      const key = normalize(value);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    }).join(', ');
  }

  function markerParts(authorship, affiliationMap) {
    const parts = [];
    if (authorship?.isEqualContributor === true) parts.push({text:'†', label:'Equal contribution'});
    if (authorship?.isCorresponding === true) parts.push({text:'*', label:'Corresponding author'});
    for (const id of authorship?.affiliationIds || []) {
      const label = affiliationMap.get(id)?.label;
      if (label) parts.push({text:label, label:`Affiliation ${label}`});
    }
    return parts;
  }

  function markerHtml(authorship, affiliationMap) {
    const parts = markerParts(authorship, affiliationMap);
    if (!parts.length) return '';
    const text = parts.map(part => part.text).join(',');
    const label = parts.map(part => part.label).join('; ');
    return `<sup class="author-affiliation-ref" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${escapeHtml(text)}</sup>`;
  }

  function renderName(name) {
    if (window.AuthorCards?.render) {
      const rendered = window.AuthorCards.render(name);
      if (rendered) return rendered;
    }
    const mine = ['weihaochiu','chiuweihao','whchiu'].includes(normalize(name));
    return `<span class="author-name${mine ? ' me' : ''}">${escapeHtml(name)}</span>`;
  }

  function renderAuthors(publication) {
    const affiliations = new Map((publication.affiliations || []).map(row => [String(row.id || ''), row]));
    const rows = Array.isArray(publication.authorships) && publication.authorships.length
      ? publication.authorships
      : (publication.authors || []).map((name, index) => ({name, authorOrder:index + 1, affiliationIds:[]}));
    return rows.map(row => `<span class="publication-author">${renderName(row.name)}${markerHtml(row, affiliations)}</span>`).join(', ');
  }

  function renderAffiliations(publication, open = false) {
    const rows = publication.affiliations || [];
    const authorships = publication.authorships || [];
    if (!rows.length && !authorships.some(row => row?.isEqualContributor === true || row?.isCorresponding === true)) return '';
    const affiliationRows = rows.map(row => {
      const text = affiliationText(row);
      if (!text) return '';
      return `<li class="affiliation-entry"><span class="affiliation-label">${escapeHtml(row.label || '')}</span><span>${escapeHtml(text)}</span></li>`;
    }).filter(Boolean).join('');
    const equal = authorships.some(row => row?.isEqualContributor === true);
    const corresponding = authorships.filter(row => row?.isCorresponding === true);
    const legend = [
      equal ? '<li><span class="author-role-marker">†</span><span>These authors contributed equally.</span></li>' : '',
      corresponding.length ? '<li><span class="author-role-marker">*</span><span>Corresponding author' + (corresponding.length > 1 ? 's' : '') + ': ' + corresponding.map(row => escapeHtml(row.name)).join(', ') + '.</span></li>' : ''
    ].filter(Boolean).join('');
    return `<details class="publication-affiliations"${open ? ' open' : ''}><summary>Author affiliations and roles</summary>${affiliationRows ? `<ol class="affiliation-list">${affiliationRows}</ol>` : ''}${legend ? `<ul class="author-role-legend">${legend}</ul>` : ''}</details>`;
  }

  function cardPublication(card) {
    const id = String(card.id || '').replace(/^pub-/, '');
    if (id && bySlug.has(id)) return bySlug.get(id);
    const metaDoi = document.querySelector('meta[name="citation_doi"]')?.content;
    if (metaDoi && card.classList.contains('publication-detail')) return bySlug.get(slugify(metaDoi));
    const doiLink = [...card.querySelectorAll('a[href*="doi.org/"]')].map(a => a.href.split('doi.org/')[1]).find(Boolean);
    return doiLink ? bySlug.get(slugify(decodeURIComponent(doiLink))) : null;
  }

  function enhanceCard(card) {
    const publication = cardPublication(card);
    if (!publication) return;
    const authors = card.querySelector('.authors');
    if (!authors) return;
    const signature = JSON.stringify(publication.authorships || publication.authors || []);
    if (card.dataset.authorshipSignature === signature) return;
    authors.classList.add('publication-authors');
    authors.innerHTML = renderAuthors(publication);
    card.querySelector(':scope > .publication-affiliations')?.remove();
    const detail = card.classList.contains('publication-detail');
    const wrapper = document.createElement('div');
    wrapper.innerHTML = renderAffiliations(publication, detail);
    const affiliationBlock = wrapper.firstElementChild;
    if (affiliationBlock) {
      const journal = card.querySelector('.journal');
      (journal || authors).insertAdjacentElement('afterend', affiliationBlock);
    }
    card.dataset.authorshipSignature = signature;
    window.AuthorCards?.init?.();
  }

  function enhanceAll(root = document) {
    root.querySelectorAll?.('.publication-card').forEach(enhanceCard);
  }

  async function load() {
    try {
      const response = await fetch(publicationsUrl, {cache:'no-store'});
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      publications = await response.json();
      bySlug = new Map(publications.map(publication => [slugify(publication.doi), publication]));
      enhanceAll();
      const observer = new MutationObserver(mutations => {
        for (const mutation of mutations) {
          for (const node of mutation.addedNodes) {
            if (node.nodeType === Node.ELEMENT_NODE) enhanceAll(node.matches?.('.publication-card') ? node.parentElement : node);
          }
        }
      });
      observer.observe(document.body, {childList:true, subtree:true});
    } catch (error) {
      console.warn('Publication authorship metadata could not be loaded.', error);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load, {once:true});
  else load();
})();
/* PUBLICATION_AUTHORSHIP_APP_END */

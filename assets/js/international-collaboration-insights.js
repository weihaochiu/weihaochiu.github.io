(() => {
  'use strict';
  if (window.__internationalCollaborationInsightsLoaded) return;
  window.__internationalCollaborationInsightsLoaded = true;

  const DATA = {
    publications: 'data/publications.json',
    openalex: 'data/openalex_publication_metrics.json',
    journals: 'data/journals.json'
  };
  const COLORS = {international:'#577b72', domestic:'#3b6f9b', foreignOnly:'#72578a', review:'#d6923a', rate:'#a64b45', grid:'#dfe6ec', ink:'#344654'};
  const COUNTRY = {TW:'Taiwan', HK:'Hong Kong', IN:'India', ID:'Indonesia', CN:'China', MO:'Macao', US:'United States'};
  const TYPE = {'international-journal':'International journal','chinese-journal':'Chinese journal','conference':'Conference','other':'Other','unclassified':'Unclassified'};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const norm = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'');
  const doiKey = value => String(value || '').trim().toLowerCase().replace(/^https?:\/\/(?:dx\.)?doi\.org\//,'');
  const yearOf = row => Number(row.year) || Number(String(row.date || '').slice(0,4)) || 0;
  const median = values => { const data=values.filter(Number.isFinite).sort((a,b)=>a-b); if(!data.length)return null; const m=Math.floor(data.length/2); return data.length%2?data[m]:(data[m-1]+data[m])/2; };
  const fmt = value => value == null ? '—' : Number(value).toLocaleString(undefined,{maximumFractionDigits:2});
  const csvEscape = value => { const text=String(value??''); return /[",\n\r]/.test(text)?`"${text.replace(/"/g,'""')}"`:text; };
  const svgEl = (tag, attrs={}) => { const node=document.createElementNS('http://www.w3.org/2000/svg',tag); Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,v)); return node; };

  function downloadCsv(filename, headers, rows) {
    const content='\ufeff'+[headers,...rows].map(row=>row.map(csvEscape).join(',')).join('\r\n')+'\r\n';
    const url=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a'); link.href=url; link.download=filename; document.body.appendChild(link); link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  }

  function downloadSvgPng(svg, filename) {
    if (!svg) return;
    const copy=svg.cloneNode(true); copy.setAttribute('xmlns','http://www.w3.org/2000/svg');
    const blob=new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml;charset=utf-8'});
    const url=URL.createObjectURL(blob), image=new Image();
    image.onload=()=>{const scale=2, box=svg.viewBox.baseVal, canvas=document.createElement('canvas'); canvas.width=box.width*scale; canvas.height=box.height*scale; const ctx=canvas.getContext('2d'); ctx.scale(scale,scale); ctx.fillStyle='#fff'; ctx.fillRect(0,0,box.width,box.height); ctx.drawImage(image,0,0,box.width,box.height); URL.revokeObjectURL(url); canvas.toBlob(png=>{const pngUrl=URL.createObjectURL(png),link=document.createElement('a');link.href=pngUrl;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(pngUrl),1000)},'image/png')};
    image.src=url;
  }

  function buildSection(publications) {
    const years=publications.map(yearOf).filter(Boolean).sort((a,b)=>a-b);
    const types=[...new Set(publications.map(row=>row.publicationType).filter(Boolean))];
    const section=document.createElement('section'); section.className='analytics-section'; section.id='international-collaboration';
    section.innerHTML=`<div class="chart-card">
      <div class="analytics-heading"><div><span class="eyebrow">Author-address analytics</span><h2>International Collaboration</h2></div><div class="chart-actions"><button class="action-button" id="internationalAllCsv" type="button">Download all records CSV</button></div></div>
      <p class="chart-note">International status is stored in each publication record and is based on linked author addresses, not author names, journal country or nationality. Pending records are excluded from the collaboration-rate denominator.</p>
      <div class="international-collaboration-filters"><label>From year<select id="internationalYearFrom"></select></label><label>To year<select id="internationalYearTo"></select></label><label>Publication type<select id="internationalType"><option value="">All types</option>${types.map(value=>`<option value="${esc(value)}">${esc(TYPE[value]||value)}</option>`).join('')}</select></label><label>Search publication<input id="internationalSearch" type="search" placeholder="Title or DOI…"></label></div>
      <div class="international-collaboration-grid" id="internationalSummary"></div>
      <div class="international-collaboration-charts">
        <div><div class="analytics-heading"><h3>Annual Collaboration Trend</h3><div class="chart-actions"><button class="action-button" id="internationalTrendCsv">CSV</button><button class="action-button" id="internationalTrendPng">PNG</button></div></div><div class="analytics-chart-frame"><div class="analytics-chart-host" id="internationalTrendChart"></div></div><p class="chart-note">Bars show publication counts; the red line shows international ÷ (international + domestic). Foreign-only and pending records are not included in the rate.</p></div>
        <div><div class="analytics-heading"><h3>Partner Countries / Regions</h3><div class="chart-actions"><button class="action-button" id="internationalCountryCsv">CSV</button><button class="action-button" id="internationalCountryPng">PNG</button></div></div><div class="analytics-chart-frame"><div class="analytics-chart-host" id="internationalCountryChart"></div></div><p class="chart-note">One paper with multiple partner countries is counted once for each country.</p></div>
      </div>
      <div class="international-section-spacer"><div class="analytics-heading"><h3>Partner Institutions</h3><div class="chart-actions"><button class="action-button" id="internationalInstitutionCsv">CSV</button></div></div><div class="table-wrap"><table class="journal-table"><thead><tr><th>Institution</th><th>Country / region</th><th>Joint publications</th><th>First year</th><th>Latest year</th></tr></thead><tbody id="internationalInstitutionBody"></tbody></table></div></div>
      <div class="international-section-spacer"><div class="analytics-heading"><div><h3>International vs Domestic Impact</h3><p class="chart-note">Descriptive comparison only; publication age and field are not controlled, so the table does not imply causation.</p></div></div><div class="table-wrap"><table class="journal-table international-impact-table"><thead><tr><th>Group</th><th>Publications</th><th>Median Google Scholar citations</th><th>Median OpenAlex citations</th><th>Median FWCI</th><th>Q1 ratio</th></tr></thead><tbody id="internationalImpactBody"></tbody></table></div></div>
      <div class="international-section-spacer"><div class="analytics-heading"><h3>Publication-level Verification Table</h3><div class="chart-actions"><button class="action-button" id="internationalVisibleCsv">Download visible CSV</button></div></div><div class="table-wrap"><table class="journal-table international-audit-table"><thead><tr><th>Year</th><th>Publication</th><th>Type</th><th>Status</th><th>Countries / regions</th><th>Foreign institutions</th><th>Evidence</th><th>Confidence</th><th>Last evaluated</th></tr></thead><tbody id="internationalAuditBody"></tbody></table></div><p class="analytics-status" id="internationalStatus"></p></div>
      <a class="back-to-top" href="#top">Back to top ↑</a>
    </div>`;
    const from=section.querySelector('#internationalYearFrom'),to=section.querySelector('#internationalYearTo');
    [...new Set(years)].forEach(year=>{from.insertAdjacentHTML('beforeend',`<option value="${year}">${year}</option>`);to.insertAdjacentHTML('beforeend',`<option value="${year}">${year}</option>`)}); from.value=String(Math.min(...years)); to.value=String(Math.max(...years));
    return section;
  }

  function renderTrend(host, rows) {
    const grouped=new Map(); rows.forEach(row=>{const year=yearOf(row);if(!year)return;const item=grouped.get(year)||{year,international:0,domestic:0,foreignOnly:0,review:0};const status=row.internationalCollaboration?.status; if(status==='international')item.international++;else if(status==='domestic')item.domestic++;else if(status==='foreign-only')item.foreignOnly++;else item.review++;grouped.set(year,item)});
    const data=[...grouped.values()].sort((a,b)=>a.year-b.year); host.innerHTML=''; if(!data.length){host.innerHTML='<div class="chart-empty">No records match these filters.</div>';return {data,svg:null};}
    const W=Math.max(760,data.length*48+110),H=390,m={l:52,r:54,t:30,b:48},innerW=W-m.l-m.r,innerH=H-m.t-m.b,max=Math.max(1,...data.map(d=>d.international+d.domestic+d.foreignOnly+d.review)),step=innerW/data.length,barW=Math.min(30,step*.66),svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H,role:'img','aria-label':'Annual international collaboration trend'});
    [0,.25,.5,.75,1].forEach(f=>{const y=m.t+innerH*(1-f);svg.append(svgEl('line',{x1:m.l,y1:y,x2:W-m.r,y2:y,stroke:COLORS.grid}));const label=svgEl('text',{x:m.l-8,y:y+4,'text-anchor':'end',fill:COLORS.ink,'font-size':10});label.textContent=String(Math.round(max*f));svg.append(label)});
    const points=[]; data.forEach((d,i)=>{const x=m.l+step*i+(step-barW)/2;let bottom=m.t+innerH;[['international',COLORS.international],['domestic',COLORS.domestic],['foreignOnly',COLORS.foreignOnly],['review',COLORS.review]].forEach(([key,color])=>{const h=d[key]/max*innerH;if(h){bottom-=h;svg.append(svgEl('rect',{x,y:bottom,width:barW,height:h,fill:color}))}});const label=svgEl('text',{x:x+barW/2,y:H-23,'text-anchor':'middle',fill:COLORS.ink,'font-size':10,transform:`rotate(-45 ${x+barW/2} ${H-23})`});label.textContent=d.year;svg.append(label);const known=d.international+d.domestic,rate=known?d.international/known*100:null;if(rate!=null)points.push([x+barW/2,m.t+innerH*(1-rate/100),rate])});
    if(points.length){const path=svgEl('polyline',{points:points.map(p=>`${p[0]},${p[1]}`).join(' '),fill:'none',stroke:COLORS.rate,'stroke-width':2.5});svg.append(path);points.forEach(p=>svg.append(svgEl('circle',{cx:p[0],cy:p[1],r:3.5,fill:COLORS.rate})));}
    const legend=[['International',COLORS.international],['Domestic',COLORS.domestic],['Foreign only',COLORS.foreignOnly],['Needs review',COLORS.review],['International rate',COLORS.rate]];legend.forEach((item,i)=>{const x=m.l+i*125;svg.append(svgEl('rect',{x,y:8,width:10,height:10,fill:item[1]}));const t=svgEl('text',{x:x+15,y:17,fill:COLORS.ink,'font-size':10});t.textContent=item[0];svg.append(t)});host.append(svg);return {data,svg};
  }

  function renderCountries(host, rows) {
    const map=new Map();rows.filter(row=>row.internationalCollaboration?.status==='international').forEach(row=>(row.internationalCollaboration.partnerCountryCodes||[]).forEach(code=>{const item=map.get(code)||{code,count:0,years:new Set(),institutions:new Set()};item.count++;item.years.add(yearOf(row));(row.internationalCollaboration.partnerInstitutions||[]).filter(x=>x.countryCode===code).forEach(x=>item.institutions.add(x.name));map.set(code,item)}));
    const data=[...map.values()].sort((a,b)=>b.count-a.count||a.code.localeCompare(b.code));host.innerHTML='';if(!data.length){host.innerHTML='<div class="chart-empty">No international partner countries match these filters.</div>';return {data,svg:null};}
    const W=520,H=Math.max(280,data.length*56+70),m={l:145,r:40,t:24,b:38},innerW=W-m.l-m.r,max=Math.max(...data.map(d=>d.count)),svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H,role:'img','aria-label':'Partner country publication counts'});
    data.forEach((d,i)=>{const y=m.t+i*56,w=d.count/max*innerW;const name=COUNTRY[d.code]||d.code,label=svgEl('text',{x:m.l-9,y:y+21,'text-anchor':'end',fill:COLORS.ink,'font-size':12});label.textContent=name;svg.append(label,svgEl('rect',{x:m.l,y,width:w,height:28,rx:3,fill:COLORS.international}));const count=svgEl('text',{x:m.l+w+7,y:y+19,fill:COLORS.ink,'font-size':11,'font-weight':700});count.textContent=d.count;svg.append(count)});host.append(svg);return {data,svg};
  }

  async function init() {
    try {
      const [publications,oaPayload,journalPayload]=await Promise.all(Object.values(DATA).map(url=>fetch(url,{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error(`${url}: ${response.status}`);return response.json()})));
      const section=buildSection(publications),collaboration=document.getElementById('collaboration');if(!collaboration)return;collaboration.insertAdjacentElement('afterend',section);
      const jump=document.querySelector('.analytics-jump-links');if(jump&&!jump.querySelector('a[href="#international-collaboration"]')){const link=document.createElement('a');link.href='#international-collaboration';link.textContent='International';jump.insertBefore(link,jump.querySelector('a[href="#jcr"]')||null)}
      const oa=oaPayload.records||{},journalRows=Object.values(journalPayload.journals||{}),journalMap=new Map();journalRows.forEach(j=>[j.title,...(j.aliases||[])].forEach(name=>journalMap.set(norm(name),j)));
      const latestQuartile=publication=>{const journal=journalMap.get(norm(publication.journal));if(!journal)return'';const years=Object.keys(journal.metricsByYear||{}).map(Number).filter(Number.isFinite).sort((a,b)=>b-a);for(const year of years){const q=journal.metricsByYear[String(year)]?.bestQuartile;if(q)return q}return''};
      let current=[],trend={data:[],svg:null},countries={data:[],svg:null},institutions=[];
      const controls=['internationalYearFrom','internationalYearTo','internationalType','internationalSearch'].map(id=>section.querySelector('#'+id));

      function rowsCsv(rows){return rows.map(row=>{const c=row.internationalCollaboration||{};return [yearOf(row),row.doi,row.title,row.publicationType,c.status,(c.countryCodes||[]).join('; '),(c.partnerCountryCodes||[]).join('; '),(c.partnerInstitutions||[]).map(x=>x.name).join('; '),c.determinationMethod,c.confidence,c.manualOverride,c.requiresManualReview,(c.sources||[]).join('; '),c.lastEvaluated,(c.warnings||[]).join('; ')]})}
      const csvHeaders=['year','doi','title','publication_type','collaboration_status','countries','partner_countries','partner_institutions','determination_method','confidence','manual_override','requires_manual_review','sources','last_evaluated','warnings'];

      function render() {
        const from=Number(controls[0].value),to=Number(controls[1].value),type=controls[2].value,query=norm(controls[3].value);current=publications.filter(row=>{const year=yearOf(row);return year>=from&&year<=to&&(!type||row.publicationType===type)&&(!query||norm(`${row.title} ${row.doi}`).includes(query))});
        const counts={international:0,domestic:0,'foreign-only':0,'needs-review':0};current.forEach(row=>{const status=row.internationalCollaboration?.status||'needs-review';counts[status]=(counts[status]||0)+1});const known=counts.international+counts.domestic,rate=known?counts.international/known*100:0,partnerCodes=new Set(),partnerNames=new Set();current.forEach(row=>{const c=row.internationalCollaboration||{};(c.partnerCountryCodes||[]).forEach(x=>partnerCodes.add(x));(c.partnerInstitutions||[]).forEach(x=>partnerNames.add(`${x.countryCode}|${x.name}`))});
        section.querySelector('#internationalSummary').innerHTML=[['International publications',counts.international,'Verified cross-border author addresses'],['International rate',`${rate.toFixed(1)}%`,`${counts.international} of ${known} classifiable publications`],['Partner countries / regions',partnerCodes.size,[...partnerCodes].map(x=>COUNTRY[x]||x).join(', ')||'None'],['Partner institutions',partnerNames.size,'Unique verified foreign affiliations'],['Pending review',counts['needs-review'],'Excluded from rate'],['Address-data coverage',`${current.length?((current.length-counts['needs-review'])/current.length*100).toFixed(1):'0.0'}%`,`${current.length-counts['needs-review']} of ${current.length} publications`]].map(x=>`<div class="summary-card"><span>${esc(x[0])}</span><strong>${esc(x[1])}</strong><small>${esc(x[2])}</small></div>`).join('');
        trend=renderTrend(section.querySelector('#internationalTrendChart'),current);countries=renderCountries(section.querySelector('#internationalCountryChart'),current);
        const institutionMap=new Map();current.filter(row=>row.internationalCollaboration?.status==='international').forEach(row=>(row.internationalCollaboration.partnerInstitutions||[]).forEach(inst=>{const key=`${inst.countryCode}|${norm(inst.name)}`,item=institutionMap.get(key)||{name:inst.name,code:inst.countryCode,count:0,years:[]};item.count++;item.years.push(yearOf(row));institutionMap.set(key,item)}));institutions=[...institutionMap.values()].sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name));section.querySelector('#internationalInstitutionBody').innerHTML=institutions.map(x=>`<tr><td class="journal-name">${esc(x.name)}</td><td>${esc(COUNTRY[x.code]||x.code)}</td><td class="numeric">${x.count}</td><td class="numeric">${Math.min(...x.years)}</td><td class="numeric">${Math.max(...x.years)}</td></tr>`).join('')||'<tr><td colspan="5">No partner institutions match these filters.</td></tr>';
        const impactRows=['international','domestic'].map(status=>{const rows=current.filter(row=>row.internationalCollaboration?.status===status),gs=rows.map(row=>Number(row.citationCount)).filter(Number.isFinite),oaCites=rows.map(row=>Number(oa[doiKey(row.doi)]?.citationCount)).filter(Number.isFinite),fwci=rows.map(row=>Number(oa[doiKey(row.doi)]?.fwci)).filter(Number.isFinite),qRows=rows.filter(row=>latestQuartile(row)),q1=qRows.filter(row=>latestQuartile(row)==='Q1').length;return {status,count:rows.length,gs:median(gs),oa:median(oaCites),fwci:median(fwci),q1:qRows.length?q1/qRows.length*100:null,qCoverage:qRows.length}});section.querySelector('#internationalImpactBody').innerHTML=impactRows.map(x=>`<tr><td><span class="collaboration-status ${x.status}">${x.status==='international'?'International':'Domestic'}</span></td><td class="numeric">${x.count}</td><td class="numeric">${fmt(x.gs)}</td><td class="numeric">${fmt(x.oa)}</td><td class="numeric">${fmt(x.fwci)}</td><td class="numeric">${x.q1==null?'—':x.q1.toFixed(1)+'%'} <small>(${x.qCoverage}/${x.count})</small></td></tr>`).join('');
        section.querySelector('#internationalAuditBody').innerHTML=current.slice().sort((a,b)=>yearOf(b)-yearOf(a)||String(a.title).localeCompare(String(b.title))).map(row=>{const c=row.internationalCollaboration||{},countries=(c.countryCodes||[]).map(x=>COUNTRY[x]||x).join(', ')||'—',institutions=(c.partnerInstitutions||[]).map(x=>x.name).join('; ')||'—',sources=(c.sources||[]).join(', ')||'—',slug=String(row.id||row.doi||row.title).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');return `<tr><td class="numeric">${yearOf(row)||'—'}</td><td class="journal-name"><a href="publications/${esc(slug)}.html">${esc(row.title||row.doi)}</a><br><small>${esc(row.doi||row.id||'')}</small></td><td>${esc(TYPE[row.publicationType]||row.publicationType||'—')}</td><td><span class="collaboration-status ${esc(c.status||'needs-review')}">${esc(c.status||'needs-review')}</span>${c.manualOverride?'<br><small>Manual lock</small>':''}</td><td>${esc(countries)}</td><td>${esc(institutions)}</td><td>${esc(sources)}${c.manualNote?`<br><small>${esc(c.manualNote)}</small>`:''}</td><td>${esc(c.confidence||'—')}</td><td>${esc(c.lastEvaluated||'—')}</td></tr>`}).join('')||'<tr><td colspan="9">No publications match these filters.</td></tr>';
        section.querySelector('#internationalStatus').textContent=`Showing ${current.length} of ${publications.length} publications. ${counts.international} international, ${counts.domestic} domestic, ${counts['foreign-only']} foreign-only and ${counts['needs-review']} pending review.`;
      }
      controls.forEach(control=>control.addEventListener(control.type==='search'?'input':'change',render));render();
      section.querySelector('#internationalAllCsv').addEventListener('click',()=>downloadCsv('international-collaboration-all-records.csv',csvHeaders,rowsCsv(publications)));
      section.querySelector('#internationalVisibleCsv').addEventListener('click',()=>downloadCsv('international-collaboration-visible-records.csv',csvHeaders,rowsCsv(current)));
      section.querySelector('#internationalTrendCsv').addEventListener('click',()=>downloadCsv('international-collaboration-annual-trend.csv',['year','international','domestic','foreign_only','needs_review','international_rate_percent'],trend.data.map(x=>[x.year,x.international,x.domestic,x.foreignOnly,x.review,(x.international+x.domestic)?(x.international/(x.international+x.domestic)*100).toFixed(1):''])));
      section.querySelector('#internationalTrendPng').addEventListener('click',()=>downloadSvgPng(trend.svg,'international-collaboration-annual-trend.png'));
      section.querySelector('#internationalCountryCsv').addEventListener('click',()=>downloadCsv('international-collaboration-partner-countries.csv',['country_code','country_region','publications','first_year','latest_year','institution_count'],countries.data.map(x=>[x.code,COUNTRY[x.code]||x.code,x.count,Math.min(...x.years),Math.max(...x.years),x.institutions.size])));
      section.querySelector('#internationalCountryPng').addEventListener('click',()=>downloadSvgPng(countries.svg,'international-collaboration-partner-countries.png'));
      section.querySelector('#internationalInstitutionCsv').addEventListener('click',()=>downloadCsv('international-collaboration-partner-institutions.csv',['institution','country_code','country_region','publications','first_year','latest_year'],institutions.map(x=>[x.name,x.code,COUNTRY[x.code]||x.code,x.count,Math.min(...x.years),Math.max(...x.years)])));
    } catch (error) { console.error(error); }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();

(()=>{
  'use strict';

  const root=document.getElementById('researchAreas');
  if(!root)return;

  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[char]));

  async function loadResearchData(name){
    const local=`data/${name}.json`;
    try{
      const response=await fetch(local,{cache:'no-store'});
      if(response.ok)return response.json();
    }catch(error){/* Fall through to the published site URL. */}
    const remote=`https://weihaochiu.github.io/data/${name}.json`;
    const response=await fetch(remote,{cache:'no-store'});
    if(!response.ok)throw new Error(`Unable to load ${name}`);
    return response.json();
  }

  function publicationKey(publication){
    return String(publication.doi||'').trim().toLowerCase();
  }

  function inferCategory(publication){
    const text=`${publication.topic||''} ${publication.title||''} ${(publication.tags||[]).join(' ')}`.toLowerCase();
    if(/redox flow|flow batter|vrfb/.test(text))return 'RFB';
    if(/perovskite|hole-transport|space pv/.test(text))return 'PSC';
    if(/dye-sensitized|dssc/.test(text))return 'DSSC';
    return 'Other';
  }

  function enrichPublications(publications,taxonomy,mendeley){
    const categoryMap=taxonomy.publications||{};
    const metricMap=mendeley.records||{};
    return publications.map(publication=>{
      const key=publicationKey(publication);
      const categoryEntry=categoryMap[key]||{};
      return {
        ...publication,
        category:categoryEntry.category||inferCategory(publication),
        mendeley:metricMap[key]||null
      };
    });
  }

  function publicationYear(publication){
    const year=Number(publication.year||String(publication.sortDate||publication.date||'').slice(0,4));
    return Number.isFinite(year)?year:0;
  }

  function publicationDateValue(publication){
    const year=publicationYear(publication);
    const month=Number(publication.month||String(publication.date||'').slice(5,7)||1);
    return year*100+(Number.isFinite(month)?month:1);
  }

  function normalizeScholarUrl(value){
    let url=String(value||'').trim();
    if(!url)return '';
    const secondHttps=url.indexOf('https://',8);
    const secondHttp=url.indexOf('http://',7);
    const second=[secondHttps,secondHttp].filter(index=>index>0).sort((a,b)=>a-b)[0];
    if(second)url=url.slice(second);
    if(url.startsWith('//'))url=`https:${url}`;
    else if(url.startsWith('/'))url=`https://scholar.google.com${url}`;
    try{
      const parsed=new URL(url,'https://scholar.google.com');
      if(!/^scholar\.google\./i.test(parsed.hostname))return '';
      parsed.protocol='https:';
      parsed.hostname='scholar.google.com';
      return parsed.toString();
    }catch(error){return ''}
  }

  function normalizeMendeleyUrl(value){
    const url=String(value||'').trim();
    if(!url)return '';
    try{
      const parsed=new URL(url);
      const host=parsed.hostname.toLowerCase();
      if(parsed.protocol!=='https:'||!(host==='mendeley.com'||host.endsWith('.mendeley.com')))return '';
      return parsed.toString();
    }catch(error){return ''}
  }

  function plural(value,singular,pluralForm=`${singular}s`){
    return Number(value)===1?singular:pluralForm;
  }

  function publicationCard(publication){
    const year=publicationYear(publication);
    const journal=publication.journal||'Journal information unavailable';
    const doiUrl=publication.doiUrl||(`https://doi.org/${encodeURIComponent(publication.doi||'')}`);
    const citationCount=Math.max(0,Number(publication.citationCount||0));
    const scholarUrl=normalizeScholarUrl(publication.scholarCitedByUrl)||normalizeScholarUrl(publication.citedByUrl);
    const citationAction=scholarUrl
      ?`<a class="action" href="${esc(scholarUrl)}" target="_blank" rel="noopener noreferrer">${citationCount} Google Scholar ${plural(citationCount,'citation')} ↗</a>`
      :`<span class="action">${citationCount} Google Scholar ${plural(citationCount,'citation')}</span>`;

    const metric=publication.mendeley||{};
    const readerCount=Number(metric.readerCount);
    const mendeleyUrl=normalizeMendeleyUrl(metric.url);
    let readerAction='<span class="action">Mendeley readers unavailable</span>';
    if(metric.status==='verified'&&Number.isFinite(readerCount)&&readerCount>=0){
      readerAction=mendeleyUrl
        ?`<a class="action" href="${esc(mendeleyUrl)}" target="_blank" rel="noopener noreferrer">${readerCount} Mendeley ${plural(readerCount,'reader')} ↗</a>`
        :`<span class="action">${readerCount} Mendeley ${plural(readerCount,'reader')}</span>`;
    }

    return `<article class="research-publication">
      <h4><a href="${esc(doiUrl)}" target="_blank" rel="noopener">${esc(publication.title)}</a></h4>
      <p class="research-publication-meta"><em>${esc(journal)}</em>${year?` · ${year}`:''}</p>
      <div class="research-publication-actions">
        <a class="action" href="${esc(doiUrl)}" target="_blank" rel="noopener">DOI ↗</a>
        ${citationAction}
        ${readerAction}
      </div>
    </article>`;
  }

  function publicationGroup(title,note,publications){
    const content=publications.length
      ?publications.map(publicationCard).join('')
      :'<p class="research-publication-empty">No publications are currently assigned to this theme.</p>';
    return `<section class="research-publication-group">
      <h3>${esc(title)}</h3>
      <p class="group-note">${esc(note)}</p>
      <div class="research-publication-list">${content}</div>
    </section>`;
  }

  function researchArea(area,index,publications,featuredCount){
    const matching=publications.filter(publication=>publication.category===area.category);
    const years=matching.map(publicationYear).filter(Boolean);
    const firstYear=years.length?Math.min(...years):null;
    const lastYear=years.length?Math.max(...years):null;
    const period=firstYear&&lastYear?(firstYear===lastYear?String(firstYear):`${firstYear}–${lastYear}`):'Not available';
    const newest=[...matching]
      .sort((a,b)=>publicationDateValue(b)-publicationDateValue(a)||String(a.title).localeCompare(String(b.title)))
      .slice(0,featuredCount);
    const mostCited=[...matching]
      .sort((a,b)=>Number(b.citationCount||0)-Number(a.citationCount||0)||publicationDateValue(b)-publicationDateValue(a))
      .slice(0,featuredCount);
    const paragraphs=(area.description||[]).map(paragraph=>`<p>${esc(paragraph)}</p>`).join('');

    return `<article class="research-topic" id="research-${esc(String(area.key||area.category).toLowerCase())}">
      <header class="research-topic-heading">
        <span class="research-topic-number">${String(index+1).padStart(2,'0')}</span>
        <div class="research-topic-title">
          <h2>${esc(area.title)}</h2>
          <div class="research-topic-meta">
            <span>Research period: ${esc(period)}</span>
            <span>${matching.length} peer-reviewed ${plural(matching.length,'publication')}</span>
          </div>
        </div>
      </header>
      <div class="research-topic-copy">${paragraphs}</div>
      <div class="research-publication-grid">
        ${publicationGroup('Newest Publications',`The ${featuredCount} most recent papers assigned to this research theme.`,newest)}
        ${publicationGroup('Most Cited Publications',`The ${featuredCount} papers with the highest current Google Scholar citation counts.`,mostCited)}
      </div>
    </article>`;
  }

  async function initResearchPage(){
    try{
      const [configuration,rawPublications,taxonomy,mendeley]=await Promise.all([
        loadResearchData('research_areas'),
        loadResearchData('publications'),
        loadResearchData('publication_taxonomy').catch(()=>({})),
        loadResearchData('mendeley_metrics').catch(()=>({}))
      ]);
      const publications=enrichPublications(rawPublications,taxonomy,mendeley);
      const featuredCount=Math.max(1,Number(configuration.featuredPublicationCount||3));
      root.innerHTML=(configuration.areas||[])
        .map((area,index)=>researchArea(area,index,publications,featuredCount))
        .join('');
    }catch(error){
      console.error(error);
      root.innerHTML='<p class="research-error">Research information could not be loaded. Please refresh the page or try again later.</p>';
    }
  }

  initResearchPage();
})();

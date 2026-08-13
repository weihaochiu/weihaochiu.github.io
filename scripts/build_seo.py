#!/usr/bin/env python3
from __future__ import annotations
import html, json, re
from datetime import date
from pathlib import Path
from urllib.parse import quote

from publication_scope import is_research_publication

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = 'https://weihaochiu.github.io'
TODAY = date.today().isoformat()
EMAIL_LINKS = '<a href="mailto:weihao.chiu@gmail.com">Personal Email</a><a href="mailto:d000019005@cgu.edu.tw">CGU Email</a>'
GA_TAG = '''<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-G82XWMCJDE"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-G82XWMCJDE');
</script>'''
PRIVATE_PATHS = ('bems-fe5049fb.html', 'website-insight-ea929558.html', 'publication-insights-4d8c7a.html')
CITATION_META_START = '<!-- SEO_CITATION_META_START -->'
CITATION_META_END = '<!-- SEO_CITATION_META_END -->'
PATENT_LLMS_START = '<!-- PATENT_LLMS_START -->'
PATENT_LLMS_END = '<!-- PATENT_LLMS_END -->'

def robots_text():
  agents = ('*', 'Googlebot', 'Bingbot', 'OAI-SearchBot', 'GPTBot', 'ChatGPT-User',
            'ClaudeBot', 'Claude-SearchBot', 'PerplexityBot', 'Google-Extended',
            'Applebot-Extended')
  blocks = []
  for agent in agents:
    lines = [f'User-agent: {agent}', 'Allow: /']
    lines += [f'Disallow: /{path}' for path in PRIVATE_PATHS]
    blocks.append('\n'.join(lines))
  return '\n\n'.join(blocks) + f'\n\nSitemap: {SITE_URL}/sitemap.xml\n'

PERSON = {
  '@context': 'https://schema.org', '@type': 'Person', '@id': SITE_URL + '/#person',
  'name': 'Wei-Hao Chiu', 'alternateName': ['邱偉豪', 'Chiu, Wei-Hao'],
  'honorificSuffix': 'Ph.D.', 'url': SITE_URL + '/',
  'image': SITE_URL + '/assets/images/profile.jpg', 'jobTitle': 'Associate Researcher',
  'email': ['mailto:weihao.chiu@gmail.com', 'mailto:d000019005@cgu.edu.tw'],
  'affiliation': {'@type':'Organization','name':'Chang Gung University','url':'https://www.cgu.edu.tw/'},
  'worksFor': {'@type':'Organization','name':'Center for Sustainability and Energy Technologies, Chang Gung University'},
  'knowsAbout': ['Perovskite solar cells','Tin and tin-lead perovskite photovoltaics','Scalable photovoltaic manufacturing','Vacuum-flash crystallization','Blade coating','Slot-die coating','Charge-transport layers','Self-assembled monolayers','Photoluminescence and electroluminescence','Quasi-Fermi level splitting','Photovoltaic reliability','Space photovoltaics','Tandem solar cells','Vanadium redox flow batteries'],
  'sameAs': ['https://scholar.google.com/citations?user=ZYbNQb8AAAAJ&hl=en','https://orcid.org/0000-0003-4484-3117','https://www.scopus.com/authid/detail.uri?authorId=7201503537','https://www.webofscience.com/wos/author/record/JCE-6812-2023','https://pure.lib.cgu.edu.tw/en/persons/wei-hao-chiu/publications/','https://www.cgu.edu.tw/cset-en/FullTimeProfessorManagement/Detail/e3d82caf-b69a-4ee3-ac95-0d1558e22d83?nodeId=17439','https://www.researchgate.net/profile/Wei-Hao-Chiu','https://www.linkedin.com/in/wei-hao-chiu-a208a9b0/','https://openalex.org/works?filter=authorships.author.id:a5007707999']
}

def esc(v): return html.escape(str(v or ''), quote=True)
def slugify(value): return re.sub(r'[^a-z0-9]+','-',str(value).lower()).strip('-') or 'publication'
def publication_slug(p): return slugify(p.get('id') or p.get('doi') or p.get('title'))
def publication_type(p): return str(p.get('publicationType') or 'international-journal')
def is_thesis(p): return publication_type(p) == 'thesis'
def publication_type_label(p):
  return {
    'international-journal':'International Journal Publication',
    'chinese-journal':'Chinese Journal Publication',
    'conference':'Conference Publication',
    'other':'Other Scholarly Output',
    'unclassified':'Unclassified Scholarly Output',
    'thesis':'Ph.D. Dissertation' if p.get('documentType') == 'doctoral-thesis' else 'M.S. Thesis',
  }.get(publication_type(p),'Scholarly Output')
AUTHOR_MAP = {}
def normalize_author_name(name): return re.sub(r'[^a-z0-9]+', '', str(name or '').lower())
def author_has_information(author):
  return bool(author and (author.get('role') or author.get('affiliation') or author.get('email') or author.get('orcid') or any((author.get('links') or {}).values())))
def author_html(name):
  author = AUTHOR_MAP.get(normalize_author_name(name))
  if not author_has_information(author):
    return '<strong class="me">'+esc(name)+'</strong>' if name in ('Chiu, Wei-Hao','Wei-Hao Chiu') else esc(name)
  me = ' me' if name in ('Chiu, Wei-Hao','Wei-Hao Chiu') else ''
  return '<button class="author-trigger'+me+'" type="button" data-author-name="'+esc(name)+'" aria-haspopup="dialog" aria-expanded="false">'+esc(name)+'</button>'

# PUBLICATION_AUTHORSHIP_BUILD_START
def publication_authorships(p):
  rows=p.get('authorships')
  if isinstance(rows,list) and rows:
    return [row for row in rows if isinstance(row,dict)]
  return [{'name':name,'authorOrder':index+1,'authorPosition':'first' if index==0 else 'last' if index==len(p.get('authors',[]))-1 else 'middle','affiliationIds':[],'isEqualContributor':None,'isCorresponding':None} for index,name in enumerate(p.get('authors',[]))]

def publication_affiliation_map(p):
  return {str(row.get('id') or ''):row for row in (p.get('affiliations') or []) if isinstance(row,dict)}

def publication_affiliation_text(row):
  address=row.get('address') or row.get('raw')
  values=[row.get('department'),row.get('institution'),address]
  if not address: values += [row.get('city'),row.get('countryCode')]
  output=[]; seen=set()
  for value in values:
    value=re.sub(r'\s+',' ',html.unescape(str(value or ''))).strip(' ,;')
    key=normalize_author_name(value)
    if value and key and key not in seen:
      seen.add(key); output.append(value)
  return ', '.join(output)

def authorship_marker_html(row,affiliations):
  symbols=[]; labels=[]
  if row.get('isEqualContributor') is True:
    symbols.append('†'); labels.append('Equal contribution')
  if row.get('isCorresponding') is True:
    symbols.append('*'); labels.append('Corresponding author')
  for aff_id in row.get('affiliationIds') or []:
    label=str((affiliations.get(str(aff_id)) or {}).get('label') or '').strip()
    if label:
      symbols.append(label); labels.append('Affiliation '+label)
  if not symbols: return ''
  return '<sup class="author-affiliation-ref" aria-label="'+esc('; '.join(labels))+'" title="'+esc('; '.join(labels))+'">'+esc(','.join(symbols))+'</sup>'

def publication_authors_html(p):
  affiliations=publication_affiliation_map(p)
  return ', '.join('<span class="publication-author">'+author_html(str(row.get('name') or ''))+authorship_marker_html(row,affiliations)+'</span>' for row in publication_authorships(p))

def publication_affiliations_html(p,details=False):
  affiliations=[row for row in (p.get('affiliations') or []) if isinstance(row,dict) and publication_affiliation_text(row)]
  rows=publication_authorships(p)
  equal=any(row.get('isEqualContributor') is True for row in rows)
  corresponding=[row for row in rows if row.get('isCorresponding') is True]
  if not affiliations and not equal and not corresponding: return ''
  aff_html=''.join('<li class="affiliation-entry"><span class="affiliation-label">'+esc(row.get('label'))+'</span><span>'+esc(publication_affiliation_text(row))+'</span></li>' for row in affiliations)
  legend=[]
  if equal: legend.append('<li><span class="author-role-marker">†</span><span>These authors contributed equally.</span></li>')
  if corresponding:
    names=', '.join(esc(row.get('name')) for row in corresponding)
    emails=[str(row.get('correspondingEmail') or '').strip() for row in corresponding if str(row.get('correspondingEmail') or '').strip()]
    email_html='' if not emails else ' '+' '.join('<a href="mailto:'+esc(email)+'">'+esc(email)+'</a>' for email in emails)
    legend.append('<li><span class="author-role-marker">*</span><span>Corresponding author'+('s' if len(corresponding)>1 else '')+': '+names+'.'+email_html+'</span></li>')
  body=(('<ol class="affiliation-list">'+aff_html+'</ol>') if aff_html else '')+(('<ul class="author-role-legend">'+''.join(legend)+'</ul>') if legend else '')
  return '<details class="publication-affiliations"'+(' open' if details else '')+'><summary>Author affiliations and roles</summary>'+body+'</details>'

def authorship_schema_person(row,p):
  affiliations=publication_affiliation_map(p); organizations=[]
  for aff_id in row.get('affiliationIds') or []:
    aff=affiliations.get(str(aff_id)); name=publication_affiliation_text(aff or {})
    if not name: continue
    org={'@type':'Organization','name':name}
    organizations.append(org)
  person={'@type':'Person','name':row.get('name','')}
  if organizations: person['affiliation']=organizations[0] if len(organizations)==1 else organizations
  same_as=[]
  if row.get('orcid'): same_as.append('https://orcid.org/'+str(row.get('orcid')).replace('https://orcid.org/',''))
  if row.get('openAlexId'): same_as.append('https://openalex.org/'+str(row.get('openAlexId')).rsplit('/',1)[-1])
  if same_as: person['sameAs']=same_as[0] if len(same_as)==1 else same_as
  if row.get('isCorresponding') is True and row.get('correspondingEmail'): person['email']='mailto:'+str(row.get('correspondingEmail'))
  return person
# PUBLICATION_AUTHORSHIP_BUILD_END

def graphical_abstract_path(p):
  """Return a site-relative GA path, preferring an explicit JSON value."""
  explicit = str(p.get('graphicalAbstract') or '').strip().replace('\\', '/')
  if explicit:
    return explicit.lstrip('/')
  stem = str(p.get('doi') or '').strip().replace('/', '_')
  if not stem:
    return ''
  ga_dir = ROOT / 'GA'
  for suffix in ('.JPG', '.PNG', '.jpg', '.png', '.JPEG', '.jpeg'):
    candidate = ga_dir / f'{stem}{suffix}'
    if candidate.is_file():
      return candidate.relative_to(ROOT).as_posix()
  return ''

def article_schema(p, url):
  identifiers=[]
  if p.get('doi'): identifiers.append({'@type':'PropertyValue','propertyID':'DOI','value':p.get('doi')})
  if p.get('id'): identifiers.append({'@type':'PropertyValue','propertyID':'Output ID','value':p.get('id')})
  if is_thesis(p):
    if p.get('repositoryUrl'):
      identifiers.append({'@type':'PropertyValue','propertyID':'Institutional repository','value':p.get('repositoryUrl')})
    obj = {'@type':'CreativeWork','@id':url+'#thesis','url':url,'mainEntityOfPage':url,'headline':p.get('title',''),'name':p.get('title',''),'alternateName':p.get('titleZh',''),'datePublished':str(p.get('year','')),'author':[authorship_schema_person(row,p) for row in publication_authorships(p)],'provider':{'@type':'CollegeOrUniversity','name':p.get('institution','')},'identifier':identifiers,'sameAs':p.get('repositoryUrl') or p.get('publicationUrl',''),'keywords':p.get('keywords',[]),'about':p.get('topic',''),'pagination':p.get('pages',''),'inLanguage':p.get('language') or 'en','genre':publication_type_label(p),'learningResourceType':'Thesis','educationalLevel':p.get('degree','')}
  else:
    obj = {'@type':'ScholarlyArticle','@id':url+'#article','url':url,'mainEntityOfPage':url,'headline':p.get('title',''),'name':p.get('title',''),'datePublished':p.get('date') or str(p.get('year','')),'author':[authorship_schema_person(row,p) for row in publication_authorships(p)],'isPartOf':{'@type':'Periodical','name':p.get('journal','')},'publisher':{'@type':'Organization','name':p.get('publisher','')},'identifier':identifiers,'sameAs':p.get('doiUrl') or p.get('publicationUrl',''),'citation':p.get('citation',''),'keywords':p.get('keywords',[]),'about':p.get('topic',''),'pagination':p.get('pages',''),'volumeNumber':p.get('volume',''),'issueNumber':p.get('issue',''),'inLanguage':p.get('language') or 'en','genre':publication_type_label(p)}
  if p.get('abstract'): obj['abstract'] = p.get('abstract')
  ga_path = graphical_abstract_path(p)
  if ga_path: obj['image'] = SITE_URL + '/' + ga_path
  return {k:v for k,v in obj.items() if v not in ('',[],None)}

def citation_meta(p):
  out=[]
  for a in p.get('authors',[]): out.append(f'<meta name="citation_author" content="{esc(a)}"/>')
  fields=[('citation_title',p.get('title')),('citation_publication_date',p.get('date') or p.get('year')),('citation_journal_title',p.get('journal')),('citation_volume',p.get('volume')),('citation_issue',p.get('issue')),('citation_firstpage',p.get('pages')),('citation_doi',p.get('doi')),('citation_abstract_html_url',p.get('doiUrl'))]
  if is_thesis(p):
    fields += [('citation_dissertation_institution',p.get('institution')),('citation_technical_report_institution',p.get('department'))]
  out += [f'<meta name="{n}" content="{esc(v)}"/>' for n,v in fields if v not in ('',None)]
  return '\n'.join(out)

def clean_publications_head(text):
  """Remove generated/legacy publication metadata before rebuilding it."""
  text = re.sub(
      re.escape(CITATION_META_START) + r'.*?' + re.escape(CITATION_META_END),
      '', text, flags=re.S)
  # Clean metadata produced by older builds before the marker block existed.
  text = re.sub(r'\s*<meta\s+name=["\']citation_[^"\']+["\'][^>]*?/?>', '', text, flags=re.I)
  # OpenAlex is rendered by app.js; loading this legacy enhancer duplicates it.
  text = re.sub(r'\s*<script\s+src=["\']assets/js/openalex-publications\.js["\']\s*></script>', '', text, flags=re.I)
  return text

def replace_person_schema(text):
  block='<script type="application/ld+json" id="person-schema">'+json.dumps(PERSON,ensure_ascii=False,separators=(',',':'))+'</script>'
  pat=re.compile(r'<script type="application/ld\+json"(?:\s+id="person-schema")?>.*?</script>',re.S)
  return pat.sub(block,text,count=1) if pat.search(text) else text.replace('</head>',block+'</head>',1)

def replace_emails(text):
  text=re.sub(r'<a href="mailto:[^"]+">Contact</a>', '<a class="button ghost" href="mailto:weihao.chiu@gmail.com">Contact</a>', text)
  text=re.sub(r'<div class="footer-links">.*?</div>', '<div class="footer-links">'+EMAIL_LINKS+'<a href="https://scholar.google.com.tw/citations?user=ZYbNQb8AAAAJ&amp;hl=zh-TW" rel="noopener" target="_blank">Google Scholar</a><a href="https://orcid.org/0000-0003-4484-3117" rel="noopener" target="_blank">ORCID</a></div>', text, flags=re.S)
  text=text.replace('weihchiu@mail.cgu.edu.tw','weihao.chiu@gmail.com')
  return text

def static_card(p, openalex_record=None):
  doi=p.get('doi',''); slug=publication_slug(p); local='publications/'+slug+'.html'
  authors=publication_authors_html(p)
  if is_thesis(p):
    labels_html='<span class="card-label publication-type-label">'+esc(publication_type_label(p))+'</span>'
    repository='<a class="action" href="'+esc(p.get('repositoryUrl'))+'" target="_blank" rel="noopener noreferrer">Institutional Repository ↗</a>' if p.get('repositoryUrl') else ''
    local_title='<p class="local-title thesis-title-zh" lang="zh-Hant">'+esc(p.get('titleZh'))+'</p>' if p.get('titleZh') else ''
    meta='<p class="thesis-meta">'+esc(p.get('institution'))+' · '+esc(p.get('department'))+'<br/>Advisor: '+esc(p.get('advisor'))+'</p>'
    return '<article class="collection-card publication-card thesis-publication-card seo-static-card" id="pub-'+slug+'" itemscope itemtype="https://schema.org/CreativeWork"><meta itemprop="identifier" content="'+esc(p.get('id'))+'"/><div class="card-heading"><h4 itemprop="headline"><a href="'+esc(local)+'">'+esc(p.get('title'))+'</a></h4><span class="date-badge" itemprop="datePublished">'+esc(p.get('year'))+'</span></div>'+local_title+'<p class="authors" itemprop="author">'+authors+'</p>'+meta+'<div class="card-labels">'+labels_html+'</div><div class="card-actions"><a class="action publication-detail-link" href="'+esc(local)+'">Details →</a>'+repository+'</div></article>'
  journal='<em>'+esc(p.get('journal'))+'</em>'
  if p.get('volume'): journal += ', '+esc(p.get('volume'))
  if p.get('pages'): journal += ', '+esc(p.get('pages'))
  journal += ' ('+esc(p.get('year'))+').'
  labels=[publication_type_label(p),p.get('topic')]+list(p.get('tags',[]))
  labels_html=''.join('<span class="card-label'+(' publication-type-label' if index==0 else '')+'">'+esc(x)+'</span>' for index,x in enumerate(labels) if x)
  n=int(p.get('citationCount') or 0)
  openalex_record = openalex_record or {}
  impact_html = ''.join(openalex_impact_actions(openalex_record)) if p.get('analytics',{}).get('fwci') is True and openalex_record.get('status') == 'verified' else ''
  doi_html='<a class="action" href="'+esc(p.get('doiUrl'))+'" target="_blank" rel="noopener">DOI ↗</a>' if p.get('doiUrl') else ''
  identifier=doi or p.get('id','')
  return '<article class="collection-card publication-card seo-static-card" id="pub-'+slug+'" itemscope itemtype="https://schema.org/ScholarlyArticle"><meta itemprop="identifier" content="'+esc(identifier)+'"/><div class="card-heading"><h4 itemprop="headline"><a href="'+esc(local)+'">'+esc(p.get('title'))+'</a></h4><span class="date-badge" itemprop="datePublished">'+esc(p.get('date'))+'</span></div><p class="authors publication-authors" itemprop="author">'+authors+'</p>'+publication_affiliations_html(p,details=False)+'<p class="journal" itemprop="isPartOf">'+journal+'</p><div class="card-labels">'+labels_html+'</div><div class="card-actions">'+doi_html+'<a class="action" href="'+esc(local)+'">Publication details →</a><span class="action">'+str(n)+' Google Scholar citation'+('s' if n!=1 else '')+'</span>'+impact_html+'</div></article>'

def static_publication_sections(pubs,openalex_records):
  types=[
    ('international-journal','International Journal Publications'),
    ('chinese-journal','Chinese Journal Publications'),
    ('conference','Conference Publications'),
    ('other','Other Scholarly Outputs'),
    ('unclassified','Unclassified Outputs'),
    ('thesis','Theses & Dissertations'),
  ]
  visible=[(key,label,[p for p in pubs if publication_type(p)==key]) for key,label in types]
  visible=[entry for entry in visible if entry[2]]
  nav=''
  if len(visible)>1:
    nav='<nav class="publication-section-nav" aria-label="Publication sections">'+''.join('<a href="#publication-section-'+esc(key)+'">'+esc(label)+' <span>'+str(len(rows))+'</span></a>' for key,label,rows in visible)+'</nav>'
  sections=[]
  for key,label,rows in visible:
    by_year={}
    for p in rows: by_year.setdefault(str(p.get('year') or 'Unknown'),[]).append(p)
    year_blocks=[]
    for year in sorted(by_year,key=lambda value:(value!='Unknown',int(value) if value.isdigit() else 0),reverse=True):
      year_rows=by_year[year]
      cards='\n'.join(static_card(p,openalex_records.get(normalize_doi(p.get('doi')),{})) for p in year_rows)
      year_blocks.append('<section class="year-group"><div class="year-heading"><h3>'+esc(year)+'</h3><span>'+str(len(year_rows))+' record'+('' if len(year_rows)==1 else 's')+'</span></div><div class="collection-list">'+cards+'</div></section>')
    sections.append('<section class="publication-type-section" id="publication-section-'+esc(key)+'"><div class="publication-section-heading"><div><span class="eyebrow">Publication type</span><h2>'+esc(label)+'</h2></div><strong>'+str(len(rows))+'</strong></div>'+''.join(year_blocks)+'</section>')
  return nav+''.join(sections)

def openalex_impact_actions(record):
  actions=[]
  fwci=record.get('fwci')
  if fwci is not None:
    actions.append('<span class="action openalex-impact" title="Field-Weighted Citation Impact; world average = 1.00">FWCI '+f'{float(fwci):.2f}'+'</span>')
  percentile=record.get('citationPercentile')
  if percentile is not None:
    top_share=max(0.0,100.0*(1.0-float(percentile)))
    digits=2 if top_share < 1 else 1
    actions.append('<span class="action openalex-impact" title="OpenAlex field-normalized citation percentile">Top '+f'{top_share:.{digits}f}'+'% normalized citations</span>')
  elif record.get('isTop1Percent') is True:
    actions.append('<span class="action openalex-impact openalex-impact-strong">Top 1% normalized citations</span>')
  elif record.get('isTop10Percent') is True:
    actions.append('<span class="action openalex-impact openalex-impact-strong">Top 10% normalized citations</span>')
  return actions

def normalize_doi(value):
  text=str(value or '').strip().lower()
  for prefix in ('https://doi.org/','http://doi.org/','https://dx.doi.org/','http://dx.doi.org/','doi:'):
    if text.startswith(prefix):
      text=text[len(prefix):]
      break
  return text.strip()

def openalex_history_by_doi(payload):
  records={}
  for work_id,record in (payload.get('works') or {}).items():
    if not isinstance(record,dict): continue
    doi=normalize_doi(record.get('doi'))
    if doi:
      records[doi]={**record,'openAlexId':record.get('openAlexId') or work_id}
  return records

def openalex_citation_count_is_zero(record):
  if record.get('status') != 'verified':
    return False
  try:
    return int(record.get('citationCount') or 0) == 0
  except (TypeError,ValueError):
    return False

def complete_citation_years(p,history_record):
  counts={}
  for row in history_record.get('citationsByYear') or []:
    if not isinstance(row,dict): continue
    try:
      year=int(row.get('year')); citations=max(0,int(row.get('citations') or 0))
    except (TypeError,ValueError):
      continue
    if year>=1900: counts[year]=citations
  try: publication_year=int(p.get('year'))
  except (TypeError,ValueError): publication_year=min(counts) if counts else date.today().year
  final_year=max([date.today().year,*counts.keys()])
  return [{'year':year,'citations':counts.get(year,0)} for year in range(publication_year,final_year+1)]

def citing_article_schema(record):
  obj={
    '@type':'ScholarlyArticle',
    '@id':record.get('doiUrl'),
    'url':record.get('doiUrl'),
    'name':record.get('title'),
    'headline':record.get('title'),
    'datePublished':record.get('publicationDate') or record.get('publicationYear'),
    'author':[{'@type':'Person','name':name} for name in (record.get('authors') or [])],
    'isPartOf':{'@type':'Periodical','name':record.get('journal')},
    'identifier':{'@type':'PropertyValue','propertyID':'DOI','value':record.get('doi')},
    'volumeNumber':record.get('volume'),
    'issueNumber':record.get('issue'),
    'pagination':record.get('pages'),
  }
  if not record.get('journal'): obj.pop('isPartOf',None)
  return {key:value for key,value in obj.items() if value not in ('',[],None)}

def citing_item_list_schema(p,url,history_record):
  articles=[row for row in (history_record.get('citingArticlesWithDoi') or []) if isinstance(row,dict) and row.get('doi')]
  if not articles: return None
  return {
    '@type':'ItemList',
    '@id':url+'#citing-articles',
    'name':'Articles citing '+str(p.get('title') or 'this work'),
    'url':url+'#citing-articles',
    'numberOfItems':len(articles),
    'about':{'@id':url+'#article'},
    'itemListOrder':'https://schema.org/ItemListOrderDescending',
    'itemListElement':[
      {'@type':'ListItem','position':index,'item':citing_article_schema(record)}
      for index,record in enumerate(articles,start=1)
    ],
  }

def citation_history_html(p,openalex_record,history_record):
  if not history_record or openalex_citation_count_is_zero(openalex_record): return ''
  rows=complete_citation_years(p,history_record)
  maximum=max([row['citations'] for row in rows],default=0)
  bars=[]
  table_rows=[]
  for row in rows:
    year=row['year']; citations=row['citations']
    height=(citations/maximum*100) if maximum else 0
    bars.append(
      '<li class="citation-year-item'+(' is-zero' if citations==0 else '')+'" '
      'aria-label="'+esc(year)+': '+esc(citations)+' citations">'
      '<span class="citation-year-count">'+esc(str(citations))+'</span>'
      '<span class="citation-year-track" aria-hidden="true"><span class="citation-year-bar" '
      'style="--citation-height:'+f'{height:.2f}'+'%"></span></span>'
      '<span class="citation-year-label">'+esc(year)+'</span></li>'
    )
    table_rows.append('<tr><th scope="row">'+esc(year)+'</th><td>'+esc(str(citations))+'</td></tr>')
  updated=str(history_record.get('lastSuccessfulUpdate') or '')[:10]
  source_note='Source: OpenAlex'
  if updated: source_note+=' · Last updated '+updated
  history_total=sum(row['citations'] for row in rows)
  return (
    '<section class="publication-detail-section citation-history-section" id="citations-by-year">'
    '<div class="citation-section-heading"><div><p class="kicker">OpenAlex citation history</p>'
    '<h2>Citations by year</h2></div><strong>'+f'{history_total:,}'+' assigned citations</strong></div>'
    '<figure class="citation-history-figure"><div class="citation-chart-scroll">'
    '<ol class="citation-year-chart" aria-label="OpenAlex citations by year">'+''.join(bars)+'</ol>'
    '</div><figcaption>'+esc(source_note)+'. Zero-citation years are included.</figcaption></figure>'
    '<details class="citation-year-data"><summary>View citation counts as a table</summary>'
    '<div class="table-wrap"><table><thead><tr><th scope="col">Year</th><th scope="col">Citations</th>'
    '</tr></thead><tbody>'+''.join(table_rows)+'</tbody></table></div></details></section>'
  )

def citing_articles_html(openalex_record,history_record):
  if not history_record or openalex_citation_count_is_zero(openalex_record): return ''
  articles=[row for row in (history_record.get('citingArticlesWithDoi') or []) if isinstance(row,dict) and row.get('doi')]
  indexed=int(history_record.get('citingWorkCount') or openalex_record.get('citationCount') or 0)
  listed=len(articles)
  summary=f'{listed:,} citing article'+('' if listed==1 else 's')+f' with DOI, from {indexed:,} records indexed by OpenAlex.'
  items=[]
  for record in articles:
    authors=', '.join(str(name) for name in (record.get('authors') or []) if str(name).strip())
    journal=esc(record.get('journal') or 'Source not supplied by OpenAlex')
    bits=[]
    if record.get('volume'): bits.append('vol. '+esc(record.get('volume')))
    if record.get('issue'): bits.append('no. '+esc(record.get('issue')))
    if record.get('pages'): bits.append('pp. '+esc(record.get('pages')))
    if record.get('publicationYear'): bits.append(esc(record.get('publicationYear')))
    bibliographic=', '.join(bits)
    items.append(
      '<li class="citing-article" itemscope itemtype="https://schema.org/ScholarlyArticle">'
      '<h3 itemprop="headline"><a href="'+esc(record.get('doiUrl'))+'" target="_blank" '
      'rel="noopener noreferrer">'+esc(record.get('title') or record.get('doi'))+' ↗</a></h3>'
      +('<p class="citing-article-authors" itemprop="author">'+esc(authors)+'</p>' if authors else '')+
      '<p class="citing-article-source"><em itemprop="isPartOf">'+journal+'</em>'
      +((' · '+bibliographic) if bibliographic else '')+'</p>'
      '<p class="citing-article-doi">DOI: <a itemprop="sameAs" href="'+esc(record.get('doiUrl'))+
      '" target="_blank" rel="noopener noreferrer">'+esc(record.get('doi'))+'</a></p></li>'
    )
  empty='<p class="citation-empty">No citing articles with a DOI are currently indexed by OpenAlex.</p>'
  return (
    '<section class="publication-detail-section citing-articles-section" id="citing-articles">'
    '<p class="kicker">OpenAlex citing works</p><h2>Articles citing this work</h2>'
    '<p class="citation-list-summary">'+esc(summary)+'</p>'
    +('<ol class="citing-article-list">'+''.join(items)+'</ol>' if items else empty)+'</section>'
  )

def thesis_page(p):
  slug=publication_slug(p); url=SITE_URL+'/publications/'+slug+'.html'
  raw_title=str(p.get('title') or '')
  title=esc(raw_title)
  title_zh=esc(p.get('titleZh'))
  degree_label=publication_type_label(p)
  desc=esc(f"{degree_label} by Wei-Hao Chiu, {p.get('institution')}, {p.get('year')}: {raw_title}")
  graph={'@context':'https://schema.org','@graph':[PERSON,article_schema(p,url)]}
  rows=[
    ('Author',str(p.get('authors',["Wei-Hao Chiu"])[0]),p.get('authorZh')),
    ('Degree',degree_label,''),
    ('Year',p.get('year'),''),
    ('Institution',p.get('institution'),p.get('institutionZh')),
    ('Department',p.get('department'),p.get('departmentZh')),
    ('Advisor',p.get('advisor'),p.get('advisorZh')),
    ('Pages',p.get('pages'),''),
    ('Language',p.get('languageLabel') or p.get('language'),''),
  ]
  facts=''.join('<div class="thesis-fact"><dt>'+esc(label)+'</dt><dd>'+esc(value)+(('<span lang="zh-Hant">'+esc(zh)+'</span>') if zh else '')+'</dd></div>' for label,value,zh in rows if value not in ('',None))
  abstract=str(p.get('abstract') or '').strip()
  abstract_zh=str(p.get('abstractZh') or '').strip()
  keywords=p.get('keywords') or []
  keywords_zh=p.get('keywordsZh') or []
  sections='<section class="publication-detail-section"><h2>Basic Information</h2><dl class="thesis-facts">'+facts+'</dl></section>'
  if abstract:
    sections+='<section class="publication-detail-section"><h2>Abstract</h2><p itemprop="abstract">'+esc(abstract)+'</p></section>'
  if abstract_zh:
    sections+='<section class="publication-detail-section" lang="zh-Hant"><h2>中文摘要</h2><p>'+esc(abstract_zh)+'</p></section>'
  if keywords:
    sections+='<section class="publication-detail-section"><h2>Keywords</h2><div class="publication-keywords">'+''.join('<span itemprop="keywords">'+esc(item)+'</span>' for item in keywords)+'</div></section>'
  if keywords_zh:
    sections+='<section class="publication-detail-section" lang="zh-Hant"><h2>中文關鍵詞</h2><div class="publication-keywords">'+''.join('<span>'+esc(item)+'</span>' for item in keywords_zh)+'</div></section>'
  repository=''
  if p.get('repositoryUrl'):
    repository='<section class="publication-detail-section"><h2>Links</h2><div class="card-actions publication-detail-actions"><a class="action" href="'+esc(p.get('repositoryUrl'))+'" target="_blank" rel="noopener noreferrer">Institutional Repository ↗</a></div></section>'
  email_url='mailto:?subject='+quote(raw_title)+'&body='+quote(url)
  share='<span class="share-wrap"><button class="action action-button share-trigger" type="button" aria-haspopup="menu" aria-expanded="false" data-share-title="'+title+'" data-share-text="'+title+'" data-share-url="'+esc(url)+'">Share</button><span class="share-menu" role="menu" hidden><button type="button" role="menuitem" data-copy-share-url="'+esc(url)+'">Copy link</button><a role="menuitem" href="'+esc(email_url)+'">Email</a><a role="menuitem" href="https://www.linkedin.com/sharing/share-offsite/?url='+quote(url,safe='')+'" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a></span></span>'
  return '''<!DOCTYPE html><html lang="{language}"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>{title} | Wei-Hao Chiu</title><meta name="description" content="{desc}"/><link rel="canonical" href="{url}"/><meta property="og:type" content="article"/><meta property="og:title" content="{title}"/><meta property="og:description" content="{desc}"/><meta property="og:url" content="{url}"/><meta property="og:image" content="{site}/assets/images/og-profile.jpg"/><meta property="article:published_time" content="{year}"/><meta property="article:author" content="{site}/"/><meta name="twitter:card" content="summary_large_image"/><meta name="twitter:title" content="{title}"/><meta name="twitter:description" content="{desc}"/><meta name="twitter:image" content="{site}/assets/images/og-profile.jpg"/>{ga}{citation}<script type="application/ld+json">{schema}</script><link href="../assets/css/styles.css" rel="stylesheet"/></head><body><header class="site-header"><div class="shell nav-shell"><a class="brand" href="../index.html"><span>Wei-Hao Chiu</span><small>Academic Profile</small></a><nav aria-label="Main navigation" class="site-nav"><a href="../about.html">About</a><a href="../research.html">Research</a><a href="../publications.html">Publications</a><a href="../patents.html">Patents</a><a href="../projects.html">Projects</a></nav></div></header><main class="content shell"><article class="collection-card publication-card publication-detail thesis-detail" itemscope itemtype="https://schema.org/CreativeWork"><p class="kicker">{degree}</p><h1 itemprop="headline">{title}</h1><p class="thesis-detail-title-zh" lang="zh-Hant">{title_zh}</p>{sections}{repository}<div class="card-actions publication-detail-actions">{share}</div><a class="action publication-return" href="../publications.html#pub-{slug}">← Return to publications</a></article></main><footer class="site-footer"><div class="shell footer-grid"><div><strong>Wei-Hao Chiu, Ph.D.</strong><p>Associate Researcher<br/>Center for Sustainability and Energy Technologies<br/>Chang Gung University</p></div><div class="footer-links">{emails}</div></div></footer><script src="../assets/js/app.js"></script></body></html>'''.format(language=esc(p.get('language') or 'en'),title=title,title_zh=title_zh,desc=desc,url=url,site=SITE_URL,year=esc(p.get('year')),degree=esc(degree_label),ga=GA_TAG,citation=citation_meta(p),schema=json.dumps(graph,ensure_ascii=False,separators=(',',':')),sections=sections,repository=repository,share=share,slug=slug,emails=EMAIL_LINKS)

def publication_page(p, openalex_record=None, unpaywall_record=None, crossref_record=None, mendeley_record=None, history_record=None):
  if is_thesis(p):
    return thesis_page(p)
  doi=p.get('doi',''); slug=publication_slug(p); url=SITE_URL+'/publications/'+slug+'.html'
  title=esc(p.get('title')); desc=esc(p.get('citation')); authors=publication_authors_html(p)
  history_record=history_record or {}
  graph_items=[PERSON,article_schema(p,url)]
  citing_schema=None if openalex_citation_count_is_zero(openalex_record) else citing_item_list_schema(p,url,history_record)
  if citing_schema: graph_items.append(citing_schema)
  graph={'@context':'https://schema.org','@graph':graph_items}
  vol=', '+esc(p.get('volume')) if p.get('volume') else ''
  pages=', '+esc(p.get('pages')) if p.get('pages') else ''
  abstract = str(p.get('abstract') or '').strip()
  highlights = p.get('highlights') or []
  if isinstance(highlights, str): highlights = [highlights]
  highlights = [str(item).strip() for item in highlights if str(item).strip()]
  keywords = p.get('keywords',[])
  if isinstance(keywords, str): keywords = [keywords]
  keywords = [str(item).strip() for item in (keywords or []) if str(item).strip()]
  ga_path = graphical_abstract_path(p)
  openalex_record = openalex_record or {}
  unpaywall_record = unpaywall_record or {}
  crossref_record = crossref_record or {}
  mendeley_record = mendeley_record or {}
  detail_sections = []
  if abstract:
    detail_sections.append('<section class="publication-detail-section"><h2>Abstract</h2><p itemprop="abstract">'+esc(abstract)+'</p></section>')
  if highlights:
    detail_sections.append('<section class="publication-detail-section"><h2>Highlights</h2><ul class="publication-highlights">'+''.join('<li>'+esc(item)+'</li>' for item in highlights)+'</ul></section>')
  if ga_path:
    ga_alt = p.get('graphicalAbstractAlt') or ('Graphical abstract for '+str(p.get('title') or 'this publication'))
    detail_sections.append('<section class="publication-detail-section graphical-abstract"><h2>Graphical Abstract</h2><figure><img src="../'+esc(ga_path)+'" alt="'+esc(ga_alt)+'" loading="lazy"/><figcaption>Graphical abstract</figcaption></figure></section>')
  if keywords:
    detail_sections.append('<section class="publication-detail-section"><h2>Keywords</h2><div class="publication-keywords">'+''.join('<span itemprop="keywords">'+esc(item)+'</span>' for item in keywords)+'</div></section>')
  details = ''.join(detail_sections)
  author_info=publication_affiliations_html(p,details=True)
  actions = []
  if p.get('doiUrl'):
    actions.append('<a class="action" href="'+esc(p.get('doiUrl'))+'" target="_blank" rel="noopener">DOI ↗</a>')
  if p.get('publicationUrl'):
    actions.append('<a class="action" href="'+esc(p.get('publicationUrl'))+'" target="_blank" rel="noopener noreferrer">Publication record ↗</a>')
  if unpaywall_record.get('isOa') and unpaywall_record.get('urlForPdf'):
    actions.append('<a class="action oa-action" href="'+esc(unpaywall_record.get('urlForPdf'))+'" target="_blank" rel="noopener noreferrer">Open Access PDF ↗</a>')
  scholar_url = p.get('citedByUrl') or p.get('scholarProfileUrl')
  if scholar_url:
    scholar_count = int(p.get('citationCount') or 0)
    actions.append('<a class="action" href="'+esc(scholar_url)+'" target="_blank" rel="noopener noreferrer">'+f'{scholar_count:,}'+' Google Scholar citation'+('' if scholar_count == 1 else 's')+' ↗</a>')
  if openalex_record.get('status') == 'verified' and openalex_record.get('url'):
    oa_count = int(openalex_record.get('citationCount') or 0)
    actions.append('<a class="action" href="'+esc(openalex_record.get('url'))+'" target="_blank" rel="noopener noreferrer">'+f'{oa_count:,}'+' OpenAlex citation'+('' if oa_count == 1 else 's')+' ↗</a>')
    if p.get('analytics',{}).get('fwci') is True:
      actions.extend(openalex_impact_actions(openalex_record))
  if crossref_record.get('status') == 'verified' and doi:
    cr_count = int(crossref_record.get('citationCount') or 0)
    crossref_url = 'https://search.crossref.org/search/works?q=' + quote(str(doi), safe='') + '&from_ui=yes'
    actions.append('<a class="action" href="'+esc(crossref_url)+'" target="_blank" rel="noopener noreferrer">'+f'{cr_count:,}'+' Crossref citation'+('' if cr_count == 1 else 's')+' ↗</a>')
  if mendeley_record.get('status') == 'verified' and mendeley_record.get('url'):
    reader_count = int(mendeley_record.get('readerCount') or 0)
    actions.append('<a class="action" href="'+esc(mendeley_record.get('url'))+'" target="_blank" rel="noopener noreferrer">'+f'{reader_count:,}'+' Mendeley reader'+('' if reader_count == 1 else 's')+' ↗</a>')
  share_text = str(p.get('title') or '')
  email_url = 'mailto:?subject='+quote(share_text)+'&body='+quote(url)
  actions.append('<span class="share-wrap"><button class="action action-button share-trigger" type="button" aria-haspopup="menu" aria-expanded="false" data-share-title="'+title+'" data-share-text="'+title+'" data-share-url="'+esc(url)+'">Share</button><span class="share-menu" role="menu" hidden><button type="button" role="menuitem" data-copy-share-url="'+esc(url)+'">Copy link</button><a role="menuitem" href="'+esc(email_url)+'">Email</a><a role="menuitem" href="https://www.linkedin.com/sharing/share-offsite/?url='+quote(url, safe='')+'" target="_blank" rel="noopener noreferrer">LinkedIn ↗</a></span></span>')
  actions_html = '<div class="card-actions publication-detail-actions">'+''.join(actions)+'</div>'
  citation_sections=citation_history_html(p,openalex_record,history_record)+citing_articles_html(openalex_record,history_record)
  return '''<!DOCTYPE html><html lang="{language}"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>{title} | Wei-Hao Chiu</title><meta name="description" content="{desc}"/><link rel="canonical" href="{url}"/><meta property="og:type" content="article"/><meta property="og:title" content="{title}"/><meta property="og:description" content="{desc}"/><meta property="og:url" content="{url}"/><meta property="og:image" content="{site}/assets/images/og-profile.jpg"/><meta property="article:published_time" content="{date}"/><meta property="article:author" content="{site}/"/><meta name="twitter:card" content="summary_large_image"/><meta name="twitter:title" content="{title}"/><meta name="twitter:description" content="{desc}"/><meta name="twitter:image" content="{site}/assets/images/og-profile.jpg"/>{ga}{citation}<script type="application/ld+json">{schema}</script><link href="../assets/css/styles.css" rel="stylesheet"/></head><body><header class="site-header"><div class="shell nav-shell"><a class="brand" href="../index.html"><span>Wei-Hao Chiu</span><small>Academic Profile</small></a><nav aria-label="Main navigation" class="site-nav"><a href="../about.html">About</a><a href="../research.html">Research</a><a href="../publications.html">Publications</a><a href="../patents.html">Patents</a><a href="../projects.html">Projects</a></nav></div></header><main class="content shell"><article class="collection-card publication-card publication-detail" itemscope itemtype="https://schema.org/ScholarlyArticle"><p class="kicker">{publication_type}</p><h1 itemprop="headline">{title}</h1><p class="authors publication-authors" itemprop="author">{authors}</p>{author_info}<p class="journal"><em>{journal}</em>{vol}{pages} ({year}).</p><p><strong>Research topic:</strong> {topic}</p>{details}{actions}{citation_sections}<a class="action publication-return" href="../publications.html#pub-{slug}">← Return to publications</a></article></main><footer class="site-footer"><div class="shell footer-grid"><div><strong>Wei-Hao Chiu, Ph.D.</strong><p>Associate Researcher<br/>Center for Sustainability and Energy Technologies<br/>Chang Gung University</p></div><div class="footer-links">{emails}</div></div></footer><script src="../assets/js/app.js"></script></body></html>'''.format(language=esc(p.get('language') or 'en'),publication_type=esc(publication_type_label(p)),title=title,desc=desc,url=url,site=SITE_URL,date=esc(p.get('date')),ga=GA_TAG,citation=citation_meta(p),schema=json.dumps(graph,ensure_ascii=False,separators=(',',':')),authors=authors,author_info=author_info,journal=esc(p.get('journal')),vol=vol,pages=pages,year=esc(p.get('year')),topic=esc(p.get('topic')),details=details,actions=actions_html,citation_sections=citation_sections,slug=slug,emails=EMAIL_LINKS)

def main():
  global AUTHOR_MAP
  sitemap_path=ROOT/'sitemap.xml'
  existing_sitemap=sitemap_path.read_text(encoding='utf-8') if sitemap_path.exists() else ''
  patent_urls=[url.removeprefix(SITE_URL+'/') for url in re.findall(r'<loc>(https://weihaochiu\.github\.io/patents/[^<]+)</loc>',existing_sitemap)]
  llms_path=ROOT/'llms.txt'
  existing_llms=llms_path.read_text(encoding='utf-8') if llms_path.exists() else ''
  patent_match=re.search(re.escape(PATENT_LLMS_START)+r'.*?'+re.escape(PATENT_LLMS_END),existing_llms,flags=re.S)
  patent_llms_block=patent_match.group(0) if patent_match else ''
  pubs=json.loads((ROOT/'data/publications.json').read_text(encoding='utf-8'))
  before_files={path.name:path.read_text(encoding='utf-8') for path in (ROOT/'publications').glob('*.html')}
  expected_files={publication_slug(p)+'.html' for p in pubs}
  authors_path=ROOT/'data/authors.json'
  author_rows=json.loads(authors_path.read_text(encoding='utf-8')) if authors_path.exists() else []
  AUTHOR_MAP={normalize_author_name(name):author for author in author_rows if author_has_information(author) for name in [author.get('name'),author.get('displayName'),author.get('nameZh'),*(author.get('aliases') or [])] if name}
  openalex_path=ROOT/'data/openalex_publication_metrics.json'
  openalex_records=json.loads(openalex_path.read_text(encoding='utf-8')).get('records',{}) if openalex_path.exists() else {}
  openalex_history_path=ROOT/'data/openalex_citation_history.json'
  openalex_history_payload=json.loads(openalex_history_path.read_text(encoding='utf-8')) if openalex_history_path.exists() else {}
  openalex_history_records=openalex_history_by_doi(openalex_history_payload)
  crossref_path=ROOT/'data/crossref_publication_metrics.json'
  crossref_records=json.loads(crossref_path.read_text(encoding='utf-8')).get('records',{}) if crossref_path.exists() else {}
  unpaywall_path=ROOT/'data/unpaywall.json'
  unpaywall_records=json.loads(unpaywall_path.read_text(encoding='utf-8')).get('records',{}) if unpaywall_path.exists() else {}
  mendeley_path=ROOT/'data/mendeley_metrics.json'
  mendeley_records=json.loads(mendeley_path.read_text(encoding='utf-8')).get('records',{}) if mendeley_path.exists() else {}
  for path in ROOT.glob('*.html'):
    text=path.read_text(encoding='utf-8'); text=replace_person_schema(text); text=replace_emails(text); path.write_text(text,encoding='utf-8')
  pubpath=ROOT/'publications.html'; text=clean_publications_head(pubpath.read_text(encoding='utf-8'))
  text=text.replace('Peer-reviewed journal publications of Wei-Hao Chiu with research-theme filtering, legal open-access links and per-publication sharing.','International and Chinese journal publications, conference publications and other scholarly outputs of Wei-Hao Chiu, with clearly separated core bibliometric scope.')
  text=text.replace('International and Chinese journal publications, conference publications and other scholarly outputs of Wei-Hao Chiu, with clearly separated core bibliometric scope.','Research publications plus separately presented theses and dissertations of Wei-Hao Chiu, with thesis records excluded from all publication research analytics.')
  if 'id="publicationTypeFilter"' not in text:
    text=text.replace('<div class="select-field"><span>Sort</span><select id="sortFilter">','<div class="select-field"><span>Type</span><select aria-label="Filter by publication type" id="publicationTypeFilter"></select></div><div class="select-field"><span>Sort</span><select id="sortFilter">',1)
  static_content='<!-- SEO_STATIC_PUBLICATIONS_START -->\n'+static_publication_sections(pubs,openalex_records)+'\n<!-- SEO_STATIC_PUBLICATIONS_END -->'
  marker_pattern=r'<!-- SEO_STATIC_PUBLICATIONS_START -->.*?<!-- SEO_STATIC_PUBLICATIONS_END -->'
  if re.search(marker_pattern,text,flags=re.S):
    text=re.sub(marker_pattern,static_content,text,count=1,flags=re.S)
  else:
    text=re.sub(r'(<div id="collectionContainer"[^>]*>).*?(</div>)',r'\1\n'+static_content+r'\n\2',text,count=1,flags=re.S)
  text=re.sub(r'(<div id="collectionContainer")[^>]*>',r'\1 data-static-publications="'+str(len(pubs))+'">',text,count=1)
  graph={'@context':'https://schema.org','@graph':[PERSON]+[article_schema(p,SITE_URL+'/publications/'+publication_slug(p)+'.html') for p in pubs]}
  schema='<script type="application/ld+json" id="publications-schema">'+json.dumps(graph,ensure_ascii=False,separators=(',',':'))+'</script>'
  text=re.sub(r'<script type="application/ld\+json" id="publications-schema">.*?</script>','',text,flags=re.S)
  text=re.sub(r'\s*</head>', '\n</head>', text, count=1)
  citation_block = CITATION_META_START+'\n'+'\n'.join(citation_meta(p) for p in pubs)+'\n'+CITATION_META_END
  text=text.replace('</head>',citation_block+'\n'+schema+'\n</head>',1)
  pubpath.write_text(text,encoding='utf-8')
  pdir=ROOT/'publications'; pdir.mkdir(exist_ok=True)
  for name in before_files:
    if name not in expected_files:
      (pdir/name).unlink()
  for p in pubs:
    key=normalize_doi(p.get('doi'))
    record=openalex_records.get(key,{})
    oa_record=unpaywall_records.get(key,{})
    cr_record=crossref_records.get(key,{})
    md_record=mendeley_records.get(key,{})
    history_record=openalex_history_records.get(normalize_doi(p.get('doi')),{})
    if history_record and not history_record.get('lastSuccessfulUpdate'):
      history_record={**history_record,'lastSuccessfulUpdate':openalex_history_payload.get('lastSuccessfulUpdate')}
    (pdir/(publication_slug(p)+'.html')).write_text(publication_page(p,record,oa_record,cr_record,md_record,history_record),encoding='utf-8')
  app=ROOT/'assets/js/app.js'; js=app.read_text(encoding='utf-8')
  js=re.sub(r'function publicationShareUrl\(anchor\)\{.*?\n\}', "function publicationShareUrl(anchor){\n  const slug=String(anchor||'').replace(/^pub-/,'');\n  return new URL(`publications/${slug}.html`,window.location.href).toString();\n}", js, count=1, flags=re.S)
  app.write_text(js,encoding='utf-8')
  (ROOT/'robots.txt').write_text(robots_text(),encoding='utf-8')
  urls=['','about.html','research.html','publications.html','patents.html','projects.html','llms.txt']+['publications/'+publication_slug(p)+'.html' for p in pubs]+patent_urls
  urls=list(dict.fromkeys(urls))
  rows='\n'.join('  <url><loc>'+SITE_URL+'/'+esc(u)+'</loc><lastmod>'+TODAY+'</lastmod></url>' for u in urls)
  sitemap_path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+rows+'\n</urlset>\n',encoding='utf-8')
  lines=['# Wei-Hao Chiu Academic Website','', '> Official academic website of Wei-Hao Chiu, Ph.D., Associate Researcher at Chang Gung University.','','## Main Pages','',f'- [Home]({SITE_URL}/)',f'- [About]({SITE_URL}/about.html)',f'- [Research]({SITE_URL}/research.html)',f'- [Publications]({SITE_URL}/publications.html)',f'- [Patents]({SITE_URL}/patents.html)',f'- [Projects]({SITE_URL}/projects.html)','','## Contact','','- Personal email: weihao.chiu@gmail.com','- Chang Gung University email: d000019005@cgu.edu.tw','','## Research Expertise','']
  lines += ['- '+x for x in PERSON['knowsAbout']]; lines += ['','## Scholarly Outputs','']
  for key,label in [('international-journal','International Journal Publications'),('chinese-journal','Chinese Journal Publications'),('conference','Conference Publications'),('other','Other Scholarly Outputs'),('unclassified','Unclassified Outputs'),('thesis','Theses & Dissertations')]:
    rows=[p for p in pubs if publication_type(p)==key]
    if not rows: continue
    lines += ['',f'### {label}','']
    for p in rows:
      doi_note=f"; DOI: {p.get('doi')}" if p.get('doi') else ''
      source=p.get('institution') if is_thesis(p) else p.get('journal')
      lines.append(f"- [{p.get('title')}]({SITE_URL}/publications/{publication_slug(p)}.html) — {source}, {p.get('year')}{doi_note}")
  llms_text='\n'.join(lines)+'\n'
  if patent_llms_block:
    llms_text=llms_text.rstrip()+'\n\n'+patent_llms_block+'\n'
  llms_path.write_text(llms_text,encoding='utf-8')
  core_count=sum(p.get('analytics',{}).get('coreJournalCount') is True for p in pubs)
  research_count=sum(is_research_publication(p) for p in pubs)
  thesis_count=sum(is_thesis(p) for p in pubs)
  mp=ROOT/'data/site_meta.json'; meta=json.loads(mp.read_text(encoding='utf-8')); meta.update({'version':'v26','lastUpdated':TODAY,'coreJournalPublications':core_count,'scholarlyOutputs':research_count,'thesesAndDissertations':thesis_count,'notes':f'V26 displays {thesis_count} theses and dissertations separately while retaining {research_count} research publications and {core_count} core international journal publications for publication analytics.'}); mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()

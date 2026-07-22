#!/usr/bin/env python3
from __future__ import annotations
import html, json, re
from datetime import date
from pathlib import Path
from urllib.parse import quote

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
def slugify(doi): return re.sub(r'[^a-z0-9]+','-',str(doi).lower()).strip('-') or 'publication'
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
  obj = {'@type':'ScholarlyArticle','@id':url+'#article','url':url,'mainEntityOfPage':url,'headline':p.get('title',''),'name':p.get('title',''),'datePublished':p.get('date') or str(p.get('year','')),'author':[{'@type':'Person','name':a} for a in p.get('authors',[])],'isPartOf':{'@type':'Periodical','name':p.get('journal','')},'publisher':{'@type':'Organization','name':p.get('publisher','')},'identifier':[{'@type':'PropertyValue','propertyID':'DOI','value':p.get('doi','')},p.get('doiUrl','')],'sameAs':p.get('doiUrl',''),'citation':p.get('citation',''),'keywords':p.get('keywords',[]),'about':p.get('topic',''),'pagination':p.get('pages',''),'volumeNumber':p.get('volume',''),'issueNumber':p.get('issue',''),'inLanguage':'en'}
  if p.get('abstract'): obj['abstract'] = p.get('abstract')
  ga_path = graphical_abstract_path(p)
  if ga_path: obj['image'] = SITE_URL + '/' + ga_path
  return {k:v for k,v in obj.items() if v not in ('',[],None)}

def citation_meta(p):
  out=[]
  for a in p.get('authors',[]): out.append(f'<meta name="citation_author" content="{esc(a)}"/>')
  fields=[('citation_title',p.get('title')),('citation_publication_date',p.get('date') or p.get('year')),('citation_journal_title',p.get('journal')),('citation_volume',p.get('volume')),('citation_issue',p.get('issue')),('citation_firstpage',p.get('pages')),('citation_doi',p.get('doi')),('citation_abstract_html_url',p.get('doiUrl'))]
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

def static_card(p):
  doi=p.get('doi',''); slug=slugify(doi); local='publications/'+slug+'.html'
  authors=', '.join(author_html(a) for a in p.get('authors',[]))
  journal='<em>'+esc(p.get('journal'))+'</em>'
  if p.get('volume'): journal += ', '+esc(p.get('volume'))
  if p.get('pages'): journal += ', '+esc(p.get('pages'))
  journal += ' ('+esc(p.get('year'))+').'
  labels=[p.get('topic')]+list(p.get('tags',[]))
  labels_html=''.join('<span class="card-label">'+esc(x)+'</span>' for x in labels if x)
  n=int(p.get('citationCount') or 0)
  return '<article class="collection-card publication-card seo-static-card" id="pub-'+slug+'" itemscope itemtype="https://schema.org/ScholarlyArticle"><meta itemprop="identifier" content="'+esc(doi)+'"/><div class="card-heading"><h4 itemprop="headline"><a href="'+esc(local)+'">'+esc(p.get('title'))+'</a></h4><span class="date-badge" itemprop="datePublished">'+esc(p.get('date'))+'</span></div><p class="authors" itemprop="author">'+authors+'</p><p class="journal" itemprop="isPartOf">'+journal+'</p><div class="card-labels">'+labels_html+'</div><div class="card-actions"><a class="action" href="'+esc(p.get('doiUrl'))+'" target="_blank" rel="noopener">DOI ↗</a><a class="action" href="'+esc(local)+'">Abstract, Highlights &amp; GA →</a><span class="action">'+str(n)+' Google Scholar citation'+('s' if n!=1 else '')+'</span></div></article>'

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

def publication_page(p, openalex_record=None, unpaywall_record=None, crossref_record=None, mendeley_record=None):
  doi=p.get('doi',''); slug=slugify(doi); url=SITE_URL+'/publications/'+slug+'.html'
  title=esc(p.get('title')); desc=esc(p.get('citation')); authors=', '.join(author_html(a) for a in p.get('authors',[]))
  graph={'@context':'https://schema.org','@graph':[PERSON,article_schema(p,url)]}
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
  actions = ['<a class="action" href="'+esc(p.get('doiUrl'))+'" target="_blank" rel="noopener">DOI ↗</a>']
  if unpaywall_record.get('isOa') and unpaywall_record.get('urlForPdf'):
    actions.append('<a class="action oa-action" href="'+esc(unpaywall_record.get('urlForPdf'))+'" target="_blank" rel="noopener noreferrer">Open Access PDF ↗</a>')
  scholar_url = p.get('citedByUrl') or p.get('scholarProfileUrl')
  if scholar_url:
    scholar_count = int(p.get('citationCount') or 0)
    actions.append('<a class="action" href="'+esc(scholar_url)+'" target="_blank" rel="noopener noreferrer">'+f'{scholar_count:,}'+' Google Scholar citation'+('' if scholar_count == 1 else 's')+' ↗</a>')
  if openalex_record.get('status') == 'verified' and openalex_record.get('url'):
    oa_count = int(openalex_record.get('citationCount') or 0)
    actions.append('<a class="action" href="'+esc(openalex_record.get('url'))+'" target="_blank" rel="noopener noreferrer">'+f'{oa_count:,}'+' OpenAlex citation'+('' if oa_count == 1 else 's')+' ↗</a>')
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
  return '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>{title} | Wei-Hao Chiu</title><meta name="description" content="{desc}"/><link rel="canonical" href="{url}"/><meta property="og:type" content="article"/><meta property="og:title" content="{title}"/><meta property="og:description" content="{desc}"/><meta property="og:url" content="{url}"/><meta property="og:image" content="{site}/assets/images/og-profile.jpg"/><meta property="article:published_time" content="{date}"/><meta property="article:author" content="{site}/"/><meta name="twitter:card" content="summary_large_image"/><meta name="twitter:title" content="{title}"/><meta name="twitter:description" content="{desc}"/><meta name="twitter:image" content="{site}/assets/images/og-profile.jpg"/>{ga}{citation}<script type="application/ld+json">{schema}</script><link href="../assets/css/styles.css" rel="stylesheet"/></head><body><header class="site-header"><div class="shell nav-shell"><a class="brand" href="../index.html"><span>Wei-Hao Chiu</span><small>Academic Profile</small></a><nav aria-label="Main navigation" class="site-nav"><a href="../about.html">About</a><a href="../research.html">Research</a><a href="../publications.html">Publications</a><a href="../patents.html">Patents</a><a href="../projects.html">Projects</a></nav></div></header><main class="content shell"><article class="collection-card publication-card publication-detail" itemscope itemtype="https://schema.org/ScholarlyArticle"><p class="kicker">Scholarly article</p><h1 itemprop="headline">{title}</h1><p class="authors" itemprop="author">{authors}</p><p class="journal"><em>{journal}</em>{vol}{pages} ({year}).</p><p><strong>Research topic:</strong> {topic}</p>{details}{actions}<a class="action publication-return" href="../publications.html#pub-{slug}">← Return to publications</a></article></main><footer class="site-footer"><div class="shell footer-grid"><div><strong>Wei-Hao Chiu, Ph.D.</strong><p>Associate Researcher<br/>Center for Sustainability and Energy Technologies<br/>Chang Gung University</p></div><div class="footer-links">{emails}</div></div></footer><script src="../assets/js/app.js"></script></body></html>'''.format(title=title,desc=desc,url=url,site=SITE_URL,date=esc(p.get('date')),ga=GA_TAG,citation=citation_meta(p),schema=json.dumps(graph,ensure_ascii=False,separators=(',',':')),authors=authors,journal=esc(p.get('journal')),vol=vol,pages=pages,year=esc(p.get('year')),topic=esc(p.get('topic')),details=details,actions=actions_html,slug=slug,emails=EMAIL_LINKS)

def main():
  global AUTHOR_MAP
  pubs=json.loads((ROOT/'data/publications.json').read_text(encoding='utf-8'))
  authors_path=ROOT/'data/authors.json'
  author_rows=json.loads(authors_path.read_text(encoding='utf-8')) if authors_path.exists() else []
  AUTHOR_MAP={normalize_author_name(name):author for author in author_rows if author_has_information(author) for name in [author.get('name'),author.get('displayName'),author.get('nameZh'),*(author.get('aliases') or [])] if name}
  openalex_path=ROOT/'data/openalex_publication_metrics.json'
  openalex_records=json.loads(openalex_path.read_text(encoding='utf-8')).get('records',{}) if openalex_path.exists() else {}
  crossref_path=ROOT/'data/crossref_publication_metrics.json'
  crossref_records=json.loads(crossref_path.read_text(encoding='utf-8')).get('records',{}) if crossref_path.exists() else {}
  unpaywall_path=ROOT/'data/unpaywall.json'
  unpaywall_records=json.loads(unpaywall_path.read_text(encoding='utf-8')).get('records',{}) if unpaywall_path.exists() else {}
  mendeley_path=ROOT/'data/mendeley_metrics.json'
  mendeley_records=json.loads(mendeley_path.read_text(encoding='utf-8')).get('records',{}) if mendeley_path.exists() else {}
  if len(pubs)!=37: raise SystemExit(f'Expected 37 publications, found {len(pubs)}')
  for path in ROOT.glob('*.html'):
    text=path.read_text(encoding='utf-8'); text=replace_person_schema(text); text=replace_emails(text); path.write_text(text,encoding='utf-8')
  pubpath=ROOT/'publications.html'; text=clean_publications_head(pubpath.read_text(encoding='utf-8'))
  cards='\n'.join(static_card(p) for p in pubs)
  text=re.sub(r'<div id="collectionContainer">.*?</div>', '<div id="collectionContainer" data-static-publications="37">\n'+cards+'\n</div>', text, count=1, flags=re.S)
  graph={'@context':'https://schema.org','@graph':[PERSON]+[article_schema(p,SITE_URL+'/publications/'+slugify(p.get('doi',''))+'.html') for p in pubs]}
  schema='<script type="application/ld+json" id="publications-schema">'+json.dumps(graph,ensure_ascii=False,separators=(',',':'))+'</script>'
  text=re.sub(r'<script type="application/ld\+json" id="publications-schema">.*?</script>','',text,flags=re.S)
  citation_block = CITATION_META_START+'\n'+'\n'.join(citation_meta(p) for p in pubs)+'\n'+CITATION_META_END
  text=text.replace('</head>',citation_block+'\n'+schema+'\n</head>',1)
  pubpath.write_text(text,encoding='utf-8')
  pdir=ROOT/'publications'; pdir.mkdir(exist_ok=True)
  for f in pdir.glob('*.html'): f.unlink()
  for p in pubs:
    record=openalex_records.get(str(p.get('doi') or '').strip().lower(),{})
    oa_record=unpaywall_records.get(str(p.get('doi') or '').strip().lower(),{})
    cr_record=crossref_records.get(str(p.get('doi') or '').strip().lower(),{})
    md_record=mendeley_records.get(str(p.get('doi') or '').strip().lower(),{})
    (pdir/(slugify(p.get('doi',''))+'.html')).write_text(publication_page(p,record,oa_record,cr_record,md_record),encoding='utf-8')
  app=ROOT/'assets/js/app.js'; js=app.read_text(encoding='utf-8')
  js=re.sub(r'function publicationShareUrl\(anchor\)\{.*?\n\}', "function publicationShareUrl(anchor){\n  const slug=String(anchor||'').replace(/^pub-/,'');\n  return new URL(`publications/${slug}.html`,window.location.href).toString();\n}", js, count=1, flags=re.S)
  app.write_text(js,encoding='utf-8')
  (ROOT/'robots.txt').write_text(robots_text(),encoding='utf-8')
  urls=['','about.html','research.html','publications.html','patents.html','projects.html','llms.txt']+['publications/'+slugify(p.get('doi',''))+'.html' for p in pubs]
  rows='\n'.join('  <url><loc>'+SITE_URL+'/'+esc(u)+'</loc><lastmod>'+TODAY+'</lastmod></url>' for u in urls)
  (ROOT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+rows+'\n</urlset>\n',encoding='utf-8')
  lines=['# Wei-Hao Chiu Academic Website','', '> Official academic website of Wei-Hao Chiu, Ph.D., Associate Researcher at Chang Gung University.','','## Main Pages','',f'- [Home]({SITE_URL}/)',f'- [About]({SITE_URL}/about.html)',f'- [Research]({SITE_URL}/research.html)',f'- [Publications]({SITE_URL}/publications.html)',f'- [Patents]({SITE_URL}/patents.html)',f'- [Projects]({SITE_URL}/projects.html)','','## Contact','','- Personal email: weihao.chiu@gmail.com','- Chang Gung University email: d000019005@cgu.edu.tw','','## Research Expertise','']
  lines += ['- '+x for x in PERSON['knowsAbout']]; lines += ['','## Publications','']
  for p in pubs: lines.append(f"- [{p.get('title')}]({SITE_URL}/publications/{slugify(p.get('doi',''))}.html) — {p.get('journal')}, {p.get('year')}; DOI: {p.get('doi')}")
  (ROOT/'llms.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
  mp=ROOT/'data/site_meta.json'; meta=json.loads(mp.read_text(encoding='utf-8')); meta.update({'version':'v23','lastUpdated':TODAY,'notes':'V23 adds static crawler-readable publications, 37 ScholarlyArticle records, upgraded Person schema, corrected email links on every page, article-specific citation and Open Graph metadata, expanded llms.txt, and crawler-aware robots and sitemap files.'}); mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()

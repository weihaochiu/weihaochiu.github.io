"""Render curated news as static HTML, separate from scholarly-output counts."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- NEWS_START -->'
END = '<!-- NEWS_END -->'


def esc(value):
    return html.escape(str(value), quote=True)


def render(items, full=False):
    cards = []
    for item in sorted(items, key=lambda row: row['sortDate'], reverse=True)[:None if full else 3]:
        anchor = esc(item['id'])
        title = esc(item['title'])
        body = ''.join(f'<p>{esc(p)}</p>' for p in item['paragraphs']) if full else f'<p>{esc(item["summary"])}</p>'
        image = item.get('image')
        if full and image:
            body += (f'<figure class="news-photo"><a href="{esc(image["full"])}" target="_blank" rel="noopener" aria-label="Open full-size poster presentation photograph">'
                     f'<img src="{esc(image["src"])}" width="{image["width"]}" height="{image["height"]}" loading="lazy" decoding="async" alt="{esc(image["alt"])}"/></a>'
                     f'<figcaption>{esc(image["caption"])}</figcaption></figure>')
        link = '<a class="action" href="about.html#awards">View award record →</a>' if full else f'<a class="action" href="news.html#{anchor}">Read news →</a>'
        heading = title if full else f'<a href="news.html#{anchor}">{title}</a>'
        cards.append(f'<article class="news-entry" id="{anchor}" aria-labelledby="title-{anchor}"><p class="news-date">{esc(item["dateLabel"])}</p><h{2 if full else 3} id="title-{anchor}">{heading}</h{2 if full else 3}>{body}{link}</article>')
    return '\n'.join(cards) or '<p>No news yet.</p>'


def main():
    items = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))
    ids = [item['id'] for item in items]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', key) for key in ids):
        raise ValueError('News IDs must be unique URL-safe anchors')
    index = ROOT / 'index.html'
    text = index.read_text(encoding='utf-8')
    section = START + '\n<section class="content shell" id="latest-news" aria-labelledby="latest-news-title"><div class="section-title"><div><span class="kicker">Updates</span><h2 id="latest-news-title">Latest News</h2></div><a href="news.html">View all news →</a></div><div class="news-preview">' + render(items) + '</div></section>\n' + END
    if START in text:
        text = re.sub(re.escape(START) + '.*?' + re.escape(END), lambda _: section, text, flags=re.S)
    else:
        text = text.replace('    <section class="content shell" id="about">', section + '\n\n    <section class="content shell" id="about">', 1)
    award_count = len(json.loads((ROOT / 'data/awards.json').read_text(encoding='utf-8')))
    text = re.sub(r'(data-output-count="awards">)\d+', lambda match: match[1] + str(award_count), text)
    index.write_text(text, encoding='utf-8')
    template = (ROOT / 'about.html').read_text(encoding='utf-8')
    head = template.split('</head>')[0]
    description = 'Academic news, conference activities and research recognitions of Wei-Hao Chiu.'
    head = head.replace('About | Wei-Hao Chiu', 'News | Wei-Hao Chiu').replace('https://weihaochiu.github.io/about.html', 'https://weihaochiu.github.io/news.html').replace('Professional experience, education, theses and awards of Wei-Hao Chiu.', description)
    header = re.search(r'<header\b.*?</header>', template, re.S).group()
    footer = re.search(r'<footer\b.*?</footer>', template, re.S).group()
    page = head + '</head><body>' + header + '<section class="page-header"><div class="shell"><h1>News</h1><p>Research updates, conference activities and recognitions.</p></div></section><main class="content shell news-archive"><a class="action" href="index.html#latest-news">← Latest news on the homepage</a>' + render(items, full=True) + '</main>' + footer + '<script src="assets/js/app.js"></script></body></html>\n'
    (ROOT / 'news.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()

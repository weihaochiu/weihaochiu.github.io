import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_news', ROOT / 'scripts/build_news.py')
news = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news)


class NewsTests(unittest.TestCase):
    def test_latest_three_and_safe_text(self):
        item = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))[0]
        items = [{**item, 'id': f'entry-{i}', 'sortDate': f'2026-10-{i:02}', 'title': '<script>test</script>'} for i in range(1, 5)]
        result = news.render(items)
        self.assertEqual(result.count('<article '), 3)
        self.assertNotIn('id="entry-1"', result)
        self.assertLess(result.index('id="entry-4"'), result.index('id="entry-3"'))
        self.assertNotIn('<script>', result)

    def test_build_preserves_home_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            for name in ('index.html', 'about.html', 'data/news.json', 'data/awards.json'):
                (root / name).write_bytes((ROOT / name).read_bytes())
            with patch.object(news, 'ROOT', root):
                news.main()
                before = [(root / name).read_bytes() for name in ('index.html', 'news.html')]
                news.main()
            self.assertEqual(before, [(root / name).read_bytes() for name in ('index.html', 'news.html')])
            home = (root / 'index.html').read_text(encoding='utf-8')
            self.assertEqual(home.count(news.START), 1)
            self.assertIn('id="combinedYearChart"', home)
            self.assertIn('data-output-count="awards">11', home)
            self.assertIn(news.STYLE_URL, home)
            story = (root / 'news/sdse-2026-poster-award.html').read_text(encoding='utf-8')
            self.assertIn('../' + news.STYLE_URL, story)

    def test_photo_assets_and_award_identity(self):
        item = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))[0]
        for key in ('src', 'full', 'thumbnail'):
            self.assertTrue((ROOT / item['image'][key]).is_file())
        self.assertIn('Conference dates', item['dateLabel'])
        archive = news.render([item], full=True)
        self.assertIn('loading="lazy"', archive)
        self.assertIn('about.html#awards', archive)
        self.assertNotIn('<figure', news.render([item]))

    def test_previews_only_load_thumbnail_and_no_image_fallback(self):
        item = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))[0]
        preview = news.render([item])
        self.assertIn(item['image']['thumbnail'], preview)
        self.assertNotIn(item['image']['src'] + '"', preview)
        self.assertNotIn(item['image']['full'], preview)
        self.assertIn('news/' + item['id'] + '.html', preview)
        plain = {key: value for key, value in item.items() if key != 'image'}
        self.assertNotIn('<img', news.render([plain]))
        self.assertNotIn('has-thumbnail', news.render([plain]))

    def test_multiyear_pagination_stories_and_cleanup(self):
        item = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))[0]
        items = [{**item, 'id': f'entry-{i}', 'sortDate': f'2026-10-{i:02}'} for i in range(1, 24)]
        items.append({**item, 'id': 'older-story', 'sortDate': '2025-12-01'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'news').mkdir()
            for name in ('index.html', 'about.html', 'data/awards.json'):
                (root / name).write_bytes((ROOT / name).read_bytes())
            source = root / 'data/news.json'
            source.write_text(json.dumps(items), encoding='utf-8')
            (root / 'news/manual.html').write_text('user-maintained page', encoding='utf-8')
            with patch.object(news, 'ROOT', root):
                paths = news.main()
                for name, count in [('news.html', 10), ('news/page-2.html', 10), ('news/page-3.html', 4), ('news/2026-page-3.html', 3), ('news/2025.html', 1)]:
                    self.assertEqual((root / name).read_text(encoding='utf-8').count('<article '), count)
                    self.assertIn(name, paths)
                story = (root / 'news/older-story.html').read_text(encoding='utf-8')
                self.assertIn('../assets/css/styles.css', story)
                self.assertIn('../assets/images/news/', story)
                self.assertIn('https://weihaochiu.github.io/news/older-story.html', story)
                page2 = (root / 'news/page-2.html').read_text(encoding='utf-8')
                self.assertIn('href="../news.html" rel="prev"', page2)
                self.assertIn('href="../news/page-3.html" rel="next"', page2)
                self.assertNotIn('poster-full.jpg', page2)
                self.assertNotIn('fetch(', page2)
                for name in paths:
                    markup = (root / name).read_text(encoding='utf-8')
                    self.assertEqual(len(re.findall(r'<link[^>]*rel="canonical"', markup)), 1)
                source.write_text(json.dumps([item]), encoding='utf-8')
                news.main()
            self.assertFalse((root / 'news/page-3.html').exists())
            self.assertFalse((root / 'news/older-story.html').exists())
            self.assertTrue((root / 'news/manual.html').exists())
            self.assertIn("location.replace('news/'+newsId+'.html')", (root / 'news.html').read_text(encoding='utf-8'))

    def test_rejects_reserved_story_ids(self):
        item = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'data/news.json').write_text(json.dumps([{**item, 'id': 'page-2'}]), encoding='utf-8')
            with patch.object(news, 'ROOT', root), self.assertRaises(ValueError):
                news.main()

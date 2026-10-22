import importlib.util
import json
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

    def test_photo_assets_and_award_identity(self):
        item = json.loads((ROOT / 'data/news.json').read_text(encoding='utf-8'))[0]
        for key in ('src', 'full'):
            self.assertTrue((ROOT / item['image'][key]).is_file())
        self.assertIn('Conference dates', item['dateLabel'])
        archive = news.render([item], full=True)
        self.assertIn('loading="lazy"', archive)
        self.assertIn('about.html#awards', archive)
        self.assertNotIn('<figure', news.render([item]))

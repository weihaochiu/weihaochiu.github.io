import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_publication_authorships import parse_jats, merge_publication, SourceResult, AuthorCandidate


class JatsAuthorshipTests(unittest.TestCase):
    def test_original_author_lists_are_complete_in_copyable_citations(self):
        publications = json.loads((Path(__file__).resolve().parents[1] / 'data/publications.json').read_text(encoding='utf-8'))
        by_id = {p['id']: p for p in publications}
        expected = {
            '10.1002/adfm.202306367': (15, 'Lin, Yan-Duo'),
            '10.1039/d3cc04699k': (10, 'Yang, June Hung'),
        }
        for identity, (count, restored) in expected.items():
            with self.subTest(identity=identity):
                publication = by_id[identity]
                self.assertEqual(count, len(publication['authors']))
                self.assertIn(restored, publication['authors'])
                self.assertEqual(publication['authors'], [a['name'] for a in publication['authorships']])
                self.assertTrue(publication['citation'].startswith('; '.join(publication['authors']) + '. '))

    def test_spiro_original_affiliation_and_correspondence(self):
        publications = json.loads((Path(__file__).resolve().parents[1] / 'data/publications.json').read_text(encoding='utf-8'))
        publication = next(p for p in publications if p['id'] == '10.1002/advs.77623')
        self.assertEqual(14, len(publication['authors']))
        self.assertEqual(9, len(publication['affiliations']))
        owner = next(a for a in publication['authorships'] if a['name'] == 'Wei-Hao Chiu')
        units = [a for a in publication['affiliations'] if a['id'] in owner['affiliationIds']]
        self.assertEqual(['2'], [a['label'] for a in units])
        self.assertIn('Sustainability and Energy Technologies', units[0]['raw'])
        self.assertFalse(owner['isCorresponding'])
        self.assertEqual(6, sum(a['isCorresponding'] is True for a in publication['authorships']))

    def test_locked_original_review_survives_conflicting_aggregator(self):
        publication = {
            'authors': ['Wei-Hao Chiu'],
            'authorships': [{'name': 'Wei-Hao Chiu', 'isCorresponding': False,
                             'isEqualContributor': None, 'correspondingEmail': '',
                             'affiliationIds': ['original'], 'sourceName': 'Wei-How Chiu'}],
            'affiliations': [{'id': 'original', 'raw': 'Original department'}],
            'authorshipMetadata': {'status': 'manual', 'manualOverride': True,
                'lockedFields': ['authorships', 'affiliations'],
                'publisherVerification': {'sourceUrl': 'https://example.test/original.pdf'}}
        }
        result = SourceResult(source='openalex', source_url='https://example.test/api',
            authors=[AuthorCandidate(name='Wei-Hao Chiu', author_order=1, is_corresponding=True,
                                     is_equal_contributor=True, corresponding_email='wrong@example.test')])
        merged, changed = merge_publication(publication, [result])
        self.assertFalse(changed)
        self.assertEqual(publication, merged)

    def test_equal_contribution_is_not_correspondence_and_editors_are_excluded(self):
        xml = '''<article><front><article-meta>
          <contrib-group content-type="author">
            <contrib><name><surname>Chiu</surname><given-names>Wei-Hao</given-names></name>
              <xref ref-type="aff" rid="a1"/><xref ref-type="author-notes" rid="eq"/></contrib>
            <contrib><name><surname>Lee</surname><given-names>Kun-Mu</given-names></name>
              <xref ref-type="aff" rid="a1"/><xref ref-type="author-notes" rid="corr"/>
              <xref ref-type="author-notes" rid="eq"/></contrib>
          </contrib-group>
          <contrib-group content-type="editor"><contrib><name><surname>Editor</surname>
            <given-names>Academic</given-names></name><role>Academic Editor</role></contrib></contrib-group>
          <aff id="a1"><label>1</label>Center for Green Technology, Chang Gung University, Taiwan; private@example.test</aff>
          <author-notes><fn id="eq"><label>†</label><p>These authors contributed equally to this work.</p></fn>
          <fn id="corr"><label>*</label><p>Correspondence: <email>lee@example.test</email></p></fn></author-notes>
          </article-meta></front></article>'''
        result = parse_jats(xml, 'https://example.test/article.xml')
        self.assertEqual(['Wei-Hao Chiu', 'Kun-Mu Lee'], [a.name for a in result.authors])
        self.assertEqual([True, True], [a.is_equal_contributor for a in result.authors])
        self.assertEqual([False, True], [a.is_corresponding for a in result.authors])
        self.assertEqual('', result.authors[0].corresponding_email)
        self.assertEqual('lee@example.test', result.authors[1].corresponding_email)
        self.assertEqual('Center for Green Technology, Chang Gung University, Taiwan',
                         result.authors[0].affiliations[0].text)

    def test_corresp_attribute_and_direct_email(self):
        result = parse_jats('''<article><front><article-meta><contrib-group>
          <contrib contrib-type="author" corresp="yes"><name><surname>Lin</surname>
          <given-names>Yan-Duo</given-names></name><address><email>lin@example.test</email></address></contrib>
          </contrib-group></article-meta></front></article>''', 'https://example.test/article.xml')
        self.assertTrue(result.authors[0].is_corresponding)
        self.assertEqual('lin@example.test', result.authors[0].corresponding_email)

    def test_shared_correspondence_note_matches_each_authors_initials(self):
        result = parse_jats('''<article><front><article-meta><contrib-group>
          <contrib><name><surname>Lee</surname><given-names>Kun-Mu</given-names></name><xref ref-type="corresp" rid="c"/></contrib>
          <contrib><name><surname>Wu</surname><given-names>Ming-Chung</given-names></name><xref ref-type="corresp" rid="c"/></contrib>
          </contrib-group><author-notes><corresp id="c">Correspondence:
          <email>lee@example.test</email> (K.-M.L.); <email>wu@example.test</email> (M.-C.W.)</corresp></author-notes>
          </article-meta></front></article>''', 'https://example.test/article.xml')
        self.assertEqual(['lee@example.test', 'wu@example.test'], [a.corresponding_email for a in result.authors])

    def test_other_author_notes_do_not_create_author_roles(self):
        result = parse_jats('''<article><front><article-meta><contrib-group><contrib>
          <name><surname>Chiu</surname><given-names>Wei-Hao</given-names></name><xref ref-type="fn" rid="n"/>
          </contrib></contrib-group><author-notes><fn id="n">Present address: Taiwan.</fn></author-notes>
          </article-meta></front></article>''', 'https://example.test/article.xml')
        self.assertIsNone(result.authors[0].is_corresponding)
        self.assertIsNone(result.authors[0].is_equal_contributor)

import unittest
from zensols.config import ImportIniConfig, ImportConfigFactory
from zensols.nlp import FeatureDocument, FeatureToken

FeatureToken.WRITABLE_FEATURE_IDS = list(FeatureToken.WRITABLE_FEATURE_IDS) + ['mimic_']


class TestParser(unittest.TestCase):
    def _get_parser(self, name: str):
        conf = ImportIniConfig(f'test-resources/{name}.conf')
        fac = ImportConfigFactory(conf)
        return fac('doc_parser')

    def test_mimic_tokenizer(self):
        parser = self._get_parser('only-tokenizer')
        text = """\
Patient recorded as having no known Allergies to Drugs

Attending:[**First Name3 (LF) 922**]"""
        should = ('Patient', 'recorded', 'as', 'having', 'no', 'known',
                  'Allergies to Drugs', 'Attending', ':',
                  '[**First Name3 (LF) 922**]')
        doc: FeatureDocument = parser(text)
        self.assertEqual(should, tuple(doc.norm_token_iter()))
        for tok in doc.token_iter():
            self.assertFalse(hasattr(tok, 'tok.mimic_'))

    def test_decorator(self):
        print()
        parser = self._get_parser('add-decorator')
        text = """\
Patient recorded as having no known Allergies to Drugs

Attending:[**First Name3 (LF) 922**]"""
        should = ('Patient', 'recorded', 'as', 'having', 'no', 'known',
                  'Allergies to Drugs', 'Attending', ':',
                  'FIRSTNAME')
        doc: FeatureDocument = parser(text)
        self.assertEqual(should, tuple(doc.norm_token_iter()))
        should = ('<none>', '<none>', '<none>', '<none>', '<none>', '<none>',
                  '<none>', '<none>', '<none>', 'pseudo')
        self.assertEqual(should, tuple(map(
            lambda t: t.mimic_, doc.token_iter())))
        if 0:
            for tok in doc.token_iter():
                tok.write()

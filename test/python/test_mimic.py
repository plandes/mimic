import unittest
import warnings
from zensols.config import ImportIniConfig, ImportConfigFactory
from zensols.nlp import FeatureDocument, FeatureToken

FeatureToken.WRITABLE_FEATURE_IDS = tuple(list(FeatureToken.WRITABLE_FEATURE_IDS) + ['mimic_'])


with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import gensim.matutils
    import transformers.image_utils


class TestParser(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._doc_parser_name = 'doc_parser'

    def _get_parser(self, name: str):
        conf = ImportIniConfig(f'test-resources/{name}.conf')
        fac = ImportConfigFactory(conf)
        return fac(self._doc_parser_name)

    def test_mimic_tokenizer(self):
        parser = self._get_parser('only-tokenizer')
        text = """\
Patient recorded as having no known Allergies to Drugs

Attending:[**First Name3 (LF) 922**]"""
        should = ('Patient', 'recorded', 'as', 'having', 'no', 'known',
                  'Allergies', 'to', 'Drugs', '\n', '\n', 'Attending', ':',
                  '[**First Name3 (LF) 922**]')
        doc: FeatureDocument = parser(text)
        self.assertEqual(should, tuple(doc.norm_token_iter()))
        for tok in doc.token_iter():
            self.assertFalse(hasattr(tok, 'tok.mimic_'))

    def test_mimic_boundaries(self):
        def should_fsep(c):
            return ('Attending', c, '[**First Name3 (LF) 922**]', '.')

        def should_bsep(c):
            return ('Attending', '[**First Name3 (LF) 922**]', c, 'trail', '.')

        parser = self._get_parser('only-tokenizer')
        tests = (("Attending [**First Name3 (LF) 922**].",
                  ('Attending', '[**First Name3 (LF) 922**]', '.')),
                 ("Attending:[**First Name3 (LF) 922**].", should_fsep(':')),
                 ("Attending-[**First Name3 (LF) 922**].", should_fsep('-')),
                 ("Attending@[**First Name3 (LF) 922**].", should_fsep('@')),
                 ("Attending[**First Name3 (LF) 922**].",
                  ('Attending', '[**First Name3 (LF) 922**]', '.')),
                 ("Attending [**First Name3 (LF) 922**] trail.",
                  ('Attending', '[**First Name3 (LF) 922**]', 'trail', '.')),
                 ("Attending [**First Name3 (LF) 922**]:trail.", should_bsep(':')),
                 ("Attending [**First Name3 (LF) 922**]-trail.", should_bsep('-')),
                 ("Attending [**First Name3 (LF) 922**]trail.",
                  ('Attending', '[**First Name3 (LF) 922**]', 'trail', '.')),
                 ("Attending[**First Name3 (LF) 922**]trail.",
                  ('Attending', '[**First Name3 (LF) 922**]', 'trail', '.')))
        for text, should in tests:
            doc: FeatureDocument = parser(text)
            self.assertEqual(should, tuple(doc.norm_token_iter()))
            for tok in doc.token_iter():
                self.assertFalse(hasattr(tok, 'tok.mimic_'))

    def test_decorator(self):
        parser = self._get_parser('add-decorator')
        text = """\
Patient recorded as having no known Allergies to Drugs

Attending:[**First Name3 (LF) 922**]"""
        doc: FeatureDocument = parser(text)

        should = ('Patient', 'recorded', 'as', 'having', 'no', 'known',
                  'Allergies', 'to', 'Drugs', '\n', '\n',
                  'Attending', ':', 'FIRSTNAME')
        self.assertEqual(should, tuple(doc.norm_token_iter()))

        should = ('-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-',
                  '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-',
                  'mask')
        self.assertEqual(should, tuple(map(
            lambda t: t.mimic_, doc.token_iter())))

    def test_decorated_combining_medical_parser(self):
        self._doc_parser_name = 'mednlp_combine_doc_parser'
        parser = self._get_parser('add-decorator')
        text = """\
Patient (John Smith) recorded as having no known Allergies to Drugs

Attending:[**First Name3 (LF) 922**]"""
        doc: FeatureDocument = parser(text)

        if 0:
            print()
            doc.write()
            for t in doc.tokens:
                print(t, t.cui_, t.ent_, t.mimic_)
            print(tuple(map(lambda t: t.norm, doc.token_iter())))
            print(tuple(map(lambda t: t.cui_, doc.token_iter())))
            print(tuple(map(lambda t: t.ent_, doc.token_iter())))
            print(tuple(map(lambda t: t.mimic_, doc.token_iter())))
            return

        should = ('Patient', '(', 'John', 'Smith', ')', 'recorded', 'as',
                  'having', 'no', 'known', 'Allergies', 'to', 'Drugs',
                  '\n', '\n', 'Attending', ':', 'FIRSTNAME')
        self.assertEqual(should, tuple(doc.norm_token_iter()))

        should = ('-<N>-', '-<N>-', '-<N>-', 'C0086418', '-<N>-', '-<N>-',
                  '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-',
                  '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-')
        self.assertEqual(should, tuple(map(
            lambda t: t.cui_, doc.token_iter())))

        should = ('-<N>-', '-<N>-', 'PERSON', 'PERSON', '-<N>-', '-<N>-',
                  '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-',
                  '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-')
        self.assertEqual(should, tuple(map(
            lambda t: t.ent_, doc.token_iter())))

        should = ('-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-',
                  '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-',
                  '-<N>-', '-<N>-', '-<N>-', '-<N>-', '-<N>-', 'mask')
        self.assertEqual(should, tuple(map(
            lambda t: t.mimic_, doc.token_iter())))

"""A utility library for parsing the MIMIC-III corpus

"""
__author__ = 'Paul Landes'

from dataclasses import dataclass, field
import logging
from pathlib import Path
from zensols.persist import Stash
from zensols.nlp import FeatureDocumentParser, FeatureDocument, FeatureToken
from . import NoteEvent, HospitalAdmission, HospitalAdmissionDbStash, Corpus

logger = logging.getLogger(__name__)


@dataclass
class Application(object):
    """A utility library for parsing the MIMIC-III corpus

    """
    config_factory: bool

    doc_parser: FeatureDocumentParser = field()
    """Used to parse command line documents."""

    corpus: Corpus = field()
    """The contains assets to access the MIMIC-III corpus via database."""

    def dump(self, sent: str, output_file: Path = Path('feature.csv')):
        """Dump all features available to a CSV file.

        :param sent: the sentence to parse and generate features

        """
        import pandas as pd
        doc: FeatureDocument = self.doc_parser(sent)
        df = pd.DataFrame(map(lambda t: t.asdict(), doc.tokens))
        df.to_csv(output_file)
        logger.info(f'write: {output_file}')

    def show(self, sent: str):
        """Parse a sentence and print all features for each token.

        :param sent: the sentence to parse and generate features

        """
        fids = set(FeatureToken.WRITABLE_FEATURE_IDS) | \
            {'ent_', 'cui_', 'mimic_'}
        fids = fids - set('dep i_sent sent_i tag children is_wh'.split())
        # parse the text in to a hierarchical langauge data structure
        doc: FeatureDocument = self.doc_parser(sent)
        print('tokens:')
        for tok in doc.token_iter():
            print(f'{tok.norm}:')
            tok.write_attributes(1, include_type=False,
                                 feature_ids=fids, inline=True)
        print('-' * 80)
        # named entities are also stored contiguous tokens at the document
        # level
        print('named entities:')
        for e in doc.entities:
            print(f'{e}: cui={e[0].cui_}/{e[0].ent_}')

    def corpus_stats(self):
        """Print corpus statistics."""
        self.corpus.write()

    def clear(self):
        """Clear the all cached admission and note parses."""
        self.corpus.clear()

    def write_discharge(self, hadm_id: str = '119960'):
        """Write a discharge summary.

        :param hadm_id: the hospital admission ID

        """
        stash: HospitalAdmissionDbStash = self.corpus.hospital_adm_stash
        if hadm_id is None:
            adm = next(iter(stash.values()))
        else:
            adm = stash[str(hadm_id)]
        adm.write()

    def write_note(self, row_id: str = '1092611'):
        """Write a note.

        :param row_id: the unique note identifier in the NOTEEVENTS table

        """
        note: NoteEvent = self.corpus.note_event_persister.get_by_id(row_id)
        print(note.text)

    def write_note_by_categories(self, note_limit: int = 10):
        """Write a random sample notes across each category.

        :param note_limit: the number of notes to write for each category

        """
        self.corpus.write_note_event_by_categories(note_limit=note_limit)

    def write_note_categories(self, hadm_id: str = '119960'):
        """Write note categories of an admission.

        :param hadm_id: the hospital admission ID

        """
        stash: Stash = self.corpus.hospital_adm_stash
        adm: HospitalAdmission = stash[hadm_id]
        for note in adm:
            print(f'{note.row_id},{note.category}')

    def unmatched_tokens(self, hadm_id: str = '119960',
                         no_ents: bool = False):
        """Find all unmatched tokens for an admission.

        :param hadm_id: the hospital admission ID

        :param no_ents: do not include unmatched entities

        """
        stash: Stash = self.corpus.hospital_adm_stash
        adm: HospitalAdmission = stash[hadm_id]
        for note in adm.notes:
            print(note)
            norm = note.doc.norm
            found_unmatch_tok = norm.find('**') > -1
            found_unmatch_ent = norm.find('<UNKNOWN>') > -1
            if found_unmatch_tok or (not no_ents and found_unmatch_ent):
                print('original:')
                print(note.doc.text)
                print('norm:')
                print(norm)
            print('_' * 120)

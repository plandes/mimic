"""A utility library for parsing the MIMIC-III corpus

"""
__author__ = 'Paul Landes'

from typing import Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
from pathlib import Path
import re
from zensols.persist import FileTextUtil
from zensols.config import ConfigFactory
from zensols.cli import ApplicationError
from zensols.nlp import FeatureDocumentParser, FeatureDocument, FeatureToken
from . import (
    NoteEvent, NoteEventPersister, Note,
    HospitalAdmission, HospitalAdmissionDbStash, Corpus,
)

logger = logging.getLogger(__name__)


class _Format(Enum):
    meta = auto()
    txt = auto()
    json = auto()

    @property
    def ext(self) -> str:
        return 'txt' if self.name == 'meta' else self.name


@dataclass
class Application(object):
    """A utility library for parsing the MIMIC-III corpus

    """
    config_factory: ConfigFactory = field()
    """Used to get temporary resources"""

    doc_parser: FeatureDocumentParser = field()
    """Used to parse command line documents."""

    corpus: Corpus = field()
    """The contains assets to access the MIMIC-III corpus via database."""

    def write_features(self, sent: str,
                       output_file: Path = Path('feature.csv')):
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

    def _get_adm(self, hadm_id: str) -> HospitalAdmission:
        stash: HospitalAdmissionDbStash = self.corpus.hospital_adm_stash
        if hadm_id == '-':
            adm = next(iter(stash.values()))
        else:
            adm = stash[str(hadm_id)]
        return adm

    def write_admission_summary(self, hadm_id: str):
        """Write an admission note categories and section names.

        :param hadm_id: the hospital admission ID or ``-`` for a random ID

        """
        adm: HospitalAdmission = self._get_adm(hadm_id)
        adm.write()

    def write_admission(self, hadm_id: str, out_dir: Path = Path('.'),
                        output_format: _Format = _Format.meta):
        """Write all the notes of an admission.

        :param hadm_id: the hospital admission ID or ``-`` for a random ID

        :param out_dir: the output directory

        :param output_format: the output format of the note

        """
        if hadm_id == '-':
            stash: HospitalAdmissionDbStash = self.corpus.hospital_adm_stash
            hadm_id = next(iter(stash.keys()))
        adm: HospitalAdmission = self._get_adm(hadm_id)
        out_dir = out_dir / 'adm' / hadm_id
        out_dir.mkdir(parents=True, exist_ok=True)
        note: Note
        for note in adm.notes:
            name: str = FileTextUtil.normalize_text(
                f'{note.category}-{note.description}')
            path: Path = out_dir / f'{note.row_id}-{name}.{output_format.ext}'
            logger.info(f'wrote note to {path}')
            with open(path, 'w') as f:
                {_Format.meta: lambda: note.write_human(writer=f),
                 _Format.txt: lambda: f.write(note.text),
                 _Format.json: lambda: f.write(note.asjson(indent=4)),
                 }[output_format]()

    def write_note(self, row_id: str):
        """Write a note.

        :param row_id: the unique note identifier in the NOTEEVENTS table

        """
        note: NoteEvent = self.corpus.note_event_persister.get_by_id(row_id)
        print(note.text)

    def write_hadm_id_for_note(self, row_id: int) -> int:
        """Get the hospital admission ID (``hadm_id``) that has note ``row_id``.

        :param row_id: the unique note identifier in the NOTEEVENTS table

        """
        np: NoteEventPersister = self.corpus.note_event_persister
        hadm_id: Optional[int] = np.get_hadm_id(row_id)
        if hadm_id is None:
            raise ApplicationError(f'No note found: {row_id}')
        print(hadm_id)
        return hadm_id

    def _get_temporary_results_dir(self) -> Path:
        return Path(self.config_factory.config.get_option(
            'temporary_results_dir', 'mimic_default'))

    def write_note_by_categories(self, note_limit: int = 1,
                                 output_format: _Format = _Format.meta):
        """Write a certain number of notes across each category.

        :param note_limit: the number of notes to write

        :param output_format: the output format of the note

        """
        np: NoteEventPersister = self.corpus.note_event_persister
        tmpdir: Path = self._get_temporary_results_dir() / 'by_category'
        tmpdir.mkdir(parents=True, exist_ok=True)
        cat: str
        ntevt_cnt = 0
        for i, cat in enumerate(np.categories):
            ntevts: Tuple[NoteEvent] = np.get_notes_by_category(cat, note_limit)
            name: str = re.sub(r'[ \t/_-]+', '-', cat).lower()
            if name.endswith('-'):
                name = name[0:-1]
            for ntevt in ntevts:
                path = tmpdir / f'{name}-{ntevt.hadm_id}.{output_format.meta}'
                with open(path, 'w') as f:
                    {_Format.meta: lambda: ntevt.write_human(writer=f),
                     _Format.txt: lambda: f.write(ntevt.text),
                     _Format.json: lambda: f.write(ntevt.asjson(indent=4)),
                     }[output_format]()
                if logger.isEnabledFor(logging.INFO):
                    logger.info(f'wrote {len(ntevts)} ntevts to {path}')
            ntevt_cnt += len(ntevts)
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'wrote {ntevt_cnt} ntevts')

    def write_discharge_reports(self, note_limit: int = 1,
                                out_dir: Path = Path('.')):
        """Write discharge reports (as apposed to addendums).

        :param note_limit: the number of notes to write

        :param out_dir: the output directory

        """
        np: NoteEventPersister = self.corpus.note_event_persister
        out_dir.mkdir(parents=True, exist_ok=True)
        notes: Tuple[NoteEvent] = np.get_discharge_reports(note_limit)
        for note in notes:
            path = out_dir / f'{note.hadm_id}.txt'
            with open(path, 'w') as f:
                note.write(writer=f)
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'wrote {len(notes)} notes to {out_dir}')

    def write_note_categories(self, hadm_id: str):
        """Write note categories of an admission.

        :param hadm_id: the hospital admission ID or ``-`` for a random ID

        """
        adm: HospitalAdmission = self._get_adm(hadm_id)
        for note in adm:
            print(f'{note.row_id},{note.category}')

    def _unmatched_tokens(self, hadm_id: str, no_ents: bool = False):
        """Find all unmatched tokens for an admission.

        :param hadm_id: the hospital admission ID or ``-`` for a random ID

        :param no_ents: do not include unmatched entities

        """
        adm: HospitalAdmission = self._get_adm(hadm_id)
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

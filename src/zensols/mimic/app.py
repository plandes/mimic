"""A utility library for parsing the MIMIC-III corpus

"""
__author__ = 'Paul Landes'

from typing import Tuple, Optional
from dataclasses import dataclass, field
import logging
from pathlib import Path
from zensols.util import stdout
from zensols.config import ConfigFactory
from zensols.cli import ApplicationError
from zensols.nlp import FeatureDocumentParser, FeatureDocument, FeatureToken
from . import (
    NoteEvent, NoteEventPersister, NoteFormat, Note,
    HospitalAdmission, HospitalAdmissionDbStash, Corpus,
    NoteDocumentPreemptiveStash,
)

logger = logging.getLogger(__name__)


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

    preempt_stash: NoteDocumentPreemptiveStash = field()
    """A multi-processing stash used to preemptively parse notes."""

    def write_features(self, sent: str, out_file: Path = None):
        """Parse a sentence as MIMIC data and write features to CSV.

        :param sent: the sentence to parse and generate features

        :param out_file: the file to write

        """
        import pandas as pd
        doc: FeatureDocument = self.doc_parser(sent)
        df = pd.DataFrame(map(lambda t: t.asdict(), doc.tokens))
        out_file = Path('feature.csv') if out_file is None else out_file
        df.to_csv(out_file)
        logger.info(f'wrote: {out_file}')

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

    def uniform_sample_hadm_ids(self, limit: int = 1):
        """Print a uniform random sample of admission hadm_ids.

        :param limit: the number to fetch

        """
        for i in self.corpus.admission_persister.uniform_sample_hadm_ids(limit):
            print(i)

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

    def write_discharge_reports(self, limit: int = 1,
                                out_dir: Path = Path('.')):
        """Write discharge reports (as apposed to addendums).

        :param limit: the number to fetch

        :param out_dir: the output directory

        """
        np: NoteEventPersister = self.corpus.note_event_persister
        out_dir.mkdir(parents=True, exist_ok=True)
        notes: Tuple[NoteEvent] = np.get_discharge_reports(limit)
        for note in notes:
            path = out_dir / f'{note.hadm_id}.txt'
            with open(path, 'w') as f:
                note.write(writer=f)
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'wrote {len(notes)} notes to {out_dir}')

    def _write_note(self, note: NoteEvent, out_file: Path,
                    output_format: NoteFormat):
        if out_file is None:
            out_file = Path(stdout.STANDARD_OUT_PATH)
        with stdout(out_file) as f:
            note.write_by_format(writer=f, note_format=output_format)
        if out_file.name != stdout.STANDARD_OUT_PATH:
            logger.info(f'wrote note to {out_file}')

    def write_note(self, row_id: int, out_file: Path = None,
                   output_format: NoteFormat = NoteFormat.text):
        """Write a note.

        :param row_id: the unique note identifier in the NOTEEVENTS table

        :param output_format: the output format of the note

        :param out_file: the file to write

        """
        note: NoteEvent = self.corpus.get_note_by_id(row_id)
        self._write_note(note, out_file, output_format)

    def write_admission(self, hadm_id: str, out_dir: Path = Path('.'),
                        output_format: NoteFormat = NoteFormat.text):
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
            path: Path = out_dir / f'{note.normal_name}.{output_format.ext}'
            self._write_note(note, path, output_format)

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

    def preempt_notes(self, input_file: Path, workers: int = None):
        """Preemptively document parse notes across multiple threads.

        :param input_file: a file of notes' unique ``row_id`` IDs

        :param workers: the number of processes to use to parse notes

        """
        if logger.isEnabledFor(logging.INFO):
            if input_file is None:
                from_str: str = 'all note anontations'
            else:
                from_str: str = str(input_file)
            logger.info(f'preempting notes from {from_str} ' +
                        f'for {workers} workers')
        try:
            with open(input_file) as f:
                row_ids = tuple(map(str.strip, f.readlines()))
        except OSError as e:
            raise ApplicationError(
                f'Could not preempt notes from file {input_file}: {e}') from e
        self.preempt_stash.process_keys(row_ids, workers)

    def _get_temporary_results_dir(self) -> Path:
        return Path(self.config_factory.config.get_option(
            'temporary_results_dir', 'mimic_default'))

    def clear(self):
        """Clear the all cached admission and note parses."""
        self.corpus.clear()

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

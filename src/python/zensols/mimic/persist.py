"""Persisters for the MIMIC-III database.

"""
__author__ = 'Paul Landes'

from typing import Tuple, Iterable, Optional, List, Callable
from dataclasses import dataclass, field
import logging
import sys
from itertools import chain
from zensols.config import Settings
from zensols.persist import persisted, ReadOnlyStash, chunks
from zensols.db import DbPersister
from zensols.db.dataclass import DataClassDbPersister
from zensols.db.sqlite import SqliteConnectionManager
from zensols.nlp import FeatureDocument, FeatureDocumentParser
from . import (
    MimicError, RecordNotFoundError,
    Admission, Patient, Diagnosis, Procedure, NoteEvent
)

logger = logging.getLogger(__name__)


@dataclass
class AdmissionPersister(DataClassDbPersister):
    """Manages instances of :class:`.Admission`.

    """
    def __post_init__(self):
        self.bean_class = Admission
        super().__post_init__()

    def get_by_hadm_id(self, hadm_id: int) -> Admission:
        """Return the admission by it's hospital admission ID."""
        adm = self.execute_by_name(
            'select_admission_by_hadm_id', params=(hadm_id,))
        if len(adm) == 0:
            raise RecordNotFoundError(self, 'hadm', hadm_id)
        if len(adm) > 1:
            raise MimicError('Found {len(adm)}>1 record(s) for hadm {hadm_id}')
        return adm[0]

    def get_hadm_ids(self, subject_id: int) -> Iterable[int]:
        """Get all hospital admission IDs (``hadm_id``) for a patient."""
        ids = self.execute_by_name(
            'select_hadm_for_subject_id', params=(subject_id,),
            row_factory='tuple')
        return map(lambda x: x[0], ids)

    def get_by_subject_id(self, subject_id: int) -> Tuple[Admission]:
        """Get an admissions by patient ID."""
        return self.execute_by_name(
            'select_admission_by_subject_id', params=(subject_id,))

    def get_admission_counts(self, limit: int = sys.maxsize) -> \
            Tuple[Tuple[int, int]]:
        """Return the counts of subjects for each hospital admission.

        :param limit: the limit on the return admission counts

        :return: a list of tuples, each in the form (``subject_id``, ``count``)

        """
        return self.execute_by_name(
            'select_admission_counts', params=(limit,),
            row_factory='tuple')

    def uniform_sample_hadm_ids(self, limit: int) -> Iterable[int]:
        """Return a sample from the uniform distribution of admission IDs.

        """
        return self.execute_by_name(
            'random_hadm', params=(limit,), row_factory=lambda x: x)


@dataclass
class PatientPersister(DataClassDbPersister):
    """Manages instances of :class:`.Patient`.

    """
    def __post_init__(self):
        self.bean_class = Patient
        super().__post_init__()

    def get_by_subject_id(self, subject_id: int) -> Patient:
        pat = self.execute_by_name(
            'select_patient_by_subject_id', params=(subject_id,))
        assert len(pat) == 1
        return pat[0]


@dataclass
class DiagnosisPersister(DataClassDbPersister):
    """Manages instances of :class:`.Diagnosis`.

    """
    def __post_init__(self):
        self.bean_class = Diagnosis
        super().__post_init__()

    def get_by_hadm_id(self, hadm_id: int) -> Diagnosis:
        """Get ICD-9 diagnoses codes by hospital admission IDs.

        """
        return self.execute_by_name(
            'select_diagnosis_by_hadm_id', params=(hadm_id,))

    def get_heart_failure_hadm_ids(self) -> Tuple[int]:
        """Return hospital admission IDs that are heart failure related.

        """
        return tuple(map(lambda r: r[0],
                         self.execute_by_name('select_heart_failure_hadm_id',
                                              row_factory='tuple')))


@dataclass
class ProcedurePersister(DataClassDbPersister):
    """Manages instances of :class:`.Procedure`.

    """
    def __post_init__(self):
        self.bean_class = Procedure
        super().__post_init__()

    def get_by_hadm_id(self, hadm_id: int) -> Procedure:
        return self.execute_by_name(
            'select_procedure_by_hadm_id', params=(hadm_id,))


@dataclass
class NoteDocumentStash(ReadOnlyStash):
    """Reads ``noteevents`` from the database and returns parsed documents.

    """
    doc_parser: FeatureDocumentParser = field(default=None)
    """NER+L medical domain natural langauge parser."""

    note_db_persister: DbPersister = field(default=None)
    """Fetches the note text by key from the DB."""

    def load(self, row_id: str) -> FeatureDocument:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'loading row ID {row_id}')
        text = self.note_db_persister.execute_by_name(
            'select_note_text_by_id', params=(row_id,), row_factory='tuple')
        # many notes have trailing newlines, which may cause issues with spaCy
        # or downstream prediction tasks
        return self.doc_parser(text[0][0].strip())

    def keys(self) -> Iterable[str]:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('returning note all DB keys')
        return map(lambda x: str(x[0]),
                   self.note_db_persister.execute_by_name(
                       'select_keys', row_factory='tuple'))

    def exists(self, name: str) -> bool:
        res = self.note_db_persister.execute_by_name(
            'select_hadm_id_by_row_id', params=(name,), row_factory='tuple')
        return len(res) > 0


@dataclass
class NoteEventPersister(DataClassDbPersister):
    """Manages instances of :class:`.NoteEvent`.

    """
    mimic_note_context: Settings = field(default=None)
    """Contains resources needed by new and re-hydrated notes, such as the
    document stash.

    """
    hadm_row_chunk_size: int = field(default=None)
    """The number of note IDs for each round trip to the DB in
    :meth:`get_hadm_ids`.

    """
    def __post_init__(self):
        self.bean_class = NoteEvent
        super().__post_init__()
        self.row_factory = self._create_bean

    def _create_bean(self, *args):
        return NoteEvent(*args, context=self.mimic_note_context)

    @property
    @persisted('_categories', cache_global=True)
    def categories(self) -> Tuple[str]:
        """All unique categories."""
        cats = self.execute_by_name('categories', row_factory='tuple')
        return tuple(map(lambda x: x[0], cats))

    @property
    def _is_sqlite(self) -> bool:
        return isinstance(self.conn_manager, SqliteConnectionManager)

    def get_note_count(self, hadm_id: int) -> int:
        """Return the count of notes for a hospital admission.

        :param hadm_id: the hospital admission ID

        """
        return self.execute_by_name(
            'select_note_count', params=(hadm_id,), row_factory='tuple')[0][0]

    def get_note_counts_by_subject_id(self, subject_id: int) -> \
            Tuple[Tuple[int, int]]:
        """Get counts of notes related to a subject.

        :param subject_id: the patient's ID

        :return: tuple of (``hadm_id``, ``count``) pairs for a subject

        """
        return self.execute_by_name(
            'select_note_count_by_subject_id', params=(subject_id,),
            row_factory='tuple')

    def get_row_ids_with_admissions(self) -> Iterable[int]:
        """Get note IDs associate with at least one admission."""
        return map(int, tuple(chain.from_iterable(
            self.execute_by_name(
                'select_keys_with_adms',
                row_factory='identity'))))

    def get_row_ids_by_hadm_id(self, hadm_id: int) -> Tuple[int]:
        """Return all note row IDs for a admission ID."""
        hadm_ids = tuple(chain.from_iterable(
            self.execute_by_name(
                'select_row_ids_by_hadm_id', params=(hadm_id,),
                row_factory='identity')))
        if self._is_sqlite:
            hadm_ids = tuple(map(int, hadm_ids))
        return hadm_ids

    def get_notes_by_hadm_id(self, hadm_id: int) -> Tuple[NoteEvent]:
        """Return notes by hospital admission ID.

        :param hadm_id: the hospital admission ID

        """
        hadm_ids = self.execute_by_name(
            'select_notes_by_hadm_id', params=(hadm_id,))
        if self._is_sqlite:
            hadm_ids = tuple(map(int, hadm_ids))
        return hadm_ids

    def get_hadm_id(self, row_id: int) -> Optional[int]:
        """Return the hospital admission for a note.

        :param row_id: the unique ID of the note event

        :return: the hospital admission unique ID ``hadm_id`` if ``row_id`` is
                 in the database

        """
        maybe_row: Tuple[int] = self.execute_by_name(
            'select_hadm_id_by_row_id', params=(row_id,),
            row_factory=lambda x: x)
        if len(maybe_row) > 0:
            if self._is_sqlite:
                maybe_row[0] = int(maybe_row[0])
            return maybe_row[0]

    def get_hadm_ids(self, row_ids: Iterable[int]) -> Iterable[int]:
        """Return the hospital admission for a set of note.

        :param row_id: the unique IDs of the note events

        :return: the hospital admission admissions unique ID ``hadm_id``

        """
        def map_chunk(ids: List[int]) -> Tuple[int]:
            return self.execute_by_name(
                sql_name, params=(tuple(ids),), row_factory=lambda x: x)

        def map_chunk_sqlite(ids: List[int]) -> Tuple[int]:
            sql: str = self.sql_entries[sql_name]
            sql = sql.replace('?', f"({','.join(map(str, ids))})")
            return self.execute(sql, row_factory=lambda x: x)

        sql_name: str = 'select_hadm_id_by_row_ids'
        chunk_fn: Callable = map_chunk_sqlite if self._is_sqlite else map_chunk
        id_lsts: Iterable[List[int]] = chunks(row_ids, self.hadm_row_chunk_size)
        return chain.from_iterable(map(chunk_fn, id_lsts))

    def get_hadm_ids_all(self) -> Iterable[int]:
        """Get all hospital admission IDs that have at least one associated
        note.

        """
        ids = self.execute_by_name('select_note_hadm_ids', row_factory='tuple')
        return map(lambda x: x[0], ids)

    def get_notes_by_category(self, category: str,
                              limit: int = sys.maxsize) -> Tuple[NoteEvent]:
        """Return notes by what the category to which they belong.

        :param category: the category of the note (i.e. ``Radiology``)

        :param limit: the limit of notes to return

        """
        return self.execute_by_name(
            'select_notes_by_category', params=(category, limit))

    def get_discharge_reports(self, limit: int = sys.maxsize) -> \
            Tuple[NoteEvent]:
        """Return discharge reports (as apposed to addendums).

        :param limit: the limit of notes to return

        """
        return self.execute_by_name('select_discharge_reports', params=[limit])

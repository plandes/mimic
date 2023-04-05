"""Hospital admission/stay details.

"""
__author__ = 'Paul Landes'

from typing import Tuple, Dict, Iterable, List, Set, Callable
from dataclasses import dataclass, field
import sys
import logging
from functools import reduce
import collections
import itertools as it
from frozendict import frozendict
from io import TextIOBase
import pandas as pd
from zensols.persist import (
    PersistableContainer, persisted,
    Stash, ReadOnlyStash, FactoryStash, DirectoryStash,
)
from zensols.config import Dictable, ConfigFactory, Settings
from zensols.multi import MultiProcessFactoryStash
from . import (
    Admission, Patient, Diagnosis, Procedure, NoteEvent,
    DiagnosisPersister, ProcedurePersister, PatientPersister,
    NoteEventPersister, AdmissionPersister, Note, NoteFactory,
)

logger = logging.getLogger(__name__)


@dataclass
class HospitalAdmission(PersistableContainer, Dictable):
    """Represents data collected by a patient over the course of their hospital
    admission.

    """
    _DICTABLE_ATTRIBUTES = 'hadm_id notes'.split()

    admission: Admission = field()
    """The admission of the admission."""

    patient: Patient = field()
    """The patient/subject."""

    diagnoses: Tuple[Diagnosis] = field()
    """The ICD-9 diagnoses of the hospital admission."""

    procedures: Tuple[Procedure] = field()
    """The ICD-9 procedures of the hospital admission."""

    notes: Tuple[Note] = field()
    """The notes by the care givers."""

    def __post_init__(self):
        super().__init__()

    @property
    def hadm_id(self) -> int:
        return self.admission.hadm_id

    @property
    @persisted('_by_category', transient=True)
    def notes_by_category(self) -> Dict[str, Tuple[Note]]:
        """All notes by :obj:`.Note.category` as keys with the list of
        resepctive notes as a list as values.

        """
        notes = collections.defaultdict(list)
        for note in self.notes:
            notes[note.category].append(note)
        return frozendict({k: tuple(notes[k]) for k in notes.keys()})

    @property
    @persisted('_by_id', transient=True)
    def notes_by_id(self) -> Dict[int, Note]:
        """Get a note by its ``row_id``."""
        return frozendict({f.row_id: f for f in self.notes})

    def get_duplicate_notes(self, text_start: int = None) -> Tuple[Set[str]]:
        """Notes with the same note text, each in their respective set.

        :param text_start: the number of first N characters used to compare
                           notes, or the entire note text if ``None``

        :return: the duplicate note``row_id``, or if there are no duplicates,
                 an empty tuple

        """
        dups = collections.defaultdict(set)
        note: Note
        for note in self.notes:
            key = note.text
            if text_start is not None:
                key = key[:text_start]
            dups[key].add(note.row_id)
        return tuple(map(lambda x: x[1], filter(
            lambda x: len(x[1]) > 1, dups.items())))

    def get_non_duplicate_notes(self, dup_sets: Tuple[Set[str]],
                                filter_fn: Callable = None) -> \
            Tuple[Tuple[Note, bool]]:
        """Return non-duplicated notes.

        :param dup_sets: the duplicate sets generated from
                         :meth:`get_duplicate_notes`

        :param filer_fn: if provided it is used to filter duplicates; if
                         everything is filtered, a note from the respective
                         duplicate set is chosen at random

        :return: a tuple of ``(<note>, <is duplicate>)`` pairs

        :see: :obj:`duplicate_notes`

        """
        def filter_ans(n: Note) -> bool:
            if n.row_id in ds:
                if filter_fn is not None:
                    return filter_fn(n)
                return True
            else:
                return False

        notes: Tuple[Note] = self.notes
        nid: Dict[int, Note] = self.notes_by_id
        dups: Set[str] = reduce(lambda x, y: x | y, dup_sets)
        # initialize with the notes not in any duplicate group, which are
        # non-duplicates
        non_dups: List[Note] = list(
            map(lambda x: (x, False),
                filter(lambda n: n.row_id not in dups, notes)))
        ds: Set[str]
        for ds in dup_sets:
            note: Note
            maybe_an: Note = tuple(filter(filter_ans, notes))
            if len(maybe_an) > 0:
                # if filter_fn is used, it returns preferred notes to use
                note = maybe_an[0]
            else:
                # if there is no preference (all filtered) pick a random
                note = nid[next(iter(ds))]
            non_dups.append((note, True))
        return tuple(non_dups)

    @property
    def feature_dataframe(self) -> pd.DataFrame:
        """The feature dataframe for the hospital admission as the constituent
        note feature dataframes.

        """
        dfs: List[pd.DataFrame] = []
        by_cat = self.notes_by_category
        for note_key in sorted(by_cat.keys()):
            for note in by_cat[note_key]:
                df = note.feature_dataframe
                df = df[df['ent_type_'] == 'mc']
                df['hadm_id'] = self.hadm_id
                first = 'hadm_id section'.split()
                new_cols = list(filter(lambda c: c not in first, df.columns))
                new_cols = first + new_cols
                dfs.append(df[new_cols])
        return pd.concat(dfs)

    def write_notes(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                    note_limit: int = sys.maxsize,
                    categories: Set[str] = None,
                    include_note_id: bool = False,
                    **note_kwargs):
        """Write the notes of the admission.

        :param note_limit: the number of notes to write

        :param include_note_id: whether to include the note identification info

        :param categories: the note categories to write

        :param note_kwargs: the keyword arguments gtiven to
                            :meth:`.Note.write_full`

        """
        notes = self.notes
        if categories is not None:
            notes = filter(lambda c: c.category in categories, notes)
        note: Note
        for note in it.islice(notes, note_limit):
            if include_note_id:
                self._write_line(f'row_id: {note.row_id} ({note.category})',
                                 depth, writer)
                note.write_full(depth, writer, **note_kwargs)
            else:
                note.write_full(depth, writer, **note_kwargs)

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout,
              include_admission: bool = False,
              include_patient: bool = False,
              include_diagnoses: bool = False,
              include_procedures: bool = False,
              **note_kwargs):
        """Write the admission and the notes of the admission.

        :param note_kwargs: the keyword arguments gtiven to
                            :meth:`.Note.write_full`

        """
        nkwargs = dict(note_line_limit=0,
                       section_line_limit=0,
                       include_fields=False,
                       include_section_divider=False,
                       include_note_divider=False,
                       include_section_header=False,
                       include_note_id=True)
        nkwargs.update(note_kwargs)
        self._write_line(f'hadm_id: {self.admission.hadm_id}', depth, writer)
        if include_admission:
            self._write_line('admission:', depth + 1, writer)
            self._write_object(self.admission, depth + 2, writer)
        if include_patient:
            self._write_line('patient:', depth + 1, writer)
            self._write_object(self.patient, depth + 2, writer)
        if include_diagnoses:
            self._write_line('diagnoses:', depth + 1, writer)
            self._write_object(self.diagnoses, depth + 2, writer)
        if include_procedures:
            self._write_line('procedures:', depth + 1, writer)
            self._write_object(self.procedures, depth + 2, writer)
        if 'note_limit' not in nkwargs or nkwargs['note_limit'] > 0:
            self._write_line('notes:', depth + 1, writer)
            self.write_notes(depth + 2, writer, **nkwargs)

    def write_full(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                   **kwargs):
        """Write a verbose output of the admission.

        :param kwargs: the keyword arguments given to meth:`write`

        """
        wkwargs = dict(note_line_limit=sys.maxsize,
                       section_line_limit=sys.maxsize,
                       include_fields=True,
                       include_section_divider=True,
                       include_note_divider=True,
                       include_section_header=True,
                       include_note_id=False,
                       include_admission=True,
                       include_patient=True,
                       include_diagnoses=True,
                       include_procedures=True)
        wkwargs.update(kwargs)
        self.write(depth, writer, **wkwargs)

    def __getitem__(self, row_id: int):
        return self.notes_by_id[row_id]

    def __contains__(self, row_id: int):
        return row_id in self.notes_by_id

    def __iter__(self) -> Iterable[Note]:
        return iter(self.notes)

    def __str__(self):
        return (f'subject: {self.admission.subject_id}, ' +
                f'hadm: {self.admission.hadm_id}, ' +
                f'num notes: {len(self.notes)}')


@dataclass
class HospitalAdmissionDbStash(ReadOnlyStash):
    """A stash that creates :class:`.HospitalAdmission` instances.  This
    instance is used by caching stashes per the default resource library
    configuration for this package.

    """
    config_factory: ConfigFactory = field()
    """The factory used to create domain objects (ie hospital admission).

    """
    mimic_note_factory: NoteFactory = field()
    """The factory that creates :class:`.Note` for hopsital admissions."""

    admission_persister: AdmissionPersister = field()
    """The persister for the ``admissions`` table."""

    diagnosis_persister: DiagnosisPersister = field()
    """The persister for the ``diagnosis`` table."""

    patient_persister: PatientPersister = field()
    """The persister for the ``patients`` table."""

    procedure_persister: ProcedurePersister = field()
    """The persister for the ``procedure`` table."""

    note_event_persister: NoteEventPersister = field()
    """The persister for the ``noteevents`` table."""

    hospital_adm_name: str = field()
    """The configuration section name of the :class:`.HospitalAdmission` used to
    load instances.

    """
    def __post_init__(self):
        super().__post_init__()
        self.strict = True

    def load(self, hadm_id: str) -> HospitalAdmission:
        """Create a *complete picture* of a hospital stay with admission,
        patient and notes data.

        :param hadm_id: the ID that specifics the hospital admission to create

        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'loading hospital admission: {hadm_id}')
        hadm_id = int(hadm_id)
        dp: DiagnosisPersister = self.diagnosis_persister
        pp: ProcedurePersister = self.procedure_persister
        adm: Admission = self.admission_persister.get_by_hadm_id(hadm_id)
        pat: Patient = self.patient_persister.get_by_subject_id(adm.subject_id)
        diag: Tuple[Diagnosis] = dp.get_by_hadm_id(hadm_id)
        procds: Tuple[Procedure] = pp.get_by_hadm_id(hadm_id)
        note_events: Tuple[NoteEvent] = self.note_event_persister.\
            get_notes_by_hadm_id(hadm_id)
        notes = tuple(map(self.mimic_note_factory, note_events))
        return self.config_factory.new_instance(
            self.hospital_adm_name, adm, pat, diag, procds, notes)

    @persisted('_keys', cache_global=True)
    def keys(self) -> Iterable[str]:
        return tuple(self.admission_persister.get_keys())

    def exists(self, hadm_id: str) -> bool:
        return self.admission_persister.exists(int(hadm_id))


@dataclass
class NoteDocumentPreemptiveStash(MultiProcessFactoryStash):
    """Contains the stash that caches feature docs and some delegate of
    :class:`.NoteDocumentStash`, same as that in :class:`.NoteEventPersister`.
    It also processes many note events at a time using sub processes using
    :meth:`process_keys`.

    """
    def process_keys(self, hadm_ids: Iterable[str]):
        """Invoke the multi-processing system to preemptively parse and store
        all hospital admissions and subordinate note events for the IDs
        provided.

        :param hadm_ids: the admission IDs to parse and cache

        """
        self._hadm_ids = set(map(str, hadm_ids))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'processing {len(hadm_ids)} up to notes')
        self.prime()

    def _create_data(self) -> Iterable[HospitalAdmission]:
        assert isinstance(self.delegate, DirectoryStash)
        dir_keys = set(self.delegate.keys())
        keys = self._hadm_ids - dir_keys
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'directory keys: {len(dir_keys)}')
            logger.debug(f'keys to process: {len(keys)}')
        return keys


@dataclass
class HospitalAdmissionDbFactoryStash(FactoryStash):
    """A factory stash that adds back the :obj:`doc_stash` for
    :class:`.NoteEvent` instances so they can parse the MIMIC-III English text
    as :class:`.FeatureDocument` instances.

    """
    doc_stash: Stash = field(default=None)
    """Contains the document that map to :obj:`row_id`."""

    preempt_stash: NoteDocumentPreemptiveStash = field(default=None)
    """A stash that processes many note events at a time."""

    mimic_note_context: Settings = field(default=None)
    """Contains resources needed by new and re-hydrated notes, such as the
    document stash.

    """
    def _populate_note(self, note: Note):
        """Add back the stash that allows the note to parse English text."""
        note._trans_context = self.mimic_note_context

    def _populate_hadm(self, hadm: HospitalAdmission):
        """Populate notes of the admission with in memory resources.

        :see: :meth:`_populate_note`

        """
        note: Note
        for note in hadm.notes:
            self._populate_note(note)

    def process_keys(self, hadm_ids: Iterable[str]):
        """Invoke the multi-processing system to preemptively parse and store
        all hospital admissions and subordinate note events for the IDs
        provided.

        :param hadm_ids: the admission IDs to parse and cache

        :see: :class:`.NoteDocumentPreemptiveStash`

        """
        row_ids = set()
        for hadm_id in hadm_ids:
            hadm: HospitalAdmission = self[hadm_id]
            row_ids.update(map(lambda n: n.row_id, hadm.notes))
        self.preempt_stash.process_keys(tuple(row_ids))

    def load(self, hadm_id: str) -> HospitalAdmission:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'loading hospital admission: {hadm_id}')
        hadm: HospitalAdmission = super().load(hadm_id)
        if hadm is not None:
            self._populate_hadm(hadm)
        return hadm

    def clear(self):
        super().clear()

    def clear_all(self, include_admissions: bool = True,
                  include_notes: bool = True):
        """Clear the admission and/or the notes cached data.

        """
        if include_admissions:
            self.clear()
        if include_notes:
            self.doc_stash.clear()
            self.preempt_stash.clear()

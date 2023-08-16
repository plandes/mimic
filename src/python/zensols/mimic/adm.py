"""Hospital admission/stay details.

"""
__author__ = 'Paul Landes'

from typing import Tuple, Dict, Iterable, List, Set, Callable, ClassVar, Any
from dataclasses import dataclass, field
import sys
import os
import logging
from functools import reduce
import collections
import itertools as it
from frozendict import frozendict
from io import TextIOBase
import pandas as pd
from zensols.persist import (
    PersistableContainer, persisted, Primeable, Stash,
    ReadOnlyStash, FactoryStash, KeySubsetStash,
)
from zensols.config import Dictable, ConfigFactory, Settings
from zensols.multi import MultiProcessStash
from zensols.db import BeanStash
from . import (
    RecordNotFoundError, Admission, Patient, Diagnosis, Procedure, NoteEvent,
    DiagnosisPersister, ProcedurePersister, PatientPersister,
    NoteEventPersister, AdmissionPersister, Note, NoteFactory,
)

logger = logging.getLogger(__name__)


@dataclass
class HospitalAdmission(PersistableContainer, Dictable):
    """Represents data collected by a patient over the course of their hospital
    admission.  Note: this object keys notes using their ``row_id`` IDs used in
    the MIMIC dataset as integers and not strings like some note stashes.

    """
    _DICTABLE_ATTRIBUTES: ClassVar[List[str]] = 'hadm_id'.split()
    _PERSITABLE_TRANSIENT_ATTRIBUTES: ClassVar[Set[str]] = {'_note_stash'}

    admission: Admission = field()
    """The admission of the admission."""

    patient: Patient = field()
    """The patient/subject."""

    diagnoses: Tuple[Diagnosis] = field()
    """The ICD-9 diagnoses of the hospital admission."""

    procedures: Tuple[Procedure] = field()
    """The ICD-9 procedures of the hospital admission."""

    def __post_init__(self):
        super().__init__()

    def _init(self, note_stash: Stash):
        self._note_stash = note_stash

    @property
    def hadm_id(self) -> int:
        """The hospital admission unique identifier."""
        return self.admission.hadm_id

    @property
    def notes(self) -> Iterable[Note]:
        """The notes by the care givers."""
        return iter(self._note_stash.values())

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

    def keys(self) -> Iterable[int]:
        return map(int, self._note_stash.keys())

    def __getitem__(self, row_id: int):
        return self._note_stash[str(row_id)]

    def __contains__(self, row_id: int):
        return str(row_id) in self.notes_by_id

    def __iter__(self) -> Iterable[Note]:
        return iter(self._note_stash.values())

    def __len__(self) -> int:
        return len(self._note_stash)

    def __str__(self):
        return (f'subject: {self.admission.subject_id}, ' +
                f'hadm: {self.admission.hadm_id}, ' +
                f'num notes: {len(self)}')


@dataclass
class _NoteBeanStash(BeanStash):
    """Adapts the :class:`.NoteEventPersister` to a
    :class:`~zensols.persist.domain.Stash`.

    """
    mimic_note_factory: NoteFactory = field()
    """The factory that creates :class:`.Note` for hopsital admissions."""

    def load(self, row_id: str) -> Note:
        note_event: NoteEvent = super().load(row_id)
        if note_event is not None:
            logger.debug(f'creating note from {note_event}')
            return self.mimic_note_factory.create(note_event)


@dataclass
class _NoteFactoryStash(FactoryStash):
    """Creates instances of :class:`.Note`.

    """
    mimic_note_context: Settings = field(default=None)
    """Contains resources needed by new and re-hydrated notes, such as the
    document stash.

    """
    def load(self, row_id: str) -> Note:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'loading note: {row_id}')
        note: Note = super().load(row_id)
        if note is not None:
            logger.debug(f'setting note context on {row_id}')
            note._trans_context = self.mimic_note_context
        return note


@dataclass
class HospitalAdmissionDbStash(ReadOnlyStash, Primeable):
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

    note_stash: Stash = field()
    """Creates cached instances of :class:`.Note`."""

    hospital_adm_name: str = field()
    """The configuration section name of the :class:`.HospitalAdmission` used to
    load instances.

    """
    def __post_init__(self):
        super().__post_init__()
        self.strict = True

    def _create_note_stash(self, adm: Admission):
        np: NoteEventPersister = self.note_event_persister
        row_ids: Tuple[int] = np.get_row_ids_by_hadm_id(adm.hadm_id)
        return KeySubsetStash(
            delegate=self.note_stash,
            key_subset=set(map(str, row_ids)),
            dynamic_subset=False)

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
        note_stash: Stash = self._create_note_stash(adm)
        adm: HospitalAdmission = self.config_factory.new_instance(
            self.hospital_adm_name, adm, pat, diag, procds)
        adm._init(note_stash)
        return adm

    @persisted('_keys', cache_global=True)
    def keys(self) -> Iterable[str]:
        return tuple(self.admission_persister.get_keys())

    def exists(self, hadm_id: str) -> bool:
        return self.admission_persister.exists(int(hadm_id))

    def prime(self):
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'priming {type(self)}...')
        self.mimic_note_factory.prime()
        super().prime()


@dataclass
class HospitalAdmissionDbFactoryStash(FactoryStash, Primeable):
    """A factory stash that configures :class:`.NoteEvent` instances so they can
    parse the MIMIC-III English text as :class:`.FeatureDocument` instances.

    """
    doc_stash: Stash = field(default=None)
    """Contains the document that map to :obj:`row_id`."""

    mimic_note_context: Settings = field(default=None)
    """Contains resources needed by new and re-hydrated notes, such as the
    document stash.

    """
    def load(self, hadm_id: str) -> HospitalAdmission:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'loading hospital admission: {hadm_id}')
        adm: HospitalAdmission = super().load(hadm_id)
        db_stash: HospitalAdmissionDbStash = self.factory
        adm._init(db_stash._create_note_stash(adm))
        return adm

    def clear(self,):
        # admission cached (i.e. data/adm)
        super().clear()
        # parsed docs (i.e. data/note-doc)
        self.doc_stash.clear()
        # note containers with sections (i.e. data/note-cont)
        self.factory.note_stash.delegate.clear()

    def prime(self):
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'priming {type(self)}...')
        self.factory.prime()
        super().prime()


@dataclass
class NoteDocumentPreemptiveStash(MultiProcessStash):
    """Contains the stash that preemptively creates :class:`.Admission`,
    :class:`.Note` and :class:`~zensols.nlp.container.FeatureDocument` cache
    files.  This class is not useful for returning any data (see
    :class:`.HospitalAdmissionDbFactoryStash).

    """
    note_event_persister: NoteEventPersister = field()
    """The persister for the ``noteevents`` table."""

    adm_factory_stash: HospitalAdmissionDbFactoryStash = field()
    """The factory to create the admission instances."""

    def __post_init__(self):
        super().__post_init__()
        self._row_ids: Tuple[str] = None

    def _create_data(self) -> Iterable[HospitalAdmission]:
        keys: Set[str] = self._row_ids
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'keys to process: {len(keys)}')
        return keys

    def _process(self, chunk: List[Any]) -> Iterable[Tuple[str, Any]]:
        np: NoteEventPersister = self.note_event_persister
        # for each row ID get the note throught the admission so sections are
        # created per the implementation specified in the configuration
        row_id: str
        for row_id in chunk:
            if logger.isEnabledFor(logging.DEBUG):
                pid = os.getpid()
                self._debug(f'processing key {row_id} in {pid}')
            hadm_id: int = np.get_hadm_id(int(row_id))
            adm: HospitalAdmission = self.adm_factory_stash[hadm_id]
            note: Note = adm[row_id]
            # force document parse
            note.doc
            # it doesn't matter what we return becuase it won't be used, so
            # return the note's debugging string
            yield (row_id, str(note))

    def _get_existing_note_row_ids(self) -> Set[str]:
        """Return the note row_ids that both have container and feature doc
        cached ID files.

        """
        existing_note_cont_ids: Set[str] = set(
            self.adm_factory_stash.factory.note_stash.delegate.keys())
        existing_doc_ids: Set[str] = set(
            self.adm_factory_stash.doc_stash.delegate.keys())
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'already cached: doc={len(existing_doc_ids)}, ' +
                        f'container={len(existing_note_cont_ids)}')
        return existing_note_cont_ids & existing_doc_ids

    def prime(self):
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'priming {type(self)}...')
        # this leads to priming the stash that installs the MedSecId in the
        # mimicsid package
        self.adm_factory_stash.prime()
        np: NoteEventPersister = self.note_event_persister
        # get the IDs we already have create previously
        existing_row_ids: Set[str] = self._get_existing_note_row_ids()
        # create a list of those row IDs we still need to create
        to_create_row_ids: Set[str] = self._row_ids - existing_row_ids
        # populate admissions that have at least one missing note
        hadm_ids: Set[int] = set()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'need: {self._row_ids}, ' +
                         f'existing: {existing_row_ids}, ' +
                         f'create: {to_create_row_ids}')
        row_id: str
        for row_id in to_create_row_ids:
            hadm_id: int = np.get_hadm_id(row_id)
            if hadm_id is None:
                raise RecordNotFoundError(self, 'row_id', row_id)
            hadm_ids.add(hadm_id)
        # first create the admissions to processes overwrite, only then can
        # notes be dervied from admissions and written across procs
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'creating {len(hadm_ids)} cached admissions')
        hadm_id: int
        for hadm_id in hadm_ids:
            adm: HospitalAdmission = self.adm_factory_stash[hadm_id]
            assert isinstance(adm, HospitalAdmission)
        # don't fork processes only to find the work is already complete
        if len(hadm_ids) == 0:
            if logger.isEnabledFor(logging.INFO):
                logger.info('no note docs to create')
        else:
            if logger.isEnabledFor(logging.INFO):
                logger.info(f'creating {len(to_create_row_ids)} note docs')
            super().prime()

    def process_keys(self, row_ids: Iterable[str], workers: int = None,
                     chunk_size: int = None):
        """Invoke the multi-processing system to preemptively parse and store
        note events for the IDs provided.

        :param row_ids: the admission IDs to parse and cache

        :param workers: the number of processes spawned to accomplish the work

        :param chunk_size: the size of each group of data sent to the child
                           process to be handled

        :see: :class:`~zensols.persist.multi.stash.MultiProcessStash`

        """
        if workers is not None:
            self.workers = workers
        if chunk_size is not None:
            self.chunk_size = chunk_size
        self._row_ids = set(row_ids)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'processing {len(row_ids)} notes')
        self.prime()

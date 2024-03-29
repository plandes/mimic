"""Discharge summary research and Mimic III data exploration.

"""
__author__ = 'Paul Landes'

from dataclasses import dataclass, field
import logging
import sys
from pathlib import Path
from io import TextIOBase
from zensols.config import Dictable, ConfigFactory
from . import (
    RecordNotFoundError, HospitalAdmission, HospitalAdmissionDbStash,
    PatientPersister, AdmissionPersister, DiagnosisPersister,
    NoteEventPersister, Note,
)

logger = logging.getLogger(__name__)


@dataclass
class Corpus(Dictable):
    """A container class provided access to the MIMIC-III dataset using a
    relational database (by default Postgress per the resource library
    configuration).  It also has methods to dump corpus statistics.

    :see: `Resource Libraries <https://plandes.github.io/util/doc/config.html#resource-libraries>`_

    """
    config_factory: ConfigFactory = field()
    """Used to clear the note event cache."""

    patient_persister: PatientPersister = field()
    """The persister for the ``patients`` table."""

    admission_persister: AdmissionPersister = field()
    """The persister for the ``admissions`` table."""

    diagnosis_persister: DiagnosisPersister = field()
    """The persister for the ``diagnosis`` table."""

    note_event_persister: NoteEventPersister = field()
    """The persister for the ``noteevents`` table."""

    hospital_adm_stash: HospitalAdmissionDbStash = field()
    """Creates hospital admission instances.  Note that this might be a caching
    stash instance, but method calls are delegated through to the instance of
    :class:`.HospitalAdmissionDbStash`.

    """
    temporary_results_dir: Path = field()
    """The path to create the output results.  This is not used, but needs to
    stay until the next :mod:`zensols.mimicsid` is retrained."""

    def __post_init__(self):
        # allow pass through method delegation from any configured cache
        # stashes on to the HospitalAdmissionDbStash such as `process_keys`
        self.hospital_adm_stash.delegate_attr = True

    def clear(self, include_notes: bool = True):
        """Clear the all cached admission and note parses.

        :param include_notes: whether to also clear the parsed notes cache

        """
        self.hospital_adm_stash.clear()
        if include_notes:
            # the note event cache stash used by :meth:`clear` to remove cached
            # parsed files
            self.config_factory('mimic_note_event_persister_stash').clear()
            self.config_factory('mimic_hospital_adm_factory_stash').clear()

    def get_hospital_adm_by_id(self, hadm_id: int) -> HospitalAdmission:
        """Return a hospital admission by its unique identifier."""
        return self.hospital_adm_stash[str(hadm_id)]

    def get_hospital_adm_for_note(self, row_id: int) -> HospitalAdmission:
        """Return an admission that has note ``row_id``.

        :raise: RecordNotFoundError if ``row_id`` is not found in the database

        """
        hadm_id: int = self.note_event_persister.get_hadm_id(row_id)
        if hadm_id is None:
            raise RecordNotFoundError(self, 'hadm_id', hadm_id)
        return self.hospital_adm_stash[str(hadm_id)]

    def get_note_by_id(self, row_id: int) -> Note:
        """Return the note (via the hospital admission) for ``row_id``.

        :raise: RecordNotFoundError if ``row_id`` is not found in the database

        """
        return self.get_hospital_adm_for_note(row_id)[row_id]

    def write_note_event_counts(self, subject_id: int, depth: int = 0,
                                writer: TextIOBase = sys.stdout):
        """Print a list of hospital admissions by count of related notes in
        descending order.

        :see: :meth:`.NoteEventPersister.get_note_counts_by_subject_id`

        """
        np: NoteEventPersister = self.note_event_persister
        for hadm_id, count in np.get_note_counts_by_subject_id(subject_id):
            self._write_line(f'{hadm_id}: {count}', depth, writer)

    def write_hosptial_count_admission(self, depth: int = 0,
                                       writer: TextIOBase = sys.stdout,
                                       limit: int = sys.maxsize):
        """Write the counts for each hospital admission.

        :param limit: the limit on the return admission counts

        :see: :meth:`.AdmissionPersister.get_admission_admission_counts`

        """
        for i in self.admission_persister.get_admission_admission_counts(limit):
            self._write_line(str(i), depth, writer)

    def write_hospital_admission(self, hadm_id: int, depth: int = 0,
                                 writer: TextIOBase = sys.stdout,
                                 note_line_limit: int = sys.maxsize):
        """Write the hospital admission identified by ``hadm_id``.

        """
        fac: HospitalAdmissionDbStash = self.hospital_adm_stash
        hadm: HospitalAdmission = fac.get(hadm_id)
        hadm.write(depth, writer, note_line_limit=note_line_limit)

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        n_notes: int = self.note_event_persister.get_count()
        n_adms: int = self.admission_persister.get_count()
        n_patients: int = self.patient_persister.get_count()
        self._write_line(f'patients: {n_patients:,}', depth, writer)
        self._write_line(f'admissions: {n_adms:,}', depth, writer)
        self._write_line(f'notes: {n_notes:,}', depth, writer)

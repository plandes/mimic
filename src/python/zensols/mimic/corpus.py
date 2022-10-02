"""Discharge summary research and Mimic III data exploration.

"""
__author__ = 'Paul Landes'

from typing import Tuple
from dataclasses import dataclass, field
import logging
import sys
import re
from pathlib import Path
import shutil
from io import TextIOBase
from zensols.config import Dictable
from . import (
    NoteEvent, HospitalAdmission, HospitalAdmissionDbStash,
    PatientPersister, AdmissionPersister, DiagnosisPersister,
    NoteEventPersister,
)

logger = logging.getLogger(__name__)


@dataclass
class Corpus(Dictable):
    """A container class provided access to the MIMIC-III dataset using a
    relational database (by default Postgress per the resource library
    configuration).  It also has methods to dump corpus statistics.

    :see: `Resource Libraries <https://plandes.github.io/util/doc/config.html#resource-libraries>`_

    """
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
    """The path to create the output results."""

    def __post_init__(self):
        # allow pass through method delegation from any configured cache
        # stashes on to the HospitalAdmissionDbStash such as `process_keys`
        self.hospital_adm_stash.delegate_attr = True

    def clear(self):
        """Clear the all cached admission and note parses."""
        self.hospital_adm_stash.clear()

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

    def write_note_event_by_categories(self, note_limit: int = 10):
        """Write a certain number of notes across each category to directory
        :obj:`temporary_results_dir`.  Each notes file is named by the
        ``hadm_id`` field.

        :param note_limit: the number of notes to write for each category.

        """
        np: NoteEventPersister = self.note_event_persister
        tmpdir: Path = self.temporary_results_dir / 'by_category'
        if tmpdir.exists():
            shutil.rmtree(tmpdir)
        tmpdir.mkdir(parents=True, exist_ok=True)
        cat: str
        ntevt_cnt = 0
        for i, cat in enumerate(self.note_event_persister.categories):
            ntevts: Tuple[NoteEvent] = np.get_notes_by_category(cat, note_limit)
            name = re.sub(r'[ \t/_-]+', '-', cat).lower()
            if name.endswith('-'):
                name = name[0:-1]
            for ntevt in ntevts:
                path = tmpdir / f'{name}-{ntevt.hadm_id}.txt'
                with open(path, 'w') as f:
                    ntevt.write(writer=f)
                if logger.isEnabledFor(logging.INFO):
                    logger.info(f'wrote {len(ntevts)} ntevts to {path}')
            ntevt_cnt += len(ntevts)
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'wrote {ntevt_cnt} ntevts')

    def write_discharge_reports(self, note_limit: int = 10):
        """Format and write a certain number of discharge notes to the file
        system.  These are written to the path configured with
        :obj:`temporary_results_dir` in subdirectory ``discharge-reports``.

        :param note_limit: the numbe

        """
        np: NoteEventPersister = self.note_event_persister
        tmpdir: Path = self.temporary_results_dir / 'discharge-reports'
        if tmpdir.exists():
            shutil.rmtree(tmpdir)
        tmpdir.mkdir(parents=True, exist_ok=True)
        notes: Tuple[NoteEvent] = np.get_discharge_reports(note_limit)
        for note in notes:
            path = tmpdir / f'{note.hadm_id}.txt'
            with open(path, 'w') as f:
                note.write(writer=f)
        if logger.isEnabledFor(logging.INFO):
            logger.info(f'wrote {len(notes)} notes to {tmpdir}')

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        n_notes: int = self.note_event_persister.get_count()
        n_adms: int = self.admission_persister.get_count()
        n_patients: int = self.patient_persister.get_count()
        self._write_line(f'patients: {n_patients:,}', depth, writer)
        self._write_line(f'admissions: {n_adms:,}', depth, writer)
        self._write_line(f'notes: {n_notes:,}', depth, writer)

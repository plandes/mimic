"""Domain classes for the corpus notes.

"""
__author__ = 'Paul Landes'

from typing import Dict, Any, Type, ClassVar, Set
from dataclasses import dataclass, field, InitVar
import sys
import re
from datetime import datetime
from io import TextIOBase
from zensols.util import APIError
from zensols.config import Dictable, Settings
from zensols.persist import PersistableContainer, persisted, Stash
from zensols.nlp import FeatureDocument


class MimicError(APIError):
    """Raised for any application level error."""
    pass


class RecordNotFoundError(MimicError):
    """Raised on any domain/container class error."""
    def __init__(self, actor: Type, key_type: str, key: int):
        actor = actor.__class__.__name__
        super().__init__(f'Actor {actor} could not find {key_type} ID {key}')


class MimicParseError(MimicError):
    """Raised for MIMIC note parsing errors."""
    def __init__(self, text: str):
        self.text = text
        trunc = 50
        if len(text) > trunc:
            text = text[0:trunc] + '...'
        super().__init__(f'Could not parse: <{text}>')


@dataclass
class MimicContainer(PersistableContainer, Dictable):
    """Abstract base class for data containers, which are plain old Python
    objects that are CRUD'd from DAO persisters.

    """
    row_id: int = field()
    """Unique row identifier."""

    def __post_init__(self):
        super().__init__()
        if self.row_id is None:
            raise RecordNotFoundError(self, 'row id', self.row_id)

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout,
              dct: Dict[str, Any] = None):
        if dct is None:
            dct = self.asdict()
        del dct['row_id']
        self._write_line(f'row_id: {self.row_id}', depth, writer)
        self._write_object(dct, depth + 1, writer)


@dataclass
class Admission(MimicContainer):
    """The ADMISSIONS table gives information regarding a patient’s admission to
    the hospital. Since each unique hospital visit for a patient is assigned a
    unique HADM_ID, the ADMISSIONS table can be considered as a definition
    table for HADM_ID. Information available includes timing information for
    admission and discharge, demographic information, the source of the
    admission, and so on.

    Table source: Hospital database.

    Table purpose: Define a patient’s hospital admission, HADM_ID.

    Number of rows: 58976

    Links to:
      * PATIENTS on SUBJECT_ID

    :see: `Dictionary <https://mimic.physionet.org/mimictables/admissions/>`_

    """
    subject_id: int = field()
    """Foreign key. Identifies the patient."""

    hadm_id: int = field()
    """Primary key. Identifies the hospital admission."""

    admittime: datetime = field()
    """Time of admission to the hospital."""

    dischtime: datetime = field()
    """Time of discharge from the hospital."""

    deathtime: datetime = field()
    """Time of death."""

    admission_type: str = field()
    """Type of admission, for example emergency or elective."""

    admission_location: str = field()
    """Admission location."""

    discharge_location: str = field()
    """Discharge location"""

    insurance: str = field()
    """The INSURANCE, LANGUAGE, RELIGION, MARITAL_STATUS, ETHNICITY columns
    describe patient demographics. These columns occur in the ADMISSIONS table
    as they are originally sourced from the admission, discharge, and transfers
    (ADT) data from the hospital database. The values occasionally change
    between hospital admissions (HADM_ID) for a single patient
    (SUBJECT_ID). This is reasonable for some fields (e.g. MARITAL_STATUS,
    RELIGION), but less reasonable for others (e.g. ETHNICITY).

    """
    language: str = field()
    """See :obj:`insurance`."""

    religion: str = field()
    """See :obj:`insurance`."""

    marital_status: str = field()
    """See :obj:`insurance`."""

    ethnicity: str = field()
    """See :obj:`insurance`."""

    edregtime: datetime = field()
    """Time that the patient was registered and discharged from the emergency
    department.

    """
    edouttime: datetime = field()
    """See :obj:`edregtime`."""

    diagnosis: str = field()
    """The DIAGNOSIS column provides a preliminary, free text diagnosis for the
    patient on hospital admission. The diagnosis is usually assigned by the
    admitting clinician and does not use a systematic ontology. As of MIMIC-III
    v1.0 there were 15,693 distinct diagnoses for 58,976 admissions. The
    diagnoses can be very informative (e.g. chronic kidney failure) or quite
    vague (e.g. weakness). Final diagnoses for a patient’s hospital stay are
    coded on discharge and can be found in the DIAGNOSES_ICD table. While this
    field can provide information about the status of a patient on hospital
    admission, it is not recommended to use it to stratify patients.

    """
    hospital_expire_flag: int = field()
    """This indicates whether the patient died within the given
    hospitalization. 1 indicates death in the hospital, and 0 indicates survival
    to hospital discharge.

    """
    has_chartevents_data: int = field()
    """Hospital admission has at least one observation in the CHARTEVENTS table.

    """


@dataclass
class Patient(MimicContainer):
    """Table source: CareVue and Metavision ICU databases.

    Table purpose: Defines each SUBJECT_ID in the database, i.e. defines a
    single patient.

    Number of rows: 46,520

    Links to:
    ADMISSIONS on SUBJECT_ID
    ICUSTAYS on SUBJECT_ID

    """

    row_id: int = field()
    """Unique row identifier."""

    subject_id: int = field()
    """Primary key. Identifies the patient."""

    gender: str = field()
    """Gender (one character: ``M``/``F``)."""

    dob: datetime = field()
    """Date of birth."""

    dod: datetime = field()
    """Date of death. Null if the patient was alive at least 90 days post
    hospital discharge.

    """

    dod_hosp: datetime = field()
    """Date of death recorded in the hospital records."""

    dod_ssn: datetime = field()
    """Date of death recorded in the social security records."""

    expire_flag: int = field()
    """Flag indicating that the patient has died."""


@dataclass
class HospitalAdmissionContainer(MimicContainer):
    """Any data container that has a unique identifier with an (inpatient)
    non-null identifier.

    """
    hadm_id: int = field()
    """Primary key. Identifies the hospital admission."""


@dataclass
class ICD9Container(MimicContainer):
    """A data container that has ICD-9 codes.
    """
    icd9_code: str = field()
    """ICD9 code for the diagnosis or procedure."""

    short_title: str = field()
    """Short title associated with the code."""

    long_title: str = field()
    """Long title associated with the code."""


@dataclass
class Diagnosis(ICD9Container):
    """Table source: Hospital database.

    Table purpose: Contains ICD diagnoses for patients, most notably ICD-9
    diagnoses.

    Number of rows: 651,047

    Links to:

    PATIENTS on SUBJECT_ID
    ADMISSIONS on HADM_ID
    D_ICD_DIAGNOSES on ICD9_CODE

    """
    pass


@dataclass
class Procedure(ICD9Container):
    """Table source: Hospital database.

    Table purpose: Contains ICD procedures for patients, most notably ICD-9
    procedures.

    Number of rows: 240,095

    Links to:

    PATIENTS on SUBJECT_ID
    ADMISSIONS on HADM_ID
    D_ICD_PROCEDURES on ICD9_CODE

    """
    pass


@dataclass
class NoteEvent(MimicContainer):
    """Table source: Hospital database.

    Table purpose: Contains all notes for patients.

    Number of rows: 2,083,180

    Links to:
      * PATIENTS on SUBJECT_ID
      * ADMISSIONS on HADM_ID
      * CAREGIVERS on CGID

    :see: `Dictionary <https://mimic.physionet.org/mimictables/noteevents/>`_

    """
    _DICTABLE_WRITE_EXCLUDES: ClassVar[Set[str]] = {'hadm_id', 'text'}
    _PERSITABLE_PROPERTIES: ClassVar[Set[str]] = set()
    _PERSITABLE_TRANSIENT_ATTRIBUTES: ClassVar[Set[str]] = {
        '_trans_context_var'}

    subject_id: int = field()
    """Foreign key. Identifies the patient.

    Identifiers which specify the patient: SUBJECT_ID is unique to a patient
    and HADM_ID is unique to a patient hospital stay.

    :see :obj:`hadm_id`

    """
    hadm_id: int = field()
    """Foreign key. Identifies the hospital admission."""

    chartdate: datetime = field()
    """Date when the note was charted.

    CHARTDATE records the date at which the note was charted. CHARTDATE will
    always have a time value of 00:00:00.

    CHARTTIME records the date and time at which the note was charted. If both
    CHARTDATE and CHARTTIME exist, then the date portions will be
    identical. All records have a CHARTDATE. A subset are missing
    CHARTTIME. More specifically, notes with a CATEGORY value of ‘Discharge
    Summary’, ‘ECG’, and ‘Echo’ never have a CHARTTIME, only CHARTDATE. Other
    categories almost always have both CHARTTIME and CHARTDATE, but there is a
    small amount of missing data for CHARTTIME (usually less than 0.5% of the
    total number of notes for that category).

    STORETIME records the date and time at which a note was saved into the
    system. Notes with a CATEGORY value of ‘Discharge Summary’, ‘ECG’,
    ‘Radiology’, and ‘Echo’ never have a STORETIME. All other notes have a
    STORETIME.

    """
    charttime: datetime = field()
    """Date and time when the note was charted. Note that some notes
    (e.g. discharge summaries) do not have a time associated with them: these
    notes have NULL in this column.

    :see: :obj:`chartdate`

    """
    storetime: datetime = field()
    """See :obj:`chartdate`."""

    category: str = field()
    """Category of the note, e.g. Discharge summary.

    CATEGORY and DESCRIPTION define the type of note recorded. For example, a
    CATEGORY of ‘Discharge summary’ indicates that the note is a discharge
    summary, and the DESCRIPTION of ‘Report’ indicates a full report while a
    DESCRIPTION of ‘Addendum’ indicates an addendum (additional text to be
    added to the previous report).
    """
    description: str = field()
    """A more detailed categorization for the note, sometimes entered by
    free-text."""

    cgid: int = field()
    """Foreign key. Identifies the caregiver."""

    iserror: bool = field()
    """Flag to highlight an error with the note."""

    text: str = field()
    """Content of the note."""

    context: InitVar[Settings] = field()
    """Contains resources needed by new and re-hydrated notes, such as the
    document stash.

    """
    def __post_init__(self, context: Settings):
        super().__post_init__()
        if self.hadm_id is None:
            raise MimicError('NoteEvent is missing hadm_id')
        self.category = self.category.strip()
        self.text = self.text.rstrip()
        self._trans_context = context.asdict()

    @property
    def _trans_context(self) -> Dict[str, Any]:
        return self._trans_context_var

    @_trans_context.setter
    def _trans_context(self, trans_context: Dict[str, Any]):
        if hasattr(self, '_trans_context_var') and \
           self._trans_context_var is not None:
            self._trans_context_var.update(trans_context)
        else:
            self._trans_context_var = dict(trans_context)
        self._trans_context_update(self._trans_context)

    def _trans_context_update(self, trans_context: Dict[str, Any]):
        pass

    @property
    def _doc_stash(self) -> Stash:
        return self._trans_context['doc_stash']

    @property
    @persisted('_id')
    def id(self) -> str:
        return re.sub(r'[/ ]+', '-', self.category).lower()

    @property
    @persisted('_truncated_text', transient=True)
    def truncted_text(self) -> str:
        return self._trunc(self.text, 70).replace('\n', ' ').strip()

    @property
    @persisted('_doc', transient=True)
    def doc(self) -> FeatureDocument:
        """The parsed document of the :obj:`name` of the section."""
        return self._get_doc()

    def _get_doc(self) -> FeatureDocument:
        return self._doc_stash[str(self.row_id)]

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout,
              line_limit: int = sys.maxsize, write_divider: bool = True,
              indent_fields: bool = True, note_indent: int = 1,
              include_fields: bool = True):
        """Write the note event.

        :param line_limit: the number of lines to write from the note text

        :param write_divider: whether to write a divider before the note text

        :param indent_fields: whether to indent the fields of the note

        :param note_indent: how many indentation to indent the note fields

        """
        if include_fields:
            dct = self._writable_dict()
            if indent_fields:
                super().write(depth, writer, dct)
            else:
                self._write_object(dct, depth, writer)
        if line_limit is not None and line_limit > 0:
            text = '\n'.join(
                filter(lambda s: len(s.strip()) > 0, self.text.split('\n')))
            if write_divider:
                self._write_divider(depth + note_indent, writer, char='_')
            self._write_block(text, depth + note_indent, writer,
                              limit=line_limit)
            if write_divider:
                self._write_divider(depth + note_indent, writer, char='_')

    def __str__(self):
        text = self.truncted_text
        return f'{self.row_id}: ({self.category}): {text}'

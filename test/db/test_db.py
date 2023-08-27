from typing import Set
import unittest
from zensols.persist import Stash
from zensols.mimic import (
    HospitalAdmission, Note, NoteEventPersister, ApplicationFactory
)
from zensols.mimic.regexnote import RadiologyNote, EchoNote
import warnings


class TestAnnotationAccess(unittest.TestCase):
    def setUp(self):
        self.maxDiff = 999999
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.corpus = ApplicationFactory.get_corpus()

    def test_note_access(self):
        stash: Stash = self.corpus.hospital_adm_stash
        adm: HospitalAdmission = stash['100139']
        rad_note: Note = adm.notes_by_category['Radiology'][0]
        echo_note: Note = adm[63188]
        self.assertEqual(RadiologyNote, type(rad_note))
        self.assertEqual(EchoNote, type(echo_note))
        sec = echo_note.sections_by_name['findings'][0]
        should = 'LEFT ATRIUM: Mild LA enlargement'
        self.assertEqual(should, sec.body[0:len(should)])
        should = 'left atrium.'
        self.assertEqual(should, sec.body[-len(should):])

    def test_ids(self):
        np: NoteEventPersister = self.corpus.note_event_persister
        hadm_ids = (102870, 106895, 110132, 112773, 120853, 121043, 132982)
        should_note_ids: Set[int] = set()
        for hadm_id in hadm_ids:
            should_note_ids.update(np.get_row_ids_by_hadm_id(hadm_id))
        note_ids: Set[int] = set()
        for hadm_id in np.get_hadm_ids(should_note_ids):
            note_ids.update(np.get_row_ids_by_hadm_id(hadm_id))
        self.assertEqual(should_note_ids, note_ids)

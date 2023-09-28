#!/usr/bin/env python

import pandas as pd
from zensols.mimic import (
    Section, Note, HospitalAdmission, Corpus, ApplicationFactory
)
from zensols.mimic.regexnote import DischargeSummaryNote


def main():
    # get the MIMIC-III corpus data acceess object
    corpus: Corpus = ApplicationFactory.get_corpus()
    # get an admission by hadm_id
    adm: HospitalAdmission = corpus.hospital_adm_stash['165315']
    # get the first discharge note (some have admissions have addendums)
    ds: Note = adm.notes_by_category[DischargeSummaryNote.CATEGORY][0]
    # get features of the note useful in ML models
    df: pd.DataFrame = ds.feature_dataframe
    print(df)
    # get the first (and only for this note) HPI section
    sec: Section = ds.sections_by_name['history-of-present-illness'][0]
    # print the headers and body of the section
    print('headers:', sec.headers)
    print('section body:')
    print(sec.headers)


if (__name__ == '__main__'):
    main()

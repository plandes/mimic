#!/usr/bin/env python

"""Example that demonstrates how to use the API to parse MIMIC-III text.

"""
__author__ = 'Paul Landes'

from dataclasses import dataclass, field
import logging
from io import StringIO
from zensols.cli import CliHarness
from zensols.mimic import Section, HospitalAdmissionDbStash, Corpus
from zensols.mimic.regexnote import DischargeSummaryNote

logger = logging.getLogger(__name__)
CONFIG = """
[cli]
apps = list: cleaner_cli, app

[cleaner_cli_decorator]
option_overrides = dict: {'clean_level': {'default': 1}}

[import]
sections = list: lib_imp

[lib_imp]
type = import
config_files = list:
    resource(zensols.util): resources/default.conf,
    resource(zensols.util): resources/escape.conf,
    resource(zensols.util): resources/cleaner.conf,
    resource(zensols.mednlp): resources/default.conf,
    resource(zensols.mimic): resources/default.conf,
    ${appenv:root_dir}/db-login-sqlite.conf,
    resource(zensols.nlp): resources/obj.conf,
    resource(zensols.nlp): resources/mapper.conf,
    resource(zensols.mednlp): resources/obj.conf,
    resource(zensols.mimic): resources/obj.conf,
    resource(zensols.mimic): resources/decorator.conf,
    ${appenv:root_dir}/db-login-sqlite.conf

[app]
class_name = shownote.Application
corpus = instance: mimic_corpus
"""


@dataclass
class Application(object):
    """Example that demonstrates how to use the API to parse MIMIC-III text.

    """
    CLI_META = {'mnemonic_overrides': {'parse_hpi': 'parse'},
                'option_excludes': {'corpus'},
                'option_overrides': {
                    'show_section_list': {'long_name': 'seclist'},
                    'print_note': {'long_name': 'print'}}}

    corpus: 'Corpus' = field()
    """The contains assets to access the MIMIC-III corpus via database."""

    def parse_hpi(self, hadm_id: str = '165315',
                  print_note: bool = False,
                  show_section_list: bool = False):
        """Parse the history of present illness section.

        :param hadm_id: the admission ID to parse

        :param print_note: whether to print the discharge summary

        :param show_section_list: whether to print a section listing

        """
        # get and admission by hadm_id
        stash: HospitalAdmissionDbStash = self.corpus.hospital_adm_stash
        adm = stash[hadm_id]

        # every admission has a discharge note, which we get by the name of the
        # category as a singleton
        ds: DischargeSummaryNote = adm.notes_by_category[
            DischargeSummaryNote.CATEGORY][0]

        # a human readable dump of the note
        if print_note:
            ds.write()

        # optionally show the sections as a Pandas dataframe
        if show_section_list:
            print('sections:')
            print(ds.section_dataframe)

        # get the first (and only for this note) HPI section
        sec: Section = ds.sections_by_name['history-of-present-illness'][0]
        sec.write()


# command line entry point
if (__name__ == '__main__'):
    CliHarness(
        src_dir_name='../src/python',
        app_config_resource=StringIO(CONFIG),
        # prototyping arguments
        proto_args='parse',
        proto_factory_kwargs={'reload_pattern': '^shownote'},
    ).run()

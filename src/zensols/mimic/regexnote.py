"""Regular expression note parsing

"""
__author__ = 'Paul Landes'

from typing import Iterable, ClassVar
from dataclasses import dataclass
from abc import ABCMeta, abstractmethod
import re
from zensols.nlp import LexicalSpan
from . import Section, SectionAnnotatorType, Note


@dataclass(repr=False)
class RegexNote(Note, metaclass=ABCMeta):
    """Base class used to collect subclass regular expressions captures and
    create sections from them.

    """
    @abstractmethod
    def _get_matches(self, text: str) -> Iterable[re.Match]:
        pass

    def _get_section_annotator_type(self) -> SectionAnnotatorType:
        return SectionAnnotatorType.REGULAR_EXPRESSION

    def _get_sections(self) -> Iterable[Section]:
        # add to match on most regex's that expect two newlines between sections
        ext_text = self.text + '\n\n'
        matches: Iterable[re.Match] = self._get_matches(ext_text)
        matches = filter(lambda m: (m.end() - m.start() > 0), matches)
        secs = []
        sid = 0
        try:
            while matches:
                m: re.Match = next(matches)
                name, sec_text = m.groups()
                sec = Section(
                    id=sid,
                    name=None,
                    container=self,
                    header_spans=(LexicalSpan(m.start(1), m.end(1)),),
                    body_span=LexicalSpan(m.start(2), m.end(2)))
                secs.append(sec)
                sid += 1
        except StopIteration:
            pass
        if len(secs) == 0:
            secs = super()._get_sections()
        return secs


@dataclass(repr=False)
class DischargeSummaryNote(RegexNote):
    """Contains sections for the discharge summary.  There should be only one of
    these per hospital admission.

    """
    CATEGORY: ClassVar[str] = 'Discharge summary'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'header': re.compile(r'([a-zA-Z ]+):\n+(.+?)\n{2,}', re.DOTALL),
        'para': re.compile(r'([A-Z ]+):[ ]{2,}(.+?)\n{2,}', re.DOTALL),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern
        if text.find('HISTORY OF PRESENT ILLNESS:') > -1:
            regex = self._SECTION_REGEX['para']
        else:
            regex = self._SECTION_REGEX['header']
        return re.finditer(regex, text)


@dataclass(repr=False)
class NursingOtherNote(RegexNote):
    CATEGORY: ClassVar[str] = 'Nursing/other'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'para': re.compile(r'([a-zA-Z ]+):[ ](.+?)\n{2,}', re.DOTALL),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern = self._SECTION_REGEX['para']
        return re.finditer(regex, text)


@dataclass(repr=False)
class EchoNote(RegexNote):
    CATEGORY: ClassVar[str] = 'Echo'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'para': re.compile(
            '(' +
            '|'.join('conclusions findings impression indication'.split() +
                     ['patient/test information', 'clinical implications']) +
            r'):[\n ]+(.+?)\n{2,}', re.DOTALL | re.IGNORECASE),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern = self._SECTION_REGEX['para']
        return re.finditer(regex, text)


@dataclass(repr=False)
class PhysicianNote(RegexNote):
    CATEGORY: ClassVar[str] = 'Physician'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'header': re.compile(
            r'[ ]{3}(' +
            'HPI|Current medications|24 Hour Events|Last dose of Antibiotics|Flowsheet Data|physical examination|labs / radiology|assessment and plan|code status|disposition' +
            r'):?\n(.+?)\n[ ]{3}[a-zA-Z0-9/ ]+:', re.DOTALL | re.IGNORECASE),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern = self._SECTION_REGEX['header']
        return re.finditer(regex, text)


@dataclass(repr=False)
class RadiologyNote(RegexNote):
    CATEGORY: ClassVar[str] = 'Radiology'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'para': re.compile(r'\s*([A-Z ]+):[\n ]{2,}(.+?)\n{2,}', re.DOTALL),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern = self._SECTION_REGEX['para']
        return re.finditer(regex, text)


@dataclass(repr=False)
class ConsultNote(RegexNote):
    """Contains sections for the discharge summary.  There should be only one of
    these per hospital admission.

    """
    CATEGORY: ClassVar[str] = 'Consult'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'header': re.compile(r'\s*([a-zA-Z/ ]+):\n+(.+?)(?:[\n]{2,}|\s+\.\n)',
                             re.DOTALL),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern = self._SECTION_REGEX['header']
        return re.finditer(regex, text)

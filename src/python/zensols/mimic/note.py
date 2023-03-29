from __future__ import annotations
"""EHR related text documents.

"""
__author__ = 'Paul Landes'

from typing import (
    Dict, Iterable, Set, Tuple, List, Any, Optional, ClassVar, Sequence
)
from dataclasses import dataclass, field, fields
from abc import ABCMeta, abstractmethod
import sys
import re
import collections
import itertools as it
from itertools import chain
from io import TextIOBase
from frozendict import frozendict
import pandas as pd
from zensols.config import ConfigFactory, Dictable
from zensols.persist import PersistableContainer, persisted
from zensols.nlp import LexicalSpan, FeatureToken, FeatureDocument
from zensols.nlp.dataframe import FeatureDataFrameFactory
from . import NoteEvent


@dataclass
class ParagraphFactory(object):
    """Splits a document in to constituent paragraphs.

    """
    _PARA_REGEX: ClassVar[re.Pattern] = re.compile(r'\n[\s.]*\n')

    def __call__(self, sec: Section) -> List[FeatureDocument]:
        par_spans: List[LexicalSpan] = []
        paras: List[FeatureDocument] = []
        bspan: LexicalSpan = sec.body_span
        bdoc: LexicalSpan = sec.body_doc
        marks: List[int] = [bspan.begin]
        for i in self._PARA_REGEX.finditer(sec.body):
            marks.extend((i.start() + bspan.begin, i.end() + bspan.begin))
        marks.append(bspan.end)
        mi = iter(marks)
        for beg in mi:
            par_spans.append(LexicalSpan(beg, next(mi)))
        ps: LexicalSpan
        for ps in par_spans:
            para: FeatureDocument = bdoc.get_overlapping_document(ps)
            para.text = ' '.join(map(lambda s: s.text.strip(), para))
            paras.append(para)
        return paras


@dataclass
class Section(PersistableContainer, Dictable):
    """A section segment with an identifier and represents a section of a
    :class:`.Note`, one for each section.  An example of a section is the
    *history of present illness* in a discharge note.

    """
    _PERSITABLE_TRANSIENT_ATTRIBUTES: ClassVar[Set[str]] = {
        'container', '_doc_stash', '_paragraph_factory'}

    _SENT_FILTER_REGEX: ClassVar[re.Pattern] = re.compile(r'^\s*\d+\.\s*')
    """Remove enumerated lists (<number> .) as separate sentences.  Example is
    hadm=119960, cat=Discharge summary, section=Discharge Medications:
    ``1. Vancomycin 125 mg``.

    """
    id: int = field()
    """The unique ID of the section."""

    name: Optional[str] = field()
    """The name of the section (i.e. ``hospital-course``).  This field is what's
    called the ``type`` in the paper, which is not used since ``type`` is a
    keyword in Python.

    """
    container: SectionContainer = field(repr=False)
    """The container that has this section."""

    header_spans: Tuple[LexicalSpan] = field()
    """The character start offset of the section, starting with the name and the
    character offset of the end of the body text.  This is the identifier of
    the section.

    """
    body_span: LexicalSpan = field()
    """Like :obj:`header_spans` but for the section body.  The body and name do
    not intersect.

    """
    def __post_init__(self):
        super().__init__()
        if self.name is None:
            if len(self.headers) == 0:
                self.name = 'unknown'
            else:
                header = ' '.join(self.headers)
                self.name = re.sub(r'[_/ ]+', '-', header).lower()

    @property
    def note_text(self) -> str:
        """The entire parent note's text."""
        return self.container.text

    @property
    @persisted('_headers', transient=True)
    def headers(self) -> Tuple[str]:
        """The section text."""
        text = self.note_text
        return tuple(map(lambda s: text[s.begin:s.end], self.header_spans))

    @property
    def body(self) -> str:
        """The section text."""
        return self.note_text[self.body_span.begin:self.body_span.end]

    @property
    def header_tokens(self) -> Iterable[FeatureToken]:
        doc: FeatureDocument = self.container._get_doc()
        spans = doc.map_overlapping_tokens(self.header_spans)
        return chain.from_iterable(spans)

    @property
    def body_tokens(self) -> Iterable[FeatureToken]:
        doc: FeatureDocument = self.container._get_doc()
        return doc.get_overlapping_tokens(self.body_span)

    @property
    @persisted('_body_doc', transient=True)
    def body_doc(self) -> FeatureDocument:
        """A feature document of the body of this section's body text."""
        return self._get_body_doc()

    def _get_body_doc(self) -> FeatureDocument:
        doc: FeatureDocument = self._doc_stash[str(self._row_id)]
        doc = self._narrow_doc(doc)
        return doc

    def _narrow_doc(self, doc: FeatureDocument) -> FeatureDocument:
        sreg: re.Pattern = self._SENT_FILTER_REGEX
        doc = doc.get_overlapping_document(self.body_span)
        doc.sents = list(filter(lambda s: sreg.match(s.text) is None,
                                doc.sents))
        return doc

    @property
    @persisted('_paragraphs', transient=True)
    def paragraphs(self) -> Tuple[FeatureDocument]:
        """The list of paragraphs, each as as a feature document, of this
        section's body text.

        """
        return tuple(self._paragraph_factory(self))

    @property
    def is_empty(self) -> bool:
        """Whether the content of the section is empty."""
        return len(self.body) == 0

    def write_sentences(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                        container: FeatureDocument = None, limit: int = 0):
        """Write all parsed sentences of the section with respective entities.

        """
        def map_ent(tp: Tuple[FeatureToken]):
            """Map a feature token to a readable string."""
            if tp[0].ent_ == 'concept':
                desc = f' ({tp[0].cui_})'
            else:
                desc = f' ({tp[0].ent_})'
            return ' '.join(map(lambda t: t.norm, tp)) + desc

        container = self.body_doc if container is None else container
        for sent in it.islice(container, limit):
            self._write_divider(depth, writer)
            self._write_line(sent.norm, depth, writer)
            mtoks = tuple(map(lambda tk: f'{tk.text} ({tk.norm})',
                              filter(lambda t: t.mimic_ != FeatureToken.NONE,
                                     sent.token_iter())))
            if len(mtoks) > 0:
                self._write_line(f"mimic: {', '.join(mtoks)}", depth, writer)
            if len(sent.entities) > 0:
                ents = ', '.join(map(map_ent, sent.entities))
                self._write_line(f'entities: {ents}', depth, writer)

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout,
              body_line_limit: int = sys.maxsize,
              norm_line_limit: int = sys.maxsize,
              par_limit: int = 0, sent_limit: int = 0,
              include_header: bool = True,
              include_id_name: bool = True):
        """Write a note section's name, original body, normalized body and
        sentences with respective sentence entities.

        :param body_line_limit: the number of line of the section's body to
                                output

        :param norm_line_limit: the number of line of the section's normalized
                                (parsed) body to output

        :param par_limit: the number of paragraphs to output

        :param sent_limit: the number of sentences to output

        :param include_header: whether to include the header

        :param include_id_name: whether to write the section ID and name

        """
        header = ' '.join(self.headers)
        if include_id_name:
            self._write_line(f'id: {self.id}', depth, writer)
            self._write_line(f'name: {self.name}', depth, writer)
        if include_header:
            self._write_line(f'headers: {header}', depth, writer)
        if not self.is_empty:
            if body_line_limit > 0:
                self._write_line('body:', depth, writer)
                self._write_block(self.body, depth + 1, writer,
                                  limit=body_line_limit)
            if norm_line_limit > 0:
                self._write_line('normalized:', depth, writer)
                self._write_block(self.body_doc.norm, depth + 1, writer,
                                  limit=norm_line_limit)
            if par_limit > 0 and sent_limit > 0:
                for par in self.paragraphs:
                    self._write_line('paragraph:', depth, writer)
                    self.write_sentences(depth + 1, writer, par, sent_limit)

    def __len__(self) -> int:
        return len(self.body_span) + sum(map(len, self.header_spans))

    def __str__(self):
        return f'{self.name} ({self.id}): body_len={len(self.body)}'


@dataclass
class SectionContainer(Dictable, metaclass=ABCMeta):
    """A *note like* container base class that has sections.  Note based classes
    extend this base class.

    """
    _DICTABLE_ATTRIBUTES: ClassVar[Set[str]] = {'sections'}

    @abstractmethod
    def _get_doc(self) -> FeatureDocument:
        """Return the parsed document that represents the text in this
        container."""
        pass

    @abstractmethod
    def _get_sections(self) -> Iterable[Section]:
        """Generate the sections cached and returned in the :obj:`sections`
        property.

        """
        pass

    @property
    @persisted('_sections')
    def sections(self) -> Dict[int, Section]:
        """A map from the name of a section (i.e. *history of present illness*
        in discharge notes) to a note section.

        """
        secs: Iterable[Section] = self._get_sections()
        return frozendict({sec.id: sec for sec in secs})

    @property
    @persisted('_by_name', transient=True)
    def sections_by_name(self) -> Dict[str, Tuple[Section]]:
        by_name = collections.defaultdict(list)
        for s in self.sections.values():
            by_name[s.name].append(s)
        return frozendict(map(lambda s: (s[0], tuple(s[1])), by_name.items()))

    @property
    def section_dataframe(self) -> pd.DataFrame:
        """A Pandas dataframe containing the section's name, header and body
        offset spans.

        """
        rows = []
        cols = 'name body headers body_begin body_end'.split()
        sec: Section
        for sec in self.sections.values():
            rows.append((sec.name, sec.body, sec.header_spans,
                         sec.body_span.begin, sec.body_span.end))
        return pd.DataFrame(rows, columns=cols)

    @property
    def feature_dataframe(self) -> pd.DataFrame:
        """Return a dataframe useful for feature craft."""
        def map_df(sec: Section):
            df = dataframe_factory(sec.body_doc)
            df['section'] = sec.name
            return df

        dataframe_factory: FeatureDataFrameFactory = \
            self._trans_context['dataframe_factory']
        dfs = map(map_df, self.sections.values())
        return pd.concat(dfs, ignore_index=True, copy=False)

    def write_fields(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        pass

    def write_human(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                    normalize: bool = False):
        """Generates a human readable version of the annotation.  This calls the
        following methods in order: :meth:`write_fields` and
        :meth:`write_sections`.

        :param depth: the starting indentation depth

        :param writer: the writer to dump the content of this writable

        :param normalize: whether to use the paragraphs' normalized
                          (:obj:~zensols.nlp.TokenContainer.norm`) or text

        """
        self.write_fields(depth, writer)
        self.write_sections(depth, writer, normalize=normalize)

    def write_sections(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                       normalize: bool = False):
        """Writes the sections of the container.

        :param depth: the starting indentation depth

        :param writer: the writer to dump the content of this writable

        :param normalize: whether to use the paragraphs' normalized
                          (:obj:~zensols.nlp.TokenContainer.norm`) or text

        """
        for sec in self.sections.values():
            header = ' '.join(sec.headers)
            div_text: str = f'{sec.id}:{sec.name}'
            if len(header) > 0:
                div_text += f' ({header})'
            self._write_divider(depth, writer, header=div_text)
            if normalize:
                for i, para in enumerate(sec.paragraphs):
                    if i > 0:
                        self._write_empty(writer)
                    self._write_wrap(para.norm, depth, writer)
            elif len(sec.body) > 0:
                self._write_block(sec.body, depth, writer)

    def write_markdown(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                       normalize: bool = False):
        """Generates markdown version of the annotation.

        :param depth: the starting indentation depth

        :param writer: the writer to dump the content of this writable

        :param normalize: whether to use the paragraphs' normalized
                          (:obj:~zensols.nlp.TokenContainer.norm`) or text

        """
        self._write_line(f'# {self.category} ({self.row_id})', depth, writer)
        for sec in self.sections.values():
            header = ' '.join(sec.headers)
            self._write_empty(writer)
            self._write_empty(writer)
            self._write_line(f'## {header}', depth, writer)
            self._write_empty(writer)
            if normalize:
                for i, para in enumerate(sec.paragraphs):
                    if i > 0:
                        self._write_empty(writer)
                    self._write_wrap(para.norm, depth, writer)
            elif len(sec.body) > 0:
                self._write_block(sec.body, depth, writer)

    def __getitem__(self, id: int):
        return self.sections[id]

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        self.write_human(depth, writer)

    def write_full(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                   note_line_limit: int = sys.maxsize,
                   section_line_limit: int = sys.maxsize,
                   section_sent_limit: int = sys.maxsize,
                   include_section_header: bool = True,
                   sections: Set[str] = None,
                   include_fields: bool = True,
                   include_note_divider: bool = True,
                   include_section_divider: bool = True):
        """Write the custom parts of the note.

        :param note_line_limit: the number of lines to write from the note text

        :param section_line_limit: the number of line of the section's body and
                                   number of sentences to output

        :param par_limit: the number of paragraphs to output

        :param sections: the sections, by name, to write

        :param include_section_header: whether to include the header

        :param include_fields: whether to write the note fields

        :param include_note_divider: whether to write dividers between notes

        :param include_section_divider: whether to write dividers between
                                        sections

        """
        secs: Sequence[Section] = self.sections.values()
        if sections is not None:
            secs = tuple(filter(lambda s: s.name in sections, secs))
        if len(secs) > 0:
            self._write_line('sections:', depth + 1, writer)
            sec: Section
            for sec in secs:
                aft: str = ''
                if section_line_limit == 0 and include_section_header:
                    aft = ':'
                self._write_line(f'{sec.name}{aft}', depth + 2, writer)
                sec.write(depth + 3, writer,
                          include_id_name=False,
                          body_line_limit=section_line_limit,
                          norm_line_limit=section_line_limit,
                          sent_limit=section_sent_limit,
                          include_header=include_section_header)
                if include_section_divider:
                    self._write_divider(depth + 3, writer)
        if include_note_divider:
            self._write_divider(depth, writer, '=')


@dataclass
class Note(NoteEvent, SectionContainer):
    """A container class of :class:`.Section` for each section for the
    text in the note events given by the property  :obj:`sections`.

    """
    _PERSITABLE_PROPERTIES: ClassVar[Set[str]] = {'sections'} | \
        NoteEvent._PERSITABLE_PROPERTIES
    _DICTABLE_WRITE_EXCLUDES: ClassVar[Set[str]] = \
        NoteEvent._DICTABLE_WRITE_EXCLUDES | {'sections'}
    _DICTABLE_WRITABLE_DESCENDANTS: ClassVar[bool] = True

    def _get_sections(self) -> Iterable[Section]:
        sec = Section(0, 'default', self, (), LexicalSpan(0, len(self.text)))
        sec._row_id = self.row_id
        return [sec]

    def _get_annotator(self) -> str:
        return 'none'

    def _trans_context_update(self, trans_context: Dict[str, Any]):
        for sec in self.sections.values():
            sec.container = self
            sec._row_id = self.row_id
            sec._doc_stash = trans_context['doc_stash']
            sec._paragraph_factory = trans_context['paragraph_factory']

    def write_fields(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        self._write_line(f'row_id: {self.row_id}', depth, writer)
        self._write_line(f'category: {self.category}', depth, writer)
        self._write_line(f'annotator: {self._get_annotator()}', depth, writer)

    def write_full(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                   note_line_limit: int = sys.maxsize,
                   section_line_limit: int = sys.maxsize,
                   section_sent_limit: int = sys.maxsize,
                   include_section_header: bool = True,
                   sections: Set[str] = None,
                   include_fields: bool = True,
                   include_note_divider: bool = True,
                   include_section_divider: bool = True):
        super().write(depth, writer,
                      line_limit=note_line_limit,
                      include_fields=include_fields)
        super().write_full(
            depth, writer,
            note_line_limit=note_line_limit,
            section_line_limit=section_line_limit,
            section_sent_limit=section_sent_limit,
            include_section_header=include_section_header,
            sections=sections,
            include_fields=include_fields,
            include_note_divider=include_note_divider,
            include_section_divider=include_section_divider)


@dataclass
class RegexNote(Note, metaclass=ABCMeta):
    """Base class used to collect subclass regular expressions captures and
    create sections from them.

    """
    @abstractmethod
    def _get_matches(self, text: str) -> Iterable[re.Match]:
        pass

    def _get_annotator(self) -> str:
        return 'regular expression'

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
        return secs


@dataclass
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


@dataclass
class NursingOtherNote(RegexNote):
    CATEGORY: ClassVar[str] = 'Nursing/other'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'para': re.compile(r'([a-zA-Z ]+):[ ](.+?)\n{2,}', re.DOTALL),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern = self._SECTION_REGEX['para']
        return re.finditer(regex, text)


@dataclass
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


@dataclass
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


@dataclass
class RadiologyNote(RegexNote):
    CATEGORY: ClassVar[str] = 'Radiology'
    _SECTION_REGEX: ClassVar[re.Pattern] = {
        'para': re.compile(r'\s*([A-Z ]+):[\n ]{2,}(.+?)\n{2,}', re.DOTALL),
    }

    def _get_matches(self, text: str) -> Iterable[re.Match]:
        regex: re.Pattern = self._SECTION_REGEX['para']
        return re.finditer(regex, text)


@dataclass
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


@dataclass
class NoteFactory(object):
    """Creates an instance of :class:`.Note` from :class:`.NoteEvent`.

    """
    config_factory: ConfigFactory = field()
    """The factory used to create notes.

    """
    category_to_note: Dict[str, str] = field()
    """A mapping between notes' category to section name for :class:.Note`
    configuration.

    """
    mimic_default_note_section: str = field()
    """The section name holding the configuration of the class to create when there
    is no mapping in :obj:`category_to_note`.

    """
    def _event_to_note(self, note_event: NoteEvent, section: str,
                       params: Dict[str, Any] = None) -> Note:
        ne_params = {f.name: getattr(note_event, f.name)
                     for f in fields(note_event)}
        if params is not None:
            ne_params.update(params)
        return self.config_factory.new_instance(section, **ne_params)

    def create(self, note_event: NoteEvent, section: str = None) -> Note:
        """Create a new factory based instance of a :class:`.Note` from a
        :class:`.NoteEvent`.

        :param note_event: the source data

        :param section: the configuration section to use to create the new note,
                        which is one of the regular expression based sections or
                        :obj:`mimic_default_note_section` for a :class:`.Note`

        """
        if section is None:
            section = self.category_to_note.get(note_event.category)
        if section is None:
            section = self.mimic_default_note_section
        return self._event_to_note(note_event, section)

    def __call__(self, note_event: NoteEvent, section: str = None) -> Note:
        """See :meth:`.create`."""
        return self.create(note_event, section)

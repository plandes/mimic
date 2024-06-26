"""EHR related text documents.

"""
from __future__ import annotations
__author__ = 'Paul Landes'
from typing import (
    Dict, Iterable, Set, Tuple, List, Any, Optional, ClassVar, Sequence
)
from dataclasses import dataclass, field, fields
from abc import ABCMeta, abstractmethod
from enum import Enum, auto
import logging
import sys
import re
import collections
import copy
import itertools as it
from itertools import chain
from io import TextIOBase
from frozendict import frozendict
import pandas as pd
from zensols.config import Dictable, ConfigFactory
from zensols.persist import PersistableContainer, persisted, Primeable
from zensols.nlp import LexicalSpan, FeatureToken, FeatureDocument
from zensols.nlp.dataframe import FeatureDataFrameFactory
from . import NoteEvent

logger = logging.getLogger(__name__)


class NoteFormat(Enum):
    """Used in :meth:`.Note.format` for a parameterized method to write a note.

    """
    text = auto()
    raw = auto()
    verbose = auto()
    summary = auto()
    json = auto()
    yaml = auto()
    markdown = auto()

    @property
    def ext(self) -> str:
        return {
            self.text: 'txt',
            self.raw: 'txt',
            self.verbose: 'txt',
            self.summary: 'txt',
            self.json: 'json',
            self.yaml: 'yaml',
            self.markdown: 'md'
        }[self]


class SectionAnnotatorType(Enum):
    """The type of :class:`.Section` annotator for :class:`.Note` instances.
    The `MedSecId`_ project adds the :obj:`human` and :obj:`model`:

    :see: `MedSecId <https://github.com/plandes/mimicsid>`_

    """
    NONE = auto()
    """Default for those without section identifiers."""

    REGULAR_EXPRESSION = auto()
    """Sections are automatically assigned by regular expressions."""

    HUMAN = auto()
    """A `MedSecId`_ human annotator."""

    MODEL = auto()
    """Predictions are provided by a `MedSecId`_ model."""


@dataclass
class ParagraphFactory(object, metaclass=ABCMeta):
    """Splits a document in to constituent paragraphs.

    """
    @abstractmethod
    def create(self, sec: Section) -> Iterable[FeatureDocument]:
        pass


@dataclass
class Section(PersistableContainer, Dictable):
    """A section segment with an identifier and represents a section of a
    :class:`.Note`, one for each section.  An example of a section is the
    *history of present illness* in a discharge note.

    """
    _DICTABLE_WRITABLE_DESCENDANTS: ClassVar[bool] = True
    _PERSITABLE_TRANSIENT_ATTRIBUTES: ClassVar[Set[str]] = {
        'container', '_doc_stash', '_paragraph_factory'}

    _SENT_FILTER_REGEX: ClassVar[re.Pattern] = re.compile(r'^\s*\d+\.\s*')
    """Remove enumerated lists (<number> .) as separate sentences.  Example is
    hadm=119960, cat=Discharge summary, section=Discharge Medications:
    ``1. Vancomycin 125 mg``.

    """
    FILTER_ENUMS: ClassVar[bool] = True
    """Whether to filter enumerated lists as separate sentences."""

    id: int = field()
    """The unique ID of the section."""

    name: Optional[str] = field()
    """The name of the section (i.e. ``hospital-course``).  This field is what's
    called the ``type`` in the paper, which is not used since ``type`` is a
    keyword in Python.

    """
    container: SectionContainer = field(repr=False)
    """The container that has this section."""

    header_spans: Tuple[LexicalSpan, ...] = field()
    """The character offsets of the section headers.  The first is usually the
    :obj:`name` of the section.  If there are no headers, this is an 0-length
    tuple.

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
    def headers(self) -> Tuple[str, ...]:
        """The section text."""
        text = self.note_text
        return tuple(map(lambda s: text[s.begin:s.end], self.header_spans))

    @property
    def body(self) -> str:
        """The section text."""
        return self.note_text[self.body_span.begin:self.body_span.end]

    def _get_doc(self) -> FeatureDocument:
        return self.container._get_doc()

    @property
    def header_tokens(self) -> Iterable[FeatureToken]:
        doc: FeatureDocument = self._get_doc()
        spans = doc.map_overlapping_tokens(self.header_spans)
        return chain.from_iterable(spans)

    @property
    def body_tokens(self) -> Iterable[FeatureToken]:
        doc: FeatureDocument = self._get_doc()
        return doc.get_overlapping_tokens(self.body_span)

    @property
    @persisted('_doc', transient=True)
    def doc(self) -> FeatureDocument:
        """A feature document of the section's body text."""
        return self._narrow_doc(self._get_doc(), self.lexspan, False)

    @property
    @persisted('_body_doc', transient=True)
    def body_doc(self) -> FeatureDocument:
        """A feature document of the body of this section's body text."""
        return self._narrow_doc(self._get_doc(), self.body_span)

    def _narrow_doc(self, doc: FeatureDocument, span: LexicalSpan,
                    filter_sent: bool = None) -> \
            FeatureDocument:
        if filter_sent is None:
            filter_sent = self.FILTER_ENUMS
        # using inclusive=true will very often leave newlines, but keep the last
        # sentence character when the sentence chunker gets confused
        doc = doc.get_overlapping_document(span, inclusive=True)
        if filter_sent:
            sreg: re.Pattern = self._SENT_FILTER_REGEX
            doc.sents = tuple(filter(lambda s: sreg.match(s.text) is None,
                                     doc.sents))
        return doc

    @property
    @persisted('_lexspan')
    def lexspan(self) -> LexicalSpan:
        """The widest lexical extent of the sections, including headers."""
        return LexicalSpan.widen(
            chain.from_iterable(((self.body_span,), self.header_spans)))

    @property
    def text(self) -> str:
        """Get the entire text of the section, which includes the headers."""
        span: LexicalSpan = self.lexspan
        ntext: str = self.note_text
        return ntext[span.begin:span.end]

    @property
    @persisted('_paragraphs', transient=True)
    def paragraphs(self) -> Tuple[FeatureDocument, ...]:
        """The list of paragraphs, each as as a feature document, of this
        section's body text.

        """
        return tuple(self._paragraph_factory.create(self))

    @property
    def is_empty(self) -> bool:
        """Whether the content of the section is empty."""
        return len(self.header_spans) == 0 and len(self.body.strip()) == 0

    @staticmethod
    def header_to_name(s: str) -> str:
        """Convert a section header text to a section name."""
        return s.replace(' ', '-').lower()

    @staticmethod
    def name_to_header(s: str) -> str:
        """Convert a section name to a section header text.  Note that this uses
        a heuristic method that might generate a string that does not match the
        original header text.

        """
        return s.replace('-', ' ').capitalize()

    def _copy_resources(self, target: Section):
        for attr in self._PERSITABLE_TRANSIENT_ATTRIBUTES:
            setattr(target, attr, getattr(self, attr))
        target._row_id = self._row_id

    def clone(self) -> Section:
        clone = copy.copy(self)
        self._copy_resources(clone)
        return clone

    def write_sentences(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                        container: FeatureDocument = None, limit: int = 0):
        """Write all parsed sentences of the section with respective entities.

        """
        def map_ent(tp: Tuple[FeatureToken, ...]):
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

    def write_as_item(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        """A terse output designed for list iteration."""
        self._write_line(f'id: {self.id}', depth, writer)
        self.write(depth + 1, writer, body_line_limit=0, norm_line_limit=0,
                   include_header_spans=True, include_body_span=True,
                   include_id_name=False)

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout,
              body_line_limit: int = sys.maxsize,
              norm_line_limit: int = sys.maxsize,
              par_limit: int = 0, sent_limit: int = 0,
              include_header: bool = True, include_id_name: bool = True,
              include_header_spans: bool = False,
              include_body_span: bool = False):
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
            self._write_line(f'header: {header}', depth, writer)
        if include_header_spans:
            self._write_line(f'header spans: {self.header_spans}',
                             depth, writer)
        if include_body_span:
            self._write_line(f'body span: {self.body_span}', depth, writer)
        if not len(self.body) > 0:
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
    extend this base class.  Sections in order of their position in the document
    are produced when using this class as an iterable.

    """
    _DICTABLE_ATTRIBUTES: ClassVar[Set[str]] = {'sections'}
    DEFAULT_SECTION_NAME: ClassVar[str] = 'default'
    """The name of the singleton section when none the note is not sectioned."""

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

    @staticmethod
    def category_to_id(s: str) -> str:
        """Convert a category string (i.e. ``Discharge summary``) to a category
        ID (i.e. ``discharge-summary``).

        """
        return Section.header_to_name(s)

    @staticmethod
    def id_to_category(s: str) -> str:
        """Convert a category ID (i.e. ``discharge-summary``) to a category
        string (i.e. ``Discharge summary``).

        """
        return Section.name_to_header(s)

    @property
    @persisted('_sections')
    def sections(self) -> Dict[int, Section]:
        """A map from the unique section identifier to a note section.

        """
        secs: Iterable[Section] = self._get_sections()
        return frozendict({sec.id: sec for sec in secs})

    @property
    @persisted('_sections_ordered', transient=True)
    def sections_ordered(self) -> Tuple[Section, ...]:
        """Sections returned in order as they appear in the note."""
        return tuple(map(lambda t: t[1], sorted(
            self.sections.items(), key=lambda t: t[0])))

    @property
    @persisted('_by_name', transient=True)
    def sections_by_name(self) -> Dict[str, Tuple[Section, ...]]:
        """A map from the name of a section (i.e. *history of present illness*
        in discharge notes) to a note section.

        """
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
        cols = 'name id body headers body_begin body_end'.split()
        sec: Section
        for sec in self.sections.values():
            rows.append((sec.name, sec.id, sec.body,
                         tuple(map(lambda s: s.astuple, sec.header_spans)),
                         sec.body_span.begin, sec.body_span.end))
        return pd.DataFrame(rows, columns=cols)

    @property
    def feature_dataframe(self) -> pd.DataFrame:
        """A dataframe useful for features used in an ML model."""
        def map_df(sec: Section):
            df = dataframe_factory(sec.body_doc)
            df['section'] = sec.name
            df['section_id'] = sec.id
            return df

        dataframe_factory: FeatureDataFrameFactory = \
            self._trans_context['dataframe_factory']
        dfs = map(map_df, self.sections.values())
        return pd.concat(dfs, ignore_index=True, copy=False)

    def write_fields(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        """Write note header fields such as the ``row_id`` and ``category``.

        """
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
        for sec in self:
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

    def write_by_format(self, depth: int = 0, writer: TextIOBase = sys.stdout,
                        note_format: NoteFormat = NoteFormat):
        """Write the note in the specified format.

        :param depth: the starting indentation depth

        :param writer: the writer to dump the content of this writable

        :param note_format: the format to use for the output

        """
        def summary_format(writer: TextIOBase):
            for s in self.sections.values():
                print(s, s.header_spans, len(s))

        {NoteFormat.text: lambda: self.write_human(depth, writer),
         NoteFormat.verbose: lambda: self.write_full(depth, writer),
         NoteFormat.raw: lambda: writer.write(self.text),
         NoteFormat.json: lambda: self.asjson(writer=writer, indent=4),
         NoteFormat.yaml: lambda: self.asyaml(writer=writer, indent=4),
         NoteFormat.markdown: lambda: self.write_markdown(depth, writer),
         NoteFormat.summary: lambda: summary_format(depth, writer),
         }[note_format]()

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        self.write_human(depth, writer)

    def __getitem__(self, id: int) -> Section:
        return self.sections[id]

    def __iter__(self) -> Iterable[Section]:
        return iter(sorted(self.sections.values(), key=lambda s: s.lexspan))


@dataclass
class GapSectionContainer(SectionContainer):
    """A container that fills in missing sections of text from a note with
    additional sections.

    """
    delegate: Note = field()
    """The note with the sections to be filled."""

    filter_empty: bool = field()
    """Whether to filter empty sections."""

    def _get_doc(self) -> FeatureDocument:
        return self.delegate._get_doc()

    def _get_sections(self) -> Iterable[Section]:
        sections: List[Section] = list(
            map(lambda s: s.clone(), self.delegate.sections.values()))
        if len(sections) > 0:
            note_text: str = self.delegate.text
            gaps: Sequence[LexicalSpan] = LexicalSpan.gaps(
                spans=map(lambda s: s.lexspan, sections),
                end=len(note_text))
            ref_sec: Section = sections[0]
            sec_cont: SectionContainer = ref_sec.container
            gap_secs: List[Section] = []
            gs: LexicalSpan
            for gs in gaps:
                gsec = Section(
                    id=-1,
                    name=None,
                    container=sec_cont,
                    header_spans=(),
                    body_span=gs)
                if self.filter_empty and gsec.is_empty:
                    continue
                ref_sec._copy_resources(gsec)
                gap_secs.append(gsec)
            sections.extend(gap_secs)
            sections.sort(key=lambda s: s.lexspan)
            sec: Section
            for sid, sec in enumerate(sections):
                sec.original_id = sec.id
                sec.id = sid
        return sections


@dataclass(repr=False)
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
        sec = Section(0, self.DEFAULT_SECTION_NAME, self, (),
                      LexicalSpan(0, len(self.text)))
        sec._row_id = self.row_id
        return [sec]

    @property
    def section_annotator_type(self) -> SectionAnnotatorType:
        """A human readable string describing who or what annotated the note."""
        return self._get_section_annotator_type()

    def _get_section_annotator_type(self) -> SectionAnnotatorType:
        return SectionAnnotatorType.NONE

    def _trans_context_update(self, trans_context: Dict[str, Any]):
        for sec in self.sections.values():
            sec.container = self
            sec._row_id = self.row_id
            sec._doc_stash = trans_context['doc_stash']
            sec._paragraph_factory = trans_context['paragraph_factory']

    def write_fields(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        sat: SectionAnnotatorType = self.section_annotator_type
        self._write_line(f'row_id: {self.row_id}', depth, writer)
        self._write_line(f'category: {self.category}', depth, writer)
        self._write_line(f'description: {self.description}', depth, writer)
        self._write_line(f'annotator: {sat.name.lower()}', depth, writer)

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

    def write(self, depth: int = 0, writer: TextIOBase = sys.stdout):
        SectionContainer.write(self, depth, writer)


@dataclass
class NoteFactory(Primeable):
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
    """The section name holding the configuration of the class to create when
    there is no mapping in :obj:`category_to_note`.

    """
    def _event_to_note(self, note_event: NoteEvent, section: str,
                       params: Dict[str, Any] = None) -> Note:
        """Create a note from the application configuration

        :param section: the configuration section that details the class

        :param params: used to initialize the new instance

        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'even to note (section={section}): {note_event}')
        ne_params = {f.name: getattr(note_event, f.name)
                     for f in fields(note_event)}
        if params is not None:
            ne_params.update(params)
        return self.config_factory.new_instance(section, **ne_params)

    def _create_from_note_event(self, note_event: NoteEvent,
                                section: str = None) -> Note:
        """Because subclasses override :meth:`create`, we need a method that
        specifically creates from :class:`.NoteEvent` for subclasses that
        recover from errors (such as MedSecId prediction) when they cannot
        create notes themselves.  This method provides a way to create them
        directly using the default regular expressions (:mod:`regexnote`).

        **Important**: do not override this method.

        :param note_event: the source data

        :param section: the configuration section to use to create the new note,
                        which is one of the regular expression based sections or
                        :obj:`mimic_default_note_section` for a :class:`.Note`


        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'create note from event: {note_event}')
        if section is None:
            section = self.category_to_note.get(note_event.category)
        if section is None:
            section = self.mimic_default_note_section
        return self._event_to_note(note_event, section)

    def create(self, note_event: NoteEvent) -> Note:
        """Create a new factory based instance of a :class:`.Note` from a
        :class:`.NoteEvent`.

        :param note_event: the source data

        """
        return self._create_from_note_event(note_event, None)

    def create_default(self, note_event: NoteEvent) -> Note:
        """Like :meth:`.create` but always create the default (:class:`.Note`)
        note.

        :param note_event: the source data

        :return: always an instance of :class:`.Note`

        """
        return self._create_from_note_event(
            note_event, self.mimic_default_note_section)

    def prime(self):
        """The MedSecId project primes by installing the model files."""
        if logger.isEnabledFor(logging.INFO):
            logger.info('priming...')

    def __call__(self, note_event: NoteEvent, section: str = None) -> Note:
        """See :meth:`.create`."""
        return self.create(note_event, section)


@dataclass
class DefaultNoteFactory(NoteFactory):
    """A note factory that creates only default notes.

    :see: :meth:`.NoteFactory.create_default`

    """
    def create(self, note_event: NoteEvent) -> Note:
        return self.create_default(note_event)

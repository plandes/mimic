"""Utility classes.

"""
__author__ = 'Paul Landes'

from typing import ClassVar, Tuple, List, Iterable, Sequence, Optional
from dataclasses import dataclass, field
import re
import logging
from zensols.nlp import LexicalSpan, FeatureSentence, FeatureDocument
from . import SectionContainer, Section, Note

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ListItemChunker(object):
    """Splits list item and enumerated lists into separate sentences.  Matched
    sentences are given if used as an iterable.  The document of all parsed
    sentences is given if used as a callable.

    """
    DEFAULT_LIST_PATTERN: ClassVar[re.Pattern] = re.compile(
        r'([0-9]+.+?[\r\n])$', re.MULTILINE)

    global_doc: FeatureDocument = field()
    """The document that contains the entire text (i.e. :class:`.Note`)."""

    sub_doc: FeatureDocument = field(default=None)
    """A lexical span of :obj:`global_doc`, which defaults to the global
    document.

    """
    global_char_offset: int = field(default=0)
    """The 0-index absolute character offset where :obj:`sub_doc` starts."""

    pattern: re.Pattern = field(default=DEFAULT_LIST_PATTERN)
    """The list regular expression, which defaults to
    :obj:`DEFAULT_LIST_PATTERN`.

    """
    def __post_init__(self):
        if self.sub_doc is None:
            self.sub_doc = self.global_doc

    def _create_sent(self, span: LexicalSpan) -> Optional[FeatureSentence]:
        sent = self.global_doc.get_overlapping_document(span).\
            to_sentence(contiguous_i_sent='reset', delim=' ')
        sent.strip()
        if sent.token_len > 0:
            return sent

    def __iter__(self) -> Iterable[FeatureSentence]:
        def match_to_span(m: re.Match) -> LexicalSpan:
            s: Tuple[int, int] = m.span()
            return LexicalSpan(s[0] + coff, s[1] + coff)

        sents = []
        if self.sub_doc.token_len > 0:
            coff: int = self.global_char_offset
            text: str = self.sub_doc.text
            gtext: str = self.global_doc.text
            matches: List[LexicalSpan] = list(map(
                match_to_span, self.pattern.finditer(text)))
            if len(matches) > 0:
                tl: int = len(text) + coff
                start: int = matches[0].begin
                end: int = matches[-1].end
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f'coff: {coff}, start={start}, end={end}')
                if start > coff:
                    fms = LexicalSpan(coff, start - 1)
                    matches.insert(0, fms)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f'adding offset match: {start}, {coff}: ' +
                                     f'<<{gtext[fms[0]:fms[1]]}>>')
                if tl > end:
                    matches.append(LexicalSpan(end, tl))
                while len(matches) > 0:
                    span: LexicalSpan = matches.pop(0)
                    sent: FeatureSentence = None
                    empty: bool = False
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            f'match {span}: <{gtext[span[0]:span[1]]}>')
                    if span.begin > start:
                        sent = self._create_sent(
                            LexicalSpan(start, span.begin - 1))
                        empty = sent is None
                        if not empty:
                            if len(sents) > 0:
                                sdoc = FeatureDocument((sents[-1], sent))
                                sents[-1] = sdoc.to_sentence(delim='\n')
                            else:
                                sents.append(sent)
                            sent = None
                            empty = True
                        matches.insert(0, span)
                    if not empty and sent is None:
                        sent = self._create_sent(span)
                    if sent is not None:
                        sents.append(sent)
                    start = span.end + 1
        return iter(sents)

    def __call__(self) -> FeatureDocument:
        sents: Tuple[FeatureSentence] = tuple(self)
        return FeatureDocument(
            sents=sents,
            text='\n'.join(map(lambda s: s.text.strip(), sents)))


@dataclass
class GapSectionContainer(SectionContainer):
    """A container that fills in missing sections of text from a note with
    additional sections.

    """
    delegate: Note = field()
    """The note with the sections to be filled."""

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
            for gs in gaps:
                gsec = Section(
                    id=-1,
                    name=None,
                    container=sec_cont,
                    header_spans=(),
                    body_span=gs)
                ref_sec._copy_resources(gsec)
                gap_secs.append(gsec)
            sections.extend(gap_secs)
            sections.sort(key=lambda s: s.lexspan)
            sec: Section
            for sid, sec in enumerate(sections):
                sec.original_id = sec.id
                sec.id = sid
        return sections

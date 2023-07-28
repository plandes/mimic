"""Utility classes.

"""
__author__ = 'Paul Landes'

from typing import ClassVar, Tuple, List, Iterable, Sequence, Optional
from dataclasses import dataclass, field
import re
import logging
from zensols.nlp import (
    LexicalSpan, TokenContainer, FeatureSentence, FeatureDocument
)
from zensols.nlp.chunker import Chunker
from . import SectionContainer, Section, Note

logger = logging.getLogger(__name__)


@dataclass
class ListItemChunker(Chunker):
    """A :class:`.Chunker` that splits list item and enumerated lists into
    separate sentences.  Matched sentences are given if used as an iterable.

    """
    DEFAULT_SPAN_PATTERN: ClassVar[re.Pattern] = re.compile(
        r'^((?:[0-9-+]+|[a-zA-Z]+:)[^\n]+)$', re.MULTILINE)
    """The default list item regular expression, which uses an initial character
    item notation or an initial enumeration digit.

    """
    pattern: re.Pattern = field(default=DEFAULT_SPAN_PATTERN)
    """The list regular expression, which defaults to
    :obj:`DEFAULT_SPAN_PATTERN`.

    """
    def _create_container(self, span: LexicalSpan) -> Optional[TokenContainer]:
        doc: FeatureDocument = self.doc.get_overlapping_document(span)
        sent: FeatureSentence = doc.to_sentence()
        sent.strip()
        if sent.token_len > 0:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'narrowed sent: <{sent.text}>')
            return sent

    def _merge_containers(self, a: TokenContainer, b: TokenContainer) -> \
            TokenContainer:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'merging: {a}||{b}')
        return FeatureDocument((a, b)).to_sentence(delim='\n')

    def to_document(self, conts: Iterable[TokenContainer]) -> FeatureDocument:
        sents: Tuple[FeatureSentence] = tuple(conts)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('creating doc from:')
            for s in sents:
                logger.debug(f'  {s}')
        return FeatureDocument(
            sents=sents,
            text='\n'.join(map(lambda s: s.text, sents)))


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

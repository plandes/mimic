"""Paragraph factories.

"""
__author__ = 'Paul Landes'

from typing import List, Set, Iterable, Optional, ClassVar
from dataclasses import dataclass, field
import logging
import re
from zensols.nlp import (
    LexicalSpan, FeatureToken, FeatureDocument, FeatureSentence
)
from zensols.nlp.chunker import ParagraphChunker, ListItemChunker
from zensols.mimic import Section, ParagraphFactory, MimicTokenDecorator

logger = logging.getLogger(__name__)


class WhitespaceParagraphFactory(ParagraphFactory):
    """A simple paragraph factory that splits on whitespace.

    """
    SEPARATOR_REGEX: ClassVar[re.Pattern] = re.compile(r'\n[\s.]*\n')

    def create(self, sec: Section) -> Iterable[FeatureDocument]:
        par_spans: List[LexicalSpan] = []
        bspan: LexicalSpan = sec.body_span
        bdoc: LexicalSpan = sec.body_doc
        marks: List[int] = [bspan.begin]
        for i in self.SEPARATOR_REGEX.finditer(sec.body):
            marks.extend((i.start() + bspan.begin, i.end() + bspan.begin))
        marks.append(bspan.end)
        mi = iter(marks)
        for beg in mi:
            par_spans.append(LexicalSpan(beg, next(mi)))
        ps: LexicalSpan
        for ps in par_spans:
            para: FeatureDocument = bdoc.get_overlapping_document(ps)
            para.text = ' '.join(map(lambda s: s.text.strip(), para))
            yield para


@dataclass
class ChunkingParagraphFactory(ParagraphFactory):
    """A paragraph factory that uses :mod:`zensols.nlp.chunker` chunking to
    split paragraphs and MIMIC lists.

    """
    MIMIC_SPAN_PATTERN: ClassVar[re.Pattern] = re.compile(
        r'(.+?)(?:(?=[\n.]{2})|\Z)', re.MULTILINE | re.DOTALL)
    """MIMIC regular expression adds period, which is used in notes to separate
    paragraphs.

    """
    min_sent_len: int = field()
    """Minimum sentence length in tokens to be kept."""

    min_list_norm_matches: int = field()
    """The minimum amount of list matches needed to use the list item chunked
    version of the section.

    """
    max_sent_list_len: int = field()
    """The maximum lenght a sentence can be to keep it chunked as a list.
    Otherwise very long sentences form from what appear to be front list
    syntax.

    """
    include_section_headers: bool = field()
    """Whether to include section headers in the output."""

    filter_sent_text: Set[str] = field()
    """A set of sentence norm values to filter from replaced documents."""

    def _norm_list(self, doc: FeatureDocument) -> FeatureDocument:
        """Normalize itemized or enumerated lists if found."""
        chunker = ListItemChunker(doc)
        list_doc: FeatureDocument = chunker()
        if len(list_doc.sents) > 0:
            max_sent_len: int = max(map(lambda s: len(s.norm), list_doc.sents))
            if len(list_doc.sents) > self.min_list_norm_matches and \
               max_sent_len < self.max_sent_list_len:
                doc = list_doc
        return doc

    def _clone_norm_doc(self, doc: FeatureDocument) -> FeatureDocument:
        """Replace mangled token norms from original text."""
        clone: FeatureDocument = doc.clone()
        for tok in clone.token_iter():
            tok.norm = tok.text
        clone.clear()
        return clone

    def _norm_doc(self, parent: FeatureDocument, doc: FeatureDocument) -> \
            Optional[FeatureDocument]:
        """Normalize the document.  This removes empty sentences, MIMIC
        separators (long dashes) and chunks item lists.

        :param parent: the note document

        :param doc: the section document

        """
        def filter_toks(t: FeatureToken) -> bool:
            feat = t.mimic_ if hasattr(t, 'mimic_') else None
            return feat != MimicTokenDecorator.SEPARATOR_TOKEN_FEATURE and \
                len(t.norm.strip()) > 0

        def filter_sents(s: FeatureSentence) -> bool:
            return s.token_len > self.min_sent_len and \
                s.norm not in self.filter_sent_text

        # remove newlines that have space around them
        sent: FeatureSentence
        for sent in doc.sents:
            sent.tokens = tuple(filter(filter_toks, sent.token_iter()))
        doc.clear()

        # remove periods on lines by themselves
        doc.sents = tuple(filter(filter_sents, doc.sents))
        doc.clear()

        # chunk enumerated and itemized lists into sentences (if any)
        if self.min_list_norm_matches > 0:
            doc = self._norm_list(doc)
        # replace mangled token norms from original text
        doc = self._clone_norm_doc(doc)
        if doc.token_len > 0:
            doc.text = parent.text[doc.lexspan.begin:doc.lexspan.end]
        if doc.token_len > 0:
            doc.reindex()
            return doc

    def create(self, sec: Section) -> Iterable[FeatureDocument]:
        include_headers: bool = self.include_section_headers
        parent: FeatureDocument = sec.container.doc
        doc: FeatureDocument
        span: LexicalSpan
        if include_headers:
            doc, span = sec.doc, sec.lexspan
        else:
            doc, span = sec.body_doc, sec.body_span
        assert isinstance(doc, FeatureDocument)
        # some section data is in the header, and thus, has no body
        if len(doc.sents) == 0:
            return []

        # chunk sections into paragraphs
        pc = ParagraphChunker(
            pattern=self.MIMIC_SPAN_PATTERN,
            doc=parent.clone(),
            sub_doc=doc,
            char_offset=span.begin)

        # normalize documents and prune empty (resulting from pruned sententces)
        return filter(lambda d: d is not None,
                      map(lambda d: self._norm_doc(parent, d), pc))

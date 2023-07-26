"""Utility classes.

"""
__author__ = 'Paul Landes'

from typing import List, Iterable, Sequence
from dataclasses import dataclass, field
from zensols.nlp import LexicalSpan, FeatureDocument
from . import SectionContainer, Section, Note


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

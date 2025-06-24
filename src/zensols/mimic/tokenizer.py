"""Modify the spaCy parser configuration to deal with the MIMIC-III dataset.

"""
__author__ = 'Paul Landes'

from typing import Tuple, Union, Optional, ClassVar, List
from dataclasses import dataclass, field
import logging
import re
from frozendict import frozendict
from spacy.language import Language
from spacy.lang.char_classes import ALPHA
from spacy.util import compile_infix_regex
from zensols.nlp import Component, FeatureTokenDecorator, FeatureToken

logger = logging.getLogger(__name__)


@dataclass
class MimicTokenizerComponent(Component):
    """Modifies the spacCy tokenizer to split on colons (``:``) to capture more
    MIMIC-III mask tokens.

    """
    def init(self, model: Language):
        inf = list(model.Defaults.infixes)
        SCHARS = ',:;/=@#%+.-'
        # split on newlines; handle newline as an infix token
        inf.insert(0, r'\n')
        # split on special characters before
        inf.insert(1, r"(?<=\*\*\])(?:[{s}])(?=[{a}0-9])".format(
            a=ALPHA, s=SCHARS))
        inf.insert(2, r"(?<=\*\*\])(?=[{a}0-9])".format(a=ALPHA))
        # split on special characters after
        inf.insert(3, r"(?<=[{a}0-9])(?:[{s}])(?=\[\*\*)".format(
            a=ALPHA, s=SCHARS))
        inf.insert(4, r"(?<=[{a}0-9])(?=\[\*\*)".format(a=ALPHA))
        # split on what look to be ranges or hospital1-hospital2
        inf.insert(3, r"(?<=\*\*\])(?:[{s}])(?=\[\*\*)".format(s=SCHARS))
        infix_re = compile_infix_regex(inf)
        model.tokenizer.infix_finditer = infix_re.finditer

    def __hash__(self) -> int:
        return super().__hash__()


@dataclass
class MimicTokenDecorator(FeatureTokenDecorator):
    """Contains the MIMIC-III regular expressions and other patterns to annotate
    and normalized feature tokens.  The class finds mask tokens and
    separators (such as a long string of dashes or asterisks).

    Attribute :obj:`onto_mapping` is a mapping from the MIMIC symbol in
    :obj:`token_entities` (2nd value in tuple) to Onto Notes 5, which is used as
    the NER symbol in spaCy.

    """
    TOKEN_FEATURE_ID: ClassVar[str] = 'mimic_'
    """The feature ID to use for MIMIC-III tokens."""

    ONTO_FEATURE_ID: ClassVar[str] = 'onto_'
    """The feature ID to use for the Onto Notes 5 (:obj:`onto_mapping`)."""

    MASK_REGEX: ClassVar[re.Pattern] = re.compile(r'\[\*\*([^\*]+)\*\*\]')
    """Matches mask tokens."""

    MASK_TOKEN_FEATURE: ClassVar[str] = 'mask'
    """The value given from entity :obj:`TOKEN_FEATURE_ID` for mask tokens
    (i.e. ``[**First Name**]``).

    """
    SEPARATOR_TOKEN_FEATURE: ClassVar[str] = 'separator'
    """The value name of separators defined by :obj:`SEP_REGEX`.

    """
    SEP_REGEX: ClassVar[re.Pattern] = re.compile(r'(_{5,}|[*]{5,}|[-]{5,})')
    """Matches text based separators such as a long string of dashes."""

    UNKNOWN_ENTITY: ClassVar[str] = '<UNKNOWN>'
    """The mask nromalized token form for unknown MIMIC entity text
    (i.e. First Name).

    """
    _REGEXES: ClassVar[List] = [[MASK_REGEX, MASK_TOKEN_FEATURE],
                                [SEP_REGEX, SEPARATOR_TOKEN_FEATURE]]

    token_entities: Tuple[Tuple[Union[re.Pattern, str]], str, Optional[str]] = \
        field(default=(
            (re.compile(r'^First Name'), 'FIRSTNAME', 'PERSON'),
            (re.compile(r'^Last Name'), 'LASTNAME', 'PERSON'),
            (re.compile(r'^21\d{2}-\d{1,2}-\d{1,2}$'), 'DATE', 'DATE')))
    """A list of psuedo token patterns and a string to replace with the
    respective match.

    """
    token_replacements: Tuple[Tuple[Union[re.Pattern, str], str]] = field(
        default=())
    """A list of token text to replaced as the normalized token text."""

    def __post_init__(self):
        self.onto_mapping = {}
        self._compile_regexes('token_entities')
        self._compile_regexes('token_replacements')
        self.onto_mapping = frozendict(self.onto_mapping)

    def _compile_regexes(self, attr: str):
        repls = []
        ent: str
        pat: Union[re.Pattern, str]
        for pat, ent, onto_name in getattr(self, attr):
            if isinstance(pat, str):
                pat = re.compile(pat)
            repls.append((pat, ent))
            if onto_name is not None:
                self.onto_mapping[ent] = onto_name
        setattr(self, attr, tuple(repls))

    def decorate(self, token: FeatureToken):
        pat: re.Pattern
        ent: str
        oid: str = FeatureToken.NONE
        matched: bool = False
        for pat, ent in self._REGEXES:
            m: re.Match = pat.match(token.norm)
            if m is not None:
                matched = True
                setattr(token, self.TOKEN_FEATURE_ID, ent)
                if ent == self.MASK_TOKEN_FEATURE:
                    token.norm: str = self.UNKNOWN_ENTITY
                    mask_val: str = m.group(1)
                    for regex, repl in self.token_entities:
                        if regex.match(mask_val) is not None:
                            oid = self.onto_mapping.get(repl, FeatureToken.NONE)
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug(f'dec: {self.TOKEN_FEATURE_ID} ' +
                                             f' -> {ent}, norm -> {mask_val}')
                            token.norm = repl
                            break
                break
        if not matched:
            setattr(token, self.TOKEN_FEATURE_ID,
                    FeatureToken.NONE)
            repl: str
            for pat, repl in self.token_replacements:
                m: re.Match = pat.match(token.norm)
                if m is not None:
                    matched = True
                    token.norm = repl
                    break
        setattr(token, self.ONTO_FEATURE_ID, oid)

"""Has a parser for medical section identification.

"""
__author__ = 'Paul Landes'

from typing import Tuple
from dataclasses import dataclass, field
import re
from spacy.language import Language
from spacy.lang.char_classes import ALPHA
from spacy.symbols import ORTH
from spacy.util import compile_infix_regex
from spacy.tokens import Token
from zensols.nlp import Component, SpacyFeatureTokenDecorator, FeatureToken


@dataclass
class MimicTokenizerComponent(Component):
    """Modifies the spacCy tokenizer to split on colons (``:``) to capture more
    MIMIC III pseudo tokens.

    """
    def init(self, model: Language):
        inf = list(model.Defaults.infixes)
        # split on colons
        inf.insert(0, r"(?<=[{a}0-9])(?:[:])(?=\[)".format(a=ALPHA))
        # split on newlines; handle newline as an infix token
        inf.insert(0, r'\n')
        infix_re = compile_infix_regex(inf)
        model.tokenizer.infix_finditer = infix_re.finditer

    def __hash__(self) -> int:
        return super().__hash__()


@dataclass
class MimicTokenDecorator(SpacyFeatureTokenDecorator):
    """Contains the MIMIC III regular expressions and other patterns to annotate
    and normalized feature tokens.  The class finds pseudo tokens and
    separators (such as a long string of dashes or asterisks).

    """
    TOKEN_FEATURE_ID = 'mimic_'
    """The feature ID to use for MIMIC III tokens."""

    PSEUDO_REGEX = re.compile(r'\[\*\*([^\*]+)\*\*\]')
    """Matches pseudo tokens."""

    SEP_REGEX = re.compile(r'(_{5,}|[*]{5,})')
    """Matches text based separators such as a long string of dashes."""

    _REGEXES = [['pseudo', PSEUDO_REGEX],
                ['separator', SEP_REGEX]]

    token_replaces: Tuple[Tuple[re.Pattern, str]] = field(
        default=((re.compile(r'^First Name'), 'FIRSTNAME'),
                 (re.compile(r'^Last Name'), 'LASTNAME'),
                 (re.compile(r'^21\d{2}-\d{1,2}-\d{1,2}$'), 'DATE')))
    """A list of psuedo token patterns and a string to replace with the respective
    match.

    """
    def decorate(self, spacy_tok: Token, feature_token: FeatureToken):
        ent: str
        pat: re.Pattern
        for ent, pat in self._REGEXES:
            m: re.Match = pat.match(feature_token.norm)
            if m is None:
                setattr(feature_token, self.TOKEN_FEATURE_ID,
                        FeatureToken.NONE)
            else:
                setattr(feature_token, self.TOKEN_FEATURE_ID, ent)
                if ent == 'pseudo':
                    pseudo_val = m.group(1)
                    for regex, repl in self.token_replaces:
                        if regex.match(pseudo_val) is not None:
                            feature_token.norm = repl
                            break
                break

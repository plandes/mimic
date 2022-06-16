"""A utility library for parsing the MIMIC-III corpus

"""
__author__ = 'Paul Landes'

from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Application(object):
    """A utility library for parsing the MIMIC-III corpus

    """
    dry_run: bool = field(default=False)
    """If given, don't do anything, just act like it."""

    def proto(self):
        """Prototype test."""
        if logger.isEnabledFor(logging.INFO):
            logger.info('do something more')

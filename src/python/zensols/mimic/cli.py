"""Command line entry point to the application.

"""
__author__ = 'Paul Landes'

from typing import List, Any, Dict, Type
import sys
from zensols.cli import ActionResult, CliHarness
from zensols.cli import ApplicationFactory as CliApplicationFactory
from . import Corpus


class ApplicationFactory(CliApplicationFactory):
    def __init__(self, *args, **kwargs):
        kwargs['package_resource'] = 'zensols.mimic'
        super().__init__(*args, **kwargs)

    @classmethod
    def get_corpus(cls: Type) -> Corpus:
        """Get the MIMIC-III corpus."""
        harness = cls.create_harness()
        return harness['mimic_corpus']


def main(args: List[str] = sys.argv, **kwargs: Dict[str, Any]) -> ActionResult:
    harness: CliHarness = ApplicationFactory.create_harness(relocate=False)
    harness.invoke(args, **kwargs)

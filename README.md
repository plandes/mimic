# MIMIC III Corpus Parsing

[![PyPI][pypi-badge]][pypi-link]
[![Python 3.9][python39-badge]][python39-link]
[![Python 3.10][python310-badge]][python310-link]
[![Build Status][build-badge]][build-link]

A utility library for parsing the [MIMIC-III] corpus.  This uses [spaCy] and
extends the [zensols.mednlp] to parse the [MIMIC-III] medical note dataset,
which include:

* Re-groups pseudo tokens as a single token.
* Modifies the [spaCy] tokenizer to deal with pseudo tokens--specifically not
  break on syntax used in the pseudo tokens.


## Documentation

See the [full documentation](https://plandes.github.io/mimic/index.html).
The [API reference](https://plandes.github.io/mimic/api.html) is also
available.


## Obtaining

The easiest way to install the command line program is via the `pip` installer:
```bash
pip3 install zensols.mimic
```

Binaries are also available on [pypi].


## Installation

1. Install the package: `pip3 install zensols.mimic`
2. Install the database (either Postgres, which is tested, or SQLite).  For
   Postgres, load MIMIC-III by following the [Postgres instructions].  An
   SQLite database file can also be used, but it has not been tested and it
   might need more configuration (resource library) work.  Refer to the [SQLite
   instructions] to create the file if you chose to try this method.


## Changelog

An extensive changelog is available [here](CHANGELOG.md).


## License

[MIT License](LICENSE.md)

Copyright (c) 2022 Paul Landes


<!-- links -->
[pypi]: https://pypi.org/project/zensols.mimic/
[pypi-link]: https://pypi.python.org/pypi/zensols.mimic
[pypi-badge]: https://img.shields.io/pypi/v/zensols.mimic.svg
[python39-badge]: https://img.shields.io/badge/python-3.9-blue.svg
[python39-link]: https://www.python.org/downloads/release/python-390
[python310-badge]: https://img.shields.io/badge/python-3.10-blue.svg
[python310-link]: https://www.python.org/downloads/release/python-3100
[build-badge]: https://github.com/plandes/mimic/workflows/CI/badge.svg
[build-link]: https://github.com/plandes/mimic/actions

[MIMIC-III]: https://physionet.org/content/mimiciii-demo/1.4/
[spaCy]: https://spacy.io
[zensols.mednlp]: https://github.com/plandes/mednlp

[SQLite instructions]: https://github.com/MIT-LCP/mimic-code/tree/main/mimic-iii/buildmimic/sqlite
[Postgres instructions]: https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iii/buildmimic/postgres/README.md

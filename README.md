# MIMIC III Corpus Parsing

[![PyPI][pypi-badge]][pypi-link]
[![Python 3.7][python37-badge]][python37-link]
[![Python 3.8][python38-badge]][python38-link]
[![Python 3.9][python39-badge]][python39-link]
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


## Changelog

An extensive changelog is available [here](CHANGELOG.md).


## License

[MIT License](LICENSE.md)

Copyright (c) 2022 Paul Landes


<!-- links -->
[pypi]: https://pypi.org/project/zensols.mimic/
[pypi-link]: https://pypi.python.org/pypi/zensols.mimic
[pypi-badge]: https://img.shields.io/pypi/v/zensols.mimic.svg
[python37-badge]: https://img.shields.io/badge/python-3.7-blue.svg
[python37-link]: https://www.python.org/downloads/release/python-370
[python38-badge]: https://img.shields.io/badge/python-3.8-blue.svg
[python38-link]: https://www.python.org/downloads/release/python-380
[python39-badge]: https://img.shields.io/badge/python-3.9-blue.svg
[python39-link]: https://www.python.org/downloads/release/python-390
[build-badge]: https://github.com/plandes/mimic/workflows/CI/badge.svg
[build-link]: https://github.com/plandes/mimic/actions

[MIMIC-III]: https://physionet.org/content/mimiciii-demo/1.4/
[spaCy]: https://spacy.io
[zensols.mednlp]: https://github.com/plandes/mednlp

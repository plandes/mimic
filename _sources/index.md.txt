# MIMIC III Corpus Parsing

[![PyPI][pypi-badge]][pypi-link]
[![Python 3.11][python311-badge]][python311-link]
[![Build Status][build-badge]][build-link]

A utility library for parsing the [MIMIC-III] corpus.  This uses [spaCy] and
extends the [zensols.mednlp] to parse the [MIMIC-III] medical note dataset.
Features include:

* Creates both natural language and medical features from medical notes.  The
  latter is generated using linked entity concepts parsed with [MedCAT] via
  [zensols.mednlp].
* Modifies the [spaCy] tokenizer to chunk masked tokens.  For example, `[`,
  `**`, `First`, `Name` `**` `]` becomes `[**First Name**]`.
* Provides a clean Pythonic object oriented representation of MIMIC-III
  admissions and medical notes.
* Interfaces MIMIC-III data as a relational database (either PostgreSQL or
  SQLite).
* Paragraph chunking using the most common syntax/physician templates provided
  in the MIMIC-III dataset.


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
2. Install the database (either PostgreSQL or SQLite).


## Configuration

After a database is installed it must be configured in a new file `~/.mimicrc`
that you create.  This INI formatted file also specifies where to cache data:
```ini
[default]
# the directory where cached data is stored
data_dir = ~/directory/to/cached/data
```
If this file doesn't exist, it must be specified with the `--config` option.


### SQLite

SQLite is the default database used for MIMIC-III access, but, it is slower and
not as well tested compared to the [PostgreSQL](PostgreSQL) driver.  See the
[SQLite database file] using the [SQLite instructions] to create the SQLite
file from MIMIC-III if you need database access.

Once you create the file, configure it with the API using the following
additional configuration in the `--config` specified file is also necessary (or in
`~/.mimicrc`):
```ini
[mimic_sqlite_conn_manager]
db_file = path: <some directory>/mimic3.sqlite3
```

### PostgreSQL

PostgreSQL is the preferred way to access MIMIC-II for this API.  The MIMIC-III
database can be loaded by following the [PostgreSQL instructions], or consider
the [PostgreSQL Docker image].  Then configure the database by adding the
following to `~/.mimicrc`:
```ini
[mimic_default]
resources_dir = resource(zensols.mimic): resources
sql_resources = ${resources_dir}/postgres
conn_manager = mimic_postgres_conn_manager

[mimic_db]
database = <needs a value>
host = <needs a value>
port = <needs a value>
user = <needs a value>
password = <needs a value>
```


The Python PostgreSQL client package is also needed (not needed for the
[SQLite](#sqlite-configuration) installs), which can be installed with:
```bash
pip3 install zensols.dbpg
```


## Usage

The [Corpus] class is the data access object used to read and parse the corpus:

```python
# get the MIMIC-III corpus data acceess object
>>> from zensols.mimic import ApplicationFactory
>>> corpus = ApplicationFactory.get_corpus()

# get an admission by hadm_id
>>> adm = corpus.hospital_adm_stash['165315']

# get the first discharge note (some have admissions have addendums)
>>> from zensols.mimic.regexnote import DischargeSummaryNote
>>> ds = adm.notes_by_category[DischargeSummaryNote.CATEGORY][0]

# dump the note as a human readable section-by-section
>>> ds.write()
row_id: 12144
category: Discharge summary
description: Report
annotator: regular_expression
----------------------0:chief-complaint (CHIEF COMPLAINT)-----------------------
Unresponsiveness
-----------1:history-of-present-illness (HISTORY OF PRESENT ILLNESS)------------
The patient is a ...

# get features of the note useful in ML models as a Pandas dataframe
>>> df = ds.feature_dataframe

# get only medical features (CUI, entity, NER and POS tag) for the HPI section
>>> df[(df['section'] == 'history-of-present-illness') & (df['cui_'] != '-<N>-')]['norm cui_ detected_name_ ent_ tag_'.split()]
             norm      cui_           detected_name_     ent_ tag_
15        history  C0455527  history~of~hypertension  concept   NN
```

See the [application example], which gives a fine grain way of configuring the
API.


## Medical Note Segmentation

This package uses regular expressions to segment notes.  However, the
[zensols.mimicsid] uses annotations and a model trained by clinical informatics
physicians.  Using this package gives this enhanced segmentation without any
API changes.


## Citation

If you use this project in your research please use the following BibTeX entry:

```bibtex
@inproceedings{landes-etal-2023-deepzensols,
    title = "{D}eep{Z}ensols: A Deep Learning Natural Language Processing Framework for Experimentation and Reproducibility",
    author = "Landes, Paul  and
      Di Eugenio, Barbara  and
      Caragea, Cornelia",
    editor = "Tan, Liling  and
      Milajevs, Dmitrijs  and
      Chauhan, Geeticka  and
      Gwinnup, Jeremy  and
      Rippeth, Elijah",
    booktitle = "Proceedings of the 3rd Workshop for Natural Language Processing Open Source Software (NLP-OSS 2023)",
    month = dec,
    year = "2023",
    address = "Singapore, Singapore",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2023.nlposs-1.16",
    pages = "141--146"
}
```


## Changelog

An extensive changelog is available [here](CHANGELOG.md).


## Community

Please star this repository and let me know how and where you use this API.
Contributions as pull requests, feedback and any input is welcome.


## License

[MIT License](LICENSE.md)

Copyright (c) 2022 - 2025 Paul Landes


<!-- links -->
[pypi]: https://pypi.org/project/zensols.mimic/
[pypi-link]: https://pypi.python.org/pypi/zensols.mimic
[pypi-badge]: https://img.shields.io/pypi/v/zensols.mimic.svg
[python311-badge]: https://img.shields.io/badge/python-3.11-blue.svg
[python311-link]: https://www.python.org/downloads/release/python-3110
[build-badge]: https://github.com/plandes/mimic/workflows/CI/badge.svg
[build-link]: https://github.com/plandes/mimic/actions

[MIMIC-III]: https://physionet.org/content/mimiciii-demo/1.4/
[MedCAT]: https://github.com/CogStack/MedCAT
[spaCy]: https://spacy.io
[zensols.mednlp]: https://github.com/plandes/mednlp

[SQLite instructions]: https://github.com/MIT-LCP/mimic-code/tree/main/mimic-iii/buildmimic/sqlite
[PostgreSQL instructions]: https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iii/buildmimic/postgres/README.md
[PostgreSQL Docker image]: https://github.com/plandes/mimicdb
[SQLite database file]: https://github.com/plandes/mimicdbsqlite
[Corpus]: https://plandes.github.io/mimic/api/zensols.mimic.html#zensols.mimic.corpus.Corpus
[application example]: https://github.com/plandes/mimic/blob/master/example/shownote.py
[zensols.mimicsid]: https://github.com/plandes/mimicsid

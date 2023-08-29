# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


## [Unreleased]


### Removed
- `NoteFactor`'s `section` parameter has been removed in favor of creating
  default notes with `create_default`.

### Added
- A new `DefaultNoteFactory` that always creates default/no-section notes.

### Changed
- Faster note to admission ID resolution in database for faster preemptive note
  parsing.
- `NoteFactory.create_default` to create new default/no-section notes.


## [1.4.1] - 2023-08-25
### Changed
- PostreSQL is now optional, and to use it, it the [zensols.dbsql] needs to be
  installed (see the [README](README.md)].
- Switch to `MultiProcessDefaultStash`, which allows for swapping in other
  multiprocessing implementations.


## [1.4.0] - 2023-08-16
Downstream moderate risk update release.

### Changes
- A cleaner CLI for MIMIC note access.
- Default to section based `Note.write`.
- `NoteStash` is now primed by upstream stashes for [zensols.mimicsid] MedSecId
  model install.
- Tokenzier separates on commas to find more MIMIC-III masks.
- More MIMIC-III mask tags created and others regular expressions fixed.
- Update to [zensols.mednlp] 1.4.0.

### Added
- SQLite support for the MIMIC-III database.
- Feature to clear cached notes from the `Corpus` class.
- CLI actions to write an admission to disk an to get random `hadm_ids`.


## [1.3.1] - 2023-06-25
### Changed
- Add default and settings for changing the MIMIC-III database name.


## [1.3.0] - 2023-06-20
### Changed
- Upgrade to [zensols.mednlp] 1.3.0.


## [1.2.0] - 2023-06-09
### Changed
- Upgrade to [zensols.mednlp] 1.2.0.
- Move admission sample to `Admission` persister.
- Narrow body `FeatureDocument`s using right exclusive spans.

### Added
- `Note.annotator` property.
- `Note` and `Admission` accessors to `Corpus` container class.
- SQL `Note` counts.


## [1.1.0] - 2023-04-05
### Changed
- MIMIC notes write changes
- Move application methods from `Corpus` to the application.
- Fixed procedure data to hospital admission class.


### Changed
- Admission and note write semantics.


## [1.0.0] - 2023-02-02
### Changed
- Updated [zensols.mednlp] to 1.0.0.


## [0.1.1] - 2022-10-02
### Changed
- Upgrade dependencies.


## [0.1.0] - 2022-10-01
Significant feature release.

### Added
- Special MIMIC-III tokenization to deal with pseudo tokens.
- Add spaCy `._.` token features extracted from MIMIC-III pseudo tokens.
- Combine [zensols.mednlp] document parser with MIMIC-III features.
- Build out MIMIC-III container classes.
- Add section and paragraph segmentation code and container classes.
- Add reusable/shared data space for parsed documents.
- Add Postgres database support.


## [0.0.1] - 2022-05-04
### Added
- Initial version.


<!-- links -->
[Unreleased]: https://github.com/plandes/mimic/compare/v1.4.1...HEAD
[1.4.1]: https://github.com/plandes/mimic/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/plandes/mimic/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/plandes/mimic/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/plandes/mimic/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/plandes/mimic/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/plandes/mimic/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/plandes/mimic/compare/v0.1.1...v1.0.0
[0.1.1]: https://github.com/plandes/mimic/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/plandes/mimic/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/plandes/mimic/compare/v0.0.0...v0.0.1

[zensols.mednlp]: https://github.com/plandes/mednlp
[zensols.mimicsid]: https://github.com/plandes/mimicsid
[zensols.dbsql]: https://github.com/plandes/dbutilpg

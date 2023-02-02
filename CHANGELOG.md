# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).


## [Unreleased]

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
[Unreleased]: https://github.com/plandes/mimic/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/plandes/mimic/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/plandes/mimic/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/plandes/mimic/compare/v0.0.0...v0.0.1

[zensols.mednlp]: https://github.com/plandes/mednlp

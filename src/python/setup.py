from pathlib import Path
from zensols.pybuild import SetupUtil

su = SetupUtil(
    setup_path=Path(__file__).parent.absolute(),
    name="zensols.mimic",
    package_names=['zensols', 'resources'],
    package_data={'': ['*.conf', '*.json', '*.yml', '*.sql']},
    description='MIMIC III Corpus Parsing',
    user='plandes',
    project='mimic',
    keywords=['tooling'],
).setup()

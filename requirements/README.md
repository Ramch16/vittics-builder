# Dependency locks

`dev.lock` pins every package (with SHA-256 hashes) needed to run the test suite on Linux, resolved with
pip-compile 7.6.2 from `pyproject.toml` (`[dev]` extra) on Python 3.13. CI installs it with
`--require-hashes` on Python 3.12 (`locked-install` job).

    pip install --require-hashes -r requirements/dev.lock
    pip install --no-deps -e .

To refresh after changing dependencies:

    pip-compile --extra dev --generate-hashes --strip-extras --allow-unsafe --output-file requirements/dev.lock pyproject.toml

macOS works with the same lock. Windows needs `colorama` for pytest, which this lock does not include; use
`pip install -e ".[dev]"` there.

"""Which build is this? The version number alone is not enough: the same 0.26.0 can be a release or any commit
after it. Installers record the commit they were built from (desktop/scripts/build_server.py writes _build.py);
a source checkout asks git."""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from . import __version__


@lru_cache(maxsize=1)
def commit() -> str:
    try:
        from ._build import COMMIT
        return str(COMMIT)
    except ImportError:
        pass
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        return ""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=root, capture_output=True, text=True,
                             timeout=3).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, capture_output=True,
                               text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return sha + ("-dirty" if sha and dirty else "")


def label() -> str:
    """'0.26.0+7784264': the version and the commit it was built from (just the version when unknown)."""
    sha = commit()
    return f"{__version__}+{sha}" if sha else __version__

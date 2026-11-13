"""Which build is this? The version number alone is not enough: the same 0.26.0 can be a release or any commit
after it. Installers record the commit they were built from (desktop/scripts/build_server.py writes _build.py);
a source checkout reads it from .git. Nothing here runs git: the label is read while a request is served, and
`git status` on a fresh Windows checkout takes seconds."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from . import __version__


def git_commit(root: Path) -> str:
    """The short commit a source checkout is on, read from its .git folder (worktrees and packed refs included)."""
    try:
        git = root / ".git"
        if git.is_file():                                   # a worktree: .git is a file naming its own folder
            target = git.read_text(encoding="utf-8").strip()
            if not target.startswith("gitdir:"):
                return ""
            git = Path(target[len("gitdir:"):].strip())
            git = git if git.is_absolute() else (root / git).resolve()
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head[:7]                                  # a detached HEAD is the commit itself
        ref = head[len("ref:"):].strip()
        common = (git / (git / "commondir").read_text(encoding="utf-8").strip()).resolve() \
            if (git / "commondir").is_file() else git
        for base in (git, common):
            if (base / ref).is_file():
                return (base / ref).read_text(encoding="utf-8").strip()[:7]
        packed = common / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref):
                    return line.split()[0][:7]
    except (OSError, ValueError, IndexError):
        pass
    return ""


@lru_cache(maxsize=1)
def commit() -> str:
    try:
        from ._build import COMMIT
        return str(COMMIT)
    except ImportError:
        return git_commit(Path(__file__).resolve().parent.parent)


def label() -> str:
    """'0.26.0+7784264': the version and the commit it was built from (just the version when unknown)."""
    sha = commit()
    return f"{__version__}+{sha}" if sha else __version__

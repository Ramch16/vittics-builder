"""Conservative, deterministic review selection; never an acceptance verdict."""
from pathlib import PurePosixPath
import re


SENSITIVE = re.compile(
    r'auth|permission|credential|secret|token|password|payment|billing|migration|'
    r'encrypt|sandbox|security|deploy|rollback|workflow|product\.json', re.I)


def review_level(task, paths):
    """Only plain documentation qualifies for reduced review. Unknown is standard.

    Risk hints can increase review, never lower it. All release gates still apply.
    Caller supplies actual changed paths, including removed/renamed source paths.
    """
    description = ' '.join(str(task.get(k, '')) for k in ('title', 'description', 'role'))
    if SENSITIVE.search(description) or any(SENSITIVE.search(p) for p in paths):
        return 'thorough', 'Sensitive task or changed path'
    if task.get('attempts', 0):
        return 'standard', 'Rework retains code review and QA'
    if paths and all(
        not p.startswith('.') and '..' not in PurePosixPath(p).parts
        and PurePosixPath(p).suffix.lower() in {'.md', '.rst', '.txt'}
        and (p.startswith('docs/') or p.lower() in {'readme.md', 'contributing.md', 'changelog.md'})
        for p in paths
    ):
        return 'light', 'Plain documentation changes only'
    return 'standard', 'Executable, mixed, or unknown changes retain code review and QA'

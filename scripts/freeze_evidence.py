"""Freeze an evidence folder (Week 21): a manifest of every file's SHA-256 plus the source it came from.

    python scripts/freeze_evidence.py freeze evidence/week3        # writes evidence/week3/FREEZE.json
    python scripts/freeze_evidence.py verify evidence/week3        # exit 1 if any file changed, appeared or vanished

The manifest names the git commit and whether the working tree was clean. A freeze records the files as they
are; it does not make their contents true. Verify before quoting any number from a frozen folder.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

NAME = "FREEZE.json"


def _files(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and p.name != NAME}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def freeze(folder: Path) -> dict:
    manifest = {"frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "git_commit": _git("rev-parse", "HEAD") or None,
                "git_clean": _git("status", "--porcelain") == "",
                "python": sys.version.split()[0], "platform": platform.platform(),
                "files": _files(folder)}
    (folder / NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify(folder: Path) -> dict:
    manifest = json.loads((folder / NAME).read_text(encoding="utf-8"))
    now = _files(folder)
    then = manifest["files"]
    return {"changed": sorted(k for k in then if k in now and now[k] != then[k]),
            "missing": sorted(set(then) - set(now)), "added": sorted(set(now) - set(then)),
            "frozen_at": manifest["frozen_at"], "git_commit": manifest["git_commit"]}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("freeze", "verify"):
        print(__doc__)
        return 2
    folder = Path(argv[1])
    if argv[0] == "freeze":
        m = freeze(folder)
        print(f"froze {len(m['files'])} files at {m['git_commit']} (clean: {m['git_clean']})")
        return 0
    result = verify(folder)
    print(json.dumps(result, indent=2))
    return 0 if not (result["changed"] or result["missing"] or result["added"]) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

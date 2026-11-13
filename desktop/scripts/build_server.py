"""Bundle the Vittics Builder backend into one executable for the desktop app (PyInstaller).

Writes src-tauri/binaries/vittics-builder-server-<target triple>[.exe], the name Tauri looks for.
Run from the desktop folder with the Python that has Vittics Builder and PyInstaller installed
(npm run server uses `python3`; set VITTICS_PYTHON to use another, e.g. the repo's .venv).
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent
PACKAGE = REPO / "vittics_builder"


def target_triple() -> str:
    out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
    return next(line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("host: "))


def record_commit() -> Path | None:
    """Write the commit this build is made from into the package, so the app can say which build it is."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO, capture_output=True,
                               text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None                                 # not a git checkout: the app then shows the version only
    path = PACKAGE / "_build.py"
    path.write_text(f'COMMIT = "{sha}{"-dirty" if dirty else ""}"\n', encoding="utf-8")
    return path


def main() -> None:
    python = os.environ.get("VITTICS_PYTHON") or sys.executable
    if os.environ.get("VITTICS_PYTHON") is None and (REPO / ".venv").exists():
        venv = REPO / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python = str(venv) if venv.exists() else python
    name = f"vittics-builder-server-{target_triple()}"
    sep = ";" if os.name == "nt" else ":"
    data = [(PACKAGE / "static", "vittics_builder/static"), (PACKAGE / "default_org.yaml", "vittics_builder"),
            (PACKAGE / "skills", "vittics_builder/skills")]
    work = HERE / "build" / "pyinstaller"
    cmd = [python, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", name,
           "--distpath", str(HERE / "src-tauri" / "binaries"), "--workpath", str(work), "--specpath", str(work),
           "--collect-submodules", "vittics_builder", "--collect-submodules", "uvicorn",
           "--exclude-module", "playwright", "--exclude-module", "tkinter"]
    for src, dest in data:
        if src.exists():
            cmd += ["--add-data", f"{src}{sep}{dest}"]
    cmd.append(str(HERE / "scripts" / "server_entry.py"))
    print("Building", name, "with", python, "on", platform.platform())
    recorded = record_commit()
    try:
        subprocess.run(cmd, check=True, cwd=REPO)
    finally:
        if recorded:
            recorded.unlink(missing_ok=True)        # keep the working tree clean
    shutil.rmtree(work, ignore_errors=True)
    print("Wrote", HERE / "src-tauri" / "binaries" / (name + (".exe" if os.name == "nt" else "")))


if __name__ == "__main__":
    main()

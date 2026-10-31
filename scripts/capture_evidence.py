"""Record a verification capture: source identity, environment, commands, exit codes and redacted logs.

    python scripts/capture_evidence.py --out evidence/week1 --step "suite=python -m pytest -q -rs -p no:cacheprovider"

Each --step is NAME=COMMAND ({capture_dir} in COMMAND becomes the new capture folder), run from the
repository root with the offline mock provider forced and every secret-looking variable removed, so no
step can reach a paid API by accident. The capture folder holds one log per step (secrets redacted before
writing) and manifest.json with the SHA-256 of every file it wrote.
Nothing is uploaded. A blocked or failed step is recorded as such; it is never turned into a pass.

The manifest does not record environment variable values. Review logs before sharing them anyway.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.I)   # same names tools.SECRET_ENV scrubs
SECRET_SHAPES = [re.compile(p) for p in (r"sk-ant-[A-Za-z0-9_-]{8,}", r"sk-proj-[A-Za-z0-9_-]{8,}",
                                         r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
                                         r"AKIA[0-9A-Z]{16}", r"://[^/\s:@]+:[^/\s@]+@")]
SUMMARY = re.compile(r"(\d+) (passed|failed|skipped|xfailed|xpassed|errors?|deselected|warnings?)")


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv: list[str], **kw) -> str:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=60, **kw)
        return (out.stdout or out.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable ({type(exc).__name__})"


def redact(text: str, env: dict[str, str]) -> str:
    for name, value in os.environ.items():
        if SECRET_NAME.search(name) and len(value) >= 6:
            text = text.replace(value, f"[REDACTED:{name}]")
    for shape in SECRET_SHAPES:
        text = shape.sub(lambda m: "://[REDACTED]@" if m.group(0).startswith("://") else "[REDACTED]", text)
    return text


def safe_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not SECRET_NAME.search(k)}
    if any(k.startswith("GIT_CONFIG_KEY_") for k in os.environ):   # git needs KEY/VALUE/COUNT as a set;
        env = {k: v for k, v in env.items() if not k.startswith("GIT_CONFIG_")}   # values may hold credentials
    env["VITTICS_PROVIDER"] = "mock"           # tests force this too (tests/conftest.py); belt and braces
    return env


def source(audited: str | None) -> dict:
    git = lambda *a: run(["git", *a], cwd=ROOT)
    remote = re.sub(r"://[^@/]+@", "://", git("remote", "get-url", "origin"))
    head = git("rev-parse", "HEAD")
    info = {"remote": remote, "head": head, "tree": git("rev-parse", "HEAD^{tree}"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_paths": [line[3:] for line in git("status", "--porcelain").splitlines() if line.strip()]}
    info["dirty"] = bool(info["dirty_paths"])
    if audited:
        info["audited_head"] = audited
        info["audited_head_matches"] = audited == head
        if audited != head:
            info["changed_since_audit"] = git("diff", "--stat", audited, head).splitlines()[-1:] or []
    return info


def packages(py: str) -> dict[str, str]:
    """Versions of the packages that matter here, as installed for interpreter `py`."""
    probe = ("import importlib.metadata as m, platform\nprint('python', platform.python_version())\n"
             "for n in ('vittics-builder','pyyaml','anthropic','fastapi','uvicorn','starlette','pydantic','pytest',"
             "'httpx','playwright','mcp'):\n    try: print(n, m.version(n))\n"
             "    except m.PackageNotFoundError: print(n, 'not installed')")
    return dict(line.split(" ", 1) for line in run([py, "-c", probe]).splitlines() if " " in line)


def chromium(py: str) -> str:
    out = run([py, "-c", "from playwright.sync_api import sync_playwright\nwith sync_playwright() as p:\n"
               "    b = p.chromium.launch(); print(b.version); b.close()"])
    return out.splitlines()[-1] if out and "Error" not in out else "unavailable"


def environment() -> dict:
    return {"os": platform.platform(), "system": platform.system(), "machine": platform.machine(),
            "versions": {"git": run(["git", "--version"]), "node": run(["node", "--version"])}}


def counts(text: str) -> dict[str, int]:
    tail = [line for line in text.splitlines() if re.search(r"\b(passed|failed|error|no tests ran)\b", line)]
    found: dict[str, int] = {}
    for number, word in SUMMARY.findall(tail[-1] if tail else ""):
        found[word.rstrip("s") if word.startswith(("error", "warning")) else word] = int(number)
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="parent folder; a new <capture-id> folder is created in it")
    ap.add_argument("--step", action="append", default=[], help="NAME=COMMAND (repeatable)")
    ap.add_argument("--audited-head", help="the commit an earlier audit inspected, to compare with HEAD")
    ap.add_argument("--label", default="", help="short note stored in the manifest")
    args = ap.parse_args(argv)
    src = source(args.audited_head)
    capture_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{src['head'][:7]}"
    folder = (ROOT / args.out / capture_id) if not Path(args.out).is_absolute() else Path(args.out) / capture_id
    folder.mkdir(parents=True)
    env = safe_env()
    steps = []
    for spec in args.step:
        name, _, command = spec.partition("=")
        command = command.replace("{capture_dir}", str(folder.relative_to(ROOT) if folder.is_relative_to(ROOT) else folder))
        if not re.fullmatch(r"[a-z0-9-]+", name) or not command:
            raise SystemExit(f"--step must be name=command with a lowercase name: {spec!r}")
        started = utc()
        try:
            proc = subprocess.run(shlex.split(command), cwd=ROOT, env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=3600)
            status, code, text = ("passed" if proc.returncode == 0 else "failed"), proc.returncode, \
                proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else "")
        except FileNotFoundError as exc:
            status, code, text = "blocked", None, f"could not start: {exc}"
        except subprocess.TimeoutExpired:
            status, code, text = "blocked", None, "timed out after 3600 s"
        log = folder / f"{name}.log"
        log.write_text(redact(text, env), encoding="utf-8")
        argv0 = shlex.split(command)[0]
        interpreter = {"packages": packages(argv0), "chromium": chromium(argv0)} \
            if Path(argv0).name.startswith("python") else None
        steps.append({"name": name, "command": command, "interpreter": interpreter, "started_at": started, "ended_at": utc(),
                      "exit_code": code, "status": status, "counts": counts(text), "log": log.name,
                      "log_sha256": sha256(log)})
    extra = sorted(f for f in folder.rglob("*") if f.is_file() and f.suffix != ".log")
    outputs = {f.relative_to(folder).as_posix(): sha256(f) for f in extra}
    manifest = {"schema_version": 1, "outputs": outputs, "capture_id": capture_id, "data_kind": "observed", "label": args.label,
                "captured_at": utc(), "provider": "mock (VITTICS_PROVIDER=mock; secret-named variables removed)",
                "source": src, "environment": environment(), "steps": steps,
                "limitations": ["Counts are parsed from each log's last pytest summary line; the log is authoritative.",
                                "A passing mock run exercises orchestration, not AI coding quality."]}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(folder.relative_to(ROOT) if folder.is_relative_to(ROOT) else folder)
    return 0 if all(s["status"] == "passed" for s in steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())

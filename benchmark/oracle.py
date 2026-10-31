"""Independent evaluation of a benchmark task tree.

The oracle copies a final tree to a fresh temporary folder that no agent can write, adds the task's hidden
tests and the original public tests (so an agent cannot weaken them), runs pytest there, and returns per-check
results. It never runs inside an agent workspace.

    python -m benchmark.oracle validate            # check every task package (starter fails, reference passes)
    python -m benchmark.oracle evaluate T03 <tree>   # evaluate a final tree; prints JSON
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

TASKS = Path(__file__).resolve().parent / "tasks"
SKIP = {"__pycache__", ".pytest_cache", ".git"}


def task_dir(task_id: str) -> Path:
    [match] = [p for p in TASKS.iterdir() if p.is_dir() and p.name.split("-", 1)[0] == task_id]
    return match


def tree_sha256(root: Path) -> str:
    """SHA-256 over sorted relative paths and file bytes (the same tree hashes the same anywhere)."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and not SKIP & set(p.relative_to(root).parts)):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def _copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*SKIP))


def evaluate(task_id: str, tree: Path, timeout: int = 120) -> dict:
    """Run public + hidden tests against `tree` in an isolated copy. Returns checks, all_passed and hashes."""
    task = task_dir(task_id)
    with tempfile.TemporaryDirectory(prefix=f"oracle-{task_id}-") as tmp:
        work = Path(tmp) / "tree"
        _copy(tree, work)
        shutil.rmtree(work / "tests", ignore_errors=True)            # the frozen public tests, not the agent's copy
        _copy(task / "starter" / "tests", work / "tests")
        shutil.rmtree(work / "hidden_oracle", ignore_errors=True)
        _copy(task / "hidden", work / "hidden_oracle")
        report = Path(tmp) / "junit.xml"
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "SYSTEMROOT", "TMPDIR", "TEMP")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}",
                                   "tests", "hidden_oracle"], cwd=work, capture_output=True, text=True, timeout=timeout, env=env)
            exit_code, output = proc.returncode, (proc.stdout + proc.stderr)[-4000:]
        except subprocess.TimeoutExpired:
            return {"task_id": task_id, "checks": [], "all_passed": None, "exit_code": None,
                    "output": f"oracle timed out after {timeout}s", "evaluated_tree_sha256": tree_sha256(tree)}
        checks = []
        if report.exists():
            for case in ET.parse(report).getroot().iter("testcase"):
                failed = any(child.tag in ("failure", "error") for child in case)
                skipped = any(child.tag == "skipped" for child in case)
                checks.append({"id": f"{case.get('classname')}::{case.get('name')}",
                               "passed": None if skipped else not failed})
    return {"task_id": task_id, "checks": checks,
            "all_passed": bool(checks) and all(c["passed"] is True for c in checks) and exit_code == 0,
            "exit_code": exit_code, "output": output, "evaluated_tree_sha256": tree_sha256(tree)}


def package_hashes(task_id: str) -> dict:
    task = task_dir(task_id)
    oracle = hashlib.sha256((tree_sha256(task / "hidden") + tree_sha256(task / "starter" / "tests")).encode()).hexdigest()
    return {"task": tree_sha256(task), "starter": tree_sha256(task / "starter"), "oracle": oracle,
            "reference": tree_sha256(task / "reference"), "spec": hashlib.sha256((task / "spec.md").read_bytes()).hexdigest()}


def validate() -> dict:
    """Each task: the starter must fail the oracle and the reference (starter + reference/app) must pass."""
    results = {}
    for task in sorted(p for p in TASKS.iterdir() if p.is_dir()):
        task_id = task.name.split("-", 1)[0]
        starter = evaluate(task_id, task / "starter")
        with tempfile.TemporaryDirectory() as tmp:
            solved = Path(tmp) / "solved"
            _copy(task / "starter", solved)
            _copy(task / "reference", solved)
            reference = evaluate(task_id, solved)
        results[task_id] = {"name": task.name, "hashes": package_hashes(task_id),
                            "checks": len(reference["checks"]),
                            "public_checks": sum(c["id"].startswith("tests.") for c in reference["checks"]),
                            "starter_fails": starter["all_passed"] is False,
                            "starter_passed_checks": sum(c["passed"] is True for c in starter["checks"]),
                            "reference_passes": reference["all_passed"] is True,
                            "reference_output": "" if reference["all_passed"] else reference["output"]}
        results[task_id]["valid"] = results[task_id]["starter_fails"] and results[task_id]["reference_passes"]
    return results


def main(argv: list[str]) -> int:
    if argv[:1] == ["validate"]:
        results = validate()
        manifest = {"package_version": "0.1.0", "tasks": results,
                    "all_valid": all(r["valid"] for r in results.values()),
                    "python": sys.version.split()[0]}
        print(json.dumps(manifest, indent=2))
        return 0 if manifest["all_valid"] else 1
    if argv[:1] == ["evaluate"] and len(argv) == 3:
        print(json.dumps(evaluate(argv[1], Path(argv[2])), indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

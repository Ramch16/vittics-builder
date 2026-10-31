"""Week 11 report, Week 19 reruns and Week 21 evidence freeze."""
import json
import shutil

import pytest

from benchmark.report import analyse, markdown

PILOT = "evidence/week3/mock-pilot-20261031/records.jsonl"


def _records():
    return [json.loads(l) for l in open(PILOT, encoding="utf-8")]


def test_report_flags_non_results_and_counts_false_releases():
    a = analyse(_records())
    text = markdown(a)
    assert "**Not results.**" in text and a["data_kinds"] == ["synthetic-mock"]
    assert a["conditions"]["multi_agent"]["false_releases"] == 24 and a["conditions"]["single_agent"]["released"] == 0
    assert a["paired"]["tasks"] == 8 and a["paired"]["mean"] == 0


def test_report_never_turns_unknown_into_zero():
    rs = _records()[:4]
    rs[0] = {**rs[0], "cost": {**rs[0]["cost"], "amount": None}, "acceptance": {**rs[0]["acceptance"], "all_passed": None}}
    for r in rs[1:]:
        r["data_kind"] = "observed"
    a = analyse(rs)
    c = a["conditions"][rs[0]["condition"]]
    assert c["unknown_cost_runs"] == 1 and c["cost_per_accepted"] is None and c["unresolved"] == 1
    assert "Optimistic bound" in markdown(a)


def test_rerun_keeps_the_original_and_logs_the_deviation(tmp_path):
    from benchmark.rerun import rerun
    from vittics_builder.llm import MockProvider
    sched = json.load(open("benchmark/schedule-20261031.json", encoding="utf-8"))
    out = tmp_path / "run"
    out.mkdir()
    first = [r for r in _records() if r["run_id"] == sched["slots"][0]["run_id"]]
    (out / "records.jsonl").write_text(json.dumps(first[0]) + "\n", encoding="utf-8")
    entry = rerun(sched, out, 1, "runner lost network", "infrastructure", MockProvider)
    lines = (out / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["run_id"] == first[0]["run_id"]
    assert json.loads(lines[1])["run_id"] == entry["rerun_id"] == first[0]["run_id"] + "-rerun1"
    assert json.loads((out / "deviations.jsonl").read_text())["reason"] == "runner lost network"
    with pytest.raises(SystemExit, match="not allowed"):
        rerun(sched, out, 1, "result looked bad", "outcome", MockProvider)


def test_freeze_detects_changed_missing_and_added_files(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("freeze", "scripts/freeze_evidence.py")
    freeze = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freeze)
    folder = tmp_path / "ev"
    shutil.copytree("evidence/week3/mock-pilot-20261031", folder)
    m = freeze.freeze(folder)
    assert len(m["files"]) == 51 and freeze.verify(folder) == {**freeze.verify(folder), "changed": [], "missing": [], "added": []}
    (folder / "summary.json").write_text("{}")
    (folder / "validation.json").unlink()
    (folder / "extra.txt").write_text("x")
    v = freeze.verify(folder)
    assert v["changed"] == ["summary.json"] and v["missing"] == ["validation.json"] and v["added"] == ["extra.txt"]


def test_offline_demo_runs_brief_to_done(tmp_path):
    import subprocess, sys
    proc = subprocess.run([sys.executable, "scripts/demo_mock.py", "--out", str(tmp_path)], capture_output=True,
                          text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "final stage: done" in proc.stdout and "single_agent:" in proc.stdout

"""The benchmark task package, schedule and harness (decisions D8-D12). Offline; MockProvider only."""
import json
from collections import Counter

import pytest

from benchmark import oracle, schedule
from vittics_builder.benchmarks import SCHEMA_PATH, check_semantics, validate_record


def test_every_task_starter_fails_and_reference_passes():
    results = oracle.validate()
    assert sorted(results) == [f"T0{i}" for i in range(1, 9)]
    bad = {k: v["reference_output"][-500:] for k, v in results.items() if not v["valid"]}
    assert not bad
    assert all(v["starter_passed_checks"] == 0 and v["public_checks"] >= 2 for v in results.values())


def test_oracle_uses_frozen_public_tests_not_the_agents_copy(tmp_path):
    """An agent that rewrites tests/ to pass does not change what the oracle runs."""
    task = oracle.task_dir("T07")
    import shutil
    shutil.copytree(task / "starter", tmp_path / "tree")
    (tmp_path / "tree" / "tests" / "test_public.py").write_text("def test_ok():\n    assert True\n")
    result = oracle.evaluate("T07", tmp_path / "tree")
    assert result["all_passed"] is False and any(c["id"].startswith("tests.") for c in result["checks"])


def test_schedule_is_reproducible_and_counterbalanced():
    a, b = schedule.build(20261031), schedule.build(20261031)
    assert a == b and len(a["slots"]) == 48 and len({s["run_id"] for s in a["slots"]}) == 48
    assert Counter(s["condition"] for s in a["slots"]) == {"multi_agent": 24, "single_agent": 24}
    for task in a["tasks"]:
        runs = [s for s in a["slots"] if s["task_id"] == task]
        firsts = []
        for repeat in (1, 2, 3):
            pair = [s for s in runs if s["repeat"] == repeat]
            assert {s["condition"] for s in pair} == {"multi_agent", "single_agent"}
            assert abs(pair[0]["slot"] - pair[1]["slot"]) == 1                  # back to back
            firsts.append(min(pair, key=lambda s: s["slot"])["condition"])
        assert len(set(firsts)) == 2                                            # each condition goes first once
    assert schedule.build(1) != a
    with open("benchmark/schedule-20261031.json") as f:
        assert json.load(f) == a                                                # the committed schedule is this one


@pytest.mark.parametrize("condition", ["multi_agent", "single_agent"])
def test_harness_writes_valid_mock_records(tmp_path, condition):
    from benchmark.harness import run_slot
    from vittics_builder.llm import MockProvider
    record = run_slot({"slot": 1, "task_id": "T07", "repeat": 1, "condition": condition,
                       "run_id": f"T07-{condition}-r1"}, tmp_path, MockProvider)
    schema = json.loads(open(SCHEMA_PATH).read())
    assert validate_record(record, schema) == [] and check_semantics([record]) == []
    assert record["data_kind"] == "synthetic-mock" and record["acceptance"]["oracle"]["kind"] == "independent_hidden"
    assert (tmp_path / record["acceptance"]["oracle"]["run_ref"]).is_file()


def test_harness_refuses_real_providers():
    from benchmark.harness import main
    with pytest.raises(SystemExit):
        main(["--schedule", "benchmark/schedule-20261031.json", "--out", "x", "--provider", "anthropic"])

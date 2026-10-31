"""Hard per-run caps (Week 6): admission, in-flight reservation, unknown cost, time, and the harness."""
import json
import threading
import time

import pytest

from vittics_builder.caps import CapExceeded, RunCaps


def test_token_cap_counts_used_and_in_flight():
    caps = RunCaps(max_total_tokens=100)
    a = caps.admit(60, 0.0)
    with pytest.raises(CapExceeded) as e:
        caps.admit(50, 0.0)                         # 60 in flight + 50 > 100
    assert e.value.kind == "tokens"
    caps.settle(a, 30, 0.0)                         # the call used less than reserved
    caps.release(caps.admit(70, 0.0))               # 30 used + 70 fits exactly
    with pytest.raises(CapExceeded):
        caps.admit(71, 0.0)


def test_unknown_cost_is_refused_under_a_cost_cap():
    with pytest.raises(CapExceeded) as e:
        RunCaps(max_cost=1.0).admit(10, None)
    assert e.value.kind == "cost"
    RunCaps(max_total_tokens=100).release(RunCaps(max_total_tokens=100).admit(10, None))   # no cost cap: fine


def test_unbounded_engines_are_refused_only_under_usage_caps():
    with pytest.raises(CapExceeded) as e:
        RunCaps(max_total_tokens=10).admit(0, None, bounded=False)
    assert e.value.kind == "unbounded"
    RunCaps(max_wall_seconds=60).admit(0, None, bounded=False)


def test_wall_cap():
    caps = RunCaps(max_wall_seconds=0.05)
    time.sleep(0.06)
    with pytest.raises(CapExceeded) as e:
        caps.admit(1, 0.0)
    assert e.value.kind == "wall"


def test_parallel_admission_never_overcommits():
    caps, admitted, refused = RunCaps(max_total_tokens=1000, max_cost=1.0), [], []
    barrier = threading.Barrier(20)

    def worker():
        barrier.wait()
        try:
            admitted.append(caps.admit(100, 0.1))
        except CapExceeded:
            refused.append(1)
    threads = [threading.Thread(target=worker) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(admitted) == 10 and len(refused) == 10


def test_runtime_stops_an_agent_at_the_token_cap(co):
    p = co.pipeline.create_project("Capped", "A tiny library.")
    ws = co.pipeline.workspace(co.pipeline.project(p["id"]))
    co.runtime.caps[p["id"]] = RunCaps(max_total_tokens=50)
    with pytest.raises(CapExceeded):
        co.runtime.run(co.org.agent("Hari"), "Build it.", ws, project_id=p["id"])
    assert not co.db.one("SELECT 1 FROM usage WHERE project_id=?", p["id"])     # refused before any call


def test_cli_engines_cannot_run_under_a_token_cap(co):
    p = co.pipeline.create_project("Capped", "A tiny library.")
    co.org.set_model("Hari", "cli:claude-code")
    co.runtime.caps[p["id"]] = RunCaps(max_total_tokens=10_000)
    with pytest.raises(CapExceeded) as e:
        co.runtime.run(co.org.agent("Hari"), "Build it.", co.pipeline.workspace(co.pipeline.project(p["id"])),
                       project_id=p["id"])
    assert e.value.kind == "unbounded"


@pytest.mark.parametrize("caps, status", [({"max_total_tokens": 200}, "blocked"),
                                          ({"max_total_tokens": 10_000_000}, "rejected")])
def test_harness_records_a_cap_stop(tmp_path, caps, status):
    from benchmark.harness import run_slot
    from vittics_builder.benchmarks import SCHEMA_PATH, check_semantics, validate_record
    from vittics_builder.llm import MockProvider
    record = run_slot({"slot": 1, "task_id": "T07", "repeat": 1, "condition": "multi_agent",
                       "run_id": "T07-multi_agent-r1"}, tmp_path, MockProvider, caps)
    schema = json.loads(open(SCHEMA_PATH, encoding="utf-8").read())
    assert validate_record(record, schema) == [] and check_semantics([record]) == []
    assert record["terminal_status"] == status and record["caps"]["max_total_tokens"] == caps["max_total_tokens"]
    if status == "blocked":
        assert record["blocker"].startswith("cap_exceeded:tokens")

"""0.23: a lighter process for small projects, no release restarts, pause/resume and other fixes from the pilot."""
import json

from fastapi.testclient import TestClient

from vittics_builder.company import Company
from vittics_builder.engines import BUILTIN_ENGINES, protocol
from vittics_builder.llm import MockProvider
from vittics_builder.pipeline import IDEA_STAGES
from vittics_builder.platforms import keep_awake
from vittics_builder.server import create_app
from vittics_builder.tools import Workspace
from vittics_builder.validation import same_contract
from test_pipeline import decide_next
from test_tickets import built, scripted_company


class Recording(MockProvider):
    """The mock company, remembering every prompt an agent was given."""

    def __init__(self):
        super().__init__()
        self.prompts = []

    def complete(self, **kwargs):
        self.prompts.append((kwargs.get("meta") or {}, json.dumps(kwargs["messages"][:1])))
        return super().complete(**kwargs)


def through_design(co, size):
    p = co.pipeline.create_project("Product", "Build a library", size=size)
    assert co.pipeline.advance(p["id"])["stage"] == "prd_approval"
    decide_next(co, "ceo")
    return p, decide_next(co, "cto")


def test_small_project_runs_the_light_process(tmp_path):
    provider = Recording()
    co = Company(tmp_path, provider=provider, create=True)
    p, after = through_design(co, "small")
    assert after["stage"] == "release_approval"
    prd = [text for meta, text in provider.prompts if "docs/PRD.md" in text and "Write the requirements" in text]
    assert prd and "This is a small project" in prd[0]
    assert not [meta for meta, _ in provider.prompts if meta.get("kind") == "auditor"]       # no audits
    reviews = {}
    for meta, _ in provider.prompts:
        if meta.get("author") and meta.get("task_key"):
            reviews.setdefault(meta["task_key"], set()).add(meta.get("agent_id") or meta.get("kind"))
    assert reviews and all(len(kinds) == 1 for kinds in reviews.values())                   # one reviewer each
    assert co.pipeline.max_rework(p["id"]) == 1


def test_standard_project_keeps_the_full_process(tmp_path):
    provider = Recording()
    co = Company(tmp_path, provider=provider, create=True)
    p, after = through_design(co, "standard")
    assert after["stage"] == "release_approval"
    assert [meta for meta, _ in provider.prompts if meta.get("kind") == "auditor"]
    assert co.pipeline.max_rework(p["id"]) == co.s.max_rework


def test_building_a_small_project_skips_the_idea_assessment(tmp_path):
    co = Company(tmp_path, provider=MockProvider(), create=True)
    client = TestClient(create_app(co, {"ceo": "ceo-token", "cto": "cto-token"}))
    small = client.post("/api/build", json={"brief": "A tiny tip calculator page", "size": "small"},
                        headers={"X-Token": "ceo-token"}).json()
    standard = client.post("/api/build", json={"brief": "A customer support portal"},
                           headers={"X-Token": "ceo-token"}).json()
    assert co.pipeline.project(small["id"])["size"] == "small"
    assert not co.db.one("SELECT 1 FROM events WHERE project_id=? AND message LIKE 'New idea:%'", small["id"])
    assert co.db.one("SELECT 1 FROM events WHERE project_id=? AND message LIKE 'New idea:%'", standard["id"])
    assert client.post("/api/build", json={"brief": "Something else entirely", "size": "huge"},
                       headers={"X-Token": "ceo-token"}).status_code == 400


def test_non_urgent_tickets_filed_during_release_wait_in_the_backlog(tmp_path):
    co = scripted_company(tmp_path, {("qa", "integration"): [
        ("create_ticket", {"title": "Refresh a stale line in the docs", "description": "Wording only.",
                           "type": "task", "priority": "low"})]})
    p = built(co)                                     # reaches the release review without another round
    docs = next(t for t in co.tickets.search(p["id"]) if t["title"] == "Refresh a stale line in the docs")
    assert docs["status"] == "backlog"
    [release] = [a for a in co.pipeline.inbox("cto") if a["kind"] == "release"]
    assert "waiting in the backlog" in release["summary"] and docs["ticket"] in release["summary"]


def test_description_text_in_product_json_may_change_without_a_new_approval(tmp_path):
    approved = json.dumps({"name": "P", "setup": "old", "checks": [{"id": "t", "command": "true"}]})
    assert same_contract(json.dumps({"name": "P", "setup": "new words", "release_status": "ok",
                                     "checks": [{"id": "t", "command": "true"}]}), approved)
    assert not same_contract(json.dumps({"name": "P", "setup": "old", "checks": []}), approved)
    assert not same_contract(None, approved) and not same_contract("not json", approved)

    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project("Product", "Build a library")
    co.pipeline.advance(p["id"])
    decide_next(co, "ceo")
    approval = next(a for a in co.pipeline.inbox("cto") if a["kind"] == "architecture")
    co.pipeline.decide(approval["id"], "cto", "approved")
    ws = Workspace(p["workspace"])
    data = json.loads(ws.read_file("product.json"))
    data["setup"] = "Reworded installation notes."
    ws.write_file("product.json", json.dumps(data))
    assert co.pipeline.advance(p["id"])["stage"] == "release_approval"     # no "checks changed" stop


def test_pause_and_resume(tmp_path):
    co = Company(tmp_path, provider=MockProvider(), create=True)
    client = TestClient(create_app(co, {"ceo": "ceo-token", "cto": "cto-token"}))
    h = {"X-Token": "ceo-token"}
    p = co.pipeline.create_project("Product", "Build a library")
    co.pipeline.advance(p["id"])                                            # waits for the CEO's PRD decision
    paused = client.post(f"/api/projects/{p['id']}/pause", headers=h).json()
    assert paused["stage"] == "paused" and paused["message"] == "Paused."
    assert co.pipeline.advance(p["id"])["stage"] == "paused"               # nothing runs while paused
    resumed = client.post(f"/api/projects/{p['id']}/run", headers=h).json()
    assert resumed["stage"] == "prd_approval" and resumed["message"].startswith("Waiting for the CEO")
    assert client.post(f"/api/projects/{p['id']}/run", headers=h).json()["message"].startswith("Waiting")


def test_a_pause_asked_for_mid_run_stops_at_the_next_safe_point(tmp_path):
    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project("Product", "Build a library")
    co.pipeline.advance(p["id"])
    decide_next(co, "ceo")
    approval = next(a for a in co.pipeline.inbox("cto") if a["kind"] == "architecture")
    co.pipeline.decide(approval["id"], "cto", "approved")
    co.pipeline._pause_requested.add(p["id"])                              # as if Pause were clicked while busy
    assert co.pipeline.advance(p["id"])["stage"] == "paused"
    assert co.pipeline.project(p["id"])["paused_stage"] == "build"
    co.pipeline.resume(p["id"], "Niki")
    assert co.pipeline.advance(p["id"])["stage"] == "release_approval"


def test_resume_says_what_happened(tmp_path):
    co = Company(tmp_path, provider=MockProvider(), create=True)
    client = TestClient(create_app(co, {"ceo": "ceo-token", "cto": "cto-token"}))
    p = co.pipeline.create_project("Product", "Build a library")
    co.db.run("UPDATE projects SET stage='done' WHERE id=?", p["id"])
    message = client.post(f"/api/projects/{p['id']}/run", headers={"X-Token": "ceo-token"}).json()["message"]
    assert message.startswith("Nothing to do")


def test_agents_run_commands_in_the_foreground():
    assert BUILTIN_ENGINES["claude-code"]["env"]["CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"] == "1"
    assert "foreground" in protocol([]) and "foreground" in protocol(["submit_review"])


def test_keep_awake_can_be_turned_off():
    assert keep_awake(False) == ""


def test_planning_proposals_are_not_scheduled_as_duplicate_build_work(tmp_path):
    from vittics_builder.agent import RunResult
    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project('Calculator', 'A small calculator', size='small')
    pm = co.org.pick(kind='product')
    result = RunResult()
    co.tickets.agent_tool(pm, 'create_ticket', {
        'title': 'Implement calculator', 'description': 'Proposal for the architect',
        'type': 'task', 'priority': 'medium', 'role': 'frontend_engineer'
    }, p['id'], None, result)
    task = co.db.one("SELECT * FROM tasks WHERE project_id=? AND origin='agent'", p['id'])
    assert task['status'] == 'backlog'
    assert co.pipeline._ready_tasks(p['id']) == []


def test_workers_receive_recorded_approval_despite_stale_files(tmp_path):
    provider = Recording()
    co = Company(tmp_path, provider=provider, create=True)
    p, _ = through_design(co, 'small')
    assert any('Recorded project decisions' in text and 'prd: approved' in text
               for _, text in provider.prompts)


def test_capacity_during_review_resumes_without_rebuilding(tmp_path, monkeypatch):
    import pytest
    from vittics_builder.engines import EngineUnavailable
    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project('Resume', 'A library', size='small')
    task = co.tickets.create(p['id'], 'Core', 'Build core', 'Lucky', status='todo', role='backend_engineer')
    ws = co.pipeline.workspace(p)
    original = co.runtime.run
    counts = {'builder': 0, 'reviewer': 0}
    def run(agent, instructions, workspace, **kw):
        if (kw.get('meta') or {}).get('author'):
            counts['reviewer'] += 1
            if counts['reviewer'] == 1:
                raise EngineUnavailable('Selected model is at capacity')
        else:
            counts['builder'] += 1
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, 'run', run)
    with pytest.raises(EngineUnavailable):
        co.pipeline._run_task(p, task, ws)
    assert co.db.one('SELECT attempts FROM tasks WHERE id=?', task['id'])['attempts'] == 0
    assert co.pipeline._run_task(p, task, ws)
    assert counts['builder'] == 1
    assert co.pipeline.project(p['id'])['repair_starts'] == 0
    assert co.db.one('SELECT builder_starts FROM tasks WHERE id=?', task['id'])['builder_starts'] == 1


def test_release_review_cannot_approve_unverified_acceptance(tmp_path):
    import pytest
    from vittics_builder.agent import RunResult
    from vittics_builder.tools import ToolError
    co = Company(tmp_path, provider=MockProvider(), create=True)
    qa = co.org.pick(kind='qa')
    args = {'score': 90, 'verdict': 'approve', 'notes': 'Automated tests pass'}
    with pytest.raises(ToolError, match='requires acceptance evidence'):
        co.runtime._execute(qa, 'submit_review', args, None, RunResult(), None, {'purpose':'integration'}, 0)
    args['acceptance'] = [{'criterion':'Keyboard journey', 'status':'unverified', 'evidence':'Browser access missing'}]
    with pytest.raises(ToolError, match='Cannot approve'):
        co.runtime._execute(qa, 'submit_review', args, None, RunResult(), None, {'purpose':'integration'}, 0)
    args['verdict'] = 'request_changes'
    result = RunResult()
    co.runtime._execute(qa, 'submit_review', args, None, result, None, {'purpose':'integration'}, 0)
    assert result.review['acceptance'][0]['status'] == 'unverified'


def test_missing_review_verdict_does_not_charge_builder_rework(tmp_path, monkeypatch):
    import pytest
    from vittics_builder.agent import RunResult
    from vittics_builder.pipeline import PipelineError
    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project('Review', 'A library', size='small')
    task = co.tickets.create(p['id'], 'Core', 'Build core', 'Lucky', status='todo', role='backend_engineer')
    original = co.runtime.run
    def run(agent, instructions, workspace, **kw):
        if (kw.get('meta') or {}).get('author'):
            return RunResult(completed=True, text='No structured verdict')
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, 'run', run)
    with pytest.raises(PipelineError, match='Review is incomplete'):
        co.pipeline._run_task(p, task, co.pipeline.workspace(p))
    saved = co.db.one('SELECT * FROM tasks WHERE id=?', task['id'])
    assert saved['attempts'] == 0 and saved['status'] == 'in_review'
    assert not co.db.one('SELECT 1 FROM reviews WHERE task_id=?', task['id'])


def test_parallel_interruption_keeps_candidate_for_review(tmp_path, monkeypatch):
    import pytest
    from vittics_builder.engines import EngineUnavailable
    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project('Retain', 'A library', size='small')
    task = co.tickets.create(p['id'], 'Core', 'Build core', 'Lucky', status='todo', role='backend_engineer')
    ws = co.pipeline.workspace(p)
    original = co.runtime.run
    counts = {'builders': 0, 'reviews': 0}
    def run(agent, instructions, workspace, **kw):
        if (kw.get('meta') or {}).get('author'):
            counts['reviews'] += 1
            if counts['reviews'] == 1:
                raise EngineUnavailable('Selected model is at capacity')
        else:
            counts['builders'] += 1
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, 'run', run)
    with pytest.raises(EngineUnavailable):
        co.pipeline._run_parallel(p, [task], ws)
    assert ws.git('branch', '--list', 'recovery/*').strip()
    assert co.pipeline._run_task(p, task, ws)
    assert counts['builders'] == 1

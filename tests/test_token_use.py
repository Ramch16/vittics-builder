"""Tokens: agents read what a ticket needs, documents stay proportionate, numbers come from real output, and
reviewers get the changes in their prompt instead of exploring the project to find them."""
import json

from vittics_builder.company import Company
from vittics_builder.llm import MockProvider
from vittics_builder.pipeline import DOC_RULES, REVIEW_BUDGET
from test_ideas import decided
from test_parallel import plan_approved


class Recording(MockProvider):
    """The mock company, remembering every prompt an agent was given."""

    def __init__(self):
        super().__init__()
        self.prompts = []

    def complete(self, **kwargs):
        self.prompts.append((kwargs.get("meta") or {}, json.dumps(kwargs["messages"][:1])))
        return super().complete(**kwargs)


def built(tmp_path):
    provider = Recording()
    co = Company(tmp_path, provider=provider, create=True)
    p = plan_approved(co)
    co.pipeline.advance(p["id"])
    return co, p, provider


def test_reviewers_get_the_ticket_diff_and_a_review_budget(tmp_path):
    co, p, provider = built(tmp_path)
    reviews = [text for meta, text in provider.prompts if meta.get("author") and meta.get("task_key")]
    assert reviews
    for text in reviews:
        assert "git diff from where the builder started" in text      # the changes are in the prompt
        assert "+++ b/" in text or "files changed" in text            # a real diff, not just a heading
        assert "focused review needs about a dozen tool calls" in text and "cannot find in the check output" in text


def test_builders_read_only_what_the_ticket_needs_and_get_the_document_rules(tmp_path):
    co, p, provider = built(tmp_path)
    builds = [text for meta, text in provider.prompts if meta.get("task_key") and not meta.get("author")]
    assert builds
    for text in builds:
        assert "only the parts this ticket needs" in text              # engineering: PRD and architecture, selectively
        assert "Documents cost tokens each time an agent reads them again" in text
        assert "never estimate or invent a number" in text
    assert "keep it under about 4 KB" in DOC_RULES and "dozen tool calls" in REVIEW_BUDGET


def test_non_engineering_tickets_do_not_start_by_reading_every_document(tmp_path):
    provider = Recording()
    co = Company(tmp_path, provider=provider, create=True)
    p = plan_approved(co)
    co.tickets.create(p["id"], "Write the help page", "A short help page.", "Lucky", status="todo", role="tech_writer")
    co.pipeline.advance(p["id"])
    docs = [text for meta, text in provider.prompts
            if meta.get("task_key") and not meta.get("author") and "Your task [" in text and "Write the help page" in text]
    assert docs and all("Read only the files this ticket names" in t for t in docs)
    assert not any("Read docs/PRD.md and docs/ARCHITECTURE.md" in t for t in docs)


def test_an_internal_tool_is_not_given_legal_support_or_documentation_tickets_by_default(tmp_path):
    provider = Recording()
    co = Company(tmp_path, provider=provider, create=True)
    decided(co, "internal")
    plan = [text for meta, text in provider.prompts if "Write docs/PLAN.md" in text]
    assert plan and "file no legal, support or documentation tickets" in plan[0]
    sell_provider = Recording()
    selling = Company(tmp_path / "sell", provider=sell_provider, create=True)
    decided(selling, "commercial")
    sold = [text for meta, text in sell_provider.prompts if "Write docs/PLAN.md" in text]
    assert sold and "file no legal, support" not in sold[0]            # selling still plans the whole company


def test_a_resumed_review_still_gets_the_diff(tmp_path, monkeypatch):
    import pytest
    from vittics_builder.engines import EngineUnavailable
    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project("Resume", "A library", size="small")
    task = co.tickets.create(p["id"], "Core", "Build core", "Lucky", status="todo", role="backend_engineer")
    ws = co.pipeline.workspace(p)
    original, prompts = co.runtime.run, []

    def run(agent, instructions, workspace, **kw):
        if (kw.get("meta") or {}).get("author"):
            prompts.append(instructions)
            if len(prompts) == 1:
                raise EngineUnavailable("Selected model is at capacity")       # the first review is cut off
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, "run", run)
    with pytest.raises(EngineUnavailable):
        co.pipeline._run_task(p, task, ws)
    assert co.pipeline._run_task(p, task, ws)                                   # resumed without rebuilding
    assert len(prompts) >= 2                                                    # the cut-off review, then the resumed ones
    assert all("git diff from where the builder started" in text and "+++ b/" in text for text in prompts)


# ---- choosing the size from the brief ----------------------------------------------------------
import pytest
from fastapi.testclient import TestClient

from vittics_builder.server import create_app
from vittics_builder.sizing import suggest_size

CHECKLIST = """Build a single-page personal task checklist.
Requirements:
- Add a task with a title.
- Save tasks in localStorage so they survive refresh.
- Work on mobile and desktop with labelled controls and keyboard navigation.
Use plain HTML, CSS, and JavaScript. No backend, login, external APIs, dependencies, or deployment."""


@pytest.mark.parametrize("brief, size", [
    (CHECKLIST, "small"),                                                       # "No backend, login..." is not a request for them
    ("A tiny tip calculator page: bill, tip percent and people. Single static HTML page with no backend.", "small"),
    ("Build a simple personal expense tracker that runs locally in my browser.", "small"),
    ("A customer support app with login, a database and Stripe payments", "standard"),
    ("A customer support portal", "standard"),                                  # short, but nothing says it is small
    ("A todo list app for teams", "standard"),                                  # "todo list", but for other people
    ("A small business invoicing system", "standard"),                          # "small" alone does not make a small tool
    ("A simple CRM", "standard"),
    ("A personal budget tracker that keeps its data in localStorage", "small"),
    ("A to-do list for my own use, on a single page", "small"),
    ("A simple blog with user accounts and an admin dashboard", "standard"),     # "simple", but accounts and admin
    ("A small tool that stores notes in a Postgres database", "standard"),
    ("simple checklist " + "with many details " * 120, "standard"),               # too long to be a small tool
    ("", "standard"),
])
def test_size_is_chosen_from_the_brief(brief, size):
    assert suggest_size(brief)[0] == size


def test_the_reason_is_given_and_logged(tmp_path):
    reason = suggest_size(CHECKLIST)[1]
    assert "single-page" in reason or "checklist" in reason or "simple" in reason
    co = Company(tmp_path, provider=MockProvider(), create=True)
    p = co.pipeline.create_project("Checklist", CHECKLIST, size="auto")
    assert p["size"] == "small"
    assert co.db.one("SELECT 1 FROM events WHERE project_id=? AND message LIKE 'Size chosen automatically: small%'", p["id"])
    big = co.pipeline.create_project("Portal", "A customer support portal with login", size="auto")
    assert big["size"] == "standard"
    assert co.pipeline.create_project("Forced", CHECKLIST, size="standard")["size"] == "standard"   # your choice wins


def test_building_with_auto_skips_the_idea_stage_only_for_small_tools(tmp_path):
    co = Company(tmp_path, provider=MockProvider(), create=True)
    client = TestClient(create_app(co, {"ceo": "ceo-token", "cto": "cto-token"}))
    headers = {"X-Token": "ceo-token"}
    small = client.post("/api/build", json={"brief": CHECKLIST}, headers=headers).json()
    standard = client.post("/api/build", json={"brief": "A customer support portal with login and a database"},
                           headers=headers).json()
    assert co.pipeline.project(small["id"])["size"] == "small"
    assert not co.db.one("SELECT 1 FROM events WHERE project_id=? AND message LIKE 'New idea:%'", small["id"])
    assert co.pipeline.project(standard["id"])["size"] == "standard"
    assert co.db.one("SELECT 1 FROM events WHERE project_id=? AND message LIKE 'New idea:%'", standard["id"])

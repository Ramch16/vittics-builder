"""Known gaps in the command boundary, written down as tests before they are fixed.

Each test states what SHOULD hold. Today it does not, so each is marked xfail(strict=True): the suite stays
green, and the day a fix lands the test starts passing, strict mode turns that into a failure, and whoever
fixed it removes the marker. IDs refer to the Week 1 audit's security register.

Only fake secrets are used, inside pytest's temporary folders. The shell syntax is POSIX sh, so these run on
macOS and Linux only.
"""
import os

import pytest

from vittics_builder.tools import ToolError, Workspace

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX shell syntax")

FAKE_VAULT = '{"STRIPE_SECRET_KEY": "sk_live_FAKE_vault_value"}'
FAKE_CREDENTIALS = '{"ANTHROPIC_API_KEY": "sk-ant-FAKE-saved-key"}'


@pytest.fixture
def company(tmp_path):
    """A company folder laid out as Vittics Builder lays it out, with an agent workspace two levels down."""
    root = tmp_path / "company"
    (root / ".vittics" / "vault").mkdir(parents=True)
    (root / ".vittics" / "vault" / "1.json").write_text(FAKE_VAULT)
    (root / ".vittics" / "credentials.json").write_text(FAKE_CREDENTIALS)
    ws = Workspace(root / "workspaces" / "1-demo")
    ws.init_repo()
    return root, ws


def leaked(ws: Workspace, command: str, secret: str) -> bool:
    """True if the command ran and its output contains the secret. A refusal is not a leak."""
    try:
        return secret in ws.run_command(command)
    except ToolError:
        return False


def test_literal_parent_path_is_refused(company):
    """The control the deny list does provide today (passes, not xfail)."""
    _, ws = company
    assert not leaked(ws, "cat ../../.vittics/vault/1.json", "sk_live_FAKE")


@pytest.mark.xfail(strict=True, reason="SEC-01: deny list is a regex; a chain of `cd ..` reaches company secrets")
def test_agent_shell_cannot_read_vault_by_changing_directory(company):
    _, ws = company
    assert not leaked(ws, "cd .. && cd .. && cat .vittics/vault/1.json", "sk_live_FAKE")


@pytest.mark.xfail(strict=True, reason="SEC-01: an absolute path to the company folder is not refused")
def test_agent_shell_cannot_read_saved_api_key_by_absolute_path(company):
    root, ws = company
    assert not leaked(ws, f"cat '{root / '.vittics' / 'credentials.json'}'", "sk-ant-FAKE")


@pytest.mark.xfail(strict=True, reason="SEC-01: quoting a system path slips past the /etc/ pattern")
def test_quoted_system_path_is_refused(company):
    _, ws = company
    with pytest.raises(ToolError):
        ws.run_command("cat '/etc/hosts'")


@pytest.mark.xfail(strict=True, reason="SEC-03: env scrubbing is by variable name; DATABASE_URL carries a password")
def test_credentials_in_connection_urls_do_not_reach_commands(company, monkeypatch):
    _, ws = company
    monkeypatch.setenv("DATABASE_URL", "postgres://app:FAKEPASS123@db.internal/app")
    assert not leaked(ws, "env", "FAKEPASS123")


@pytest.mark.xfail(strict=True, reason="SEC-05: a git hook planted by an agent command runs on the company's commit")
def test_agent_planted_git_hook_does_not_run_on_company_commit(company, tmp_path):
    _, ws = company
    proof = tmp_path / "hook-ran"
    hook = f'#!/bin/sh\\necho ran > "{proof}"\\n'
    ws.run_command(f"printf '{hook}' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit")
    ws.write_file("a.txt", "1")
    ws.commit("company commit")
    assert not proof.exists()


def test_file_tools_still_refuse_git_internals(company):
    """write_file already keeps agents out of .git (passes, not xfail); SEC-05 is about the shell route."""
    _, ws = company
    with pytest.raises(ToolError):
        ws.write_file(".git/hooks/pre-commit", "#!/bin/sh\n")


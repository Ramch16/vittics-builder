"""Known gaps in the command boundary, written down as tests before they are fixed.

Each test states what SHOULD hold. SEC-03 and SEC-05 are fixed (URL-credential scrubbing; company git calls run
with hooks disabled). SEC-01 is fixed where an OS sandbox hides the company's .vittics folder from agent commands
(bubblewrap on Linux, sandbox-exec on macOS); elsewhere those tests stay xfail(strict=True). SEC-05 is fixed for
the company's git calls in local mode; Docker mode's writable .git mount is a separate item (P-05b).

Only fake secrets are used, inside pytest's temporary folders. The shell syntax is POSIX sh, so these run on
macOS and Linux only.
"""
import os

import pytest

from vittics_builder.tools import ToolError, Workspace, sandbox_backend

NO_SANDBOX = sandbox_backend() is None

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


@pytest.mark.xfail(NO_SANDBOX, strict=True, reason="SEC-01: without bubblewrap (Linux) or sandbox-exec (macOS) the shell can reach company secrets")
def test_agent_shell_cannot_read_vault_by_changing_directory(company):
    _, ws = company
    assert not leaked(ws, "cd .. && cd .. && cat .vittics/vault/1.json", "sk_live_FAKE")


@pytest.mark.xfail(NO_SANDBOX, strict=True, reason="SEC-01: without bubblewrap (Linux) or sandbox-exec (macOS) an absolute path reaches company secrets")
def test_agent_shell_cannot_read_saved_api_key_by_absolute_path(company):
    root, ws = company
    assert not leaked(ws, f"cat '{root / '.vittics' / 'credentials.json'}'", "sk-ant-FAKE")


def test_quoted_system_path_is_refused(company):
    _, ws = company
    with pytest.raises(ToolError):
        ws.run_command("cat '/etc/hosts'")


def test_credentials_in_connection_urls_do_not_reach_commands(company, monkeypatch):
    _, ws = company
    monkeypatch.setenv("DATABASE_URL", "postgres://app:FAKEPASS123@db.internal/app")
    assert not leaked(ws, "env", "FAKEPASS123")


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



def test_unrelated_environment_does_not_reach_commands(company, monkeypatch):
    """Decision D7: local-mode commands get an allowlisted environment, not ours minus secret-looking names."""
    _, ws = company
    monkeypatch.setenv("INTERNAL_BILLING_ENDPOINT", "billing.internal.example")
    out = ws.run_command("env")
    assert "billing.internal.example" not in out and "PATH=" in out


def test_git_fsmonitor_planted_by_an_agent_does_not_run(company, tmp_path):
    """core.fsmonitor names a program git runs on status; company git calls switch it off (SEC-05)."""
    _, ws = company
    proof = tmp_path / "fsmonitor-ran"
    ws.run_command(f"git config core.fsmonitor 'touch {proof}; false'")
    ws.write_file("b.txt", "1")
    ws.changed_files()
    ws.commit("company commit")
    assert not proof.exists()

# Sai: security reproduction and isolation

**Role in the plan:** security owner.
**Time:** about 6–8 hours (more if you set up Docker).
**Status:** all tasks pending.

## Read first

- `docs/research/security-findings-2026-10-31.md`: current status of SEC-01 to SEC-12, W1-S1 and A-01.
- `docs/research/threat-model.md`.
- `vittics_builder/tools.py`: `command_env`, `secret_dirs`, `sandbox_backend`, `hide_paths`, `Workspace.git`.
- `tests/test_security_boundaries.py`.

## Tasks

### Q1. Reproduce on your own machine, before and after

Run the security tests on the old branch, then on the fix branch, on your own computer. Record the OS, the
Python version and whether bubblewrap is installed.

```
git checkout research/week2-readiness
python -m pytest -q -p no:cacheprovider tests/test_security_boundaries.py -rxX    # expect 5 xfailed (the gaps)
git checkout fix/review-and-isolation-policies
python -m pytest -q -p no:cacheprovider tests/test_security_boundaries.py -rxX    # expect all pass (or 2 xfail without a sandbox)
python -c "from vittics_builder.tools import sandbox_backend; print(sandbox_backend())"
```

**Deliverable:** `docs/research/reviews/sai-week3.md` with both runs: the command, the full summary line and
the environment.
**Accepted when:** both runs are recorded from your machine, with the real output.

### Q2. Try to break the fixes

Use fake secrets only. Try to:
- read `<company>/.vittics` from an agent command another way (symlinks, `/proc/self/cwd`, `find /`, a
  Python one-liner);
- get a password-bearing variable through the allowlist (for example, an allowed name carrying a URL);
- make the company's git run code (other config keys: `core.sshCommand`, `diff.external`, `filter.*`,
  `core.pager`).

```python
# starting point, in a Python shell
from pathlib import Path
from vittics_builder.tools import Workspace
root = Path("/tmp/q2-company"); (root/".vittics"/"vault").mkdir(parents=True, exist_ok=True)
(root/".vittics"/"vault"/"1.json").write_text('{"K": "FAKE-SECRET"}')
ws = Workspace(root/"workspaces"/"1-x"); ws.init_repo()
print(ws.run_command("your attempt here"))
```

**Deliverable:** a table in your review file (attempt, result, severity in your judgement). Each working
bypass gets a failing test in a PR, or an issue if you can't write the test.
**Accepted when:** at least 8 distinct attempts are recorded.

### Q3. Rate and dispose of every finding

For each row of `security-findings-2026-10-31.md`, give your own severity and disposition (fixed, accept risk,
fix needed, out of scope), with your reason.

**Deliverable:** a "Register" table in your review file.

### Q4. Checks that were blocked here

Run where your network allows, and record the output or the blocker:

```
pip install pip-audit && pip-audit --vulnerability-service osv
cd desktop && npm audit --package-lock-only
cargo install cargo-audit && (cd desktop/src-tauri && cargo audit)     # if Rust is installed
```

If you have Docker: run `python -m pytest -q tests/test_security_boundaries.py` with `sandbox.mode: docker`
configured, and test whether a hook can be planted through the Docker mount (P-05b).

### Q5. GitHub reviews

Review the fix PR (security parts) and PRs #8–#10 on GitHub from your account, with your reasons.

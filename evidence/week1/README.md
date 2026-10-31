# Week 1 evidence captures

Each folder is one run of `scripts/capture_evidence.py`, named `<UTC time>-<short HEAD>`. `manifest.json`
records the source (remote, HEAD, tree, branch, dirty paths, the audited commit), the machine, and every
step: command, start/end time, exit code, status and the SHA-256 of its redacted log. A failed or blocked
step stays in the record; nothing here is edited after capture.

All runs use the offline mock provider with secret-named variables removed: they exercise orchestration,
not AI coding quality. `data_kind` in each file says whether data is observed, synthetic or synthetic-mock.

| Capture | Source | Result | Notes |
| --- | --- | --- | --- |
| `20261025T173648Z-f01a108` | `main` `f01a108`, only untracked `scripts/` | suite: 376 passed, 8 skipped, 5 xfailed (exit 0) · browser subset: 38 passed, **1 failed** (exit 1) · synthetic trace: exit 0 | The browser-subset failure (`test_integrations.py` MCP stdio test) comes from this capture's interpreter: it saw `mcp` 2.3.0 from system site-packages, outside the `mcp>=1.12,<2` range in `pyproject.toml`. CI's browser job installs no `mcp` and skips that test. Kept as recorded. |
| `20261025T174908Z-abda17a` | `research/week1-evidence` `abda17a`, clean tree | suite: 391 passed, 8 skipped, 12 xfailed (exit 0) · browser subset: 38 passed, 1 skipped (exit 0) · synthetic trace: exit 0, final stage `done` · synthetic dry run: exit 0, 12 records valid | Browser subset ran in an isolated venv matching CI (`[dev]` + `playwright==1.63.0`, Chromium 153.0.8010.12, no `mcp`); the 1 skip is the MCP test, as in CI. Outputs hashed in `manifest.json` → `outputs`. |

A first capture attempt at 17:35 UTC was discarded, not kept. The capture script then removed
`GIT_CONFIG_KEY_<n>` but kept `GIT_CONFIG_COUNT`, which broke git for every test, and the run was stopped
part-way. The same defect in the product is finding W1-S1 (`docs/research/threat-model.md`).

Review every log for secrets before publishing it. Logs are redacted for known key shapes and for values
of secret-named variables, which is not a guarantee.

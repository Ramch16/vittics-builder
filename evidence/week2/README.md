# Week 2 evidence capture

One capture, `20261025T190715Z-bb76b2c`, of `research/week2-readiness` at `bb76b2c` (clean tree). The Week 1 branch tip `f5fd58c` was restored from the bundle, after its SHA-256 `65a5e9b1…` was verified, into a fresh clone. Mock provider only, with secret-named variables removed. These are AI-operated checks, not Sai's independent review.

| Step | Exit | Result |
| --- | --- | --- |
| suite (`pytest -q -rs -rxX`) | 0 | 404 passed, 8 skipped, 12 xfailed. The xfails are the known strict gaps SEC-01 ×3, SEC-03, SEC-05, W1-F1, W1-S2 and SEC-08 ×5 |
| browser-subset (isolated venv: `[dev]` + playwright 1.63.0, no mcp) | 0 | 38 passed, 1 skipped (MCP SDK not installed) |
| synthetic-dry-run | 0 | 12 schema-v2 synthetic records valid and consistent; 10 broken variants each caught |
| deps-snapshot / deps-snapshot-browser | 0 | 30 / 33 resolved packages; identical to the files audited below |
| pip-audit-pypi / pip-audit-pypi-browser | 0 | 0 known vulnerabilities in 30 / 33 packages (PyPI advisory service, at capture time) |
| pip-audit-osv | **1** | **Blocked**: proxy 403 to api.osv.dev. Not a result |
| npm-audit (desktop lockfile only) | 0 | 0 vulnerabilities in the npm tree |

The capture script exits 1 overall because the OSV step was blocked. That failure is kept as recorded. Cargo crates, Docker images and optional extras were not audited (see `docs/research/reproducibility-inventory.md`).

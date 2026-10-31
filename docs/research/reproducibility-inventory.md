# Reproducibility inventory (Week 2)

Prepared with AI assistance (Claude Code) on 2026-10-25 for **Sai**, who owns reliability, to review. This is a **resolved-version snapshot** of the environments Claude used. It is **not** a lockfile, and it is not a clean-environment reproduction on another machine. No dependency was pinned in the repository by this work.

## 1. Machine and tools used for Week 1–2 captures

| Item | Value | Notes |
| --- | --- | --- |
| OS | Linux 6.18.44 x86_64, glibc 2.39 | Ephemeral cloud container |
| Python | 3.13.17 (CPython, Clang 23.1.3 build) | CI uses 3.11 and 3.12. **3.13 is not in the CI matrix.** |
| Git | 2.43.0 | |
| Node / npm | 22.23.4 / 10.9.9 | Only needed for the desktop build (`@tauri-apps/cli`) |
| Rust / Cargo | cargo 1.97.0 | Present but unused; the desktop app was not built |
| Docker | CLI present, **daemon unavailable** | Docker sandbox mode and the hosted image were not exercised |
| Chromium (Playwright) | 153.0.8010.12 | Via `playwright==1.63.0` |

## 2. Python dependency snapshot

`pyproject.toml` declares open ranges (`pyyaml>=6`, `anthropic>=0.40`, `fastapi>=0.110`, `uvicorn>=0.29`, dev `pytest>=8`, `httpx>=0.27`). `pip install -e ".[dev]"` on 2026-10-25 resolved to these versions (`pip freeze --exclude-editable`, 30 packages):

| Package | Version | Package | Version |
| --- | --- | --- | --- |
| annotated-doc | 0.0.5 | idna | 3.20 |
| annotated-types | 0.8.0 | iniconfig | 2.3.1 |
| anthropic | 2.3.0 | jiter | 0.18.0 |
| anyio | 4.15.1 | opentelemetry-api | 1.45.1 |
| certifi | 2026.10.23 | packaging | 26.3 |
| click | 8.5.0 | pluggy | 1.7.0 |
| docstring_parser | 0.18.0 | pydantic | 2.14.1 |
| fastapi | 0.162.0 | pydantic_core | 2.50.1 |
| h11 | 0.16.0 | Pygments | 2.21.0 |
| httpcore | 1.0.9 | pytest | 9.1.1 |
| httpcore2 | 2.16.0 | PyYAML | 6.0.3 |
| httpx | 0.28.1 | sniffio | 1.3.1 |
| httpx2 | 2.16.0 | starlette | 1.10.0 |
| truststore | 0.10.5 | typing-inspection | 0.4.4 |
| typing_extensions | 4.16.0 | uvicorn | 0.54.0 |

The browser environment adds `playwright==1.63.0`, `greenlet==3.5.6` and `pyee==13.0.1` (33 packages).

## 3. Variants that change test outcomes

| Variant | Effect | Evidence |
| --- | --- | --- |
| `playwright` + Chromium absent | 7 browser tests skip in the main suite (as in CI's main jobs) | Week 1 captures, `-rs` skip reasons |
| `mcp` absent | `test_integrations.py:99` skips (as in CI's browser job) | Week 1 result capture |
| `mcp` 2.3.0 present (outside the declared `>=1.12,<2`) | The MCP stdio test **fails**: `TypeError: float + timedelta` in mcp's request clock, raised through `integrations.py:84` | Week 1 baseline capture `20261025T173648Z-f01a108` |
| Windows | `tests/test_security_boundaries.py` and the symlink test skip (POSIX shell / symlink rights); one desktop test skips on non-Windows | test markers |
| Host sets git config through `GIT_CONFIG_COUNT/KEY/VALUE` | On `main`, every git command in agent workspaces fails, because the scrub drops the KEYs but keeps COUNT. Fixed on the research branch (claim S-06) | `tests/test_tools.py::test_git_config_environment_is_scrubbed_as_a_set` |

The two Week 1 browser captures ran in different environments (system site-packages with `mcp` 2.3.0, versus an isolated venv without `mcp`). They are not a before/after comparison.

## 4. Git configuration the tests rely on

- Tests create repositories in pytest temp folders. Company git calls pass `user.name`/`user.email` with `-c` (`tools.py` `Workspace.git`). The CI workflow also sets a global identity and `core.autocrlf false`.
- Week 1–2 captures remove every secret-named environment variable. The capture script also drops the whole `GIT_CONFIG_*` set, so no host git credentials reach the tests.

## 5. Dependency audits performed (scope is exact; no wider claim)

| Scope | Tool / service | When (UTC) | Exit | Result | Disposition |
| --- | --- | --- | --- | --- | --- |
| 30 resolved Python packages (`[dev]`) | pip-audit 2.10.1, PyPI advisory service, `--no-deps --disable-pip` | 2026-10-25 19:00:27–19:00:29 | 0 | No known vulnerabilities | None needed. Advisory data as of that time only. |
| 33 resolved Python packages (`[dev]` + browser) | same | finished 2026-10-25 19:00:38 | 0 | No known vulnerabilities | same |
| Same 30 packages | pip-audit 2.10.1, **OSV service** | 2026-10-25 19:00:29 | 1 | **Blocked**: proxy refused `api.osv.dev` (403) | Not run; retry where OSV is reachable |
| Desktop npm tree (12 packages, `package-lock.json`) | npm 10.9.9 `npm audit --package-lock-only` | 2026-10-25 19:05:07 | 0 | 0 vulnerabilities reported | Build-time tool only |
| Rust crates (`Cargo.lock`, 422 packages) | — | — | — | **Not run**: `cargo-audit` not installed | Install `cargo-audit` and run before any desktop release |
| Docker base image and Debian packages | — | — | — | **Not run**: no daemon, no scanner | Scan before any hosted use |
| mcp, pyinstaller (optional extras) | — | — | — | Not in the audited sets | Audit when installed |

Raw redacted outputs are kept with the Week 2 evidence capture. "No known vulnerabilities" means the queried database had no matching advisory at that moment. It is not a security certification.

## 6. What full reproducibility still needs

1. A tested lockfile with hashes (proposal P-06) installed in CI, and a clean-machine reproduction on another OS.
2. Python 3.13 added to CI, or captures run on 3.11/3.12 to match CI.
3. `mcp<2` enforced in the browser environment, or `integrations.py` adapted to mcp 2.x with a test.
4. Docker-mode tests on a host with a daemon (Sai's environment), with synthetic fixtures only.
5. Base images pinned by digest.

# Threat model and execution-boundary matrix (draft)

Status: **draft, prepared with AI assistance (Claude Code), awaiting Sai's review.** Captured 2026-10-25 at
`main` `f01a108`. Scope: one company folder on one machine, its dashboard and the agents it runs. An AI-written
threat model is not an independent security audit. Findings below were reproduced only with synthetic files
and fake credentials, inside temporary folders.

## Assets

| Asset | Where it lives |
| --- | --- |
| Model API key | `.vittics/credentials.json` (mode 0600, `ai.py:52-63`) and the server's environment |
| CEO / CTO dashboard tokens | Server environment (`VITTICS_CEO_TOKEN`, `VITTICS_CTO_TOKEN`) or printed at start (`server.py`, `serve`) |
| Project secrets (vault) | `.vittics/vault/<project>.json` (mode 0600, `vault.py:33-38`) |
| Company records | `.vittics/company.db`: prompts, tool output, approvals, usage; plaintext |
| Product source and release evidence | `workspaces/<id>-<name>/` git repository, `docs/VERIFICATION.json`, `verification_runs` table |
| The host itself | Whatever the server's OS user can reach |

## Trust boundaries

1. **Human ↔ dashboard.** Bearer tokens in an `X-Token` header, compared with `secrets.compare_digest` (`server.py:169`). No rate limit or lockout. HTTPS is the operator's job.
2. **Agent ↔ workspace.** File tools confine paths with `resolve()` and refuse `.git` (`tools.py:215-233`). Shell commands run either on the host behind a regex deny list (`tools.py:20-38`), which is **not an OS sandbox**, or in Docker (`tools.py:270-277`).
3. **Agent ↔ host checks.** Product checks the CTO approved in `product.json` run through `Workspace.run_command` with the vault values as environment (`pipeline.py:907-935`, `validation.py:177-215`). Builders can ask for them with `run_approved_checks`. That makes the human approval of `product.json` the boundary: approved commands run agent-written product code with the project's secrets.
4. **CLI engine ↔ host.** CLI engines run on the host under each CLI's own permission model (`engines.py:20-58`), not the Docker sandbox.
5. **Company ↔ outside.** Federation peers (HMAC-signed envelopes, `federation.py:41-85`), worker machines (signed node calls, `server.py` `node_call`), URL-added skills (`skills.py:68-73`), customer feedback text.

## Engine/action policy matrix

What each execution path can do *as configured in code*. "Enforced by" names the mechanism. **Tested here**
means a test in this repository exercises it; nothing in this table was run against a real CLI install.

| Path | Read | Write | Execute | Network | Inherited credentials | Host-check escape | Supported / tested version | Enforced by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| API agent, `sandbox.mode: local` (default) | workspace files via tools; **any host file via shell** | workspace via tools; **anywhere the OS user can, via shell** | host shell, regex deny list | unrestricted | env minus secret-looking *names* (`KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIAL`); values in other names pass (SEC-03) | `run_approved_checks` (approved commands only) | n/a; tested (`test_tools.py`, `test_security_boundaries.py`) | regex only (SEC-01) |
| API agent, `sandbox.mode: docker` | mounted workspace (incl. `.git`) | mounted workspace (incl. `.git`) | container `sh -lc`, as root in the container, no CPU/memory/pid limits | none unless `docker_network: true` | none from host env (only `extra_env` names for checks) | same as above | Docker not exercised in this audit | container; **`.git` writable → host hooks (SEC-05)** |
| `cli:claude-code` | `Read`, `Glob`, `Grep` | `Edit`, `Write` when the role has write tools | `Bash` when the role has `run_command` | Claude Code's own | `engine_env`: scrubbed + `CLAUDE_CODE_OAUTH_TOKEN` (since #9) | `run_checks` action | Claude Code 2.1 per code comment; argv tested with a stand-in | `--allowedTools`/`--disallowedTools`, `--permission-mode acceptEdits`. **A role with `Bash` but no `Edit`/`Write` (reviewers) can still write files via the shell; "may run tests but not edit" is not enforced.** |
| `cli:codex` | `--sandbox read-only` | `--sandbox workspace-write` | allowed in both levels, inside Codex's sandbox | Codex default | scrubbed + `OPENAI_API_KEY`, `CODEX_API_KEY` | `run_checks` | Codex CLI 0.160.1 per code comment; not run here | Codex sandbox; no separate execute switch |
| `cli:gemini`, `cli:qwen` | **no flag** (CLI default) | `--yolo` (auto-approve everything) | not separately controlled | CLI default | scrubbed + own keys | `run_checks` | `verified: False`: flags from docs only | CLI default behaviour; read level is **not** an enforced read-only mode |
| `cli:copilot` | **no flag** | `--allow-all-tools` | not separately controlled | CLI default | scrubbed + `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN` | `run_checks` | `verified: False` | as above |
| `cli:cursor` | **no flag** | `--force` | not separately controlled | CLI default | scrubbed + `CURSOR_API_KEY` | `run_checks` | `verified: False` | as above |
| `cli:opencode` | **no flag** | `--dangerously-skip-permissions` | not separately controlled | CLI default | scrubbed + `*_API_KEY` | `run_checks` | `verified: False` | as above |
| Custom engine under `engines:` | whatever its `level_args`/`tools` say | same | same | its own | scrubbed + its `env_keep` only | `run_checks` | user-defined | user-defined |
| Unknown engine name | refused: the run ends with "Unknown engine" (`agent.py:258-262`; tested in `test_engines.py`) | — | — | — | — | — | — | code check |
| Host acceptance checks | host (or container in Docker mode, since checks use `pipeline.workspace()`) | same | the approved `product.json` commands | as the path above | **the project's vault values, by design** | — (this is the escape hatch) | tested (`test_approved_runner.py`, `test_evidence_registry.py`) | CTO approval of `product.json`; `same_contract` before every run |

Read this table as non-equivalent rows. Only `claude-code` maps role rights onto CLI tool permissions, and
even there shell access implies write. The five unverified adapters give builders blanket-approval flags and
give read-only roles no flag at all.

## Findings register

Severity is this draft's proposal for Sai to re-rate. "Reproduced" means a test or script in this repository shows it with fake data.

| ID | Severity (proposed) | Finding | Reproduction | Disposition |
| --- | --- | --- | --- | --- |
| SEC-01 | High | Regex deny list is bypassable (`cd ..` chains, quotes, absolute paths); agent shell reads vault and saved API key in local mode | `tests/test_security_boundaries.py` (strict xfail) | Open; proposal P-04 |
| SEC-02 | High | CLI engines inherited dashboard tokens and other keys | `tests/test_engines.py` (passes since #9) | **Fixed in #9** |
| SEC-03 | Medium | Name-based env scrub passes secrets inside other names (`DATABASE_URL`) | `tests/test_security_boundaries.py` (strict xfail) | Open |
| SEC-04 | Medium | Either token could set autopilot that decided the other person's gates | `tests/test_idea_to_production.py` (passes since #10) | **Fixed in #10** |
| SEC-05 | High (Docker) | `.git` is writable from agent commands; a planted hook runs on the company's commit on the host | `tests/test_security_boundaries.py` (strict xfail, local mode); Docker path inferred from `tools.py:271` | Open; proposal P-05 |
| SEC-06 | Medium | Hosted image has no Docker, so agent commands run as the server's user beside `company.db`, the vault and credentials | code reading (`Dockerfile`, `hosting.py:17-19`) | Open |
| SEC-07 | Medium | Vault values reach agent-written product code during host checks; redaction is exact-string only | code reading (`vault.py:66-70`, `pipeline.py:915`) | Open; intended behaviour, needs explicit approval wording |
| SEC-08 | Medium | Unverified CLI adapters: blanket write flags; no read-only flag | this table; `engines.py:29-43` | Open |
| SEC-11 | Needs test | Prompt-injection surfaces: ticket text, customer feedback, federation proposals, memory, URL-added skills (http allowed, no hash) | not tested | Weeks 9–10 |
| W1-S1 | Low | The env scrub removed `GIT_CONFIG_KEY_<n>` but kept `GIT_CONFIG_COUNT`, so git inside agent commands fails when the host sets git config through the environment (found while capturing evidence). | `tests/test_tools.py::test_git_config_environment_is_scrubbed_as_a_set` | **Fixed on this branch** (`tools.scrub_env`), pending review |
| W1-S2 | Medium | A task whose review roles cannot be staffed passes with zero reviews | `tests/test_week1_negative.py` (strict xfail) | Open |

## What existing scanners do and do not establish

- `Security.scan` (`security.py:13-30`) is a bounded prefix scanner. It reads ≤1000 files of ≤500 KB in the current tree and looks only for `sk-ant-`/`sk-proj-` prefixes. It skips `.env*` files, `.vittics/`, symlinks, binaries and git history. A clean result does not establish secret safety.
- `Security.dependencies` (`security.py:32-55`) queries OSV only when `security.osv_enabled: true` and every line of `requirements.txt` is pinned with `==`. **No OSV or other vulnerability scan was executed for this audit**, so no vulnerability claim is made either way.

## Human review required

| Owner | Needed | Status |
| --- | --- | --- |
| Sai | Re-rate severities; reproduce SEC-01/03/05, W1-S1, W1-S2 independently; record affected scope and disposition | **Not received** |
| Nikhil | Decide whether reviewers on CLI engines must lose shell access, and the policy for unverified adapters | **Not received** |

Report any genuine vulnerability privately as `SECURITY.md` describes; do not post exploit details publicly.

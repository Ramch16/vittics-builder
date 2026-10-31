# Security findings register, status on 31 October 2026

Source revision: branch `fix/review-and-isolation-policies` (commit `fe67526`) on top of
`research/week2-readiness` (`5bd0eab`). Earlier registers: `threat-model.md`, `week2-evidence-readiness.md` §4.

Status words: **fixed** = a regression test reproduced the problem and passes after the change;
**fixed (scoped)** = fixed only in the stated scope; **open** = not fixed; **untested** = no test exists.
None of these has been independently reproduced by a person yet; that is Sai's packet
(`task-packets/sai-security.md`).

| ID | Finding | Status | Evidence |
| --- | --- | --- | --- |
| SEC-01 (S-01) | Agent commands in local mode can read the company's vault and saved API keys | **Fixed (scoped):** Linux with working bubblewrap and macOS with sandbox-exec. **Open** on Windows and on Linux without bubblewrap | `test_agent_shell_cannot_read_vault_by_changing_directory`, `test_agent_shell_cannot_read_saved_api_key_by_absolute_path` pass with bubblewrap 0.9.0; xfail without it (both runs recorded) |
| SEC-01 (quoted path) | `cat '/etc/hosts'` slipped past the deny list | **Fixed** (deny list is a seatbelt, not isolation) | `test_quoted_system_path_is_refused` |
| SEC-02 (S-04) | CLI engines inherited dashboard tokens and keys | **Fixed** on `main` (PR #9) | `test_cli_engines_do_not_inherit_the_dashboard_tokens_or_other_keys` |
| SEC-03 (S-03) | Passwords inside other variables (`DATABASE_URL`) reached commands | **Fixed:** URL-credential values are dropped; local-mode commands get an allowlisted environment | `test_credentials_in_connection_urls_do_not_reach_commands`, `test_unrelated_environment_does_not_reach_commands` |
| SEC-04 (S-05) | The CTO could autopilot the CEO's gates | **Fixed** on `main` (PR #10) | `test_autopilot_only_decides_for_whoever_chose_it` |
| SEC-05 (S-02) | A git hook planted by an agent ran on the company's commit | **Fixed (scoped):** the company's git calls disable hooks and fsmonitor. Docker mode's writable `.git` mount (P-05b) is **open and untested** | `test_agent_planted_git_hook_does_not_run_on_company_commit`, `test_git_fsmonitor_planted_by_an_agent_does_not_run` |
| SEC-06 (S-09) | The hosted image has no Docker, so commands run beside the company data | **Open, untested.** The sandbox backends above apply if the image ships bubblewrap and user namespaces work; not verified | — |
| SEC-07 (S-07) | Vault values reach agent-written product code during host checks | **Open by design.** Nothing persisted holds the values | `test_vault_canary_reaches_checks_but_no_stored_record` |
| SEC-08 (S-08) | Unverified CLI adapters had no read-only flag | **Mitigated:** refused for read-only roles in a workspace (D5). Adapters are still unverified | `test_unverified_adapters_refuse_read_only_roles_in_a_workspace` (5 cases) |
| Reviewer Bash | A Claude Code reviewer got Bash, which can write files | **Fixed:** reviewer roles have no shell (D4) | `test_reviewer_roles_get_no_shell`, `test_review_through_a_cli_on_the_subscription` |
| SEC-09 (S-10) | Docker sandbox has no user, pids or memory limits | **Open, untested** (no Docker daemon in this environment) | — |
| SEC-10 (S-11) | Dashboard tokens static, no rate limit; desktop CSP null | **Open, untested** | — |
| SEC-11 (S-12) | Prompt-injection surfaces | **Open, untested** (Weeks 9–10) | — |
| SEC-12 (S-13) | Plaintext SQLite; secrets files mode 0600 | **Open** (scope decision needed) | — |
| W1-S1 (S-06) | The git environment config set was split by the secret filter | **Fixed** on `research/week1-evidence` | `test_git_config_environment_is_scrubbed_as_a_set` |
| A-01 (W1-F2/W1-S2) | Tasks done with zero reviews | **Fixed** (D1/D2) | `test_no_task_is_done_without_an_independent_review` |

## Residual risks to state plainly

- The OS sandbox hides one folder; it is not full isolation. Commands still run as the user, with network
  access and the rest of the filesystem. Docker mode remains the recommendation for untrusted prompts.
- bubblewrap needs unprivileged user namespaces. `sandbox_backend()` runs a trial and falls back to no
  sandbox when the trial fails, so on such a machine SEC-01 is open, silently from the agent's side. The
  dashboard does not yet tell the user which mode is active (proposed follow-up).
- The macOS sandbox-exec path is implemented but was **not run** here (Linux only). CI's macOS job is its
  first test.
- No dependency vulnerability scan was rerun for this change (the Week 2 PyPI audit stands; OSV, cargo and
  Docker image scans are still blocked or not run).

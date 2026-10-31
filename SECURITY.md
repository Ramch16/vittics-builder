# Security

Vittics Builder runs AI agents that read, write and execute code. Please report security problems
privately to the maintainer (open a GitHub security advisory on the repository) rather than in a
public issue.

What Vittics Builder protects:
- Agents' commands in local mode get an allowlisted environment (PATH, HOME, locale, toolchain and proxy
  variables). Secret-looking names (`KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIAL`) and any value that
  embeds a URL password (such as `DATABASE_URL=postgres://user:pass@host`) are removed. CLI engines get the
  scrubbed environment, except for the login each one signs in with (its `env_keep`).
- In local mode, the company's `.vittics` folder (vault, saved keys, dashboard tokens, database) is hidden
  from agents' commands by bubblewrap on Linux or sandbox-exec on macOS, when a trial run shows it works.
- The company's git calls run with hooks and fsmonitor disabled.
- Reviewer roles have no shell; built-in CLI adapters without a verified read-only mode are refused for
  read-only roles.
- File tools cannot leave the project workspace; a deny list blocks privilege escalation,
  deleting outside the workspace, piping downloads into a shell and `git push`.
- With `sandbox.mode: docker`, agents' commands run in a container: no network unless allowed, no privilege
  gain (`no-new-privileges`), at most 1024 processes and 4 GB of memory, the NET_RAW, MKNOD, AUDIT_WRITE and
  SETFCAP capabilities dropped, and the workspace's `.git` mounted read-only.
- After ten wrong dashboard tokens from one address within five minutes, sign-in is refused for that address
  (HTTP 429) until the window passes.
- Dashboard access needs a CEO or CTO token. Keep it on localhost or behind HTTPS (e.g. Tailscale).

What it does not protect against:
- CLI engines (`cli:claude-code` and others) run on your machine under the CLI's own permission
  rules, not in the Docker sandbox.
- The deny list is a seatbelt, not a sandbox, in `sandbox.mode: local`. Without bubblewrap or sandbox-exec
  (Windows; Linux without bubblewrap or without unprivileged user namespaces), agents' commands can read
  the company's `.vittics` folder.
- Docker mode still runs commands as the image's user (root in the default image), and these limits have been
  checked as command-line arguments only, not against a running Docker daemon.
- AI audits are not a substitute for a professional security review.

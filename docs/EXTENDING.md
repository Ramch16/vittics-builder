# Connections, organization management and portable teams

These are extension foundations, not a hosted public marketplace or multi-tenant
identity system. Companies still use separate company folders/databases and the
existing CEO/CTO accounts. A community requires real adoption and contributors;
adding these interfaces does not establish ecosystem parity with Paperclip.

## Local and remote MCP connections

Install `pip install -e '.[mcp]'`. Existing stdio configuration continues working.
Streamable HTTP requires MCP SDK 1.30 or later (declared by the extra). Review
`examples/integrations/remote-mcp.yaml`, merge the connections you want into your
company's `org.yaml`, set the roles/tools explicitly, enable the selected entry,
and restart the company service. Entries in the example are disabled by default.

```yaml
tools:
  mcp:
    documentation:
      enabled: true
      transport: streamable_http
      url: https://learn.microsoft.com/api/mcp
      roles: [architect, tech_writer]
      tools: [microsoft_docs_search, microsoft_docs_fetch]
```

Remote connections support public endpoints or pre-provisioned credential headers:

```yaml
headers_env:
  Authorization: VITTICS_GITHUB_AUTHORIZATION
```

Set that environment variable to the complete header value, such as `Bearer <PAT>`;
do not put actual credentials in org.yaml, examples or packages. The service must
inherit the variable. Header bindings require a secret-labelled variable (for
example AUTH, TOKEN or KEY in its name), or a Bearer/Basic value, so unrelated
child processes filter it out of their inherited environment. Requests use HTTPS, except HTTP on literal loopback hosts;
URL credentials, query strings and fragments are refused. Redirects are not
followed, and proxy/credential environment variables are not inherited by the
remote HTTP client. Public service availability, server tool names and account
permissions still depend on the provider. This is not an OAuth login/token-refresh
implementation. It does not support arbitrary SSE-only legacy endpoints, resources
or prompts; the current integration surface is MCP tools.

GitHub's read-only endpoint and Microsoft Learn are documented examples:
- [GitHub remote MCP documentation](https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md)
- [Microsoft Learn MCP developer reference](https://learn.microsoft.com/en-us/training/support/mcp-developer-reference)

The example profiles were checked against those provider docs; authenticated
provider accounts were not connected or exercised by the test suite. The remote
transport itself is tested against a real local MCP HTTP server, with bound
headers and allowed/denied tools. External MCP servers are trusted integrations:
review their permissions and data destinations before enabling them. Enabling a
write tool authorizes agents in its role allowlist to call it; this change does
not add per-call human approval prompts.

Inspect configuration without disclosing endpoint URLs or header values:

```sh
vittics-builder integrations
vittics-builder integrations --server documentation --role architect --project 1
```

The second command contacts that server and lists its allowed advertised tools;
it does not invoke a model or call service actions. Missing credentials in the
inventory are a local configuration check, not proof of remote access. Operations
shows the connection inventory, transports and role/tool scopes. `enabled: false`
hides and blocks the connection even if another enabled server grants MCP access.

## Organization editing

The Team page supports adding/editing departments and roles and reassigning agents.
Empty departments remain visible so newly created teams can be configured and
staffed. Role editing changes titles, responsibilities, department and tool grants;
work type is fixed for existing roles. Use a new role for a different work type.

The CEO manages the whole organization. The CTO can edit their departments and
roles, and reassign agents only when both source and destination report to the
CTO. Only the CEO creates departments or changes reporting lines. The API enforces
these rules independently of which buttons the dashboard displays.

Reassignment preserves the agent's identity, model, seat identity and history;
it does not retrain a model or reset performance. Transfer or finish existing
assignments first. Running agents prevent restructuring their department; active
ticket reviews also block department/role edits. Changes apply to subsequent work.
This is not nested management hierarchies, arbitrary human accounts or RBAC.

```sh
vittics-builder org update-dept engineering --name 'Product Engineering' --as ceo
vittics-builder org update-role backend_engineer --title 'API engineer' --tools read_file,write_file,run_command --as cto
vittics-builder org reassign Hari --role frontend_engineer --as cto
```

API equivalents (authenticated via the existing X-Token mechanism):

| Operation | Endpoint |
| --- | --- |
| Connection inventory | GET `/api/integrations` |
| Create department | POST `/api/organization/departments` |
| Rename/change reporting line | PATCH `/api/organization/departments/{id}` |
| Create role | POST `/api/organization/roles` |
| Inspect/edit role | GET/PATCH `/api/organization/roles/{id}` |
| Reassign agent | POST `/api/agents/{id}/reassign` with `{"role":"destination_role"}` |

## Publish and share portable teams

A version 1 bundle contains `schema_version`, `sha256`, `manifest` and `assets`.
The manifest holds a name, semantic version, optional description, departments
and roles. Assets are bounded Markdown skills. `examples/teams/research.json` and
`support.json` are installable reference bundles; they do not create paid agents.
Choose a bundle, inspect all content, and obtain its SHA-256 from a trusted source.
The pin detects changes; it does not authenticate the publisher.

```sh
vittics-builder marketplace import --bundle examples/teams/research.json --sha256 <reviewed-sha256>
vittics-builder marketplace list
vittics-builder marketplace install --name examples/research@1.0.0 --sha256 <reviewed-sha256>
vittics-builder marketplace export --name examples/research@1.0.0 --bundle research-share.json
```

Import registers content for review; installation is a separate explicit step.
Export refuses existing output files. Install verifies the stored checksum, refuses
role collisions and department changes, and rolls back created departments/roles
and skill files if installation fails. Compatible existing departments may be
reused. Staff imported roles explicitly with `org hire` after choosing a runtime.
The CEO controls import/export/installation through the API and role-aware CLI.

API: GET `/api/marketplace/export?name=...`; POST `/api/marketplace/import` with
`{"bundle":{...},"sha256":"reviewed-pin"}`. Existing registration and installation
endpoints remain supported. Bundles contain package content, not company database
snapshots, live credentials, projects, routines or complete agent histories. Prompts
and Markdown may contain sensitive author-supplied text: review before sharing.

## Contributing an extension

1. Use `examples/integrations/release_notes_server.py` as a minimal MCP server.
   It defaults to stdio; `--http` runs a loopback HTTP server on port 8088.
2. Document inputs, outputs, read/write actions, authentication requirements,
   data destinations, timeouts and failure behavior. Start with read-only tools.
3. Add an explicit server configuration and the smallest role/tool allowlist.
   Third-party adapters run as MCP services, not in-process Python imports.
4. For team packages, use unique role/department identifiers, increment versions
   for changed content and include the reviewed checksum. No install hooks,
   executable assets or connection credentials are accepted in packages.
5. Submit fixture-backed tests for permissions, invalid input, timeouts and
   credential isolation. Optional remote-service tests must not need live keys.

The repository accepts examples through normal pull requests. There is no public
publisher verification service, automatic package downloader or plugin store yet.

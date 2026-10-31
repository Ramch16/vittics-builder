# T06 Configuration migration

Implement `app/migrate.py`: `migrate(config: dict) -> dict` returns the configuration at version 3.

Versions
- v1: `{"version": 1, "db_host": str, "db_port": int, ...}`
- v2: `{"version": 2, "database": {"host": str, "port": int}, ...}`
- v3: v2 plus `"timeouts": {"connect": int}`; `connect` comes from v1/v2 key `connect_timeout` if present
  (which is then removed), else 10.

Requirements
- R1 v1 and v2 inputs are migrated step by step to v3; other keys are kept unchanged.
- R2 A v3 input returns an equal copy (idempotent): `migrate(migrate(x)) == migrate(x)`.
- R3 Missing or unsupported `version` (including bools and versions above 3) raises `UnsupportedVersion`.
- R4 A v1 config without `db_host` or `db_port` raises `ValueError`.
- R5 The input is never modified, including nested dicts, even when migration fails.

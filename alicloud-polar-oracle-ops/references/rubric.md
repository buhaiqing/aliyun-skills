---
name: alicloud-polar-oracle-ops-rubric
description: >-
  GCL rubric for `alicloud-polar-oracle-ops` (PolarDB Oracle-compatible,
  polarDB-IO 2021-11-26 API, Oracle 11g/12c/19c engine). Inherits the
  canonical PolarDB rubric from `alicloud-polar-mysql-ops` with
  Oracle-specific deviations. Phase 1, thirteenth skill.
license: MIT
metadata:
  skill: alicloud-polar-oracle-ops
  api: polardb-io 2021-11-26
  engine: oracle
  cli_applicability: dual-path
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
    - ../../alicloud-polar-mysql-ops/references/rubric.md  # CANONICAL
---

# PolarDB Oracle GCL Rubric (Phase 1 — Thirteenth Skill)

> **Inherits the canonical PolarDB rubric from
> [`alicloud-polar-mysql-ops/references/rubric.md`](../../alicloud-polar-mysql-ops/references/rubric.md).**
> Read the canonical first. This file documents **only the Oracle-specific
> deviations**.

## Oracle-Specific Deviations

### B1. SQL Engine Substitution

| Aspect | MySQL canonical | Oracle deviation |
|---|---|---|
| Client | `mysql` | `sqlplus` (or `sqlcl`) |
| Endpoint hostname suffix | `pc-xxxx.mysql.polardb.rds.aliyuncs.com` | `pc-xxxx.oracle.polardb.rds.aliyuncs.com` |
| Default port | 3306 | 1521 |
| Password env var | `MYSQL_PWD` | `ORACLE_PASSWORD` (or `sqlplus` accepts via `conn username/password@//host:1521/service`) |
| Schema operations | `DROP DATABASE` | `DROP USER ... CASCADE` (no DROP DATABASE in Oracle) |
| Show structure | `DESCRIBE table` | `DESC table` (sqlplus) or `DBA_TAB_COLUMNS` query |
| High-risk maintenance | `OPTIMIZE TABLE` | `TRUNCATE TABLE ... DROP STORAGE` / `SHRINK SPACE` |
| Durable cluster setting | N/A | `ALTER SYSTEM SET ... SCOPE=SPFILE` (persistent) or `SCOPE=BOTH` |
| Privilege | `GRANT ALL ON *.*` | `GRANT DBA TO user` (over-privileged) |

### B2. Additional Regex Hot-Spots (Oracle)

| Regex | Risk | Examples |
|---|---|---|
| `^drop\s+user\s+\S+\s+cascade` | DESTRUCTIVE-MASS | `DROP USER legacy_app CASCADE;` |
| `^alter\s+system\s+set\b.*scope\s*=\s*spfile` | CONFIG-MUTATION (durable) | `ALTER SYSTEM SET processes=500 SCOPE=SPFILE;` |
| `^alter\s+system\s+kill\s+session` | LOCK-RISK (kills a session) | `ALTER SYSTEM KILL SESSION '123,4567';` |
| `^alter\s+database\s+(datafile|tempfile)\s+resize` | FATAL (storage change) | `ALTER DATABASE DATAFILE '...' RESIZE 10G;` |
| `^alter\s+system\s+switch\s+logfile` | CONFIG-MUTATION | Forces a log switch |
| `^drop\s+tablespace\b` | DESTRUCTIVE-MASS | `DROP TABLESPACE legacy INCLUDING CONTENTS;` |
| `^revoke\s+dba` | PRIVILEGE-LOSS | `REVOKE DBA FROM app_user;` |
| `^truncate\s+table\s+\w+\s+drop\s+storage` | DESTRUCTIVE-MASS | `TRUNCATE TABLE users DROP STORAGE;` |
| `grant\s+dba\b` | PRIVILEGE-ESCALATION | `GRANT DBA TO new_admin;` |

### B3. PL/SQL-Specific Risks

- **`BEGIN ... EXECUTE IMMEDIATE 'DROP USER ...';`** — Oracle can wrap DDL
  in PL/SQL blocks. The Critic must pattern-match the inner SQL.
- **`UTL_FILE` package** — file I/O from inside the DB. Risky if the
  stored procedure can write to OS paths. Cross-skill audit recommended.
- **`DBMS_SCHEDULER` jobs** — scheduling destructive procedures.

### B4. Engine-Specific Credential Surface

| Secret | Where it appears | Sanitization regex |
|---|---|---|
| `ORACLE_PASSWORD` | Env var | `(ORACLE_PASSWORD=)[^ ]+` → `<masked>` |
| `POLARDB_ORACLE_NEW_PASSWORD` | Env var | `(POLARDB_ORACLE_NEW_PASSWORD=)[^ ]+` → `<masked>` |
| `sqlplus user/pass@//host:1521/service` | CLI | `(sqlplus\s+\S+/)\S+(@)` → `$1<masked>$2` |
| `tnsnames.ora` content | Connection descriptor | Not a secret, but may contain host/port enumeration |

## Worked Example

`DROP USER ... CASCADE` PASS (with backup):

```json
{
  "iter": 1,
  "generator": {
    "command": "sqlplus sys/<masked>@//pc-bp1...:1521/PDB1 as sysdba -c 'DROP USER legacy_app CASCADE;'",
    "exit_code": 0
  },
  "preflight": {
    "user_confirmation": "User confirmed: 'drop user legacy_app CASCADE, expdp backup completed at /backup/legacy_app-20260604.dmp'",
    "backup_trace": [
      {"command": "expdp system/<masked>@//pc-bp1...:1521/PDB1 schemas=legacy_app dumpfile=legacy_app-20260604.dmp", "result": "1.2GB written", "exit_code": 0}
    ]
  },
  "critic": { "scores": { "correctness": 1, "safety": 1, "idempotency": 1,
    "traceability": 1, "spec_compliance": 1, "region_compliance": 1,
    "credential_hygiene": 1, "well_architected": 1 }, "blocking": false },
  "decision": "PASS"
}
```

## Anti-Patterns (Oracle-specific additions)
- ❌ `DROP USER ... CASCADE` without `expdp` backup
- ❌ `ALTER SYSTEM SET ... SCOPE=SPFILE` without backup of original value
- ❌ `GRANT DBA TO user` (privilege escalation — requires justification)
- ❌ `DROP TABLESPACE ... INCLUDING CONTENTS` without backup
- ❌ `REVOKE DBA FROM user` (privilege loss) without confirmation


### Wrapper Compliance (per `AGENTS.md` §15.8 + GCL §3, §14.2.4)

**Definition:** Every `aliyun <product>` invocation against this skill
MUST be routed through `scripts/<product>-skillopt-wrapper.sh`, not
invoked as a bare CLI call. A direct call is a **silent bypass** that
strips self-repair, Langfuse tracing, and circuit-breaker protection.

| Score | Meaning |
|:-----:|---------|
| **1** | The command was routed through the skillopt wrapper (or a non-aliyun path: SDK / data-plane tool / no-wrapper skill) |
| **0** | The command is a direct `aliyun <product>` call while the skill's `scripts/*-skillopt-wrapper.sh` exists — **WRAPPER_BYPASS** |

**Trace field (added in GCL v1.8.0):** `iterations[].generator.execution_path`
records one of `wrapper` | `direct_aliyun` | `sdk_jit` | `data_plane` | `other`.


## Changelog
1.0.0 | 2026-06-04 | PolarDB Oracle GCL rubric (Phase 1, thirteenth skill). Inherits canonical from polar-mysql-ops; adds 9 Oracle-specific regex hot-spots and 4 Oracle-specific credential patterns. PL/SQL DDL-in-block risk noted.

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

## Worked Examples

> **Per AGENTS.md §8.2: all Examples below use read-only or safe-write ops only.**
> No `DROP USER` / `DROP TABLESPACE` / `ALTER SYSTEM` in any Example.

### Example 1: `DescribeDBClusters` PASS (read-only listing)

Use case: User asks "list all PolarDB-Oracle clusters in cn-hangzhou".

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun polardb DescribeDBClusters --RegionId cn-hangzhou --PageSize 10",
    "exit_code": 0,
    "result_excerpt": "{\"Items\":{\"DBCluster\":[{\"DBClusterId\":\"pc-bp1xxxx\",\"DBClusterStatus\":\"Running\",\"Engine\":\"Oracle\"}]}}",
    "request_id": "F3E4..."
  },
  "critic": {
    "scores": {
      "correctness": 1.0, "safety": 1.0, "idempotency": 1.0,
      "traceability": 1.0, "spec_compliance": 1.0,
      "region_compliance": 1.0, "credential_hygiene": 1.0,
      "well_architected": 1.0, "wrapper_compliance": 1.0
    },
    "blocking": false
  },
  "decision": "PASS"
}
```

**Why it passes:** `DescribeDBClusters` is read-only; engine filter confirms Oracle; region matches; response includes `DBClusterId` + `DBClusterStatus`; `RequestId` present.

### Example 2: `CreateAccount` PASS (safe-write with env-var password)

Use case: User asks "create a PolarDB-Oracle account for the app".

**Cost / safety guardrails (mandatory):**
- `AccountName = app_service` (NOT in {sys, system, oracle} reserved set)
- `AccountPassword` delivered via `$ORACLE_PASSWORD` env var (NOT CLI flag)
- `AccountType = Normal` (NOT Super — least privilege)
- Password complexity met (Oracle-specific)

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun polardb CreateAccount --DBClusterId pc-bp1xxxx --AccountName app_service --AccountPassword $ORACLE_PASSWORD --AccountType Normal",
    "exit_code": 0,
    "result_excerpt": "{\"RequestId\":\"Z5X6...\"}",
    "request_id": "Z5X6..."
  },
  "preflight": {
    "uniqueness_check": "DescribeAccounts --AccountName app_service → empty (name available)",
    "user_confirmation": "User confirmed: 'create account app_service on pc-bp1xxxx'"
  },
  "critic": {
    "scores": {
      "correctness": 1.0, "safety": 1.0, "idempotency": 1.0,
      "traceability": 1.0, "spec_compliance": 1.0,
      "region_compliance": 1.0, "credential_hygiene": 1.0,
      "well_architected": 1.0, "wrapper_compliance": 1.0
    },
    "blocking": false
  },
  "decision": "PASS"
}
```

**Why it passes:** `DescribeAccounts` called first to verify name uniqueness; `AccountName` not in reserved set; password via env var (`$ORACLE_PASSWORD` per Polar-Oracle convention); `AccountType = Normal`.

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
1.1.0 | 2026-07-12 | Per AGENTS.md §8.2: Worked Example rewritten to use read-only `DescribeDBClusters` + safe-write `CreateAccount` (previously demonstrated `DROP USER ... CASCADE` which violates §8.2).

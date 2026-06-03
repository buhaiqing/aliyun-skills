---
name: alicloud-polar-pg-ops-rubric
description: >-
  GCL rubric for `alicloud-polar-pg-ops` (PolarDB PostgreSQL 2021-11-26
  API — **legacy/v1** variant). Inherits canonical from
  `alicloud-polar-mysql-ops`; shares PG-specific deviations with
  `alicloud-polar-postgresql-ops`. Phase 1, fourteenth skill.
license: MIT
metadata:
  skill: alicloud-polar-pg-ops
  api: polardb-pg 2021-11-26
  engine: postgresql
  cli_applicability: dual-path
  rubric_version: "1.0.0"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
    - ../../alicloud-polar-mysql-ops/references/rubric.md  # CANONICAL
    - ../../alicloud-polar-postgresql-ops/references/rubric.md  # PG variant
---

# PolarDB PG (2021) GCL Rubric (Phase 1 — Fourteenth Skill)

> **Inherits the canonical PolarDB rubric from
> [`alicloud-polar-mysql-ops/references/rubric.md`](../../alicloud-polar-mysql-ops/references/rubric.md)
> AND the PostgreSQL-specific deviations from
> [`alicloud-polar-postgresql-ops/references/rubric.md`](../../alicloud-polar-postgresql-ops/references/rubric.md).**
>
> The two PolarDB PostgreSQL skills (`alicloud-polar-postgresql-ops` and
> `alicloud-polar-pg-ops`) are **API variants of the same engine**:
>
> | Aspect | `alicloud-polar-postgresql-ops` | `alicloud-polar-pg-ops` |
> |---|---|---|
> | API version | PolarDB 2022-05-30 | polardb-pg 2021-11-26 |
> | Engine | PostgreSQL 11/12/13/14/15 | PostgreSQL 11/12/13/14 |
> | Status | Current | Legacy / v1 |
> | CLI / SDK | `aliyun polardb` (unified) | `aliyun polardb-pg` (separate) |
>
> **Read both rubrics; the PG-specific deviations (hot-spots, credential
> surface) apply identically.** This file documents only the
> API-version-specific deviations.

## API-Version Deviations (polar-pg-ops 2021-11-26)

### C1. CLI Path

| Canonical (polar-mysql) | polar-pg-ops deviation |
|---|---|
| `aliyun polardb ...` | `aliyun polardb-pg ...` (separate product) |
| `polardb-2022-05-30` SDK | `polardb-pg-2021-11-26` SDK |

### C2. Endpoint Hostname Suffix

| Canonical (polar-mysql) | polar-pg-ops deviation |
|---|---|
| `pc-xxxx.mysql.polardb.rds.aliyuncs.com` | `pc-xxxx.pg.polardb.rds.aliyuncs.com` |

(The `aliyun polardb` (2022) family uses `pc-bp1xxxxx.pg.polardb.rds.aliyuncs.com`; the legacy `polar-pg` family uses a different prefix. Confirm the actual hostname from `DescribeDBClusterEndpoint` response.)

### C3. Operation Name Differences

A few control-plane operations differ in name (not in semantics) between
the two PolarDB PG APIs. The Critic MUST verify the operation name
matches the skill's API:

| Action | `polardb` 2022-05-30 | `polar-pg` 2021-11-26 |
|---|---|---|
| Create cluster | `CreateDBCluster` | `CreateDBInstance` |
| Delete cluster | `DeleteDBCluster` | `DeleteDBInstance` |
| Describe cluster | `DescribeDBClusterAttribute` | `DescribeDBInstanceAttribute` |
| Create account | `CreateAccount` | `CreateAccount` (same) |
| Reset account password | `ResetAccountPassword` | `ResetAccountPassword` (same) |

> **GCL implication:** A trace that uses the 2022-05-30 operation name
> while the skill declares `polardb-pg 2021-11-26` API is a **Spec
> Compliance = 0** finding (wrong API for the skill).

### C4. Engine Version Range

| Skill | Supported engine versions |
|---|---|
| `alicloud-polar-postgresql-ops` | PostgreSQL 11 / 12 / 13 / 14 / 15 |
| `alicloud-polar-pg-ops` (this) | PostgreSQL 11 / 12 / 13 / 14 (no 15) |

Critic MUST reject operations requesting PG 15 on this skill.

## Termination Thresholds

Identical to canonical PolarDB rubric. `max_iter=2`. Safety=0 or Credential
Hygiene=0 → ABORT.

## Worked Example

`DeleteDBInstance` (polar-pg-ops 2021) PASS:

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun polardb-pg DeleteDBInstance --DBInstanceId pc-bp1... --RegionId cn-hangzhou",
    "exit_code": 0
  },
  "preflight": {
    "user_confirmation": "User confirmed: 'delete pc-bp1... (legacy-pg-cluster), backup pc-bp1-final created.'",
    "backup_trace": [
      {"command": "aliyun polardb-pg CreateBackup --DBInstanceId pc-bp1...", "result": "BackupId pc-bp1-final", "status": "Success"}
    ]
  },
  "critic": { "scores": { "correctness": 1, "safety": 1, "idempotency": 1,
    "traceability": 1, "spec_compliance": 1, "region_compliance": 1,
    "credential_hygiene": 1, "well_architected": 1 }, "blocking": false },
  "decision": "PASS"
}
```

## Anti-Patterns (polar-pg-ops specific)
- ❌ Using `polardb 2022-05-30` operation names on this skill (use 2021-11-26 names)
- ❌ Requesting PG 15 (not supported on 2021-11-26 API)

## Changelog
1.0.0 | 2026-06-04 | PolarDB PG (2021) GCL rubric (Phase 1, fourteenth skill). Inherits canonical from polar-mysql-ops AND PG-specific from polar-postgresql-ops; documents the 2021-11-26 vs 2022-05-30 API version deviations (CLI path, operation names, engine version range).

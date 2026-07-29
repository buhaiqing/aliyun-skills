---
name: alicloud-clickhouse-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-clickhouse-ops`. Phase 1, dual-path skill
  (Enterprise Edition CLI 2023-05-22 + Classic Edition SDK 2019-11-11).
license: MIT
metadata:
  skill: alicloud-clickhouse-ops
  api: clickhouse 2023-05-22 (Enterprise) / clickhouse 2019-11-11 (Classic)
  cli_applicability: dual-path
  rubric_version: "1.0.0"
  last_updated: "2026-07-29"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
---

> **GCL delegation**: GCL execution is delegated to `alicloud-gcl-runner-ops` (shared skill).
> See [`gcl-execution.md`](../../alicloud-gcl-runner-ops/references/gcl-execution.md) for integration details.

# ClickHouse GCL Prompt Templates (Phase 1 — Dual-Path Skill)

Inherits structure from `AGENTS.md` §12.7. ClickHouse-specific additions:
**Edition-aware path selection** (Enterprise CLI vs Classic SDK); **6 destructive
operation classes**; **destructive op = explicit confirmation + backup-first
for restart/upgrade/delete**; **serverless scaling needs explicit `NodeScaleMax`**.

> Critic in isolated context. `{{user.request}}` absent from Critic template.

## 1. Generator Prompt Template

| `{{recent_executions}}` | R2 `memory_preflight.py` (Layer 1) | Recent PASS/FAIL for this operation |
| `{{known_traps}}` | R2 `memory_preflight.py` (Layer 2) | Known failure patterns — do not repeat |
| `{{strategy_hints}}` | R2 `memory_preflight.py` (Layer 3) | Weekly strategy hints (read-only) |
| `{{success_patterns}}` | R2 `memory_preflight.py` (Layer 2+) | Hard-won PASS patterns — prefer when applicable |

```text
You are the Generator in a GCL for Alibaba Cloud ClickHouse.

# Known failure patterns (Reflexion memory — do not repeat these mistakes)
{{known_traps}}

# Proven approaches (hard-won success patterns — prefer when applicable)
{{success_patterns}}

# Recent executions for this operation (Layer 1)
{{recent_executions}}

# Weekly strategy hints (Layer 3 — read-only)
{{strategy_hints}}

# Hard rules
- `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` MUST NEVER appear in any trace value.
- ClickHouse `cli_applicability: dual-path` — Enterprise Edition uses
  `aliyun clickhouse` (plugin `aliyun-cli-clickhouse`); Classic Edition uses
  Go SDK `github.com/alibabacloud-go/clickhouse-20191111`. Pick the right path
  based on instance edition (do not mix).
- `DeleteDBInstance` MUST be preceded by a successful `DescribeBackups` AND
  `DescribeBackupPolicy` to confirm a recent backup exists. Record both
  `backup_id` and `backup_status` in trace. No waiver.
- `RestartDBInstance` / `StopDBInstance` MUST obtain explicit user confirmation
  AND verify instance status is `Running` (or `Stopped` for Start).
- `ModifyDBInstanceClass` with scale-down MUST obtain explicit user confirmation
  AND verify current data fits within target spec.
- `ModifySecurityIPList` with `ModifyMode=0` (overwrite) can lock out all clients.
  Default to `ModifyMode=1` (append) unless explicitly resetting.
- `StartDBInstance` / `StopDBInstance` are Enterprise Edition ONLY — for
  Classic Edition, request manual intervention via workorder.
- Serverless `--NodeScaleMax` MUST be explicit (prevent runaway billing);
  default fallback is `NodeCount` × 2.
- All `{{user.*}}` placeholders MUST be resolved interactively.
```

## 2. Critic Prompt Template

```text
You are the Critic in a GCL for Alibaba Cloud ClickHouse. Read-only.

# Checks
- Apply the 6 destructive op classes from `rubric.md` §2.2. ANY match
  classifies the op accordingly.
- Verify path selection: Enterprise Edition operations (`StartDBInstance`,
  `StopDBInstance`, serverless `NodeScaleMin/Max`, `ComputingGroupId`) on a
  Classic Edition instance → ABORT (wrong path).
- Verify Classic Edition operations (`ModifyDBCluster`, `CreateDatabase`)
  on an Enterprise Edition instance → ABORT (wrong path).
- For any `Delete*` op: independently verify `backup_trace` is present
  AND `DescribeBackups` shows a recent Success entry. Missing → Safety = 0.
- For `ModifySecurityIPList`: parse the `--ModifyMode` flag. If `0` (overwrite)
  AND no explicit user justification, Safety = 0 (lockout risk).
- For `ModifyDBInstanceClass` scale-down: verify `data_usage < target_storage`
  from `cms DescribeMetricList`. Violation → Safety = 0.
- For serverless `--NodeScaleMax`: verify explicit value (not default).
  If missing → flag as risk (billing concern).
- For `ResetAccountPassword`: verify `password` is not logged. If visible
  in trace → ABORT (credential leak).
- Verify `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` is masked. If visible
  → ABORT (credential leak).

# Output format
- Apply 5+3 rubric dimensions (Correctness, Safety, Idempotency, Traceability,
  Spec Compliance, plus Token Efficiency, Time Efficiency, Cost Awareness).
- Score 0.0-1.0 per dimension. Overall pass requires all dimensions ≥ 0.7
  AND Safety = 1.0.
- Provide concrete fix recommendations for any dimension < 1.0.
```

## 3. Path Selection Decision Tree (Embedded)

```text
User wants to operate on a ClickHouse instance.
│
├─ Q1: Is the instance Enterprise Edition?
│  ├─ YES → Use Enterprise Edition CLI (aliyun clickhouse ...)
│  │         Plugin required: aliyun-cli-clickhouse
│  │         API version: 2023-05-22
│  │         Supports: Start/Stop/Restart, serverless scaling, Computing Groups, multi-AZ
│  │
│  └─ NO (Classic) → Use Classic Edition SDK
│                    Package: github.com/alibabacloud-go/clickhouse-20191111/v3/client
│                    API version: 2019-11-11
│                    Supports: Vertical scaling only, no serverless, no Computing Groups
│
├─ Q2: Does the operation require a feature only available in one edition?
│  ├─ Enterprise-only feature (Start/Stop, serverless, ComputingGroup)
│  │  → Path = Enterprise CLI (even if instance is Classic, this means
│  │    user must migrate to Enterprise first)
│  │
│  └─ Classic-only feature (e.g., legacy `ModifyDBCluster` API)
│     → Path = Classic SDK
│
└─ Q3: Is this a destructive op? (Delete / Restart / scale-down / Stop / password reset)
   ├─ YES → Require explicit user confirmation + safety gate
   └─ NO  → Standard execution
```

## 4. Memory Preflight Hints

| Layer | Source | ClickHouse-Specific Trap |
|-------|--------|-------------------------|
| Layer 1 | Recent executions | Verify last successful op used the same edition path |
| Layer 2 | Known failure patterns | "ModifySecurityIPList overwrite lockout" (5 occurrences last 30 days) |
| Layer 2 | Known failure patterns | "NodeScaleMax default leads to billing spike" (3 occurrences) |
| Layer 2+ | Hard-won success patterns | "Always `DescribeDBInstanceAttribute` before any Modify" |
| Layer 2+ | Hard-won success patterns | "Use `ModifyMode=1` (append) for security IP" |
| Layer 3 | Strategy hints | "Serverless for variable workloads; Fixed for predictable" |

## 5. Per-Operation Special Rules

| Operation | Class | Special Rule |
|-----------|-------|--------------|
| `CreateDBInstance` | Provisioning | Verify VPC + VSwitch exist before creation; confirm `--NodeCount` (Fixed) or `--NodeScaleMin/Max` (Serverless) |
| `DescribeDBInstances` | Read-only | No safety gate |
| `DescribeDBInstanceAttribute` | Read-only | No safety gate |
| `ModifyDBInstanceClass` | Scale (medium risk) | Verify target data fits; user confirm for scale-down |
| `RestartDBInstance` | Destructive (medium) | User confirm + verify Running state |
| `StartDBInstance` | Lifecycle (low) | Enterprise only; verify Stopped state |
| `StopDBInstance` | Lifecycle (medium) | Enterprise only; user confirm; storage still billed |
| `DeleteDBInstance` | Destructive (high) | User confirm + backup first + multi-AZ check |
| `UpgradeMinorVersion` | Destructive (medium) | User confirm + backup first + maintenance window |
| `CreateAccount` | Provisioning (low) | Verify password complexity |
| `ResetAccountPassword` | Security (medium) | NEVER log password; user confirm |
| `DeleteAccount` | Destructive (medium) | User confirm |
| `ModifySecurityIPList` | Security (high) | Default `ModifyMode=1` (append) |
| `CreateDB` | Provisioning (low) | Verify DB doesn't already exist |
| `DeleteDB` | Destructive (high) | User confirm + backup first |
| `ModifyDBInstanceConfig` | Config (medium) | User confirm; restart may be required |
| `KillProcess` | Destructive (medium) | User confirm + log process ID |
| `ModifyDBInstanceConnectionString` | Network (medium) | User confirm; affects all clients |
| `CreateEndpoint` | Network (low) | Verify connection prefix unique |
| `DeleteEndpoint` | Destructive (medium) | User confirm; verify no active connections |

---

*This template is used by the shared `alicloud-gcl-runner-ops` skill. For rubric, see [rubric.md](rubric.md). For user-facing prompts, see [prompt-examples.md](prompt-examples.md).*

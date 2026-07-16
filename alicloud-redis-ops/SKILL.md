---
name: alicloud-redis-ops
description: >-
  Use when deploying, configuring, troubleshooting, or monitoring Alibaba Cloud
  Redis / Tair (KVStore) instances — create, modify, delete, restart, scale,
  migrate, upgrade, or flush instances; manage accounts, backups, whitelists,
  SSL, parameters, and maintenance windows; monitor CPU, memory, connections,
  QPS, latency, and cache hit rate; analyze slow queries, big keys, and hot
  keys; diagnose connection timeouts, high latency, OOM, CPU spikes, and
  replication lag. Also covers Tair enterprise (persistent memory, disk type).
  Trigger even without explicit "Redis" or "Tair" — Chinese terms: 缓存, 实例,
  备份, 白名单, 参数, 监控, 慢查询, 大Key, 热Key, 连接超时, 延迟高,
  云数据库Redis, 云数据库Tair. NOT for RDS, PolarDB, MongoDB, self-managed
  Redis on ECS, or billing/RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.2.4"
  last_updated: "2026-06-16"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "R-kvstore 2015-01-01 / https://www.alibabacloud.com/help/en/redis"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help r-kvstore` — r-kvstore is fully supported by the official aliyun CLI."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Redis / Tair Operations Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path (control plane) | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/redis-skillopt-wrapper.sh` for all r-kvstore control-plane CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun r-kvstore` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. For runtime enforcement, source the shared shim: `source ../../alicloud-skill-generator/scripts/skillopt-shim/aliyun-shim.sh`. | [SkillOpt](references/skillopt-integration.md), [Shim](file://../../alicloud-skill-generator/scripts/skillopt-shim/SHIM-README.md) |
| Credentials | Read `{env.*}` from environment; wrapper auto-loads repo/skill `.env` — never ask user to paste secrets | [Integration](references/integration.md) |
| GCL | All write operations MUST pass GCL adversarial review before execution | [GCL Rubric](references/rubric.md) |



> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/redis-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun r-kvstore ...` 命令在执行时应替换为 `./scripts/redis-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun r-kvstore` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。
## Overview

Alibaba Cloud Redis / Tair (KVStore) provides managed Redis-compatible and
Tair enterprise-grade key-value database services. This skill is an
**operational runbook** for agents: explicit scope, credential rules, pre-flight
checks, **dual-path execution** (official **SDK/API** and **CLI** flows), response
validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` fully supports `r-kvstore`.
  Each execution flow documents **both** the SDK step and the `aliyun` step for
  every operation.

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Create Instance | Create Redis/Tair instance | Medium | Medium |
| Describe Instances | List all instances in region | Low | None |
| Describe Instance Attribute | Query instance details | Low | None |
| Restart Instance | Restart instance | Low | **High** |
| Delete Instance | Delete instance | Low | **High** |
| Modify Instance Spec | Scale up/down instance | Medium | Medium |
| Describe Accounts | List database accounts | Low | None |
| Create Account | Create database account | Medium | Medium |
| Delete Account | Delete database account | Low | **High** |
| Reset Account Password | Reset account password | Low | Medium |
| Describe Backups | List backups | Low | None |
| Create Backup | Create manual backup | Low | Low |
| Restore Instance | Restore from backup | Medium | **High** |
| Describe Security IPs | Query IP whitelist | Low | None |
| Modify Security IPs | Update IP whitelist | Medium | Medium |
| Describe Parameters | Query instance parameters | Low | None |
| Modify Parameter | Modify instance parameter | Medium | Medium |
| Describe Slow Logs | Query slow query logs | Low | None |
| Describe History Monitor Values | Query monitor metrics | Low | None |
| Modify Instance Maintain Time | Update maintenance window | Low | Low |
| Modify Instance SSL | Enable/disable SSL | Medium | Medium |
| Modify Intranet Bandwidth | Adjust instance bandwidth | Medium | Medium |
| Migrate To Other Zone | Migrate instance to another zone | Medium | **High** |
| Upgrade Minor Version | Upgrade minor version | Medium | Medium |
| Flush Instance | Clear all data in instance | Low | **High** |
| Intelligent Inspection | Run health check | Low | None |
| Execute Redis Command | Run redis-cli via Cloud Assistant | Medium | **High** |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud Redis" OR "Tair" OR "KVStore" OR "云数据库Redis"
  OR "云数据库Tair" OR "缓存"
- User requires automated self-repair and dynamic configuration optimization for Redis/Tair operations via Runtime Harness
- Task involves CRUD or lifecycle operations on **Redis/Tair instances** (create,
  describe, modify, delete, list, restart, upgrade)
- Task involves **instance accounts** (create, describe, delete, reset password)
- Task involves **backups** (create, describe, restore, delete)
- Task involves **whitelists / security groups** (describe, modify)
- Task involves **parameters** (describe, modify)
- Task involves **performance monitoring** (CPU, memory, connections, QPS, latency,
  big key / hot key analysis)
- Task involves **slow query logs** (describe, analyze)
- Task involves **instance migration, scaling, or architecture changes**
- Task keywords: Redis, Tair, KVStore, 缓存, 实例, 备份, 白名单, 参数, 监控,
  慢查询, 大Key, 热Key, instance, backup, whitelist, parameter, monitor, slow log
- User asks to deploy, configure, troubleshoot, or monitor Redis/Tair **via API,
  SDK, CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
  (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **RDS (relational database)** → delegate to: `alicloud-rds-ops`
  (when present)
- Task is about **PolarDB MySQL** → delegate to: `alicloud-polar-mysql-ops`
- Task is about **PolarDB PostgreSQL** → delegate to: `alicloud-polar-postgresql-ops`
- Task is about **PolarDB Oracle-compatible** → delegate to: `alicloud-polar-oracle-ops`
- Task is about **MongoDB** → delegate to: `alicloud-mongodb-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.instance_id}}` | User-supplied Redis/Tair InstanceId | Ask once; reuse |
| `{{user.instance_name}}` | User-supplied instance name | Ask once; reuse |
| `{{user.instance_class}}` | Instance class/specification | Ask once; reuse |
| `{{user.engine_version}}` | Redis engine version (e.g., 5.0, 6.0, 7.0) | Ask once; reuse |
| `{{user.account_name}}` | Database account name | Ask once; reuse |
| `{{user.backup_id}}` | Backup ID | Ask once; reuse |
| `{{output.instance_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.request_id}}` | From API response | For support / correlation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** For write operations (CreateInstance, CreateAccount, etc.),
  generate a unique `Token` (UUID v4) per logical request. Reuse the same `Token`
  for retries within 24 hours to ensure idempotency.

### Response Field Table

> **TE-3/TE-6**: Only most commonly used fields shown. Full field lists → [API & SDK Usage](references/api-sdk-usage.md#response-fields).

| Operation | Key Fields |
|-----------|-------------|
| CreateInstance | `InstanceId`, `InstanceStatus` |
| DescribeInstances | `InstanceId`, `InstanceStatus`, `ConnectionDomain`, `InstanceClass`, `EngineVersion` |
| DescribeInstanceAttribute | `InstanceId`, `InstanceStatus`, `Capacity`, `Bandwidth`, `Connections` |
| RestartInstance | `RequestId` |
| DeleteInstance | `RequestId` |
| DescribeAccounts | `AccountName`, `AccountType`, `AccountStatus` |
| DescribeBackups | `BackupId`, `BackupStatus`, `BackupType`, `BackupStartTime`, `BackupSize` |
| DescribeSecurityIps | `SecurityIpGroupName`, `SecurityIpList` |
| DescribeParameters | `ParameterName`, `ParameterValue` |
| DescribeSlowLogs | `SQLText`, `ExecuteTime`, `ElapsedTime` |
| DescribeHistoryMonitorValues | `HistoryMonitorValues` |
| ModifyInstanceConfig | `RequestId` |
| DeleteAccount / ResetPassword / etc. | `RequestId` |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateInstance | — | `Normal` | 10s | 600s |
| RestartInstance | `Normal` | `Normal` | 10s | 300s |
| DeleteInstance | any stable state | absent | 10s | 300s |
| ModifyInstanceSpec | `Normal` | `Normal` | 10s | 600s |
| ModifyInstanceConfig | `Normal` | `Normal` | 5s | 60s |
| ModifySecurityIps | `Normal` | `Normal` | 5s | 60s |
| CreateAccount | — | `Available` | 5s | 120s |
| DeleteAccount | `Normal` | `Normal` | 5s | 60s |
| ResetAccountPassword | `Normal` | `Normal` | 5s | 60s |
| RestoreInstance | — | `Normal` | 10s | 600s |
| MigrateToOtherZone | `Normal` | `Normal` | 10s | 600s |
| ModifyInstanceMaintainTime | `Normal` | `Normal` | 5s | 60s |
| ModifyInstanceSSL | `Normal` | `Normal` | 10s | 120s |
| ModifyIntranetBandwidth | `Normal` | `Normal` | 5s | 60s |
| UpgradeMinorVersion | `Normal` | `Normal` | 10s | 600s |
| FlushInstance | `Normal` | `Normal` | 10s | 300s |


## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and `aliyun`) → Validate → Recover**.

---

### Operation: Create Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | `aliyun r-kvstore describe-regions` | `{{user.region}}` supported | Suggest valid region |
| Engine / Version | `aliyun r-kvstore describe-available-resource` | `{{user.engine_version}}` supported | Suggest valid combo |
| VPC/VSwitch | `aliyun vpc describe-vpcs` / `describe-v-switches` | VPC and VSwitch exist | Delegate to `alicloud-vpc-ops` |
| Quota | `aliyun r-kvstore describe-available-resource` | Sufficient quota | HALT; user raises quota |

#### Execution — CLI (Primary Path)

```bash
aliyun r-kvstore create-instance \
  --RegionId "{{user.region}}" \
  --InstanceName "{{user.instance_name}}" \
  --InstanceClass "{{user.instance_class}}" \
  --EngineVersion "{{user.engine_version|5.0}}" \
  --ZoneId "{{user.zone_id}}" \
  --NetworkType "{{user.network_type|VPC}}" \
  --VPCId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --ChargeType "{{user.charge_type|PostPaid}}" \
  --Password "{{user.password}}" \
  --Token "{{user.token}}"
```

> **Note:** Output is JSON by default. Parse `InstanceId` from response.

#### Execution — JIT Go SDK (Fallback Path)

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

1. Read `{{output.instance_id}}` from `$.InstanceId`.
2. Poll **DescribeInstances** until `InstanceStatus` is `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

3. On success, report `{{output.instance_id}}`, connection domain, and key fields.
4. On terminal failure, go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI; retry once if safe |
| `QuotaExceeded` / `InstanceQuotaExceeded` | 0 | — | HALT |
| `InsufficientBalance` | 0 | — | HALT |
| `InstanceAlreadyExists` | 0 | — | Ask reuse vs new name |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe Instances

#### Execution — CLI

```bash
# Describe all instances in region
aliyun r-kvstore describe-instances --RegionId "{{user.region}}"

# Describe specific instance
aliyun r-kvstore describe-instances \
  --RegionId "{{user.region}}" \
  --InstanceId "{{user.instance_id}}"

# Extract specific fields with JMESPath
aliyun r-kvstore describe-instances --RegionId "{{user.region}}" \
  --output cols=InstanceId,InstanceStatus,InstanceClass,EngineVersion rows=Instances.KVStoreInstance[].{InstanceId,InstanceStatus,InstanceClass,EngineVersion}
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Instance ID | `$.Instances.KVStoreInstance[].InstanceId` | Plain text |
| Name | `$.Instances.KVStoreInstance[].InstanceName` | Plain text |
| Status | `$.Instances.KVStoreInstance[].InstanceStatus` | Normal, Creating, Changing, etc. |
| Instance Class | `$.Instances.KVStoreInstance[].InstanceClass` | e.g., redis.master.small.default |
| Engine Version | `$.Instances.KVStoreInstance[].EngineVersion` | e.g., 5.0, 6.0, 7.0 |
| Region | `$.Instances.KVStoreInstance[].RegionId` | Plain text |
| Zone | `$.Instances.KVStoreInstance[].ZoneId` | Plain text |
| Network Type | `$.Instances.KVStoreInstance[].NetworkType` | CLASSIC / VPC |
| VPC ID | `$.Instances.KVStoreInstance[].VPCId` | Plain text |
| VSwitch ID | `$.Instances.KVStoreInstance[].VSwitchId` | Plain text |
| Connection Domain | `$.Instances.KVStoreInstance[].ConnectionDomain` | Connection endpoint |
| Port | `$.Instances.KVStoreInstance[].Port` | Service port |
| Capacity | `$.Instances.KVStoreInstance[].Capacity` | MB |
| Bandwidth | `$.Instances.KVStoreInstance[].Bandwidth` | MB/s |
| Connections | `$.Instances.KVStoreInstance[].Connections` | Max connections |
| QPS | `$.Instances.KVStoreInstance[].QPS` | Max QPS |
| Create Time | `$.Instances.KVStoreInstance[].CreateTime` | ISO 8601 |
| Charge Type | `$.Instances.KVStoreInstance[].ChargeType` | PrePaid / PostPaid |
| Architecture Type | `$.Instances.KVStoreInstance[].ArchitectureType` | standard / cluster / rwsplit |

---

### Operation: Describe Instance Attribute

#### Execution — CLI

```bash
aliyun r-kvstore describe-instance-attribute \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Instance ID | `$.Instances.KVStoreInstance[].InstanceId` | Plain text |
| Status | `$.Instances.KVStoreInstance[].InstanceStatus` | Plain text |
| Capacity | `$.Instances.KVStoreInstance[].Capacity` | MB |
| Bandwidth | `$.Instances.KVStoreInstance[].Bandwidth` | MB/s |
| Connections | `$.Instances.KVStoreInstance[].Connections` | Max connections |
| QPS | `$.Instances.KVStoreInstance[].QPS` | Max QPS |
| Config | `$.Instances.KVStoreInstance[].Config` | Parameter config JSON |
| Security IP List | `$.Instances.KVStoreInstance[].SecurityIPList` | Comma-separated |
| Maintain Start Time | `$.Instances.KVStoreInstance[].MaintainStartTime` | Maintenance window start |
| Maintain End Time | `$.Instances.KVStoreInstance[].MaintainEndTime` | Maintenance window end |

---

### Operation: Restart Instance

#### Pre-flight

- Verify instance exists and status is `Normal`.
- **MUST** obtain explicit confirmation: restart causes brief connection interruption.

#### Execution — CLI

```bash
aliyun r-kvstore restart-instance --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Delete Instance

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of instance
  `{{user.instance_id}}` (`{{user.instance_name}}`).
- **MUST NOT** proceed without clear user assent.
- Verify instance is in `Normal` status. If not, warn user.
- **Recommendation:** Create final backup before deletion (optional, user decides).

#### Execution — CLI

```bash
aliyun r-kvstore delete-instance --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll **DescribeInstances** until instance is absent (returns empty list or
`InstanceNotFound`) within **300s**.

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Modify Instance Spec

#### Pre-flight

- Verify instance exists and status is `Normal`.
- Check target spec availability via `DescribeAvailableResource`.
- **MUST** obtain explicit confirmation: scaling causes brief connection interruption.

#### Execution — CLI

```bash
aliyun r-kvstore modify-instance-spec \
  --InstanceId "{{user.instance_id}}" \
  --InstanceClass "{{user.instance_class}}" \
  --OrderType "UPGRADE"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Describe Accounts

#### Execution — CLI

```bash
aliyun r-kvstore describe-accounts \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Account Name | `$.Accounts.Account[].AccountName` | Plain text |
| Account Status | `$.Accounts.Account[].AccountStatus` | Available / Unavailable |
| Account Type | `$.Accounts.Account[].AccountType` | Normal / Super |
| Account Privilege | `$.Accounts.Account[].AccountPrivilege` | Read / Write / Replicate |

---

### Operation: Create Account

#### Pre-flight

- Verify instance exists and status is `Normal`.
- Verify account name does not already exist (call DescribeAccounts first).

#### Execution — CLI

```bash
aliyun r-kvstore create-account \
  --InstanceId "{{user.instance_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.account_password}}" \
  --AccountType "{{user.account_type|Normal}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until account status is `Available`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Delete Account

#### Pre-flight

- Verify account exists via DescribeAccounts.
- **MUST** obtain explicit confirmation: deletion is irreversible.

#### Execution — CLI

```bash
aliyun r-kvstore delete-account \
  --InstanceId "{{user.instance_id}}" \
  --AccountName "{{user.account_name}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll **DescribeAccounts** until account is absent:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Reset Account Password

#### Pre-flight

- Verify account exists via DescribeAccounts.
- **MUST** obtain explicit confirmation: password reset affects all connections using this account.

#### Execution — CLI

```bash
aliyun r-kvstore reset-account-password \
  --InstanceId "{{user.instance_id}}" \
  --AccountName "{{user.account_name}}" \
  --AccountPassword "{{user.new_password}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Verify account status returns to `Available`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Describe Backups

#### Execution — CLI

```bash
# List backups for an instance
aliyun r-kvstore describe-backups \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"

# Extract backup IDs and status
aliyun r-kvstore describe-backups \
  --InstanceId "{{user.instance_id}}" \
  --output cols=BackupId,BackupStatus,BackupType,BackupStartTime rows=Backups.Backup[].{BackupId,BackupStatus,BackupType,BackupStartTime}
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Backup ID | `$.Backups.Backup[].BackupId` | Plain text |
| Backup Status | `$.Backups.Backup[].BackupStatus` | Success / Failed |
| Backup Type | `$.Backups.Backup[].BackupType` | Automated / Manual |
| Backup Start Time | `$.Backups.Backup[].BackupStartTime` | ISO 8601 |
| Backup End Time | `$.Backups.Backup[].BackupEndTime` | ISO 8601 |
| Backup Size | `$.Backups.Backup[].BackupSize` | Bytes |
| Backup Mode | `$.Backups.Backup[].BackupMode` | Full / Incremental |

---

### Operation: Create Backup

#### Pre-flight

- Verify instance exists and status is `Normal`.
- Check if backup window conflicts with maintenance window.

#### Execution — CLI

```bash
aliyun r-kvstore create-backup \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll **DescribeBackups** until backup status is `Success`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Restore Instance

#### Pre-flight

- Verify backup exists via DescribeBackups.
- **MUST** obtain explicit confirmation: restore overwrites current data.

#### Execution — CLI

```bash
aliyun r-kvstore restore-instance \
  --InstanceId "{{user.instance_id}}" \
  --BackupId "{{user.backup_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Describe Security IPs (Whitelist)

#### Execution — CLI

```bash
aliyun r-kvstore describe-security-ips \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Security IP Group Name | `$.SecurityIpGroups.SecurityIpGroup[].SecurityIpGroupName` | Group name |
| Security IP List | `$.SecurityIpGroups.SecurityIpGroup[].SecurityIpList` | Comma-separated IPs |

---

### Operation: Modify Security IPs

#### Pre-flight

- Verify instance exists and status is `Normal`.
- **MUST** obtain explicit confirmation: modifying whitelist affects access control.

#### Execution — CLI

```bash
aliyun r-kvstore modify-security-ips \
  --InstanceId "{{user.instance_id}}" \
  --SecurityIps "{{user.security_ips}}" \
  --SecurityIpGroupName "{{user.security_ip_group_name|default}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Verify whitelist updated via DescribeSecurityIps:

```bash
aliyun r-kvstore describe-security-ips \
  --InstanceId "{{user.instance_id}}" \
  --output cols=SecurityIpList rows=SecurityIpGroups.SecurityIpGroup[?SecurityIpGroupName=='{{user.security_ip_group_name|default}}'].SecurityIpList
```

---

### Operation: Describe Parameters

#### Execution — CLI

```bash
aliyun r-kvstore describe-parameters \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Parameter Name | `$.RunningParameters.Parameter[].ParameterName` | Parameter name |
| Parameter Value | `$.RunningParameters.Parameter[].ParameterValue` | Current value |
| Parameter Description | `$.RunningParameters.Parameter[].ParameterDescription` | Description |
| Modifiable Status | `$.RunningParameters.Parameter[].ModifiableStatus` | true / false |

---

### Operation: Modify Parameter

#### Pre-flight

- Verify instance exists and status is `Normal`.
- Check parameter is modifiable via DescribeParameters.
- **MUST** obtain explicit confirmation: parameter change may require restart.

#### Execution — CLI

```bash
aliyun r-kvstore modify-parameter \
  --InstanceId "{{user.instance_id}}" \
  --ParameterName "{{user.parameter_name}}" \
  --ParameterValue "{{user.parameter_value}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Verify parameter updated via DescribeParameters:

```bash
aliyun r-kvstore describe-parameters \
  --InstanceId "{{user.instance_id}}" \
  --output cols=ParameterName,ParameterValue rows=RunningParameters.Parameter[?ParameterName=='{{user.parameter_name}}'].{ParameterName,ParameterValue}
```

---

### Operation: Describe Slow Logs

#### Execution — CLI

```bash
aliyun r-kvstore describe-slow-logs \
  --InstanceId "{{user.instance_id}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| SQL Text | `$.Items.SlowLog[].SQLText` | Slow query command |
| Execute Time | `$.Items.SlowLog[].ExecuteTime` | ISO 8601 timestamp |
| Elapsed Time | `$.Items.SlowLog[].ElapsedTime` | Microseconds |
| DB Name | `$.Items.SlowLog[].DBName` | Database name |
| Account Name | `$.Items.SlowLog[].AccountName` | Account name |

---

### Operation: Describe History Monitor Values

#### Execution — CLI

```bash
aliyun r-kvstore describe-history-monitor-values \
  --InstanceId "{{user.instance_id}}" \
  --MonitorKeys "{{user.monitor_keys}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Monitor Values | `$.HistoryMonitorValues` | Historical metric values JSON |

---

### Operation: Modify Instance Maintain Time

#### Pre-flight

- Verify instance exists and status is `Normal`.
- **MUST** obtain explicit confirmation: maintenance window change may affect scheduled maintenance.

#### Execution — CLI

```bash
aliyun r-kvstore modify-instance-maintain-time \
  --InstanceId "{{user.instance_id}}" \
  --MaintainStartTime "{{user.maintain_start_time}}" \
  --MaintainEndTime "{{user.maintain_end_time}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Verify maintenance time updated:

```bash
aliyun r-kvstore describe-instances \
  --RegionId "{{user.region}}" \
  --InstanceId "{{user.instance_id}}" \
  --output cols=MaintainStartTime,MaintainEndTime rows=Instances.KVStoreInstance[0].{MaintainStartTime,MaintainEndTime}
```

---

### Operation: Modify Instance SSL

#### Pre-flight

- Verify instance exists and status is `Normal`.
- **MUST** obtain explicit confirmation: enabling/disabling SSL causes brief connection interruption.

#### Execution — CLI

```bash
aliyun r-kvstore modify-instance-ssl \
  --InstanceId "{{user.instance_id}}" \
  --SSLEnabled "{{user.ssl_enabled|Enable}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Modify Intranet Bandwidth

#### Pre-flight

- Verify instance exists and status is `Normal`.
- Check bandwidth limits via `DescribeIntranetAttribute`.

#### Execution — CLI

```bash
aliyun r-kvstore modify-intranet-bandwidth \
  --InstanceId "{{user.instance_id}}" \
  --Bandwidth "{{user.bandwidth}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Verify bandwidth updated via DescribeIntranetAttribute:

```bash
aliyun r-kvstore describe-intranet-attribute \
  --InstanceId "{{user.instance_id}}" \
  --output cols=Bandwidth rows=Bandwidth
```

---

### Operation: Migrate To Other Zone

#### Pre-flight

- Verify instance exists and status is `Normal`.
- Verify target zone supports the instance class via `DescribeAvailableResource`.
- **MUST** obtain explicit confirmation: migration causes brief connection interruption.

#### Execution — CLI

```bash
aliyun r-kvstore migrate-to-other-zone \
  --InstanceId "{{user.instance_id}}" \
  --ZoneId "{{user.zone_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Upgrade Minor Version

#### Pre-flight

- Verify instance exists and status is `Normal`.
- Check available minor version via `DescribeEngineVersion`.
- **MUST** obtain explicit confirmation: upgrade causes brief connection interruption.

#### Execution — CLI

```bash
aliyun r-kvstore upgrade-minor-version \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

### Operation: Flush Instance

#### Pre-flight

- Verify instance exists and status is `Normal`.
- **MUST** obtain explicit confirmation: flush deletes ALL data. This is irreversible.
- **Recommendation:** Create backup before flush.

#### Execution — CLI

```bash
aliyun r-kvstore flush-instance \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

完整 Go SDK 示例见 [references/api-sdk-usage.md#go-sdk-examples](references/api-sdk-usage.md#go-sdk-examples)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)
```

---

---

### Operation: Intelligent Inspection（智能巡检）

一键执行 Redis 实例的全面健康检查。整合 Redis 状态 + CMS 指标 + 慢查询 + 白名单 + 备份状态分析。Full CLI script at [references/intelligent-inspection.md](references/intelligent-inspection.md).

**5-step workflow:** DescribeInstances (status) → CMS CPU/memory/connections/latency → DescribeSlowLogs → DescribeSecurityIps → DescribeBackups → Scoring report.

**Scoring criteria:**

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| 实例状态 | Normal=100, 其他=0 | 20% |
| CPU使用率 | <70%=100, 70-85%=60, >85%=0 | 20% |
| 内存使用率 | <75%=100, 75-90%=60, >90%=0 | 20% |
| 连接使用率 | <70%=100, 70-85%=60, >85%=0 | 15% |
| 延迟 | AvgRt<5ms=100, 5-20ms=60, >20ms=0 | 15% |
| 备份状态 | 最近成功=100, 失败=0 | 10% |

**Output format** — Same JSON schema as all other inspection skills (score, dimensions, recommendations).

### Supported Anomaly Patterns
  1. 内存-连接数双高: Memory>85% + Connections>阈值
  2. 响应延迟-吞吐瓶颈: Latency突增 + Throughput下降
  3. 缓存命中率突降: HitRate从95%降至80%
  4. 键空间-内存碎片: Keyspace大 + Memory碎片率高
```

### DAS 联动引用

See: [DAS Cache Analysis Integration](../alicloud-das-ops/references/integration.md)

### 批量操作引用

See: [Batch Operations](../alicloud-skill-generator/templates/batch-operations.md)

### API计数引用

See: [API Usage Metrics](../alicloud-skill-generator/references/api-call-counter.md)

---

### Operation: Execute Redis Command via Cloud Assistant

通过阿里云 ECS 云助手（Cloud Assistant）在指定 ECS 实例上执行任意 Redis CLI 命令。
适用于需要直接操作 Redis 数据面（如 `DEL`、`GET`、`SET`、`TTL`、`EXISTS`、`KEYS` 等）而管控面 API 无法覆盖的场景。

> **适用场景：** 删除特定缓存 Key、查询 Key 是否存在、修改 Key 的 TTL、批量操作数据等。
> ⚠️ **注意：** 此操作要求目标 ECS 实例与 Redis 实例在同一 VPC 内，或网络可达。

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| ECS 实例存在 | `aliyun ecs DescribeInstances --InstanceIds '["{{user.ecs_instance_id}}"]'` | 实例已找到 | HALT — 确认 ECS InstanceId |
| ECS 状态 | `InstanceStatus` | `Running` | HALT — 先启动实例 |
| Cloud Assistant 已安装 | `aliyun ecs DescribeCloudAssistantStatus --RegionId {{user.region}} --InstanceIds '["{{user.ecs_instance_id}}"]'` | `CloudAssistantStatus` == `true` | HALT — 引导安装云助手 Agent |
| Redis 实例存在 | `aliyun r-kvstore describe-instances --InstanceId "{{user.redis_instance_id}}"` | 实例已找到 | HALT — 确认 Redis InstanceId |
| Redis 状态 | `InstanceStatus` | `Normal` | HALT — 实例不可用 |
| Redis 命令确认 | 用户确认 | 明确同意执行 `{{user.redis_command}}` | HALT — 必须获得确认 |

#### 变量约定

| 变量 | 含义 | 来源 |
|------|------|------|
| `{{user.region}}` | 地域 | 用户提供或从环境推断 |
| `{{user.ecs_instance_id}}` | 目标 ECS 实例 ID | 用户提供或通过 `DescribeInstances` 查询 |
| `{{user.redis_instance_id}}` | Redis 实例 ID | 用户提供或通过 `DescribeInstances` 确定 |
| `{{user.redis_host}}` | Redis 连接地址 | 从 `DescribeInstanceAttribute` 的 `ConnectionDomain` 自动获取 |
| `{{user.redis_port}}` | Redis 端口 | 默认 `6379` |
| `{{user.redis_password}}` | Redis 密码（可选） | 用户提供；无密码时留空 |
| `{{user.redis_command}}` | 待执行的 Redis 命令 | 用户提供，如 `DEL 8560pfuat:gpas_lsym_funding_token` |
| `{{user.redis_cli_version}}` | 期望的 redis-cli 最低版本（可选） | 用户提供；不指定则仅检查存在性 |
| `{{env.REDIS_CLI_BIN_URL}}` | 离线模式自定义二进制 URL（专有云/无外网场景） | 从 `.env` 读取；未设置则走包管理器+源码兜底 |

> **何时需要配置 `REDIS_CLI_BIN_URL`？** 仅在 ECS 跳板机**无公网出口**时（如金融云、政务云、专有云、网闸隔离环境）。阿里云 ECS + 公网通的场景**不需要配**——脚本会自动用阿里云内网镜像源加速。完整决策树、配置步骤、二进制准备、验证方法、FAQ 见 [`references/redis-cli-install.md` 「用户配置指南」](references/redis-cli-install.md#用户配置指南必读)。

#### Execution

完整执行流程（5 个 Step + 合并执行 + Post-execution Validation + 退出码全表 + 日志解读 + Failure Recovery）参见：

> **[references/redis-cli-execution.md](references/redis-cli-execution.md)**

执行概览：

| Step | 操作 | 说明 |
|------|------|------|
| 1 | `aliyun r-kvstore describe-instance-attribute` | 获取 Redis 连接地址 |
| 2 | `aliyun ecs RunCommand — ensure_redis_cli` | **幂等** ensure redis-cli（已装+版本符合则跳过；按 OS 自适应安装；阿里云镜像加速；离线模式兜底）。安装策略权威源见 [`references/redis-cli-install.md`](references/redis-cli-install.md) |
| 3 | `aliyun ecs RunCommand — REDISCLI_AUTH` | 密码即时 export（不持久化写 bashrc） |
| 4 | `aliyun ecs RunCommand — redis-cli DEL/GET/SET/--bigkeys/--hotkeys` | 执行 Redis 命令（含网络可达性检测 + 错误分类诊断） |

退出码快速参考：

| ExitCode | 阶段 | 含义 | 人工动作 |
|:--------:|------|------|---------|
| 0  | 整体     | ✅ 成功 | 检查 `[SUMMARY] Result:` |
| 20 | install  | 安装失败（pkg + 源码兜底都失败） | 查看 `[DIAG] disk/mem/dns_test` |
| 21 | install  | 源码编译依赖缺失 | 设 `REDIS_CLI_BIN_URL` 走离线模式 |
| 22 | install  | 离线包下载失败 | 检查 `REDIS_CLI_BIN_URL` URL/网络 |
| 30 | network  | ECS → Redis 不可达 | 检查 VPC/安全组/白名单 |
| 40 | exec     | Redis 命令失败 | 查看 `[ERROR] TYPE=... FIX=...` |

所有诊断日志使用结构化前缀 `[HH:MM:SS] [PHASE] key=value`，支持 Agent 自动解析和人工快速定位。

## Enhanced Pre-flight Check (MANDATORY)

> **CRITICAL:** Before executing ANY Redis/Tair operation, MUST run the enhanced pre-flight check script to validate environment and detect potential issues early.

### Why Enhanced Pre-flight Check?

Based on real-world execution failures, this enhanced check addresses:
1. **CLI plugin installation issues** (permission restrictions in CI environments)
2. **Environment variable loading** (automatic .env file detection)
3. **Go SDK version compatibility** (preventing runtime errors)
4. **Network connectivity** (endpoint accessibility)
5. **CI environment detection** (special handling for restricted environments)

### Execution

```bash
# Run enhanced pre-flight check
bash scripts/preflight-check.sh

# Exit codes:
# 0 = PASS (all checks passed, ready to execute)
# 1 = FAIL (critical issues, cannot proceed)
# 2 = WARNING (warnings present, proceed with caution)
```

### Check Categories

| Category | Checks | Severity |
|----------|--------|----------|
| Environment Detection | CI/local, OS/arch | INFO |
| CLI Installation | aliyun binary, version | CRITICAL |
| **CLI Plugin Installation** | r-kvstore plugin, permissions, auto-install | **CRITICAL** |
| Credentials | .env file, env vars, CLI config | CRITICAL |
| Go Runtime | Go binary, version compatibility | WARNING |
| Network Connectivity | Endpoint accessibility | WARNING |

### Automatic Issue Detection and Resolution

The script automatically:
1. **Detects .env file** and loads environment variables
2. **Checks plugin installation** and attempts auto-install if missing
3. **Handles permission restrictions** gracefully (CI environments)
4. **Validates Go version** for SDK fallback compatibility
5. **Provides actionable suggestions** for each issue

### Output Example

```
=== Enhanced Pre-flight Check for Redis/Tair Operations ===

[1] Environment Detection
[i] Running in CI environment
[i] Operating System: Darwin (arm64)

[2] Alibaba Cloud CLI Installation
[✓] Alibaba Cloud CLI installed: 3.0.167

[3] CLI Plugin Installation Check
[✗] Redis/Tair plugin (aliyun-cli-r-kvstore) not installed
[i] Attempting to install Redis/Tair plugin...
[!] Plugin directory lacks write permission (common in CI/restricted environments)
[!] Suggestion: Use Go SDK fallback path or fix permissions

[4] Credentials Check
[i] Found .env file: .env
[✓] .env file loaded successfully
[✓] ALIBABA_CLOUD_ACCESS_KEY_ID is set (length: 20)
[✓] ALIBABA_CLOUD_ACCESS_KEY_SECRET is set (masked for security)
[✓] ALIBABA_CLOUD_REGION_ID is set: cn-hangzhou

[5] Go Runtime Check (Fallback Path)
[✓] Go runtime installed: go1.24.0
[✓] Go version meets minimum requirement (1.21+)

[6] Network Connectivity Check
[✓] Can reach Alibaba Cloud endpoint: r-kvstore.aliyuncs.com

Overall Status: WARNING
Recommended Execution Path: SDK Fallback (due to plugin permission issue)
```

### Integration with Execution Flows

**Every operation MUST start with:**
```bash
# Step 1: Run pre-flight check
bash scripts/preflight-check.sh
PREFLIGHT_STATUS=$?

# Step 2: Determine execution path based on status
if [ $PREFLIGHT_STATUS -eq 0 ]; then
    # Use CLI (Primary Path)
    aliyun r-kvstore describe-instances --RegionId "$ALIBABA_CLOUD_REGION_ID"
elif [ $PREFLIGHT_STATUS -eq 2 ]; then
    # Use SDK Fallback (warnings present)
    go run scripts/sdk-fallback.go
else
    # HALT - critical issues
    echo "Cannot proceed. Fix critical issues first."
    exit 1
fi
```

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path):

   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback):

   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOCACHE="/tmp/go-cache"
       export GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"
   fi
   go version
   ```

3. **Configure Credentials** (automatic .env loading supported):

   **Option A: Environment Variables**
   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value (i.e., display as `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`). Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

   **Option B: .env File (Recommended for CI)**
   ```bash
   # Create .env file in project root
   cat > .env <<EOF
   ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
   ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
   ALIBABA_CLOUD_REGION_ID=cn-hangzhou
   EOF
   
   # Pre-flight check will auto-load .env file
   bash scripts/preflight-check.sh
   ```

4. **Verify Configuration** (via pre-flight check):

   ```bash
   # Use enhanced pre-flight check instead of manual verification
   bash scripts/preflight-check.sh
   ```

> **Note:** The `--waiter` flag is supported by the `aliyun` CLI. See [CLI Usage](references/cli-usage.md) for details.

---

## Well-Architected Assessment

| Pillar | Key Guidance |
|--------|-------------|
| **Security** | IAM: `r-kvstore:Describe*` for read, `r-kvstore:CreateInstance`, `Modify*` for mutating. VPC-only deployment. Set SecurityIPList to app server IPs only. Enable SSL/TLS. Create separate accounts per app with minimal ACL |
| **Stability** | Cluster/standard with read-only replicas + auto-failover (< 30s). **Scenario:** Monitor ConnectionUsage/MemoryUsage/QPSUse/KeyCount → alert at 80% → daily backup + AOF persistence → test restore quarterly |
| **Cost** | Prepaid up to 70% off. Read-only replicas for read-heavy workloads. Waste: Memory < 30% for 7d → downgrade. Connections < 10 consistently → downgrade |
| **Efficiency** | Enable auto-renewal. Use `ModifyInstanceConfig` for hot-reload. JSON output for pipeline |
| **Performance** | CPU > 80% → scale up. Memory > 85% → scale up. Connection > 80% → scale up. QPS > 80% → scale up. Use Tair data types (TairString, TairHash). Shard at > 100k QPS/node |

---

## Reference Directory

- [Core Concepts](references/core-concepts.md) — Redis/Tair architecture, instance types, Tair data types, networking model
- [API & SDK Usage](references/api-sdk-usage.md) — Complete API operation mapping with request/response fields and Go SDK patterns
- [CLI Usage](references/cli-usage.md) — `aliyun r-kvstore` command reference, output formatting, and `--waiter` usage
- [Polling Patterns](references/polling-patterns.md) — Generic polling template and per-operation polling parameters
- [Redis CLI Execution via Cloud Assistant](references/redis-cli-execution.md) — 数据面命令执行的端到端编排（合并脚本、退出码、Failure Recovery）
- [redis-cli Install — Design Spec + User Guide](references/redis-cli-install.md) — 设计规范、OS 支持矩阵、用户配置指南（决策树、镜像加速、离线模式、FAQ）
- [`scripts/redis-cli-install.sh`](scripts/redis-cli-install.sh) — **可执行权威实现**（344 行 bash）：`bash redis-cli-install.sh` 直接跑，或 `source` 后调用 `ensure_redis_cli`，或在云助手脚本里 `cat` 拼装
- [Troubleshooting Guide](references/troubleshooting.md) — Symptom-based decision tree, diagnostic commands, error code reference, and support escalation
- [Monitoring & Alerts](references/monitoring.md) — Key metrics, KPI thresholds, automated monitoring flows, and CloudMonitor integration
- [Prompts Guide](references/prompt-examples.md) — Ready-to-use prompt templates for 40+ operational scenarios (lifecycle, security, diagnostics, batch ops, advanced analytics)
- [Integration](references/integration.md) — VPC, RAM, CI/CD, Terraform/Pulumi/Ansible integration patterns
- [GCL Rubric](references/rubric.md) — **Phase 1 rollout** GCL rubric (5 core + 3 Aliyun dimensions, per-op Safety sub-rules, 5-class data-plane command classification, 4 worked examples)
- [GCL Prompt Templates](references/prompt-templates.md) — **Phase 1 rollout** Generator & Critic prompt templates (dual-path CLI/SDK aware)
- [Runtime Harness Integration](references/skillopt-integration.md) — Runtime Harness wrapper for self-repair, dynamic optimization, and Langfuse tracing

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required APIs only.
- **Availability:** Use multi-AZ deployment for production instances.
- **Cost:** Right-size instances; use auto-renewal for PrePaid instances.
- **Security:** Regularly rotate passwords; restrict whitelist to minimum required IPs.
- **Backup:** Enable automated backups; test restore procedures periodically.

---

## Quality Gate (GCL)

This skill is the **second rollout** of the Generator-Critic-Loop (GCL)
adversarial quality gate defined in [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).
Every runtime execution of an `alicloud-redis-ops` operation MUST be wrapped
in a GCL loop before the result is returned to the user.

> **Two references in this directory carry the GCL contract:**
>
> | File | Purpose |
> |---|---|
> | [`references/rubric.md`](references/rubric.md) | The 5 core + 3 Aliyun-specific rubric dimensions, per-op Safety sub-rules, the 5-class / 8-regex data-plane command classification, and 4 worked examples |
> | [`references/prompt-templates.md`](references/prompt-templates.md) | The Generator and Critic prompt templates (with `{{env.*}}` / `{{user.*}}` / `{{output.*}}` placeholders) |
>
> The full rationale, termination rules, anti-patterns, and rollout roadmap
> live in `AGENTS.md` §12. This section is only a pointer + per-skill override.

### GCL Scope for Redis / Tair

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1 rollout, second skill) |
| Default `max_iter` | **2** (inherited from `AGENTS.md` §12.8) |
| Operations covered | ALL operations in this SKILL.md (CRUD + lifecycle + accounts + backups + whitelists + parameters + Cloud Assistant data-plane) |
| Operations most scrutinized | `DeleteInstance`, `FlushInstance`, `RestoreInstance`, `DeleteAccount`, `ResetAccountPassword`, `ModifySecurityIps` (especially `0.0.0.0/0`), `ModifyParameter` (high-risk params), `Execute Redis Command via Cloud Assistant` (data-plane classification) |

### Per-Op Safety Sub-Rules (Quick Reference)

For the **full** sub-rule table (with the exact `Score 1` conditions), see
[`references/rubric.md` §1.2](../alicloud-redis-ops/references/rubric.md).
Highlights:

| Operation | Hard Safety condition (Score 1 requires) |
|---|---|
| `DeleteInstance` | Explicit user confirmation of `{{user.instance_id}}` AND `{{user.instance_name}}`; `InstanceStatus == Normal`; backup created in the same flow OR user explicitly waived |
| `FlushInstance` | Explicit user confirmation that **ALL data** will be wiped; backup created OR user explicitly waived; `InstanceStatus == Normal` |
| `RestoreInstance` | Explicit user confirmation that current data will be overwritten; `BackupId` verified via `DescribeBackups` with `BackupStatus == Success`; target instance is the original owner (cross-instance restore needs an extra confirmation entry) |
| `ResetAccountPassword` | Explicit user confirmation that all current connections will be invalidated; **`AccountPassword` NOT present in any trace field**; password complexity 8-30 chars, mixed case + digits |
| `CreateAccount` | `AccountName` is not `root` / `admin` / `redis`; password delivered via env var, not as a CLI flag |
| `ModifySecurityIps` | **No `0.0.0.0/0` entry** in `{{user.security_ips}}` unless user explicitly justified (Redis whitelists are network-level ACLs — more dangerous than SG rules) |
| `ModifyParameter` | Parameter is not in the high-risk list (`maxmemory-policy`, `appendonly`, `save`, `protected-mode`, `bind`, `requirepass`) unless user explicitly justified |
| `Execute Redis Command via Cloud Assistant` | See `rubric.md` §1.2.1 — 5 risk classes (READ-ONLY / WRITE-KEY / DESTRUCTIVE-MASS / CONFIG-MUTATION / FATAL); 8 regex hot-spots (FLUSHALL, FLUSHDB, SHUTDOWN, DEBUG, CONFIG SET, `DEL cache:*`, `KEYS *`, `EVAL ... DEL ... KEYS ...`) |

### Redis-Specific Additions (beyond the 5 core dimensions)

| Dimension | Threshold | Why it matters for Redis |
|---|---|---|
| **Region Compliance** | ≥ 0.5 | `--RegionId` must match `{{user.region}}` to avoid cross-region cost leakage and accidental cross-region side-effects |
| **Credential Hygiene** | = 1 (**absolute**) | `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `REDISCLI_AUTH`, **and any `AccountPassword` value** must never appear in any trace field — promoted to absolute gate due to the high density of password-bearing operations in this skill |
| **Well-Architected** | ≥ 0.5 | The 5 WA pillars from `references/well-architected-assessment.md` are scored when the op is WA-sensitive (cost / security / stability) |
| **Data-plane classification** (cross-validation only, no separate score) | n/a | For the "Execute Redis Command via Cloud Assistant" operation, the Generator MUST populate `command_classification` and the Critic MUST independently re-classify — disagreement is a finding (Traceability 0) |

### Dual-Path Trace Convention (CLI vs. SDK)

Unlike `alicloud-ecs-ops` (cli-first), this skill is `dual-path` (CLI
primary, Go SDK fallback). The trace MUST record which path was used:

```json
{
  "generator": {
    "path": "cli",  // or "sdk"
    "command": "aliyun r-kvstore flush-instance --InstanceId r-bp1...",  // null if path=sdk
    "sdk_request": null,  // or Go struct literal if path=sdk
    ...
  }
}
```

Path selection rules (inherited from `prompt-templates.md` §1):

1. Default to `cli` — `aliyun r-kvstore <action> --InstanceId ...`.
2. Use `sdk` only when: (a) CLI lacks the operation, (b) user explicitly requested SDK, or (c) CLI returned 5xx after 2 retries.

### Termination (inherited from `AGENTS.md` §12.5)

| Condition | Behavior |
|---|---|
| All dimensions ≥ threshold | **PASS** — return Generator's result |
| Safety = 0 **or** Credential Hygiene = 0 | **ABORT** — never return partial output |
| Other dimension < threshold AND iter < 2 | **RETRY** — inject Critic suggestions into next Generator prompt |
| Other dimension < threshold AND iter = 2 | **MAX_ITER** — return best-so-far + unresolved rubric items |

### Trace Persistence (mandatory)

Every GCL run MUST write `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`
with the schema defined in `AGENTS.md` §12.6. Apply the Redis-specific
sanitization regex helpers in `rubric.md` §2.2 to scrub
`ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `REDISCLI_AUTH`, and `AccountPassword`
before persisting.

> `./audit-results/` is already in the repository `.gitignore` (added in the
> ECS pilot rollout, `AGENTS.md` §12.11 Phase 1).

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.2.4 | 2026-06-16 | Added Microsoft SkillOpt integration for self-repair and dynamic configuration optimization capabilities for Redis/Tair operations |
| 1.2.3 | 2026-06-12 | **复盘后 P0/P1 bug 修复**：(1) `use_aliyun_yum_mirror` sed 分隔符冲突修复（实测验证）；(2) 移除 `.sh` 末尾不可靠守卫，改 `REDIS_CLI_INSTALL_AUTORUN=1` 显式开关；(3) `execution.md` Step 2 残留过时文档清理；(4) 合并脚本改用 `printf %q` + `<<'BIZ'` 杜绝 shell 注入；(5) 锚点修复（章节标题去括号化）。所有改动通过 syntax check + functional sed test + source/autorun/silent 三模式验证。 |
| 1.2.2 | 2026-06-12 | **安装脚本抽取为独立可执行文件 `scripts/redis-cli-install.sh`**（344 行 bash，通过 `bash -n` 语法检查；可被 `cat`/`source`/`bash` 三种方式调用）。`redis-cli-execution.md` 合并脚本改为 `cat scripts/redis-cli-install.sh` 即时拼装，**用户无需手动复制粘贴函数**。`redis-cli-install.md` 删除原 311 行内嵌脚本，保留为「设计规范 + 用户配置指南」（净减 264 行）。 |
| 1.2.1 | 2026-06-12 | `redis-cli-install.md` 新增「用户配置指南」（30 秒决策树、场景化配置步骤、二进制自编译方法、副作用与还原、6 条 FAQ）；`.env.example` 增加 `REDIS_CLI_BIN_URL` 注释模板；SKILL.md 变量约定区增加"何时需配置"提示。 |
| 1.2.0 | 2026-06-12 | redis-cli 安装层重构：抽出 `references/redis-cli-install.md` 为唯一权威源；新增 SUSE/zypper 支持；新增阿里云 ECS 镜像源加速（`mirrors.cloud.aliyuncs.com` / `mirrors.aliyun.com`）；新增离线模式 `REDIS_CLI_BIN_URL`；源码兜底自动安装 `gcc make`；统一退出码契约（20/21/22）；删除 exit 10/11（被 `ensure_redis_cli` 的幂等检查替代）。 |
| 1.1.0 | 2026-06-04 | 新增 `## Quality Gate (GCL)` 章节 + `references/rubric.md` + `references/prompt-templates.md`。Default `max_iter=2`。Redis 特定：双通道追踪约定、数据面命令分类（5 风险等级）、Credential Hygiene 提升为绝对门禁。 |
| 1.0.0 | 2026-05-14 | Initial Redis/Tair skill with dual-path (CLI + SDK) support |


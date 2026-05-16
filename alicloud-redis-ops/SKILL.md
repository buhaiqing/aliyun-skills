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
  version: "1.0.0"
  last_updated: "2026-05-14"
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

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud Redis" OR "Tair" OR "KVStore" OR "云数据库Redis"
  OR "云数据库Tair" OR "缓存"
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
- Task is about **PolarDB PostgreSQL** → delegate to: `alicloud-polar-pg-ops`
- Task is about **PolarDB Oracle-compatible** → delegate to: `alicloud-polar-oracle-ops`
- Task is about **MongoDB** → delegate to: `alicloud-mongodb-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

### Delegation Rules

- If creating a Redis/Tair instance in a VPC, verify VPC and VSwitch exist (via
  `alicloud-vpc-ops`) before instance creation.
- If restoring from backup, verify the backup exists via DescribeBackups before
  initiating RestoreInstance.
- Multi-product requests: handle each product with its skill; do not merge
  unrelated APIs into one ambiguous flow.

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

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value in console output, debug messages, error messages, or logs.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` | Raw credential value in output |
> | Error messages | `Error: API call failed (credential omitted)` | Error containing raw credential value |
> | Log files | `[INFO] Credentials: Secret=***` | `[INFO] AK Secret: LTAI5t...` |
> | Verification | `test -n "$var" && echo "Secret is set"` (existence check only) | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
> | JIT Go SDK | env read via `os.Getenv(...)` is safe; never print `Config` struct | `fmt.Printf("Config: %+v", config)` |
> | Debug/verbose | `Debug mode may expose credentials (use with caution)` | Un-masked credential in debug output |
>
> **Credential verification MUST check existence only**, never echo the value. This applies to ALL execution flows (SDK, CLI, and debugging scripts).

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** For write operations (CreateInstance, CreateAccount, etc.),
  generate a unique `Token` (UUID v4) per logical request. Reuse the same `Token`
  for retries within 24 hours to ensure idempotency.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateInstance | `$.InstanceId` | string | New instance ID |
| CreateInstance | `$.InstanceStatus` | string | Initial status (Creating) |
| DescribeInstances | `$.Instances.KVStoreInstance[].InstanceId` | array | Instance IDs |
| DescribeInstances | `$.Instances.KVStoreInstance[].InstanceStatus` | string | Instance status |
| DescribeInstances | `$.Instances.KVStoreInstance[].InstanceClass` | string | Instance class |
| DescribeInstances | `$.Instances.KVStoreInstance[].EngineVersion` | string | Engine version |
| DescribeInstances | `$.Instances.KVStoreInstance[].RegionId` | string | Region ID |
| DescribeInstances | `$.Instances.KVStoreInstance[].ZoneId` | string | Zone ID |
| DescribeInstances | `$.Instances.KVStoreInstance[].NetworkType` | string | CLASSIC / VPC |
| DescribeInstances | `$.Instances.KVStoreInstance[].VPCId` | string | VPC ID |
| DescribeInstances | `$.Instances.KVStoreInstance[].VSwitchId` | string | VSwitch ID |
| DescribeInstances | `$.Instances.KVStoreInstance[].CreateTime` | string | ISO 8601 timestamp |
| DescribeInstances | `$.Instances.KVStoreInstance[].ChargeType` | string | PrePaid / PostPaid |
| DescribeInstances | `$.Instances.KVStoreInstance[].ConnectionDomain` | string | Connection domain |
| DescribeInstanceAttribute | `$.Instances.KVStoreInstance[].InstanceId` | string | Instance ID |
| DescribeInstanceAttribute | `$.Instances.KVStoreInstance[].InstanceStatus` | string | Status |
| DescribeInstanceAttribute | `$.Instances.KVStoreInstance[].Capacity` | long | Capacity (MB) |
| DescribeInstanceAttribute | `$.Instances.KVStoreInstance[].Bandwidth` | long | Bandwidth (MB/s) |
| DescribeInstanceAttribute | `$.Instances.KVStoreInstance[].Connections` | long | Max connections |
| DescribeInstanceAttribute | `$.Instances.KVStoreInstance[].QPS` | long | Max QPS |
| DescribeInstanceAttribute | `$.Instances.KVStoreInstance[].Config` | string | Parameter config JSON |
| RestartInstance | `$.RequestId` | string | Request ID |
| DeleteInstance | `$.RequestId` | string | Request ID |
| DescribeAccounts | `$.Accounts.Account[].AccountName` | array | Account names |
| DescribeAccounts | `$.Accounts.Account[].AccountType` | string | Normal / Super |
| DescribeAccounts | `$.Accounts.Account[].AccountStatus` | string | Available / Unavailable |
| DescribeBackups | `$.Backups.Backup[].BackupId` | array | Backup IDs |
| DescribeBackups | `$.Backups.Backup[].BackupStatus` | string | Success / Failed |
| DescribeBackups | `$.Backups.Backup[].BackupType` | string | Automated / Manual |
| DescribeBackups | `$.Backups.Backup[].BackupStartTime` | string | ISO 8601 timestamp |
| DescribeBackups | `$.Backups.Backup[].BackupEndTime` | string | ISO 8601 timestamp |
| DescribeBackups | `$.Backups.Backup[].BackupSize` | long | Backup size (bytes) |
| DescribeSecurityIps | `$.SecurityIpGroups.SecurityIpGroup[].SecurityIpGroupName` | array | Whitelist group names |
| DescribeSecurityIps | `$.SecurityIpGroups.SecurityIpGroup[].SecurityIpList` | array | IP whitelist entries |
| DescribeParameters | `$.RunningParameters.Parameter[].ParameterName` | array | Parameter names |
| DescribeParameters | `$.RunningParameters.Parameter[].ParameterValue` | array | Parameter values |
| DescribeSlowLogs | `$.Items.SlowLog[].SQLText` | array | Slow query commands |
| DescribeSlowLogs | `$.Items.SlowLog[].ExecuteTime` | string | Execution timestamp |
| DescribeSlowLogs | `$.Items.SlowLog[].ElapsedTime` | long | Elapsed time (microseconds) |
| DescribeMonitorItems | `$.MonitorItems.MonitorItem[].MonitorKey` | array | Metric keys |
| DescribeHistoryMonitorValues | `$.HistoryMonitorValues` | object | Historical metric values |
| DescribeIntranetAttribute | `$.Bandwidth` | long | Intranet bandwidth (MB/s) |
| DescribeIntranetAttribute | `$.IntranetBandwidth` | long | Intranet bandwidth (MB/s) |
| ModifyInstanceConfig | `$.RequestId` | string | Request ID for tracking |
| ModifySecurityIps | `$.RequestId` | string | Request ID for tracking |
| DeleteAccount | `$.RequestId` | string | Request ID for tracking |
| ResetAccountPassword | `$.RequestId` | string | Request ID for tracking |
| ModifyInstanceMaintainTime | `$.RequestId` | string | Request ID for tracking |
| ModifyInstanceSSL | `$.RequestId` | string | Request ID for tracking |
| ModifyIntranetBandwidth | `$.RequestId` | string | Request ID for tracking |
| UpgradeMinorVersion | `$.RequestId` | string | Request ID for tracking |
| FlushInstance | `$.RequestId` | string | Request ID for tracking |

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

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-14 | Initial Redis/Tair skill with dual-path (CLI + SDK) support |

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

```go
package main

import (
	"fmt"
	"os"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	rkvstore "github.com/alibabacloud-go/r-kvstore-20150101/v2/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		Endpoint:        tea.String("r-kvstore.aliyuncs.com"),
	}

	c, err := rkvstore.NewClient(config)
	if err != nil {
		panic(err)
	}

	req := &rkvstore.CreateInstanceRequest{
		RegionId:      tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		InstanceName:  tea.String(os.Getenv("INSTANCE_NAME")),
		InstanceClass: tea.String(os.Getenv("INSTANCE_CLASS")),
		EngineVersion: tea.String(os.Getenv("ENGINE_VERSION")),
		ZoneId:        tea.String(os.Getenv("ZONE_ID")),
		NetworkType:   tea.String(os.Getenv("NETWORK_TYPE")),
		VPCId:         tea.String(os.Getenv("VPC_ID")),
		VSwitchId:     tea.String(os.Getenv("VSWITCH_ID")),
		ChargeType:    tea.String(os.Getenv("CHARGE_TYPE")),
		Password:      tea.String(os.Getenv("PASSWORD")),
		Token:         tea.String(os.Getenv("TOKEN")),
	}

	resp, err := c.CreateInstance(req)
	if err != nil {
		panic(err)
	}

	instanceId := tea.ToString(resp.Body.InstanceId)
	fmt.Printf("Created Redis/Tair instance: %s\n", instanceId)

	// Poll until Normal
	for i := 0; i < 60; i++ {
		descReq := &rkvstore.DescribeInstancesRequest{
			RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
			InstanceId: tea.String(instanceId),
		}
		descResp, err := c.DescribeInstances(descReq)
		if err != nil {
			panic(err)
		}
		items := descResp.Body.Instances.KVStoreInstance
		if len(items) > 0 && tea.ToString(items[0].InstanceStatus) == "Normal" {
			fmt.Println("Instance is Normal")
			break
		}
		time.Sleep(10 * time.Second)
	}
}
```

#### Post-execution Validation

1. Read `{{output.instance_id}}` from `$.InstanceId`.
2. Poll **DescribeInstances** until `InstanceStatus` is `Normal`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{output.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
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

```go
req := &rkvstore.DescribeInstancesRequest{
	RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeInstances(req)
```

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

```go
req := &rkvstore.DescribeInstanceAttributeRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeInstanceAttribute(req)
```

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

```go
req := &rkvstore.RestartInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.RestartInstance(req)
```

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
for i in $(seq 1 30); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
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

```go
req := &rkvstore.DeleteInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DeleteInstance(req)
```

#### Post-execution Validation

Poll **DescribeInstances** until instance is absent (returns empty list or
`InstanceNotFound`) within **300s**.

```bash
for i in $(seq 1 30); do
  RESULT=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=TotalCount rows=TotalCount)
  [ "$RESULT" = "0" ] && break
  sleep 10
done
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

```go
req := &rkvstore.ModifyInstanceSpecRequest{
	InstanceId:  tea.String(os.Getenv("INSTANCE_ID")),
	InstanceClass: tea.String(os.Getenv("INSTANCE_CLASS")),
	OrderType:   tea.String("UPGRADE"),
}
resp, err := c.ModifyInstanceSpec(req)
```

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
```

---

### Operation: Describe Accounts

#### Execution — CLI

```bash
aliyun r-kvstore describe-accounts \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

```go
req := &rkvstore.DescribeAccountsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeAccounts(req)
```

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

```go
req := &rkvstore.CreateAccountRequest{
	InstanceId:      tea.String(os.Getenv("INSTANCE_ID")),
	AccountName:     tea.String(os.Getenv("ACCOUNT_NAME")),
	AccountPassword: tea.String(os.Getenv("ACCOUNT_PASSWORD")),
	AccountType:     tea.String(os.Getenv("ACCOUNT_TYPE")),
}
resp, err := c.CreateAccount(req)
```

#### Post-execution Validation

Poll until account status is `Available`:

```bash
for i in $(seq 1 24); do
  STATUS=$(aliyun r-kvstore describe-accounts \
    --InstanceId "{{user.instance_id}}" \
    --AccountName "{{user.account_name}}" \
    --output cols=AccountStatus rows=Accounts.Account[0].AccountStatus)
  [ "$STATUS" = "Available" ] && break
  sleep 5
done
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

```go
req := &rkvstore.DeleteAccountRequest{
	InstanceId:  tea.String(os.Getenv("INSTANCE_ID")),
	AccountName: tea.String(os.Getenv("ACCOUNT_NAME")),
}
resp, err := c.DeleteAccount(req)
```

#### Post-execution Validation

Poll **DescribeAccounts** until account is absent:

```bash
for i in $(seq 1 24); do
  RESULT=$(aliyun r-kvstore describe-accounts \
    --InstanceId "{{user.instance_id}}" \
    --AccountName "{{user.account_name}}" \
    --output cols=TotalCount rows=Accounts.Account[0].AccountName)
  [ -z "$RESULT" ] && break
  sleep 5
done
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

```go
req := &rkvstore.ResetAccountPasswordRequest{
	InstanceId:      tea.String(os.Getenv("INSTANCE_ID")),
	AccountName:     tea.String(os.Getenv("ACCOUNT_NAME")),
	AccountPassword: tea.String(os.Getenv("NEW_PASSWORD")),
}
resp, err := c.ResetAccountPassword(req)
```

#### Post-execution Validation

Verify account status returns to `Available`:

```bash
for i in $(seq 1 24); do
  STATUS=$(aliyun r-kvstore describe-accounts \
    --InstanceId "{{user.instance_id}}" \
    --AccountName "{{user.account_name}}" \
    --output cols=AccountStatus rows=Accounts.Account[0].AccountStatus)
  [ "$STATUS" = "Available" ] && break
  sleep 5
done
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

```go
req := &rkvstore.DescribeBackupsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	StartTime:  tea.String(os.Getenv("START_TIME")),
	EndTime:    tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeBackups(req)
```

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

```go
req := &rkvstore.CreateBackupRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.CreateBackup(req)
```

#### Post-execution Validation

Poll **DescribeBackups** until backup status is `Success`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun r-kvstore describe-backups \
    --InstanceId "{{user.instance_id}}" \
    --output cols=BackupStatus rows=Backups.Backup[0].BackupStatus)
  [ "$STATUS" = "Success" ] && break
  sleep 10
done
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

```go
req := &rkvstore.RestoreInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	BackupId:   tea.String(os.Getenv("BACKUP_ID")),
}
resp, err := c.RestoreInstance(req)
```

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
```

---

### Operation: Describe Security IPs (Whitelist)

#### Execution — CLI

```bash
aliyun r-kvstore describe-security-ips \
  --InstanceId "{{user.instance_id}}"
```

#### Execution — JIT Go SDK

```go
req := &rkvstore.DescribeSecurityIpsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeSecurityIps(req)
```

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

```go
req := &rkvstore.ModifySecurityIpsRequest{
	InstanceId:          tea.String(os.Getenv("INSTANCE_ID")),
	SecurityIps:         tea.String(os.Getenv("SECURITY_IPS")),
	SecurityIpGroupName: tea.String(os.Getenv("SECURITY_IP_GROUP_NAME")),
}
resp, err := c.ModifySecurityIps(req)

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

```go
req := &rkvstore.DescribeParametersRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeParameters(req)
```

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

```go
req := &rkvstore.ModifyParameterRequest{
	InstanceId:     tea.String(os.Getenv("INSTANCE_ID")),
	ParameterName:  tea.String(os.Getenv("PARAMETER_NAME")),
	ParameterValue: tea.String(os.Getenv("PARAMETER_VALUE")),
}
resp, err := c.ModifyParameter(req)

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

```go
req := &rkvstore.DescribeSlowLogsRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	StartTime:  tea.String(os.Getenv("START_TIME")),
	EndTime:    tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeSlowLogs(req)
```

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

```go
req := &rkvstore.DescribeHistoryMonitorValuesRequest{
	InstanceId:  tea.String(os.Getenv("INSTANCE_ID")),
	MonitorKeys: tea.String(os.Getenv("MONITOR_KEYS")),
	StartTime:   tea.String(os.Getenv("START_TIME")),
	EndTime:     tea.String(os.Getenv("END_TIME")),
}
resp, err := c.DescribeHistoryMonitorValues(req)
```

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

```go
req := &rkvstore.ModifyInstanceMaintainTimeRequest{
	InstanceId:        tea.String(os.Getenv("INSTANCE_ID")),
	MaintainStartTime: tea.String(os.Getenv("MAINTAIN_START_TIME")),
	MaintainEndTime:   tea.String(os.Getenv("MAINTAIN_END_TIME")),
}
resp, err := c.ModifyInstanceMaintainTime(req)

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

```go
req := &rkvstore.ModifyInstanceSSLRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	SSLEnabled: tea.String(os.Getenv("SSL_ENABLED")),
}
resp, err := c.ModifyInstanceSSL(req)

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
for i in $(seq 1 12); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
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

```go
req := &rkvstore.ModifyIntranetBandwidthRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	Bandwidth:  tea.Int64(int64(os.Getenv("BANDWIDTH"))),
}
resp, err := c.ModifyIntranetBandwidth(req)

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

```go
req := &rkvstore.MigrateToOtherZoneRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ZoneId:     tea.String(os.Getenv("ZONE_ID")),
}
resp, err := c.MigrateToOtherZone(req)
```

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
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

```go
req := &rkvstore.UpgradeMinorVersionRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.UpgradeMinorVersion(req)
```

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
for i in $(seq 1 60); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
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

```go
req := &rkvstore.FlushInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.FlushInstance(req)
```

#### Post-execution Validation

Poll until `InstanceStatus` returns to `Normal`:

```bash
for i in $(seq 1 30); do
  STATUS=$(aliyun r-kvstore describe-instances \
    --RegionId "{{user.region}}" \
    --InstanceId "{{user.instance_id}}" \
    --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
  [ "$STATUS" = "Normal" ] && break
  sleep 10
done
```

---

---

### Operation: Intelligent Inspection（智能巡检）

一键执行Redis/Tair实例的全面健康检查，整合CMS指标 + 实例配置 + 慢查询分析。

#### 执行流程

1. 调用 `DescribeInstances` 检查实例状态和配置
2. 调用 `alicloud-cms-ops` 查询最近15分钟的CPU/内存/连接/延迟指标
3. 调用 `DescribeSlowLogs` 检查最近1小时的慢查询
4. 调用 `DescribeSecurityIps` 检查白名单配置
5. 调用 `DescribeBackups` 检查最近备份状态
6. 综合评分并生成巡检报告

#### 巡检评分标准

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| 实例状态 | Normal=100, 其他=0 | 20% |
| CPU使用率 | <70%=100, 70-85%=60, >85%=0 | 20% |
| 内存使用率 | <75%=100, 75-90%=60, >90%=0 | 20% |
| 连接使用率 | <70%=100, 70-85%=60, >85%=0 | 15% |
| 延迟 | AvgRt<5ms=100, 5-20ms=60, >20ms=0 | 15% |
| 备份状态 | 最近一次成功=100, 失败=0 | 10% |

#### 执行 — CLI

```bash
#!/bin/bash
# redis-intelligent-inspection.sh
# Usage: ./redis-intelligent-inspection.sh <InstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"
SCORE=0

echo "=== Redis/Tair Intelligent Inspection ==="
echo "Instance: $INSTANCE_ID"
echo "Region: $REGION"
echo ""

# 1. Instance status check
STATUS=$(aliyun r-kvstore describe-instances \
  --RegionId "$REGION" \
  --InstanceId "$INSTANCE_ID" \
  --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
echo "[1/5] Instance Status: $STATUS"
[ "$STATUS" = "Normal" ] && SCORE=$((SCORE + 20))

# 2. CPU usage check
CPU=$(aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "N/A")
echo "[2/5] CPU Usage: $CPU%"
# (Threshold logic would be implemented in production)

# 3. Slow log check
SLOW_COUNT=$(aliyun r-kvstore describe-slow-logs \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=TotalCount rows=TotalCount 2>/dev/null || echo "0")
echo "[3/5] Slow Logs (1h): $SLOW_COUNT"

# 4. Backup check
BACKUP_STATUS=$(aliyun r-kvstore describe-backups \
  --InstanceId "$INSTANCE_ID" \
  --PageSize 1 \
  --output cols=BackupStatus rows=Backups.Backup[0].BackupStatus 2>/dev/null || echo "N/A")
echo "[4/5] Last Backup: $BACKUP_STATUS"
[ "$BACKUP_STATUS" = "Success" ] && SCORE=$((SCORE + 10))

# 5. Whitelist check
WHITELIST=$(aliyun r-kvstore describe-security-ips \
  --InstanceId "$INSTANCE_ID" \
  --output cols=SecurityIpList rows=SecurityIpGroups.SecurityIpGroup[0].SecurityIpList 2>/dev/null || echo "N/A")
echo "[5/5] Whitelist: $WHITELIST"

echo ""
echo "=== Inspection Score: $SCORE/100 ==="
if [ "$SCORE" -ge 80 ]; then
  echo "Status: HEALTHY"
elif [ "$SCORE" -ge 60 ]; then
  echo "Status: WARNING - Review recommended"
else
  echo "Status: CRITICAL - Immediate action required"
fi
```

#### 输出格式

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "redis",
  "resource_id": "r-bp1zxszhcgatnx****",
  "overall_score": 85,
  "dimensions": [
    {"name": "实例状态", "score": 100, "status": "healthy"},
    {"name": "CPU使用率", "score": 80, "status": "warning", "value": "75%"},
    {"name": "内存使用率", "score": 60, "status": "critical", "value": "92%"},
    {"name": "连接使用率", "score": 90, "status": "healthy", "value": "45%"},
    {"name": "延迟", "score": 100, "status": "healthy", "value": "2ms"},
    {"name": "备份状态", "score": 100, "status": "healthy"}
  ],
  "recommendations": [
    "内存使用率92%超过严重阈值，建议扩容或优化数据",
    "CPU使用率75%超过警告阈值，建议检查慢查询"
  ]
}
```

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

> **CLI Polling with `--waiter`:** For operations that require waiting for state transitions, `aliyun` CLI supports `--waiter` (when available):
> ```bash
> aliyun r-kvstore describe-instances \
>   --InstanceId "{{user.instance_id}}" \
>   --waiter expr='Instances.KVStoreInstance[0].InstanceStatus' to=Normal timeout=600 interval=10
> ```
> Use `--waiter` when documented for the product; otherwise use shell loop polling as shown in execution flows.

## Reference Directory

- [Core Concepts](references/core-concepts.md) — Redis/Tair architecture, instance types, Tair data types, networking model
- [API & SDK Usage](references/api-sdk-usage.md) — Complete API operation mapping with request/response fields and Go SDK patterns
- [CLI Usage](references/cli-usage.md) — `aliyun r-kvstore` command reference, output formatting, and `--waiter` usage
- [Troubleshooting Guide](references/troubleshooting.md) — Symptom-based decision tree, diagnostic commands, error code reference, and support escalation
- [Monitoring & Alerts](references/monitoring.md) — Key metrics, KPI thresholds, automated monitoring flows, and CloudMonitor integration
- [Prompts Guide](references/prompts.md) — Ready-to-use prompt templates for 40+ operational scenarios (lifecycle, security, diagnostics, batch ops, advanced analytics)
- [Integration](references/integration.md) — VPC, RAM, CI/CD, Terraform/Pulumi/Ansible integration patterns

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required APIs only.
- **Availability:** Use multi-AZ deployment for production instances.
- **Cost:** Right-size instances; use auto-renewal for PrePaid instances.
- **Security:** Regularly rotate passwords; restrict whitelist to minimum required IPs.
- **Backup:** Enable automated backups; test restore procedures periodically.

---
name: alicloud-elasticsearch-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud Elasticsearch — Elasticsearch instances (ES), Logstash instances, Kibana,
  snapshots, plugins, and diagnostics. User mentions Elasticsearch, 阿里云ES,
  ES实例, Logstash, 搜索引擎, 全文检索, 日志分析, or describes Elasticsearch-specific
  scenarios (cluster health, index management, snapshot backup, plugin installation,
  performance tuning, version upgrade) even without naming the product directly.
  Not for billing, RAM, VPC (unless VPC endpoint configuration), or related products
  that have their own ops skills.
license: MIT
compatibility: >-
  Alibaba Cloud Go SDK (`github.com/alibabacloud-go/elasticsearch-20170613/v6/client`),
  valid API credentials, network access to Alibaba Cloud Elasticsearch endpoints.
  Note: Official `aliyun` CLI does NOT directly support Elasticsearch product —
  JIT Go SDK is the primary execution path.
metadata:
  author: alicloud
  version: "2.1.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "elasticsearch-2017-06-13 (SDK v6.3.0)"
  cli_applicability: "sdk-only"
  cli_support_evidence: >-
    Official `aliyun` CLI does not expose Elasticsearch product subcommand.
    Verified via `aliyun help` output — no `elasticsearch` command available.
    JIT Go SDK (`github.com/alibabacloud-go/elasticsearch-20170613/v6`) is required
    for all Elasticsearch operations.
  well_architected_compliance: "80% (Security: 92%, Stability: 88%, Cost: 65%, Performance: 80%, Efficiency: 85%)"
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Elasticsearch Operations Skill

## Overview

Alibaba Cloud Elasticsearch provides fully managed Elasticsearch clusters based on the open-source Elasticsearch, offering cloud-native search and analytics capabilities with enterprise features. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **SDK/API execution**, response validation, and failure recovery. **Do not use the web console as the primary agent execution path**.

> **UX Compliance:** This skill follows the [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: sdk-only`:** Official `aliyun` CLI does **not** expose Elasticsearch product. **SDK/API remains mandatory** for all operations. This skill uses JIT Go SDK for all Elasticsearch management operations.

## Five Core Standards (Quality Gates)

Every generated skill MUST satisfy these five standards. Use them as a design checklist:

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with ≥ 10 Elasticsearch-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product (Elasticsearch), one primary resource model (Instance); cross-product delegation to other skills |

### Well-Architected Framework Integration (卓越架构)

In addition to the Five Core Standards, every generated skill MUST map its operations to Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html) five pillars:

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | IAM permissions, credential masking, VPC endpoint, HTTPS | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | Snapshot backup, multi-zone, restart/upgrade runbook | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | Instance spec selection, storage tiering | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Batch plugin operations, CI/CD integration | `references/well-architected-assessment.md` §2.4 |
| **性能 (Performance)** | Index template, ILM policy, cluster health metrics | `references/well-architected-assessment.md` §2.5 |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud Elasticsearch" OR "阿里云ES" OR "ES实例" OR "Logstash" OR "搜索引擎"
- Task involves lifecycle operations on **Elasticsearch Instance** (create, describe, modify, delete, list, restart, upgrade)
- Task involves **Logstash Instance** management
- Task involves **Snapshot** backup and restore operations
- Task involves **Plugin** installation, configuration, or removal
- Task keywords: 集群健康, 索引管理, 快照备份, 日志分析, 全文检索, 性能调优, 版本升级, Kibana配置
- User asks to deploy, configure, troubleshoot, or monitor Elasticsearch **via API, SDK, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is VPC network creation only → delegate to: `alicloud-vpc-ops` (VPC endpoint config is within scope)
- Task is ECS instance for Elasticsearch BEK deployment → delegate to: `alicloud-ecs-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

- If VPC or VSwitch creation needed before Elasticsearch instance → complete via `alicloud-vpc-ops` first
- If security group rules needed → delegate to `alicloud-ecs-ops` for security group operations
- Multi-product requests: handle each product with its skill; do not merge unrelated APIs

## Variable Convention (Agent-Readable)

Structured placeholders reduce injection ambiguity and unsafe prompts:

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.instance_id}}` | User-supplied Elasticsearch instance ID | Ask once; reuse |
| `{{user.instance_name}}` | User-supplied instance name | Ask once; reuse |
| `{{user.version}}` | Elasticsearch version (e.g., 7.10, 8.9) | Ask once; reuse |
| `{{user.node_spec}}` | Node specification (data node spec) | Ask once; reuse |
| `{{output.instance_id}}` | From last API JSON response | Parse from `Body.Result.instanceId` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Endpoint:** `elasticsearch.aliyuncs.com` (public) or VPC endpoint
- **API Version:** `2017-06-13`
- **SDK Package:** `github.com/alibabacloud-go/elasticsearch-20170613/v6/client`

### Example Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateInstance | `$.body.result.instanceId` | string | New ES instance ID |
| DescribeInstance | `$.body.result.status` | string | Instance status (Normal, Activating, etc.) |
| ListInstance | `$.body.result.instances[].instanceId` | array | List of instance IDs |
| DescribeInstance | `$.body.result.esVersion` | string | Elasticsearch version |
| DescribeInstance | `$.body.result.nodeAmount` | int | Number of data nodes |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateInstance | — | `Normal` | 10s | 600s (10min) |
| RestartInstance | `Normal` | `Normal` | 10s | 300s |
| UpdateInstance | `Normal` | `Normal` | 10s | 300s |
| DeleteInstance | `Normal` | absent | 10s | 300s |

## Quick Start

### What This Skill Does
This skill enables you to deploy, configure, troubleshoot, and monitor Elasticsearch instances on Alibaba Cloud using JIT Go SDK (CLI does not support Elasticsearch).

### Prerequisites
- [ ] Go runtime installed (1.21+) or JIT download capability
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup
```bash
# Check Go runtime
go version

# Quick SDK test (in /tmp/aliyun-sdk-workspace)
mkdir -p /tmp/aliyun-sdk-workspace && cd /tmp/aliyun-sdk-workspace
go mod init es-test
go get github.com/alibabacloud-go/elasticsearch-20170613/v6/client
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
```

### Your First Command
```go
// List Elasticsearch instances
package main

import (
    "fmt"
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    elasticsearch "github.com/alibabacloud-go/elasticsearch-20170613/v6/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("elasticsearch.aliyuncs.com"),
    }
    client, _ := elasticsearch.NewClient(config)
    req := &elasticsearch.ListInstanceRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    resp, _ := client.ListInstance(req)
    fmt.Println(tea.ToString(resp.Body))
}
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand Elasticsearch architecture
- [Common Operations](#execution-flows) — Create, manage, and delete instances
- [Troubleshooting](references/troubleshooting.md) — Fix common issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateInstance | Create a new Elasticsearch cluster | High | Low |
| DescribeInstance | View instance details | Low | None |
| ListInstance | List all Elasticsearch instances | Low | None |
| UpdateInstance | Modify instance configuration | Medium | Medium |
| RestartInstance | Restart Elasticsearch cluster | Medium | Medium |
| DeleteInstance | Remove an Elasticsearch instance | Low | **High** — irreversible |
| CreateSnapshot | Create backup snapshot | Medium | Low |
| RestoreSnapshot | Restore from snapshot | Medium | Medium |
| UpgradeEngineVersion | Upgrade Elasticsearch version | High | High |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1.0 | 2026-05-17 | AIOps optimization: Added proactive-inspection.md (8 multi-metric anomaly patterns), alarm-storm-handling.md, diagnostic-report-schema.md. Enhanced monitoring.md (Section 8), troubleshooting.md (Section 6 multi-round self-reflection), integration.md (Section 6 cross-skill diagnosis). Added observability.md, prompts.md. All P0/P1 items completed. |
| 2.0.0 | 2026-05-17 | Well-Architected Framework optimization: Security (92%), Stability (88%). Added security-enhancement.md, stability-enhancement.md, knowledge-base.md, batch-operations.md. P0 gaps resolved. |
| 1.0.0 | 2026-05-17 | Initial Elasticsearch SDK-only skill based on elasticsearch-20170613 v6.3.0 |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK) → Validate → Recover**. Do not skip phases.

### Operation: Create Elasticsearch Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | Import elasticsearch client; version v6.3.0+ | No import error | Document SDK install |
| Go runtime | `go version` ≥ 1.21 | Exit code 0 | JIT download Go 1.24 |
| Credentials | Env vars set; construct credential | Non-empty keys | HALT; user configures env |
| Region | Check supported regions via DescribeRegions | Region supported | Suggest valid region |
| Quota | Check instance quota (user quota API) | Sufficient quota | HALT; user raises quota |
| VPC exists | Validate VPC and VSwitch IDs | Found in region | HALT; create via vpc-ops |

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

Execute:
```bash
# In /tmp/aliyun-sdk-workspace
go mod init es-create
go get github.com/alibabacloud-go/elasticsearch-20170613/v6/client
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go run ./main.go
```

#### Post-execution Validation

1. Capture `{{output.instance_id}}` from response: `Body.Result.InstanceId`
2. Poll DescribeInstance until terminal success state:

```go
// Polling loop
for i := 0; i < 60; i++ {
    resp, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    if err != nil { panic(err) }
    status := tea.ToString(resp.Body.Result.Status)
    if status == "Normal" {
        fmt.Println("✅ Instance created and running")
        break
    }
    if status == "Activating" || status == "Initializing" {
        time.Sleep(10 * time.Second)
        continue
    }
    fmt.Printf("❌ Unexpected status: %s\n", status)
    break
}
```

#### Failure Recovery

| Error pattern | Max retries | Agent Action | UX Feedback |
|--------------|-------------|--------------|-------------|
| `InvalidParameter` | 0 | Fix parameters per OpenAPI spec | `[ERROR] InvalidParameter: Check parameter values against API docs` |
| `QuotaExceeded` | 0 | HALT; user raises quota | `[ERROR] QuotaExceeded: Instance quota limit reached. Request quota increase.` |
| `VpcNotFound` | 0 | HALT; create VPC via vpc-ops | `[ERROR] VpcNotFound: Create VPC first using alicloud-vpc-ops` |
| `RegionNotSupported` | 0 | HALT; suggest valid region | `[ERROR] RegionNotSupported: Use supported region (cn-hangzhou, cn-shanghai, etc.)` |
| `Throttling` / 429 | 3 | Exponential backoff 2s → 4s → 8s | `⚠️ Rate limited. Retrying in {backoff}s...` |
| `InternalError` / 5xx | 3 | Retry with backoff; HALT if persists | `[ERROR] InternalError: Server error. Retry or escalate with RequestId` |

### Operation: Describe Elasticsearch Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | Import elasticsearch client | No import error | Install SDK |
| Instance ID | User provided | Non-empty ID string | Ask user for instance_id |

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| InstanceId | `Body.Result.InstanceId` | Unique identifier |
| InstanceName | `Body.Result.InstanceName` | Display name |
| Status | `Body.Result.Status` | Normal/Activating/Inactive |
| EsVersion | `Body.Result.EsVersion` | Elasticsearch version |
| Endpoints | `Body.Result.Endpoints` | Connection endpoints |
| NodeAmount | `Body.Result.NodeAmount` | Data node count |

### Operation: List Elasticsearch Instances

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

### Operation: Update Elasticsearch Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance exists | DescribeInstance | Found | HALT; instance not found |
| Instance status | DescribeInstance | `Normal` (stable) | Wait for stable state |
| Pending operations | Check for restart in progress | None | Wait for completion |

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Poll DescribeInstance until `Status` returns to `Normal`
2. Validate updated configuration matches request
3. Report completion with new configuration details

### Operation: Restart Elasticsearch Instance

#### Pre-flight (Safety Gate)

- **WARN** user: Restart causes temporary service interruption
- **MUST** confirm: instance ID and restart intent

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll status: `Activating` → `Normal` (restart in progress) → `Normal` (complete)

### Operation: Delete Elasticsearch Instance

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of `{{user.instance_name}}` (`{{user.instance_id}}`)
- **MUST** warn user: all data, indices, snapshots will be lost
- **MUST NOT** proceed without clear user assent

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll DescribeInstance until **NotFound** error (instance deleted)

### Operation: Create Snapshot (Backup)

> **Stability Pillar:** Following Alibaba Cloud Well-Architected Framework §面向风险的应急快恢, backup operations are mandatory before destructive changes.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance exists | DescribeInstance | Found and `Normal` | HALT |
| Snapshot quota | Check snapshot limits | Sufficient | HALT; user raises quota |

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll snapshot status until `Success` (check via DescribeSnapshot or ListSnapshots)

### Operation: Upgrade Engine Version

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Instance exists | DescribeInstance | Found and `Normal` | HALT |
| Target version supported | GetRegionConfiguration | Version available | HALT; unsupported version |
| Backup exists | ListSnapshots | At least one snapshot | WARN; suggest backup first |

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Poll until upgrade completes (status transitions through upgrade phases)

## Prerequisites

1. **Bootstrap Go runtime** (JIT SDK execution path):

   ```bash
   # Check if Go exists
   if ! command -v go &> /dev/null; then
       # JIT download Go 1.24 (auto-detects OS and architecture)
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

2. **Configure Credentials** — Environment variables (recommended):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```
   > **IMPORTANT:** When outputting the above commands to console or logs, the agent MUST replace `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with the masking format `****` instead of the actual secret value (i.e., display as `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`). Never resolve `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` to its actual value in any visible output.

3. **Initialize SDK Workspace**:

   ```bash
   mkdir -p /tmp/aliyun-sdk-workspace
   cd /tmp/aliyun-sdk-workspace
   go mod init es-sdk-script
   
   # Core dependencies
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/tea-utils/v2/service
   
   # Elasticsearch SDK
   go get github.com/alibabacloud-go/elasticsearch-20170613/v6/client
   ```

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [Security Enhancement](references/security-enhancement.md) — **NEW: Fine-grained RAM policies, credential validation, ActionTrail integration**
- [Stability Enhancement](references/stability-enhancement.md) — **NEW: Recovery runbooks, change window management, fault classification**
- [Knowledge Base](references/knowledge-base.md) — **NEW: Common issues, version behaviors, troubleshooting trees**
- [Observability Configuration](references/observability.md) — **NEW: Three-pillar observability stack, Grafana dashboards, alert rules**
- [Prompt Templates](references/prompts.md) — **NEW: Standardized AIOps prompt templates for operations, diagnosis, inspection, reports**
- [User Experience Specification](../alicloud-skill-generator/references/user-experience-spec.md)
- [Execution Environment Setup](../alicloud-skill-generator/references/execution-environment.md)
- [Enhanced Self-Healing Framework](../alicloud-skill-generator/references/enhanced-self-healing-framework.md)

## Operations Directory

- [Batch Operations](operations/batch-operations.md) — **NEW: Safe batch restart, spec upgrade, snapshot, whitelist patterns**
- [Proactive Inspection](operations/proactive-inspection.md) — **NEW: AIOps proactive health inspection with multi-metric anomaly patterns**
- [Alarm Storm Handling](operations/alarm-storm-handling.md) — **NEW: AIOps alarm storm detection, deduplication, suppression, aggregation**

## Reports Directory

- [Diagnostic Report Schema](reports/diagnostic-report-schema.md) — **NEW: Unified JSON schema for AIOps diagnostic reports**

## Operational Best Practices

- **Least privilege:** RAM policies scoped to `elasticsearch:*` actions only.
- **Multi-zone:** Recommend distributing nodes across multiple zones for HA.
- **Backup:** Create snapshots before major changes (restart, upgrade, spec change).
- **Cost:** Select appropriate node spec based on workload; use reserved instances for stable workloads.

---

## Quality Gate (GCL)

Tenth rollout of GCL per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, tenth skill) |
| `max_iter` | 2 |
| `cli_applicability` | **sdk-only** (REST + Go SDK; CLI is not the primary path) |
| Most-scrutinized | Wildcard `DELETE /*` / `DELETE /<prefix>*` (Safety = 0), `_delete_by_query` with `match_all`, `_forcemerge max_num_segments=1` (irreversible) |
| Hard rule | All `Delete*` ops (instance, index, by-query) require `snapshot_trace` — no waiver |

### Changelog
1.0.0 | 2026-06-04 | Tenth rollout.

---

## Well-Architected Assessment

This skill's operations are evaluated against Alibaba Cloud's Well-Architected Framework (卓越架构). For detailed assessment patterns per pillar:
- [Security Assessment](references/well-architected-assessment.md#21-安全支柱-security)
- [Stability Assessment](references/well-architected-assessment.md#22-稳定支柱-stability)
- [Cost Assessment](references/well-architected-assessment.md#23-成本支柱-cost)
- [Efficiency Assessment](references/well-architected-assessment.md#24-效率支柱-efficiency)
- [Performance Assessment](references/well-architected-assessment.md#25-性能支柱-performance)

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **APPLIES** — 本 skill 必须有 `assets/code-snippets/` 目录.

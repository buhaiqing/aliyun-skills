<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

---
name: alicloud-sas-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud Security Center (云安全中心) — asset inventory, agent installation, security
  alerts, vulnerabilities, baseline checks, security score, AccessKey leak
  detection, virus scan, and proactive defense. User mentions Security Center,
  云安全中心, SAS, 安全中心, 主机安全, 漏洞, 基线, 安全告警, 安全评分, Agent 客户端,
  资产中心, 威胁检测, AK 泄露, 病毒查杀, 防勒索, or describes scenarios like
  compromised servers, unfixed CVEs, offline agents, or suspicious processes —
  even without naming the product. Not for ActionTrail audit logs, RAM-only
  permission design, WAF, KMS keys, or pure ECS lifecycle management.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints. Optional plugin: `aliyun plugin install --names aliyun-cli-sas`.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-20"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Sas 2018-12-03 / https://help.aliyun.com/zh/security-center/developer-reference/api-sas-2018-12-03-overview"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help sas` — Product Sas (Security Center), Version
    2018-12-03. Core operations (DescribeCloudCenterInstances, DescribeSuspEvents,
    DescribeVulList, AddInstallCode, OperationSuspEvents, GetSecurityScoreRule)
    have matching CLI commands.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Security Center (SAS) Operations Skill

## Overview

Alibaba Cloud **Security Center** (云安全中心, API product code **Sas**) provides unified
threat detection, vulnerability management, baseline compliance, asset security posture,
and host/container protection across Alibaba Cloud and hybrid assets. This skill is an
**operational runbook** for agents: explicit scope, credential rules, pre-flight checks,
**dual-path execution** (official **`aliyun sas`** CLI as primary, **JIT Go SDK** as
fallback), response validation, and failure recovery.

**Primary resource model:** protected **assets** (servers, containers, cloud products)
identified by **UUID** / **instance ID**, with derived security objects (alerts, vulnerabilities,
baseline risks, security score).

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports the `sas` product.
  Document **both** CLI and SDK paths in each execution flow below. See
  [references/cli-usage.md](references/cli-usage.md) for coverage gaps.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT with delegation to ActionTrail, RAM, ECS, WAF, KMS |
| 2 | **Structured I/O** | `{{env.*}}`, `{{user.*}}`, `{{output.*}}` with OpenAPI JSON paths |
| 3 | **Explicit Actionable Steps** | Pre-flight → Execute → Validate → Recover per operation |
| 4 | **Complete Failure Strategies** | ≥ 15 error codes in Failure Recovery + troubleshooting.md |
| 5 | **Absolute Single Responsibility** | One product (Security Center / Sas); no duplicate ECS/RAM flows |

See [references/well-architected-assessment.md](references/well-architected-assessment.md) for five-pillar guidance.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Security Center" OR "云安全中心" OR "SAS" OR "安全中心" OR "主机安全"
- Task involves **asset inventory** (list servers, agent online/offline, risk flags)
- Task involves **agent lifecycle** (install command, install status, uninstall)
- Task involves **security alerts** (DescribeSuspEvents, handle/ignore/quarantine)
- Task involves **vulnerabilities** (list, detail, fixable list, scan tasks)
- Task involves **baseline / configuration assessment** (check warnings, submit scan)
- Task involves **security score** or global risk statistics
- Task involves **AccessKey leak detection** on assets
- Task involves **virus scan**, **anti-brute-force**, **anti-ransomware** policies managed in Security Center
- Task keywords: 漏洞, 基线, 告警, 安全评分, Agent, 资产, 威胁, 病毒, AK泄露, 主机防护

### SHOULD NOT Use This Skill When

- Task is **API audit / who deleted resource** → delegate to: `alicloud-actiontrail-ops`
- Task is **RAM policy design only** → delegate to: `alicloud-ram-ops`
- Task is **ECS create/stop/resize** without security context → delegate to: `alicloud-ecs-ops`
- Task is **WAF rules** → product `waf-openapi` (separate skill when present)
- Task is **KMS key lifecycle** → delegate to: `alicloud-kms-ops`
- Task is **SOAR playbooks only** → product `sophonsoar` (separate skill when present)
- User insists on **console-only** with no API → state limitation

### Delegation Rules

- **Agent offline on ECS:** use this skill for install/status; use `alicloud-ecs-ops` for instance reachability (security group, Cloud Assistant).
- **Alert root-cause on ECS:** `DescribeSuspEventDetail` here → remediation commands on `alicloud-ecs-ops` if instance change needed.
- **Compliance audit trail:** Security Center findings + `alicloud-actiontrail-ops` for API call provenance.
- Multi-product: complete Security Center query/handle first, then delegate per affected product.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime AK | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime SK | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Use for regional APIs when required |
| `{{user.region_id}}` | Target region | Ask once; reuse |
| `{{user.uuid}}` | Asset UUID in Security Center | Ask once; reuse |
| `{{user.instance_id}}` | ECS/instance ID | Ask once; reuse |
| `{{user.susp_uuid}}` | Alert event UUID | Ask once; reuse |
| `{{user.vul_name}}` | Vulnerability name/alias | Ask once; reuse |
| `{{user.criteria}}` | JSON search criteria for assets | Build from DescribeCriteria or user filters |
| `{{user.start_time}}` | Query start (epoch ms or ISO) | Ask once; reuse |
| `{{user.end_time}}` | Query end | Ask once; reuse |
| `{{output.uuid}}` | Asset UUID from API | Parse `$.Instances[].Uuid` |
| `{{output.request_id}}` | RequestId | Parse `$.RequestId` |
| `{{output.install_code}}` | Agent install verification code | Parse from AddInstallCode / DescribeInstallCode |

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI canonical:** Sas `2018-12-03`, RPC style.
- **Endpoint:** `tds.{region}.aliyuncs.com` (e.g. `tds.cn-shanghai.aliyuncs.com`). See [references/integration.md](references/integration.md).
- **RAM action prefix:** `yundun-sas:*` (e.g. `yundun-sas:DescribeCloudCenterInstances`).
- **Pagination:** Prefer `UseNextToken=true` for large asset lists.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| DescribeCloudCenterInstances | `$.Instances[].Uuid` | string | Asset UUID |
| DescribeCloudCenterInstances | `$.Instances[].InstanceId` | string | Cloud instance ID |
| DescribeCloudCenterInstances | `$.Instances[].ClientStatus` | string | `online` / `offline` / `pause` |
| DescribeCloudCenterInstances | `$.Instances[].RiskStatus` | string | `YES` / `NO` |
| DescribeSuspEvents | `$.SuspEvents[].SuspUuid` | string | Alert UUID |
| DescribeSuspEvents | `$.SuspEvents[].Level` | string | Alert severity |
| DescribeVulList | `$.VulRecords[].Name` | string | Vulnerability name |
| DescribeVulDetails | `$.CveList[].CveName` | string | CVE identifier |
| GetSecurityScoreRule | `$.SecurityScoreRules` | array | Score deduction rules |
| DescribeAllRegionsStatistics | `$.SuspiciousEventCount` | integer | Alert count (verify field in response) |

## Quick Start

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

### Verify Setup

```bash
aliyun sas DescribeAllRegionsStatistics
```

### Your First Command

```bash
# List assets with risk (example criteria — adjust per DescribeCriteria)
aliyun sas DescribeCloudCenterInstances \
  --Criteria '[{"name":"riskStatus","value":"YES"}]' \
  --PageSize 20 \
  --CurrentPage 1
```

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| DescribeCloudCenterInstances | Asset inventory & risk flags | Low | None |
| AddInstallCode / DescribeAgentInstallStatus | Agent install | Medium | Low |
| DescribeSuspEvents / DescribeSuspEventDetail | List/query alerts | Low | None |
| OperationSuspEvents | Handle alerts (block/ignore/quarantine) | Medium | **High** |
| DescribeVulList / DescribeVulDetails | Vulnerability management | Low | None |
| DescribeCheckWarningSummary | Baseline risk overview | Low | None |
| GetSecurityScoreRule | Security score config | Low | None |
| DescribeAccesskeyLeakList | AK leak list | Low | None |
| CreateVirusScanOnceTask | One-time virus scan | Medium | Low |
| AddUninstallClientsByUuids | Uninstall agent | Low | **High** |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI + SDK) → Validate → Recover**.

### Operation: Describe Assets (DescribeCloudCenterInstances)

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI | `aliyun version` | Exit 0 | Install CLI |
| Credentials | Env vars set | Non-empty | HALT |
| Criteria | Valid JSON array | Parseable | Use `DescribeCriteria` to build filters |

#### CLI Execution

```bash
aliyun sas DescribeCloudCenterInstances \
  --Criteria '{{user.criteria}}' \
  --MachineTypes ecs \
  --LogicalExp OR \
  --PageSize 50 \
  --CurrentPage 1 \
  --Lang zh
```

```bash
# NextToken pagination (recommended for large estates)
aliyun sas DescribeCloudCenterInstances \
  --Criteria '{{user.criteria}}' \
  --UseNextToken true \
  --NextToken "{{output.next_token}}" \
  --PageSize 100
```

#### SDK Execution (JIT Fallback)

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Validation

- `$.Success` is `true`
- Report count: `$.TotalCount`, highlight `ClientStatus=offline` and `RiskStatus=YES`

#### Failure Recovery

| Error | Action |
|-------|--------|
| `InvalidParameter` (Criteria) | HALT; fix JSON per DescribeCriteria |
| `Forbidden.NoPermission` | HALT; add `yundun-sas:DescribeCloudCenterInstances` |

---

### Operation: Install Security Center Agent

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Asset exists | DescribeCloudCenterInstances by instance ID | Found | HALT |
| ECS + Cloud Assistant | Delegate to ecs-ops if install via OOS/assistant fails | Assistant online | Document network path |

#### CLI Execution

```bash
# Generate install command for a UUID
aliyun sas AddInstallCode --Uuid {{user.uuid}}
```

```bash
# Query install verification code
aliyun sas DescribeInstallCode --Uuid {{user.uuid}}
```

```bash
# After running install on host (within 2 minutes)
aliyun sas DescribeAgentInstallStatus --Uuid {{user.uuid}}
```

#### Validation

- `DescribeCloudCenterInstances` shows `ClientStatus=online` for `{{user.uuid}}`
- Poll every 30s, max 10 minutes

#### Failure Recovery

| Error | Action |
|-------|--------|
| Agent still `offline` | Check security group, outbound to `tds.*.aliyuncs.com`, host firewall |
| `ClientNotOnline` | Retry install; verify UUID matches instance |

---

### Operation: Query Security Alerts (DescribeSuspEvents)

#### Pre-flight

| Check | Method | Expected |
|-------|--------|----------|
| Time range | Start/end within API limits | Adjust if empty results |

#### CLI Execution

```bash
aliyun sas DescribeSuspEvents \
  --From "{{user.start_time}}" \
  --To "{{user.end_time}}" \
  --PageSize 50 \
  --CurrentPage 1
```

```bash
# Alert detail
aliyun sas DescribeSuspEventDetail --SuspUuid {{user.susp_uuid}}
```

#### Validation

- Present: `SuspUuid`, `Level`, `EventName`, affected `Uuid` / instance
- For handling, require user confirmation before `OperationSuspEvents`

---

### Operation: Handle Security Alerts (OperationSuspEvents)

> **⚠️ DESTRUCTIVE / IMPACTFUL — Requires explicit user confirmation.**

#### Pre-flight (Safety Gate)

- **MUST** show alert summary from `DescribeSuspEventDetail`
- **MUST** confirm operation type: isolate, quarantine, ignore, mark misreport, etc.
- **MUST NOT** auto-block production IPs without user assent

#### CLI Execution

```bash
# Example: handle multiple alerts — verify exact Operation parameter via `aliyun help sas OperationSuspEvents`
aliyun sas OperationSuspEvents \
  --Operation <user_confirmed_operation> \
  --SuspUuidList '["{{user.susp_uuid}}"]'
```

#### Validation

- Re-query `DescribeSuspEvents` or `DescribeSuspEventDetail` for status change
- If quarantine: verify via `DescribeSuspEventQuaraFiles`

---

### Operation: Query Vulnerabilities (DescribeVulList)

#### CLI Execution

```bash
# By type: cve, sys, cms, app, etc. — see `aliyun help sas DescribeVulList`
aliyun sas DescribeVulList \
  --Type cve \
  --PageSize 50 \
  --CurrentPage 1
```

```bash
aliyun sas DescribeVulDetails --Name {{user.vul_name}}
```

```bash
aliyun sas DescribeCanFixVulList --Type cve
```

#### Validation

- Cross-check `$.NeedFix` / severity on affected assets via asset describe

---

### Operation: Baseline / Configuration Assessment

#### CLI Execution

```bash
aliyun sas DescribeCheckWarningSummary
```

```bash
aliyun sas DescribeCheckWarnings \
  --StrategyId <strategy_id> \
  --RiskId <risk_id>
```

```bash
# Trigger baseline scan (verify parameters in API doc)
aliyun sas SubmitCheck
```

#### Validation

- Compare `passRate` / risk counts before and after scan (poll task status APIs if returned)

---

### Operation: Security Score & Global Statistics

#### CLI Execution

```bash
aliyun sas GetSecurityScoreRule
```

```bash
aliyun sas DescribeAllRegionsStatistics
```

```bash
aliyun sas DescribeSecureSuggestion --Lang zh
```

---

### Operation: AccessKey Leak Detection

#### CLI Execution

```bash
aliyun sas DescribeAccesskeyLeakList
```

```bash
aliyun sas DescribeAccessKeyLeakDetail --Id <leak_record_id>
```

```bash
aliyun sas ModifyAccessKeyLeakDeal --Id <leak_record_id> --DealType <type>
```

#### Delegation

- Rotate/disable leaked AK → `alicloud-ram-ops` after recording leak in Security Center

---

### Operation: Virus Scan (CreateVirusScanOnceTask)

#### CLI Execution

```bash
aliyun sas CreateVirusScanOnceTask --UuidList '["{{user.uuid}}"]'
```

#### Validation

- Poll task status via Describe* task APIs; confirm `DescribeAffectedAssets` when complete

---

### Operation: Uninstall Agent (AddUninstallClientsByUuids)

> **⚠️ DESTRUCTIVE — Removes host protection. Requires explicit confirmation.**

#### Pre-flight (Safety Gate)

- **MUST** confirm UUID list and business impact (no HIDS, no real-time alerts)

#### CLI Execution

```bash
aliyun sas AddUninstallClientsByUuids --Uuids '["{{user.uuid}}"]'
```

#### Validation

- `ClientStatus` becomes `offline` or asset removed from active protection list

## Failure Recovery Reference

| Error Code | Description | Retryable | Max Retries | Agent Action |
|------------|-------------|-----------|-------------|--------------|
| `InvalidParameter` | Parameter validation failed | No | 0 | Fix per OpenAPI; retry once if typo |
| `InvalidParameterValue` | Value out of range | No | 0 | HALT; check enums |
| `Forbidden.NoPermission` / `Forbidden.RAM` | RAM denied | No | 0 | HALT; delegate `alicloud-ram-ops` |
| `NoPermission` | Insufficient privilege | No | 0 | HALT; scope `yundun-sas:*` minimally |
| `Throttling` / `Throttling.User` | Rate limited | Yes | 3 | Exponential backoff 1s, 2s, 4s |
| `InternalError` | Server error | Yes | 2 | Retry; escalate with RequestId |
| `ServiceUnavailable` | Temporary outage | Yes | 3 | Backoff; check status page |
| `InvalidAccessKeyId` | Bad AK | No | 0 | HALT; fix credentials |
| `SignatureDoesNotMatch` | Bad signature | No | 0 | HALT; fix SK / clock skew |
| `MissingParameter` | Required field missing | No | 0 | HALT; add parameter |
| `QuotaExceeded` | Quota exceeded | No | 0 | HALT; reduce scope or upgrade edition |
| `OperationDenied` | Operation not allowed | No | 0 | HALT; check edition / asset binding |
| `ClientNotOnline` | Agent offline | No | 0 | Run agent install flow |
| `UuidNotFound` | Asset UUID unknown | No | 0 | Refresh asset list |
| `SuspEventNotFound` | Alert not found | No | 0 | Widen time range; re-list events |
| `InstallCodeNotFound` | Install code missing | No | 0 | Call `AddInstallCode` again |
| `EditionNotSupported` | Feature not in current edition | No | 0 | HALT; suggest upgrade/trial `CreateSasTrial` |

### HALT vs Retry

| Condition | Decision |
|-----------|----------|
| Permission / parameter / edition errors | **HALT** |
| Throttling / 5xx / network | **Retry** with backoff |
| Agent offline for host-scoped action | **HALT** → agent install sub-flow |

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [Knowledge Base](references/knowledge-base.md)
- [Observability](references/observability.md)

## Operational Best Practices

- **Coverage:** Bind all ECS/ACK assets; keep agents `online`.
- **Triage:** Alerts → vulns → baseline → score, in that order for incident response.
- **Least privilege:** Scope RAM to required `yundun-sas:*` actions per workflow.
- **Audit:** Pair findings with `alicloud-actiontrail-ops` for change attribution.


## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.

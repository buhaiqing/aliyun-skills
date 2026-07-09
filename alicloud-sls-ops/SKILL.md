<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

---
name: alicloud-sls-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud Simple Log Service (SLS, 日志服务) — log collection, storage, analysis,
  alerting, dashboards, logtail configuration, consumer groups, and cross-region
  replication. User mentions SLS, 日志服务, Log Service, logtail, 日志采集,
  日志分析, 日志存储, 日志告警, or describes scenarios like log querying,
  real-time analysis, log aggregation, or observability setup — even without
  naming the product directly. Not for CMS monitoring (use alicloud-cms-ops),
  ActionTrail audit logs, or pure ECS/SLB lifecycle management.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun sls`, Go binary with plugin),
  Go 1.21+ runtime (for JIT SDK fallback), valid API credentials, network
  access to Alibaba Cloud endpoints. Plugin required: `aliyun plugin install
  --names aliyun-cli-sls`.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-05"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "SLS OpenAPI 2020-12-30 / https://help.aliyun.com/zh/sls/developer-reference/api-overview"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help sls` — Product Sls (Simple Log Service),
    Version 2020-12-30. Requires plugin installation:
    `aliyun plugin install --names aliyun-cli-sls`. Core operations
    (CreateLogStore, GetLogStore, CreateIndex, GetLogs, CreateAlert,
    CreateDashboard) have matching CLI commands with REST-style path patterns.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Simple Log Service (SLS) Operations Skill

## Overview

Alibaba Cloud **Simple Log Service** (SLS, 日志服务, API product code **sls**) provides
comprehensive log collection, storage, analysis, and visualization capabilities. This skill is an
**operational runbook** for agents: explicit scope, credential rules, pre-flight checks,
**dual-path execution** (official **`aliyun sls`** CLI as primary, **JIT Go SDK** as fallback),
response validation, and failure recovery.

**Primary resource model:** **Projects** (identified by `projectName`) containing **Logstores**
(identified by `logstore`) for log storage, **Indexes** for querying, **Alerts** for monitoring,
and **Dashboards** for visualization.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports the `sls` product via plugin.
  SLS uses REST-style API paths. Document **both** CLI and SDK paths in each execution flow below.
  See [references/cli-usage.md](references/cli-usage.md) for coverage gaps and plugin installation.

> **Important:** SLS CLI uses REST-style path patterns: `aliyun sls GET /logstores/{logstore}/logs`.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT with delegation to CMS, ActionTrail, ECS |
| 2 | **Structured I/O** | `{{env.*}}`, `{{user.*}}`, `{{output.*}}` with REST API paths |
| 3 | **Explicit Actionable Steps** | Pre-flight → Execute → Validate → Recover per operation |
| 4 | **Complete Failure Strategies** | ≥ 15 error codes in Failure Recovery + troubleshooting.md |
| 5 | **Absolute Single Responsibility** | One product (SLS); no duplicate CMS/Audit flows |

See [references/well-architected-assessment.md](references/well-architected-assessment.md) for five-pillar guidance.

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper ./scripts/sls-skillopt-wrapper.sh to enable automated self-repair; fallback to native aliyun only when wrapper unavailable. | SkillOpt |
| Credentials | Read {{env.*}} from environment; never ask user to paste secrets | Integration |
| GCL | All write operations MUST pass GCL review before execution | GCL Rubric |


## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "SLS" OR "日志服务" OR "Log Service" OR "logtail" OR "sls"
- Task involves **project management** (create/delete/query SLS projects)
- Task involves **logstore management** (create/delete/query logstores)
- Task involves **index configuration** (create/update indexes for querying)
- Task involves **log collection** (logtail configuration, machine groups)
- Task involves **log querying** (SQL queries, log analysis, time-range searches)
- Task involves **alerting** (create/update/delete alert rules)
- Task involves **dashboards** (create/update/delete dashboards, widgets)
- Task involves **consumer groups** (real-time log consumption)
- Task involves **cross-region replication** (logstore replication)
- Task keywords: SLS, 日志服务, logtail, 日志采集, 日志分析, 日志存储, 日志告警, 日志查询, 日志监控

### SHOULD NOT Use This Skill When

- Task is **metrics monitoring only** → delegate to: `alicloud-cms-ops`
- Task is **API audit trail** → delegate to: `alicloud-actiontrail-ops`
- Task is **ECS create/stop/resize** without SLS context → delegate to: `alicloud-ecs-ops`
- Task is **SLB access logs** → delegate to: `alicloud-slb-ops`
- User insists on **console-only** with no API → state limitation

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime AK | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime SK | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Use cn-hangzhou for SLS (mainland China) |
| `{{user.region_id}}` | Target region | Ask once; reuse |
| `{{user.project_name}}` | SLS project name | Ask once; reuse |
| `{{user.logstore}}` | Logstore name | Ask once; reuse |
| `{{user.logstore_id}}` | Logstore ID | Parse from GetLogStore |
| `{{user.topic}}` | Log topic (optional) | Ask once; reuse |
| `{{user.alert_name}}` | Alert rule name | Ask once; reuse |
| `{{user.dashboard_name}}` | Dashboard name | Ask once; reuse |
| `{{output.project_name}}` | SLS project name | Parse from CreateProject |
| `{{output.logstore_name}}` | Logstore name | Parse from CreateLogStore |
| `{{output.request_id}}` | RequestId | Parse from API response |

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI canonical:** SLS OpenAPI `2020-12-30`, REST style.
- **Endpoint:** `{project}.{region}.log.aliyuncs.com` (e.g. `my-project.cn-hangzhou.log.aliyuncs.com`).
- **RAM action prefix:** `log:*` (e.g. `log:GetLogStore`).
- **Pagination:** `offset` + `line` or `cursor`.
- **CLI invocation:** REST-style path patterns: `aliyun sls GET/POST/PUT/DELETE <path> --body "..."`.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| GetLogStore | `$.logstore` | string | Logstore name |
| GetLogStore | `$.ttl` | string | Retention period (days) |
| GetLogStore | `$.shardCount` | integer | Number of shards |
| GetLogs | `$.count` | integer | Total log count |
| GetLogs | `$.logs[]` | array | Log entries |
| GetIndex | `$.index` | object | Index configuration |
| ListAlerts | `$.alerts[]` | array | Alert rules |

## Quick Start

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

### 1. Install SLS CLI Plugin

```bash
# Install SLS plugin (required for sls CLI)
aliyun plugin install --names aliyun-cli-sls
```

### 2. Verify Setup

```bash
# Query SLS project info (REST-style)
aliyun sls GET /logstores --header "x-log-apiversion=0.9.0" \
  --project "my-project"
```

### Your First Command

```bash
# Query logs from a logstore
aliyun sls GET /logstores/my-logstore/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "from * | select __time__, __topic__, content limit 100" \
  --project "my-project"
```

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateProject | Create SLS project | Low | Low |
| GetLogStore | Query logstore details | Low | None |
| CreateLogStore | Create logstore | Low | Low |
| DeleteLogStore | Delete logstore | Low | **High** |
| CreateIndex | Create logstore index | Medium | Medium |
| DeleteIndex | Delete logstore index | Low | **High** |
| GetLogs | Query logs | Low | None |
| CreateAlert | Create alert rule | Medium | Medium |
| DeleteAlert | Delete alert rule | Low | **High** |
| CreateDashboard | Create dashboard | Medium | Medium |
| DeleteDashboard | Delete dashboard | Low | **High** |
| CreateConsumerGroup | Create consumer group | Low | Low |
| DeleteConsumerGroup | Delete consumer group | Low | Medium |
| AnalyzeSlbPerHostTraffic | Rank top subdomains by traffic from SLB access logs | Medium | Low |

## Runbooks (Agent-Executable)

| Runbook | 适用场景 | 关键优化 |
|---------|----------|----------|
| [SLB Access Log Cruise](references/runbooks/slb-access-log-cruise.md) | SLB 七层访问日志多维度巡检 | 并行查询、自动发现目标、异常阈值检测 |

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/sls-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun sls ...` 命令在执行时应替换为 `./scripts/sls-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun sls` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI + SDK) → Validate → Recover**.

> **CLI Note:** SLS CLI uses REST-style path patterns with `--header "x-log-apiversion=0.9.0"`.

### Operation: Create SLS Project (CreateProject)

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | Env vars set | Non-empty | HALT |
| Region | Valid SLS region | cn-hangzhou, cn-shanghai, etc. | Check supported regions |
| Project name | Alphanumeric + hyphens, 3-63 chars | Valid format | HALT; fix format |

#### CLI Execution

```bash
# Create SLS project
aliyun sls POST / \
  --header "x-log-apiversion=0.9.0" \
  --body '{"project":"{{user.project_name}}","description":"Log Service project","region":"{{user.region_id}}"}' \
  --project "{{user.project_name}}"
```

#### SDK Execution (JIT Fallback)

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Validation

- HTTP 200 response
- `$.project` is non-empty

#### Failure Recovery

| Error | Action |
|-------|--------|
| `ProjectAlreadyExists` | HALT; project name already taken |
| `InvalidProjectName` | HALT; fix project name format |
| `Forbidden.NoPermission` | HALT; add `log:CreateProject` permission |

---

### Operation: Create Logstore (CreateLogStore)

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SLS project | ProjectExists | Project exists | HALT; create project first |
| Logstore name | Alphanumeric + hyphens, 3-63 chars | Valid format | HALT; fix format |

#### CLI Execution

```bash
# Create logstore
aliyun sls POST /logstores \
  --header "x-log-apiversion=0.9.0" \
  --body '{"logstore":"{{user.logstore}}","ttl":30,"shardCount":2}' \
  --project "{{user.project_name}}"
```

#### Validation

- HTTP 200 response
- Re-query `GetLogStore` to confirm creation

#### Failure Recovery

| Error | Action |
|-------|--------|
| `LogstoreAlreadyExists` | HALT; logstore name already taken |
| `ProjectNotFound` | HALT; create project first |
| `InvalidLogstoreName` | HALT; fix logstore name format |

---

### Operation: Query Logs (GetLogs)

#### CLI Execution

```bash
# Query logs with SQL
aliyun sls GET /logstores/{{user.logstore}}/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "from * | select __time__, __topic__, content limit 100" \
  --project "{{user.project_name}}"
```

#### Validation

- `$.count` ≥ 0
- `$.logs[]` contains log entries

---

### Operation: Delete Logstore (DeleteLogStore)

> **⚠️ DESTRUCTIVE — Requires explicit user confirmation.**

#### Pre-flight (Safety Gate)

- **MUST** confirm: logstore `{{user.logstore}}` will be permanently deleted
- **MUST** warn: All logs in this logstore will be lost
- **MUST NOT** proceed without user assent

#### CLI Execution

```bash
# Delete logstore
aliyun sls DELETE /logstores/{{user.logstore}} \
  --header "x-log-apiversion=0.9.0" \
  --project "{{user.project_name}}"
```

#### Validation

- HTTP 200 response
- Re-query `GetLogStore` — should return 404

---

### Operation: Analyze SLB Per-Host Traffic (AnalyzeSlbPerHostTraffic)

> **Use case:** SLB 实例反馈流量大，需识别同一 SLB IP 上多个子域名（Host）中
> 流量 / 访问量 Top N，定位热点子域名。底层依赖 SLB Access Log 投递到 SLS。

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SLB 监听类型 | 委托 `alicloud-slb-ops` | HTTPS / HTTP（七层） | HALT；四层 SLB 无 host 字段，本 Runbook 不适用 |
| SLB Access Log 已开启并投递到 SLS | 委托 `alicloud-slb-ops` | logstore 持续有日志 | HALT；先开启 Access Log |
| host 字段已建索引 | `GET /logstores/{{user.logstore}}/index` | host 在 line/key 索引中 | 走 `CreateIndex` 增加 host 索引 |
| 时间窗口 | 用户确认 `{{user.time_from}}` / `{{user.time_to}}` | 非空 Unix 秒；**默认 ≤ 24h**，> 24h 必须用户二次确认（防止 SLS 查询配额耗尽 / 计费上扬） | 询问一次；reuse |
| SLB 类型确认 | 委托 `alicloud-slb-ops` 返回 `clb7` 或 `alb` | 用于下方字段适配表选择 | HALT；类型未知不可执行 |

#### SLB Access Log 字段适配表

> 不同 SLB 类型默认投递的字段名不一致；执行前 **必须** 按下表替换 SQL 中的占位字段，否则会得到 `column not found` 或空结果。

| 语义 | CLB 七层 (`clb7`) | ALB (`alb`) | 备注 |
|---|---|---|---|
| 请求 Host | `host` | `host` | 一致 |
| 出向字节（响应体） | `body_bytes_sent` | `response_body_size` | ALB 字段不同 |
| 入向字节（请求体） | `request_length` | `request_size` | ALB 字段不同 |
| 请求耗时（秒） | `request_time` | `request_time` | 一致 |
| 状态码 | `status` | `status` | 一致 |
| 客户端 IP | `client_ip` | `client_ip` | 一致 |

> **占位语义**：下方 SQL 使用 `{{field.bytes_out}}` / `{{field.bytes_in}}` / `{{field.rt}}` 三个变量，Agent 在生成查询前需按上表替换。

#### CLI Execution（统一通过 wrapper；wrapper 不可用时 fallback 原生 `aliyun sls`）

```bash
# Top N 子域名（按 PV）
./scripts/sls-skillopt-wrapper.sh GET /logstores/{{user.logstore}}/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "* | select host, count(*) as pv, sum({{field.bytes_out}})/1024/1024 as mb_out, avg({{field.rt}}) as avg_rt group by host order by pv desc limit 20" \
  --from {{user.time_from}} --to {{user.time_to}} \
  --project "{{user.project_name}}"
```

```bash
# Top N 子域名（按出向流量字节）
./scripts/sls-skillopt-wrapper.sh GET /logstores/{{user.logstore}}/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "* | select host, sum({{field.bytes_out}})/1024/1024/1024 as gb_out, count(*) as pv group by host order by gb_out desc limit 20" \
  --from {{user.time_from}} --to {{user.time_to}} \
  --project "{{user.project_name}}"
```

```bash
# 趋势：每小时各子域名 QPS（识别突发热点）
./scripts/sls-skillopt-wrapper.sh GET /logstores/{{user.logstore}}/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "* | select date_trunc('hour', __time__) as hr, host, count(*) as cnt group by hr, host order by hr" \
  --from {{user.time_from}} --to {{user.time_to}} \
  --project "{{user.project_name}}"
```

> **Fallback:** wrapper 或 `skillopt-lib.sh` 缺失时，将 `./scripts/sls-skillopt-wrapper.sh` 替换为 `aliyun sls`，并在 trace 的 `execution_path` 中标记为 `direct_aliyun`。
>
> **SDK Fallback:** wrapper 与 CLI 均不可用时（如离线运行环境），改走 JIT Go SDK，参见 [API & SDK Usage](references/api-sdk-usage.md)。

#### Validation

- HTTP 200，`$.count > 0`
- 返回行中 `host` 列非空率 ≥ 95%（否则可能命中四层监听或字段未抽取，HALT）
- 记录 Top1 host 的 `pv / 总 pv` 比值与 `gb_out / 总 gb_out` 比值至 trace，便于后续告警基线

#### Failure Recovery

| Error | Action |
|-------|--------|
| `IndexNotFound` 或 host 字段为空 | 走 `CreateIndex` 为 host 建索引；或回退确认监听层级 |
| `Throttling` | wrapper 自动指数退避；3 次仍失败则缩小时间窗口 |
| `InvalidQuery` | 检查 SQL 语法；常见：未对 host 建索引导致 `group by host` 失败 |
| 全部 host 为空 | HALT；监听非七层，本 Runbook 不适用 |

---

## Failure Recovery Reference

| Error Code | Description | Retryable | Max Retries | Agent Action |
|------------|-------------|-----------|-------------|--------------|
| `ProjectAlreadyExists` | Project name taken | No | 0 | HALT; choose different name |
| `ProjectNotFound` | Project not found | No | 0 | HALT; create project first |
| `LogstoreAlreadyExists` | Logstore name taken | No | 0 | HALT; choose different name |
| `LogstoreNotFound` | Logstore not found | No | 0 | HALT; create logstore first |
| `IndexNotFound` | Index not configured | No | 0 | Create index first |
| `InvalidLogstoreName` | Invalid name format | No | 0 | HALT; fix format |
| `InvalidQuery` | SQL query syntax error | No | 0 | Fix query syntax |
| `ShardCountExceedsLimit` | Too many shards | No | 0 | HALT; reduce shard count |
| `TtlExceedsLimit` | TTL out of range | No | 0 | HALT; check TTL limits |
| `Forbidden.NoPermission` | RAM denied | No | 0 | HALT; delegate `alicloud-ram-ops` |
| `Throttling` | Rate limited | Yes | 3 | Exponential backoff 1s, 2s, 4s |
| `InternalError` | Server error | Yes | 2 | Retry; escalate with RequestId |
| `ServiceUnavailable` | Temporary outage | Yes | 3 | Backoff; check status page |
| `InvalidAccessKeyId` | Bad AK | No | 0 | HALT; fix credentials |
| `SignatureDoesNotMatch` | Bad signature | No | 0 | HALT; fix SK / clock skew |

### HALT vs Retry

| Condition | Decision |
|-----------|----------|
| Permission / parameter / quota errors | **HALT** |
| Throttling / 5xx / network | **Retry** with backoff |
| Log collection issues | **HALT** → verify logtail config |

## Quality Gate (GCL)

This skill is part of the **Generator-Critic-Loop (GCL)** adversarial quality gate defined in [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). Every runtime execution of an `alicloud-sls-ops` operation MUST be wrapped in a GCL loop before the result is returned to the user.

> **Two references in this directory carry the GCL contract:**
>
> | File | Purpose |
> |---|---|
> | [`references/rubric.md`](references/rubric.md) | The 5 core + 3 Aliyun-specific rubric dimensions, per-op Safety sub-rules |
> | [`references/prompt-templates.md`](references/prompt-templates.md) | The Generator and Critic prompt templates |

### GCL Scope for SLS

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 2 rollout) |
| Default `max_iter` | **2** (inherited from `AGENTS.md` §12.8) |
| Operations covered | ALL operations in this SKILL.md |
| Operations most scrutinized | `DELETE /` (Delete Project), `DELETE /logstores/*` (Delete Logstore), `DELETE /index` (Delete Index) |

### Per-Op Safety Sub-Rules (Quick Reference)

For the **full** sub-rule table, see [`references/rubric.md`](../alicloud-sls-ops/references/rubric.md).

| Operation | Hard Safety condition (Score 1 requires) |
|---|---|
| `DELETE /` | Explicit user confirmation of `{{user.project}}`; verify project holds no active logstores |
| `DELETE /logstores/{logstore}` | Explicit user confirmation of `{{user.logstore}}`; check no active log shippers are streaming to it |
| `DELETE /logstores/{logstore}/index` | Explicit user confirmation; warn that log query/dashboards will be disabled |

### SLS-Specific Additions (beyond the 5 core dimensions)

| Dimension | Threshold | Why it matters for SLS |
|---|---|---|
| **SLS REST Headers Enforcement** | = 1 (**absolute**) | `--header "x-log-apiversion=0.9.0"` must be present |
| **Project/Endpoint Scope** | = 1 | `--project` parameter matches target resource scope |
| **Credential Hygiene** | = 1 (**absolute**) | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` must never appear in any trace field |

### Termination (inherited from `AGENTS.md` §12.5)

| Condition | Behavior |
|---|---|
| All dimensions ≥ threshold | **PASS** — return Generator's result |
| Safety = 0 **or** Credential Hygiene = 0 | **ABORT** — never return partial output |
| Other dimension < threshold AND iter < 2 | **RETRY** — inject Critic suggestions into next Generator prompt |
| Other dimension < threshold AND iter = 2 | **MAX_ITER** — return best-so-far + unresolved rubric items |

### Trace Persistence (mandatory)

Every GCL run MUST write `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json` with the schema defined in `AGENTS.md` §12.6. Apply the SLS-specific sanitization regex helpers to scrub `ALIBABA_CLOUD_ACCESS_KEY_SECRET` before persisting.

> `./audit-results/` is already in the repository `.gitignore`.

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting](references/troubleshooting.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)

## Operational Best Practices

- **Coverage:** Collect logs from all critical applications and infrastructure.
- **Indexing:** Create indexes for fields you frequently query.
- **Retention:** Set appropriate TTL based on compliance requirements.
- **Alerting:** Create alerts for critical log patterns (errors, exceptions).
- **Dashboards:** Build dashboards for operational visibility.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-05 | Initial SLS operations skill with dual-path CLI/SDK |

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

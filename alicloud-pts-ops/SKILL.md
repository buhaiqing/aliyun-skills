---
name: alicloud-pts-ops
description: >-
  Use when the user needs to create, configure, run, stop, analyze, or troubleshoot
  Alibaba Cloud Performance Testing Service (PTS, 性能测试) — PTS scene lifecycle,
  load configuration, debug runs, reports, JMeter scenes, and VPC binding for
  intranet targets. User mentions PTS, 性能测试, 压测, 压力测试, 全链路压测,
  JMeter压测, or describes scenarios (load test planning, RPS/concurrency tuning,
  scene debug failures, report analysis, production load test safety) even without
  naming the product directly. NOT for billing-only, RAM-only, SLB/ECS provisioning
  without PTS context, or products with their own ops skills.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary) with **aliyun-cli-pts** plugin
  (recommended), Go 1.21+ for JIT SDK fallback, valid API credentials, network
  access to Alibaba Cloud endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-16"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "PTS 2020-10-20 / https://help.aliyun.com/zh/pts/"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help pts` (API version 2020-10-20). Plugin
    `aliyun-cli-pts` exposes kebab-case commands (e.g. `list-pts-scene`,
    `create-pts-scene`, `start-pts-scene`). Install:
    `aliyun plugin install --names aliyun-cli-pts`.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
  gcl_classification: recommended
  gcl_max_iter: 3
  token_budget_estimate: "~3200 tokens (SKILL.md only)"
  references_index:
    - path: "references/core-concepts.md"
      load_condition: "架构、配额、场景状态机"
    - path: "references/cli-usage.md"
      load_condition: "CLI 命令速查"
    - path: "references/api-sdk-usage.md"
      load_condition: "SDK / OpenAPI 详情"
    - path: "references/troubleshooting.md"
      load_condition: "错误码与排障"
    - path: "references/monitoring.md"
      load_condition: "压测指标与报告"
    - path: "references/integration.md"
      load_condition: "JIT SDK 与跨 Skill 委托"
    - path: "references/well-architected-assessment.md"
      load_condition: "卓越架构五支柱评估"
    - path: "references/idempotency-checklist.md"
      load_condition: "幂等与重试"
    - path: "references/skillopt-integration.md"
    - path: "references/polling-patterns.md"
      load_condition: "SkillOpt 自修复"
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud PTS (Performance Testing) Operations Skill

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/pts-skillopt-wrapper.sh` for all PTS CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun pts` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |

## Common JSON Paths (Centralized)

```
# CreatePtsScene / SavePtsScene:     $.SceneId
# ListPtsScene:                      $.SceneViewList[].{SceneId,SceneName,Status,CreateTime}
# GetPtsScene:                       $.Scene.{SceneName,LoadConfig,RelationList}
# GetPtsSceneRunningStatus:          $.Status (WaitStart|Debugging|Running|Finished|...)
# StartPtsScene / StopPtsScene:      $.Success, $.RequestId
# GetPtsReportDetails:               $.Report.{SceneId,StartTime,EndTime,SuccessRate,AvgRt}
# ListPtsReports:                    $.ReportList[].{ReportId,SceneId,SceneName,Status}
# DeletePtsScene:                    $.Success
```

## Overview

Alibaba Cloud PTS (Performance Testing Service) provides API-driven load testing for HTTP/API, PTS-native scenes, and JMeter-based scenes. This skill is an **operational runbook** for agents: scene CRUD, debug runs, full load tests, report retrieval, and safe production guardrails.

**Execution paths:** Dual-path — PTS CLI plugin (`aliyun pts <kebab-command>`) as primary; JIT Go SDK (`github.com/alibabacloud-go/pts-20201020/v2`) as fallback for automation.

> **CLI plugin required:** Built-in `aliyun pts` lists the product but API help needs plugin `aliyun-cli-pts`. Run `aliyun plugin install --names aliyun-cli-pts` before first use.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT triggers; delegates VPC/SLB/ECS/RAM to sibling skills |
| 2 | **Structured I/O** | `{{env.*}}` / `{{user.*}}` / `{{output.*}}` with OpenAPI JSON paths |
| 3 | **Explicit Actionable Steps** | Pre-flight → Execute → Validate → Recover per operation |
| 4 | **Complete Failure Strategies** | ≥10 PTS error codes; HALT vs retry per category |
| 5 | **Absolute Single Responsibility** | PTS scenes, reports, JMeter envs only |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "PTS", "性能测试", "压测", "压力测试", "全链路压测", "JMeter压测"
- Task involves **PTS scene** lifecycle: create, save, modify, list, get, delete
- Task involves **running or stopping** load tests (`start-pts-scene`, `stop-pts-scene`, debug)
- Task involves **reports**: list reports, get report details, baseline comparison
- Task involves **JMeter scenes** on PTS (save/list/start/stop open JMeter scenes)
- User asks to tune **RPS, concurrency, agent count**, or max running time
- User asks to diagnose PTS failures: scene won't start, debug timeout, high error rate

### SHOULD NOT Use This Skill When

- Task is purely billing → `alicloud-billing-ops`
- Task is RAM/permission only → `alicloud-ram-ops`
- Task is VPC/subnet/SG creation without PTS context → `alicloud-vpc-ops`
- Task is SLB/ALB backend tuning without PTS → `alicloud-slb-ops` / `alicloud-alb-ops`
- Task is ECS capacity planning without load test → `alicloud-ecs-ops`
- User insists on **console-only** flows with no API → state limitation

### Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 写操作（启动压测、删除场景）前对抗性评审 |
| VPC / 安全组 | `alicloud-vpc-ops` | 内网压测目标需 VPC 打通时 |
| 被压服务排障 | 对应产品 skill | 压测通过后仍慢 → RDS/Redis/SLB 等 |
| CMS 告警 | `alicloud-cms-ops` | 非 PTS 内置指标的自定义告警 |

## Variable Convention (Agent-Readable)

| Var | Category | Items |
|-----|----------|-------|
| `{{env.*}}` | Environment (NEVER ask; HALT if unset) | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID` |
| `{{user.*}}` | User input (ask once, reuse) | `scene_name`, `scene_id`, `target_url`, `rps_begin`, `rps_limit`, `agent_count`, `max_running_time_min`, `test_mode`, `report_id`, `key_word`, `page_number`, `page_size`, `jmeter_scene_id`, `vpc_id`, `confirm_production_load_test` |
| `{{output.*}}` | API response | `scene_id`, `report_id`, `status`, `success_rate`, `avg_rt_ms`, `request_id` |

> **凭据安全（强制）：** 禁止输出 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`。验证用 `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"`。

## API and Response Conventions

- **OpenAPI version:** `2020-10-20`; endpoint `pts.{region}.aliyuncs.com`
- **Scene body:** `Scene` entity JSON — see [core-concepts.md](references/core-concepts.md)
- **Scene status:** `Draft` | `WaitStart` | `Debugging` | `Running` | `Finished` (verify in API response)
- **Pagination:** `ListPtsScene` — `PageNumber` (≥1), `PageSize` (10–1000)
- **CLI style:** Plugin uses **kebab-case** commands, not PascalCase (`list-pts-scene`, not `ListPtsScene`)

## Quick Start

### Prerequisites

- [ ] `aliyun` CLI installed
- [ ] `aliyun plugin install --names aliyun-cli-pts`
- [ ] Credentials configured
- [ ] Region set (e.g. `cn-hangzhou`)

### Verify Setup

```bash
aliyun pts list-pts-scene --page-number 1 --page-size 10 --region "${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"
```

### Next Steps

- [CLI Usage](references/cli-usage.md) — full command map
- [Core Concepts](references/core-concepts.md) — scene model, limits, safety
- [Troubleshooting](references/troubleshooting.md) — error codes

## Capabilities at a Glance

| Operation | CLI Command | Risk |
|-----------|-------------|------|
| List scenes | `list-pts-scene` | None |
| Get scene | `get-pts-scene` | None |
| Create scene | `create-pts-scene` | Low |
| Save/modify scene | `save-pts-scene` / `modify-pts-scene` | Medium |
| Debug scene | `start-debug-pts-scene` | Medium |
| **Start load test** | `start-pts-scene` | **High** (production impact) |
| Stop test | `stop-pts-scene` | Low |
| Delete scene | `delete-pts-scene` | **High** |
| List/get reports | `list-pts-reports` / `get-pts-report-details` | None |
| JMeter scene | `save-open-jmeter-scene` / `start-testing-jmeter-scene` | High |

---

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/pts-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun pts ...` 命令在执行时应替换为 `./scripts/pts-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun pts` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute → Validate → Recover**.

### Operation: List PTS Scenes

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI plugin | `aliyun pts version` | Exit 0 | Install `aliyun-cli-pts` |
| Credentials | env non-empty | AK + Secret set | HALT |
| Region | `--region` or env | Valid PTS region | HALT |

#### Execute — CLI

```bash
aliyun pts list-pts-scene \
  --page-number {{user.page_number|default:1}} \
  --page-size {{user.page_size|default:10}} \
  --region "${ALIBABA_CLOUD_REGION_ID}" \
  ${user.key_word:+--key-word "${user.key_word}"}
```

#### Validate

Parse `{{output.scene_id}}` from `$.SceneViewList[].SceneId`; present `SceneName`, `Status`, `CreateTime`.

---

### Operation: Create PTS Scene (Minimal HTTP)

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Target URL | user confirms | Non-prod or approved URL | HALT if production without approval |
| Scene name unique | `list-pts-scene --key-word` | No duplicate | Ask rename |
| RAM | `pts:CreatePtsScene` | Allowed | Delegate `alicloud-ram-ops` |

#### Execute — CLI

```bash
aliyun pts create-pts-scene --region "${ALIBABA_CLOUD_REGION_ID}" --scene "$(cat <<'EOF'
{
  "sceneName": "{{user.scene_name}}",
  "loadConfig": {
    "agentCount": {{user.agent_count|default:1}},
    "maxRunningTime": {{user.max_running_time_min|default:5}},
    "testMode": "{{user.test_mode|default:tps_mode}}",
    "configuration": {
      "allRpsBegin": {{user.rps_begin|default:10}},
      "allRpsLimit": {{user.rps_limit|default:100}}
    }
  },
  "relationList": [{
    "relationName": "链路1",
    "apiList": [{
      "apiName": "API-1",
      "method": "GET",
      "url": "{{user.target_url}}",
      "headerList": [],
      "checkPointList": []
    }]
  }]
}
EOF
)"
```

Full `Scene` schema: [api-sdk-usage.md](references/api-sdk-usage.md).

#### Validate

1. Parse `{{output.scene_id}}` from `$.SceneId`
2. `get-pts-scene --scene-id {{output.scene_id}}` — config matches intent

#### Failure Recovery

| Error | Action |
|-------|--------|
| `CreateSceneFail` | Fix Scene JSON structure |
| `InvalidParameter` | Verify URL, RPS ranges |
| `Forbidden` | RAM policy `pts:*` |
| `Throttling.User` | Backoff 3× |

---

### Operation: Debug PTS Scene

#### Pre-flight

| Check | Expected | On Failure |
|-------|----------|------------|
| Scene exists | `get-pts-scene` returns data | HALT |
| Status | Not `Running` full test | `stop-pts-scene` first if needed |

#### Execute

```bash
aliyun pts start-debug-pts-scene --scene-id "{{user.scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

#### Validate

Poll `get-pts-scene-running-status` until debug completes or timeout (interval 10s, max 300s).

```bash
aliyun pts get-pts-debug-sample-logs --scene-id "{{user.scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

---

### Operation: Start PTS Load Test

#### Safety Gate (MANDATORY)

- **MUST** confirm target environment is **non-production** OR user explicitly sets `{{user.confirm_production_load_test}}=yes`
- **MUST** show planned `rps_limit`, `agent_count`, `max_running_time_min`
- **MUST** warn: load test may degrade target service availability
- **MUST NOT** proceed without clear assent for production targets

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Scene ready | `get-pts-scene` | Valid loadConfig | Fix scene |
| No concurrent run | `get-pts-scene-running-status` | Not `Running` | `stop-pts-scene` or wait |
| Quota | account PTS quota | Within limit | HALT |

#### Execute

```bash
aliyun pts start-pts-scene --scene-id "{{user.scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

#### Validate

```bash
# 通用轮询，参数见 [references/polling-patterns.md](references/polling-patterns.md)（60×30s → Finished/WaitStart）
```

Then fetch report via `get-pts-reports-by-scene-id` or `list-pts-reports`.

#### Failure Recovery

| Error | Action |
|-------|--------|
| Scene already running | `stop-pts-scene` then retry |
| Agent quota exceeded | Reduce `agentCount` or request quota |
| Target unreachable | Check VPC binding — [integration.md](references/integration.md) |

---

### Operation: Stop PTS Scene

```bash
aliyun pts stop-pts-scene --scene-id "{{user.scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

Validate: `get-pts-scene-running-status` no longer `Running`.

---

### Operation: Delete PTS Scene

#### Safety Gate

- **MUST** obtain explicit confirmation with `{{user.scene_id}}` and scene name
- **MUST** ensure scene is not `Running` or `Debugging`

#### Execute

```bash
aliyun pts stop-pts-scene --scene-id "{{user.scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}" 2>/dev/null || true
aliyun pts delete-pts-scene --scene-id "{{user.scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

#### Validate

`list-pts-scene --key-word "{{user.scene_id}}"` returns empty.

---

### Operation: Get Report Details

```bash
aliyun pts list-pts-reports --region "${ALIBABA_CLOUD_REGION_ID}" \
  --page-number 1 --page-size 10

aliyun pts get-pts-report-details --report-id "{{user.report_id}}" \
  --region "${ALIBABA_CLOUD_REGION_ID}"
```

Present: success rate, avg RT, TPS, error breakdown — paths in [monitoring.md](references/monitoring.md).

---

## Reference Directory

| File | Purpose |
|------|---------|
| [core-concepts.md](references/core-concepts.md) | Architecture, Scene model, quotas |
| [cli-usage.md](references/cli-usage.md) | Full CLI command map |
| [api-sdk-usage.md](references/api-sdk-usage.md) | SDK operations map |
| [troubleshooting.md](references/troubleshooting.md) | Error codes, diagnostics |
| [monitoring.md](references/monitoring.md) | Reports, metrics, baselines |
| [integration.md](references/integration.md) | JIT SDK, VPC, cross-skill |
| [well-architected-assessment.md](references/well-architected-assessment.md) | Five pillars |
| [idempotency-checklist.md](references/idempotency-checklist.md) | Retry/idempotency |
| [skillopt-integration.md](references/skillopt-integration.md) | SkillOpt usage |
| [polling-patterns.md](references/polling-patterns.md) | 场景状态轮询模板 |
| [rubric.md](references/rubric.md) | GCL rubric |
| [prompt-templates.md](references/prompt-templates.md) | GCL prompts |

## Quality Gate (GCL)

| Aspect | Setting |
|--------|---------|
| Required? | **Recommended** (`max_iter=3`) |
| Most-scrutinized | `start-pts-scene` (production impact), `delete-pts-scene`, `start-testing-jmeter-scene` |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-16 | Initial PTS skill: dual-path CLI plugin + SDK, SkillOpt, GCL recommended |

## See Also

- [alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) — meta-skill rules
- [execution-environment.md](../alicloud-skill-generator/references/execution-environment.md) — CLI setup

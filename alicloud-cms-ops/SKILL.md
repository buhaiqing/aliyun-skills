---
name: alicloud-cms-ops
description: >-
  Use this skill when users need Alibaba Cloud CloudMonitor/CMS monitoring,
  alarms, metrics, dashboards, health inspection, anomaly detection, alarm
  storm handling, or cross-resource correlation. Trigger on CloudMonitor, CMS,
  云监控, 监控, 告警, 指标, 监控大盘, 性能巡检, 主动巡检, 异常检测,
  vague health questions, and metric analysis. Covers `aliyun cms`, `aliyun
  cms2`, and JIT Go SDK fallback for documented CloudMonitor APIs.
license: MIT
compatibility: >-
  Alibaba Cloud CLI (`aliyun` >=3.3.15 with `cms`/`cms2` plugins), Go 1.21+
  for JIT SDK fallback, valid Alibaba Cloud credentials, network access to
  Alibaba Cloud endpoints.
metadata:
  author: alicloud
  version: "2.4.4"
  last_updated: "2026-06-16"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  api_profile: "Cms/2019-01-01 (RPC), Cms/2024-03-30 (ROA)"
  cli_applicability: dual-path
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud CloudMonitor (CMS) Operations Skill

<!-- markdownlint-disable MD013 -->

Compact operational entrypoint. Keep only routing, guards, and decision logic
here; load command examples, SDK code, installation diagnosis, and advanced
analytics from `references/` on demand.

## Scope

**Use for:** metric/latest-value queries, metric metadata, alarm rule CRUD,
contact groups, monitor groups, custom/event monitoring, dashboards, anomaly
analysis, alarm storm handling, proactive inspections, CloudMonitor 2.0,
and automated self-repair and dynamic configuration optimization via Runtime Harness
(formerly SkillOpt; not affiliated with Microsoft SkillOpt).

**Do not use for:** creating/modifying monitored resources themselves (delegate
to product skills), pure billing (`alicloud-billing-ops`), pure RAM policy design
(`alicloud-ram-ops`), or undocumented CMS APIs.

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the Runtime Harness wrapper `./scripts/cms-harness-wrapper.sh` with `--skillopt-enable` for **all** `aliyun cms` / `aliyun cms2` calls (read-only and mutating) to enable automated self-repair, dynamic optimization, and Langfuse tracing. The legacy `./scripts/cms-skillopt-wrapper.sh` shim delegates to the harness wrapper. Fallback to native `aliyun cms` is permitted only when the wrapper file is confirmed missing or `harness-lib.sh` cannot be sourced. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md), [Shim](../../alicloud-skill-generator/scripts/skillopt-shim/SHIM-README.md) |
| Ops report | When user asks for "运营摘要", "Runtime Harness 报告", "SkillOpt 报告", "健康状态", or "运行统计", use `./scripts/cms-harness-wrapper.sh report --skillopt-report` to generate Markdown operations summary without calling aliyun CLI. | [SkillOpt](references/skillopt-integration.md#operations-summary-report) |
| SDK path | Use JIT Go SDK only when CLI lacks request shape or plugin is unavailable | [SDK](references/api-sdk-usage.md), [Integration](references/integration.md) |
| CLI verification | Run `<action> --help` before first use; auto-install missing `cms`/`cms2` plugins, then verify | [Plugin setup](references/cli-usage.md#cli-plugins-and-ai-mode), [Diagnosis](references/cli-install-diagnosis.md) |
| Credentials | Read `{{env.*}}` only from environment; never ask user to paste or print secrets | [Integration](references/integration.md) |
| Metadata | Query namespaces/metrics dynamically with `DescribeProjectMeta` / `DescribeMetricMetaList` | [Core concepts](references/core-concepts.md) |

Required env vars: `ALIBABA_CLOUD_ACCESS_KEY_ID`,
`ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID`.

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 Runtime Harness wrapper `./scripts/cms-harness-wrapper.sh` 运行（旧的 `./scripts/cms-skillopt-wrapper.sh` 仍可作为 shim 使用）。
> 以下所有代码块中的 `aliyun cms ...` 命令在执行时应替换为 `./scripts/cms-harness-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `harness-lib.sh` 缺失时，才退回到原生 `aliyun cms` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Common Pre-flight

| Check | Method | Expected | On failure |
| --- | --- | --- | --- |
| CLI | `aliyun version` | >= 3.3.15 | diagnose/install or SDK fallback |
| Plugins | `aliyun cms --help`; `aliyun cms2 --help` when needed | help output | install/update plugin, verify again |
| Credentials | env vars above | non-empty | HALT; user configures env/profile |
| Permission | `aliyun cms DescribeProjectMeta --RegionId {{user.region}}` | success | diagnose RAM/AK/network |
| Resource | delegate by namespace/product | exists in region | HALT before alarm writes |
| JSON args | `jq . <<<'{{json}}'` | valid JSON | fix `Dimensions`, contact groups, actions |

## Variable Convention

| Placeholder | Meaning |
| --- | --- |
| `{{user.region}}` | Target region; default from env only if user did not specify |
| `{{user.namespace}}` / `{{user.metric_name}}` | CMS namespace/metric |
| `{{user.instance_id}}` | Monitored resource ID |
| `{{user.alarm_name}}` / `{{output.alarm_id}}` | Alarm name / parsed alarm ID |
| `{{user.contact_group}}` | CMS contact group |
| `{{user.group_id}}` / `{{user.group_name}}` | Monitor group ID/name |
| `{{output.metric_data}}` | Parsed metric datapoints |

## Operation Map

| Intent | Primary action | Critical guard | Load |
| --- | --- | --- | --- |
| Query time-series metric | `DescribeMetricList` | namespace/metric/time range valid | [CLI examples](references/cli-usage.md#examples), [SDK](references/api-sdk-usage.md#describemetriclist) |
| Query latest/top values | `DescribeMetricLast` / `DescribeMetricTop` | dimensions valid | [CLI](references/cli-usage.md) |
| List products/metrics | `DescribeProjectMeta` / `DescribeMetricMetaList` | paginate/filter | [Core concepts](references/core-concepts.md) |
| Create/update alarm | `PutMetricAlarm` / `PutResourceMetricRule` | resource + contact group exist; confirm impact | [CLI](references/cli-usage.md#example-2-create-cpu-alarm-rule) |
| List/export alarms | `DescribeMetricAlarmList` | paginate; save JSON before mutation | [CLI pagination](references/cli-usage.md#pagination) |
| Delete/disable/silence alarm | `DeleteMetricAlarm`, blacklist APIs | explicit confirmation + rollback | [GCL](references/rubric.md), [CLI](references/cli-usage.md) |
| Monitor groups/contacts | group/contact APIs | delete requires confirmation | [CLI](references/cli-usage.md) |
| Custom/event monitoring | `PutCustomMetric`, `PutEventRule` | JSON/event pattern valid | [CLI](references/cli-usage.md) |
| AIOps inspection/storm RCA | multi-metric queries + correlation | verify resources via product skills | [AIOps](references/aiops-inspection.md), [Troubleshooting](references/troubleshooting.md) |
| APM/RUM/SecOps/FinOps | CMS2 or SDK APIs | explicit need only | [Observability](references/observability.md), [SecOps](references/secops-monitoring.md), [Advanced](#advanced-analytics) |
| Self-repair & dynamic optimization | `SkillOpt` | enable/disable via flags | [SkillOpt](references/skillopt-integration.md) |

## Safety Gates

| Operation type | Requirement |
| --- | --- |
| Read/query | run common pre-flight; paginate; limit time range |
| Create non-destructive | show material config; confirm if user impact is possible |
| Update/patch/delete/disable/silence | present exact command, risk, backup JSON, rollback; wait for explicit confirmation |
| Dynamic discovery | HITL if 0 or >100 instances, first filter pattern, production critical resources, or permanent silence |
| Credentials/contact data | mask secrets/contact details; never commit `.env` |

Run GCL review for high-risk writes when time allows; use
[`references/rubric.md`](references/rubric.md) and
[`references/prompt-templates.md`](references/prompt-templates.md).

## Error Handling

| Error | Action |
| --- | --- |
| `Throttling.User` / flow control | **MANDATORY**: Re-run the command via `./scripts/cms-harness-wrapper.sh --skillopt-enable` to automatically apply backoff (1s/2s/4s) and retry up to 6 times. |
| `InvalidParameter` / `InvalidJSON` | **MANDATORY**: Re-run the command via `./scripts/cms-harness-wrapper.sh --skillopt-enable` to automatically parse, compact, and repair JSON dimensions. |
| empty datapoints | Check region/resource state; run via `./scripts/cms-harness-wrapper.sh --skillopt-enable` to verify resource existence. |
| `Forbidden` / `NoPermission` | Run via `./scripts/cms-harness-wrapper.sh --skillopt-enable` to output least-privilege, action-specific RAM policy suggestions. |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | HALT; user fixes/rotates AK env/profile |
| `ResourceNotFound` | Run via `./scripts/cms-harness-wrapper.sh --skillopt-enable` to verify resource existence via product skill (e.g. ECS) in the same region. |
| `QuotaExceeded` | List quota/stale rules; user decides cleanup or quota increase |
| CLI/plugin/network timeout | Run [diagnosis](references/cli-install-diagnosis.md); degrade to SDK only if safe |

Full RCA/self-healing: [Troubleshooting](references/troubleshooting.md),
[Knowledge Base](references/knowledge-base.md),
[SkillOpt Integration](references/skillopt-integration.md).

## Module Routing

| User intent | Load |
| --- | --- |
| CLI syntax, examples, plugin setup, AI-Mode, pagination, JSON | [CLI](references/cli-usage.md) |
| SDK fallback/request-response | [SDK](references/api-sdk-usage.md) |
| installation, credentials, RAM, delegation | [Integration](references/integration.md) |
| failures, empty data, alarm not firing | [Troubleshooting](references/troubleshooting.md) |
| monitoring design, dashboard, alarms | [Monitoring](references/monitoring.md) |
| AIOps / storm handling | [AIOps Inspection](references/aiops-inspection.md) |
| APM / RUM / AI observability | [Observability](references/observability.md) |
| SecOps | [SecOps](references/secops-monitoring.md) |
| GCL scoring/prompts | [Rubric](references/rubric.md), [Prompt Templates](references/prompt-templates.md) |
| SkillOpt integration | [SkillOpt](references/skillopt-integration.md) |
| Prompt snippets (historical reference) | [Prompts](references/prompts.md) |

## Advanced Analytics

Load only when explicitly requested:

| Scenario | Document |
| --- | --- |
| Performance prediction, capacity planning | [AIOps Prediction](references/advanced/aiops-prediction.md) |
| Cost analysis, idle resources, optimization | [FinOps Analysis](references/advanced/finops-analysis.md) |
| Self-repair & dual optimization (static pre-execution + dynamic runtime) | [SkillOpt Integration](references/skillopt-integration.md) |

## Well-Architected Assessment

| Pillar | Guidance |
| --- | --- |
| Security | Least privilege; `{{env.*}}`; mask secrets/contact details |
| Stability | `EvaluationCount >= 3` for prod; use maintenance windows; verify rollback |
| Cost | Prefer `Period=300`; watch metric-query quota; reduce SMS noise |
| Efficiency | Use templates/groups; query metadata dynamically; avoid duplicate alarms |
| Performance | Use latest-value APIs for point-in-time checks; batch/paginate lists |

Full assessment: [well-architected-assessment.md](references/well-architected-assessment.md).

## Reference Directory

Core: [Concepts](references/core-concepts.md), [CLI](references/cli-usage.md),
[SDK](references/api-sdk-usage.md), [Integration](references/integration.md),
[Troubleshooting](references/troubleshooting.md), [Monitoring](references/monitoring.md),
[Observability](references/observability.md), [SecOps](references/secops-monitoring.md),
[Rubric](references/rubric.md), [Prompt Templates](references/prompt-templates.md).

## Quality Gate (GCL)

Recommended Phase 5 gate (`max_iter=3`). Scrutinize `DeleteMetricAlarm` and
`DeleteMonitorGroup`: backup current JSON, confirm monitoring coverage impact,
define rollback, then validate post-state.

## Changelog

| Version | Date | Changes |
| --- | --- | --- |
| 2.4.4 | 2026-06-16 | Added prefix-based routing for cross-product ResourceNotFound auto-repair (supporting ECS, RDS, Redis, SLB, MongoDB, PolarDB, EIP, VPC); refactored all platform-specific `date` commands in guide docs to be 100% cross-platform compatible; expanded backward compatibility test suite to 42 tests. |
| 2.4.3 | 2026-06-16 | Guided agent execution flow to prefer SkillOpt wrapper and alias paths; updated error handling actions to enforce self-repair routing. |
| 2.4.2 | 2026-06-16 | SkillOpt hardening: `.runtime/` paths, repair stdout passthrough, legacy script delegates to wrapper, doc accuracy fixes |
| 2.4.1 | 2026-06-16 | SkillOpt self-repair wrapper library, dynamic optimization, backward-compat tests |
| 2.4.0 | 2026-06-16 | Added Runtime Harness (SkillOpt) integration documentation and sample scripts |
| 2.3.3 | 2026-06-15 | Further token-efficiency compaction; moved plugin/AI-mode command details to `references/cli-usage.md` |
| 2.3.2 | 2026-06-15 | Integrated automated cms/cms2 plugin installation and configuration workflow |
| 2.3.1 | 2026-06-15 | Token-efficiency compaction with lazy-loaded references |

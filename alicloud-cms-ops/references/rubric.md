---
name: alicloud-cms-ops-rubric
description: >-
  GCL rubric for `alicloud-cms-ops` (Cloud Monitor — alarm rule,
  monitor group lifecycle + GCL Phase 3-B phantom-op alarm integration).
  Enhanced from lean recommended to full Phase 3-B alarm-entry role.
license: MIT
metadata:
  skill: alicloud-cms-ops
  api: Cms 2019-01-01
  cli_applicability: dual-path
  gcl_classification: recommended
  rubric_version: "1.5.0"
  rubric_phase: "3-H (Dynamic Instance-Level Alert Management + HITL)"
  last_updated: "2026-06-05"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
    - cli-usage.md
    - ../../../scripts/gcl_actiontrail_crosscheck.py
    - ../../../scripts/README.md
---

# CMS GCL Rubric (Phase 3-B — Phantom Alarm Integration)

> **This skill serves two roles:**
> 1. **Standard destructive-op GCL** (`recommended`, `max_iter=3`):
>    `DeleteMetricAlarm`, `DeleteMonitorGroup` — per Phase 5 rollout.
> 2. **Phase 3-B Phantom Alarm Entry Point**: `PutMetricAlarm` rules that
>    monitor `crosscheck-report-*.json` phantom-op rate. This rubric adds
>    the alarm-creation sub-rules for this second role.

> **Hard rules:** Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
> Phantom alarms monitor `summary.phantoms` from the crosscheck report;
> threshold = 0 in `--strict` mode (any phantom is a finding).

## 1. Standard GCL — Per-Op Safety Sub-Rules

| Operation | Sub-rule (Score 1) |
|---|---|
| `DeleteMetricAlarm` | (a) user confirmation naming `{{user.alarm_rule_name}}`; (b) **backup the alarm rule JSON** via `DescribeMetricAlarmList` in the same flow; (c) warn monitoring coverage removed |
| `DeleteMonitorGroup` | (a) user confirmation naming `{{user.group_name}}`; (b) warn group alarms + contacts detached |
| `PutMetricAlarm` (create) | (a) user confirmation; (b) `Namespace` + `MetricName` valid per `DescribeProjectMeta`; (c) `ContactGroups` verified via `DescribeContactGroupList` |
| `PutMetricAlarm` (update existing) | (a) user confirmation; (b) **backup current alarm rule** via `DescribeMetricAlarmList` before overwriting; (c) warn that threshold change may cause notification storm |

## 2. Phase 3-B — Phantom Alarm Schema

This section defines the **input schema** for creating CMS alarms from
`crosscheck-report-*.json` (produced by `gcl_actiontrail_crosscheck.py`).

### 2.1 Crosscheck Report JSON Paths

| JSON Path | Type | Meaning | CMS Metric Name |
|---|---|---|---|
| `summary.phantoms` | int | PHANTOM_PASS + PHANTOM_FAIL count; should be **0** in healthy state | `gcl_summary_phantoms` |
| `summary.by_finding_type.PHANTOM_PASS` | int | Count of "local PASS, no cloud event" findings | `gcl_phantom_pass` |
| `summary.by_finding_type.PHANTOM_FAIL` | int | Count of "local FAIL, cloud event exists" findings | `gcl_phantom_fail` |
| `summary.by_finding_type.RESOURCE_MISMATCH` | int | ResourceName mismatch count (medium severity) | `gcl_resource_mismatch` |
| `summary.by_finding_type.TIMING_ANOMALY` | int | Timing anomaly count (low severity) | `gcl_timing_anomaly` |
| `summary.api_errors` | int | LookupErrors failures (infra issue, NOT phantom) | `gcl_api_errors` |
| `summary.by_skill.*.with_findings` | dict | Per-skill finding count | `gcl_skill_findings` |

### 2.2 Alarm Thresholds

| Threshold | Severity | CMS Alarm Rule Template |
|---|---|---|
| `PHANTOM_PASS > 0` (strict) | P1 — critical | `Statistics=Average Period=300 EvaluationCount=1 Threshold=0 ComparisonOperator=><` — triggers on ANY phantom pass |
| `PHANTOM_PASS > N` (lenient) | P2 — high | `Threshold=N ComparisonOperator=><` — triggers when phantom pass rate exceeds expected baseline |
| `PHANTOM_FAIL > 0` | P1 — critical | Same as phantom pass; safety gate bypass = always page on-call |
| `api_errors > 5` | P2 — high | ActionTrail infra issue — page SRE |
| `timing_anomaly > 10` | P3 — warning | Clock skew / replay — log and review weekly |

### 2.3 Alarm Action Template

```bash
aliyun cms PutMetricAlarm \
  --AlarmName "GCL-Phantom-${ENVIRONMENT}-Pass" \
  --Namespace "acs_custom_<account_id>" \
  --MetricName "gcl_phantom_pass" \
  --Dimensions "" \
  --Statistics "Average" \
  --ComparisonOperator ">" \
  --Threshold 0 \
  --Period 300 \
  --EvaluationCount 1 \
  --ContactGroups '["gcl-oncall"]' \
  --Webhook "https://api.pagerduty.com/v2/..." \
  --EffectiveInterval "00:00-23:59"
```

**Mandatory pre-requisites before creating:**
1. `DescribeContactGroupList` → verify `gcl-oncall` contact group exists.
2. `DescribeMetricMetaList` → verify `gcl_phantom_pass` metric namespace is registered (or use `acs_custom`).
3. `DescribeMetricAlarmList` → check existing alarm with same name; if exists, either skip or update.

## 3. Detection Regex

| Regex | Risk | Examples |
|---|---|---|
| `DeleteMetricAlarm\b` | DESTRUCTIVE-MASS | `aliyun cms DeleteMetricAlarm` |
| `DeleteMonitorGroup\b` | DESTRUCTIVE-LIMITED | `aliyun cms DeleteMonitorGroup` |
| `PutMetricAlarm\b` | WRITE-KEY | `aliyun cms PutMetricAlarm` |

## 4. Worked Example — Create Phantom Alarm

```json
{
  "iter": 1,
  "generator": {
    "command": "aliyun cms PutMetricAlarm --AlarmName GCL-Phantom-Pass --Namespace acs_custom_123456 --MetricName gcl_phantom_pass ...",
    "exit_code": 0
  },
  "preflight": {
    "user_confirmation": "User confirmed: create GCL phantom alarm for environment=production.",
    "contact_group_check": "DescribeContactGroupList → gcl-oncall exists",
    "alarm_name_check": "DescribeMetricAlarmList → GCL-Phantom-Pass does not exist (fresh create)"
  },
  "critic": {
    "scores": { "safety": 1.0, "correctness": 1.0, "idempotency": 1.0 },
    "suggestions": []
  },
  "decision": "PASS"
}
```

## 5. Worked Example — Phantom Found (SAFETY_FAIL)

```json
{
  "iter": 1,
  "generator": { "command": "aliyun cms DeleteMetricAlarm --AlarmName GCL-Phantom-Pass" },
  "preflight": {
    "user_confirmation": "User confirmed: delete GCL phantom alarm.",
    "backup": "DescribeMetricAlarmList → rule JSON backed up"
  },
  "critic": { "scores": { "safety": 0.0, "correctness": 1.0 },
    "suggestions": ["BLOCKED: Phantom alarm is a critical P1 monitoring rule. Confirm this is not a production environment and the phantom issue is resolved before deleting."],
    "blocking": true },
  "decision": "SAFETY_FAIL"
}
```

## 6. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.5.0 | 2026-06-05 | **Phase 3-H — Dynamic Instance-Level Alert Management + HITL Decision Framework**: §3 HITL Scoring (confidence matrix + threshold rules); §7 HITL Workflow (5-option prompt); §8 Auto-Processing Criteria; Updated §1 with new operations (CreateMetricRuleBlackList, PutResourceMetricRule, PutEventRule); rubric_phase updated to 3-H |
| 1.0.0 | 2026-06-04 | CMS GCL rubric — Enhanced from Phase 5 lean to Phase 3-B full. New: §2 (Phantom Alarm Schema with JSON path table + alarm thresholds + template CLI); §4-5 (worked examples for alarm create + phantom-found SAFETY_FAIL). Renamed: §1 now covers both standard CMS ops and phantom alarm create.

## 3. Phase 3-H — HITL Confidence Scoring Framework

This section defines the **confidence scoring algorithm** for deciding **Auto-Processing** vs **HITL (Human-in-the-Loop)** when managing instance-level alerts dynamically.

### 3.1 Confidence Score Calculation

```
confidence = (
  # 1. Instance Count Range (max 25)
  instance_count_in_range(10-50) ? 25 : 
  instance_count_in_range(5-10, 50-100) ? 15 : 0 +
  
  # 2. Filter Explicitness (max 20)
  filter_has_explicit_tags ? 20 : 
  filter_has_status_only ? 10 : 0 +
  
  # 3. Environment Criticality (max 20)
  non_critical_env ? 20 : 
  staging_env ? 10 : 0 +
  
  # 4. Operation Standardness (max 15)
  standard_operation ? 15 : 
  complex_operation ? 5 : 0 +
  
  # 5. Rollback Readiness (max 10)
  rollback_available ? 10 : 0 +
  
  # 6. Historical Success Rate (max 10)
  high_success_rate ? 10 : 
  no_history ? 5 : 0
)
```

### 3.2 Confidence Threshold Matrix

| Confidence | Decision | HITL Required? | Critic Action |
|------------|----------|----------------|---------------|
| **90-100** | AUTO-PROCESS | No | Monitor only |
| **80-89** | AUTO-PROCESS (with logging) | No | Log for audit |
| **60-79** | **HITL_RECOMMENDED** | Yes | Suggest user review |
| **40-59** | **HITL_REQUIRED** | **Yes** | Block until confirmation |
| **0-39** | **HITL_MANDATORY** | **Yes + Warning** | Strong warning + education |

### 3.3 HITL Trigger Conditions (Hard Rules)

**🔴 HITL MANDATORY — Auto-processing BLOCKED:**

| Condition | Reason | Agent Action |
|-----------|--------|--------------|
| `instance_count == 0` | No instances match filter | Pause + diagnose filter |
| `instance_count > 100` | Too many instances for safety | Require batch processing |
| `env == "production" AND critical_tier` | Critical prod environment | Always HITL |
| `match_rate > 80%` of total instances | Risk of mass operation | Require explicit confirmation |
| `operation == "permanent_silence"` | Irreversible action | Double-confirm |
| `filter_complexity == "composite"` | Complex boolean logic | Explain before execute |
| `first_execution_of_filter` | No historical validation | Verify filter correctness |

**🟠 HITL RECOMMENDED — User decides:**

| Condition | Reason | Agent Action |
|-----------|--------|--------------|
| `instance_count > 50` | Large scope | Suggest review |
| `env == "production"` | Prod environment | Warn + suggest HITL |
| `match_rate > 50%` | Affects many instances | Confirm scope |
| `filter_has_wildcards` | Broad matching | Verify intent |
| `confidence_score 60-79` | Uncertain confidence | Recommend review |

### 3.4 Scoring Dimension Details

| Dimension | Points | Criteria | Example |
|-----------|--------|----------|---------|
| **Instance Count** | 25 | 10 ≤ count ≤ 50 | `20 instances` → 25 pts |
| | 15 | 5 ≤ count < 10 OR 50 < count ≤ 100 | `8 instances` → 15 pts |
| | 0 | count < 5 OR count > 100 | `3 instances` → 0 pts |
| **Filter Explicit** | 20 | Has specific tags + status | `tag:env=prod,status=Running` → 20 pts |
| | 10 | Status only or broad tags | `status=Running` → 10 pts |
| | 0 | No filter or wildcards | `*` or no filter → 0 pts |
| **Non-Critical Env** | 20 | dev/test/staging | `env=staging` → 20 pts |
| | 10 | Pre-prod/UAT | `env=uat` → 10 pts |
| | 0 | Production | `env=production` → 0 pts |
| **Standard Operation** | 15 | threshold_adjust, notification_change | Adjust threshold → 15 pts |
| | 5 | Complex composite rules | Multi-metric expression → 5 pts |
| **Rollback Ready** | 10 | Has corresponding delete/disable | Blacklist has Delete → 10 pts |
| | 0 | No rollback path | Permanent change → 0 pts |
| **Historical Success** | 10 | > 90% success rate with similar filters | Used 5x, all success → 10 pts |
| | 5 | No history or < 50% success | First time → 5 pts |
| | 0 | < 50% success rate | Failed before → 0 pts |

## 4. Phase 3-H — HITL Workflow Specification

### 4.1 5-Option HITL Prompt

When HITL is triggered, present user with:

```
[HITL] Instance-Level Alert Operation Requires Confirmation

Operation: {{operation_name}}
Target: {{product}} instances matching {{filter_description}}
Matched Instances: {{instance_count}} ({{instance_sample}})
Environment: {{environment}}
Confidence Score: {{confidence}}/100 ({{confidence_level}})

⚠️  This operation affects {{instance_count}} instances.

Choose an action:
1. [CONFIRM] Execute as specified
2. [MODIFY] Adjust filter/scope before execution
3. [VIEW] Show all matched instances (full list)
4. [CANCEL] Abort operation
5. [SCHEDULE] Execute during maintenance window

Your choice (1-5): __
```

### 4.2 Option Handling

| Choice | Action | Next Step |
|--------|--------|-----------|
| **1. CONFIRM** | Proceed with execution | Run GCL → Execute → Validate |
| **2. MODIFY** | Enter modify mode | Show filter editor → Recalculate confidence → Re-prompt |
| **3. VIEW** | Display full instance list | Show `DescribeInstances` results → Re-prompt |
| **4. CANCEL** | Abort operation | Log cancellation reason → Exit gracefully |
| **5. SCHEDULE** | Defer to maintenance window | Create scheduled task → Confirm schedule → Exit |

### 4.3 Modify Mode Flow

```
User selects [MODIFY]
  ↓
Show current filter: {{current_filter_json}}
  ↓
Prompt: "Enter new filter criteria (JSON) or type HELP for examples"
  ↓
Parse new filter → Re-run instance discovery
  ↓
Recalculate confidence score
  ↓
If confidence ≥ 80: "Auto-processing now possible. Proceed?"
If confidence < 80: Re-prompt with updated info
```

## 5. Phase 3-H — Updated Operation Sub-Rules

### 5.1 New Operations (Phase 3-H)

| Operation | Sub-rule (Score 1) | HITL Trigger |
|-----------|-------------------|--------------|
| `CreateMetricRuleBlackList` | (a) **confidence scoring** ≥ 80; (b) **instance validation** via delegated skill query; (c) **time range** explicit (start/end); (d) **non-permanent** preferred | instance_count > 100 OR permanent silence |
| `PutResourceMetricRule` | (a) **confidence scoring** ≥ 80; (b) **Resources** validated (instance IDs exist); (c) **threshold logic** reasonable (not too aggressive); (d) **contact groups** verified | instance_count > 100 OR composite expression |
| `PutEventRule` | (a) **confidence scoring** ≥ 80; (b) **event pattern** validated against product events; (c) **target** verified (MNS topic/FC function exists) | event_type == "InstanceDeletion" OR "Failover" |
| `PutMetricRuleTargets` | (a) **confidence scoring** ≥ 80; (b) **contact groups** exist; (c) **webhook URL** valid format | webhook points to external domain |

### 5.2 Cross-Skill Delegation Validation

| Step | Validation | Fail Action |
|------|------------|-------------|
| 1. Delegate to product skill | Return `query_command`, `id_field`, `resource_key` | HITL — manual filter specification |
| 2. Query instances | Execute returned command with filters | Diagnose filter (see troubleshooting.md) |
| 3. Validate count | Check `instance_count` against threshold | If 0 → diagnose; If > 100 → HITL |
| 4. Build Resources JSON | Transform IDs to CMS format | Auto-transform per skill spec |
| 5. Verify existence | Critic re-queries to confirm | If mismatch → ABORT + investigate |

## 6. Worked Example — HITL Decision Flow

### Example 1: Auto-Processing (High Confidence)

```json
{
  "iter": 1,
  "request": {
    "operation": "CreateMetricRuleBlackList",
    "product": "ecs",
    "filter": {"tag:env": "staging", "status": "Running"},
    "scope": "CPUUtilization > 80%"
  },
  "delegation": {
    "skill": "alicloud-ecs-ops",
    "query": "DescribeInstances",
    "result": {
      "instance_count": 25,
      "instances": ["i-xxx1", "i-xxx2", "..."]
    }
  },
  "confidence_calculation": {
    "instance_count": 25,
    "score_instance_range": 25,
    "filter_explicit": true,
    "score_filter": 20,
    "environment": "staging",
    "score_env": 20,
    "operation": "standard",
    "score_op": 15,
    "rollback_available": true,
    "score_rollback": 10,
    "history": "high_success",
    "score_history": 10,
    "total_confidence": 100
  },
  "decision": "AUTO-PROCESS",
  "generator": {
    "command": "aliyun cms CreateMetricRuleBlackList --RegionId cn-hangzhou ...",
    "exit_code": 0
  },
  "critic": {
    "scores": {"safety": 1.0, "correctness": 1.0, "idempotency": 1.0, "confidence": 1.0},
    "decision": "PASS"
  }
}
```

### Example 2: HITL Required (Low Confidence)

```json
{
  "iter": 1,
  "request": {
    "operation": "PutResourceMetricRule",
    "product": "ecs",
    "filter": {"status": "Running"},
    "scope": "all_running_instances"
  },
  "delegation": {
    "skill": "alicloud-ecs-ops",
    "query": "DescribeInstances",
    "result": {
      "instance_count": 0,
      "instances": [],
      "total_instances_in_account": 150
    }
  },
  "confidence_calculation": {
    "instance_count": 0,
    "score_instance_range": 0,
    "filter_explicit": false,
    "score_filter": 0,
    "environment": "unknown",
    "score_env": 0,
    "operation": "standard",
    "score_op": 15,
    "rollback_available": true,
    "score_rollback": 10,
    "history": "none",
    "score_history": 5,
    "total_confidence": 30
  },
  "decision": "HITL_MANDATORY",
  "hitl_reason": "instance_count=0 (no instances match filter)",
  "hitl_prompt": {
    "message": "[HITL] No instances matched your filter 'status=Running'. Possible issues:",
    "suggestions": [
      "1. Check tag key/value spelling (case-sensitive)",
      "2. Verify instances are in the target region",
      "3. Try broader filter: remove 'status' constraint",
      "4. Check if instances exist via: aliyun ecs DescribeInstances"
    ],
    "options": ["MODIFY_FILTER", "VIEW_ALL_INSTANCES", "CANCEL"]
  }
}
```

### Example 3: HITL Triggered by Critical Environment

```json
{
  "iter": 1,
  "request": {
    "operation": "CreateMetricRuleBlackList",
    "product": "rds",
    "filter": {"tag:env": "production", "status": "Running"},
    "scope": "all_production_rds"
  },
  "delegation": {
    "skill": "alicloud-rds-ops",
    "query": "DescribeDBInstances",
    "result": {
      "instance_count": 45,
      "instances": ["rm-xxx1", "rm-xxx2", "..."]
    }
  },
  "confidence_calculation": {
    "instance_count": 45,
    "score_instance_range": 25,
    "filter_explicit": true,
    "score_filter": 20,
    "environment": "production",
    "score_env": 0,
    "operation": "standard",
    "score_op": 15,
    "rollback_available": true,
    "score_rollback": 10,
    "history": "high_success",
    "score_history": 10,
    "total_confidence": 80
  },
  "hitl_trigger": "environment=production (hard rule)",
  "decision": "HITL_REQUIRED",
  "hitl_prompt": {
    "message": "[HITL] Production environment detected. This operation will affect 45 RDS instances.",
    "warning": "Silencing production alerts may delay incident response.",
    "options": ["CONFIRM", "MODIFY", "VIEW", "CANCEL", "SCHEDULE"],
    "recommendation": "Consider scheduling during maintenance window (option 5)"
  }
}
```
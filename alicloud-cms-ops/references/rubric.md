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
  rubric_version: "1.0.0"
  rubric_phase: "3-B (Phantom Alarm Integration)"
  last_updated: "2026-06-04"
  parent: ../../../AGENTS.md
  references:
    - prompt-templates.md
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
1.0.0 | 2026-06-04 | CMS GCL rubric — Enhanced from Phase 5 lean to Phase 3-B full.
  New: §2 (Phantom Alarm Schema with JSON path table + alarm thresholds + template CLI);
  §4-5 (worked examples for alarm create + phantom-found SAFETY_FAIL).
  Renamed: §1 now covers both standard CMS ops and phantom alarm create.
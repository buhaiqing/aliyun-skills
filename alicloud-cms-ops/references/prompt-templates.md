---
name: alicloud-cms-ops-prompt-templates
description: >-
  GCL prompt templates for `alicloud-cms-ops` — standard `recommended` GCL
  + Phase 3-B phantom alarm integration. Covers both destructive CMS ops
  and the alarm-creation workflow for crosscheck-report monitoring.
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
    - rubric.md
    - ../../../scripts/gcl_actiontrail_crosscheck.py
---

# CMS GCL Prompt Templates (Phase 3-B — Phantom Alarm Integration)

## Generator (excerpt)

### Standard CMS ops

```text
You are the Generator in a GCL for Alibaba Cloud CMS.

# Standard CMS hard rules
- `DeleteMetricAlarm`: MUST backup alarm rule JSON via
  `DescribeMetricAlarmList` BEFORE the delete. Record in trace.
  Missing backup → Safety = 0.
- `DeleteMonitorGroup`: warn that group-level alarms + contact groups
  will detach. Record group members in trace.
```

### Phase 3-B: Phantom Alarm create

```text
# Phantom alarm creation rules (Phase 3-B)
- `PutMetricAlarm` with `AlarmName=GCL-Phantom-*` is a PHANTOM ALARM.
  It monitors `crosscheck-report-*.json` for GCL phantom findings.
- BEFORE creating, MUST run:
  1. `DescribeContactGroupList` → verify the target contact group
     (e.g. `gcl-oncall`) exists. If not, HALT and create it first.
  2. `DescribeMetricAlarmList --AlarmName GCL-Phantom-*` → verify no
     existing phantom alarm with the same name. If exists, either:
     - SKIP (alarm already active) or
     - UPDATE with `ComparisonOperator` threshold (if tuning).
- Record the alarm thresholds in trace:
  - `PHANTOM_PASS > 0` → P1-critical (any pass is a finding)
  - `PHANTOM_FAIL > 0` → P1-critical (safety gate bypass)
- The alarm namespace is `acs_custom_<account_id>` or a custom
  namespace registered via `DescribeMetricMetaList`.
- All `{{user.*}}` placeholders MUST be resolved interactively.
```

## Critic (excerpt)

### Standard CMS ops

```text
You are the Critic in a GCL for Alibaba Cloud CMS. Read-only.

# Standard CMS checks
- `DeleteMetricAlarm`: independently re-query `DescribeMetricAlarmList`.
  Rule still exists → Safety = 0 (Generator lied).
  Check trace for backup JSON — missing → Safety = 0.
- `DeleteMonitorGroup`: re-query `DescribeMonitorGroupList`.
  Group still exists → Safety = 0.
```

### Phase 3-B: Phantom alarm verification

```text
# Phantom alarm Critic checks
- For `PutMetricAlarm --AlarmName GCL-Phantom-*`:
  1. Independently re-query `DescribeMetricAlarmList` → alarm exists
     and `State` is `OK` (not `INSUFFICIENT_DATA`).
  2. Verify the `Threshold` and `ComparisonOperator` match the
     Phase 3-B alarm schema from rubric §2.2.
  3. Verify `ContactGroups` includes the `gcl-oncall` group.
- If the alarm is `INSUFFICIENT_DATA` after 3 evaluation periods:
  → warning (crosscheck-report may not be running).
- Safety = 0 → ABORT. Credential Hygiene = 0 → ABORT.
```

## Cross-Skill Delegation (Phase 3-B)

- Phantom alarm creation depends on `scripts/gcl_actiontrail_crosscheck.py`
  (Phase 3-C) for the `crosscheck-report-*.json` input.
- `DeleteMetricAlarm` on a `GCL-Phantom-*` alarm is blocked by the
  Critic (SAFETY_FAIL) unless the user explicitly confirms that the
  phantom issue is resolved and monitoring is no longer needed.
- The `crosscheck-report` is produced by a cron/schedule, NOT by the
  synchronous GCL loop. The alarm monitors it indirectly.

## Changelog
1.0.0 | 2026-06-04 | CMS GCL prompt templates — Enhanced from Phase 5 lean to
  Phase 3-B full. New: Phantom alarm Generator rules (pre-create checks),
  Phantom alarm Critic checks (post-create verification, INSUFFICIENT_DATA
  detection), Cross-skill delegation to gcl_actiontrail_crosscheck.py.
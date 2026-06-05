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
  rubric_version: "1.5.0"
  rubric_phase: "3-H (Dynamic Instance-Level Management)"
  last_updated: "2026-06-05"
  parent: ../../../AGENTS.md
  references:
    - rubric.md
    - scripts/gcl_actiontrail_crosscheck.py
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

## Phase 3-C: Alarm Blacklist (Silence/Mute) Operations

### Generator: Create alarm blacklist for specific instance

```text
You are the Generator in a GCL for Alibaba Cloud CMS Alarm Blacklist operations.

# Alarm Blacklist Creation Rules
- `CreateMetricRuleBlackList`: Create a blacklist policy to silence alerts for specific instances.

## Pre-flight Checks (MUST PASS)
1. `DescribeMetricRuleBlackList --Namespace {{user.namespace}}` → verify no existing
   blacklist covers the same instance + metric combination.
2. `DescribeMetricAlarmList --AlarmName {{user.alarm_name}}` → verify the target
   alarm rule exists and is active.
3. If `--EffectiveTime` is provided, validate the time format:
   - ISO 8601 format: `2026-06-05T15:00:00Z/2026-06-06T15:00:00Z`
   - Start time must be < End time
   - Duration should not exceed 7 days for temporary silence

## Variable Mapping
- `{{user.blacklist_name}}`: Descriptive name (e.g., "EIP-{instanceId}-临时静默-{日期}")
- `{{user.namespace}}`: Cloud product namespace (e.g., "acs_vpc_eip", "acs_ecs_dashboard")
- `{{user.metric_name}}`: Metric name (e.g., "OutBandwidthDropRate", "cpu_total")
- `{{user.resources}}`: JSON array of instance IDs: `["eip-xxx", "eip-yyy"]`
- `{{user.scope}}`: Scope type - "USER" (account-wide) or "GROUP" (specific group)
- `{{user.group_id}}`: Required if scope="GROUP"
- `{{user.effective_time}}`: Optional time range for temporary silence
- `{{user.region_id}}`: Region ID (e.g., "cn-shanghai")

## Safety Rules
- Permanent blacklist (no EffectiveTime) → MUST confirm: "This will permanently silence
  alerts for the specified instance(s). Confirm? (yes/no)"
- For critical instances (production, core services) → Recommend max 24h silence
- Record in trace: blacklist_id, instance_list, metric, created_time, expiry_time

## CLI Template

> **Note**: CLI templates use Handlebars syntax for conditional parameters:
> - `{{variable}}` — Required variable (replace at runtime)
> - `{{#if variable}}...{{/if}}` — Optional block (include only if variable is provided)
> - Agent must validate all `{{user.*}}` variables exist before executing

```bash
# Create temporary blacklist (24h silence)
aliyun cms CreateMetricRuleBlackList \
  --Name "{{user.blacklist_name}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "{{user.metric_name}}" \
  --Resources '{{user.resources}}' \
  --Scope "{{user.scope}}" {{#if user.group_id}}--ScopeValue "{{user.group_id}}"{{/if}} \
  {{#if user.effective_time}}--EffectiveTime "{{user.effective_time}}"{{/if}} \
  --RegionId {{user.region_id}}

# Query created blacklist
aliyun cms DescribeMetricRuleBlackList \
  --RegionId {{user.region_id}} \
  --Namespace {{user.namespace}}

# Disable blacklist (restore alerts)
aliyun cms DisableMetricRuleBlackList \
  --BlackListId {{output.blacklist_id}} \
  --RegionId {{user.region_id}}

# Enable blacklist again
aliyun cms EnableMetricRuleBlackList \
  --BlackListId {{output.blacklist_id}} \
  --RegionId {{user.region_id}}

# Delete blacklist (permanent removal)
aliyun cms DeleteMetricRuleBlackList \
  --BlackListId {{output.blacklist_id}} \
  --RegionId {{user.region_id}}
```

## Example Scenarios

### Scenario 1: Silence EIP outbound bandwidth drop alert for 24h
```bash
aliyun cms CreateMetricRuleBlackList \
  --Name "EIP-eip-uf6xii12c69nz0x5e718o-临时静默-24h" \
  --Namespace "acs_vpc_eip" \
  --MetricName "OutBandwidthDropRate" \
  --Resources '["eip-uf6xii12c69nz0x5e718o"]' \
  --Scope "USER" \
  --EffectiveTime "2026-06-05T15:00:00Z/2026-06-06T15:00:00Z" \
  --RegionId cn-shanghai
```

### Scenario 2: Silence multiple ECS CPU alerts in a group
```bash
aliyun cms CreateMetricRuleBlackList \
  --Name "ECS-维护窗口-CPU静默" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "cpu_total" \
  --Resources '["i-xxx", "i-yyy", "i-zzz"]' \
  --Scope "GROUP" \
  --ScopeValue "245146569" \
  --EffectiveTime "2026-06-05T02:00:00Z/2026-06-05T06:00:00Z" \
  --RegionId cn-hangzhou
```

## Success Criteria
- `output.blacklist_id` is returned and non-empty
- `DescribeMetricRuleBlackList` confirms the policy exists with status "ENABLED"
- For temporary silence: `EffectiveTime` matches requested range
```

### Critic: Verify alarm blacklist creation

```text
You are the Critic in a GCL for Alibaba Cloud CMS Alarm Blacklist. Read-only.

# Alarm Blacklist Verification Rules

## Post-Create Verification
For `CreateMetricRuleBlackList`:
1. Re-query `DescribeMetricRuleBlackList --BlackListId {{output.blacklist_id}}` →
   - Policy must exist and status = "ENABLED"
   - `Namespace` and `MetricName` must match Generator input
   - `Resources` list must exactly match requested instances
2. If `EffectiveTime` was specified:
   - Verify `StartTime` and `EndTime` match the requested range
   - Verify current time is within the effective window (if start time is in past)
3. Cross-check with `DescribeMetricAlarmList`:
   - The silenced alarm rule should still exist (blacklist ≠ delete rule)
   - No duplicate blacklist policies for same instance+metric

## Safety Checks
- **Safety = 0 → ABORT** if:
  - Blacklist policy not found after creation
  - Resources list mismatch (Generator claimed to silence A,B,C but only A,B in policy)
  - Permanent blacklist created for critical production instance without explicit confirmation
- **Warning** (log but don't abort):
  - Blacklist duration > 7 days (may indicate forgotten policy)
  - Instance appears in multiple blacklist policies (redundant)

## Idempotency Check
- Re-running CreateMetricRuleBlackList with same name → should return existing policy
- Check if Generator handled this gracefully vs creating duplicates

## Trace Requirements
- Generator trace MUST contain: blacklist_id, instance_list, metric, scope, expiry
- Critic trace MUST contain: verification timestamp, actual vs expected comparison
```

### Cross-Skill Delegation

- `CreateMetricRuleBlackList` depends on correct instance identification:
  - For EIP: delegate to `alicloud-eip-ops` to verify instance exists and is active
  - For ECS: delegate to `alicloud-ecs-ops` to verify instance status
- After blacklist creation, may need to notify via:
  - `alicloud-sls-ops` to log the silence action
  - `alicloud-actiontrail-ops` to audit the configuration change
- Blacklist expiry handling:
  - For permanent blacklists: recommend periodic review (quarterly)
  - For temporary blacklists: no action needed (auto-expires)

## Phase 3-D: Alert Threshold Tuning (告警阈值调优)

### Use Case
告警规则过于敏感（频繁误报）或过于迟钝（漏报），需要调整阈值、统计周期或连续触发次数。

### Generator: Modify alert thresholds

```text
You are the Generator in a GCL for Alibaba Cloud CMS Alert Threshold Tuning.

# Threshold Tuning Rules
- `PutResourceMetricRule`: Update existing metric alarm rule with new thresholds
- `PutMetricRuleTargets`: Update notification targets if needed

## Pre-flight Checks (MUST PASS)
1. `DescribeMetricAlarmList --AlarmName {{user.alarm_name}}` →
   - Verify rule exists and capture current thresholds (backup)
   - Check rule state (Enabled/Disabled)
2. Analyze historical data:
   - `DescribeMetricList --Namespace {{user.namespace}} --MetricName {{user.metric_name}}`
   - Query last 7 days of metric values to validate new threshold合理性
3. Calculate impact:
   - If threshold increases: estimate reduction in alert frequency
   - If threshold decreases: estimate increase in alert frequency
4. Verify notification channels still valid:
   - `DescribeContactGroupList` → confirm contact groups exist

## Variable Mapping
- `{{user.alarm_name}}`: Existing alarm rule name (required)
- `{{user.rule_id}}`: Rule ID (auto-fetched if alarm_name provided)
- `{{user.namespace}}`: Product namespace (e.g., "acs_ecs_dashboard")
- `{{user.metric_name}}`: Metric name
- `{{user.threshold_critical}}`: Critical level threshold
- `{{user.threshold_warn}}`: Warning level threshold (optional)
- `{{user.threshold_info}}`: Info level threshold (optional)
- `{{user.statistics}}`: Statistics type (Average, Maximum, Minimum, Sum)
- `{{user.comparison_operator}}`: GreaterThanThreshold, LessThanThreshold, etc.
- `{{user.period}}`: Evaluation period in seconds (60, 300, 900)
- `{{user.times}}`: Consecutive periods to trigger (1-10)
- `{{user.silence_time}}`: Notification silence period in seconds
- `{{user.contact_groups}}`: Contact groups for notifications (JSON array)

## Safety Rules
- **Threshold increase > 50%** → MUST confirm: "This significantly raises the threshold,
  potentially causing missed alerts. Confirm? (yes/no)"
- **Removing Critical level** → MUST confirm: "No critical level will remain.
  Confirm? (yes/no)"
- **Changing comparison direction** (e.g., > to <) → Double-check metric semantics
- Record in trace: old_threshold, new_threshold, reason_for_change, expected_impact

## CLI Template

```bash
# 1. Backup current rule
aliyun cms DescribeMetricAlarmList \
  --AlarmName "{{user.alarm_name}}" \
  --RegionId {{user.region_id}} > /tmp/alarm-backup-{{user.alarm_name}}.json

# 2. Update threshold (single level update)
aliyun cms PutResourceMetricRule \
  --RuleId "{{user.rule_id}}" \
  --RuleName "{{user.alarm_name}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "{{user.metric_name}}" \
  --Escalations.Critical.Statistics "{{user.statistics}}" \
  --Escalations.Critical.ComparisonOperator "{{user.comparison_operator}}" \
  --Escalations.Critical.Threshold "{{user.threshold_critical}}" \
  --Escalations.Critical.Times {{user.times}} \
  --Period {{user.period}} \
  --ContactGroups '{{user.contact_groups}}' \
  --SilenceTime {{user.silence_time}} \
  --RegionId {{user.region_id}}

# 3. Verify update
aliyun cms DescribeMetricAlarmList \
  --AlarmName "{{user.alarm_name}}" \
  --RegionId {{user.region_id}}
```

## Example Scenarios

### Scenario 1: Raise CPU threshold from 80% to 90% to reduce noise
```bash
# Backup first
aliyun cms DescribeMetricAlarmList --AlarmName "ECS-CPU-Critical" --RegionId cn-hangzhou > /tmp/backup-cpu.json

# Update threshold
aliyun cms PutResourceMetricRule \
  --RuleId "rule-xxx" \
  --RuleName "ECS-CPU-Critical" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "cpu_total" \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "90" \
  --Escalations.Critical.Times 3 \
  --Period 60 \
  --ContactGroups '["ops-team"]' \
  --SilenceTime 3600 \
  --RegionId cn-hangzhou
```

### Scenario 2: Adjust memory threshold with multiple levels
```bash
aliyun cms PutResourceMetricRule \
  --RuleId "rule-yyy" \
  --RuleName "ECS-Memory-Usage" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "memory_usedutilization" \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "95" \
  --Escalations.Critical.Times 3 \
  --Escalations.Warn.Statistics "Average" \
  --Escalations.Warn.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Warn.Threshold "85" \
  --Escalations.Warn.Times 3 \
  --Period 300 \
  --ContactGroups '["ops-team","dba-team"]' \
  --SilenceTime 7200 \
  --RegionId cn-hangzhou
```

### Scenario 3: Extend evaluation period to reduce false positives
```bash
aliyun cms PutResourceMetricRule \
  --RuleId "rule-zzz" \
  --RuleName "RDS-Connection-Count" \
  --Namespace "acs_rds_dashboard" \
  --MetricName "ConnectionUsage" \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "80" \
  --Escalations.Critical.Times 5 \
  --Period 300 \
  --ContactGroups '["dba-oncall"]' \
  --RegionId cn-hangzhou
```

## Success Criteria
- Backup JSON file created before any modification
- `DescribeMetricAlarmList` confirms new thresholds are applied
- Rule state remains "Enabled" after update
- Notification channels unchanged (unless explicitly modified)
```

### Critic: Verify threshold changes

```text
You are the Critic in a GCL for Alibaba Cloud CMS Alert Threshold Tuning. Read-only.

# Threshold Tuning Verification Rules

## Post-Update Verification
For `PutResourceMetricRule`:
1. Verify backup exists: Check trace for `/tmp/alarm-backup-{{alarm_name}}.json`
2. Re-query `DescribeMetricAlarmList --AlarmName {{user.alarm_name}}` →
   - Threshold values must match new values exactly
   - ComparisonOperator must match
   - Period and Times must match
3. Cross-check impact:
   - Query `DescribeMetricData` for last 24h → would the new threshold have triggered?
   - If new threshold > historical max → Safety = 0 (rule will never fire)
4. Verify notification channels:
   - ContactGroups must not be accidentally cleared
   - SilenceTime must be as intended

## Safety Checks
- **Safety = 0 → ABORT** if:
  - No backup recorded in trace before modification
  - Threshold changed but not reflected in DescribeMetricAlarmList
  - Critical level threshold > 99% for percentage metrics (likely misconfiguration)
  - ContactGroups accidentally set to empty (lost notification)
- **Warning** (log but don't abort):
  - Threshold increase > 100% (major change, verify with user)
  - ComparisonOperator flipped (e.g., > to <)
  - Period increased > 10x (from 60s to 900s)

## Rollback Plan
If Generator reports failure or verification fails:
1. Restore from backup JSON using extracted parameters
2. Re-apply original rule configuration
3. Verify restoration successful
```

## Phase 3-E: Notification Channel Management (告警通知渠道管理)

### Use Case
修改告警规则的通知方式（联系人组、Webhook、钉钉、短信等），或调整静默期。

### Generator: Update notification channels

```text
You are the Generator in a GCL for Alibaba Cloud CMS Notification Channel Management.

# Notification Channel Rules
- `PutMetricRuleTargets`: Update notification targets (contact groups, webhooks)
- `PutResourceMetricRule`: Update SilenceTime, EmailSubject

## Pre-flight Checks (MUST PASS)
1. `DescribeContactGroupList` → verify all target contact groups exist
2. `DescribeMetricAlarmList --AlarmName {{user.alarm_name}}` →
   - Capture current notification configuration (backup)
   - Verify rule is not in "INSUFFICIENT_DATA" state
3. If adding webhook:
   - Test webhook endpoint accessibility (HTTP probe)
   - Verify webhook URL is HTTPS (security requirement)
4. For P1/Critical alerts:
   - Ensure at least 2 notification channels (e.g., SMS + Email)

## Variable Mapping
- `{{user.alarm_name}}`: Alarm rule name (required)
- `{{user.contact_groups}}`: Contact groups JSON array: '["group1","group2"]'
- `{{user.webhook}}`: Webhook URL (HTTPS only)
- `{{user.silence_time}}`: Notification silence in seconds (0 = no silence)
- `{{user.email_subject}}`: Custom email subject template
- `{{user.level}}`: Alert levels to notify (Critical, Warn, Info)

## Safety Rules
- **Removing all contact groups** → MUST confirm: "No notification channels will remain.
  This alert will be silent. Confirm? (yes/no)"
- **Webhook without HTTPS** → Reject: "Webhook must use HTTPS protocol"
- **Critical alert with only email** → Warning: "Recommend adding SMS or phone call"
- Record in trace: old_channels, new_channels, change_reason

## CLI Template

```bash
# 1. Backup current configuration
aliyun cms DescribeMetricAlarmList \
  --AlarmName "{{user.alarm_name}}" \
  --RegionId {{user.region_id}} > /tmp/notification-backup-{{user.alarm_name}}.json

# 2. Update notification channels (contact groups + webhook)
aliyun cms PutMetricRuleTargets \
  --RuleId "{{user.rule_id}}" \
  --RegionId {{user.region_id}} \
  --ContactGroups '{{user.contact_groups}}' \
  --Webhook "{{user.webhook}}"

# 3. Update silence time and email subject
aliyun cms PutResourceMetricRule \
  --RuleId "{{user.rule_id}}" \
  --RuleName "{{user.alarm_name}}" \
  --SilenceTime {{user.silence_time}} \
  --EmailSubject "{{user.email_subject}}" \
  --RegionId {{user.region_id}}

# 4. Verify configuration
aliyun cms DescribeMetricAlarmList \
  --AlarmName "{{user.alarm_name}}" \
  --RegionId {{user.region_id}}
```

## Example Scenarios

### Scenario 1: Add webhook for auto-ticketing
```bash
aliyun cms PutMetricRuleTargets \
  --RuleId "rule-xxx" \
  --RegionId cn-hangzhou \
  --ContactGroups '["ops-team"]' \
  --Webhook "https://jira.example.com/webhook/create-ticket"
```

### Scenario 2: Change contact group for shift handover
```bash
aliyun cms PutMetricRuleTargets \
  --RuleId "rule-yyy" \
  --RegionId cn-hangzhou \
  --ContactGroups '["ops-night-shift"]' \
  --Webhook ""
```

### Scenario 3: Adjust silence time to prevent alert spam
```bash
aliyun cms PutResourceMetricRule \
  --RuleId "rule-zzz" \
  --RuleName "High-Frequency-Metric" \
  --SilenceTime 14400 \
  --EmailSubject "[{{level}}] {{metricName}} alert for {{instanceId}}" \
  --RegionId cn-hangzhou
```

## Success Criteria
- Backup created before modification
- New contact groups are reflected in `DescribeMetricAlarmList`
- Webhook URL is HTTPS and reachable
- Silence time is between 0-86400 seconds (1 day max)
```

### Critic: Verify notification channel changes

```text
You are the Critic in a GCL for Alibaba Cloud CMS Notification Management. Read-only.

# Notification Channel Verification Rules

## Post-Update Verification
1. Verify backup exists in trace
2. Re-query `DescribeMetricAlarmList --AlarmName {{alarm_name}}` →
   - ContactGroups must match requested groups
   - Webhook must match (if provided)
   - SilenceTime must match
3. Test webhook connectivity (if changed):
   - HTTP HEAD request to webhook URL
   - Must return 2xx or 3xx status
4. Verify critical alerts have redundant channels:
   - For Critical level: count(notification_channels) >= 2

## Safety Checks
- **Safety = 0 → ABORT** if:
  - ContactGroups set to empty array [] for active alert
  - Webhook URL uses HTTP instead of HTTPS
  - SilenceTime > 86400 seconds (1 day) without justification
  - Backup not found in trace
- **Warning**:
  - Single notification channel for P1/Critical alert
  - Webhook response time > 5 seconds (may cause timeout)

## Rollback
If verification fails, restore from backup and re-test.
```

## Phase 3-F: Event Alert Handling (事件告警处理)

### Use Case
处理系统事件告警（如实例重启、磁盘故障、安全事件等），区别于指标告警。

### Generator: Manage event-based alerts

```text
You are the Generator in a GCL for Alibaba Cloud CMS Event Alert Management.

# Event Alert Rules
- `PutEventRule`: Create/update event-based alarm rule
- `PutEventRuleTargets`: Configure event notification targets
- Event alerts monitor system events, not metric thresholds

## Pre-flight Checks (MUST PASS)
1. `DescribeEventRuleList --NamePrefix {{user.rule_name}}` →
   - Check for existing rules with same name
   - Understand event pattern scope
2. Validate event pattern:
   - Must match valid Alibaba Cloud event names
   - Example: "ecs:Instance:Reboot", "rds:Instance:Failover"
3. Check event level alignment with notification channels:
   - Critical events → Immediate notification (SMS/phone)
   - Info events → Email/DingTalk only
4. Verify silence period appropriateness:
   - Event alerts usually don't need long silence (events are discrete)

## Variable Mapping
- `{{user.rule_name}}`: Event rule name (required)
- `{{user.event_type}}`: Event type (e.g., "ecs", "rds", "slb")
- `{{user.event_pattern}}`: Event pattern/keyword (e.g., "Reboot", "Failover")
- `{{user.level}}`: Event level (CRITICAL, WARN, INFO)
- `{{user.contact_groups}}`: Notification contact groups
- `{{user.webhook}}`: Webhook for event notification
- `{{user.status}}`: Rule status (ENABLED, DISABLED)

## Safety Rules
- **Event pattern too broad** (e.g., "*") → MUST confirm: "This will capture ALL events.
  Confirm? (yes/no)"
- **Critical event without immediate notification** → Warning
- **Event rule for deprecated events** → Check if event type still valid
- Record in trace: event_pattern, matched_event_types, notification_config

## CLI Template

```bash
# 1. Create event rule
aliyun cms PutEventRule \
  --RuleName "{{user.rule_name}}" \
  --EventType "{{user.event_type}}" \
  --GroupId "{{user.group_id}}" \
  --EventPattern '{{user.event_pattern}}' \
  --Level "{{user.level}}" \
  --Status "{{user.status}}" \
  --RegionId {{user.region_id}}

# 2. Configure notification targets
aliyun cms PutEventRuleTargets \
  --RuleName "{{user.rule_name}}" \
  --ContactGroups '{{user.contact_groups}}' \
  --Webhook "{{user.webhook}}" \
  --RegionId {{user.region_id}}

# 3. Query event history to test pattern
aliyun cms DescribeEventList \
  --EventType "{{user.event_type}}" \
  --StartTime "{{user.start_time}}" \
  --EndTime "{{user.end_time}}" \
  --RegionId {{user.region_id}}

# 4. Verify rule
aliyun cms DescribeEventRuleList \
  --NamePrefix "{{user.rule_name}}" \
  --RegionId {{user.region_id}}
```

## Example Scenarios

### Scenario 1: Monitor ECS instance reboot events
```bash
# Create event rule for instance reboot
aliyun cms PutEventRule \
  --RuleName "ECS-Instance-Reboot-Alert" \
  --EventType "ecs" \
  --GroupId "245146569" \
  --EventPattern '{"eventName": ["Instance:Reboot", "Instance:Redeploy"]}' \
  --Level "WARN" \
  --Status "ENABLED" \
  --RegionId cn-hangzhou

# Configure notification
aliyun cms PutEventRuleTargets \
  --RuleName "ECS-Instance-Reboot-Alert" \
  --ContactGroups '["ops-team"]' \
  --RegionId cn-hangzhou
```

### Scenario 2: Alert on RDS failover events
```bash
aliyun cms PutEventRule \
  --RuleName "RDS-Failover-Critical" \
  --EventType "rds" \
  --EventPattern '{"eventName": ["Instance:Failover"]}' \
  --Level "CRITICAL" \
  --Status "ENABLED" \
  --RegionId cn-hangzhou

aliyun cms PutEventRuleTargets \
  --RuleName "RDS-Failover-Critical" \
  --ContactGroups '["dba-oncall","ops-manager"]' \
  --RegionId cn-hangzhou
```

### Scenario 3: Query recent events to validate pattern
```bash
aliyun cms DescribeEventList \
  --EventType "ecs" \
  --StartTime "2026-06-01T00:00:00Z" \
  --EndTime "2026-06-05T23:59:59Z" \
  --RegionId cn-hangzhou \
  --PageSize 100
```

## Success Criteria
- Event pattern is valid and matches expected event types
- Rule status is "ENABLED" after creation
- Notification targets configured successfully
- Recent events query returns expected results (pattern validation)
```

### Critic: Verify event alert configuration

```text
You are the Critic in a GCL for Alibaba Cloud CMS Event Alert Management. Read-only.

# Event Alert Verification Rules

## Post-Create Verification
1. `DescribeEventRuleList --NamePrefix {{rule_name}}` →
   - Rule must exist with status "ENABLED"
   - EventPattern must match Generator input
   - Level must match
2. Test event pattern:
   - `DescribeEventList --EventType {{type}} --StartTime {{recent}}` →
   - Check if any recent events match the pattern
   - If no matches in 7 days → pattern may be too restrictive or event rare
3. Verify notification:
   - `DescribeEventRuleTargets --RuleName {{rule_name}}` →
   - ContactGroups and Webhook must be configured

## Safety Checks
- **Safety = 0 → ABORT** if:
  - Event pattern is "*" (wildcards capture everything)
  - Event rule created but no notification targets configured
  - Rule status is "DISABLED" immediately after creation
- **Warning**:
  - Event pattern too specific (e.g., specific instance ID hardcoded)
  - No events matched in last 30 days (verify event type still exists)

## Cross-Skill Delegation
- Event alert pattern validation:
  - `alicloud-ecs-ops`: Verify ECS event names are valid
  - `alicloud-rds-ops`: Verify RDS event names are valid
  - `alicloud-slb-ops`: Verify SLB event names are valid
```

## Phase 3-G: Composite Expression Alerts (复合表达式告警)

### Use Case
创建多条件复合告警（如：CPU > 80% AND Memory > 90%），支持复杂业务场景。

### Generator: Create composite expression alerts

```text
You are the Generator in a GCL for Alibaba Cloud CMS Composite Expression Alerts.

# Composite Expression Rules
- `PutResourceMetricRule`: Create alarm with ExpressionRaw for complex logic
- Supports: logical operators (&&, ||), conditional expressions, count()
- Use case: Multi-metric conditions, instance-specific thresholds

## Pre-flight Checks (MUST PASS)
1. Validate expression syntax:
   - Check parentheses matching
   - Verify metric names exist in namespace
   - Validate comparison operators
2. Test expression logic:
   - Query historical data for each metric in expression
   - Simulate expression evaluation with real data
3. Check for expression complexity:
   - If expression length > 500 chars → suggest simplification
   - If > 5 conditions → recommend splitting into multiple rules
4. Verify referenced instances exist:
   - `DescribeInstances` (ECS) or product-specific describe API

## Variable Mapping
- `{{user.rule_name}}`: Composite alarm rule name
- `{{user.namespace}}`: Product namespace
- `{{user.expression_raw}}**: Raw expression string (e.g., "$Average > 80 && $instanceId == 'i-xxx'")
- `{{user.metric_names}}`: List of metrics used in expression (for validation)
- `{{user.resources}}**: Resources to monitor (may include all or subset)
- `{{user.threshold_critical}}**: Threshold for composite expression
- `{{user.period}}**: Evaluation period
- `{{user.times}}**: Consecutive periods

## Expression Syntax Reference
- Variables: $Average, $Maximum, $Minimum, $Sum, $instanceId
- Operators: && (AND), || (OR), !=, ==, >, <, >=, <=
- Functions: count($metric > threshold) > N
- Conditionals: ($instanceId == 'i-xxx' ? 80 : 50)

## Safety Rules
- **Expression with syntax error** → Reject before API call
- **Expression always true/false** → Simulate with historical data first
- **Circular reference** in multi-rule setup → Detect and prevent
- Record in trace: expression_raw, parsed_conditions, validation_result

## CLI Template

```bash
# Create composite expression alert
aliyun cms PutResourceMetricRule \
  --RuleName "{{user.rule_name}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "composite_metric_placeholder" \
  --ExpressionRaw "{{user.expression_raw}}" \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "{{user.threshold_critical}}" \
  --Escalations.Critical.Times {{user.times}} \
  --Period {{user.period}} \
  --Resources '{{user.resources}}' \
  --ContactGroups '{{user.contact_groups}}' \
  --RegionId {{user.region_id}}

# Verify rule creation
aliyun cms DescribeMetricAlarmList \
  --AlarmName "{{user.rule_name}}" \
  --RegionId {{user.region_id}}
```

## Example Scenarios

### Scenario 1: CPU and Memory combined alert
```bash
aliyun cms PutResourceMetricRule \
  --RuleName "ECS-High-Resource-Usage" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "cpu_total" \
  --ExpressionRaw '$Average > 80 && $memory_usedutilization > 90' \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "1" \
  --Escalations.Critical.Times 2 \
  --Period 60 \
  --Resources '[{"instanceId":"i-xxx"},{"instanceId":"i-yyy"}]' \
  --ContactGroups '["ops-team"]' \
  --RegionId cn-hangzhou
```

### Scenario 2: Instance-specific thresholds
```bash
aliyun cms PutResourceMetricRule \
  --RuleName "ECS-CPU-Conditional" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "cpu_total" \
  --ExpressionRaw '$Average > ($instanceId == "i-xxx" ? 90 : 70)' \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "1" \
  --Escalations.Critical.Times 3 \
  --Period 60 \
  --Resources '[{"instanceId":"i-xxx"},{"instanceId":"i-yyy"},{"instanceId":"i-zzz"}]' \
  --ContactGroups '["ops-team"]' \
  --RegionId cn-hangzhou
```

### Scenario 3: Count-based alert (N instances threshold breach)
```bash
aliyun cms PutResourceMetricRule \
  --RuleName "ECS-Multi-Instance-CPU" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "cpu_total" \
  --ExpressionRaw 'count($Average > 80) > 3' \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "1" \
  --Escalations.Critical.Times 1 \
  --Period 300 \
  --Resources '[{"instanceId":"i-1"},{"instanceId":"i-2"},{"instanceId":"i-3"},{"instanceId":"i-4"},{"instanceId":"i-5"}]' \
  --ContactGroups '["ops-manager"]' \
  --RegionId cn-hangzhou
```

## Success Criteria
- Expression syntax is valid (parentheses matched, operators correct)
- All referenced metrics exist in the namespace
- All referenced instances exist
- Rule evaluates without error in DescribeMetricAlarmList
- Historical data simulation shows expected trigger behavior
```

### Critic: Verify composite expression alerts

```text
You are the Critic in a GCL for Alibaba Cloud CMS Composite Expression Alerts. Read-only.

# Composite Expression Verification Rules

## Post-Create Verification
1. `DescribeMetricAlarmList --AlarmName {{rule_name}}` →
   - ExpressionRaw must match exactly
   - No syntax errors in rule state
   - Rule status should be "Enabled"
2. Expression validation:
   - Parse ExpressionRaw → extract all conditions
   - Verify each metric name exists in namespace
   - Verify each instanceId in Resources list
3. Logic simulation:
   - Query historical data for last 24h
   - Evaluate expression with real values
   - If always true/false → flag as potential issue
4. Complexity check:
   - Expression length should be < 1000 chars
   - Condition count should be < 10

## Safety Checks
- **Safety = 0 → ABORT** if:
  - Expression has syntax error (parentheses mismatch)
  - Referenced metric doesn't exist in namespace
  - Referenced instance doesn't exist
  - Expression always evaluates to true/false (tested with historical data)
- **Warning**:
  - Expression too complex (> 10 conditions)
  - Hardcoded instance IDs in expression (consider templating)
  - Using OR (||) with broad conditions (may cause excessive alerts)

## Cross-Skill Validation
- Expression metrics validation:
  - `alicloud-ecs-ops`: Validate ECS metric names
  - `alicloud-rds-ops`: Validate RDS metric names
  - `alicloud-slb-ops`: Validate SLB metric names
- Instance existence check:
  - Delegate to respective product skills based on instanceId prefix
```

## Phase 3-H: Dynamic Instance-Level Alert Management (基于实例级别的动态告警管理)

### Use Case
需要先查询实例列表（按标签、规格、状态筛选），再动态应用到告警规则。避免硬编码实例 ID，实现批量、可维护的告警配置。

### Generator: Dynamic instance targeting

```text
You are the Generator in a GCL for Alibaba Cloud CMS Dynamic Instance-Level Alert Management.

# Dynamic Instance Alert Rules
- Step 1: Query instances dynamically based on filters
- Step 2: Transform instance list to Resources JSON format
- Step 3: Apply alarm rule to dynamic instance set

## Pre-flight Checks (MUST PASS)

### Phase 1: Instance Discovery
1. **Query instances with filters:**
   - `aliyun ecs DescribeInstances --RegionId {{user.region_id}}` (ECS)
   - `aliyun rds DescribeDBInstances --RegionId {{user.region_id}}` (RDS)
   - `aliyun vpc DescribeEipAddresses --RegionId {{user.region_id}}` (EIP)
   - Add filters as needed: `--Tag`, `--Status`, `--InstanceType`, etc.

2. **Filter conditions ({{user.filters}}):**
   - Tag filter: `--Tag '[{"Key":"env","Value":"production"}]'`
   - Status filter: `--Status Running` (ECS), `--DBInstanceStatus Running` (RDS)
   - Instance type: `--InstanceTypeFamily ecs.c7` (特定规格)
   - VPC/Zone filter: `--VpcId vpc-xxx`, `--ZoneId cn-hangzhou-a`

3. **Instance count validation:**
   - If count == 0 → HALT: "No instances match the filter criteria"
   - If count > 100 → Confirm: "Large instance set ({{count}}). Confirm batch operation?"
   - Record in trace: filter_conditions, matched_instance_count, instance_list_sample

### Phase 2: Instance-to-Alarm Mapping
Transform query result to CMS Resources format:

```json
// ECS instances
[{"instanceId":"i-xxx"}, {"instanceId":"i-yyy"}]

// RDS instances
[{"dbInstanceId":"rm-xxx"}, {"dbInstanceId":"rm-yyy"}]

// EIP instances
[{"instanceId":"eip-xxx"}, {"instanceId":"eip-yyy"}]
```

## Variable Mapping
- `{{user.product}}`: Product type (ecs, rds, eip, slb, redis)
- `{{user.filters}}`: JSON filter criteria:
  ```json
  {
    "tags": [{"Key": "env", "Value": "production"}],
    "status": "Running",
    "instance_type": "ecs.c7.xlarge",
    "vpc_id": "vpc-xxx",
    "zone_id": "cn-hangzhou-a"
  }
  ```
- `{{user.alarm_template}}`: Base alarm rule template name
- `{{user.namespace}}`: Product namespace
- `{{user.metric_name}}**: Metric to monitor
- `{{user.dynamic_resources}}`: Output from instance query (auto-populated)
- `{{user.max_instances}}**: Maximum instances per rule (default 50, CMS limit)

## Safety Rules
- **Empty instance list** → HALT before creating alarm
- **Instance count > max_instances** → Split into multiple alarm rules
- **Cross-product mixing** → Reject (e.g., ECS + RDS in same rule)
- **Tag-based filter too broad** (matches > 50% of all instances) → Confirm
- Record in trace: query_command, filter_json, instance_count, resource_json_hash

## Auto-Processing vs HITL (Human-in-the-Loop) Decision Matrix

**核心原则**: LLM 在自信有把握时自动处理；存在不确定性时执行 HITL，提交人工复核。

### Auto-Processing Conditions (自动处理条件)

满足以下**所有**条件时，LLM 可直接执行：

| 条件 | 阈值 | 说明 |
|------|------|------|
| **实例数量** | 10 ≤ count ≤ 50 | 适中的批量规模 |
| **过滤器明确性** | 高 | Tag + Status 组合，无通配符 |
| **环境重要性** | 非核心生产 | 开发/测试环境，或非关键业务 |
| **操作类型** | 标准告警创建 | 非删除/禁用类破坏性操作 |
| **回滚方案** | 已就绪 | 有明确的禁用/删除命令 |
| **历史成功率** | > 90% | 相同过滤模式过去执行成功 |

**自信度评分** (Confidence Score):
```
confidence = (
  (instance_count_in_range ? 25 : 0) +
  (filter_explicit ? 20 : 0) +
  (non_critical_env ? 20 : 0) +
  (standard_op ? 15 : 0) +
  (rollback_ready ? 10 : 0) +
  (high_success_rate ? 10 : 0)
)

if confidence >= 80: AUTO-PROCESS
if confidence < 80: HITL_REQUIRED
```

### HITL Trigger Conditions (人工复核触发条件)

满足以下**任一**条件时，**必须**暂停并提交人工复核：

| 触发条件 | 风险等级 | HITL 原因 |
|---------|---------|----------|
| **实例数 = 0** | 🔴 Critical | 过滤器可能有误，需确认 |
| **实例数 > 100** | 🔴 Critical | 影响范围过大，需分批确认 |
| **匹配率 > 80%** | 🟠 High | 过滤器过宽，可能包含非目标实例 |
| **关键生产环境** | 🔴 Critical | 核心业务实例，误操作影响大 |
| **永久静默操作** | 🟠 High | 无过期时间，需确认长期策略 |
| **实例数变化 > 50%** | 🟠 High | 过滤条件不稳定，需审查 |
| **无状态过滤** | 🟡 Medium | 可能包含 Stopped 实例 |
| **跨区域实例** | 🟡 Medium | 网络延迟、时区差异等因素 |
| **首次执行该过滤模式** | 🟡 Medium | 无历史数据验证 |
| **复杂复合过滤器** | 🟡 Medium | 多条件组合，逻辑复杂 |

### HITL Workflow (人工复核流程)

当触发 HITL 时，执行以下流程：

```text
🛑 HITL TRIGGERED

Reason: {{trigger_reason}}
Risk Level: {{risk_level}}

📋 待人工确认信息:
1. 过滤器详情:
   - Tag: {{tag_filter}}
   - Status: {{status_filter}}
   - Other: {{other_filters}}

2. 影响范围:
   - 匹配实例数: {{instance_count}}
   - 占总实例比例: {{percentage}}%
   - 关键实例: {{critical_instances}}

3. 拟执行操作:
   - 操作类型: {{operation_type}}
   - 告警规则: {{alarm_name}}
   - 阈值设置: {{threshold}}
   - 通知渠道: {{contact_groups}}

4. 回滚方案:
   - 回滚命令: {{rollback_command}}
   - 预计恢复时间: {{recovery_time}}

⏸️ 等待人工确认...

选项:
[1] ✅ 确认执行 - 继续操作
[2] 📝 修改过滤器 - 提供新的过滤条件
[3] 🔍 查看实例列表 - 展示匹配实例详情
[4] ❌ 取消操作 - 终止并记录原因
[5] ⏰ 定时执行 - 延迟到指定时间执行

请选择 [1-5]:
```

### Auto-Correction with Confidence Threshold

对于可自动修复的问题，设置**自信度阈值**：

| 问题类型 | 自动修复自信度 | 处理方式 |
|---------|---------------|---------|
| Tag Key 大小写错误 (ENV→env) | 95% | 自动修复 |
| Status 大小写错误 (running→Running) | 95% | 自动修复 |
| 缺少状态过滤 | 70% | 建议添加，等待确认 |
| 过滤器过宽 (>100 实例) | 60% | 提供优化建议，HITL |
| 实例数 = 0 | 40% | 提供排查方案，HITL |
| 关键生产环境 | 30% | HITL，即使其他条件满足 |

### Decision Log (决策日志)

所有自动处理和 HITL 决策必须记录：

```json
{
  "decision": {
    "timestamp": "2026-06-05T15:30:00Z",
    "type": "AUTO_PROCESS",
    "confidence_score": 85,
    "triggered_conditions": [
      "instance_count_in_range: 25",
      "filter_explicit: true",
      "non_critical_env: true"
    ],
    "skipped_hitl_triggers": [
      "首次执行该过滤模式 (但自信度足够)"
    ]
  }
}

{
  "decision": {
    "timestamp": "2026-06-05T15:35:00Z",
    "type": "HITL_REQUIRED",
    "confidence_score": 55,
    "triggered_hitl_conditions": [
      "实例数 > 100: 150",
      "关键生产环境: true"
    ],
    "human_response": {
      "reviewer": "ops-team-lead",
      "decision": "MODIFY_FILTER",
      "new_filter": "添加了 service=api 标签",
      "new_instance_count": 32
    }
  }
}
```

## Product-Agnostic Discovery Pattern

**不要硬编码产品矩阵！** 使用以下通用模式，通过 delegation 获取产品特定信息：

### 通用查询模式

```text
# 获取产品查询信息（通过 Cross-Skill Delegation）
{{user.product_skill}}: 提供以下信息：
1. 查询命令（如 DescribeInstances, DescribeDBInstances）
2. 主要过滤参数（Tag, Status 等参数名）
3. 实例 ID 字段名（InstanceId, DBInstanceId 等）
4. 资源 JSON 中的 key 名称（instanceId, dbInstanceId 等）
5. 状态字段的有效值（Running, Available, Active 等）

# 使用返回信息构建查询
aliyun {{user.product}} {{output.query_command}} \
  --RegionId {{user.region_id}} \
  {{#if user.filters.tags}}--Tag '{{user.filters.tags}}'{{/if}} \
  {{#if user.filters.status}}--{{output.status_param}} '{{user.filters.status}}'{{/if}} \
  --PageSize 100 \
  --output cols={{output.id_field}},{{output.name_field}} rows={{output.jmespath}}
```

### Cross-Skill Delegation 映射

不要预设产品矩阵，而是动态查询：

| 用户需求 | 委托 Skill | 返回信息 |
|---------|-----------|---------|
| "ECS 实例" | `alicloud-ecs-ops` | DescribeInstances, InstanceId, instanceId, Running |
| "RDS 实例" | `alicloud-rds-ops` | DescribeDBInstances, DBInstanceId, instanceId, Running |
| "Redis 实例" | `alicloud-redis-ops` | DescribeInstances (r-kvstore), InstanceId, instanceId, Normal |
| "SLB 实例" | `alicloud-slb-ops` | DescribeLoadBalancers, LoadBalancerId, loadBalancerId, Active |
| "PolarDB" | `alicloud-polar-mysql-ops` | DescribeDBClusters, DBClusterId, dbClusterId, Running |
| "EIP" | `alicloud-eip-ops` | DescribeEipAddresses, AllocationId, instanceId, Available |

**重要原则**：Skill 返回的信息是 authoritative source，不要 hardcode。

## CLI Template

```bash
# ========== PHASE 1: DISCOVER INSTANCES (Generic Pattern) ==========

# Step 1: Get product-specific query info via skill delegation
# (This is done via cross-skill call, not hardcoded)

# Step 2: Build and execute query dynamically
OUTPUT=$(aliyun {{user.product}} {{output.query_command}} \
  --RegionId {{user.region_id}} \
  {{#if user.filters.tags}}--Tag '{{user.filters.tags}}'{{/if}} \
  {{#if user.filters.status}}--{{output.status_param}} '{{user.filters.status}}'{{/if}} \
  --PageSize 100 \
  --output cols={{output.id_field}} rows={{output.jmespath}})

# Step 3: Extract instance IDs (product-agnostic pattern)
INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE '{{output.id_pattern}}')

# Step 4: Build Resources JSON with correct key
RESOURCES=$(echo "$INSTANCE_IDS" | jq -R -s -c \
  'split("\n")[:-1] | map({"{{output.resource_key}}": .})')

# ========== PHASE 2: VALIDATION ==========

COUNT=$(echo "$RESOURCES" | jq '. | length')
if [ "$COUNT" -eq 0 ]; then
  echo "ERROR: No instances match filters"
  exit 1
elif [ "$COUNT" -gt {{user.max_instances}} ]; then
  echo "WARNING: Instance count ($COUNT) exceeds limit ({{user.max_instances}})"
fi

# ========== PHASE 3: CREATE ALARM ==========

aliyun cms PutResourceMetricRule \
  --RuleName "{{user.alarm_name}}" \
  --Namespace "{{user.namespace}}" \
  --MetricName "{{user.metric_name}}" \
  --Resources "$RESOURCES" \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "{{user.threshold}}" \
  --Escalations.Critical.Times {{user.times}} \
  --Period {{user.period}} \
  --ContactGroups '{{user.contact_groups}}' \
  --RegionId {{user.region_id}}
```

## Example Scenarios

### Scenario 1: Tag-based dynamic targeting with optimization feedback

```bash
# Step 1: Query production ECS instances
OUTPUT=$(aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --Tag '[{"Key":"env","Value":"production"}]' \
  --Status Running \
  --PageSize 100 \
  --output cols=InstanceId,InstanceName,Tags rows=Instances.Instance[])

# Step 2: Transform
INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
RESOURCES=$(echo "$INSTANCE_IDS" | jq -R -s -c 'split("\n")[:-1] | map({instanceId: .})')
COUNT=$(echo "$RESOURCES" | jq '. | length')

# Step 3: 自审检查 - 实例数过多，触发优化建议
if [ "$COUNT" -gt 100 ]; then
  echo "⚠️  优化建议: 匹配到 $COUNT 个实例，建议添加更精确的过滤条件"
  echo "推荐方案:"
  echo "  1. 添加服务标签: --Tag '[{\"Key\":\"env\",\"Value\":\"production\"},{\"Key\":\"service\",\"Value\":\"api\"}]'"
  echo "  2. 按 VPC 拆分: --VpcId vpc-xxx"
  echo "  3. 按实例规格: --InstanceTypeFamily ecs.c7"
fi

# Step 4: Create alarm
aliyun cms PutResourceMetricRule \
  --RuleName "Production-ECS-CPU-Alert" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "cpu_total" \
  --Resources "$RESOURCES" \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "90" \
  --Escalations.Critical.Times 3 \
  --Period 60 \
  --ContactGroups '["ops-team"]' \
  --RegionId cn-hangzhou
```

### Scenario 2: Zero instances detected - auto-correction

```bash
# 初始查询（过滤器可能有误）
OUTPUT=$(aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --Tag '[{"Key":"ENV","Value":"production"}]' \
  --Status running \
  --PageSize 100)

INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
COUNT=$(echo "$INSTANCE_IDS" | wc -l)

# 🚨 自审发现: 实例数 = 0，触发自动优化
if [ "$COUNT" -eq 0 ]; then
  echo "🚨 问题: 过滤器过于严格，未匹配到实例"
  echo "自动优化尝试:"
  
  # 尝试 1: 修复大小写
  echo "尝试 1: 修复 Tag Key 大小写 (ENV -> env)..."
  OUTPUT=$(aliyun ecs DescribeInstances \
    --RegionId cn-hangzhou \
    --Tag '[{"Key":"env","Value":"production"}]' \
    --PageSize 100)
  COUNT=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+' | wc -l)
  
  if [ "$COUNT" -gt 0 ]; then
    echo "✅ 成功! 修复大小写后匹配到 $COUNT 个实例"
    INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
  else
    # 尝试 2: 移除状态过滤
    echo "尝试 2: 移除状态过滤..."
    OUTPUT=$(aliyun ecs DescribeInstances \
      --RegionId cn-hangzhou \
      --Tag '[{"Key":"env","Value":"production"}]' \
      --PageSize 100)
    COUNT=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+' | wc -l)
    
    if [ "$COUNT" -gt 0 ]; then
      echo "✅ 成功! 移除状态过滤后匹配到 $COUNT 个实例"
      echo "⚠️  注意: 过滤器缺少状态条件，可能包含 Stopped 实例"
      INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
    else
      echo "❌ 失败: 即使放宽条件仍未匹配到实例，请检查:"
      echo "  - 区域 ID 是否正确 (当前: cn-hangzhou)"
      echo "  - Tag Value 是否正确 (当前: production)"
      echo "  - 实例是否存在且已分配该 Tag"
      exit 1
    fi
  fi
fi

# 继续创建告警...
```

### Scenario 3: Multi-filter targeting - High-memory RDS instances
```bash
# Query specific RDS instances
OUTPUT=$(aliyun rds DescribeDBInstances \
  --RegionId cn-hangzhou \
  --DBInstanceStatus Running \
  --Engine MySQL \
  --PageSize 100 \
  --output cols=DBInstanceId,DBInstanceClass rows=Items.DBInstance[])

# Filter by instance class (memory >= 8GB) using grep/jq
RESOURCES=$(echo "$OUTPUT" | grep -E 'rds.mysql.(c1|r6)' | grep -oE 'rm-[a-z0-9]+' | \
  jq -R -s -c 'split("\n")[:-1] | map({instanceId: .})')

# Create alarm for high-memory instances
aliyun cms PutResourceMetricRule \
  --RuleName "RDS-HighMemory-ConnectionAlert" \
  --Namespace "acs_rds_dashboard" \
  --MetricName "ConnectionUsage" \
  --Resources "$RESOURCES" \
  --Escalations.Warn.Statistics "Average" \
  --Escalations.Warn.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Warn.Threshold "80" \
  --Escalations.Warn.Times 5 \
  --Period 300 \
  --ContactGroups '["dba-team"]' \
  --RegionId cn-hangzhou
```

### Scenario 4: HITL triggered - Critical production environment

```bash
# 查询生产环境 ECS（关键业务）
OUTPUT=$(aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --Tag '[{"Key":"env","Value":"production"},{"Key":"tier","Value":"critical"}]' \
  --Status Running \
  --PageSize 100)

INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
COUNT=$(echo "$INSTANCE_IDS" | wc -l)

# 🛑 HITL TRIGGERED - 关键生产环境
if [ "$COUNT" -gt 0 ]; then
  # 计算自信度
  CONFIDENCE=45  # 关键生产环境扣分
  
  if [ "$COUNT" -gt 10 ]; then
    CONFIDENCE=$((CONFIDENCE - 10))  # 实例数较多
  fi
  
  echo "🛑 HITL TRIGGERED - 需要人工复核"
  echo ""
  echo "触发原因:"
  echo "  - 🔴 关键生产环境 (tier=critical)"
  echo "  - 🟠 影响实例数: $COUNT"
  echo "  - 📊 自信度评分: $CONFIDENCE/100 (低于阈值 80)"
  echo ""
  echo "📋 待确认信息:"
  echo "  - 实例列表预览 (前5个):"
  echo "$INSTANCE_IDS" | head -5 | sed 's/^/    - /'
  echo ""
  echo "  - 拟执行操作: 创建 CPU > 90% 告警规则"
  echo "  - 通知渠道: ops-oncall"
  echo "  - 回滚方案: aliyun cms DeleteMetricAlarmList --RuleId <id>"
  echo ""
  echo "选项:"
  echo "  [1] ✅ 确认执行 - 继续创建告警规则"
  echo "  [2] 📝 修改过滤条件 - 排除部分实例"
  echo "  [3] 🔍 查看完整实例列表 - 展示所有 $COUNT 个实例"
  echo "  [4] ❌ 取消操作"
  echo ""
  
  # 等待人工输入（实际实现中）
  # read -p "请选择 [1-4]: " choice
  
  # 示例：人工选择选项 2，修改过滤器
  echo "人工选择: [2] 修改过滤条件"
  echo "修改: 添加 service=api 标签缩小范围"
  
  # 重新查询
  OUTPUT=$(aliyun ecs DescribeInstances \
    --RegionId cn-hangzhou \
    --Tag '[{"Key":"env","Value":"production"},{"Key":"tier","Value":"critical"},{"Key":"service","Value":"api"}]' \
    --Status Running \
    --PageSize 100)
  
  NEW_COUNT=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+' | wc -l)
  echo "优化后实例数: $NEW_COUNT (原: $COUNT)"
fi

# 继续执行...
```

### Scenario 5: Auto-processing with confidence check

```bash
# 查询开发环境实例（低风险评估）
OUTPUT=$(aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --Tag '[{"Key":"env","Value":"dev"},{"Key":"team","Value":"backend"}]' \
  --Status Running \
  --InstanceTypeFamily ecs.c7 \
  --PageSize 100)

INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
COUNT=$(echo "$INSTANCE_IDS" | wc -l)

# Confidence Scoring Checklist
# Each condition: +points | Pass/Fail
# Total score >= 80 → auto-process; < 80 → HITL

CONFIDENCE=0

# ✅ Check 1: Instance count in safe range (10-50)
if [ "$COUNT" -ge 10 ] && [ "$COUNT" -le 50 ]; then
  CONFIDENCE=$((CONFIDENCE + 25))  # ✅ PASS
else
  echo "⚠️ Instance count ($COUNT) outside safe range"
fi

# ✅ Check 2: Clear filters (Tag + Status specified)
CONFIDENCE=$((CONFIDENCE + 20))  # ✅ PASS (both specified above)

# ✅ Check 3: Non-critical environment
CONFIDENCE=$((CONFIDENCE + 20))  # ✅ PASS (dev environment)

# ✅ Check 4: Standard operation (alarm creation)
CONFIDENCE=$((CONFIDENCE + 15))  # ✅ PASS

# ✅ Check 5: Rollback plan available
CONFIDENCE=$((CONFIDENCE + 10))  # ✅ PASS (can delete rule)

# ✅ Check 6: High historical success rate
CONFIDENCE=$((CONFIDENCE + 10))  # ✅ PASS

echo "📊 Confidence Score: $CONFIDENCE/100"

# Decision
if [ "$CONFIDENCE" -ge 80 ]; then
  echo "✅ Auto-processing (score >= 80)"
  
  RESOURCES=$(echo "$INSTANCE_IDS" | jq -R -s -c 'split("\n")[:-1] | map({instanceId: .})')
  
  aliyun cms PutResourceMetricRule \
    --RuleName "Dev-Backend-CPU-Alert" \
    --Namespace "acs_ecs_dashboard" \
    --MetricName "cpu_total" \
    --Resources "$RESOURCES" \
    --Escalations.Warn.Statistics "Average" \
    --Escalations.Warn.ComparisonOperator "GreaterThanThreshold" \
    --Escalations.Warn.Threshold "85" \
    --Escalations.Warn.Times 5 \
    --Period 300 \
    --ContactGroups '["dev-team"]' \
    --RegionId cn-hangzhou
  
  echo "✅ Alarm rule created (auto mode)"
  
else
  echo "🛑 HITL triggered (score $CONFIDENCE < 80)"
  # HITL workflow...
fi
```

## Success Criteria
- Instance query returns non-empty list
- Resources JSON format is valid for CMS API
- Alarm rule created with correct instance count
- Rule state is "Enabled" after creation
- Instance list can be refreshed/updated independently

## Instance Discovery

> **Note**: Do NOT rely on hardcoded instance ID prefixes. Use the dynamic discovery mechanism:
> - Step 1: Call `DescribeDimensionResourceList` or `DescribeProductResourceList` to get actual resource IDs
> - Step 2: These APIs return valid `resourceValue` values that can be directly used in `--Resources` JSON
> - Step 3: For unknown products, first query available dimensions via `DescribeProductResourceList`
>
> This approach is product-agnostic and handles any Alibaba Cloud service automatically.
```

### Critic: Verify dynamic instance targeting

```text
You are the Critic in a GCL for Alibaba Cloud CMS Dynamic Instance-Level Management. Read-only.

# Dynamic Instance Verification Rules

## Post-Operation Verification

### Phase 1: Instance Query Validation
1. Independently re-run the instance discovery query:
   - Use same filters as Generator
   - Verify instance count matches Generator's claim
   - Check for any instances that should have been included but weren't

2. **Instance list integrity check:**
   - Randomly sample 3-5 instances from the list
   - Verify each instance exists and matches filter criteria
   - Check instance status (should be Running/Active, not Stopped/Deleted)

### Phase 2: Resources JSON Validation
1. Verify JSON format is valid:
   - Must be valid JSON array
   - Each element must have correct key (instanceId, dbInstanceId, etc.)
   - No duplicate instance IDs

2. **Cross-check with alarm rule:**
   - `DescribeMetricAlarmList --AlarmName {{alarm_name}}` →
   - Extract Resources field
   - Compare with Generator's claimed list
   - Must match exactly

### Phase 3: Filter Accuracy
1. **Tag-based filters:**
   - Verify tagged instances are included
   - Verify untagged instances are excluded
2. **Status filters:**
   - Check that stopped/deleted instances are not in list
3. **Type/Spec filters:**
   - Verify instance types match criteria

## Safety Checks
- **Safety = 0 → ABORT** if:
  - Instance query returns different count than Generator claims
  - Alarm rule Resources don't match query results
  - Stopped/terminated instances included in list
  - Empty instance list passed to alarm creation (should have halted)
- **Warning** (log but don't abort):
  - Instance count changed between query and alarm creation (race condition)
  - Large instance set (> 100) without pagination handling
  - Instances from multiple regions mixed in same rule

## Cross-Skill Validation
- Delegate instance verification to product-specific skills:
  - `alicloud-ecs-ops`: Verify ECS instance existence and tags
  - `alicloud-rds-ops`: Verify RDS instance status and engine
  - `alicloud-redis-ops`: Verify Redis instance availability
  - `alicloud-slb-ops`: Verify SLB instance configuration

## Dynamic Update Handling
If this is a scheduled/refresh operation:
1. Compare current instance list with previous run
2. Flag significant changes (> 20% instance count change)
3. Verify new instances actually match filter criteria
4. Check if removed instances were intentionally decommissioned

## Trace Requirements
- Generator trace MUST contain:
  - Query command with all filters
  - Raw query output (first 100 chars or summary)
  - Instance count
  - Resources JSON hash
  - Any exclusions applied
- Critic trace MUST contain:
  - Independent query results
  - Sampling verification details
  - Cross-check results

## Self-Review & Optimization Mechanism (自审优化机制)

### Optimization Trigger Conditions

Critic MUST trigger optimization review when:

| 条件 | 优化类型 | 建议动作 |
|------|---------|---------|
| 实例数 = 0 | 过滤器过严 | 放宽过滤条件 |
| 实例数 > 100 | 过滤器过宽 | 增加过滤条件 |
| 实例数占总实例 > 80% | 缺少有效过滤 | 添加标签/状态过滤 |
| 实例数变化率 > 50% | 过滤条件不稳定 | 检查 Tag 一致性 |
| 同一实例出现在多个规则 | 重叠监控 | 合并规则或去重 |
| 过滤器匹配所有状态 | 缺少状态过滤 | 添加 Running/Active 过滤 |

### Self-Review Checklist

```text
## 自审清单 (Self-Review Checklist)

### 1. 过滤器有效性审查
- [ ] Tag Key 是否存在拼写错误（如 env vs ENV）
- [ ] Tag Value 是否存在大小写不匹配（如 Production vs production）
- [ ] 状态值是否对该产品有效（如 ECS 用 Running，Redis 用 Normal）
- [ ] 区域 ID 是否与实例实际部署区域一致

### 2. 实例覆盖度审查  
- [ ] 预期的实例是否都被包含（抽查 3-5 个已知实例）
- [ ] 不应包含的实例是否被排除（如测试实例、已下线实例）
- [ ] 是否存在跨环境混合（如生产与测试实例在同一规则）

### 3. 性能与可维护性审查
- [ ] 实例数量是否适合单条规则（建议 < 100）
- [ ] 是否需要分页处理（> 100 实例时）
- [ ] 定时刷新周期是否合理（建议 >= 1 小时）
- [ ] 过滤器是否稳定（避免使用易变动的标签如 create-time）

### 4. 告警策略匹配度审查
- [ ] 告警阈值是否适合该实例集合（不同规格实例可能需要不同阈值）
- [ ] 是否需要按实例规格分组（如高内存 vs 低内存实例）
- [ ] 通知渠道是否与实例重要性匹配
```

### Optimization Recommendations

当发现优化点时，Critic 应提供具体建议：

#### 场景 1: 过滤器过严（实例数 = 0）
```text
🚨 问题: 过滤条件过于严格，未匹配到任何实例

建议优化:
1. 检查 Tag Key/Value 大小写: "ENV" → "env"
2. 检查状态值: "running" → "Running"  
3. 放宽过滤条件，分步测试:
   - Step 1: 仅按区域查询所有实例（验证基础查询）
   - Step 2: 添加一个过滤条件（如 --Status Running）
   - Step 3: 逐步添加其他过滤条件
4. 使用模糊匹配: Tag Value 使用通配符

回滚方案:
- 暂时移除过滤条件，使用全量实例列表
- 手动指定关键实例 ID（临时方案）
```

#### 场景 2: 过滤器过宽（实例数 > 100）
```text
🚨 问题: 过滤器过于宽泛，匹配到 {{count}} 个实例，超过建议值 100

建议优化:
1. 添加更精确的 Tag 过滤:
   - 从 `--Tag '[{"Key":"env","Value":"prod"}]'`
   - 改为 `--Tag '[{"Key":"env","Value":"prod"},{"Key":"service","Value":"api"}]'`
2. 添加实例规格过滤: `--InstanceTypeFamily ecs.c7`
3. 添加 VPC 过滤: `--VpcId vpc-xxx`
4. 拆分多条规则:
   - 按服务拆分: api-service, batch-service, cache-service
   - 按区域拆分: hangzhou-a, hangzhou-b, hangzhou-c

性能影响:
- 当前查询时间: {{query_time}}s
- 建议查询时间: < 5s
- CMS Resources 字段大小限制: 64KB（约 500 个实例 ID）
```

#### 场景 3: 重叠监控（同一实例多规则）
```text
🚨 问题: 检测到 {{overlap_count}} 个实例同时出现在多条告警规则中

重叠实例:
{{overlap_list}}

建议优化:
1. 合并规则（推荐）:
   - 如果阈值相同，合并为一条规则
   - 使用统一的 ContactGroups
2. 差异化规则:
   - 如果阈值不同，使用 ExpressionRaw 设置实例特定阈值
   - 示例: `$Average > ($instanceId == "i-xxx" ? 90 : 80)`
3. 规则分层:
   - Critical 规则: 核心实例（20%）
   - Warn 规则: 全部实例（100%）
   - Info 规则: 非核心实例（80%）

避免:
- 同一实例同一指标多条 Critical 规则（会导致重复告警）
```

#### 场景 4: 缺少状态过滤
```text
⚠️  警告: 过滤器未包含状态条件，可能包含 Stopped/Deleted 实例

建议优化:
1. 添加状态过滤（产品特定）:
   - ECS: `--Status Running`
   - RDS: `--DBInstanceStatus Running`
   - Redis: 查询后过滤 `$Status == "Normal"`
2. 定期清理规则中的无效实例:
   - 设置定时任务，移除已下线实例
   - 或使用动态刷新机制（自动更新）

风险:
- Stopped 实例的告警永远不会触发（浪费规则资源）
- Deleted 实例会导致告警规则状态异常
```

### Auto-Optimization Workflow

```text
## 自动优化工作流 (高级)

当启用 auto-optimization 模式时:

Step 1: 基线建立
- 首次执行时记录: instance_count, query_time, filter_hash
- 存储在 trace: baseline_snapshot

Step 2: 持续监控  
- 每次执行对比基线:
  - instance_count 变化 > 20% → 触发审查
  - query_time > 10s → 触发优化
  - filter_match_rate > 90% → 提示添加过滤

Step 3: 自动调优建议
- 生成优化报告:
  ```json
  {
    "current_state": {
      "instance_count": 150,
      "match_rate": 0.95,
      "query_time": 12.5
    },
    "recommendations": [
      {
        "type": "add_filter",
        "suggestion": "Add --Tag service=api to reduce instances",
        "expected_count": 45,
        "expected_time": 3.2
      }
    ],
    "confidence": 0.85
  }
  ```

Step 4: 人工确认
- 将建议提交给运维人员确认
- 提供一键应用优化建议的命令
```

### Optimization Trace Format

```json
{
  "optimization_review": {
    "triggered_at": "2026-06-05T15:30:00Z",
    "trigger_reason": "instance_count_zero",
    "original_filters": {
      "tags": [{"Key": "ENV", "Value": "prod"}],
      "status": "running"
    },
    "issues_found": [
      {
        "type": "case_mismatch",
        "field": "Tag.Key",
        "expected": "env",
        "actual": "ENV"
      },
      {
        "type": "case_mismatch", 
        "field": "Status",
        "expected": "Running",
        "actual": "running"
      }
    ],
    "recommendations": [
      {
        "priority": "high",
        "action": "fix_case",
        "before": "--Tag '[{\"Key\":\"ENV\"...",
        "after": "--Tag '[{\"Key\":\"env\"..."
      }
    ],
    "optimized_filters": {
      "tags": [{"Key": "env", "Value": "prod"}],
      "status": "Running"
    },
    "test_result": {
      "instance_count": 12,
      "status": "success"
    }
  }
}
```

## Phase Summary: When to Use Which

| 场景 | 推荐方案 | 关键命令 | 适用情况 |
|------|---------|---------|---------|
| **临时静默**特定实例 | Phase 3-C | CreateMetricRuleBlackList | 已知问题，需要临时屏蔽 |
| **永久静默**特定实例 | Phase 3-C | CreateMetricRuleBlackList (无 EffectiveTime) | 实例下线，无需监控 |
| **调整告警敏感度** | Phase 3-D | PutResourceMetricRule | 误报太多或漏报 |
| **修改通知方式** | Phase 3-E | PutMetricRuleTargets | 换值班人员、加 Webhook |
| **系统事件监控** | Phase 3-F | PutEventRule | 实例重启、故障转移等 |
| **多条件复合告警** | Phase 3-G | PutResourceMetricRule + ExpressionRaw | CPU+内存同时高、多实例聚合 |
| **基于标签批量管理** | Phase 3-H | DescribeInstances + 动态 Resources | 按 env/service/team 标签批量设置 |
| **定时同步实例列表** | Phase 3-H | cron + 实例查询 + 更新 Rule | 自动扩缩容场景 |
| **排除特定实例** | Phase 3-H | 查询全部 + jq 减法过滤 | 大部分实例需要监控，少数例外 |

## Changelog
1.0.0 | 2026-06-04 | CMS GCL prompt templates — Enhanced from Phase 5 lean to
  Phase 3-B full. New: Phantom alarm Generator rules (pre-create checks),
  Phantom alarm Critic checks (post-create verification, INSUFFICIENT_DATA
  detection), Cross-skill delegation to gcl_actiontrail_crosscheck.py.
1.1.0 | 2026-06-05 | Added Phase 3-C: Alarm Blacklist (Silence/Mute) operations.
  New: CreateMetricRuleBlackList Generator/Critic rules, CLI templates for
  temporary/permanent silence, EIP/ECS scenario examples, safety gates for
  critical instances.
1.2.0 | 2026-06-05 | Added Phase 3-D~G: Alert Threshold Tuning, Notification Channel
  Management, Event Alert Handling, and Composite Expression Alerts.
  New: Comprehensive prompt templates for common alert management scenarios.
1.3.0 | 2026-06-05 | Added Phase 3-H: Dynamic Instance-Level Alert Management.
  New: Instance discovery by tags/filters, dynamic Resources JSON generation,
  batch targeting, scheduled refresh, instance exclusion patterns.
  Fix: All phases now include instance-level dynamic handling examples.
1.4.0 | 2026-06-05 | Added Self-Review & Optimization Mechanism for Phase 3-H.
  New: Auto-detection of filter issues (too strict/too broad), optimization
  recommendations with specific fixes, auto-correction workflows, optimization
  trace format. Cross-skill delegation instead of hardcoded product matrix.
1.5.0 | 2026-06-05 | Added Auto-Processing vs HITL (Human-in-the-Loop) Decision Matrix.
  New: Confidence scoring algorithm, clear HITL trigger conditions, automated
  vs manual decision boundaries, HITL workflow with interactive prompts,
  decision logging for audit trail.
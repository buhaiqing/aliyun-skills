# CLI Usage Guide for alicloud-cms-ops

## Overview

This document provides detailed CLI usage patterns for CloudMonitor (CMS)
operations. The `aliyun` CLI supports CMS core operations via the `cms`
command namespace.

## CLI Plugins and AI-Mode

Install and verify plugins idempotently before first use:

```bash
aliyun plugin install cms || true
aliyun plugin install cms2 || true
aliyun plugin update
aliyun cms --help
aliyun cms2 --help
```

## SkillOpt Integration Flags

These flags are **parsed by the SkillOpt wrapper only** (`cms-skillopt-wrapper.sh` or
`skillopt_wrap`). They are **not** native `aliyun` CLI parameters.

| Flag | Description | Default |
| --- | --- | --- |
| `--skillopt-enable` | Enable self-repair and dynamic optimization | `false` |
| `--skillopt-disable` | Disable SkillOpt | — |
| `--skillopt-log-file` | Path to SkillOpt log file | `${SKILLS_DIR}/.runtime/logs/alicloud-cms-ops/cms-skillopt-YYYYMMDD.log` |
| `--skillopt-retries` | Maximum number of repair retries | `3` |
| `--skillopt-backoff` | Backoff intervals in seconds (space-separated) | `1 2 4` |

### Example Usage

```bash
./scripts/cms-skillopt-wrapper.sh DescribeMetricList --skillopt-enable \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

Use AI-Mode during agent-driven sessions, then disable it after business
commands finish:

```bash
aliyun configure ai-mode enable
aliyun configure ai-mode set-user-agent --user-agent "AlibabaCloud-Agent-Skills/alicloud-cms-ops"
aliyun plugin update
# run CMS commands
aliyun configure ai-mode disable
```

If installation or help verification fails, run
[`cli-install-diagnosis.md`](cli-install-diagnosis.md) and fall back to SDK only
when the operation remains safe.

## CLI Coverage

### Supported Operations (Verified)

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| DescribeMetricList | `aliyun cms DescribeMetricList` | Query time-series metric data |
| DescribeMetricLast | `aliyun cms DescribeMetricLast` | Query latest metric data point |
| DescribeMetricData | `aliyun cms DescribeMetricData` | Query metric data (alternative) |
| DescribeMetricTop | `aliyun cms DescribeMetricTop` | Query top N metric values |
| PutMetricAlarm | `aliyun cms PutMetricAlarm` | Create/update alarm rule |
| DescribeMetricAlarmList | `aliyun cms DescribeMetricAlarmList` | List alarm rules |
| DeleteMetricAlarm | `aliyun cms DeleteMetricAlarm` | Delete alarm rule(s) |
| DescribeMetricMetaList | `aliyun cms DescribeMetricMetaList` | List available metrics |
| DescribeProjectMeta | `aliyun cms DescribeProjectMeta` | List supported products |
| CreateMonitorGroup | `aliyun cms CreateMonitorGroup` | Create monitor group |
| DescribeMonitorGroups | `aliyun cms DescribeMonitorGroups` | List monitor groups |
| DeleteMonitorGroup | `aliyun cms DeleteMonitorGroup` | Delete monitor group |
| PutMonitorGroupDynamicRule | `aliyun cms PutMonitorGroupDynamicRule` | Create dynamic group rule |
| DescribeMonitorGroupInstances | `aliyun cms DescribeMonitorGroupInstances` | List group instances |
| CreateMonitorGroupInstances | `aliyun cms CreateMonitorGroupInstances` | Add instances to group |
| DeleteMonitorGroupInstances | `aliyun cms DeleteMonitorGroupInstances` | Remove instances from group |
| PutCustomMetric | `aliyun cms PutCustomMetric` | Publish custom metric |
| DescribeCustomMetric | `aliyun cms DescribeCustomMetric` | Query custom metrics |
| DescribeContactGroupList | `aliyun cms DescribeContactGroupList` | List contact groups |
| PutContactGroup | `aliyun cms PutContactGroup` | Create/update contact group |
| DeleteContactGroup | `aliyun cms DeleteContactGroup` | Delete contact group |
| DescribeContactList | `aliyun cms DescribeContactList` | List contacts |
| PutContact | `aliyun cms PutContact` | Create/update contact |
| DeleteContact | `aliyun cms DeleteContact` | Delete contact |

### New in Phase 3-H: Dynamic Instance Management

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| CreateMetricRuleBlackList | `aliyun cms CreateMetricRuleBlackList` | Create alarm blacklist (silence specific instances) |
| DescribeMetricRuleBlackList | `aliyun cms DescribeMetricRuleBlackList` | List alarm blacklists |
| EnableMetricRuleBlackList | `aliyun cms EnableMetricRuleBlackList` | Enable a blacklist |
| DisableMetricRuleBlackList | `aliyun cms DisableMetricRuleBlackList` | Disable a blacklist (restore alerts) |
| DeleteMetricRuleBlackList | `aliyun cms DeleteMetricRuleBlackList` | Delete a blacklist permanently |
| PutResourceMetricRule | `aliyun cms PutResourceMetricRule` | Create/update alarm with dynamic Resources |
| PutMetricRuleTargets | `aliyun cms PutMetricRuleTargets` | Update notification targets |
| PutEventRule | `aliyun cms PutEventRule` | Create event-based alarm |
| PutEventRuleTargets | `aliyun cms PutEventRuleTargets` | Configure event notification |
| DescribeEventRuleList | `aliyun cms DescribeEventRuleList` | List event rules |
| DescribeEventList | `aliyun cms DescribeEventList` | Query historical events |

### SDK-Only Operations (CLI Coverage Gaps)

| Operation | Reason | SDK Package |
|-----------|--------|-------------|
| ExecuteQuery | CloudMonitor 2.0 ROA API | `cms-2024-03-30` |
| ContextStore operations | CloudMonitor 2.0 advanced | `cms-2024-03-30` |
| MemoryStore operations | CloudMonitor 2.0 advanced | `cms-2024-03-30` |
| Subscription operations | CloudMonitor 2.0 advanced | `cms-2024-03-30` |

## SkillOpt Integration

To enable automated self-repair and dynamic configuration optimization for CMS commands, use the following patterns:

### Direct Command Usage

SkillOpt flags are processed by the wrapper, **not** by the `aliyun` CLI itself.
Always route CMS commands through `cms-skillopt-wrapper.sh` (or the alias) when
you want self-repair and optimization.

```bash
# Enable SkillOpt for a single command
./scripts/cms-skillopt-wrapper.sh DescribeMetricList --skillopt-enable \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization \
    --Dimensions '[{"instanceId":"i-abc123"}]'

# Run without SkillOpt (native aliyun CLI, no wrapper overhead)
aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

### Using Aliases (Recommended for Persistent Sessions)
Add this to your `.bashrc` or `.zshrc` to enable SkillOpt by default for all CMS commands:
```bash
# Replace SKILLS_DIR with the actual path to aliyun-skills repo.
export SKILLS_DIR="$HOME/opensource/git/aliyun-skills"
alias aliyun-cms='source "$SKILLS_DIR/alicloud-cms-ops/scripts/skillopt-lib.sh" && skillopt_wrap cms'
```

Then use it like any standard CMS command:
```bash
aliyun-cms DescribeMetricList --skillopt-enable \
    --Namespace acs_ecs_dashboard --MetricName CPUUtilization \
    --Dimensions '[{"instanceId":"i-abc123"}]'
```

---

### Dual Optimization Capabilities
SkillOpt provides two complementary optimization layers to ensure robust and efficient CMS operations:
1. **Static Pre-Execution Optimization** (事前优化): Runs before command execution to fix parameter format errors, validate cloud resources, and check permissions proactively
2. **Dynamic Runtime Optimization** (运行时优化): Adjusts query parameters, retry strategies, and quota usage in real-time based on runtime performance, error rates, and API usage patterns

## Common Patterns

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Datapoints[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun cms DescribeMetricList --PageSize 50 | jq '{code: .Code, metrics: [.Values[]]}'
```

### Authentication

```bash
# Via environment variables (preferred)
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# Via CLI profile
aliyun configure --profile cms-profile
aliyun cms DescribeMetricList --profile cms-profile ...
```

### Output Filtering

```bash
# JSON output (default)
aliyun cms DescribeMetricList ...

# Table output with specific columns
aliyun cms DescribeMetricAlarmList ... \
  --output cols=AlarmName,Namespace,MetricName,State rows=AlarmList.Alarm[]

# JMESPath filter (default JSON output already)
aliyun cms DescribeMetricList ... \
  --filter "Datapoints[?Average > `80`]"
```

### Pagination

```bash
# Auto-pagination with --pager
aliyun cms DescribeMetricAlarmList --pager

# Manual pagination
aliyun cms DescribeMetricAlarmList --PageSize 100 --PageNumber 1
aliyun cms DescribeMetricAlarmList --PageSize 100 --PageNumber 2
```

### Time Range Patterns

```bash
# Last hour (cross-platform compatible; works on Linux/macOS)
aliyun cms DescribeMetricList \
  --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Specific time range
aliyun cms DescribeMetricList \
  --StartTime "2026-05-14T00:00:00Z" \
  --EndTime "2026-05-14T23:59:59Z"
```

## Examples

### Example 1: Query ECS CPU Usage

```bash
aliyun cms DescribeMetricList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Period 60 \
  --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Dimensions '[{"instanceId":"i-abcdefgh1234567890"}]'
```

### Example 2: Create CPU Alarm Rule

```bash
aliyun cms PutMetricAlarm \
  --RegionId cn-hangzhou \
  --AlarmName "ECS-High-CPU" \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-abcdefgh1234567890"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 80 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["ops-team"]' \
  --EffectiveInterval "00:00-23:59"
```

### Example 3: List All Alarm Rules

```bash
aliyun cms DescribeMetricAlarmList \
  --RegionId cn-hangzhou \
  --PageSize 50 \
  --PageNumber 1
```

### Example 4: Query Available Metrics for ECS

```bash
aliyun cms DescribeMetricMetaList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard
```

### Example 5: Publish Custom Metric

```bash
aliyun cms PutCustomMetric \
  --RegionId cn-hangzhou \
  --MetricList '[{"metricName":"custom_app_latency","namespace":"acs_custom","dimensions":{"service":"api-gateway"},"value":120,"timestamp":$(date +%s)000}]'
```

## Error Handling

| Error | CLI Output | Action |
|-------|-----------|--------|
| `Throttling.User` | `Request was denied due to user flow control` | Wait 5s, retry |
| `InvalidParameter` | `The specified parameter is invalid` | Check parameter values |
| `ResourceNotFound` | `The specified resource is not found` | Verify resource ID |
| `Forbidden` | `User not authorized` | Check RAM permissions |

## Advanced: Dynamic Instance Management (Phase 3-H)

### Cross-Product Instance Discovery Pattern

**Principle**: Don't hardcode product-specific queries. Use skill delegation to get dynamic parameters.

```bash
# Generic pattern (product-agnostic)
# 1. Get query parameters from skill delegation
# 2. Build and execute query dynamically
# 3. Transform to CMS Resources format

# Step 1: Query instances (example: ECS)
OUTPUT=$(aliyun {{product}} {{query_command}} \
  --RegionId {{region_id}} \
  --Tag '[{"Key":"{{tag_key}}","Value":"{{tag_value}}"}]' \
  --{{status_param}} {{status_value}} \
  --PageSize 100 \
  --output cols={{id_field}} rows={{jmespath}})

# Step 2: Extract and transform
INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE '{{id_pattern}}')
RESOURCES=$(echo "$INSTANCE_IDS" | jq -R -s -c \
  'split("\n")[:-1] | map({"{{resource_key}}": .})')

# Step 3: Create alarm
aliyun cms PutResourceMetricRule \
  --RuleName "{{alarm_name}}" \
  --Namespace "{{namespace}}" \
  --MetricName "{{metric_name}}" \
  --Resources "$RESOURCES" \
  ...
```

### Example 6: Alarm Blacklist (Silence Specific Instances)

```bash
# Create temporary blacklist (24h silence)
aliyun cms CreateMetricRuleBlackList \
  --Name "EIP-eip-xxx-Temporary-Silence" \
  --Namespace "acs_vpc_eip" \
  --MetricName "OutBandwidthDropRate" \
  --Resources '["eip-uf6xii12c69nz0x5e718o"]' \
  --Scope "USER" \
  --EffectiveTime "2026-06-05T15:00:00Z/2026-06-06T15:00:00Z" \
  --RegionId cn-shanghai

# Query blacklist
aliyun cms DescribeMetricRuleBlackList \
  --RegionId cn-shanghai \
  --Namespace acs_vpc_eip

# Disable blacklist (restore alerts)
aliyun cms DisableMetricRuleBlackList \
  --BlackListId "blacklist-xxx" \
  --RegionId cn-shanghai

# Delete blacklist
aliyun cms DeleteMetricRuleBlackList \
  --BlackListId "blacklist-xxx" \
  --RegionId cn-shanghai
```

### Example 7: Dynamic Instance Targeting with Tag Filter

```bash
#!/bin/bash
# Dynamic instance discovery and alarm creation

REGION="cn-hangzhou"
ALARM_NAME="Production-ECS-CPU-Dynamic"

# Step 1: Discover instances by tag
OUTPUT=$(aliyun ecs DescribeInstances \
  --RegionId $REGION \
  --Tag '[{"Key":"env","Value":"production"}]' \
  --Status Running \
  --PageSize 100 \
  --output cols=InstanceId rows=Instances.Instance[])

# Step 2: Extract instance IDs
INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
COUNT=$(echo "$INSTANCE_IDS" | wc -l)

echo "Discovered $COUNT instances"

# Step 3: Validate count (safety check)
if [ "$COUNT" -eq 0 ]; then
  echo "ERROR: No instances match filter criteria"
  exit 1
elif [ "$COUNT" -gt 100 ]; then
  echo "WARNING: Large instance set ($COUNT), consider adding more filters"
  # HITL: Pause for manual confirmation
  read -p "Continue? (y/n) " confirm
  [ "$confirm" != "y" ] && exit 0
fi

# Step 4: Transform to Resources JSON
RESOURCES=$(echo "$INSTANCE_IDS" | jq -R -s -c \
  'split("\n")[:-1] | map({instanceId: .})')

# Step 5: Create alarm with dynamic resources
aliyun cms PutResourceMetricRule \
  --RuleName "$ALARM_NAME" \
  --Namespace "acs_ecs_dashboard" \
  --MetricName "cpu_total" \
  --Resources "$RESOURCES" \
  --Escalations.Critical.Statistics "Average" \
  --Escalations.Critical.ComparisonOperator "GreaterThanThreshold" \
  --Escalations.Critical.Threshold "90" \
  --Escalations.Critical.Times 3 \
  --Period 60 \
  --ContactGroups '["ops-team"]' \
  --RegionId $REGION

echo "Alarm created successfully for $COUNT instances"
```

### Example 8: Auto-Correction on Zero Instances

```bash
#!/bin/bash
# Auto-correction when filter returns zero instances

REGION="cn-hangzhou"
TAG_KEY="env"
TAG_VALUE="production"

echo "Attempting to query instances with Tag[$TAG_KEY]=$TAG_VALUE"

# First attempt (may have case issues)
OUTPUT=$(aliyun ecs DescribeInstances \
  --RegionId $REGION \
  --Tag "[{\"Key\":\"$TAG_KEY\",\"Value\":\"$TAG_VALUE\"}]" \
  --Status Running \
  --PageSize 100)

INSTANCE_IDS=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+')
COUNT=$(echo "$INSTANCE_IDS" | wc -l)

# Auto-correction: Fix common issues
if [ "$COUNT" -eq 0 ]; then
  echo "No instances found. Attempting auto-correction..."
  
  # Try 1: Lowercase tag key
  echo "Try 1: Using lowercase tag key..."
  OUTPUT=$(aliyun ecs DescribeInstances \
    --RegionId $REGION \
    --Tag '[{"Key":"env","Value":"production"}]' \
    --PageSize 100)
  COUNT=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+' | wc -l)
  
  if [ "$COUNT" -gt 0 ]; then
    echo "✓ Success with lowercase tag key: $COUNT instances"
  else
    # Try 2: Remove status filter
    echo "Try 2: Removing status filter..."
    OUTPUT=$(aliyun ecs DescribeInstances \
      --RegionId $REGION \
      --Tag '[{"Key":"env","Value":"production"}]' \
      --PageSize 100)
    COUNT=$(echo "$OUTPUT" | grep -oE 'i-[a-z0-9]+' | wc -l)
    
    if [ "$COUNT" -gt 0 ]; then
      echo "✓ Success without status filter: $COUNT instances"
      echo "⚠ Warning: May include stopped instances"
    else
      echo "✗ Auto-correction failed. Manual intervention required."
      exit 1
    fi
  fi
fi

# Proceed with alarm creation...
```

### Example 9: Scheduled Instance List Refresh

```bash
#!/bin/bash
# Cron job: Refresh alarm rule instance list hourly

REGION="cn-hangzhou"
ALARM_NAME="Auto-Refresh-Alarm"
RULE_ID="rule-xxx"  # Get from DescribeMetricAlarmList

# Query current instances
NEW_INSTANCES=$(aliyun ecs DescribeInstances \
  --RegionId $REGION \
  --Tag '[{"Key":"auto-alert","Value":"enabled"}]' \
  --Status Running \
  --PageSize 100 | \
  grep -oE 'i-[a-z0-9]+' | \
  jq -R -s -c 'split("\n")[:-1] | map({instanceId: .})')

NEW_COUNT=$(echo "$NEW_INSTANCES" | jq '. | length')
echo "Found $NEW_COUNT current instances"

# Get existing alarm resources
CURRENT=$(aliyun cms DescribeMetricAlarmList \
  --AlarmName "$ALARM_NAME" \
  --RegionId $REGION \
  --output json)

CURRENT_COUNT=$(echo "$CURRENT" | jq -r '.AlarmList.Alarm[0].Resources | length')
echo "Alarm currently has $CURRENT_COUNT instances"

# Compare and update if different
if [ "$NEW_COUNT" -ne "$CURRENT_COUNT" ]; then
  echo "Instance count changed ($CURRENT_COUNT → $NEW_COUNT), updating alarm..."
  
  aliyun cms PutResourceMetricRule \
    --RuleId "$RULE_ID" \
    --RuleName "$ALARM_NAME" \
    --Namespace "acs_ecs_dashboard" \
    --MetricName "cpu_total" \
    --Resources "$NEW_INSTANCES" \
    --RegionId $REGION
  
  echo "✓ Alarm updated with new instance list"
else
  echo "No change in instance count"
fi
```

### Example 10: Event-Based Alert

```bash
# Create event rule for instance reboot
aliyun cms PutEventRule \
  --RuleName "ECS-Reboot-Event-Alert" \
  --EventType "ecs" \
  --GroupId "245146569" \
  --EventPattern '{"eventName": ["Instance:Reboot", "Instance:Redeploy"]}' \
  --Level "WARN" \
  --Status "ENABLED" \
  --RegionId cn-hangzhou

# Configure notification
aliyun cms PutEventRuleTargets \
  --RuleName "ECS-Reboot-Event-Alert" \
  --ContactGroups '["ops-team"]' \
  --RegionId cn-hangzhou

# Query recent events
aliyun cms DescribeEventList \
  --EventType "ecs" \
  --StartTime "2026-06-01T00:00:00Z" \
  --EndTime "2026-06-05T23:59:59Z" \
  --PageSize 100 \
  --RegionId cn-hangzhou
```

### Example 11: Composite Expression Alert

```bash
# Multi-condition alert: CPU > 80 AND Memory > 90
aliyun cms PutResourceMetricRule \
  --RuleName "ECS-High-Resource-Combined" \
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

# Instance-specific thresholds
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

## Auto-Processing vs HITL Decision Framework

When implementing dynamic instance management, use this framework:

### Confidence Scoring

```bash
# Calculate confidence before execution
calculate_confidence() {
  local count=$1
  local is_critical=$2
  local confidence=0
  
  # Instance count range (10-50 is optimal)
  if [ "$count" -ge 10 ] && [ "$count" -le 50 ]; then
    confidence=$((confidence + 25))
  fi
  
  # Filter explicitness
  confidence=$((confidence + 20))
  
  # Environment (non-critical = +20)
  if [ "$is_critical" != "true" ]; then
    confidence=$((confidence + 20))
  fi
  
  # Standard operation (+15)
  confidence=$((confidence + 15))
  
  # Rollback ready (+10)
  confidence=$((confidence + 10))
  
  echo $confidence
}

# Usage
COUNT=25
IS_CRITICAL="false"
CONFIDENCE=$(calculate_confidence $COUNT $IS_CRITICAL)

echo "Confidence Score: $CONFIDENCE/100"

if [ "$CONFIDENCE" -ge 80 ]; then
  echo "✓ AUTO-PROCESS: Executing with confidence"
  # Execute alarm creation
else
  echo "🛑 HITL REQUIRED: Manual confirmation needed"
  # HITL workflow
fi
```

## References

- [Alibaba Cloud CLI Documentation](https://help.aliyun.com/zh/cli/)
- [CMS CLI Integration Example](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/cli-integration-example)
- [OpenAPI Portal - CMS](https://api.aliyun.com/api/Cms/2019-01-01)

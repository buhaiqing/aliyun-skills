# Monitoring & AIOps — Function Compute (FC 3.0)

## Key Metrics (CloudMonitor)

| Metric | MetricName (CMS) | Unit | Description |
|--------|-------------------|------|-------------|
| Total invocations | FunctionTotalInvocations | Count | Sum of all invocations |
| Function errors | FunctionFunctionErrors | Count | Errors from function code |
| Client errors | FunctionClientErrors | Count | Errors from client request |
| Server errors | FunctionServerErrors | Count | FC platform errors |
| Avg duration | FunctionAvgDuration | Millisecond | Mean execution time |
| P90 duration | FunctionP90Duration | Millisecond | 90th percentile |
| Max duration | FunctionMaxDuration | Millisecond | Maximum execution time |
| Max memory usage | FunctionMaxMemoryUsageMB | MB | Peak memory per instance |
| Avg memory usage | FunctionAvgMemoryUsageMB | MB | Average memory per instance |
| Max memory utilization | FunctionMaxMemoryUtilization | % | Peak memory / allocated |
| Avg memory utilization | FunctionAvgMemoryUtilization | % | Average memory / allocated |

**Additional:**
- FunctionProvisionInvocations — invocations on provisioned instances
- FunctionConcurrencyThrottles — throttled due to concurrency limit
- FunctionResourceThrottles — throttled due to resource limit
- FunctionDequeueCount — async invocation dequeue count
- FunctionInstanceCount — number of running instances
- FunctionInstanceProvisionCount — number of provisioned instances

## Alert Example

```bash
# Via CMS CLI
aliyun cms PutContactGroup --ContactGroupName "fc-ops-team" --ContactNames "ops-admin"
aliyun cms PutMetricRuleTemplate --Name "FC Critical" \
  --AlarmResources "arn:acs:fc:cn-hangzhou::functions/*" \
  --Namespace "acs_fc" \
  --MetricName "FunctionFunctionErrors" \
  --Threshold 10 \
  --ComparisonOperator ">=" \
  --EvaluationCount 3 \
  --Statistics "Average" \
  --Period 300
```

## AIOps Multi-Metric Anomaly Inspection (L2+)

FC-specific anomaly patterns for proactive inspection:

### Pattern 1: Cold Start Impact

```
Condition: FunctionMaxDuration >> FunctionAvgDuration (p95 > 5x avg)
Interpretation: Cold start dominating execution time
```

**Action:**
- Consider provisioned instances for latency-sensitive functions
- Increase memory allocation (higher memory = faster init)
- Reduce package size / use layers

### Pattern 2: Memory Pressure

```
Condition: FunctionMaxMemoryUtilization > 85% OR FunctionMaxMemoryUsageMB approaching limit
Interpretation: Risk of OOM errors (exit status 1)
```

**Action:**
- Increase `memorySize` config (up to 3072 MB)
- Profile function for memory leaks
- Use 10240 MB disk if working with large datasets

### Pattern 3: Throttle Cascade

```
Condition: FunctionConcurrencyThrottles > 0 OR FunctionResourceThrottles > 0
Interpretation: Concurrency or resource limit hit — cascading failures possible
```

**Action:**
- Review `maxConcurrency` setting per function
- Request account-level concurrency increase
- Consider provisioned instances for baseline traffic

### Pattern 4: Error Spike

```
Condition: FunctionFunctionErrors > 0 AND FunctionTotalInvocations stable/rising
Interpretation: Function code regression or downstream dependency failure
```

**Action:**
- Check recent code version deployments
- Review async retry config
- Check downstream service health

### Pattern 5: Duration Degradation

```
Condition: FunctionAvgDuration trending upward over 24h+
Interpretation: Performance regression or resource saturation
```

**Action:**
- Review code changes
- Check if hitting timeout limit
- Profile cold vs warm start durations

### Pattern 6: Idle Resource Waste

```
Condition: FunctionInstanceProvisionCount > 0 AND FunctionTotalInvocations ≈ 0 (24h)
Interpretation: Paying for unused provisioned capacity
```

**Action:**
- Reduce or remove provisioned instance count
- Set up cost alert for idle function detection

## Recommended Alert Thresholds

| Metric | Warning | Critical | Recovery |
|--------|---------|----------|----------|
| FunctionFunctionErrors | > 10/5min | > 50/5min | 2min sustained below warning |
| FunctionClientErrors | > 20/5min | > 100/5min | 2min sustained below warning |
| FunctionMaxDuration | > 90% of timeout | > timeout | — |
| FunctionMaxMemoryUtilization | > 80% | > 95% | < 90% for 5min |
| FunctionConcurrencyThrottles | > 5/5min | > 20/5min | 0 for 2min |
| FunctionResourceThrottles | > 0 | > 5/5min | 0 for 2min |

## CLI Monitoring Integration

Query FC metrics via CMS API:

```bash
# Query function-level metric
aliyun cms DescribeMetricList \
  --Namespace "acs_fc" \
  --MetricName "FunctionTotalInvocations" \
  --Period 300 \
  --StartTime "2026-05-18 00:00:00" \
  --EndTime "2026-05-18 01:00:00" \
  --Dimensions '[{"functionName": "my-function"}]'
```

## Proactive Inspection (AIOps L3+)

1. **List all functions**: `ListFunctions` via SDK or `fc-open GET`
2. **For each function**, query last 24h metrics for:
   - `FunctionTotalInvocations`
   - `FunctionFunctionErrors`
   - `FunctionMaxMemoryUtilization`
   - `FunctionMaxDuration`
3. **Apply anomaly patterns** (above)
4. **Cross-skill delegation**:
   - If RDS/Redis connectivity suspected → `alicloud-das-ops`
   - If network issue → VPC skill
   - If RAM issue → `alicloud-ram-ops`
5. **Generate inspection report** with optimization recommendations

## CLI Monitoring Integration — Multi-Metric Queries

Query FC metrics via CMS API for anomaly inspection:

```bash
# Query cold start metrics (InitialDuration)
aliyun cms DescribeMetricList --Namespace acs_fc \
  --MetricName InitialDuration \
  --Dimensions '[{"functionName":"{{user.function_name}}"}]' \
  --Period 60 --Length 300

# Query error count
aliyun cms DescribeMetricList --Namespace acs_fc \
  --MetricName FunctionErrors \
  --Dimensions '[{"functionName":"{{user.function_name}}"}]' \
  --Period 60 --Length 300

# Query throttling
aliyun cms DescribeMetricList --Namespace acs_fc \
  --MetricName Throttles \
  --Dimensions '[{"functionName":"{{user.function_name}}"}]' \
  --Period 60 --Length 300

# Query duration (p50/p95/p99)
aliyun cms DescribeMetricList --Namespace acs_fc \
  --MetricName FunctionDuration \
  --Dimensions '[{"functionName":"{{user.function_name}}"}]' \
  --Period 60 --Length 300
```

### Recovery & Cross-Skill Delegation

| Pattern Detected | Primary Action | Delegate To |
|-----------------|----------------|-------------|
| MemoryPressure | Recommend memory increase | Memory right-sizing analysis |
| ThrottleCascade | Check concurrency config | Increase function concurrency limit |
| ErrorRateSpike | Check function state + logs | `alicloud-sls-ops` (if present) |
| IdleResourceWaste | Recommend removing provisioned | Cost optimization review |
| ColdStartBurst | Add provisioned instance or optimize code | Performance analysis |

## Alert-Driven Diagnosis (AIOps 5-Step Decision Tree)

```
[FC Alert Triggered]
    │
    ├── Step 1: Verify Alert Validity
    │   Check current metric value vs threshold
    │   └─ False positive? → Check CMS alert rule config
    │
    ├── Step 2: Check Function Status
    │   GetFunction → verify state=ACTIVE, lastUpdateStatus=SUCCESSFUL
    │   └─ State=FAILED? → Check stateReason, stateReasonCode
    │
    ├── Step 3: Multi-Metric Correlation
    │   Query all 8 FC CMS metrics
    │   Match against anomaly patterns (above table)
    │
    ├── Step 4: Deep Diagnosis
    │   Check async task status, provisioned config, VPC config
    │   └─ If function connects to RDS → delegate to DAS
    │
    └── Step 5: Unified Diagnostic Report
        Generate report with root cause + fix + risk assessment
```

### Diagnostic Report Schema

```
## FC Diagnostic Report — {{user.function_name}}

### Alert Summary
- Triggered rule: {{output.alert_rule}}
- Metric: {{output.metric_name}} = {{output.metric_value}} (threshold: {{output.threshold}})

### Function Status
- State: {{output.state}}
- Last update: {{output.last_update}}
- Memory: {{output.memory}} MB, Timeout: {{output.timeout}}s

### Anomaly Patterns Detected
- [Pattern name]: [severity] — [interpretation]

### Root Cause
[Identified root cause with confidence level]

### Recommended Actions
1. [Specific, actionable step]
2. [Follow-up step]

### Cost Impact
[If applicable: estimate of cost waste or optimization savings]
```
# Prompts Handbook — FC 3.0

## Metrics Query Prompts

### Metric: Function invocations (single function)
```
Query all FC invocations for function "{{user.function_name}}" in region "{{env.ALIBABA_CLOUD_REGION_ID}}" over the last {{user.time_range|default:"1 hour"}}.
Use CMS namespace "acs_fc", metric "FunctionTotalInvocations", period 300s.
```

### Metric: Memory utilization trend
```
Query FC memory utilization for function "{{user.function_name}}" over the last {{user.time_range}}.
Include FunctionMaxMemoryUtilization and FunctionMaxMemoryUsageMB. Identify if utilization exceeds 85%.
```

### Metric: Throttling analysis
```
Query FC throttling for function "{{user.function_name}}" over the last {{user.time_range}}.
Include FunctionConcurrencyThrottles and FunctionResourceThrottles. Identify throttling patterns and peak periods.
```

### Multi-metric: All function metrics batch
```
For ALL FC functions in region "{{env.ALIBABA_CLOUD_REGION_ID}}", query the following metrics over the last {{user.time_range|default:"24 hours"}}:
1. FunctionTotalInvocations
2. FunctionFunctionErrors
3. FunctionMaxMemoryUtilization
4. FunctionAvgDuration and FunctionP90Duration
5. FunctionConcurrencyThrottles
Return results grouped by function name, sorted by error rate.
```

## Alert Management Prompts

### Create alert rule: function errors
```
Create a CMS alert rule for FC function "{{user.function_name}}" errors:
- Metric: FunctionFunctionErrors
- Threshold: > 10 per 5 minutes
- Evaluation count: 3 consecutive periods
- Alert group: fc-ops-team
```

### Create alert rule: memory utilization
```
Create a CMS alert rule for FC function "{{user.function_name}}" memory:
- Metric: FunctionMaxMemoryUtilization
- Threshold: > 85%
- Severity: Warning
```

## Anomaly Diagnosis Prompts

### Diagnose cold start issue
```
Analyze function "{{user.function_name}}" for cold start impact:
1. Compare FunctionP90Duration with FunctionAvgDuration
2. If p90 > 5x avg, investigate cold start as root cause
3. Check provisioned instance config
4. Recommend optimization steps
```

### Diagnose throttle cascade
```
Analyze function "{{user.function_name}}" for throttling:
1. Query FunctionConcurrencyThrottles over last 1 hour
2. Check maxConcurrency limit vs actual concurrent executions
3. Recommend limit adjustment or provisioned instances
```

## Proactive Inspection Prompts

### Weekly inspection
```
Run a proactive inspection of ALL FC functions in region "{{env.ALIBABA_CLOUD_REGION_ID}}":
1. List all functions
2. For each, check last 24h metrics: invocations, errors, memory, duration
3. Apply all anomaly patterns
4. Flag functions with idle provisioned instances
5. Generate optimization recommendations report
```

### Cost optimization review
```
Review FC functions for cost optimization:
1. List all provisioned instance configs
2. Cross-reference with last 7d invocation counts
3. Identify functions with provisioned instances but < 100 invocations
4. Calculate potential savings from removing idle provisioned instances
5. Recommend memory right-sizing for functions with < 30% memory utilization
```

## Multi-Round Self-Review Prompts

## Deploy & Lifecycle Prompts

### Package and upload to OSS
```
Package the local source code at "{{user.source_dir}}" for FC deployment:
1. Create a zip, excluding node_modules/ or other build artifacts
2. Upload to OSS bucket "{{user.oss_bucket}}" under prefix "{{user.oss_prefix}}"
3. Verify the uploaded object exists and is accessible
```

### Deploy from source (end-to-end)
```
Deploy function "{{user.function_name}}" to FC in region "{{env.ALIBABA_CLOUD_REGION_ID}}":
1. Package local source from "{{user.source_dir}}" and upload to OSS
2. If function exists, update code; otherwise create new function with runtime "{{user.runtime}}"
3. Set memorySize "{{user.memory_mb|default:512}}" and timeout "{{user.timeout|default:60}}"
4. Wait for function to become ACTIVE
5. Trigger a test invocation with payload '{"test": true}'
6. Report result: function name, state, and invocation response
```

### Hot update function code
```
Update code for existing FC function "{{user.function_name}}":
1. Upload new package to OSS as "{{user.oss_prefix}}/{{user.function_name}}-v2.zip"
2. Call UpdateFunction with code field pointing to new OSS object
3. Verify function state transitions to ACTIVE
4. Test invocation to confirm new code works
```

### Add trigger to function
```
Add a {{user.trigger_type|default:"timer"}} trigger to FC function "{{user.function_name}}":
- Trigger name: "{{user.trigger_name}}"
- Configure trigger with appropriate settings
- Verify trigger is created and enabled
```

### Round 1 diagnostic
```
Initial diagnosis for FC function "{{user.function_name}}":
- Collect 24h metrics
- Check function config
- Identify top anomaly pattern
```

### Round 2 critical reflection (if Round 1 unclear)
```
Re-evaluate the initial diagnosis:
- Are there alternative root causes?
- Could this be a cascading failure from another function?
- Has there been a recent deployment that matches the timing?
- Check async invocation status and DLQ
```

### Round 3 deep investigation (if Round 2 still unclear)
```
Deep investigation for FC function "{{user.function_name}}":
- Query function invocation logs in SLS
- Check downstream service health (RDS, Redis, external APIs)
- Review VPC network connectivity
- Check RAM execution role permissions
- Generate final root cause assessment with confidence level
```
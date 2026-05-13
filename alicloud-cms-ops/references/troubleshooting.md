# Troubleshooting Guide for alicloud-cms-ops

## Common Issues

### Issue 1: Throttling / Rate Limiting

**Symptoms:**
- Error: `Throttling.User` or `Request was denied due to user flow control`
- API calls fail intermittently

**Root Cause:**
- CMS metric query APIs share a quota of **1,000,000 calls/month** (free tier)
- Per-API limit: **50 calls/second** per account

**Resolution:**
1. Implement exponential backoff: 1s → 2s → 4s → max 3 retries
2. Reduce query frequency or batch requests
3. Enable CloudMonitor pay-as-you-go if quota exceeded
4. Use longer Period values (300s instead of 60s) to reduce call volume

**Prevention:**
- Cache metric data when possible
- Use DescribeMetricLast instead of DescribeMetricList for latest values
- Implement client-side rate limiting

---

### Issue 2: No Metric Data Returned

**Symptoms:**
- `DescribeMetricList` returns empty `Datapoints` array
- `Success: true` but no data

**Root Causes & Resolution:**

| Cause | Check | Fix |
|-------|-------|-----|
| Instance not running | Instance state | Start the instance |
| Wrong namespace | `DescribeProjectMeta` | Use correct namespace (e.g., `acs_ecs_dashboard`) |
| Wrong metric name | `DescribeMetricMetaList` | Use valid metric name |
| Wrong dimensions | Dimension format | Use correct JSON format: `[{"instanceId":"i-xxx"}]` |
| Time range too old | Data retention | Period <60s: 7 days; 60s: 31 days; ≥300s: 91 days |
| Instance just created | Data collection delay | Wait 5-10 minutes for first data point |
| Region mismatch | Instance region | Query the correct region |

**Debug Steps:**
```bash
# 1. Verify namespace
aliyun cms DescribeProjectMeta --RegionId cn-hangzhou

# 2. Verify metric exists
aliyun cms DescribeMetricMetaList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard

# 3. Check instance exists and running
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --InstanceIds '["i-xxx"]'

# 4. Query with broader time range
aliyun cms DescribeMetricList \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Period 300 \
  --StartTime "$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Dimensions '[{"instanceId":"i-xxx"}]'
```

---

### Issue 3: Alarm Rule Not Triggering

**Symptoms:**
- Alarm rule exists but no notifications received
- State shows `OK` when it should be `ALARM`

**Root Causes & Resolution:**

| Cause | Check | Fix |
|-------|-------|-----|
| Evaluation count not met | `--EvaluationCount` | Reduce from 3 to 1 for testing |
| Threshold too high/low | Metric values | Adjust threshold based on actual data |
| Effective interval | `--EffectiveInterval` | Ensure current time is within interval |
| Alarm disabled | `--EnableState` | Set to `true` |
| Contact group empty | `DescribeContactGroupList` | Add contacts to group |
| MNS topic not found | MNS console | Create topic or use correct ARN |
| Silence period | Alarm history | Check if in silence period |

**Debug Steps:**
```bash
# 1. Check alarm rule details
aliyun cms DescribeMetricAlarmList \
  --RegionId cn-hangzhou \
  --AlarmName "your-alarm-name"

# 2. Check current metric values
aliyun cms DescribeMetricLast \
  --RegionId cn-hangzhou \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"i-xxx"}]'

# 3. Verify contact group
aliyun cms DescribeContactGroupList --RegionId cn-hangzhou
```

---

### Issue 4: Permission Denied (Forbidden)

**Symptoms:**
- Error: `Forbidden` or `User not authorized`
- Error: `NoPermission`

**Root Cause:**
- RAM user lacks CloudMonitor permissions

**Resolution:**
1. Attach policy `AliyunCloudMonitorReadOnlyAccess` for read operations
2. Attach policy `AliyunCloudMonitorFullAccess` for write operations
3. For custom policies, ensure these actions are allowed:
   - `cms:DescribeMetricList`
   - `cms:DescribeMetricLast`
   - `cms:PutMetricAlarm`
   - `cms:DescribeMetricAlarmList`
   - `cms:DeleteMetricAlarm`
   - `cms:DescribeMetricMetaList`

**Verify Permissions:**
```bash
aliyun ram ListPoliciesForUser --UserName your-username
```

---

### Issue 5: InvalidParameter Errors

**Symptoms:**
- Error: `InvalidParameter` with various messages

**Common Causes:**

| Parameter | Common Mistake | Correct Format |
|-----------|---------------|----------------|
| Dimensions | Wrong JSON format | `[{"instanceId":"i-xxx"}]` |
| Period | Unsupported value | 15, 60, 300, 900, 3600 |
| Statistics | Wrong value | Average, Minimum, Maximum, Value |
| ComparisonOperator | Wrong format | `>`, `>=`, `<`, `<=`, `==`, `!=` |
| StartTime/EndTime | Wrong format | `2026-05-14T10:00:00Z` |
| ContactGroups | Wrong JSON format | `["group1","group2"]` |
| AlarmActions | Wrong ARN format | `acs:mns:region:account:topics/topic-name` |

---

### Issue 6: CLI Not Found or Outdated

**Symptoms:**
- `command not found: aliyun`
- CLI version too old, missing CMS commands

**Resolution:**
```bash
# Check version
aliyun version

# Update CLI
brew upgrade aliyun-cli  # macOS
# Or re-run installer
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# Verify CMS support
aliyun cms --help
```

---

### Issue 7: SDK Import Errors

**Symptoms:**
- Go build fails with `module not found`
- Import path errors

**Resolution:**
```bash
# Initialize module
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Get dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea/tea
go get github.com/alibabacloud-go/cms-20190101/v7/client

# For CloudMonitor 2.0
go get github.com/alibabacloud-go/cms-2024-03-30/v2/client
```

---

## Diagnostic Commands

### Full System Check

```bash
#!/bin/bash
# cms-health-check.sh

echo "=== CMS Health Check ==="

# 1. CLI version
echo "1. CLI Version:"
aliyun version

# 2. Credentials
echo -e "\n2. Credentials:"
echo "AK_ID: ${ALIBABA_CLOUD_ACCESS_KEY_ID:0:4}****"
echo "AK_SECRET: ${ALIBABA_CLOUD_ACCESS_KEY_SECRET:+<set>}"
echo "REGION: ${ALIBABA_CLOUD_REGION_ID}"

# 3. List supported products
echo -e "\n3. Supported Products:"
aliyun cms DescribeProjectMeta --RegionId ${ALIBABA_CLOUD_REGION_ID}

# 4. List alarm rules
echo -e "\n4. Alarm Rules:"
aliyun cms DescribeMetricAlarmList \
  --RegionId ${ALIBABA_CLOUD_REGION_ID} \
  --PageSize 10

# 5. List contact groups
echo -e "\n5. Contact Groups:"
aliyun cms DescribeContactGroupList --RegionId ${ALIBABA_CLOUD_REGION_ID}

echo -e "\n=== Check Complete ==="
```

---

## Root-Cause Diagnosis Decision Tree (AIOps)

> This section provides **cross-skill root-cause diagnosis flows** triggered by CMS alarms. Each scenario follows the 5-step protocol: Verify → Resource Check → Multi-Metric Correlation → Deep Diagnosis → Report.

---

### Scenario 1: ECS High CPU Alarm

Triggered by: `CPUUtilization >= Threshold` on `acs_ecs_dashboard`

#### Step 1: Verify Alarm Validity
```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```
**If metric < threshold:** False positive → Check alarm rule `EvaluationCount` and `Statistics`

#### Step 2: Check Resource Status (Delegate to alicloud-ecs-ops)
```bash
aliyun ecs DescribeInstances \
  --RegionId {{user.region}} \
  --InstanceIds '["{{user.instance_id}}"]'
```
**If status != Running:** Resource stopped → Start instance or investigate

#### Step 3: Multi-Metric Correlation
```bash
for metric in MemoryUsage DiskUsage LoadAverage InternetInRate InternetOutRate; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} \
    --Namespace acs_ecs_dashboard \
    --MetricName "$metric" \
    --Period 300 \
    --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```

| Correlated Pattern | Interpretation | Next Action |
|-------------------|----------------|-------------|
| CPU + Memory both high | Resource exhaustion | Consider scale-up |
| CPU high, Load high, CPU < 50% | IO wait (disk bottleneck) | Check DiskUsage and IOPSUsage |
| CPU spike + Network spike | Traffic surge | Check SLB; consider auto-scaling |
| CPU high alone | Runaway process | Delegate to ECS for process-level diagnosis |

#### Step 4: Deep Diagnosis (Optional)
If pattern indicates deep issue, delegate to DAS for AI diagnosis.

#### Step 5: Compile Report
```markdown
## Diagnosis Report: ECS High CPU
- Resource: {{user.instance_id}}
- Status: (from Step 2)
- CPU Trend: (from Step 1 + 3)
- Correlated Patterns: (from Step 3)
- Root Cause: (synthesized)
- Recommendation: (actionable)
```

---

### Scenario 2: RDS ConnectionUsage Alarm

Triggered by: `ConnectionUsage >= Threshold` on `acs_rds_dashboard`

#### Step 1: Verify Alarm Validity
```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_rds_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```

#### Step 2: Check Resource Status (Delegate to alicloud-rds-ops)
```bash
aliyun rds DescribeDBInstances \
  --RegionId {{user.region}} \
  --DBInstanceId {{user.instance_id}}
```

#### Step 3: Multi-Metric Correlation
```bash
for metric in CpuUsage MemoryUsage DiskUsage IOPSUsage; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} \
    --Namespace acs_rds_dashboard \
    --MetricName "$metric" \
    --Period 300 \
    --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```

| Correlated Pattern | Interpretation | Next Action |
|-------------------|----------------|-------------|
| ConnectionUsage high, CPUUsage low | Sleeping connections / connection leak | Check connection pool; delegate to DAS |
| ConnectionUsage + CPUUsage both high | Active query overload | Delegate to DAS for slow query analysis |
| ConnectionUsage high, IOPSUsage high | Query causing high IO | Check indexes; delegate to DAS |

#### Step 4: Deep Diagnosis (Delegate to alicloud-das-ops — **Recommended**)
```bash
# DAS: GetInstanceInspections (health score)
# DAS: CreateDiagnosticReport (SQL/performance diagnosis)
# DAS: CreateLatestDeadLockAnalysis (deadlock check)
# DAS: GetQueryOptimizeData (query governance)
```

---

### Scenario 3: SLB DropConnection Alarm

Triggered by: `DropConnection > 0` on `acs_slb_dashboard`

#### Step 1: Verify Alarm Validity
```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_slb_dashboard \
  --MetricName DropConnection \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
```

#### Step 2: Check SLB Status (Delegate to alicloud-slb-ops)
```bash
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId {{user.instance_id}}
```

#### Step 3: Check Backend Server Health
```bash
aliyun slb DescribeVServerGroups --LoadBalancerId {{user.instance_id}}
aliyun slb DescribeVServerGroupAttribute --VServerGroupId {{user.vserver_group_id}}
```

#### Step 4: If Backend Unhealthy → Delegate to alicloud-ecs-ops
```bash
aliyun ecs DescribeInstances \
  --RegionId {{user.region}} \
  --InstanceIds '["{{user.backend_server_id}}"]'
```

| Backend Status | Interpretation | Next Action |
|---------------|----------------|-------------|
| ECS Stopped | Backend down | Start ECS or remove from SLB |
| ECS Running but high CPU | Backend overloaded | Follow ECS High CPU scenario |
| ECS healthy but DropConnection persists | SLB config issue | Check listener health check config |

---

### Scenario 4: Redis ConnectionUsage Alarm

Triggered by: `ConnectionUsage >= Threshold` on `acs_kvstore_dashboard`

```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_kvstore_dashboard \
  --MetricName ConnectionUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'

aliyun redis DescribeInstances --RegionId {{user.region}} --InstanceId {{user.instance_id}}

for metric in CpuUsage MemoryUsage UsedConnection QPS; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} --Namespace acs_kvstore_dashboard \
    --MetricName "$metric" --Period 300 \
    --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```

| Correlated Pattern | Interpretation | Next Action |
|-------------------|----------------|-------------|
| ConnectionUsage high, QPS low | Connection leak | Check app for unclosed connections |
| ConnectionUsage + QPS both high | Traffic surge | Consider upgrading instance spec |
| ConnectionUsage high, MemoryUsage high | Large key ops | Check big keys; delegate to DAS cache analysis |

---

### Scenario 5: PolarDB CPUUsage Alarm

Triggered by: `CpuUsage >= Threshold` on `acs_polardb_dashboard`

```bash
aliyun cms DescribeMetricLast \
  --RegionId {{user.region}} \
  --Namespace acs_polardb_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'

aliyun polardb DescribeDBClusters --RegionId {{user.region}} --DBClusterId {{user.instance_id}}

for metric in MemoryUsage ConnectionUsage IOPSUsage DataSize; do
  aliyun cms DescribeMetricList \
    --RegionId {{user.region}} --Namespace acs_polardb_dashboard \
    --MetricName "$metric" --Period 300 \
    --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
    --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
done
```
> PolarDB has tight DAS integration; **always recommend DAS diagnosis** for PolarDB alarms.

---

## Escalation Path

| Issue | Self-Service | Escalate To |
|-------|-------------|-------------|
| Rate limiting | Backoff, reduce frequency | Alibaba Cloud support (quota increase) |
| Data missing | Verify instance, namespace, metric | Product team if instance running but no data |
| Alarm not firing | Check threshold, evaluation count | Alibaba Cloud support (backend issue) |
| Permission | Attach RAM policies | Security team (custom policy review) |
| CLI bug | Update CLI, use SDK fallback | Alibaba Cloud CLI GitHub issues |
| SDK bug | Update SDK version | Alibaba Cloud SDK GitHub issues |
| Cross-skill diagnosis failure | Check delegated skill status | Skill owner + Alibaba Cloud support |
| DAS diagnosis unavailable | Check DAS instance registration | DAS support team |

---

## References

- [CMS API Error Codes](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/api-cms-2019-01-01-overview)
- [RAM Policies for CMS](https://help.aliyun.com/zh/ram/user-guide/grant-permissions-to-the-ram-user)
- [CMS Quotas and Limits](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/product-overview/quotas)

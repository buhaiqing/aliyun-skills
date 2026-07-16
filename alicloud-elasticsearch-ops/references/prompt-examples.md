# Standardized Prompt Templates — Alibaba Cloud Elasticsearch

> **Purpose:** Reusable prompt templates for consistent AIOps interactions.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Prompt Template Categories

| Category | Purpose | Usage Context |
|----------|---------|----------------|
| **Operation Prompts** | Execute specific operations | Create, modify, delete instances |
| **Diagnostic Prompts** | Troubleshoot issues | Error resolution, health checks |
| **Inspection Prompts** | Proactive monitoring | Daily/weekly inspections |
| **Analysis Prompts** | Performance analysis | Optimization, capacity planning |
| **Report Prompts** | Generate reports | Diagnostic, inspection reports |

---

## 2. Operation Prompt Templates

### 2.1 Instance Creation Prompt

```markdown
# Create Elasticsearch Instance

**Context:**
- Region: {{region_id}}
- Environment: {{profile}}
- Purpose: {{purpose}}

**Required Parameters:**
- Instance Name: {{instance_name}}
- ES Version: {{version}} (options: 7.10_aliyun, 8.5_aliyun, 8.9_aliyun)
- Node Spec: {{node_spec}} (options: elasticsearch.sn2ne.large, xlarge, 2xlarge, 4xlarge)
- Node Count: {{node_count}} (minimum: 3 for production)
- VPC ID: {{vpc_id}}
- VSwitch ID: {{vswitch_id}}

**Optional Parameters:**
- Disk Type: {{disk_type}} (default: cloud_ssd)
- Disk Size: {{disk_size}}GB (default: 100)
- Zone Count: {{zone_count}} (default: 3 for HA)
- Dedicated Masters: {{master_enabled}} (default: true)

**Pre-flight Checks:**
1. Verify VPC exists: DescribeVpc({{vpc_id}})
2. Verify VSwitch exists: DescribeVSwitch({{vswitch_id}})
3. Check quota: GetInstanceQuota(regionId)
4. Validate version: GetRegionConfiguration(version)

**Execution:**
- Execute: CreateInstance with validated parameters
- Poll: DescribeInstance until Status = Normal (max 600s)
- Validate: Cluster health = green

**Expected Output:**
- Instance ID: {{output.instance_id}}
- Status: Normal
- Cluster Health: green
- Endpoints: {{output.endpoints}}

**Error Handling:**
- VpcNotFound → Delegate to alicloud-vpc-ops
- QuotaExceeded → Request quota increase
- InvalidParameter → Adjust parameters per API spec
```

### 2.2 Instance Modification Prompt

```markdown
# Modify Elasticsearch Instance

**Context:**
- Instance ID: {{instance_id}}
- Modification Type: {{modification_type}}
- Reason: {{reason}}

**Modification Types:**
1. **Node Spec Upgrade** - Scale up compute
2. **Node Count Change** - Add/remove nodes
3. **Disk Expansion** - Increase storage
4. **Configuration Update** - Adjust settings

**Pre-flight Checks:**
1. DescribeInstance → Verify Status = Normal
2. Check pending operations → No pending tasks
3. Create pre-change snapshot → Backup safety

**Execution:**
- Create Snapshot: pre-modify-{{timestamp}}
- Execute: UpdateInstance with {{modification_params}}
- Poll: DescribeInstance until Status = Normal (max 300s)
- Validate: Modification applied successfully

**Confirmation Required:**
- ⚠️ Modification may cause service restart
- ⚠️ Pre-change snapshot will be created
- Proceed? [Yes/No]

**Expected Output:**
- Snapshot ID: {{output.snapshot_id}}
- Modification Status: Completed
- Instance Status: Normal
- New Configuration: {{output.new_config}}

**Rollback:**
- If modification fails → Restore from snapshot
```

### 2.3 Instance Restart Prompt

```markdown
# Restart Elasticsearch Instance

**Context:**
- Instance ID: {{instance_id}}
- Restart Reason: {{reason}}
- Change Window: {{change_window}}

**Pre-flight Checks:**
1. DescribeInstance → Status = Normal
2. Create snapshot → pre-restart-{{timestamp}}
3. Check change window → Within maintenance window
4. WARN user → Service will be temporarily unavailable

**Confirmation Required:**
⚠️ Restart causes temporary service interruption (estimated 1-5 minutes)
⚠️ Pre-restart snapshot will be created
Instance: {{instance_id}}
Proceed with restart? [Yes/No]

**Execution:**
- Create Snapshot: pre-restart-{{timestamp}}
- Execute: RestartInstance(instanceId)
- Poll: DescribeInstance until Status = Normal (max 300s)
- Validate: Cluster health = green

**Expected Output:**
- Snapshot ID: {{output.snapshot_id}}
- Restart Duration: {{duration}}s
- Instance Status: Normal
- Cluster Health: green

**Rollback:**
- If restart fails → Investigate via DiagnoseInstance
- If cluster unhealthy → Check logs, restore if needed
```

### 2.4 Instance Deletion Prompt

```markdown
# Delete Elasticsearch Instance

**Context:**
- Instance ID: {{instance_id}}
- Instance Name: {{instance_name}}
- Deletion Reason: {{reason}}

**⚠️ CRITICAL WARNING:**
This operation is IRREVERSIBLE. All data, indices, snapshots will be permanently lost.

**Pre-flight Checks:**
1. DescribeInstance → Confirm instance details
2. ListSnapshots → Check for recent backups
3. Verify no dependencies → No applications connected

**MANDATORY Confirmation:**
You are about to DELETE instance {{instance_name}} ({{instance_id}})
All data will be permanently lost and cannot be recovered.
Type "DELETE {{instance_id}}" to confirm:

**Execution:**
- Execute: DeleteInstance(instanceId)
- Poll: DescribeInstance until NotFound error (max 300s)
- Verify: Instance no longer appears in ListInstance

**Expected Output:**
- Deletion Status: Completed
- Instance no longer exists

**Post-deletion:**
- Update application configurations
- Remove monitoring/alert rules
- Update documentation
```

---

## 3. Diagnostic Prompt Templates

### 3.1 Error Diagnosis Prompt

```markdown
# Diagnose Elasticsearch Error

**Context:**
- Instance ID: {{instance_id}}
- Error Code: {{error_code}}
- Error Message: {{error_message}}
- Operation Attempted: {{operation}}

**Diagnosis Workflow:**

**Round 1: Initial Diagnosis**
1. DescribeInstance → Get current status
2. DiagnoseInstance → Run health diagnostics
3. Classify error → Determine category

**Round 2: Hypothesis Validation**
1. Test hypothesis with targeted checks
2. Gather supporting/refuting evidence
3. Calculate confidence level

**Round 3: Root Cause Analysis**
1. Multi-metric correlation analysis
2. Log pattern analysis
3. Cross-skill dependency check

**Round 4: Remediation Planning**
1. Generate remediation actions
2. Prioritize by impact/risk
3. Validate safety

**Error Classification:**
| Error Code | Category | Cross-Skill Need |
|------------|----------|------------------|
| VpcNotFound | Infrastructure | alicloud-vpc-ops |
| Forbidden.RAM | Security | alicloud-ram-ops |
| Throttling | Rate Limit | Self-handle |
| InternalError | System | Escalate |

**Expected Output:**
- Root Cause: {{root_cause}}
- Confidence: {{confidence}}%
- Remediation Actions: {{actions}}
- Cross-Skill Delegation: {{delegation_needed}}
```

### 3.2 Cluster Health Diagnosis Prompt

```markdown
# Diagnose Cluster Health Issue

**Context:**
- Instance ID: {{instance_id}}
- Current Health: {{health_status}}
- Unassigned Shards: {{unassigned_count}}

**Diagnosis Steps:**

**Step 1: Health Status Analysis**
- GET _cluster/health → Detailed cluster state
- Identify: yellow/red cause

**Step 2: Node Investigation**
- GET _cat/nodes?v → Node status
- Check: Node availability, disk, load

**Step 3: Shard Analysis**
- GET _cat/shards?v&s=state → Shard states
- Identify: Unassigned shard reasons
- GET _cluster/allocation/explain → Allocation details

**Step 4: Resolution Actions**

**For Yellow (unassigned replicas):**
- Check node count >= replica_count + 1
- Adjust allocation settings if needed
- Wait for rebalance

**For Red (unassigned primaries):**
- Identify failed nodes
- Restart failed nodes
- Restore shards if corruption

**Expected Output:**
- Cluster Health: green
- All shards assigned
- Nodes healthy
```

### 3.3 Performance Diagnosis Prompt

```markdown
# Diagnose Performance Degradation

**Context:**
- Instance ID: {{instance_id}}
- Performance Issue: {{issue_type}}
- Observed Symptoms: {{symptoms}}

**Issue Types:**
1. High search latency (> 200ms)
2. High indexing latency (> 100ms)
3. JVM heap pressure (> 85%)
4. CPU saturation (> 80%)

**Diagnosis Steps:**

**Step 1: Metric Collection**
- Get CMS metrics for last 1 hour
- Identify threshold breaches
- Detect multi-metric patterns

**Step 2: Query Analysis**
- ListSearchLog → Find slow queries
- Analyze query patterns
- Identify heavy aggregations

**Step 3: JVM Analysis**
- GET _nodes/stats/jvm → JVM details
- Check GC frequency and pause time
- Analyze heap distribution

**Step 4: Optimization Recommendations**

**For High Latency:**
- Enable query cache
- Optimize aggregations
- Add coordinator nodes

**For JVM Pressure:**
- Increase heap (max 32GB)
- Switch to G1GC
- Reduce memory-intensive queries

**Expected Output:**
- Performance Issue: {{root_cause}}
- Optimization Steps: {{recommendations}}
- Expected Improvement: {{improvement}}
```

---

## 4. Inspection Prompt Templates

### 4.1 Daily Inspection Prompt

```markdown
# Daily Elasticsearch Inspection

**Context:**
- Instance IDs: {{instance_ids}}
- Inspection Date: {{date}}

**Inspection Checklist:**

**Check 1: Instance Status (Critical)**
- DescribeInstance → Status = Normal?
- Flag: ❌ if Status != Normal

**Check 2: Cluster Health (Critical)**
- DescribeElasticsearchHealth → Health = green?
- Flag: ⚠️ if yellow, ❌ if red

**Check 3: JVM Heap (Warning threshold: 85%)**
- Get JVM metrics → Heap < 85%?
- Flag: ⚠️ if 85-95%, ❌ if > 95%

**Check 4: Disk Usage (Warning threshold: 80%)**
- Get disk metrics → Disk < 80%?
- Flag: ⚠️ if 80-95%, ❌ if > 95%

**Check 5: Snapshot Verification (Mandatory)**
- ListSnapshots → Recent backup (< 24h)?
- Flag: ⚠️ if no backup

**Check 6: Multi-Metric Anomaly Detection**
- Detect correlation patterns (P1-P8)
- Flag: ⚠️ for any pattern detected

**Inspection Report:**
- Overall Status: {{overall}}
- Findings: {{findings}}
- Remediation Triggered: {{actions}}
```

### 4.2 Weekly Deep Inspection Prompt

```markdown
# Weekly Deep Elasticsearch Inspection

**Context:**
- Instance IDs: {{instance_ids}}
- Inspection Week: {{week}}

**Deep Analysis:**

**Analysis 1: Trend Analysis (7-day metrics)**
- CPU trend → Growth pattern?
- Disk trend → Capacity planning?
- Query trend → Workload changes?

**Analysis 2: Capacity Planning**
- Disk growth rate → Days to full?
- Node utilization → Need scaling?
- QPS trend → Capacity adequate?

**Analysis 3: Index Analysis**
- GET _cat/indices → Large indices (> 10M docs)
- Shard count analysis → Optimal?
- Index age → ILM policy needed?

**Analysis 4: Node Distribution**
- GET _cat/nodes → Load balance
- Disk per node → Even distribution?
- Shard per node → Balance check

**Recommendations:**
- Capacity: {{capacity_recommendations}}
- Optimization: {{optimization_recommendations}}
- ILM Policy: {{ilm_recommendations}}
```

---

## 5. Analysis Prompt Templates

### 5.1 Capacity Analysis Prompt

```markdown
# Elasticsearch Capacity Analysis

**Context:**
- Instance ID: {{instance_id}}
- Analysis Period: {{period}} days

**Capacity Metrics:**

**Current State:**
- Node Count: {{node_count}}
- Disk Size: {{disk_size}}
- CPU/Memory Spec: {{spec}}

**Usage Analysis:**
- Average CPU: {{avg_cpu}}%
- Peak CPU: {{peak_cpu}}%
- Average Disk: {{avg_disk}}%
- Disk Growth Rate: {{growth_rate}}%/day

**Projection:**
- Days to 80% disk: {{days_to_80}}
- Days to full: {{days_to_full}}
- QPS growth: {{qps_growth}}%/month

**Recommendations:**
- Disk expansion: {{disk_recommendation}}
- Node addition: {{node_recommendation}}
- Spec upgrade: {{spec_recommendation}}

**Cost Estimate:**
- Current monthly cost: {{current_cost}}
- Recommended monthly cost: {{recommended_cost}}
- Savings/Investment: {{cost_diff}}
```

### 5.2 Performance Optimization Prompt

```markdown
# Elasticsearch Performance Optimization

**Context:**
- Instance ID: {{instance_id}}
- Current Performance: {{current_metrics}}
- Target Performance: {{target_metrics}}

**Optimization Areas:**

**Query Optimization:**
- Analyze slow queries → Optimization candidates
- Enable query cache → Expected improvement
- Index optimization → Shard count adjustment

**JVM Optimization:**
- Heap size → Current vs recommended
- GC policy → CMS vs G1GC recommendation
- Thread pool → Adjustment needed?

**Infrastructure Optimization:**
- Node spec → Upgrade needed?
- Coordinator nodes → Add for query routing?
- Warm nodes → Add for historical data?

**Expected Improvements:**
- Latency reduction: {{expected_latency_improvement}}
- Throughput increase: {{expected_throughput_increase}}
- Cost optimization: {{expected_cost_savings}}
```

---

## 6. Report Prompt Templates

### 6.1 Diagnostic Report Prompt

```markdown
# Generate Elasticsearch Diagnostic Report

**Context:**
- Instance ID: {{instance_id}}
- Report Type: {{report_type}}
- Trigger: {{trigger_reason}}

**Report Sections:**

**1. Summary Section**
- Instance ID, Timestamp, Overall Status
- Severity assessment

**2. Findings Section**
- All diagnostic findings with severity
- Threshold violations

**3. Metrics Section**
- Key metrics snapshot
- Threshold comparison

**4. Root Cause Section**
- Hypothesis with confidence
- Evidence supporting hypothesis
- Diagnosis rounds

**5. Remediation Section**
- Action plan
- Automated vs manual actions
- Cross-skill dependencies

**6. Self-Reflection Section**
- Round summary
- Satisfaction status
- Lessons learned

**Output Format:**
- JSON: For AIOps integration
- Markdown: For human review

**Report ID:** ES-DIAG-{{date}}-{{time}}-{{suffix}}
```

### 6.2 Inspection Report Prompt

```markdown
# Generate Elasticsearch Inspection Report

**Context:**
- Instance IDs: {{instance_ids}}
- Inspection Type: {{type}} (daily/weekly)
- Date: {{date}}

**Report Sections:**

**1. Executive Summary**
- Overall health status
- Instances healthy/warning/critical

**2. Instance-by-Instance Status**
- Table: Instance | Status | Health | CPU | Disk | JVM

**3. Findings Summary**
- Critical findings count
- Warning findings count
- Pattern detections

**4. Remediation Actions**
- Triggered actions
- Pending actions
- Cross-skill delegations

**5. Capacity Planning (Weekly)**
- Growth trends
- Capacity projections
- Recommendations

**6. Next Inspection**
- Scheduled date
- Focus areas

**Output Format:**
- Markdown dashboard format
- Email-friendly summary
```

---

## 7. Alarm Storm Handling Prompt Templates

### 7.1 Alarm Storm Detection Prompt

```markdown
# Detect and Handle Alarm Storm

**Context:**
- Time Window: {{time_window}} minutes
- Threshold: >10 alerts/min OR >30 alerts/5min
- Alert Source: {{alert_source}}

**Detection Workflow:**

**Step 1: Storm Detection**
- Count alerts in last {{time_window}} minutes
- Classify: Moderate (>10/min) or Severe (>30/5min)
- Identify affected instances

**Step 2: Pattern Classification**
- Group alerts by error code
- Identify dominant error pattern:
  - APIRateLimitStorm: Throttling dominant
  - CascadeFailureStorm: InstanceNotFound/ConnectionTimeout
  - ClusterWideFailureStorm: ClusterHealth.Red
  - NetworkPartitionStorm: ConnectionTimeout
  - ConfigurationDriftStorm: Forbidden/OperationDenied

**Step 3: Root Cause Identification**
- Analyze pattern-specific root cause
- Check cross-skill dependencies
- Determine remediation action

**Step 4: Storm Handling**
- Apply deduplication (5-minute window)
- Suppress downstream alerts
- Aggregate into single actionable alert
- Execute remediation

**Expected Output:**
- Storm Status: {{storm_status}}
- Pattern: {{pattern_name}}
- Suppressed Count: {{suppressed_count}}
- Root Cause: {{root_cause}}
- Remediation: {{remediation_action}}
- Report ID: ES-DIAG-{{timestamp}}-STORM

**Integration:**
- Trigger proactive-inspection on affected instances
- Generate diagnostic report via diagnostic-report-schema
- Cross-reference with monitoring.md multi-metric patterns
```

### 7.2 Alarm Deduplication Prompt

```markdown
# Deduplicate and Aggregate Alarms

**Context:**
- Alerts: {{alert_list}}
- Deduplication Window: 5 minutes
- Aggregation Threshold: >5 similar alerts

**Deduplication Rules:**

**Rule 1: Exact Duplicate**
- Same instance + error code + message
- Action: Suppress duplicate, keep first
- Window: 5 minutes

**Rule 2: Similar Pattern**
- Same error code, different instance
- Action: Aggregate by error code
- Window: 10 minutes

**Rule 3: Cascade Pattern**
- Related error codes in sequence
- Action: Group by root cause
- Window: 15 minutes

**Execution:**
1. For each alert:
   - Check if seen within window
   - If duplicate → Suppress
   - If new → Mark seen, group by error code
2. If group count > 5:
   - Generate aggregated report
   - Identify root cause pattern
3. Forward unique alerts

**Expected Output:**
- Forwarded Alerts: {{forwarded_count}}
- Suppressed Alerts: {{suppressed_count}}
- Aggregated Groups: {{aggregated_groups}}
- Storm Detected: {{storm_detected}}
```

### 7.3 Storm Remediation Prompt

```markdown
# Execute Alarm Storm Remediation

**Context:**
- Storm Pattern: {{pattern_name}}
- Root Cause: {{root_cause}}
- Affected Instances: {{instance_ids}}

**Remediation Actions by Pattern:**

**APIRateLimitStorm:**
1. Implement exponential backoff
2. Reduce concurrent API calls
3. Batch operations with delay
4. Monitor rate limit consumption

**CascadeFailureStorm:**
1. Identify dependency (VPC/RAM)
2. Delegate to cross-skill (vpc-ops/ram-ops)
3. Wait for dependency resolution
4. Verify affected instances

**ClusterWideFailureStorm:**
1. Check master node status
2. Restart failed master nodes
3. Wait for cluster recovery
4. Validate cluster health = green

**NetworkPartitionStorm:**
1. Test node connectivity
2. Check VPC routing
3. Delegate to vpc-ops if needed
4. Verify network restored

**Execution:**
- Execute pattern-specific remediation
- Monitor progress
- Update remediation status

**Verification:**
- Alert rate normalized (<5/min)
- Affected instances healthy
- Root cause resolved

**Expected Output:**
- Remediation Status: {{remediation_status}}
- Actions Completed: {{actions_completed}}
- Verification Result: {{verification_result}}
- Storm Closed: {{storm_closed}}
```

---

## 8. Prompt Usage Guidelines

### 8.1 Template Variables

| Variable | Source | Example |
|----------|--------|---------|
| `{{instance_id}}` | User input | es-cn-abc123 |
| `{{region_id}}` | Environment | cn-hangzhou |
| `{{profile}}` | User input | production |
| `{{error_code}}` | API response | VpcNotFound |
| `{{timestamp}}` | System | 2026-05-17T14:30:25Z |
| `{{output.*}}` | API response | output.instance_id |

### 8.2 Prompt Execution Checklist

```
Before Using Prompt:
□ Context variables filled
□ Pre-flight checks understood
□ Confirmation requirements noted
□ Error handling paths known

During Execution:
□ Follow workflow steps sequentially
□ Validate each step result
□ Document findings
□ Track progress

After Execution:
□ Verify expected output
□ Generate report if applicable
□ Update knowledge base
□ Log for audit trail
```

---

*These standardized prompt templates provide consistent AIOps interaction patterns.*
# Alarm Storm Handling — Alibaba Cloud Elasticsearch

> **Purpose:** Patterns for handling alarm storms, deduplication, suppression, and escalation management.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Alarm Storm Definition

### 1.1 What is Alarm Storm?

**Alarm Storm:** A surge of correlated alerts from the same root cause, overwhelming operators and obscuring the actual issue.

| Indicator | Threshold | Classification |
|-----------|-----------|----------------|
| Alert count per minute | > 10 alerts/min | Storm detected |
| Alert count per 5 min | > 30 alerts/5min | Severe storm |
| Same error code frequency | > 5 occurrences/min | Correlated storm |
| Multiple instances affected | > 3 instances simultaneously | Cascade failure |

### 1.2 Alarm Storm Causes

| Cause | Typical Pattern | Example |
|-------|-----------------|---------|
| **Network partition** | Multiple nodes unreachable simultaneously | VPC routing issue |
| **API throttling** | Repeated Throttling errors across operations | Burst API calls |
| **Cluster-wide failure** | All instances report cluster red | Master node failure |
| **Configuration drift** | Same error across all instances | Invalid whitelist update |
| **Dependency failure** | VPC/Security group issue affecting all | Cross-skill dependency |

---

## 2. Alarm Deduplication Strategy

### 2.1 Deduplication Rules

| Rule | Condition | Action | Window |
|------|-----------|--------|--------|
| **Exact duplicate** | Same instance + error code + message | Suppress duplicate, keep first | 5 minutes |
| **Similar pattern** | Same error code, different instance | Aggregate by error code | 10 minutes |
| **Cascade pattern** | Related error codes in sequence | Group by root cause | 15 minutes |
| **Threshold pattern** | Same metric threshold breach | Summarize by threshold | 30 minutes |

### 2.2 Deduplication Implementation

```go
type AlarmDeduplicator struct {
    seenAlarms    map[string]time.Time
    groupedAlarms map[string][]Alarm
    windowSeconds int
}

type Alarm struct {
    InstanceId  string
    ErrorCode   string
    Message     string
    Timestamp   time.Time
    Severity    string
}

func (d *AlarmDeduplicator) ProcessAlarm(alarm Alarm) *DeduplicationResult {
    key := fmt.Sprintf("%s-%s-%s", alarm.InstanceId, alarm.ErrorCode, alarm.Message)
    
    // Check if exact duplicate within window
    if seenTime, exists := d.seenAlarms[key]; exists {
        if time.Since(seenTime) < time.Duration(d.windowSeconds) * time.Second {
            return &DeduplicationResult{
                Action:    "Suppress",
                Reason:    "Duplicate within window",
                Original:  nil,
            }
        }
    }
    
    // Mark as seen
    d.seenAlarms[key] = alarm.Timestamp
    
    // Group similar alarms by error code
    groupKey := alarm.ErrorCode
    d.groupedAlarms[groupKey] = append(d.groupedAlarms[groupKey], alarm)
    
    // Check if alarm storm detected
    if len(d.groupedAlarms[groupKey]) > 5 {
        return &DeduplicationResult{
            Action:    "Aggregate",
            Reason:    "Storm detected",
            Original:  nil,
            Group:     d.groupedAlarms[groupKey],
        }
    }
    
    return &DeduplicationResult{
        Action:    "Forward",
        Reason:    "New unique alarm",
        Original:  &alarm,
    }
}

type DeduplicationResult struct {
    Action    string // Suppress, Aggregate, Forward
    Reason    string
    Original  *Alarm
    Group     []Alarm
}
```

### 2.3 Aggregated Alarm Report

```markdown
# Aggregated Alarm Report (Storm Detected)

**Detection Time:** {{timestamp}}
**Alarm Count:** {{alarm_count}} in last {{window}} minutes
**Root Cause Pattern:** {{root_cause_pattern}}

## Affected Instances

| Instance ID | Error Code | First Seen | Count |
|-------------|------------|------------|-------|
| es-cn-abc1 | Throttling | 10:23:15 | 8 |
| es-cn-abc2 | Throttling | 10:23:18 | 6 |
| es-cn-abc3 | Throttling | 10:23:20 | 5 |

## Root Cause Hypothesis

**Pattern:** API Throttling Storm
**Cause:** Burst of concurrent API calls exceeding rate limit
**Recommendation:** Implement exponential backoff, reduce concurrent operations

## Action Required

1. Reduce API call frequency
2. Implement request batching
3. Monitor rate limit consumption

## Suppressed Alarms

- 19 duplicate Throttling alerts suppressed
- Aggregated into single actionable alert
```

---

## 3. Alarm Suppression Rules

### 3.1 Suppression Matrix

| Suppression Type | Trigger | Duration | Scope |
|------------------|---------|----------|-------|
| **Maintenance window** | Scheduled maintenance | 2-4 hours | All instances in maintenance |
| **Known issue** | Documented known limitation | Until resolution | Specific error code |
| **Cascade suppression** | Root cause identified | Until fix | All downstream alarms |
| **Threshold adjustment** | Temporary threshold raise | 24 hours | Specific metric |

### 3.2 Maintenance Window Suppression

```go
type MaintenanceWindow struct {
    StartTime    time.Time
    EndTime      time.Time
    InstanceIds  []string
    Reason       string
}

func (m *MaintenanceWindow) ShouldSuppress(alarm Alarm) bool {
    // Check if alarm instance in maintenance
    for _, id := range m.InstanceIds {
        if id == alarm.InstanceId {
            // Check if within maintenance window
            if alarm.Timestamp.After(m.StartTime) && alarm.Timestamp.Before(m.EndTime) {
                return true
            }
        }
    }
    return false
}

func suppressMaintenanceAlarms(alarms []Alarm, windows []MaintenanceWindow) []Alarm {
    result := []Alarm{}
    
    for _, alarm := range alarms {
        suppressed := false
        for _, window := range windows {
            if window.ShouldSuppress(alarm) {
                fmt.Printf("⚠️ Suppressing alarm for %s (maintenance)\n", alarm.InstanceId)
                suppressed = true
                break
            }
        }
        if !suppressed {
            result = append(result, alarm)
        }
    }
    
    return result
}
```

### 3.3 Cascade Suppression

```yaml
Cascade Suppression Pattern:

Root Cause: VPC routing failure
Primary Alarm: VpcNotFound on es-cn-abc1
Downstream Alarms:
  - InstanceNotFound (3 instances)
  - ConnectionTimeout (5 instances)
  - ClusterRed (2 instances)

Suppression Strategy:
  1. Identify root cause: VPC failure
  2. Suppress all downstream VPC-related alarms
  3. Focus on root cause resolution
  4. Clear suppression after VPC restored
```

---

## 4. Alarm Storm Resolution Workflow

### 4.1 Storm Detection and Response

```go
func handleAlarmStorm(alarms []Alarm) *StormResponse {
    // Step 1: Detect storm
    storm := detectAlarmStorm(alarms)
    if !storm.Detected {
        return &StormResponse{Status: "NoStorm"}
    }
    
    fmt.Printf("🚨 Alarm Storm Detected: %d alarms in %d seconds\n", 
        storm.AlarmCount, storm.WindowSeconds)
    
    // Step 2: Classify storm pattern
    pattern := classifyStormPattern(alarms)
    fmt.Printf("Pattern: %s\n", pattern.Name)
    
    // Step 3: Identify root cause
    rootCause := identifyRootCause(alarms, pattern)
    fmt.Printf("Root Cause: %s\n", rootCause.Description)
    
    // Step 4: Suppress duplicates and downstream alarms
    deduplicatedAlarms := dedupAndSuppress(alarms, rootCause)
    
    // Step 5: Generate aggregated report
    report := generateAggregatedReport(storm, pattern, rootCause, deduplicatedAlarms)
    
    // Step 6: Trigger remediation
    if rootCause.RemediationAction != "" {
        triggerRemediation(rootCause.RemediationAction)
    }
    
    return &StormResponse{
        Status:        "Handled",
        Storm:         storm,
        Pattern:       pattern,
        RootCause:     rootCause,
        Report:        report,
        Remediation:   rootCause.RemediationAction,
    }
}

type StormResponse struct {
    Status      string
    Storm       *AlarmStorm
    Pattern     *StormPattern
    RootCause   *RootCause
    Report      string
    Remediation string
}

func detectAlarmStorm(alarms []Alarm) *AlarmStorm {
    // Count alarms in last 5 minutes
    window := 5 * time.Minute
    cutoff := time.Now().Add(-window)
    
    recentCount := 0
    for _, alarm := range alarms {
        if alarm.Timestamp.After(cutoff) {
            recentCount++
        }
    }
    
    if recentCount > 30 {
        return &AlarmStorm{
            Detected:     true,
            AlarmCount:   recentCount,
            WindowSeconds: 300,
            Severity:     "Severe",
        }
    }
    
    if recentCount > 10 {
        return &AlarmStorm{
            Detected:     true,
            AlarmCount:   recentCount,
            WindowSeconds: 300,
            Severity:     "Moderate",
        }
    }
    
    return &AlarmStorm{Detected: false}
}
```

### 4.2 Storm Pattern Classification

```go
func classifyStormPattern(alarms []Alarm) *StormPattern {
    // Count by error code
    errorCounts := make(map[string]int)
    for _, alarm := range alarms {
        errorCounts[alarm.ErrorCode]++
    }
    
    // Find dominant error code
    dominantError := ""
    maxCount := 0
    for code, count := range errorCounts {
        if count > maxCount {
            maxCount = count
            dominantError = code
        }
    }
    
    // Classify pattern
    patterns := map[string]string{
        "Throttling":           "APIRateLimitStorm",
        "InternalError":        "ServiceDegradationStorm",
        "OperationDenied":      "ConfigurationDriftStorm",
        "InstanceNotFound":     "CascadeFailureStorm",
        "ClusterHealth.Red":    "ClusterWideFailureStorm",
        "ConnectionTimeout":    "NetworkPartitionStorm",
    }
    
    patternName := patterns[dominantError]
    if patternName == "" {
        patternName = "UnknownPattern"
    }
    
    return &StormPattern{
        Name:            patternName,
        DominantError:   dominantError,
        AffectedCount:   maxCount,
        TotalAlarms:     len(alarms),
    }
}

type StormPattern struct {
    Name          string
    DominantError string
    AffectedCount int
    TotalAlarms   int
}
```

---

## 5. Root Cause Identification

### 5.1 Root Cause Analysis Matrix

| Pattern | Root Cause Hypothesis | Verification Method |
|---------|----------------------|---------------------|
| APIRateLimitStorm | API burst exceeding quota | Check API call history |
| ServiceDegradationStorm | Backend service issue | Check service status, retry test |
| ConfigurationDriftStorm | Invalid config applied | Compare before/after config |
| CascadeFailureStorm | Dependency failure (VPC/RAM) | Cross-skill diagnosis |
| ClusterWideFailureStorm | Master node failure | Check master node status |
| NetworkPartitionStorm | Network routing issue | Test connectivity between nodes |

### 5.2 Root Cause Identification Implementation

```go
func identifyRootCause(alarms []Alarm, pattern *StormPattern) *RootCause {
    switch pattern.Name {
    case "APIRateLimitStorm":
        return &RootCause{
            Description:      "API rate limit exceeded due to burst calls",
            Category:         "Throttling",
            RemediationAction: "ImplementExponentialBackoff",
            CrossSkill:        false,
        }
        
    case "CascadeFailureStorm":
        return &RootCause{
            Description:      "Dependency failure (VPC or RAM)",
            Category:         "Infrastructure",
            RemediationAction: "DelegateToVpcOpsOrRamOps",
            CrossSkill:        true,
            DelegateSkill:     "alicloud-vpc-ops or alicloud-ram-ops",
        }
        
    case "ClusterWideFailureStorm":
        return &RootCause{
            Description:      "Master node failure causing cluster-wide red",
            Category:         "Cluster",
            RemediationAction: "RestartMasterNodes",
            CrossSkill:        false,
        }
        
    case "NetworkPartitionStorm":
        return &RootCause{
            Description:      "Network partition isolating nodes",
            Category:         "Network",
            RemediationAction: "DelegateToVpcOps",
            CrossSkill:        true,
            DelegateSkill:     "alicloud-vpc-ops",
        }
        
    default:
        return &RootCause{
            Description:      "Unknown root cause, requires investigation",
            Category:         "Unknown",
            RemediationAction: "TriggerDeepDiagnosis",
            CrossSkill:        false,
        }
    }
}

type RootCause struct {
    Description      string
    Category         string
    RemediationAction string
    CrossSkill        bool
    DelegateSkill     string
}
```

---

## 6. Cross-Skill Delegation for Storm Resolution

### 6.1 Cross-Skill Storm Resolution Matrix

| Storm Pattern | Primary Resolution | Delegation | Return Criteria |
|---------------|--------------------|------------|-----------------|
| VPC-related storm | Network diagnosis | alicloud-vpc-ops | VPC restored |
| RAM permission storm | Permission fix | alicloud-ram-ops | Permission granted |
| Security group storm | SG rule fix | alicloud-ecs-ops | SG configured |
| CMS alert storm | Alert rule update | alicloud-cms-ops | Rules optimized |

### 6.2 Delegation Workflow Example

```yaml
# VPC Storm Resolution Workflow

Phase 1: Detection (alicloud-elasticsearch-ops)
  - Detect: Multiple instances reporting VpcNotFound
  - Classify: CascadeFailureStorm (VPC dependency)
  - Identify root cause: VPC {{vpc_id}} not found

Phase 2: Delegation (alicloud-vpc-ops)
  - Execute: DescribeVpc({{vpc_id}})
  - If VPC deleted: CreateVpc
  - If VPC routing issue: Fix routing table
  - Return: {{output.vpc_status}}

Phase 3: Verification (alicloud-elasticsearch-ops)
  - Check: DescribeInstance for all affected instances
  - Validate: Status = Normal, Cluster health = green
  - Clear: Suppression rules for downstream alarms

Phase 4: Storm Closure
  - Generate: Storm resolution report
  - Clear: Alarm storm state
  - Log: Incident for audit trail
```

---

## 7. Alarm Storm Handling Checklist

### 7.1 Storm Response Checklist

```
Detection:
□ Alarm count exceeds threshold (>10/min or >30/5min)
□ Storm pattern classified (API, Network, Cascade, Cluster)
□ Root cause hypothesis identified

Suppression:
□ Duplicate alarms suppressed within window
□ Downstream alarms suppressed based on root cause
□ Maintenance windows applied if applicable

Analysis:
□ Root cause verified via diagnostic
□ Cross-skill dependencies checked
□ Escalation path identified if needed

Resolution:
□ Remediation action triggered
□ Cross-skill delegation if required
□ Progress monitored

Closure:
□ Affected instances verified healthy
□ Suppression rules cleared
□ Storm report generated
□ Incident logged for audit
```

---

## 8. Metrics for Alarm Storm Analysis

### 8.1 Storm Metrics Dashboard

| Metric | Purpose | Threshold |
|--------|---------|-----------|
| **Alarm rate** | Alerts per minute | >10 = storm |
| **Dedup ratio** | Percentage of suppressed alarms | Target: >50% during storm |
| **Resolution time** | Time from storm to resolution | Target: <15 min |
| **Root cause accuracy** | Correct root cause identification | Target: >90% |
| **False positive rate** | Storms incorrectly identified | Target: <5% |

---

## 9. Integration with Proactive Inspection

### 9.1 Alarm Storm Triggered Inspection

When alarm storm is detected, proactive inspection should be triggered for root cause investigation:

```yaml
Alarm Storm → Proactive Inspection Integration:

Trigger: Storm.Detected == true
Action:
  1. Suppress storm alarms via deduplication
  2. Invoke proactive-inspection workflow on affected instances
  3. Use multi-metric anomaly patterns (P1-P8) for diagnosis
  4. Generate diagnostic report with storm context

Integration Flow:
  ├── alarm-storm-handling.md (detect, suppress, aggregate)
  ├── proactive-inspection.md (diagnose, remediate)
  └── diagnostic-report-schema.md (report, track)
```

### 9.2 Cross-Reference with Other AIOps Components

| Component | Integration Point | Reference |
|-----------|-------------------|-----------|
| **Proactive Inspection** | Storm triggers inspection on affected instances | `operations/proactive-inspection.md` |
| **Multi-Metric Anomaly** | Storm patterns use P1-P8 detection | `references/monitoring.md#8` |
| **Diagnostic Report** | Storm resolution documented in report | `reports/diagnostic-report-schema.md` |
| **Cross-Skill Diagnosis** | Storm may require cross-skill delegation | `references/integration.md#6` |
| **Self-Reflection** | Multi-round analysis for complex storms | `references/troubleshooting.md#6` |

---

*This alarm storm handling guide provides patterns for managing alert floods with deduplication and root cause identification. See [proactive-inspection.md](proactive-inspection.md) for integrated diagnosis workflow.*
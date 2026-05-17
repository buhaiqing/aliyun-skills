# Troubleshooting Guide — Alibaba Cloud Elasticsearch

> **Purpose:** Common error codes, diagnostic procedures, and recovery patterns.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Error Code Reference (≥ 10 Codes)

| Code / HTTP | Meaning | Agent Action | UX Feedback |
|-------------|---------|--------------|-------------|
| `InvalidParameter` / 400 | Request parameter validation failed | Fix parameter per OpenAPI spec | `[ERROR] InvalidParameter: Check parameter values. See API docs for valid ranges.` |
| `InvalidParameter.Value` / 400 | Parameter value out of valid range | Adjust value to valid range | `[ERROR] InvalidParameter.Value: Value {value} not in valid range [{min}-{max}].` |
| `MissingParameter` / 400 | Required parameter not provided | Add missing field | `[ERROR] MissingParameter: {field} is required. Add to request.` |
| `InstanceNotFound` / 404 | Instance ID does not exist | Verify ID via ListInstance | `[ERROR] InstanceNotFound: Instance {id} not found. Verify ID or create new instance.` |
| `RegionNotSupported` / 400 | Elasticsearch not available in this region | Use supported region | `[ERROR] RegionNotSupported: Elasticsearch not available in {region}. Use: cn-hangzhou, cn-shanghai, etc.` |
| `QuotaExceeded.Instance` / 400 | Instance quota limit reached | Request quota increase | `[ERROR] QuotaExceeded: Instance quota reached. Request quota increase at console.` |
| `QuotaExceeded.Node` / 400 | Node count exceeds quota | Reduce nodes or raise quota | `[ERROR] QuotaExceeded.Node: Node quota limit. Reduce node count or request increase.` |
| `VpcNotFound` / 404 | VPC ID not found in region | Create VPC via vpc-ops | `[ERROR] VpcNotFound: VPC {id} not found. Create VPC using alicloud-vpc-ops.` |
| `VswitchNotFound` / 404 | VSwitch not found | Create VSwitch in VPC | `[ERROR] VswitchNotFound: VSwitch {id} not found. Create in VPC first.` |
| `Forbidden.RAM` / 403 | RAM policy denies action | Add RAM permission | `[ERROR] Forbidden.RAM: RAM policy denies {action}. Add elasticsearch:* permission.` |
| `OperationDenied.InstanceStatus` / 403 | Instance in wrong state for operation | Wait for stable state | `[ERROR] OperationDenied: Instance status {status} not valid for operation. Wait for Normal.` |
| `OperationDenied.PendingTask` / 403 | Another operation in progress | Wait and retry | `[ERROR] OperationDenied: Pending operation. Wait 30s and retry.` |
| `Throttling` / 429 | API rate limit exceeded | Exponential backoff retry | `⚠️ Throttling: Rate limit. Retrying in 2s... (attempt {n}/3)` |
| `InternalError` / 500 | Server-side error | Retry with backoff; escalate | `[ERROR] InternalError: Server error. RequestId: {id}. Retry or escalate.` |
| `ServiceUnavailable` / 503 | Service temporarily unavailable | Retry later | `[ERROR] ServiceUnavailable: Service down. Retry in 60s.` |
| `VersionNotSupported` / 400 | ES version not available | Use supported version | `[ERROR] VersionNotSupported: Version {v} not supported. Use: 7.10, 8.9, etc.` |
| `NodeSpecNotSupported` / 400 | Node spec not available | Use valid spec | `[ERROR] NodeSpecNotSupported: Spec {spec} not valid. Use: elasticsearch.sn2ne.large, etc.` |

---

## 2. Diagnostic Procedure

### Order of Investigation

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Describe Instance → Get current status            │
│          client.DescribeInstance(instanceId)                │
├─────────────────────────────────────────────────────────────┤
│  Step 2: List Instance → Verify instance exists in region  │
│          client.ListInstance(regionId)                      │
├─────────────────────────────────────────────────────────────┤
│  Step 3: Check Instance Status → Identify operation state  │
│          Status: Normal | Activating | Failed               │
├─────────────────────────────────────────────────────────────┤
│  Step 4: Diagnose Instance → Run health diagnostics        │
│          client.DiagnoseInstance(instanceId)                │
├─────────────────────────────────────────────────────────────┤
│  Step 5: List Diagnose Reports → Review past diagnoses     │
│          client.ListDiagnoseReport(instanceId)              │
├─────────────────────────────────────────────────────────────┤
│  Step 6: Describe Elasticsearch Health → Cluster health    │
│          client.DescribeElasticsearchHealth(instanceId)     │
├─────────────────────────────────────────────────────────────┤
│  Step 7: Check Logs → ListSearchLog for error patterns     │
│          client.ListSearchLog(instanceId)                   │
└─────────────────────────────────────────────────────────────┘
```

### Diagnostic Code Examples

#### Check Instance Status

```go
response, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
    InstanceId: tea.String(instanceId),
})
if err != nil {
    if strings.Contains(err.Error(), "InstanceNotFound") {
        fmt.Println("❌ Instance not found")
        return
    }
    panic(err)
}

status := tea.ToString(response.Body.Result.Status)
fmt.Printf("Instance Status: %s\n", status)
fmt.Printf("ES Version: %s\n", tea.ToString(response.Body.Result.EsVersion))
fmt.Printf("Node Amount: %d\n", tea.ToInt32(response.Body.Result.NodeAmount))
```

#### Run Diagnostics

```go
response, err := client.DiagnoseInstance(&elasticsearch.DiagnoseInstanceRequest{
    InstanceId: tea.String(instanceId),
})
if err != nil {
    panic(err)
}

reportId := tea.ToString(response.Body.Result.ReportId)
fmt.Printf("Diagnostic Report ID: %s\n", reportId)

// Later: fetch report details
reportResponse, err := client.DescribeDiagnoseReport(&elasticsearch.DescribeDiagnoseReportRequest{
    InstanceId: tea.String(instanceId),
    ReportId:   tea.String(reportId),
})
```

---

## 3. Common Issue Patterns

### Pattern 1: Instance Creation Timeout

**Symptoms:** Instance stuck in `Activating` for > 10 minutes

**Investigation Steps:**
1. Check DescribeInstance status
2. Verify VPC/VSwitch connectivity
3. Check quota limits
4. Review CloudMonitor events

**Resolution:**
```go
// Check if still activating
status := getStatus(instanceId)
if status == "Activating" && timeSinceCreation > 10*time.Minute {
    // May be stuck; check underlying resources
    fmt.Println("⚠️ Instance creation may be stuck")
    // Recommend: check VPC, VSwitch, quota, or contact support
}
```

### Pattern 2: Restart Never Completes

**Symptoms:** Restart stuck in `Activating`, instance unavailable

**Investigation:**
```go
// Poll restart status
for i := 0; i < 30; i++ {
    status := getStatus(instanceId)
    if status == "Normal" {
        break
    }
    if status == "Failed" {
        fmt.Println("❌ Restart failed")
        // Check diagnose reports
        break
    }
    time.Sleep(10 * time.Second)
}
```

**Resolution:**
- Check diagnose reports for failure cause
- Verify disk space, memory pressure
- May need manual intervention via console

### Pattern 3: Connection Refused

**Symptoms:** Cannot connect to ES endpoint

**Investigation:**
1. Check instance status (`Normal`)
2. Verify endpoint from DescribeInstance
3. Check IP whitelist (`ModifyWhiteIps`)
4. Verify network ACL/security group
5. Check HTTPS enabled/disabled

**Resolution:**
```go
// Check whitelist
response, err := client.DescribeInstance(instanceIdRequest)
// Check Endpoints array
for _, ep := range response.Body.Result.Endpoints {
    fmt.Printf("Endpoint: %s (type: %s)\n", 
        tea.ToString(ep.Endpoint), 
        tea.ToString(ep.EndpointType))
}

// Verify whitelist
whiteListResp, err := client.DescribeInstance(instanceIdRequest)
// whiteListResp.Body.Result.WhiteIpList contains allowed IPs
```

### Pattern 4: Snapshot Creation Fails

**Symptoms:** CreateSnapshot returns error

**Investigation:**
1. Check instance status (must be `Normal`)
2. Verify snapshot quota
3. Check existing snapshots not in progress
4. Verify disk space

**Resolution:**
```go
// List existing snapshots
response, err := client.ListSnapshots(&elasticsearch.ListSnapshotsRequest{
    InstanceId: tea.String(instanceId),
})
// Check for in-progress snapshots
for _, snap := range response.Body.Result.Snapshots {
    if tea.ToString(snap.Status) == "InProgress" {
        fmt.Println("⚠️ Snapshot already in progress")
        return
    }
}
```

### Pattern 5: Plugin Installation Failure

**Symptoms:** InstallUserPlugins returns error

**Investigation:**
1. Verify plugin compatibility with ES version
2. Check disk space for plugin
3. Verify plugin name is correct
4. Check if plugin already installed

**Resolution:**
```go
// List installed plugins first
response, err := client.ListPlugins(&elasticsearch.ListPluginsRequest{
    InstanceId: tea.String(instanceId),
})
for _, plugin := range response.Body.Result.Plugins {
    fmt.Printf("Installed: %s\n", tea.ToString(plugin.Name))
}
```

### Pattern 6: RAM Permission Denied

**Symptoms:** `Forbidden.RAM` error

**Investigation:**
1. Check RAM policy for user/role
2. Verify action is allowed for Elasticsearch
3. Check resource scope in policy

**Resolution:**
- Add RAM policy with `elasticsearch:*` actions
- Or specific actions needed for operation
- Verify resource scope matches instance

---

## 4. Multi-Round Diagnosis Template

```go
func diagnoseIssue(client *elasticsearch.Client, instanceId string) {
    // Round 1: Basic status check
    fmt.Println("=== Round 1: Basic Status ===")
    inst, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    if err != nil {
        fmt.Printf("❌ DescribeInstance error: %v\n", err)
        return
    }
    
    status := tea.ToString(inst.Body.Result.Status)
    fmt.Printf("Status: %s\n", status)
    
    if status != "Normal" {
        // Round 2: Check operation history
        fmt.Println("=== Round 2: Action History ===")
        actions, err := client.ListActionRecords(&elasticsearch.ListActionRecordsRequest{
            InstanceId: tea.String(instanceId),
        })
        if err == nil {
            // Review recent actions
            for _, action := range actions.Body.Result.ActionRecords {
                fmt.Printf("Action: %s | Status: %s | Time: %s\n",
                    tea.ToString(action.ActionName),
                    tea.ToString(action.Status),
                    tea.ToString(action.StartTime))
            }
        }
    }
    
    // Round 3: Run diagnostics
    fmt.Println("=== Round 3: Health Diagnostics ===")
    diag, err := client.DiagnoseInstance(&elasticsearch.DiagnoseInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    if err == nil {
        fmt.Printf("Diagnostic triggered. Report ID: %s\n", 
            tea.ToString(diag.Body.Result.ReportId))
    }
    
    // Round 4: Check cluster health
    fmt.Println("=== Round 4: Cluster Health ===")
    health, err := client.DescribeElasticsearchHealth(&elasticsearch.DescribeElasticsearchHealthRequest{
        InstanceId: tea.String(instanceId),
    })
    if err == nil {
        fmt.Printf("Cluster Health: %s\n", tea.ToString(health.Body.Result.Status))
    }
    
    // Round 5: Check logs
    fmt.Println("=== Round 5: Recent Logs ===")
    logs, err := client.ListSearchLog(&elasticsearch.ListSearchLogRequest{
        InstanceId: tea.String(instanceId),
        StartTime: tea.String(time.Now().Add(-1*time.Hour).Format("2006-01-02T15:04:05Z")),
        EndTime:   tea.String(time.Now().Format("2006-01-02T15:04:05Z")),
    })
    if err == nil {
        for _, log := range logs.Body.Result.Logs {
            if strings.Contains(tea.ToString(log.Content), "ERROR") {
                fmt.Printf("ERROR Log: %s\n", tea.ToString(log.Content)[:200])
            }
        }
    }
}
```

---

## 5. Escalation Template

When all diagnostic steps fail, use this escalation format:

```
[ESCALATE] Elasticsearch Instance Issue

Instance ID: {instanceId}
Region: {regionId}
Status: {status}
Error Code: {errorCode}
RequestId: {requestId}

Issue Description:
{description of problem}

Steps Taken:
1. DescribeInstance → status = {status}
2. DiagnoseInstance → reportId = {reportId}
3. ListSearchLog → {error patterns found}

Suspected Cause:
{hypothesis based on diagnostics}

Recommended Action:
{suggested resolution or need for manual intervention}

Support Channel: https://workorder.console.aliyun.com/
```

---

## 6. Multi-Round Self-Reflection Process (AIOps Pattern)

### 6.1 Self-Reflection Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  Multi-Round Self-Reflection Process                                │
│  Purpose: Iteratively refine diagnosis until satisfactory result     │
├─────────────────────────────────────────────────────────────────────┤
│  Round 1: Initial Diagnosis                                         │
│  ├── Run standard diagnostic procedure (§2)                         │
│  ├── Collect all observable symptoms                                │
│  ├── Generate initial root cause hypothesis                         │
│  ├── Confidence threshold: 0.5                                      │
│  └── Output: findings_1, hypothesis_1, confidence_1                 │
├─────────────────────────────────────────────────────────────────────┤
│  Round 2: Hypothesis Validation                                     │
│  ├── Test hypothesis_1 with targeted diagnostics                    │
│  ├── Gather evidence to support/refute hypothesis                   │
│  ├── If confidence < 0.7: Generate alternative hypothesis           │
│  ├── Cross-skill dependency check                                   │
│  └── Output: findings_2, hypothesis_2, confidence_2, new_findings   │
├─────────────────────────────────────────────────────────────────────┤
│  Round 3: Deep Analysis (if needed)                                 │
│  ├── If confidence < 0.85: Deep dive into logs/metrics              │
│  ├── Multi-metric correlation analysis                              │
│  ├── Historical pattern comparison                                  │
│  ├── Generate remediation action plan                               │
│  └── Output: findings_3, root_cause_final, remediation_plan         │
├─────────────────────────────────────────────────────────────────────┤
│  Round 4: Remediation Execution                                     │
│  ├── Execute remediation actions                                    │
│  ├── Monitor remediation progress                                   │
│  ├── Verify resolution                                              │
│  ├── If unresolved: Escalate or iterate                             │
│  └── Output: remediation_result, verification_status                │
├─────────────────────────────────────────────────────────────────────┤
│  Round 5: Post-Resolution Reflection                                │
│  ├── Validate issue fully resolved                                  │
│  ├── Update knowledge base with pattern                             │
│  ├── Document lessons learned                                       │
│  ├── Generate final diagnostic report                               │
│  ├── Output: final_report, satisfaction_status                      │
├─────────────────────────────────────────────────────────────────────┤
│  Satisfaction Criteria:                                              │
│  ├── confidence >= 0.85 AND                                         │
│  ├── remediation executed AND                                        │
│  ├── verification passed (status=Normal, health=green)              │
│  └── If unsatisfied: Return to Round 3 or escalate                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Self-Reflection Implementation

```go
func multiRoundSelfReflection(client *elasticsearch.Client, instanceId string, initialError error) *ReflectionResult {
    result := &ReflectionResult{
        InstanceId:    instanceId,
        InitialError:  initialError,
        StartTime:     time.Now(),
        Rounds:        []ReflectionRound{},
    }
    
    // Round 1: Initial Diagnosis
    round1 := runInitialDiagnosis(client, instanceId, initialError)
    result.Rounds = append(result.Rounds, round1)
    
    if round1.Confidence >= 0.85 {
        result.SatisfactionStatus = "Satisfied"
        result.FinalHypothesis = round1.Hypothesis
        return result
    }
    
    // Round 2: Hypothesis Validation
    round2 := validateHypothesis(client, instanceId, round1)
    result.Rounds = append(result.Rounds, round2)
    
    if round2.Confidence >= 0.85 {
        result.SatisfactionStatus = "Satisfied"
        result.FinalHypothesis = round2.Hypothesis
        return result
    }
    
    // Round 3: Deep Analysis
    round3 := deepAnalysis(client, instanceId, round2)
    result.Rounds = append(result.Rounds, round3)
    
    if round3.Confidence >= 0.85 {
        result.SatisfactionStatus = "Satisfied"
        result.FinalHypothesis = round3.Hypothesis
        // Execute remediation
        result.RemediationResult = executeRemediation(client, instanceId, round3.RemediationActions)
        return result
    }
    
    // Round 4: Remediation Execution (even with lower confidence)
    round4 := executeRemediationRound(client, instanceId, round3)
    result.Rounds = append(result.Rounds, round4)
    
    // Round 5: Post-Resolution Reflection
    round5 := postResolutionReflection(client, instanceId, round4)
    result.Rounds = append(result.Rounds, round5)
    
    if round5.VerificationPassed {
        result.SatisfactionStatus = "Satisfied"
    } else {
        result.SatisfactionStatus = "NeedsIteration"
        result.EscalationRequired = true
    }
    
    result.EndTime = time.Now()
    result.TotalDuration = result.EndTime.Sub(result.StartTime)
    
    return result
}

type ReflectionResult struct {
    InstanceId         string
    InitialError       error
    StartTime          time.Time
    EndTime            time.Time
    TotalDuration      time.Duration
    Rounds             []ReflectionRound
    FinalHypothesis    string
    RemediationResult  *RemediationResult
    SatisfactionStatus string // Satisfied, NeedsIteration, Escalate
    EscalationRequired bool
    FinalReportId      string
}

type ReflectionRound struct {
    RoundNumber      int
    Findings         []Finding
    NewFindingsCount int
    Hypothesis       string
    Confidence       float64
    Actions          []string
    Timestamp        time.Time
    Duration         time.Duration
}

func runInitialDiagnosis(client *elasticsearch.Client, instanceId string, err error) ReflectionRound {
    round := ReflectionRound{
        RoundNumber: 1,
        Timestamp:   time.Now(),
    }
    
    // Standard diagnostic procedure
    findings := standardDiagnostic(client, instanceId, err)
    round.Findings = findings
    
    // Generate hypothesis from findings
    hypothesis, confidence := generateHypothesis(findings)
    round.Hypothesis = hypothesis
    round.Confidence = confidence
    
    round.Duration = time.Since(round.Timestamp)
    return round
}

func validateHypothesis(client *elasticsearch.Client, instanceId string, prevRound ReflectionRound) ReflectionRound {
    round := ReflectionRound{
        RoundNumber:      2,
        Timestamp:        time.Now(),
        Findings:         prevRound.Findings,
        Hypothesis:       prevRound.Hypothesis,
    }
    
    // Test hypothesis with targeted checks
    evidence := testHypothesis(client, instanceId, prevRound.Hypothesis)
    
    // Calculate new confidence
    round.Confidence = calculateConfidence(prevRound.Confidence, evidence)
    
    // If low confidence, generate alternative hypothesis
    if round.Confidence < 0.7 {
        altHypothesis := generateAlternativeHypothesis(round.Findings)
        round.Hypothesis = altHypothesis
        round.Actions = append(round.Actions, "Generated alternative hypothesis")
    }
    
    // Cross-skill check
    crossSkillDeps := checkCrossSkillDependencies(instanceId, round.Findings)
    if len(crossSkillDeps) > 0 {
        round.Actions = append(round.Actions, "Cross-skill delegation required")
    }
    
    // Count new findings
    round.NewFindingsCount = countNewFindings(round.Findings, prevRound.Findings)
    
    round.Duration = time.Since(round.Timestamp)
    return round
}

func deepAnalysis(client *elasticsearch.Client, instanceId string, prevRound ReflectionRound) ReflectionRound {
    round := ReflectionRound{
        RoundNumber:      3,
        Timestamp:        time.Now(),
        Findings:         prevRound.Findings,
        Hypothesis:       prevRound.Hypothesis,
    }
    
    // Multi-metric correlation
    correlations := analyzeMetricCorrelations(instanceId)
    for _, corr := range correlations {
        round.Findings = append(round.Findings, Finding{
            Category:  "Correlation",
            Message:   corr.Description,
            Severity:  corr.Severity,
        })
    }
    
    // Historical pattern comparison
    historicalPatterns := compareHistoricalPatterns(instanceId, round.Findings)
    if len(historicalPatterns) > 0 {
        round.Actions = append(round.Actions, "Historical pattern matched")
    }
    
    // Generate remediation actions
    round.RemediationActions = generateRemediationActions(round.Hypothesis, round.Findings)
    
    round.Confidence = calculateFinalConfidence(prevRound.Confidence, correlations, historicalPatterns)
    round.NewFindingsCount = len(correlations)
    
    round.Duration = time.Since(round.Timestamp)
    return round
}
```

### 6.3 Satisfaction Criteria Matrix

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| **Confidence level** | ≥ 0.85 | Hypothesis validation score |
| **Root cause identified** | Yes | Clear, actionable hypothesis |
| **Remediation planned** | Yes | Specific action steps defined |
| **Cross-skill resolved** | Yes (if applicable) | Dependencies addressed |
| **Verification passed** | Yes | Status=Normal, Health=green |

### 6.4 Escalation Triggers

| Trigger | Condition | Action |
|---------|-----------|--------|
| **Low confidence** | Confidence < 0.5 after Round 3 | Escalate to specialist |
| **Cross-skill failure** | Delegation unsuccessful | Escalate with dependency details |
| **Remediation failed** | Action unsuccessful after 3 attempts | Escalate with error history |
| **Time threshold** | Duration > 30 minutes | Escalate to prevent extended downtime |
| **Verification failed** | Status != Normal after remediation | Iterate or escalate |

### 6.5 Self-Reflection Report Template

```markdown
# Multi-Round Self-Reflection Report

**Instance:** {{instance_id}}
**Initial Error:** {{initial_error}}
**Duration:** {{total_duration}}
**Satisfaction Status:** {{satisfaction_status}}

## Round Summary

| Round | New Findings | Confidence | Key Action |
|-------|--------------|------------|------------|
{{#each rounds}}
| {{round_number}} | {{new_findings_count}} | {{confidence}}% | {{primary_action}} |
{{/each}}

## Final Hypothesis

{{final_hypothesis}}

## Remediation Executed

{{#each remediation_result.actions}}
- {{name}}: {{status}}
{{/each}}

## Verification

- Instance Status: {{verification.status}}
- Cluster Health: {{verification.health}}
- Result: {{verification.result}}

## Lessons Learned

{{#each lessons}}
- {{.}}
{{/each}}

## Escalation Required

{{#if escalation_required}}
Yes - Reason: {{escalation_reason}}
{{else}}
No - Issue resolved through self-reflection
{{/if}}
```

---

*For diagnostic report schema, see [../reports/diagnostic-report-schema.md](../reports/diagnostic-report-schema.md).*
# Integration — Alibaba Cloud Elasticsearch

> **Purpose:** SDK setup, environment configuration, automation patterns, cross-skill delegation.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-17

---

## 1. Environment Setup

### Prerequisites

| Requirement | Minimum Version | Recommended |
|-------------|----------------|-------------|
| Go runtime | 1.21 | 1.24+ |
| Network | HTTPS outbound to `*.aliyuncs.com` | VPC endpoint preferred |
| Credentials | AK/SK pair with RAM policy | STS temporary credentials |

### Environment Variables

```bash
# Required
export ALIBABA_CLOUD_ACCESS_KEY_ID="<your-access-key-id>"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="<your-access-key-secret>"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# Optional
export ALIBABA_CLOUD_SECURITY_TOKEN="<sts-token>"      # For STS auth
export ALIBABA_CLOUD_ENDPOINT="elasticsearch.aliyuncs.com"
export GOPROXY="https://goproxy.cn,direct"              # China mirror
```

---

## 2. SDK Bootstrap

### JIT Go Runtime Setup

```bash
# Check and download Go if needed
if ! command -v go &> /dev/null; then
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    [ "$ARCH" = "x86_64" ] && ARCH="amd64"
    [ "$ARCH" = "aarch64" ] && ARCH="arm64"
    
    mkdir -p /tmp/go-runtime
    curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
    
    export PATH="/tmp/go-runtime/go/bin:$PATH"
    export GOPATH="/tmp/go-workspace"
    export GOCACHE="/tmp/go-cache"
    export GOMODCACHE="/tmp/go-modcache"
fi

go version
```

### SDK Workspace Setup

```bash
# Create workspace
mkdir -p /tmp/aliyun-es-workspace
cd /tmp/aliyun-es-workspace

# Initialize module
go mod init es-operations

# Core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service

# Elasticsearch SDK (v6 for 2017-06-13 API)
go get github.com/alibabacloud-go/elasticsearch-20170613/v6/client
```

---

## 3. Client Configuration

### Basic Client (AK/SK)

```go
package main

import (
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    elasticsearch "github.com/alibabacloud-go/elasticsearch-20170613/v6/client"
)

func createClient() (*elasticsearch.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("elasticsearch.aliyuncs.com"),
    }
    
    return elasticsearch.NewClient(config)
}
```

### STS Client (Temporary Credentials)

```go
func createSTSClient() (*elasticsearch.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        SecurityToken:   tea.String(os.Getenv("ALIBABA_CLOUD_SECURITY_TOKEN")),
        Endpoint:        tea.String("elasticsearch.aliyuncs.com"),
    }
    
    return elasticsearch.NewClient(config)
}
```

### VPC Endpoint Client (Internal Network)

```go
func createVPCClient(regionId string) (*elasticsearch.Client, error) {
    endpoint := fmt.Sprintf("%s.elasticsearch-vpc.aliyuncs.com", regionId)
    
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String(endpoint),
    }
    
    return elasticsearch.NewClient(config)
}
```

---

## 4. Automation Patterns

### Batch Instance Management

```go
func batchUpdateNodeSpec(client *elasticsearch.Client, instanceIds []string, newSpec string) {
    for _, instanceId := range instanceIds {
        request := &elasticsearch.UpdateInstanceRequest{
            InstanceId: tea.String(instanceId),
            NodeSpec:   tea.String(newSpec),
        }
        
        _, err := client.UpdateInstance(request)
        if err != nil {
            fmt.Printf("❌ Failed to update %s: %v\n", instanceId, err)
            continue
        }
        
        fmt.Printf("✅ Updated %s\n", instanceId)
        
        // Wait for instance to stabilize before next update
        waitForInstance(client, instanceId, "Normal", 300)
    }
}

func waitForInstance(client *elasticsearch.Client, instanceId string, targetStatus string, timeoutSeconds int) {
    for i := 0; i < timeoutSeconds/10; i++ {
        resp, err := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
            InstanceId: tea.String(instanceId),
        })
        if err != nil {
            panic(err)
        }
        
        status := tea.ToString(resp.Body.Result.Status)
        if status == targetStatus {
            return
        }
        time.Sleep(10 * time.Second)
    }
    fmt.Printf("⚠️ Timeout waiting for %s\n", instanceId)
}
```

### Scheduled Snapshot Automation

```go
func createScheduledSnapshot(client *elasticsearch.Client, instanceId string) {
    snapshotName := fmt.Sprintf("daily-backup-%s", time.Now().Format("20060102"))
    
    request := &elasticsearch.CreateSnapshotRequest{
        InstanceId:    tea.String(instanceId),
        SnapshotName:  tea.String(snapshotName),
        Description:   tea.String("Automated daily backup"),
    }
    
    response, err := client.CreateSnapshot(request)
    if err != nil {
        fmt.Printf("❌ Snapshot failed: %v\n", err)
        return
    }
    
    fmt.Printf("✅ Snapshot created: %s\n", tea.ToString(response.Body.Result.SnapshotId))
}
```

### Health Check Automation

```go
func checkClusterHealth(client *elasticsearch.Client, instanceId string) (string, error) {
    response, err := client.DescribeElasticsearchHealth(&elasticsearch.DescribeElasticsearchHealthRequest{
        InstanceId: tea.String(instanceId),
    })
    if err != nil {
        return "", err
    }
    
    health := tea.ToString(response.Body.Result.Status)
    
    switch health {
    case "green":
        fmt.Println("✅ Cluster healthy (green)")
    case "yellow":
        fmt.Println("⚠️ Cluster degraded (yellow) - check unassigned shards")
    case "red":
        fmt.Println("🚨 Cluster unhealthy (red) - immediate investigation needed")
    }
    
    return health, nil
}
```

---

## 6. Cross-Skill Diagnosis Decision Tree (AIOps Pattern)

### 6.1 5-Step Cross-Skill Diagnosis Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: Error Classification (Local Diagnosis)                    │
│  ├── Classify error code (Throttling, InstanceNotFound, etc.)      │
│  ├── Identify if error is Elasticsearch-specific                   │
│  └── Determine cross-skill dependency need                         │
├─────────────────────────────────────────────────────────────────────┤
│  Step 2: Dependency Analysis (Cross-Skill Check)                   │
│  ├── Check VPC dependency: Does error involve VPC/VSwitch?        │
│  ├── Check RAM dependency: Is Forbidden.RAM error?                │
│  ├── Check CMS dependency: Need monitoring/alert integration?     │
│  └── Check ActionTrail dependency: Need audit trail?              │
│  Decision Matrix:                                                   │
│  ┌─────────────────────┬───────────────────────────────────────┐  │
│  │ Error Code          │ Required Skill                         │  │
│  ├─────────────────────┼───────────────────────────────────────┤  │
│  │ VpcNotFound         │ alicloud-vpc-ops (create VPC)          │  │
│  │ VswitchNotFound     │ alicloud-vpc-ops (create VSwitch)      │  │
│  │ Forbidden.RAM       │ alicloud-ram-ops (fix permissions)     │  │
│  │ Connection issues   │ alicloud-vpc-ops + alicloud-ecs-ops    │  │
│  │ Monitoring setup    │ alicloud-cms-ops                       │  │
│  │ Audit trail         │ alicloud-actiontrail-ops               │  │
│  └─────────────────────┴───────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  Step 3: Cross-Skill Delegation (Execute)                          │
│  ├── Prepare delegation input (instance_id, error context)         │
│  ├── Call target skill with specific operation                     │
│  ├── Monitor delegation progress                                   │
│  └── Capture output for integration                                │
│  Example:                                                           │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ VpcNotFound → Delegate to alicloud-vpc-ops                    │ │
│  │   Execute: CreateVpc(regionId, vpcName)                       │ │
│  │   Output: {{output.vpc_id}}                                   │ │
│  │   Return: Resume CreateInstance with {{output.vpc_id}}        │ │
│  └───────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│  Step 4: Integration & Verification (Post-Delegation)              │
│  ├── Integrate delegation output into local operation               │
│  ├── Execute local operation with integrated inputs                │
│  ├── Verify operation success                                      │
│  └── Validate cross-skill resolution effectiveness                 │
│  Verification Checklist:                                           │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ □ Delegation output received and valid                        │ │
│  │ □ Local operation executed successfully                      │ │
│  │ □ DescribeInstance → Status = Normal                         │ │
│  │ □ Cluster health verified                                    │ │
│  │ □ Cross-skill issue resolved                                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│  Step 5: Report & Escalation (Closure)                             │
│  ├── Generate diagnostic report with cross-skill details           │
│  ├── Document cross-skill dependency resolution                    │
│  ├── Update skill knowledge base with pattern                      │
│  └── Escalate if unresolved after delegation                      │
│  Report Fields:                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ cross_skill_dependencies:                                     │ │
│  │   - skill_name: alicloud-vpc-ops                              │ │
│  │     dependency_type: required                                 │ │
│  │     status: resolved                                          │ │
│  │     operation: CreateVpc                                      │ │
│  │     output: vpc-abc123                                        │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Cross-Skill Diagnosis Code Template

```go
func crossSkillDiagnosis(client *elasticsearch.Client, instanceId string, errorCode string) *DiagnosisResult {
    result := &DiagnosisResult{
        InstanceId:    instanceId,
        ErrorCode:     errorCode,
        Timestamp:     time.Now(),
    }
    
    // Step 1: Error Classification
    fmt.Println("=== Step 1: Error Classification ===")
    classification := classifyError(errorCode)
    fmt.Printf("Error: %s | Category: %s | CrossSkillNeed: %v\n",
        errorCode, classification.Category, classification.RequiresCrossSkill)
    
    if !classification.RequiresCrossSkill {
        result.DiagnosisPath = "Local"
        return result
    }
    
    // Step 2: Dependency Analysis
    fmt.Println("=== Step 2: Dependency Analysis ===")
    dependencies := analyzeDependencies(errorCode)
    for _, dep := range dependencies {
        fmt.Printf("Dependency: %s | Skill: %s | Type: %s\n",
            dep.Dependency, dep.RequiredSkill, dep.DependencyType)
        result.CrossSkillDependencies = append(result.CrossSkillDependencies, dep)
    }
    
    // Step 3: Cross-Skill Delegation
    fmt.Println("=== Step 3: Cross-Skill Delegation ===")
    for _, dep := range dependencies {
        delegationResult := delegateToSkill(dep.RequiredSkill, dep.Operation, instanceId)
        fmt.Printf("Delegation to %s: %s\n", dep.RequiredSkill, delegationResult.Status)
        
        if delegationResult.Status == "Success" {
            result.DelegationOutputs = append(result.DelegationOutputs, delegationResult)
        } else {
            result.Status = "DelegationFailed"
            return result
        }
    }
    
    // Step 4: Integration & Verification
    fmt.Println("=== Step 4: Integration & Verification ===")
    integrationSuccess := integrateDelegationOutputs(client, instanceId, result.DelegationOutputs)
    if !integrationSuccess {
        result.Status = "IntegrationFailed"
        return result
    }
    
    // Verify resolution
    inst, _ := client.DescribeInstance(&elasticsearch.DescribeInstanceRequest{
        InstanceId: tea.String(instanceId),
    })
    status := tea.ToString(inst.Body.Result.Status)
    fmt.Printf("Verification: Instance status=%s\n", status)
    
    if status == "Normal" {
        result.Status = "Resolved"
    } else {
        result.Status = "VerificationFailed"
    }
    
    // Step 5: Report & Escalation
    fmt.Println("=== Step 5: Report & Escalation ===")
    report := generateDiagnosticReport(instanceId, "cross_skill_diagnosis", result)
    result.ReportId = report.ReportId
    
    if result.Status != "Resolved" {
        result.EscalationRequired = true
        result.EscalationReason = "Cross-skill diagnosis unresolved"
    }
    
    return result
}

type DiagnosisResult struct {
    InstanceId           string
    ErrorCode            string
    Timestamp            time.Time
    Status               string
    DiagnosisPath        string
    CrossSkillDependencies []CrossSkillDependency
    DelegationOutputs    []DelegationOutput
    ReportId             string
    EscalationRequired   bool
    EscalationReason     string
}

type CrossSkillDependency struct {
    Dependency       string
    RequiredSkill    string
    DependencyType   string // required, optional, fallback
    Operation        string
}

type DelegationOutput struct {
    Skill    string
    Operation string
    Status   string
    Output   string
}
```

---

## 7. Cross-Skill Delegation Matrix (Enhanced)

### 7.1 Extended Delegation Matrix for AIOps

| Primary Issue | Dependency Analysis | Required Skill | Delegation Operation | Return Criteria |
|---------------|--------------------|----------------|--------------------|-----------------|
| **VpcNotFound** | VPC infrastructure missing | alicloud-vpc-ops | CreateVpc | VPC ID returned |
| **VswitchNotFound** | VSwitch missing in zone | alicloud-vpc-ops | CreateVSwitch | VSwitch ID returned |
| **Forbidden.RAM** | Permission denied | alicloud-ram-ops | AttachPolicyToUser | Policy attached |
| **ConnectionTimeout** | Network ACL/SG blocking | alicloud-ecs-ops | ModifySecurityGroupRule | SG rule updated |
| **MonitoringSetup** | Need alert rules | alicloud-cms-ops | CreateAlertRule | Alert rule active |
| **AuditTrail** | Need operation history | alicloud-actiontrail-ops | LookupEvents | Events retrieved |
| **CostEstimation** | Need pricing info | alicloud-bss-ops | GetPrice | Price retrieved |

### 7.2 Cross-Skill Delegation Templates

```yaml
Template: VpcNotFound Resolution

Trigger: Error code = "VpcNotFound"
Analysis:
  - VPC ID invalid or deleted
  - Region mismatch possible
  
Delegation:
  Skill: alicloud-vpc-ops
  Operations:
    1. DescribeVpc → Check if VPC exists
    2. If not exists: CreateVpc → {{output.vpc_id}}
  
Integration:
  Resume: CreateInstance with {{output.vpc_id}}
  
Verification:
  DescribeInstance → Status = Normal
  
Report:
  cross_skill_dependencies:
    - skill_name: alicloud-vpc-ops
      status: resolved
      operation: CreateVpc
      output: {{output.vpc_id}}

---

Template: Forbidden.RAM Resolution

Trigger: Error code = "Forbidden.RAM"
Analysis:
  - RAM policy missing elasticsearch permissions
  - User/role lacks required actions
  
Delegation:
  Skill: alicloud-ram-ops
  Operations:
    1. GetPolicyForUser → Check current policy
    2. CreatePolicy → Define Elasticsearch policy
    3. AttachPolicyToUser → Attach to user
  
Integration:
  Retry: Original operation after policy attach
  
Verification:
  DescribeInstance → Success (no Forbidden.RAM)
  
Report:
  cross_skill_dependencies:
    - skill_name: alicloud-ram-ops
      status: resolved
      operation: AttachPolicyToUser
      output: policy-attached

---

Template: ConnectionTimeout Resolution

Trigger: Connection refused to ES endpoint
Analysis:
  - Whitelist blocking client IP
  - Security group rules blocking
  - VPC routing issue
  
Delegation:
  Skills: [alicloud-vpc-ops, alicloud-ecs-ops]
  Operations:
    1. (alicloud-vpc-ops) DescribeVpc → Check VPC routing
    2. (alicloud-ecs-ops) DescribeSecurityGroupRules → Check SG
    3. (alicloud-ecs-ops) ModifySecurityGroupRule → Allow ES port
  
Integration:
  Retry: Connection test after SG update
  
Verification:
  Connection established successfully
  
Report:
  cross_skill_dependencies:
    - skill_name: alicloud-vpc-ops
      status: resolved
      operation: DescribeVpc
    - skill_name: alicloud-ecs-ops
      status: resolved
      operation: ModifySecurityGroupRule
```

---

## 8. Cross-Skill Dependency Tracking

### 8.1 Dependency Resolution Tracking

```go
func trackDependencyResolution(result *DiagnosisResult) *DependencyReport {
    report := &DependencyReport{
        InstanceId:    result.InstanceId,
        Timestamp:     time.Now(),
        TotalDeps:     len(result.CrossSkillDependencies),
    }
    
    resolved := 0
    pending := 0
    failed := 0
    
    for _, dep := range result.CrossSkillDependencies {
        for _, output := range result.DelegationOutputs {
            if output.Skill == dep.RequiredSkill {
                if output.Status == "Success" {
                    resolved++
                    report.ResolvedDeps = append(report.ResolvedDeps, dep)
                } else if output.Status == "Failed" {
                    failed++
                    report.FailedDeps = append(report.FailedDeps, dep)
                } else {
                    pending++
                    report.PendingDeps = append(report.PendingDeps, dep)
                }
            }
        }
    }
    
    report.ResolvedCount = resolved
    report.PendingCount = pending
    report.FailedCount = failed
    
    if failed > 0 {
        report.OverallStatus = "Failed"
    } else if pending > 0 {
        report.OverallStatus = "InProgress"
    } else {
        report.OverallStatus = "Resolved"
    }
    
    return report
}

type DependencyReport struct {
    InstanceId     string
    Timestamp      time.Time
    TotalDeps      int
    ResolvedCount  int
    PendingCount   int
    FailedCount    int
    OverallStatus  string
    ResolvedDeps   []CrossSkillDependency
    PendingDeps    []CrossSkillDependency
    FailedDeps     []CrossSkillDependency
}
```

### Retry Strategy

```go
func retryWithBackoff(client *elasticsearch.Client, request interface{}, maxRetries int) {
    backoff := 2 * time.Second
    
    for attempt := 1; attempt <= maxRetries; attempt++ {
        // Execute request (type assertion needed)
        response, err := executeRequest(client, request)
        
        if err == nil {
            return response, nil
        }
        
        // Check error type
        if isNonRetryableError(err) {
            return nil, err  // HALT
        }
        
        fmt.Printf("⚠️ Attempt %d failed, retrying in %v...\n", attempt, backoff)
        time.Sleep(backoff)
        backoff = backoff * 2  // Exponential backoff
    }
    
    return nil, fmt.Errorf("max retries exceeded")
}

func isNonRetryableError(err error) bool {
    if sdkErr, ok := err.(*tea.SDKError); ok {
        code := tea.ToString(sdkErr.Code)
        nonRetryableCodes := []string{
            "InvalidParameter", "InstanceNotFound", "QuotaExceeded",
            "Forbidden.RAM", "VpcNotFound", "VswitchNotFound",
        }
        for _, c := range nonRetryableCodes {
            if code == c {
                return true
            }
        }
    }
    return false
}
```

---

## 7. CI/CD Integration

### Pipeline Integration Template

```yaml
# .github/workflows/es-management.yml
name: Elasticsearch Operations

on:
  workflow_dispatch:
    inputs:
      operation:
        description: 'Operation type'
        required: true
        default: 'list'
      instance_id:
        description: 'Instance ID'
        required: false

env:
  ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_ID }}
  ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIBABA_CLOUD_ACCESS_KEY_SECRET }}
  ALIBABA_CLOUD_REGION_ID: cn-hangzhou

jobs:
  es-operation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-go@v4
        with:
          go-version: '1.24'
      
      - run: |
          mkdir -p /tmp/es-workspace
          cd /tmp/es-workspace
          go mod init es-ci
          go get github.com/alibabacloud-go/elasticsearch-20170613/v6/client
          go get github.com/alibabacloud-go/darabonba-openapi/v2/client
          go get github.com/alibabacloud-go/tea
      
      - run: |
          cd /tmp/es-workspace
          # Generate and execute operation script
          go run ./main.go
```

---

## 8. Credential Security

### Security Rules

| Context | Required Behavior |
|---------|-------------------|
| Console output | Mask all credential values with first 4 chars + `****` (e.g., `abcd****`) |
| Log files | Never log `AccessKeySecret` |
| Error messages | Sanitize credential fields before display |
| CI/CD secrets | Use secret store, never commit credentials |
| Go SDK scripts | Use `os.Getenv()` only, no hardcoded values |

### Credential Verification

```go
// Safe credential check (existence only, never expose value)
func verifyCredentials() error {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    
    if ak == "" {
        return fmt.Errorf("ALIBABA_CLOUD_ACCESS_KEY_ID not set")
    }
    if sk == "" {
        return fmt.Errorf("ALIBABA_CLOUD_ACCESS_KEY_SECRET not set")
    }
    
    // Masked output
    fmt.Printf("✅ ALIBABA_CLOUD_ACCESS_KEY_ID: %s****\n", ak[:4])
    fmt.Printf("✅ ALIBABA_CLOUD_ACCESS_KEY_SECRET: %s****\n", sk[:4])
    
    return nil
}
```

---

*For Well-Architected assessment patterns, see [well-architected-assessment.md](well-architected-assessment.md).*
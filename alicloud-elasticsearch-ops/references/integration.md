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

## 5. Cross-Skill Delegation Matrix

| Dependency | Required Skill | Delegation Pattern |
|------------|----------------|-------------------|
| VPC creation | `alicloud-vpc-ops` | Create VPC → Get VPC ID → Create ES |
| VSwitch creation | `alicloud-vpc-ops` | Create VSwitch → Get VSwitch ID → Create ES |
| Security group | `alicloud-ecs-ops` | Create SG → Get SG ID → Configure ES whitelist |
| RAM policy | `alicloud-ram-ops` | Create policy → Attach to RAM user |
| Monitoring alerts | `alicloud-cms-ops` | Create alert rule → Link to ES instance |

### Delegation Flow Example

```yaml
# Create Elasticsearch instance with dependencies

Step 1: Create VPC (alicloud-vpc-ops)
  - Execute: CreateVpc
  - Output: {{output.vpc_id}}

Step 2: Create VSwitch (alicloud-vpc-ops)
  - Execute: CreateVSwitch
  - Input: {{output.vpc_id}}, zoneId
  - Output: {{output.vswitch_id}}

Step 3: Create Elasticsearch (this skill)
  - Execute: CreateInstance
  - Input: {{output.vpc_id}}, {{output.vswitch_id}}
  - Output: {{output.instance_id}}

Step 4: Configure whitelist (optional)
  - Execute: ModifyWhiteIps
  - Input: {{output.instance_id}}, user.ip_list
```

---

## 6. Error Handling & Retry

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
| Console output | Mask all credential values with `<masked>` or `***` |
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
    fmt.Printf("✅ ALIBABA_CLOUD_ACCESS_KEY_ID: %s***\n", ak[:4])
    fmt.Println("✅ ALIBABA_CLOUD_ACCESS_KEY_SECRET: <masked>")
    
    return nil
}
```

---

*For Well-Architected assessment patterns, see [well-architected-assessment.md](well-architected-assessment.md).*
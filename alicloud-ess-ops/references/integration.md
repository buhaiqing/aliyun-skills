# Integration — Auto Scaling (ESS)

> Version: 1.0.0 | Last Updated: 2026-06-07

## Go Bootstrap

### Prerequisites
- Go 1.21+ (1.24+ for JIT mode)
- `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID`

### Quick Start Script

```go
package main

import (
    "fmt"
    "os"
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    ess "github.com/alibabacloud-go/ess-20140828/v2/client"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    // Read credentials from environment (NEVER hardcode)
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    client, err := ess.NewClient(config)
    if err != nil {
        panic(fmt.Sprintf("Failed to create ESS client: %v", err))
    }

    // Example: List scaling groups
    resp, err := client.DescribeScalingGroups(&ess.DescribeScalingGroupsRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        PageSize: tea.Int(20),
    })
    if err != nil {
        panic(fmt.Sprintf("API call failed: %v", err))
    }
    fmt.Printf("Found %d scaling groups\n", tea.Int32Value(resp.Body.TotalCount))
}
```

> ⚠️ **NEVER** `fmt.Printf("%+v", config)` — it leaks `AccessKeySecret`.
> ⚠️ **NEVER** `log.Printf("%+v", response)` if response may contain credential info.

### Client Factory Pattern

```go
func NewESSClient() (*ess.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    return ess.NewClient(config)
}
```

### JIT Go SDK Usage

For one-off operations, create a `.go` file in a temp directory and run:
```bash
cd /tmp/ess-jit-$$
cat > main.go << 'GOEOF'
// ... Go code as above ...
GOEOF
go mod init ess-jit && go mod tidy && go run .
```

## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | Access key ID | `LTAI5t...` |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | Access key secret | `<masked>` |
| `ALIBABA_CLOUD_REGION_ID` | Yes | Region code | `cn-hangzhou` |

## Cross-Skill Delegation

| Scenario | Delegate To | Reason |
|----------|------------|--------|
| Create ECS instances for scaling | `alicloud-ecs-ops` | ECS lifecycle management |
| Configure ALB listeners/rules | `alicloud-alb-ops` | ALB configuration |
| Configure CLB listeners | `alicloud-slb-ops` | CLB configuration |
| Manage RDS instances | `alicloud-rds-ops` | RDS lifecycle |
| Create VPC/VSwitches | `alicloud-vpc-ops` | Network setup |
| RAM policies for ESS | `alicloud-ram-ops` | Permission management |
| CMS alarm configuration | `alicloud-cms-ops` | CloudMonitor integration |
| GCL quality gate | `alicloud-gcl-runner-ops` | Pre-execution adversarial review |

## Credential Security

- **DO NOT** hardcode credentials in scripts or configs
- **DO NOT** log, echo, or print `AccessKeySecret`
- **DO** use environment variables exclusively
- **DO** verify credential existence without displaying values:
  ```bash
  # ✅ Safe
  test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" || echo "❌ Secret not set"
  
  # ❌ Unsafe — NEVER do this
  echo "Secret: $ALIBABA_CLOUD_ACCESS_KEY_SECRET"
  ```
# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

### Enhanced Self-Healing Framework (MANDATORY)

All installation flows MUST follow the **Enhanced Self-Healing Framework** defined in [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

**Key Self-Healing Capabilities:**
- **Pre-flight Checks:** Network connectivity, disk space, permissions, system compatibility
- **Intelligent Error Classification:** Network, permission, resource, configuration errors
- **Multi-Path Self-Healing:** Multiple recovery strategies per error type
- **Health Verification:** Post-installation validation with health score ≥ 8/10
- **Graceful Degradation:** Clear fallback paths when self-healing fails

### Go Runtime Bootstrap (Enhanced Self-Healing)

The Agent MUST use enhanced self-healing for Go runtime JIT download:

**Multi-Version & Multi-Mirror Strategy:**
- **Primary:** Go 1.24+ (latest stable)
- **Fallback:** Go 1.23 → 1.22 → 1.21 (minimum compatibility)
- **Mirrors:** Official + China CDN mirrors (4 mirrors)

**Self-Healing Capabilities:**

| Error Type | Self-Healing Actions | Max Attempts |
|------------|---------------------|--------------|
| Download timeout | Mirror switch, timeout increase, version fallback | 4 versions × 4 mirrors |
| Download incomplete | File size check (>100MB), re-download, cache clear | 3 |
| Extract failure | Integrity check, re-download, clean workspace | 2 |
| Version incompatible | Fallback to compatible version (go1.21+) | 4 versions |
| PATH setup fail | Use absolute path, verify binary exists | 1 |

**Health Check:**
- Go binary exists and executable
- Version ≥ go1.21
- Workspace initialized
- Dependencies cached

For detailed implementation, see [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../../alicloud-skill-generator/references/enhanced-self-healing-framework.md) Section 3.2.

### JIT SDK Script Template

```bash
# Initialize workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Get dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service
go get github.com/alibabacloud-go/ecs-20140526/v4/client
```

### SDK Script Example

```go
package main

import (
	"fmt"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	ecs "github.com/alibabacloud-go/ecs-20140526/v4/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	client, err := ecs.NewClient(config)
	if err != nil {
		panic(err)
	}

	req := &ecs.DescribeInstancesRequest{
		RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	resp, err := client.DescribeInstances(req)
	if err != nil {
		panic(err)
	}

	fmt.Println(tea.ToString(resp.Body))
}
```

Execute:
```bash
go run ./main.go
```

## Cross-Product Dependencies

| This Skill Needs | From Skill | Verification Command |
|------------------|------------|---------------------|
| VPC/VSwitch | `alicloud-vpc-ops` | `aliyun vpc DescribeVpcs --RegionId ...` |
| RAM permissions | `alicloud-ram-ops` | `aliyun ram GetPolicy ...` |
| Security group rules | `alicloud-ecs-ops` (this skill) | `aliyun ecs DescribeSecurityGroups ...` |
| Monitoring/Alerts | `alicloud-cms-ops` | `aliyun cms DescribeMetricList ...` |
| Auto Scaling | `alicloud-ess-ops` | `aliyun ess DescribeScalingGroups ...` |

## Credential Sources (Priority Order)

| Priority | Source | Description |
|----------|--------|-------------|
| 1 (highest) | CLI flags | `--access-key-id`, `--access-key-secret`, `--region` |
| 2 | Shell environment | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID` |
| 3 | `~/.aliyun/config.json` | Persistent profile config (JSON format) |
| 4 (lowest) | Default profile | `default` profile from config file |

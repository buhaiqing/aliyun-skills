# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

### Enhanced Self-Healing Framework (MANDATORY)

All installation flows MUST follow the **Enhanced Self-Healing Framework** defined in [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

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

For detailed implementation, see [alicloud-skill-generator/references/enhanced-self-healing-framework.md](../alicloud-skill-generator/references/enhanced-self-healing-framework.md) Section 3.2.

### JIT Go SDK Setup for SLB

```bash
# Create workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace

# Initialize Go module
go mod init sdk-script

# Get core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service

# Get SLB SDK
go get github.com/alibabacloud-go/slb-20140515/v2/client
```

### Example JIT Script

```go
// /tmp/aliyun-sdk-workspace/slb-example.go
package main

import (
	"fmt"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	slb "github.com/alibabacloud-go/slb-20140515/v2/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	c, err := slb.NewClient(config)
	if err != nil {
		panic(err)
	}

	// Example: Describe all SLB instances
	req := &slb.DescribeLoadBalancersRequest{
		RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	resp, err := c.DescribeLoadBalancers(req)
	if err != nil {
		panic(err)
	}

	fmt.Println(tea.ToString(resp.Body))
}
```

Execute:
```bash
cd /tmp/aliyun-sdk-workspace
go run ./slb-example.go
```

## aliyun CLI Setup

### Install

```bash
# Official installer (auto-detects OS/arch)
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

# Or Homebrew (macOS)
brew install aliyun-cli
```

### Configure

```bash
# Environment variables (preferred for Agent)
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"

# Or interactive
aliyun configure

# Or config file
mkdir -p ~/.aliyun
cat > ~/.aliyun/config.json << 'EOF'
{
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AK",
      "access_key_id": "{{user.access_key_id}}",
      "access_key_secret": "{{user.access_key_secret}}",
      "region_id": "{{user.region}}"
    }
  ]
}
EOF
```

### Verify

```bash
aliyun slb DescribeRegions
```

## Cross-Product Integration

### With ECS

When backend servers are ECS instances:

```bash
# Verify ECS instance exists (delegate to alicloud-ecs-ops)
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --InstanceIds '["i-bp67acfmxazb4ph***"]'

# Then add to SLB
aliyun slb AddBackendServers \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --BackendServers '[{"ServerId":"i-bp67acfmxazb4ph***","Weight":"100"}]'
```

### With VPC

When creating SLB in VPC:

```bash
# Verify VPC exists (delegate to alicloud-vpc-ops)
aliyun vpc DescribeVpcs \
  --RegionId cn-hangzhou \
  --VpcId vpc-bp67acfmxazb4ph***

# Verify VSwitch exists
aliyun vpc DescribeVSwitches \
  --RegionId cn-hangzhou \
  --VpcId vpc-bp67acfmxazb4ph*** \
  --VSwitchId vsw-bp67acfmxazb4ph***

# Then create SLB
aliyun slb CreateLoadBalancer \
  --RegionId cn-hangzhou \
  --VpcId vpc-bp67acfmxazb4ph*** \
  --VSwitchId vsw-bp67acfmxazb4ph***
```

### With CMS (CloudMonitor)

For monitoring and alerts:

```bash
# Query SLB metrics (delegate to alicloud-cms-ops for detailed setup)
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceTrafficRX \
  --Dimensions '{"instanceId":"lb-bp67acfmxazb4ph***"}'
```

### With OSS

For access log storage:

```bash
# Enable access log forwarding to OSS
aliyun slb SetAccessLogsDownloadAttribute \
  --LoadBalancerId lb-bp67acfmxazb4ph*** \
  --LogsDownloadStatus on \
  --LogProject slb-logs \
  --LogStore slb-access-logs
```

## MCP Integration Notes

When integrating with Model Context Protocol (MCP):

- Use `{{env.*}}` placeholders for credentials in MCP tool definitions
- Document required environment variables in MCP server configuration
- SLB operations are generally fast (< 5s); use synchronous MCP responses
- For polling operations (create/delete), consider async MCP patterns

## Security Notes

- **NEVER** commit `.env` files to version control
- **NEVER** log certificate private keys
- **NEVER** expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET` in output
- Use RAM roles with minimal permissions for production
- Enable deletion protection for production SLB instances
- Regularly rotate SSL certificates before expiry

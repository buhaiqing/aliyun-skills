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

### SDK Dependencies

```bash
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script

# Core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service

# RDS-specific SDK
go get github.com/alibabacloud-go/rds-20140815/v2/client
```

### Credential Verification

```bash
# Primary: aliyun CLI validation
aliyun rds DescribeRegions

# Fallback: Go SDK credential check
cat > /tmp/aliyun-sdk-workspace/verify.go << 'EOF'
package main

import (
    "fmt"
    "os"
)

func main() {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    if ak == "" || sk == "" {
        fmt.Println("Missing ALIBABA_CLOUD_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        os.Exit(1)
    }
    fmt.Println("Credentials OK")
}
EOF
go run /tmp/aliyun-sdk-workspace/verify.go
```

> **SECURITY WARNING:** The verification code above **ONLY checks for existence**
> of credentials. **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
> in console output.

## Cross-Product Integration

| Scenario | Primary Skill | Delegated Skill | Integration Point |
|----------|--------------|-----------------|-------------------|
| Create RDS in VPC | `alicloud-rds-ops` | `alicloud-vpc-ops` | Verify VPC/VSwitch before CreateDBInstance |
| RDS with ECS access | `alicloud-rds-ops` | `alicloud-ecs-ops` | Add ECS security group IPs to RDS whitelist |
| RDS backup to OSS | `alicloud-rds-ops` | `alicloud-oss-ops` | Configure cross-region backup storage |
| RDS monitoring | `alicloud-rds-ops` | `alicloud-cms-ops` | Set up CloudMonitor alerts |
| RDS with RAM | `alicloud-rds-ops` | `alicloud-ram-ops` | Configure service-linked roles |

## API Profile

- **Service Code**: `rds`
- **API Version**: `2014-08-15`
- **Endpoint Pattern**: `rds.aliyuncs.com` (global), `rds.{{region}}.aliyuncs.com` (regional)
- **Protocol**: HTTPS (RPC-style)
- **SDK Package**: `github.com/alibabacloud-go/rds-20140815/v2/client`

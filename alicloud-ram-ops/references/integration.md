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

### JIT Go SDK Workflow

1. **Initialize workspace:**
   ```bash
   mkdir -p /tmp/aliyun-sdk-workspace
   cd /tmp/aliyun-sdk-workspace
   go mod init sdk-script
   ```

2. **Get dependencies:**
   ```bash
   export GOPROXY="https://goproxy.cn,direct"

   # Core dependencies
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/tea-utils/v2/service

   # RAM SDK
   go get github.com/alibabacloud-go/ram-20150501/v2/client

   # STS SDK
   go get github.com/alibabacloud-go/sts-20150401/v2/client
   ```

3. **Generate script** (Agent dynamically creates operation-specific .go file)

4. **Execute:**
   ```bash
   go run ./main.go
   ```

### SDK Package Naming

| Product | Go SDK Package |
|---------|---------------|
| RAM | `github.com/alibabacloud-go/ram-20150501/v2/client` |
| STS | `github.com/alibabacloud-go/sts-20150401/v2/client` |

## Environment Variable Loading

Credentials can be sourced from multiple locations:

```
Shell env (highest) > `.env` file > aliyun config.json > defaults (lowest)
```

### `.env` File Format

```ini
# Alibaba Cloud credentials
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

- **Security**: `.env` MUST be in `.gitignore` — never commit credentials
- **RAM note:** RAM is global; `cn-hangzhou` is the typical default even if
  resources are in other regions.

### Go `.env` Loading (optional)

```go
package main

import (
    "os"
    "github.com/joho/godotenv"
)

func init() {
    godotenv.Load(".env")
}

func main() {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    region := os.Getenv("ALIBABA_CLOUD_REGION_ID")
}
```

## Credential Verification

```bash
# Primary: aliyun CLI validation
aliyun ram ListUsers --MaxItems 5
aliyun sts GetCallerIdentity
```

If `aliyun` validation fails, attempt retries per retry logic. After 3 failures,
proceed to JIT Go SDK and verify:

```bash
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
    fmt.Println("Credentials OK (JIT Go SDK mode)")
}
EOF
go run /tmp/aliyun-sdk-workspace/verify.go
```

> **SECURITY WARNING:** Verification code ONLY checks for existence. NEVER log
> the actual secret value.

## Cross-Product Delegation

When a RAM operation is part of a multi-product workflow:

1. **RAM setup first:** Create users, roles, policies
2. **Attach resource policies:** Use the target product's skill to attach
   resource-level policies (e.g., OSS bucket policy, ECS resource group policy)
3. **Verify end-to-end:** Use the target product's skill to verify the RAM
   identity can access the resource

Example: ECS instance access via RAM role
1. Create RAM role with ECS service principal (this skill)
2. Attach `AliyunECSFullAccess` to role (this skill)
3. Create ECS instance and attach instance role (`alicloud-ecs-ops` skill)
4. Verify instance metadata can retrieve STS credentials (`alicloud-ecs-ops` skill)

## CloudMonitor (CMS) Integration

### RAM Policy for CMS Access

When configuring CloudMonitor (CMS) permissions via RAM, the following policies
are commonly used. Delegate to `alicloud-cms-ops` for actual monitoring operations.

#### Read-Only Policy for CMS

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cms:DescribeMetricList",
        "cms:DescribeMetricLast",
        "cms:DescribeMetricData",
        "cms:DescribeMetricTop",
        "cms:DescribeMetricMetaList",
        "cms:DescribeProjectMeta",
        "cms:DescribeMetricAlarmList",
        "cms:DescribeMonitorGroups",
        "cms:DescribeMonitorGroupInstances",
        "cms:DescribeContactGroupList",
        "cms:DescribeContactList"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Full Access Policy for CMS

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "cms:*",
      "Resource": "*"
    }
  ]
}
```

### Delegation Protocol

When a user needs monitoring permissions:

```
[RAM Permission Request]
    │
    ├── 1. Determine required CMS operations (read-only or full access)
    ├── 2. Create or attach CMS policy via this skill (alicloud-ram-ops)
    ├── 3. Verify CMS access via alicloud-cms-ops (DescribeMetricList)
    └── 4. If access denied → check policy attachment and return to step 2
```

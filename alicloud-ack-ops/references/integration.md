# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (`github.com/alibabacloud-go/cs-20151215/v4/client`)

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

### JIT Go SDK Workflow for ACK

1. **Initialize workspace:**
   ```bash
   mkdir -p /tmp/aliyun-sdk-workspace
   cd /tmp/aliyun-sdk-workspace
   go mod init sdk-script
   ```

2. **Get dependencies:**
   ```bash
   export GOPROXY="https://goproxy.cn,direct"
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/tea-utils/v2/service
   go get github.com/alibabacloud-go/cs-20151215/v4/client
   ```

3. **Generate script** (Agent dynamically creates operation-specific .go file)

4. **Execute:**
   ```bash
   go run ./main.go
   ```

### SDK Package Reference

| Product | Go SDK Package |
|---------|---------------|
| ACK (CS) | `github.com/alibabacloud-go/cs-20151215/v4/client` |

## Cross-Product Dependencies

| ACK Operation | Depends On | Delegate To |
|---------------|------------|-------------|
| CreateCluster | VPC, VSwitch | `alicloud-vpc-ops` |
| CreateCluster | Key Pair (optional) | `alicloud-ecs-ops` |
| Public API Server | SLB (auto-created) | `alicloud-slb-ops` (if manual management needed) |
| Persistent Storage | NAS / OSS | `alicloud-nas-ops`, `alicloud-oss-ops` |
| Log Collection | SLS (Logtail) | `alicloud-sls-ops` (when present) |
| Monitoring / Alerts | CloudMonitor (CMS) | `alicloud-cms-ops` |

## CloudMonitor (CMS) Integration

### Metric Query

ACK (Kubernetes) metrics are available via CloudMonitor under the `acs_k8s_dashboard` namespace.
Delegate to `alicloud-cms-ops` for metric queries and alarm management.

```bash
# Query cluster CPU usage
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"clusterId":"{{user.cluster_id}}"}]' \
  --Period 60

# Query cluster memory usage
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName MemoryUsage \
  --Dimensions '[{"clusterId":"{{user.cluster_id}}"}]' \
  --Period 60
```

### Alarm Rule Management

Create monitoring alarms for ACK clusters via CMS:

```bash
# Create cluster CPU usage alarm
aliyun cms PutMetricAlarm \
  --AlarmName "ack-{{user.cluster_id}}-cpu-high" \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"clusterId":"{{user.cluster_id}}"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 80 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["{{user.contact_group}}"]'
```

### Alarm-to-Diagnosis Delegation

When CMS alarms fire for ACK clusters, the following delegation protocol applies:

| Alarm Metric | Primary Diagnosis Skill | Secondary Diagnosis Skill |
|-------------|------------------------|--------------------------|
| CpuUsage | `alicloud-ack-ops` | `alicloud-ecs-ops` (node diagnosis) |
| MemoryUsage | `alicloud-ack-ops` | `alicloud-ecs-ops` (node diagnosis) |
| DiskUsage | `alicloud-ack-ops` | `alicloud-ecs-ops` (node diagnosis) |
| NetworkInRate / NetworkOutRate | `alicloud-ack-ops` | `alicloud-vpc-ops` |
| PodStatus | `alicloud-ack-ops` | — |

### Delegation Protocol

```
[CMS Alarm Fires (acs_k8s_dashboard)]
    │
    ├── 1. Identify metric from alarm rule
    ├── 2. Invoke alicloud-ack-ops to check cluster/node/pod status
    ├── 3. If node-level issue suspected → invoke alicloud-ecs-ops
    ├── 4. If network issue suspected → invoke alicloud-vpc-ops
    └── 5. Compile unified diagnosis report
```

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

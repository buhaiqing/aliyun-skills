# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (`github.com/alibabacloud-go/cs-20151215/v4/client`)

### Go Runtime Bootstrap

If Agent Runtime lacks Go, JIT download from official source:

```bash
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
    export GOPROXY="https://goproxy.cn,direct"
fi

go version
```

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

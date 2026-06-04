# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (`github.com/alibabacloud-go/cs-20151215/v4/client`)
— same package as ManagedKubernetes, since ASK is a `cluster_type` value
in the same CS product.

### Enhanced Self-Healing Framework (MANDATORY)

All installation flows MUST follow the **Enhanced Self-Healing Framework**
defined in
[`alicloud-skill-generator/references/enhanced-self-healing-framework.md`](../../alicloud-skill-generator/references/enhanced-self-healing-framework.md).

**Key Self-Healing Capabilities:**
- **Pre-flight Checks:** Network, disk, permissions, system compatibility
- **Intelligent Error Classification:** Network / permission / resource / configuration
- **Multi-Path Self-Healing:** Multiple recovery strategies per error type
- **Health Verification:** Post-install validation with health score ≥ 8/10
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

For detailed implementation, see the meta-skill framework doc Section 3.2.

### JIT Go SDK Workflow for ASK

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
| ACK / ASK (CS) | `github.com/alibabacloud-go/cs-20151215/v4/client` |

## Cross-Product Dependencies

| ASK Operation | Depends On | Delegate To |
|---------------|------------|-------------|
| CreateCluster | VPC, VSwitch | `alicloud-vpc-ops` |
| CreateCluster | NAT Gateway (for Pod egress) | `alicloud-nat-ops` |
| ECI Pods (compute) | ECI quota | [`alicloud-eci-ops`](../../alicloud-eci-ops/SKILL.md) |
| Container image pull | ACR or other registry | `alicloud-acr-ops` (when present) |
| Public API server | SLB (auto-created) | `alicloud-slb-ops` (when present) |
| Log collection | SLS / Logtail | `alicloud-sls-ops` (when present) |
| Monitoring / Alerts | CloudMonitor (CMS) | `alicloud-cms-ops` |
| Cluster authentication | RAM | `alicloud-ram-ops` |
| Cost reporting | Billing | `alicloud-billing-ops` |

## CloudMonitor (CMS) Integration

ASK metrics live in **two namespaces**:

| Namespace | What |
|-----------|------|
| `acs_k8s_dashboard` | Cluster / control plane (shared with ManagedKubernetes) |
| `acs_eci_dashboard` | ECI Pod metrics + region-level quota usage |

For detailed query examples, see [Monitoring](monitoring.md).
For full CMS workflow, delegate to `alicloud-cms-ops`.

### Alarm Rule Example (ECI Quota)

```bash
aliyun cms PutMetricAlarm \
  --AlarmName "ask-eci-vcpu-quota-{{user.cluster_id}}" \
  --Namespace acs_eci_dashboard \
  --MetricName eci.vcpu.quota.usage \
  --Dimensions '[{"regionId":"{{user.region}}"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 85 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["{{user.contact_group}}"]'
```

### Alarm-to-Diagnosis Delegation

When CMS alarms fire for ASK:

| Alarm Metric | Primary Diagnosis Skill | Secondary Diagnosis Skill |
|--------------|------------------------|---------------------------|
| ECI vCPU quota | `alicloud-ack-serverless-ops` | [`alicloud-eci-ops`](../../alicloud-eci-ops/SKILL.md) |
| ECI memory quota | `alicloud-ack-serverless-ops` | [`alicloud-eci-ops`](../../alicloud-eci-ops/SKILL.md) |
| ECI instance count quota | `alicloud-ack-serverless-ops` | [`alicloud-eci-ops`](../../alicloud-eci-ops/SKILL.md) |
| Cluster CPU/Memory | `alicloud-ack-serverless-ops` | — |
| Pod Status (Pending) | `alicloud-ack-serverless-ops` | `alicloud-eci-ops` (quota) |
| API Server Latency | `alicloud-ack-serverless-ops` | (Alibaba-managed) |

### Delegation Protocol

```
[CMS Alarm Fires]
    │
    ├── 1. Identify metric from alarm rule
    ├── 2. Invoke alicloud-ack-serverless-ops to check cluster state + ECI quota
    ├── 3. If ECI quota issue → invoke alicloud-eci-ops
    ├── 4. If VPC/network issue → invoke alicloud-vpc-ops / alicloud-nat-ops
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

> **Security:** `.env` MUST be in `.gitignore` — never commit credentials.
> When printing to console, mask:
> `export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"`

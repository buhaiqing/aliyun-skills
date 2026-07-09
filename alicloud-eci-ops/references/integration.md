# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK
(`github.com/alibabacloud-go/eci-20180808/client`)

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

### JIT Go SDK Workflow for ECI

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
   go get github.com/alibabacloud-go/eci-20180808/client
   ```

3. **Generate script** (Agent dynamically creates operation-specific .go file)

4. **Execute:**
   ```bash
   go run ./main.go
   ```

### SDK Package Reference

| Product | Go SDK Package |
|---------|---------------|
| ECI | `github.com/alibabacloud-go/eci-20180808/client` |

## Cross-Product Dependencies

| ECI Operation | Depends On | Delegate To |
|---------------|------------|-------------|
| CreateContainerGroup | VPC, VSwitch, SecurityGroup | `alicloud-vpc-ops` |
| CreateContainerGroup | ECI quota | `aliyun eci ListUsage` (in this skill) |
| ECI egress (internet) | NAT Gateway OR EIP | `alicloud-nat-ops` (or use `AutoCreateEip` flag) |
| Private image pull | ACR (or other registry) | `alicloud-acr-ops` (when present) |
| Container logs | SLS | `alicloud-sls-ops` (when present) |
| Monitoring / Alerts | CloudMonitor (CMS) | `alicloud-cms-ops` |
| ECI in ASK context (K8s) | ASK kubeconfig | [`alicloud-ask-ops`](../../alicloud-ask-ops/SKILL.md) |
| Cluster authentication | RAM | `alicloud-ram-ops` |
| Cost reporting | Billing | `alicloud-billing-ops` |
| VirtualNode to K8s | self-managed K8s cluster | `alicloud-cs-ops` (when present) |
| ImageCache | (self-contained) | (no delegation) |
| DataCache | (self-contained, may need NAS/OSS) | `alicloud-nas-ops` / `alicloud-oss-ops` (when present) |

## CloudMonitor (CMS) Integration

ECI metrics live in `acs_eci_dashboard` namespace (shared with ASK Pods,
since ASK Pods **are** ECI ContainerGroups).

| Metric | Description |
|--------|-------------|
| `eci.cpu.usage` | Per-ECI CPU |
| `eci.memory.usage` | Per-ECI memory |
| `eci.network.in.bytes` / `eci.network.out.bytes` | Network |
| `eci.status` | Status distribution |

> **⚠️ Verify exact metric names** before production alerting.

For detailed CMS workflows, delegate to `alicloud-cms-ops`.

### Alarm Rule Example

```bash
# ECI container CPU high
aliyun cms PutMetricAlarm \
  --AlarmName "eci-cpu-high-{{user.container_group_id}}" \
  --Namespace acs_eci_dashboard \
  --MetricName eci.cpu.usage \
  --Dimensions '[{"containerGroupId":"{{user.container_group_id}}"}]' \
  --Statistics Average \
  --ComparisonOperator ">=" \
  --Threshold 85 \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups '["{{user.contact_group}}"]'
```

### Quota Monitoring (Special Case — **CORRECTED**)

ECI quota is **NOT** a CMS metric — it's queried via the dedicated
`ListUsage` API. To alert on quota:

**Option A:** Periodic poller that publishes custom CMS metric
```bash
# Pseudocode — every 5 minutes
QUOTA=$(aliyun eci ListUsage --body '{"RegionId":"'$REGION'"}')
USED_RATIO=$(echo "$QUOTA" | jq '.Data[0].CpuUsed / .Data[0].CpuQuota')
# Publish to CMS as custom metric, or trigger alarm logic directly
```

**Option B:** Application-level check before any `CreateContainerGroup`
(see [SKILL.md pre-flight](../SKILL.md#pre-flight-checks)).

> **Historical note:** Earlier versions of this file mentioned
> `DescribeContainerGroupQuota` — that operation does **not exist** in the
> ECI CLI. Use `ListUsage`.

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

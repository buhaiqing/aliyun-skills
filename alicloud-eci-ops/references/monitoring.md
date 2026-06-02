# Monitoring ECI

## Overview

ECI monitoring has two layers:

| Layer | Source | What |
|-------|--------|------|
| **ECI instance metrics** | `acs_eci_dashboard` (CMS) | Per-ECI CPU, memory, network |
| **ECI region quota** | `aliyun eci ListUsage` (API) | Region-level vCPU/memory used vs total |
| **Container logs** | SLS (optional) | stdout/stderr from ECI containers |

## Metric Namespaces

| Namespace | Scope | Description |
|-----------|-------|-------------|
| `acs_eci_dashboard` | ECI / account | ECI Pod metrics + region-level quota |
| `acs_k8s_dashboard` | (shared with ASK) | For ECI used as ASK Pod |

## ECI Instance-Level Metrics (`acs_eci_dashboard`)

| Metric | Description | Unit | Dimensions |
|--------|-------------|------|------------|
| `eci.cpu.usage` | ECI vCPU usage | % | containerGroupId, containerName |
| `eci.memory.usage` | ECI memory usage | bytes | containerGroupId, containerName |
| `eci.network.in.bytes` | Network inbound | bytes/s | containerGroupId |
| `eci.network.out.bytes` | Network outbound | bytes/s | containerGroupId |
| `eci.status` | ECI status distribution | count | regionId, status |

> **⚠️ Verify exact metric names** via
> `aliyun cms DescribeMetricMetaList --Namespace acs_eci_dashboard`
> before production alerting.

## ECI Region-Level Quota (via API, **not** CMS)

ECI quota is queried via the **dedicated `ListUsage` API** (not via CMS
metrics, and **not** via the non-existent `DescribeContainerGroupQuota`):

```bash
aliyun eci ListUsage --body '{"RegionId":"cn-hangzhou"}'
```

Sample response (verify exact shape on first use):

```json
{
  "Data": [
    {
      "Name": "..."
    }
  ]
}
```

> **Note:** Exact response field names for quota need first-use
> verification. Look for fields like `CpuQuota` / `CpuUsed` /
> `MemoryQuota` / `MemoryUsed` / `InstanceCountQuota` / `InstanceCountUsed`
> in the response. Update this file after first production run.

| Likely field | Meaning |
|--------------|---------|
| `CpuQuota` / `CpuUsed` | Region vCPU quota vs current usage |
| `MemoryQuota` / `MemoryUsed` | Region memory quota (GB) vs current usage |
| `GpuQuota` / `GpuUsed` | GPU quota (if applicable) |
| `InstanceCountQuota` / `InstanceCountUsed` | ECI instance count quota |

## KPI Thresholds

| KPI | Warning | Critical | Action |
|-----|---------|----------|--------|
| ECI vCPU quota usage | > 70% | > 90% | **Raise ECI vCPU quota in ECI console** |
| ECI memory quota usage | > 70% | > 90% | **Raise ECI memory quota** |
| ECI instance count quota | > 70% | > 90% | **Raise ECI instance quota** |
| Container CPU usage | > 70% avg | > 85% | Increase `Cpu`; right-size |
| Container memory usage | > 75% avg | > 90% | Increase `Memory`; check leak |
| ECI Pending (Scheduling) | > 5 | > 20 | Check quota, VSwitch IP |
| ECI Failed | > 5 in 1h | > 20 in 1h | Investigate logs |
| ECI cost spike (daily) | > 150% baseline | > 200% | Check `RestartPolicy`, over-provisioning |

## Querying Metrics

```bash
# ECI vCPU usage (per instance)
aliyun cms DescribeMetricList \
  --Namespace acs_eci_dashboard \
  --MetricName eci.cpu.usage \
  --Dimensions '[{"containerGroupId":"{{user.container_group_id}}"}]' \
  --Period 60

# Quota (via API, not CMS)
aliyun eci ListUsage --body '{"RegionId":"{{user.region}}"}'
```

## ECI Status Distribution (Status Dashboard)

Use `DescribeContainerGroups` (not CMS) for current status counts:

```bash
aliyun eci DescribeContainerGroups --RegionId $REGION \
  --output cols=Status rows=ContainerGroups[].Status \
  | sort | uniq -c
```

## Alarm Rule Examples

### ECI Container High CPU (via CMS)

```bash
aliyun cms PutMetricAlarm \
  --AlarmName "eci-cpu-high" \
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

> **Note:** Quota metrics (CPU/memory/instance count) are typically
> queried via `ListUsage` API, not CMS. To alert on quota:
> - **Option A:** Periodic poller that publishes custom CMS metric
> - **Option B:** Application-level check before any `CreateContainerGroup`
>   (see SKILL.md pre-flight section)

## Container Log Collection (SLS)

ECI containers do not have built-in log persistence. To ship logs to SLS:

1. **Pre-provision** an SLS Project + Logstore
2. **Option A:** Add a log-shipper sidecar container in the ContainerGroup
3. **Option B:** Use `aliyun eci` with `SlsEnable` flag (verify support)

For log collection from ECI to SLS, delegate to `alicloud-sls-ops` (when present).

For one-off log inspection, use `ExecContainerCommand`:

```bash
aliyun eci ExecContainerCommand --RegionId $REGION \
  --ContainerGroupId $CG_ID --ContainerName app \
  --Command '["/bin/sh", "-c", "cat /var/log/app.log 2>/dev/null | tail -100"]' \
  --Sync true
```

## Alert Storm Handling (ECI)

1. **Quota exhaustion cascade** — many ECIs simultaneously `Scheduling` →
   raise ECI quota in ECI console immediately
2. **Image pull storm** — all new ECIs fail with `ImagePullError` → check
   ACR / network; consider mirror or fallback image
3. **Crash loop storm** — many ECIs restarting in a tight loop → likely
   app bug; check `RestartPolicy` to avoid infinite billing
4. **VSwitch IP exhaustion** — ECIs in one VSwitch `Scheduling` →
   expand VSwitch CIDR or rebalance

## Dashboard Panels (Essential)

| Panel | Source | What |
|-------|--------|------|
| ECI Quota Overview | `ListUsage` API | vCPU/memory used vs total bars |
| ECI Status Distribution | `DescribeContainerGroups` | Pending / Running / Failed counts |
| Top ECI by CPU | `acs_eci_dashboard` or describe | Top 10 by `eci.cpu.usage` |
| Top ECI by Memory | `acs_eci_dashboard` or describe | Top 10 by `eci.memory.usage` |
| ECI Cost Trend | (billing) | Daily ECI cost |
| Failed ECI Alert | (status filter) | ECIs in `Failed` for > 1h |
| Scheduling ECI | (status filter) | ECIs stuck in `Scheduling` |

## Monitoring Health Checklist

| Check | Frequency | Tool | Pass Criteria |
|-------|-----------|------|---------------|
| ECI quota < 80% | 5 min | `ListUsage` API | Headroom available |
| No `Scheduling` > 5 min | 1 min | `DescribeContainerGroups` | < 5 ECIs stuck |
| No `Failed` > 1h | 5 min | `DescribeContainerGroups` | Cleaned up |
| Restart loops not present | 5 min | `DescribeContainerGroup` `$.Containers[].RestartCount` | < 5 restarts per CG |
| Container log delivery | Daily | SLS | No gaps |

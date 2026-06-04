# NAS Monitoring

## CMS (CloudMonitor) Namespaces

NAS exposes metrics through Alibaba Cloud's CloudMonitor service. The primary
namespace is **`acs_nas_dashboard`** (some newer metrics use **`acs_nas`**).

| Namespace | Scope | Notes |
|-----------|-------|-------|
| `acs_nas_dashboard` | File-system-level metrics | Capacity, throughput, IOPS, client count |
| `acs_nas` | Mount-target-level metrics (newer) | Per-MT latency and connection count |

> **Verify with API:** run `aliyun cms DescribeMetricMetaList --Namespace acs_nas_dashboard`
> to enumerate current metrics. The list below is a representative subset.

## Key Metrics

### Capacity Metrics (acs_nas_dashboard)

| Metric | Unit | Description | Typical Alert |
|--------|------|-------------|---------------|
| `SizeUsed` | Bytes | Total used capacity (sum of all files) | > 80% of quota |
| `SizeTotal` | Bytes | Total provisioned capacity | — |
| `FileCount` | Count | Number of files (sample-based) | — |
| `IAUsed` | Bytes | Data in Infrequent Access tier | — |
| `ArchiveUsed` | Bytes | Data in Archive tier | — |

### Throughput Metrics (acs_nas_dashboard)

| Metric | Unit | Description | Typical Alert |
|--------|------|-------------|---------------|
| `ReadBytes` | Bytes/s | Aggregate read throughput | > 80% of provisioned bandwidth |
| `WriteBytes` | Bytes/s | Aggregate write throughput | > 80% of provisioned bandwidth |
| `ReadIOPS` | ops/s | Aggregate read IOPS | > 80% of provisioned IOPS |
| `WriteIOPS` | ops/s | Aggregate write IOPS | > 80% of provisioned IOPS |

### Latency Metrics

| Metric | Unit | Description | Typical Alert |
|--------|------|-------------|---------------|
| `ReadLatency` | μs | Average read operation latency | > 10 ms (extreme), > 50 ms (general-purpose) |
| `WriteLatency` | μs | Average write operation latency | > 10 ms (extreme), > 50 ms (general-purpose) |

### Mount Target Metrics (acs_nas)

| Metric | Unit | Description |
|--------|------|-------------|
| `ActiveConnection` | Count | Number of active NFS/SMB clients |
| `MountTargetStatus` | 0/1 | 1 = Active, 0 = Inactive |
| `ProtocolError` | Count/s | Protocol-level error rate |

## Sample Alarm Rules

### Rule 1: Capacity > 85% (file-system level)

```bash
aliyun cms PutResourceMetricRule \
  --RuleName "NAS-HighCapacity" \
  --Namespace "acs_nas_dashboard" \
  --MetricName "SizeUsedPercentage" \
  --Resources "[{\"id\":\"<file-system-id>\"}]" \
  --Statistics "Average" \
  --Threshold "85" \
  --ComparisonOperator "GreaterThanOrEqualThreshold" \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups "['ops-team']" \
  --Webhook "https://example.com/webhook"
```

> **Note:** `SizeUsedPercentage` may not be a directly exposed metric; use
> `SizeUsed / SizeTotal * 100` via CMS expression (when supported) or query
> `DescribeFileSystems` for `MeteredSize` and compare against quota.

### Rule 2: Mount Target Inactive (any state)

```bash
aliyun cms PutResourceMetricRule \
  --RuleName "NAS-MountTargetDown" \
  --Namespace "acs_nas" \
  --MetricName "MountTargetStatus" \
  --Resources "[{\"id\":\"<mount-target-id>\"}]" \
  --Statistics "Average" \
  --Threshold "1" \
  --ComparisonOperator "LessThanThreshold" \
  --Period 60 \
  --EvaluationCount 2 \
  --ContactGroups "['ops-team']"
```

### Rule 3: Read Latency Spike

```bash
aliyun cms PutResourceMetricRule \
  --RuleName "NAS-HighReadLatency" \
  --Namespace "acs_nas_dashboard" \
  --MetricName "ReadLatency" \
  --Resources "[{\"id\":\"<file-system-id>\"}]" \
  --Statistics "Average" \
  --Threshold "50000" \
  --ComparisonOperator "GreaterThanThreshold" \
  --Period 300 \
  --EvaluationCount 3 \
  --ContactGroups "['ops-team']"
```

(Threshold of 50000 μs = 50 ms; adjust per storage class.)

## Dashboard Composition

A typical NAS health dashboard should include:

1. **Capacity panel** — `SizeUsed` line; horizontal threshold at 80%.
2. **Throughput panel** — `ReadBytes` + `WriteBytes` stacked area.
3. **IOPS panel** — `ReadIOPS` + `WriteIOPS` stacked area.
4. **Latency panel** — `ReadLatency` + `WriteLatency` lines.
5. **Per-MT status grid** — `MountTargetStatus` for each mount target.
6. **Snapshot status** — count of `Progressing` snapshots (should normally be 0).

## Custom Query Examples

### Total Used Capacity Across All File Systems

```bash
# CLI: paginate through all FSs and sum MeteredSize
TOTAL=0
for ID in $(aliyun nas DescribeFileSystems --PageSize 100 | jq -r '.FileSystems.FileSystem[].FileSystemId'); do
  SIZE=$(aliyun nas DescribeFileSystems --FileSystemId "$ID" | jq -r '.FileSystems.FileSystem[0].MeteredSize')
  TOTAL=$((TOTAL + SIZE))
done
echo "Total used: $TOTAL bytes"
```

### Active Mount Targets

```bash
for FS in $(aliyun nas DescribeFileSystems --PageSize 100 | jq -r '.FileSystems.FileSystem[].FileSystemId'); do
  echo "FS: $FS"
  aliyun nas DescribeMountTargets --FileSystemId "$FS" \
    --output cols=MountTargetId,MountTargetDomain,Status \
           rows=MountTargets.MountTarget[].[MountTargetId,MountTargetDomain,Status]
done
```

## Proactive Inspection Script

```bash
#!/usr/bin/env bash
# nas_health_check.sh — query NAS health metrics for all FSs in a region
set -euo pipefail

REGION="${ALIBABA_CLOUD_REGION_ID:-cn-hangzhou}"

echo "=== NAS Health Check (region: $REGION) ==="

# 1. File system inventory
echo
echo "[1] File systems:"
aliyun nas DescribeFileSystems --PageSize 100 \
  --output cols=FileSystemId,FileSystemType,Status,StorageType,MeteredSize \
         rows=FileSystems.FileSystem[].[FileSystemId,FileSystemType,Status,StorageType,MeteredSize]

# 2. Mount target inventory
echo
echo "[2] Mount targets per file system:"
for FS in $(aliyun nas DescribeFileSystems --PageSize 100 | jq -r '.FileSystems.FileSystem[].FileSystemId'); do
  COUNT=$(aliyun nas DescribeMountTargets --FileSystemId "$FS" | jq '.MountTargets.MountTarget | length')
  ACTIVE=$(aliyun nas DescribeMountTargets --FileSystemId "$FS" | jq '[.MountTargets.MountTarget[] | select(.Status == "Active")] | length')
  echo "  $FS — total=$COUNT active=$ACTIVE"
done

# 3. Recycle bin status (only standard NAS)
echo
echo "[3] Recycle bin status (standard NAS only):"
for FS in $(aliyun nas DescribeFileSystems --FileSystemType standard --PageSize 100 | jq -r '.FileSystems.FileSystem[].FileSystemId'); do
  ATTR=$(aliyun nas GetRecycleBinAttribute --FileSystemId "$FS" 2>/dev/null || echo "n/a")
  echo "  $FS: $ATTR"
done

# 4. Snapshot in-progress
echo
echo "[4] Snapshots in progress:"
aliyun nas DescribeAutoSnapshotTasks --PageSize 100 2>/dev/null \
  --output cols=FileSystemId,Status,Progress \
         rows=AutoSnapshotTasks.AutoSnapshotTask[].[FileSystemId,Status,Progress] || echo "  (no in-progress tasks)"

# 5. Recent autonomous events
echo
echo "[5] Recent NAS autonomous events (last 24h):"
START=$(date -u -d '24 hours ago' +%FT%TZ 2>/dev/null || date -u -v-24H +%FT%TZ)
END=$(date -u +%FT%TZ)
aliyun nas DescribeSnapshots --CreateTimeStart "$START" --CreateTimeEnd "$END" --PageSize 10 \
  --output cols=SnapshotId,SourceFileSystemId,Status,CreateTime \
         rows=Snapshots.Snapshot[].[SnapshotId,SourceFileSystemId,Status,CreateTime] 2>/dev/null || true

echo
echo "=== Health check complete ==="
```

## Integration with Apsara Stack / AIOps

When integrating NAS health with a higher-level observability platform
(Grafana, Datadog, etc.), use:

- **CMS OpenAPI** for metric scraping:
  `cms.DescribeMetricList` with `Namespace=acs_nas_dashboard`
- **ActionTrail** for audit events:
  `actiontrail.LookupEvents` with `ServiceName=nas`
- **NAS-specific event types** (when subscribed):
  - `NAS:FileSystem:Created`
  - `NAS:FileSystem:Deleted`
  - `NAS:MountTarget:StatusChanged`
  - `NAS:Snapshot:Created`
  - `NAS:Snapshot:Failed`
  - `NAS:RecycleBin:FileRestored`

# Monitoring — DTS (Data Transmission Service)

## Key Metrics

DTS publishes metrics to CloudMonitor (CMS). These are available via `aliyun cms DescribeMetricList`.

| Metric | Namespace / MetricName | Unit | Description |
|--------|------------------------|------|-------------|
| Task Status | N/A (via DescribeDtsJobDetail) | status string | `Migrating`, `Synchronizing`, `Failed`, etc. |
| Sync Delay | `acs_dts` / `delay` | seconds (sync) / ms (migration) | Replication lag between source and target |
| RPS | `acs_dts` / `rps` | rows/second | Rows processed per second |
| IOPS | `acs_dts` / `iops` | operations/second | I/O operations per second |
| Network Throughput | `acs_dts` / `network_out` | bytes/second | Outbound network throughput |
| Memory Usage | `acs_dts` / `memory_usage` | bytes | Memory consumption on DTS server |
| CPU Usage | `acs_dts` / `cpu_usage` | % | CPU utilization on DTS server |
| DU Usage | `acs_dts` / `du_usage` | DUs | Current DTS Unit consumption |

## Monitoring Methods

### Method 1: Direct API Polling

```bash
# Check task status and delay
aliyun dts DescribeDtsJobDetail \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" | jq '{Status, Delay, DtsJobName}'
```

### Method 2: CMS Metrics

```bash
# Get DTS metrics from CloudMonitor
aliyun cms DescribeMetricList \
  --Namespace acs_dts \
  --MetricName delay \
  --Period 300 \
  --Dimensions "[{\"instanceId\":\"{{user.dts_instance_id}}\"}]"
```

### Method 3: Create Alert Rule

```bash
# Create a monitor rule for the DTS task
aliyun dts CreateJobMonitorRule \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --DtsJobId "{{user.dts_job_id}}" \
  --Type delay \
  --NotifyRule '{"contactGroups":["DBA"]}' \
  --DelayRule '{"delayThreshold":60}' \
  --State Y
```

## Recommended Alert Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Sync delay | > 10s | > 60s | Increase DU; check target performance |
| Task status = Failed | — | Immediate | Check DescribeDtsJobDetail for error |
| Task status = Suspended | > 5min | > 30min | Check if suspension was intentional |
| RPS drop > 50% | 5min | 15min | Check source/target performance |
| DU usage > 80% | 5min | 15min | Consider increasing DU limit |
| Memory usage > 80% | 5min | 15min | Decrease DU or split task |

## Dashboard Template

### CMS Dashboard Widgets for DTS

1. **Task Status Overview** — Grid showing status of all DTS jobs per region
2. **Sync Delay Timeline** — Line chart of `delay` metric over 24h
3. **Throughput History** — RPS line chart
4. **DU Utilization** — Bar chart of DU usage per instance
5. **Error Count** — Gauge of failed tasks in last hour

## Anomaly Patterns

| Pattern | Detection | Likely Cause | Action |
|---------|-----------|-------------|--------|
| Delay spikes at same time daily | Monitor delay at fixed intervals | Scheduled jobs on source or target | Schedule DTS maintenance window; adjust DU |
| Gradually increasing delay | Trend analysis | Source write rate > DTS throughput | Increase DU; optimize source writes |
| Intermittent disconnections | Status toggles between Migrating/Suspended | Network instability | Check DTS CIDR whitelist; VPC routing |
| RPS drops to 0 | RPS monitoring | Source/target connectivity issue | DescribeConnectionStatus |
| Task fails with same error pattern | Reproducible failures | Data type incompatibility | Update schema mapping |
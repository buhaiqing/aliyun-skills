# Monitoring — PTS

> Version: 1.0.0 | Last Updated: 2026-06-16

## Runtime Metrics (During Test)

```bash
aliyun pts get-pts-scene-running-data --scene-id "{{scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
aliyun pts get-pts-scene-running-status --scene-id "{{scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

| Field (typical) | Meaning |
|-----------------|---------|
| RPS / TPS | Current throughput |
| Avg RT | Average response time (ms) |
| Error rate | Failed requests / total |
| Active agents | Running load generators |

## Report Metrics (Post-Test)

```bash
aliyun pts get-pts-report-details --report-id "{{report_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

| Metric | Use |
|--------|-----|
| Success rate | SLA pass/fail |
| Avg / P90 / P99 RT | Latency regression |
| TPS peak | Capacity ceiling |
| Error distribution | Root cause hints |

List reports:

```bash
aliyun pts list-pts-reports --page-number 1 --page-size 10 --region "${ALIBABA_CLOUD_REGION_ID}"
aliyun pts get-pts-reports-by-scene-id --scene-id "{{scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

## Baseline Comparison

```bash
aliyun pts get-pts-scene-base-line --scene-id "{{scene_id}}" --region "${ALIBABA_CLOUD_REGION_ID}"
```

Workflow:

1. Run stable benchmark → `create-pts-scene-base-line-from-report`
2. On each release → re-run scene → compare report vs baseline
3. Regression threshold: e.g. P99 RT +20% or success rate −1%

## JMeter Report Metrics

```bash
aliyun pts get-jmeter-report-details --report-id "{{report_id}}"
aliyun pts get-jmeter-sample-metrics --report-id "{{report_id}}"
```

## CloudMonitor Integration

PTS may expose account-level usage metrics in CMS (namespace varies by edition). For **target** service metrics during load tests, query via `alicloud-cms-ops`:

```bash
# Example: ECS CPU during PTS run
aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard \
  --MetricName CPUUtilization \
  --Dimensions '[{"instanceId":"{{instance_id}}"}]' \
  --Period 60 --Length 300
```

## Suggested Alarms (Target Side)

| Alarm | Metric | Threshold | When |
|-------|--------|-----------|------|
| Target CPU high | `CPUUtilization` | >85% 5min | During PTS run |
| SLB 5xx spike | `Code5xx` | >1% | During PTS run |
| RDS connections | `ConnectionUsage` | >80% | DB under test |

## Dashboard Layout

```
Row 1: [PTS TPS] [PTS Avg RT] [PTS Error %]
Row 2: [Target CPU] [Target Memory] [SLB ActiveConnections]
Row 3: [Baseline vs Current P99] [Success Rate Delta]
```

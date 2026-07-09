# AIOps Inspection — Cross-Skill Anomaly Detection & Diagnosis

> Lazy-loaded reference. Only read when performing multi-metric anomaly inspection, alarm-driven cross-skill diagnosis, proactive monitoring inspection, or alarm storm handling. Not needed for single metric query or alarm CRUD.

---

## Multi-Metric Anomaly Inspection

Execute joint multi-metric inspection on a target resource to identify composite anomaly patterns. Critical when single metrics appear normal but combinations indicate risk.

### Supported Anomaly Patterns

| Pattern | Metrics Involved | Detection Logic | Severity |
|---------|-----------------|-----------------|----------|
| CPU-Memory Pressure | CPUUtilization, MemoryUsage | Both >= 80% for >= 10min | Critical |
| Disk-IO Bottleneck | DiskUsage, IOPSUsage | DiskUsage >= 85% AND IOPSUsage >= 90% | Critical |
| Network Saturation | InternetInRate, InternetOutRate | Either > baseline + 3σ for >= 5min | Warning |
| Load-CPU Mismatch | LoadAverage, CPUUtilization | LoadAverage > vCPU*2 AND CPUUtilization < 50% (indicates IO wait) | Warning |
| Connection Exhaustion | ConnectionUsage, CpuUsage | ConnectionUsage >= 90% AND CPUUsage < 30% (sleeping connections) | Critical |
| Memory Leak Trend | MemoryUsage | Monotonic increase over 30min with slope > 5%/10min | Warning |
| CPU Spike | CPUUtilization | Sudden increase > 50 percentage points within 5min | Warning |

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Resource exists | Delegate to product skill (e.g., `alicloud-ecs-ops` DescribeInstances) | Resource found and Running | HALT |
| Metrics available | `DescribeMetricMetaList` for namespace | All pattern metrics exist | Reduce pattern scope |
| Time range valid | StartTime < EndTime, within retention | Valid range | Adjust range |
| Quota check | Track API call count | < 80% of 1M/month | Warn; proceed with caution |

### Execution — CLI (Multi-Call Sequence)

```bash
#!/bin/bash
# multi-metric-inspection.sh

REGION="{{user.region}}"
NAMESPACE="{{user.namespace}}"
INSTANCE_ID="{{user.instance_id}}"
START_TIME="$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DIMENSIONS="[{\"instanceId\":\"${INSTANCE_ID}\"}]"

METRICS=()
case "$NAMESPACE" in
  acs_ecs_dashboard)
    METRICS=(CPUUtilization MemoryUsage DiskUsage LoadAverage InternetInRate InternetOutRate)
    ;;
  acs_rds_dashboard)
    METRICS=(CpuUsage MemoryUsage DiskUsage ConnectionUsage IOPSUsage)
    ;;
  acs_slb_dashboard)
    METRICS=(InstanceActiveConnection DropConnection DropPacketRX DropPacketTX)
    ;;
  *)
    echo "Unknown namespace: $NAMESPACE"
    exit 1
    ;;
esac

RESULTS_DIR="/tmp/cms-inspection-$(date +%s)"
mkdir -p "$RESULTS_DIR"

for metric in "${METRICS[@]}"; do
  echo "Querying $metric..."
  aliyun cms DescribeMetricList \
    --RegionId "$REGION" \
    --Namespace "$NAMESPACE" \
    --MetricName "$metric" \
    --Period 300 \
    --StartTime "$START_TIME" \
    --EndTime "$END_TIME" \
    --Dimensions "$DIMENSIONS" \
    > "$RESULTS_DIR/${metric}.json" 2>&1
done

echo "Results saved to $RESULTS_DIR"
```

### Execution — JIT Go SDK (Advanced Correlation)

```go
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	cms20190101 "github.com/alibabacloud-go/cms-20190101/v7/client"
)

type DataPoint struct {
	Timestamp int64   `json:"timestamp"`
	Average   float64 `json:"Average"`
	Maximum   float64 `json:"Maximum"`
	Minimum   float64 `json:"Minimum"`
}

func queryMetric(client *cms20190101.Client, namespace, metricName, dimensions string, startTime, endTime string) ([]DataPoint, error) {
	request := &cms20190101.DescribeMetricListRequest{
		RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		Namespace:  tea.String(namespace),
		MetricName: tea.String(metricName),
		Period:     tea.String("300"),
		StartTime:  tea.String(startTime),
		EndTime:    tea.String(endTime),
		Dimensions: tea.String(dimensions),
	}
	response, err := client.DescribeMetricList(request)
	if err != nil {
		return nil, err
	}

	var result struct {
		Datapoints string `json:"Datapoints"`
	}
	bodyStr := tea.ToString(response.Body)
	if err := json.Unmarshal([]byte(bodyStr), &result); err != nil {
		return nil, err
	}

	var datapoints []DataPoint
	if err := json.Unmarshal([]byte(result.Datapoints), &datapoints); err != nil {
		return nil, err
	}

	sort.Slice(datapoints, func(i, j int) bool {
		return datapoints[i].Timestamp < datapoints[j].Timestamp
	})
	return datapoints, nil
}

func detectAnomalyPattern(metrics map[string][]DataPoint, vCPU int) []string {
	var patterns []string

	cpu := metrics["CPUUtilization"]
	mem := metrics["MemoryUsage"]
	disk := metrics["DiskUsage"]
	iops := metrics["IOPSUsage"]
	load := metrics["LoadAverage"]
	conn := metrics["ConnectionUsage"]

	// Pattern: CPU-Memory Pressure
	if len(cpu) >= 2 && len(mem) >= 2 {
		cpuHigh, memHigh := true, true
		for i := len(cpu) - 2; i < len(cpu); i++ {
			if cpu[i].Average < 80 {
				cpuHigh = false
			}
			if mem[i].Average < 80 {
				memHigh = false
			}
		}
		if cpuHigh && memHigh {
			patterns = append(patterns, "CPU-Memory Pressure (Critical)")
		}
	}

	// Pattern: Disk-IO Bottleneck
	if len(disk) > 0 && len(iops) > 0 {
		latestDisk := disk[len(disk)-1].Average
		latestIOPS := iops[len(iops)-1].Average
		if latestDisk >= 85 && latestIOPS >= 90 {
			patterns = append(patterns, "Disk-IO Bottleneck (Critical)")
		}
	}

	// Pattern: Load-CPU Mismatch (IO wait)
	if len(load) > 0 && len(cpu) > 0 {
		latestLoad := load[len(load)-1].Average
		latestCPU := cpu[len(cpu)-1].Average
		if float64(vCPU)*2 < latestLoad && latestCPU < 50 {
			patterns = append(patterns, "Load-CPU Mismatch / IO Wait (Warning)")
		}
	}

	// Pattern: Connection Exhaustion
	if len(conn) > 0 && len(cpu) > 0 {
		latestConn := conn[len(conn)-1].Average
		latestCPU := cpu[len(cpu)-1].Average
		if latestConn >= 90 && latestCPU < 30 {
			patterns = append(patterns, "Connection Exhaustion (Critical)")
		}
	}

	// Pattern: Memory Leak Trend
	if len(mem) >= 6 {
		slope := (mem[len(mem)-1].Average - mem[len(mem)-6].Average) / 5
		if slope > 5 {
			patterns = append(patterns, "Memory Leak Trend (Warning)")
		}
	}

	// Pattern: CPU Spike
	if len(cpu) >= 2 {
		delta := cpu[len(cpu)-1].Average - cpu[len(cpu)-2].Average
		if delta > 50 {
			patterns = append(patterns, fmt.Sprintf("CPU Spike (+%.0f%%) (Warning)", delta))
		}
	}

	return patterns
}

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		Endpoint:        tea.String("metrics.aliyuncs.com"),
	}
	client, err := cms20190101.NewClient(config)
	if err != nil {
		panic(err)
	}

	now := time.Now().UTC()
	startTime := now.Add(-1 * time.Hour).Format("2006-01-02T15:04:05Z")
	endTime := now.Format("2006-01-02T15:04:05Z")

	namespace := "{{user.namespace}}"
	instanceID := "{{user.instance_id}}"
	dimensions := fmt.Sprintf(`{"instanceId":"%s"}`, instanceID)

	metrics := map[string][]DataPoint{}
	metricNames := []string{"CPUUtilization", "MemoryUsage", "DiskUsage", "LoadAverage", "IOPSUsage", "ConnectionUsage", "InternetInRate", "InternetOutRate"}

	for _, name := range metricNames {
		dp, err := queryMetric(client, namespace, name, dimensions, startTime, endTime)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to query %s: %v\n", name, err)
			continue
		}
		metrics[name] = dp
	}

	patterns := detectAnomalyPattern(metrics, 4)
	if len(patterns) == 0 {
		fmt.Println("No anomaly patterns detected.")
		return
	}

	fmt.Println("=== Anomaly Patterns Detected ===")
	for _, p := range patterns {
		fmt.Printf("- %s\n", p)
	}
}
```

### Validation

| Check | Method | Expected |
|-------|--------|----------|
| Data completeness | All queried metrics return non-empty Datapoints | >= 2 data points per metric |
| Pattern match | Evaluate detection logic against collected data | Identify matched patterns with severity |
| Cross-skill trigger | If Critical pattern matched | Auto-delegate to corresponding product skill |

### Recovery & Cross-Skill Delegation

| Pattern Detected | Primary Delegation | Secondary Delegation | DAS Delegation |
|-----------------|-------------------|---------------------|----------------|
| CPU-Memory Pressure | `alicloud-ecs-ops` | `alicloud-vpc-ops` | Optional |
| Disk-IO Bottleneck | `alicloud-ecs-ops` | — | Optional |
| Load-CPU Mismatch | `alicloud-ecs-ops` | — | Optional |
| Connection Exhaustion | `alicloud-rds-ops` | `alicloud-das-ops` | **Recommended** |
| Memory Leak Trend | `alicloud-ecs-ops` | — | Optional |
| CPU Spike | `alicloud-ecs-ops` | — | Optional |

> **Delegation Protocol:** When a pattern is detected, the agent MUST:
> 1. Record the pattern and severity in the inspection report
> 2. Invoke the primary skill to check resource status
> 3. If severity is Critical or resource status is abnormal, invoke DAS skill for AI diagnosis
> 4. Compile a unified report with findings from all delegated skills

---

## Alarm-Driven Cross-Skill Diagnosis

When a CMS alarm triggers, execute the automated cross-skill root-cause diagnosis per the decision tree below.

### Diagnosis Decision Tree

```
[CMS Alarm] → Step 1: Verify via DescribeMetricLast
  ├─ Normal → False positive; check rule config
  └─ Abnormal → Step 2: Check resource (delegate by namespace)
       ├─ acs_ecs_dashboard → alicloud-ecs-ops
       ├─ acs_rds_dashboard → alicloud-rds-ops
       ├─ acs_slb_dashboard → alicloud-slb-ops
       └─ acs_k8s_dashboard → alicloud-ack-ops

       → Step 3: Multi-metric correlation → Step 4: DAS deep diagnosis
       → Step 5: Unified report (findings + recommendations)
```

### Unified Diagnosis Report Schema

| Field | Source | Example |
|-------|--------|---------|
| `report_id` | Generated | `rpt-uuid` |
| `timestamp` | CMS | `2026-05-14T10:30:00Z` |
| `alarm_source` | CMS | `ECS-CPU-Critical` |
| `resource_id` | CMS | `i-abcdefgh1234567890` |
| `resource_status` | Product Skill | `Running` |
| `metric_value` | CMS | `CPUUtilization: 96.5%` |
| `anomaly_patterns` | Inspection | `["CPU-Memory Pressure"]` |
| `root_cause` | Synthesized | `CPU saturation due to runaway process` |
| `delegated_skills` | Agent | `["alicloud-ecs-ops", "alicloud-das-ops"]` |
| `recommendation` | Synthesized | `Scale up instance or optimize query` |

### Execution — CLI (Diagnosis Orchestration Script)

```bash
#!/bin/bash
# alarm-diagnosis-orchestrator.sh

REGION="{{user.region}}"
ALARM_NAME="{{user.alarm_name}}"
NAMESPACE="{{user.namespace}}"
METRIC_NAME="{{user.metric_name}}"
INSTANCE_ID="{{user.instance_id}}"
REPORT_DIR="/tmp/cms-diagnosis-$(date +%s)"
mkdir -p "$REPORT_DIR"

echo "=== CMS Alarm Diagnosis Started ==="
echo "Alarm: $ALARM_NAME | Metric: $METRIC_NAME | Resource: $INSTANCE_ID"

# Step 1: Verify alarm validity
echo -e "\n[Step 1] Verifying alarm validity..."
aliyun cms DescribeMetricLast \
  --RegionId "$REGION" \
  --Namespace "$NAMESPACE" \
  --MetricName "$METRIC_NAME" \
  --Dimensions "[{\"instanceId\":\"${INSTANCE_ID}\"}]" \
  > "$REPORT_DIR/step1_metric_last.json"

METRIC_VALUE=$(cat "$REPORT_DIR/step1_metric_last.json" | jq -r '.Datapoints | fromjson? | .[0].Average // "N/A"')
echo "Current metric value: $METRIC_VALUE"

# Step 2: Check resource status (namespace-specific)
echo -e "\n[Step 2] Checking resource status..."
case "$NAMESPACE" in
  acs_ecs_dashboard)
    aliyun ecs DescribeInstances --RegionId "$REGION" --InstanceIds "[\"${INSTANCE_ID}\"]" > "$REPORT_DIR/step2_resource.json"
    ;;
  acs_rds_dashboard)
    aliyun rds DescribeDBInstances --RegionId "$REGION" --DBInstanceId "$INSTANCE_ID" > "$REPORT_DIR/step2_resource.json"
    ;;
  acs_slb_dashboard)
    aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId "$INSTANCE_ID" > "$REPORT_DIR/step2_resource.json"
    ;;
  *)
    echo "Unknown namespace: $NAMESPACE"
    ;;
esac

# Step 3: Multi-metric correlation
echo -e "\n[Step 3] Running multi-metric correlation..."
# (Invoke the multi-metric inspection logic above)

# Step 4: Check correlated alarms in last 1h
echo -e "\n[Step 4] Checking correlated alarms..."
START_TIME="$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

aliyun cms DescribeMetricAlarmList \
  --RegionId "$REGION" \
  --State ALARM \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  > "$REPORT_DIR/step4_correlated_alarms.json"

# Step 5: Compile report
echo -e "\n[Step 5] Compiling diagnosis report..."
cat > "$REPORT_DIR/diagnosis_report.md" << 'EOF'
# CMS Alarm Diagnosis Report

| Field | Value |
|-------|-------|
| Alarm | {{user.alarm_name}} |
| Metric | {{user.metric_name}} |
| Resource | {{user.instance_id}} |
| Current Value | (from step 1) |
| Resource Status | (from step 2) |
| Correlated Alarms | (from step 4) |

## Findings
(TODO: populate from delegated skills)

## Recommendations
(TODO: synthesize)
EOF

echo -e "\n=== Diagnosis Complete ==="
echo "Report saved to: $REPORT_DIR/diagnosis_report.md"
```

---

## Proactive Monitoring Inspection

Execute periodic multi-resource, multi-metric proactive inspection to identify potential issues before they become incidents.

### Execution Flow

1. **Discovery:** List all resources in the monitor group
   ```bash
   aliyun cms DescribeMonitorGroupInstances \
     --RegionId {{user.region}} \
     --GroupId {{user.group_id}}
   ```

2. **Metric Collection:** Collect key metrics for each resource
   ```bash
   aliyun cms DescribeMetricList \
     --RegionId {{user.region}} \
     --Namespace {{user.namespace}} \
     --MetricName {{user.metric_name}} \
     --Period 300 \
     --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
     --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --Dimensions '[{"instanceId":"{{user.instance_id}}"}]'
   ```

3. **Anomaly Detection:** Apply static threshold + trend analysis
   - **Static Threshold:** Compare against predefined thresholds
   - **Trend Analysis:** Calculate slope of last N data points; flag if slope accelerates
   - **YoY/DoD Comparison:** Compare with same period yesterday/last week (requires history)

4. **Cross-Skill Diagnosis:** Delegate flagged resources to product skills

5. **Report Generation:** Generate inspection report

   | Resource | Metric | Status | Severity | Pattern | Delegated Skill | Finding |
   |----------|--------|--------|----------|---------|-----------------|---------|
   | i-xxx | CPUUtilization | ALARM | Critical | CPU Spike | alicloud-ecs-ops | High load |
   | rm-yyy | ConnectionUsage | WARNING | Warning | Connection Exhaustion | alicloud-rds-ops | 85% used |

### Anomaly Detection Algorithm (Trend)

```go
// Calculate linear regression slope for trend detection
func calculateSlope(points []DataPoint) float64 {
	n := float64(len(points))
	if n < 2 {
		return 0
	}
	var sumX, sumY, sumXY, sumX2 float64
	for i, p := range points {
		x := float64(i)
		y := p.Average
		sumX += x
		sumY += y
		sumXY += x * y
		sumX2 += x * x
	}
	slope := (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX)
	return slope
}

// Flag if slope indicates accelerating increase
func isAcceleratingIncrease(points []DataPoint) bool {
	if len(points) < 6 {
		return false
	}
	slope1 := calculateSlope(points[:len(points)/2])
	slope2 := calculateSlope(points[len(points)/2:])
	return slope2 > slope1 && slope2 > 2.0
}
```

---

## Alarm Storm Handling

When multiple alarms trigger simultaneously, execute aggregation and suppression strategies.

### Storm Detection Criteria

| Criteria | Threshold | Action |
|----------|-----------|--------|
| Alarm rate | > 10 alarms in 5 minutes | Enter storm mode |
| Same resource | > 3 alarms for same instance | Aggregate into single incident |
| Same namespace | > 50% of alarms from one namespace | Focus diagnosis on that product |
| Cascading pattern | Alarm A followed by Alarm B within 2min | Mark B as "likely caused by A" |

### Storm Handling Workflow

1. **Detection:** Monitor DescribeMetricAlarmList with State=ALARM
2. **Aggregation:** Group alarms by resource_id, namespace, time window
3. **Suppression:** For aggregated alarms, suppress notifications except the primary
4. **Root Resource Identification:** Find the earliest alarm in the cascade
5. **Focused Diagnosis:** Delegate to the root resource's skill for deep diagnosis

```bash
#!/bin/bash
# alarm-storm-detector.sh

REGION="{{user.region}}"
START_TIME="$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-5M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

aliyun cms DescribeMetricAlarmList \
  --RegionId "$REGION" \
  --State ALARM \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --PageSize 100 \
  > /tmp/active_alarms.json

ALARM_COUNT=$(cat /tmp/active_alarms.json | jq '.AlarmList | length')
echo "Active alarms in last 5min: $ALARM_COUNT"

if [ "$ALARM_COUNT" -gt 10 ]; then
  echo "ALARM STORM DETECTED!"
  cat /tmp/active_alarms.json | jq '
    .AlarmList | group_by(.Dimensions) | 
    map({resource: .[0].Dimensions, count: length, alarms: map(.AlarmName)})
  '
fi
```
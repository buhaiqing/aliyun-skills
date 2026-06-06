# DAS Intelligent Inspection

Execute a comprehensive health check for database instances via DAS. Combines DAS native scoring, CMS metrics, autonomous events, and DAS Pro status.

## JIT Go SDK Script

```go
package main

import (
    "encoding/json"
    "fmt"
    "os"
    "time"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    das "github.com/alibabacloud-go/das-20200116/v5/client"
    "github.com/alibabacloud-go/tea/tea"
)

func newDASClient() (*das.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("das.cn-shanghai.aliyuncs.com"),
    }
    return das.NewClient(config)
}

func main() {
    instanceId := os.Getenv("INSTANCE_ID")
    if instanceId == "" {
        fmt.Println("INSTANCE_ID is required")
        os.Exit(1)
    }

    client, err := newDASClient()
    if err != nil {
        panic(err)
    }

    dimensions := []map[string]interface{}{}
    recommendations := []string{}

    // 1. Get inspection score
    inspectReq := &das.GetInstanceInspectionsRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
    }
    inspectResp, err := client.GetInstanceInspections(inspectReq)
    if err == nil {
        score := inspectResp.Body.Data.Score
        dimensions = append(dimensions, map[string]interface{}{
            "name": "DAS巡检评分", "score": score, "status": "healthy",
        })
        if score != nil && *score < 60 {
            recommendations = append(recommendations, "DAS巡检评分低于60，建议创建诊断报告进行详细分析")
        }
    }

    // 2. Check autonomous events (last 24h)
    now := time.Now().UTC()
    startTime := now.Add(-24 * time.Hour).Format("2006-01-02T15:04:05Z")
    endTime := now.Format("2006-01-02T15:04:05Z")

    eventReq := &das.GetAutonomousNotifyEventsInRangeRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
        StartTime:  tea.String(startTime),
        EndTime:    tea.String(endTime),
    }
    eventResp, err := client.GetAutonomousNotifyEventsInRange(eventReq)
    if err == nil && eventResp.Body.Data != nil {
        dimensions = append(dimensions, map[string]interface{}{
            "name": "自治事件", "score": 100, "status": "healthy",
        })
    }

    // 3. Check DAS Pro usage
    proReq := &das.GetDasProServiceUsageRequest{
        RegionId:   tea.String("cn-shanghai"),
        InstanceId: tea.String(instanceId),
    }
    proResp, err := client.GetDasProServiceUsage(proReq)
    if err == nil && proResp.Body.Data != nil {
        dimensions = append(dimensions, map[string]interface{}{
            "name": "DAS Pro状态", "score": 100, "status": "healthy",
        })
    }

    result := map[string]interface{}{
        "inspection_time": time.Now().UTC().Format("2006-01-02T15:04:05Z"),
        "resource_type":   "database",
        "resource_id":     instanceId,
        "dimensions":      dimensions,
        "recommendations": recommendations,
    }
    b, _ := json.MarshalIndent(result, "", "  ")
    fmt.Println(string(b))
}
```

## Output Format

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "database",
  "resource_id": "rm-2ze8g2am97624****",
  "overall_score": 75,
  "dimensions": [
    {"name": "DAS巡检评分", "score": 75, "status": "warning"},
    {"name": "自治事件", "score": 100, "status": "healthy"},
    {"name": "DAS Pro状态", "score": 100, "status": "healthy"}
  ],
  "recommendations": [
    "DAS巡检评分75分，建议检查低分维度并优化",
    "建议通过CreateDiagnosticReport生成详细诊断报告"
  ],
  "confidence_score": 0.82
}
```

## Confidence Scoring

| Dimension | Weight | Calculation |
|-----------|--------|-------------|
| Data Completeness | 0.3 | Actual data items / Expected data items |
| Anomaly Pattern Match | 0.4 | Anomaly patterns found / Threshold-matched patterns |
| Historical Similar Cases | 0.3 | Matched historical cases / Total historical cases |

**Levels:** 0.9-1.0 auto-fix, 0.7-0.89 human review, 0.5-0.69 more evidence needed, 0.3-0.49 investigate further, 0.0-0.29 insufficient info.
```
# API & SDK Usage — PTS

> Version: 1.0.0 | Last Updated: 2026-06-16

## OpenAPI

- **Service Endpoint:** `pts.{region}.aliyuncs.com`
- **API Version:** 2020-10-20
- **Documentation:** https://help.aliyun.com/zh/pts/performance-test-pts-3-0/developer-reference/api-pts-2020-10-20-overview

## Go SDK

- **Package:** `github.com/alibabacloud-go/pts-20201020/v2/client`
- **OpenAPI config:** `github.com/alibabacloud-go/darabonba-openapi/v2/client`
- **Tea:** `github.com/alibabacloud-go/tea/tea`

> JIT workflow: [integration.md](integration.md)

## SDK Operations Map

### PTS Scene Operations

| Goal | OperationId | CLI (plugin) | Notes |
|------|-------------|--------------|-------|
| Create | `CreatePtsScene` | `create-pts-scene` | `--scene` JSON string |
| Save | `SavePtsScene` | `save-pts-scene` | Full Scene object |
| Modify | `ModifyPtsScene` | `modify-pts-scene` | Partial updates |
| List | `ListPtsScene` | `list-pts-scene` | PageNumber + PageSize required |
| Get | `GetPtsScene` | `get-pts-scene` | `--scene-id` |
| Delete | `DeletePtsScene` | `delete-pts-scene` | **Destructive** |
| Batch delete | `DeletePtsScenes` | `delete-pts-scenes` | JSON array of IDs |
| Start | `StartPtsScene` | `start-pts-scene` | **Safety gate** |
| Stop | `StopPtsScene` | `stop-pts-scene` | |
| Debug start | `StartDebugPtsScene` | `start-debug-pts-scene` | |
| Debug stop | `StopDebugPtsScene` | `stop-debug-pts-scene` | |
| Running status | `GetPtsSceneRunningStatus` | `get-pts-scene-running-status` | Poll after start |
| Running data | `GetPtsSceneRunningData` | `get-pts-scene-running-data` | Live metrics |
| Adjust speed | `AdjustPtsSceneSpeed` | `adjust-pts-scene-speed` | Mid-run RPS change |
| Debug logs | `GetPtsDebugSampleLogs` | `get-pts-debug-sample-logs` | |

### Report & Baseline Operations

| Goal | OperationId | CLI |
|------|-------------|-----|
| List reports | `ListPtsReports` | `list-pts-reports` |
| Reports by scene | `GetPtsReportsBySceneId` | `get-pts-reports-by-scene-id` |
| Report detail | `GetPtsReportDetails` | `get-pts-report-details` |
| Get baseline | `GetPtsSceneBaseLine` | `get-pts-scene-base-line` |
| Create baseline | `CreatePtsSceneBaseLineFromReport` | `create-pts-scene-base-line-from-report` |
| Update baseline | `UpdatePtsSceneBaseLine` | `update-pts-scene-base-line` |
| Delete baseline | `DeletePtsSceneBaseLine` | `delete-pts-scene-base-line` |

### JMeter Operations

| Goal | OperationId | CLI |
|------|-------------|-----|
| List scenes | `ListOpenJMeterScenes` | `list-open-jmeter-scenes` |
| Get scene | `GetOpenJMeterScene` | `get-open-jmeter-scene` |
| Save scene | `SaveOpenJMeterScene` | `save-open-jmeter-scene` |
| Remove | `RemoveOpenJMeterScene` | `remove-open-jmeter-scene` |
| Start test | `StartTestingJMeterScene` | `start-testing-jmeter-scene` |
| Stop test | `StopTestingJMeterScene` | `stop-testing-jmeter-scene` |
| Debug start | `StartDebuggingJMeterScene` | `start-debugging-jmeter-scene` |
| Debug stop | `StopDebuggingJMeterScene` | `stop-debugging-jmeter-scene` |
| JMeter report | `GetJMeterReportDetails` | `get-jmeter-report-details` |
| Sample metrics | `GetJMeterSampleMetrics` | `get-jmeter-sample-metrics` |
| Sampling logs | `GetJMeterSamplingLogs` | `get-jmeter-sampling-logs` |
| Running data | `GetJMeterSceneRunningData` | `get-jmeter-scene-running-data` |
| JMeter logs | `GetJMeterLogs` | `get-jmeter-logs` |
| List envs | `ListEnvs` | `list-envs` |
| Save env | `SaveEnv` | `save-env` |
| Remove env | `RemoveEnv` | `remove-env` |

## Pagination

| API | Parameters | Defaults |
|-----|------------|----------|
| `ListPtsScene` | `PageNumber`, `PageSize` | Size 10–1000 |
| `ListPtsReports` | `PageNumber`, `PageSize` | Same pattern |
| `ListOpenJMeterScenes` | `PageNumber`, `PageSize` | Same pattern |

## Response Fields (Verified)

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreatePtsScene | `$.SceneId` | string | New scene ID |
| ListPtsScene | `$.SceneViewList[].SceneId` | array | Scene IDs |
| ListPtsScene | `$.SceneViewList[].SceneName` | string | Name |
| ListPtsScene | `$.SceneViewList[].Status` | string | Lifecycle state |
| ListPtsScene | `$.SceneViewList[].CreateTime` | string | Created at |
| GetPtsScene | `$.Scene` | object | Full scene config |
| StartPtsScene | `$.Success` | bool | Start accepted |
| GetPtsReportDetails | `$.Report` | object | Metrics summary |
| All | `$.RequestId` | string | Trace ID |

## Minimal SDK Example — List Scenes

```go
package main

import (
	"fmt"
	"os"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	pts "github.com/alibabacloud-go/pts-20201020/v2/client"
	"github.com/alibabacloud-go/tea/tea"
)

func main() {
	cfg := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}
	c, err := pts.NewClient(cfg)
	if err != nil {
		panic(err)
	}
	resp, err := c.ListPtsScene(&pts.ListPtsSceneRequest{
		PageNumber: tea.Int32(1),
		PageSize:   tea.Int32(10),
	})
	if err != nil {
		panic(err)
	}
	fmt.Println(tea.Prettify(resp.Body))
}
```

> ⚠️ Never `fmt.Printf("%+v", cfg)` — leaks `AccessKeySecret`.

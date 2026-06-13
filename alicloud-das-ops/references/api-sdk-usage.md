# API & SDK — Alibaba Cloud DAS

## OpenAPI

- **Service**: DAS
- **API Version**: 2020-01-16
- **Base Endpoint**: `das.aliyuncs.com`
- **Official Docs**: https://www.alibabacloud.com/help/en/das

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| 获取实例信息 | `GetInstance` | `GetInstance()` | `aliyun das GetInstance` |
| 获取慢SQL列表 | `GetAsyncErrorRequestList` | `GetAsyncErrorRequestList()` | `aliyun das GetAsyncErrorRequestList` |
| 创建告警规则 | `CreateAlarm` | `CreateAlarm()` | `aliyun das CreateAlarm` |
| 获取告警列表 | `GetAlarmList` | `GetAlarmList()` | `aliyun das GetAlarmList` |

## SDK Package

```bash
go get github.com/alibabacloud-go/das-20200116/client
```

## Request / Response Notes

### Common Patterns
- **Pagination**: `PageNumber`, `PageSize` parameters
- **Filters**: Use `Describe*` APIs with filter parameters
- **Async Operations**: Long-running operations return `RequestId` for polling

### Response Codes
- **Success**: HTTP 200, JSON with `RequestId`
- **Client Error**: HTTP 4xx, check error message
- **Server Error**: HTTP 5xx, retry with backoff

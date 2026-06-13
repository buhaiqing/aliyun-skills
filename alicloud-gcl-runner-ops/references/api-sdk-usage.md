# API & SDK — Alibaba Cloud GCL Runner

## OpenAPI

- **Service**: GCL
- **API Version**: N/A
- **Base Endpoint**: `gcl.aliyuncs.com`
- **Official Docs**: https://www.alibabacloud.com/help/en/gcl

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| 执行 GCL 循环 | `Run` | `Run()` | `python gcl_runner.py` |
| 解析评分标准 | `ParseRubric` | `ParseRubric()` | `内置方法` |
| 对抗性评审 | `Critique` | `Critique()` | `内置方法` |

## SDK Package

```bash
go get github.com/alibabacloud-go/gcl-N/A/client
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

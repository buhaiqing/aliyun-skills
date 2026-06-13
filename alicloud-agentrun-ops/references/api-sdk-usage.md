# API & SDK — Alibaba Cloud AgentRun

## OpenAPI

- **Service**: ECS
- **API Version**: 2014-05-26
- **Base Endpoint**: `ecs.aliyuncs.com`
- **Official Docs**: https://www.alibabacloud.com/help/en/ecs

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| 执行命令 | `RunCommand` | `RunCommand()` | `aliyun ecs RunCommand` |
| 查询执行记录 | `DescribeInvocations` | `DescribeInvocations()` | `aliyun ecs DescribeInvocations` |
| 查询执行结果 | `DescribeInvocationResults` | `DescribeInvocationResults()` | `aliyun ecs DescribeInvocationResults` |
| 发送文件 | `SendFile` | `SendFile()` | `aliyun ecs SendFile` |

## SDK Package

```bash
go get github.com/alibabacloud-go/ecs-20140526/client
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

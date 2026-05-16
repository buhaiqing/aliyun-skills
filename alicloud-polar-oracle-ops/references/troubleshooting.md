# Troubleshooting Guide — PolarDB Oracle-compatible (IO)

> Version: 1.0.0 | Last Updated: 2026-05-16

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| InvalidDBClusterId.NotFound | Cluster not found | Verify ID; HALT |
| InvalidParameter | Parameter validation failed | Check OpenAPI spec |
| DBClusterQuotaExceeded | Quota exceeded | HALT; raise quota |
| InsufficientBalance | No funds | HALT; recharge |
| OperationDenied | Operation not permitted | Check cluster status |
| AccountNameInvalid | Invalid account name | Fix format |
| DBNameAlreadyExists | Database exists | Reuse or rename |
| Throttling | Rate limited | Exponential backoff, max 3 retries |
| InternalError | Server error | Retry 3x; HALT with RequestId |
| Forbidden.RAM | Insufficient IAM | User adds RAM policy |

## Diagnostic Order

1. Verify cluster exists: `aliyun polardb-io DescribeDBClusterAttribute`
2. Check cluster status: must be `Running` for most operations
3. Verify region consistency
4. For coverage: `aliyun help polardb-io`

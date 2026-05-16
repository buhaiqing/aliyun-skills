# Troubleshooting Guide — PolarDB PostgreSQL

> Version: 1.0.0 | Last Updated: 2026-05-16

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| InvalidDBClusterId.NotFound | Cluster not found | Verify ID |
| InvalidParameter | Parameter validation failed | Check against OpenAPI |
| DBClusterQuotaExceeded | Cluster quota exceeded | HALT; raise quota |
| InsufficientBalance | Insufficient balance | HALT; recharge |
| Throttling | Rate limited | Exponential backoff, max 3 retries |
| InternalError | Server error | Retry 3x; HALT with RequestId |
| Forbidden.RAM | Insufficient RAM | User adds RAM policy |

## Diagnostic Order

1. Verify cluster exists: `aliyun polardb-pg DescribeDBClusterAttribute`
2. Check cluster status: `DBClusterStatus` must be `Running`
3. Verify region consistency
4. For CLI coverage: `aliyun help polardb-pg`

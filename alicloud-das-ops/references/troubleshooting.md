# DAS Troubleshooting Reference

## Common Errors and Resolution

### InvalidDBInstanceId.NotFound
- **Cause:** Instance ID does not exist, or the instance is not registered in DAS.
- **Resolution:**
  1. Verify the instance ID using the engine-specific skill (e.g., `alicloud-rds-ops`).
  2. If the instance exists but is not in DAS, run `AddHDMInstance` to register it.
  3. Ensure the instance is in `Running` state before registration.

### OperationDenied.InstanceStatus
- **Cause:** The database instance is in a state that does not allow the operation (e.g., creating, restarting, deleting).
- **Resolution:** Wait for the instance to reach a stable state (`Running`), then retry.

### Throttling
- **Cause:** API rate limit exceeded.
- **Resolution:** Implement exponential backoff (1s, 2s, 4s, 8s). If persistent, reduce call frequency or contact Alibaba Cloud support to raise quotas.

### InvalidParameter
- **Cause:** Missing required parameter, malformed value, or parameter out of range.
- **Resolution:** Cross-check request parameters against the OpenAPI spec for the specific operation. Verify `RegionId` is set to `cn-shanghai`.

### InsufficientBalance
- **Cause:** Account balance is insufficient for DAS Pro (enterprise edition) features.
- **Resolution:** Delegate to `alicloud-billing-ops` for recharge or cost optimization. Alternatively, verify if the feature is available in the free tier.

### Endpoint Resolution Failure
- **Cause:** SDK cannot resolve the DAS endpoint.
- **Resolution:** Explicitly set the endpoint to `das.cn-shanghai.aliyuncs.com` (public) or `das.vpc-proxy.aliyuncs.com` (VPC) in the SDK config. Do not rely on default endpoint resolution for DAS.

## SDK / Build Issues

### `go get` fails for das-20200116
- Ensure Go version is >= 1.21.
- Check network access to `proxy.golang.org` or configure `GOPROXY` (e.g., `https://goproxy.cn,direct` for China regions).
- Verify the import path: `github.com/alibabacloud-go/das-20200116/v5/client`.

### JIT build timeout
- DAS SDK compilation is usually fast (< 10s). If timeout occurs, check disk space and network.
- Pre-warm the module cache by running `go mod tidy` in the workspace before critical operations.

## Diagnostic Tips

- Always verify instance registration status with `GetInstanceInspections` before running diagnosis or optimization operations.
- For DAS Pro features (SQL insight, auto-scaling, auto-SQL optimization), first verify the instance has an active Pro license via `GetDasProServiceUsage`.
- When polling async tasks (cache analysis, diagnostic report), use the documented poll interval and max wait times. Do not poll more frequently than every 5 seconds to avoid throttling.

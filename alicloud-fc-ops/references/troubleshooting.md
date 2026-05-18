# Troubleshooting — Function Compute (FC 3.0)

## Error Codes

| Error Code | HTTP Status | Meaning | Agent Action |
|-----------|------------|---------|-------------|
| InvalidArgument | 400 | Request parameter validation failed (missing/invalid fields) | Check body field types and required params |
| AccessDenied | 403 | Insufficient RAM permissions for FC API or resource | Add RAM policy with `fc:*` or specific fc actions |
| Forbidden.RAM | 403 | RAM policy explicitly denies the operation | Review RAM policy deny rules |
| FunctionNotFound | 404 | Specified function does not exist | Verify function name; ListFunctions to find correct name |
| TriggerNotFound | 404 | Specified trigger does not exist | Verify trigger name; ListTriggers |
| BucketAccessDenied | 403 | Cannot access OSS code package (wrong bucket ACL or RAM) | Check OSS bucket ACL and RAM policy |
| ResourceNotFound | 404 | Resource already deleted or never existed | Check ListFunctions; may need to recreate |
| OperationDenied | 403 | Operation not allowed (e.g. update published version, delete while in use) | Verify function state; wait or use qualifier |
| ResourceLimitExceeded | 409 | Account quota reached (functions count, concurrency) | HALT; request quota increase or delete unused |
| ServiceNotFound | 403 | FC service not activated for this account | HALT; enable FC in console first |
| ServiceBusy | 503 | FC platform temporarily unavailable | Retry with exponential backoff; escalates if persists |
| InternalError | 500 | FC platform internal error | Retry 3x with backoff; then HALT and escalate with RequestId |
| Throttling | 429 | Too many API requests | Retry with exponential backoff (2s, 4s, 8s) |
| RequestExpired | 400 | Request timestamp too old (> 15min) | Check system clock; retry immediately |
| InvalidSecurityToken | 400 | Invalid or expired STS token | Refresh STS credentials |
| InvalidParameter | 400 | Parameter out of valid range (e.g. memory outside 128-3072) | Check valid ranges in core-concepts.md limits |
| CodeTooLarge | 400 | Code package exceeds size limit | Use OSS upload path; max 50MB direct, 500MB via OSS |
| Timeout | 408 | Function execution exceeded timeout setting | Increase timeout; optimize code or split workloads |

## Diagnostic Order

Follow this sequence when troubleshooting FC issues:

1. **Check function exists and state**: `aliyun fc-open GET /2023-03-30/functions/{name}`
   - Verify `$.state == "ACTIVE"` or `SUCCESSFUL`
   - If `FAILED`, check `$.stateReason` and `$.stateReasonCode`
2. **Verify RAM permissions**: Ensure execution role has required `fc:*` permissions
3. **Check OSS code accessibility**: Verify bucket is accessible by FC execution role
4. **Review function config**: runtime, handler, memorySize, timeout match expectations
5. **Check concurrency limits**: `GetConcurrencyConfig` — verify not at limit
6. **Check provisioned vs on-demand**: `GetProvisionConfig` — warm instances may be missing
7. **Review recent changes**: deployments, config updates, trigger changes
8. **Check downstream dependencies**: RDS, Redis, OSS, external APIs
9. **Check region consistency**: `ALIBABA_CLOUD_REGION_ID` matches function location

## Common Issues

### "Function execution timed out"
- **Root cause**: execution time > configured timeout
- **Fix**: Increase `timeout` setting; optimize code; check external API latency

### "Function ran out of memory"
- **Root cause**: memory usage > configured `memorySize`
- **Fix**: Increase `memorySize`; profile memory with CloudMonitor metrics

### "Cold start latency is high"
- **Root cause**: Function init takes time (package download, runtime start, ENI setup)
- **Fix**:
  - Provisioned instances eliminate cold start
  - Increase memory (higher memory = faster CPU = faster init)
  - Reduce package size; use layers
  - Avoid VPC binding if not needed (+200-300ms ENI setup)

### "Function invocations are throttled"
- **Root cause**: Account-level or function-level concurrency limit reached
- **Fix**: Request concurrency quota increase; set provisioned instances; review `maxConcurrency`

### "Async invocation failed"
- **Root cause**: Function error or DLQ misconfigured
- **Fix**:
  - Check `maximumRetryAttempts` (set >= 2)
  - Configure `destination.onFailure` to SNS/Log for DLQ pattern
  - Increase `maxAsyncEventAgeInSeconds` if needed

# Failure Recovery Reference — ActionTrail (操作审计)

## Error Taxonomy

| Error Code | Description | Retryable | Max Retries | Backoff | Agent Action |
|------------|-------------|-----------|-------------|---------|--------------|
| `TrailNotFoundException` | Specified trail does not exist | No | 0 | — | HALT; suggest listing trails with DescribeTrails |
| `TrailAlreadyExistsException` | Trail name already in use | No | 0 | — | HALT; suggest a different trail name |
| `InvalidParameter` | Invalid parameter value | No | 0 | — | HALT; check parameter values against API docs |
| `InvalidParameterValue` | Parameter value out of range | No | 0 | — | HALT; check parameter constraints |
| `Throttling` | Request throttled | Yes | 3 | Exponential (1s, 2s, 4s) | Wait and retry; reduce request rate |
| `RequestError` | Network/connection error | Yes | 3 | Exponential (1s, 2s, 4s) | Check network connectivity; retry |
| `ServiceUnavailable` | Service temporarily unavailable | Yes | 3 | Exponential (2s, 4s, 8s) | Wait and retry; check service status |
| `InternalError` | Internal server error | Yes | 2 | Exponential (2s, 4s) | Retry; if persists, escalate |
| `AccessDenied` | Insufficient permissions | No | 0 | — | HALT; check RAM policy permissions |
| `InvalidAccessKeyId` | AccessKey ID not found | No | 0 | — | HALT; verify AccessKey ID |
| `SignatureDoesNotMatch` | Request signature mismatch | No | 0 | — | HALT; check credential configuration |
| `MissingParameter` | Required parameter missing | No | 0 | — | HALT; add required parameter |
| `DependencyViolation` | Resource has dependencies | No | 0 | — | HALT; resolve dependencies first |
| `QuotaExceeded` | Trail quota exceeded (max 5 per region) | No | 0 | — | HALT; delete unused trails or use different region |
| `AccessKeyNotFoundException` | AccessKey ID not found for audit | No | 0 | — | HALT; verify AccessKey ID |
| `InvalidEventType` | Invalid event type specified | No | 0 | — | HALT; use valid event types: ApiCall, ConsoleOperation, AliyunServiceEvent, PasswordReset, ConsoleSignin, ConsoleSignout |
| `InsightTypeNotAvailable` | Invalid or not-yet-enabled InsightType | No | 0 | — | HALT; use valid types: IpInsight, ApiCallRateInsight, ApiErrorRateInsight, AkInsight, PolicyChangeInsight, PasswordChangeInsight, TrailConcealmentInsight |
| `TimeRangeExceeded` | Time range exceeds 30 days or 90-day limit | No | 0 | — | HALT; adjust time range (max 30 days span, within 90 days) |

## HALT vs Retry Decision Matrix

| Condition | Decision | Rationale |
|-----------|----------|-----------|
| Business error (TrailNotFound, InvalidParameter, AccessDenied) | **HALT** | User or configuration action required |
| Throttling (Throttling) | **Retry** | Temporary; backoff resolves |
| Network error (RequestError, ServiceUnavailable) | **Retry** | Temporary infrastructure issue |
| Quota error (QuotaExceeded) | **HALT** | Requires resource cleanup or quota increase |
| Credential error (InvalidAccessKeyId, SignatureDoesNotMatch) | **HALT** | Requires credential fix |
| Missing parameter (MissingParameter) | **HALT** | Requires user input |
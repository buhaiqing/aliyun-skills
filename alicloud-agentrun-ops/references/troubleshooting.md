# Troubleshooting Guide — AgentRun Sandbox Operations

> **Purpose**: Error code reference, diagnostic procedures, and recovery strategies.

## 1. Error Response Format

### 1.1 Standard Error Structure

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": {
      "field": "additional context"
    }
  }
}
```

### 1.2 HTTP Status Codes

| Status | Category | Typical Causes |
|---|---|---|
| **400** | Client Error | Invalid parameters, malformed request |
| **401** | Authentication | Invalid/expired credentials |
| **403** | Authorization | RAM permission denied, signature mismatch |
| **404** | Not Found | Resource does not exist |
| **409** | Conflict | Resource already exists, state conflict |
| **413** | Payload Too Large | File > 100MB limit |
| **429** | Rate Limited | Too many requests |
| **500** | Server Error | Internal service failure |
| **507** | Insufficient Storage | Sandbox disk full |

---

## 2. Error Codes Reference

### 2.1 Control Plane Errors

| Error Code | HTTP | Cause | Resolution |
|---|---|---|---|
| `InvalidParameter` | 400 | Invalid request body | Check cpu/memory/templateName values |
| `InvalidParameter.TemplateName` | 400 | Template name invalid | 1-64 chars, alphanumeric/hyphen/underscore only |
| `InvalidParameter.ValueOutOfRange` | 400 | CPU/memory out of range | CPU: 1-8, Memory: 1024-16384 MB |
| `TemplateAlreadyExists` | 409 | Template name conflict | Use different name or update existing |
| `TemplateNotFound` | 404 | Template does not exist | Verify templateName, create first |
| `TemplateDependencyExists` | 409 | Sandbox depends on template | Delete sandboxes first |
| `SandboxAlreadyExists` | 409 | SandboxId conflict | Use different ID or let system generate |
| `SandboxNotFound` | 404 | Sandbox does not exist | Verify sandboxId (ULID format) |
| `SandboxNotReady` | 400 | Sandbox not in READY state | Wait for creation to complete |
| `Forbidden.RAM` | 403 | RAM permission denied | Request policy: `fc:CreateTemplate`, `fc:CreateSandbox` |
| `QuotaExceeded.Templates` | 429 | Template quota exceeded | Request quota increase via ticket |
| `QuotaExceeded.Sandboxes` | 429 | Sandbox quota exceeded | Clean up old sandboxes, request increase |
| `InternalError` | 500 | Service internal failure | Retry with exponential backoff (max 3) |

### 2.2 Data Plane Errors

| Error Code | HTTP | Cause | Resolution |
|---|---|---|---|
| `InvalidParameter.Code` | 400 | Code execution parameter error | Check language, code, timeout fields |
| `InvalidParameter.Path` | 400 | Invalid file path | No hidden files (`.` prefix), valid absolute path |
| `FileNotFound` | 404 | File does not exist in sandbox | Verify path, create file first |
| `FileAlreadyExists` | 409 | File already exists | Use different name or overwrite |
| `DirectoryNotFound` | 404 | Directory does not exist | Create directory with mkdir first |
| `FileSizeExceeded` | 413 | File > 100MB limit | Split file or use external storage |
| `StorageQuotaExceeded` | 507 | Sandbox disk full | Clean up files, increase diskSize |
| `ExecutionTimeout` | 400 | Code execution timeout | Reduce code complexity, set higher timeout |
| `ProcessNotFound` | 404 | Process PID not found | Verify pid, process may have terminated |
| `SandboxTerminated` | 400 | Sandbox already terminated | Create new sandbox |
| `ContextNotFound` | 404 | Context ID invalid | Create new context or use correct ID |
| `WebSocketConnectionFailed` | 400 | TTY WebSocket failed | Check sandbox status, retry connection |

### 2.3 Signing Errors

| Error Code | HTTP | Cause | Resolution |
|---|---|---|---|
| `SignatureDoesNotMatch` | 403 | Signature calculation error | Check signing algorithm, header order |
| `InvalidAccessKeyId.NotFound` | 403 | AK does not exist | Verify AccessKey ID |
| `InvalidAccessKeyId.Disabled` | 403 | AK disabled | Enable AK in RAM console |
| `RequestExpired` | 403 | X-Acs-Date timestamp too old | Sync clock, use NTP, timestamp < 15 min |
| `MissingAuthenticationToken` | 403 | Missing Authorization header | Include all required headers |
| `InvalidDate` | 403 | Date format invalid | Use ISO8601: `20250910T083000Z` |

---

## 3. Diagnostic Procedures

### 3.1 Pre-Flight Checks

**Before Any Operation**:

| Check | Method | Expected | Action on Failure |
|---|---|---|---|
| Credentials | `env vars non-empty` | AK + SK + Region + Account | HALT; configure environment |
| Clock Sync | `date -u` | Within 5 min of UTC | Sync with NTP |
| RAM Permissions | Test call or RAM console | Permissions granted | Request RAM policy update |
| Network Access | `curl agentrun endpoint` | HTTP 200/4xx | Check firewall, proxy |

### 3.2 Template Issues

**Symptom: CreateTemplate fails with `InvalidParameter`**

Diagnostic Steps:
1. Validate `templateName`: regex `[a-zA-Z0-9-_]{1,64}`
2. Check `cpu`: integer 1-8
3. Check `memory`: integer 1024-16384
4. Verify `networkMode`: `PUBLIC` or `PRIVATE`
5. If PRIVATE, ensure `vpcId` and `securityGroupId` provided

**Symptom: CreateTemplate fails with `TemplateAlreadyExists`**

Diagnostic Steps:
1. Call `GetTemplate(templateName)` to check existing
2. If exists and needs update → use `UpdateTemplate`
3. If new template needed → use different name

### 3.3 Sandbox Issues

**Symptom: CreateSandbox fails with `TemplateNotFound`**

Diagnostic Steps:
1. Call `ListTemplates` to verify template exists
2. Check template `status` = `READY`
3. If CREATING → poll until READY (interval 5s, max 60s)

**Symptom: Sandbox stuck in CREATING state**

Diagnostic Steps:
1. Poll `GetSandbox(sandboxId)` every 5 seconds
2. If > 120 seconds in CREATING → service issue
3. Call `DeleteSandbox` to clean up
4. Retry with new sandbox creation

**Symptom: ExecuteCode returns `SandboxNotReady`**

Diagnostic Steps:
1. Call `GetSandbox(sandboxId)` check status
2. If TERMINATED → create new sandbox
3. If CREATING → wait until READY

### 3.4 Execution Issues

**Symptom: ExecuteCode timeout (30 seconds)**

Diagnostic Steps:
1. Check code complexity (loops, I/O operations)
2. Reduce dataset size
3. Set explicit `timeout` parameter (< 30)
4. Split into multiple smaller executions

**Symptom: ExecuteCode returns error in results**

Diagnostic Steps:
1. Parse `results[type="stderr"]` for error message
2. Check `results[type="endOfExecution"].status`
3. If `error` → check code syntax, runtime errors
4. If `timeout` → optimize code complexity

### 3.5 File System Issues

**Symptom: File upload fails with `FileSizeExceeded`**

Diagnostic Steps:
1. Check file size (must be < 100MB)
2. Split large files into chunks
3. Use external storage (OSS) for large data

**Symptom: WriteFile fails with hidden file error**

Diagnostic Steps:
1. Check filename (cannot start with `.`)
2. Use valid filename pattern

**Symptom: `StorageQuotaExceeded`**

Diagnostic Steps:
1. List files with `ListFiles` to check disk usage
2. Remove unnecessary files
3. Increase `diskSize` in template (requires UpdateTemplate + new sandbox)

### 3.6 Signing Issues

**Symptom: `SignatureDoesNotMatch`**

Diagnostic Steps:
1. Verify header ordering (alphabetical, lowercase)
2. Check header values (trim spaces)
3. Verify body hash matches actual body
4. Ensure `X-Acs-Date` format is ISO8601
5. Check signing key derivation chain

**Symptom: `RequestExpired`**

Diagnostic Steps:
1. Check system clock: `date -u`
2. Ensure timestamp within 15 minutes
3. Use NTP to sync clock

---

## 4. Recovery Strategies

### 4.1 Retry Policies

| Error Type | Retry | Strategy | Max Attempts |
|---|---|---|---|
| **5xx Server Error** | ✅ Yes | Exponential backoff (1s → 2s → 4s) | 3 |
| **429 Rate Limited** | ✅ Yes | Wait + retry | 3 |
| **403 Signature Error** | ❌ No | Fix signing logic | 0 |
| **404 Not Found** | ❌ No | Verify resource exists | 0 |
| **400 Invalid Parameter** | ❌ No | Fix request body | 0 |

### 4.2 Exponential Backoff Implementation

```python
import time

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except (500, 429) as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait_time)
```

### 4.3 Graceful Degradation

**Sandbox Failure → Create New Sandbox**:
1. Delete failed sandbox
2. Create new sandbox from template
3. Restore state from file backups

**Template Failure → Use Default Template**:
1. Fallback to pre-created default template
2. Create sandbox from default

---

## 5. Monitoring & Alerting

### 5.1 Key Metrics

| Metric | Threshold | Alert Action |
|---|---|---|
| Sandbox creation time | > 60 seconds | Investigate service health |
| Sandbox failure rate | > 5% | Review template config, quota |
| Code execution timeout rate | > 10% | Optimize code, increase timeout |
| Signature error rate | > 1% | Audit signing implementation |
| 5xx error rate | > 1% | Contact support |

### 5.2 Health Check Integration

```bash
# Pre-execution health check
curl -X GET "https://{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/health" \
  -H "Authorization: $SIGNATURE"

# Expected: status = "ok"
```

---

## 6. Support Channels

| Issue Type | Channel | Response Time |
|---|---|---|
| API Documentation | help.aliyun.com | Self-service |
| Technical Support | Ticket via console | 24-48 hours |
| Quota Increase | Ticket via console | 3-5 business days |
| Service Outage | Emergency ticket | Immediate |

---

## 7. Common Pitfalls

### 7.1 Signing Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Header not lowercase | 403 Signature mismatch | Use lowercase header names |
| Header value has trailing space | 403 Signature mismatch | TrimSpace all header values |
| Body read after hash calculation | 403 Signature mismatch | Read body once, store for hash and request |
| Wrong date format | 403 InvalidDate | Use `YYYYMMDDTHHMMSSZ` |
| Clock drift > 15 min | 403 RequestExpired | Sync with NTP |

### 7.2 Sandbox Management Mistakes

| Mistake | Consequence | Prevention |
|---|---|---|
| Not stopping sandbox after use | Resource waste | Always call StopSandbox |
| Creating sandbox before template READY | SandboxNotReady error | Poll template until READY |
| Using terminated sandbox | All operations fail | Check status before operations |
| Ignoring 6-hour limit | Unexpected termination | Track sandbox creation time |

### 7.3 File System Mistakes

| Mistake | Consequence | Prevention |
|---|---|---|
| Hidden file upload | 400 InvalidParameter | Avoid `.` prefix filenames |
| File > 100MB | 413 Payload Too Large | Check size before upload |
| Writing to `/` or system paths | Permission denied | Use `/home/user` or `/workspace` |
| Not cleaning up files | Disk quota exceeded | Regular cleanup |

---

## 8. Debug Checklist

**Before API Call**:
- [ ] AK/SK configured and valid
- [ ] Region and Account ID correct
- [ ] RAM permissions verified
- [ ] Clock synchronized (NTP)
- [ ] Network connectivity verified

**For Template Operations**:
- [ ] templateName valid (1-64 chars)
- [ ] CPU 1-8, Memory 1024-16384
- [ ] NetworkMode valid (PUBLIC/PRIVATE)
- [ ] No existing template conflict

**For Sandbox Operations**:
- [ ] Template exists and READY
- [ ] SandboxId format valid (ULID)
- [ ] Sandbox status = READY for data plane ops

**For Signing**:
- [ ] Headers lowercase, sorted alphabetically
- [ ] Header values trimmed
- [ ] Body hash matches
- [ ] Timestamp within 15 min
- [ ] Signing key derivation correct
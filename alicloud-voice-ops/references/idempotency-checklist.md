# Alibaba Cloud Voice Messaging Service Idempotency Checklist

## What is Idempotency?
An operation is idempotent if performing it multiple times produces the same result as performing it once. This prevents duplicate calls, tasks, or notifications.

## Idempotency Rules for Voice Messaging

### 1. Single Call Operations
✅ Use `--out-id` parameter to ensure idempotency:
```bash
aliyun dyvmsapi single-call-by-voice \
  --called-number 15912345678 \
  --voice-code VFS-12345678-1234-1234-1234-1234567890ab \
  --out-id my-unique-request-id-123
```
Duplicate requests with the same `out-id` will return the original call ID instead of creating a new call.

### 2. Batch Task Operations
✅ Use unique task IDs and validate task status before retrying:
1. Generate a unique `task-name` for each batch task
2. Check if task exists with `list-call-task --task-name <task-name>`
3. Only create a new task if no existing pending/failed task with the same name

### 3. Template/File Management
✅ Template and file operations are automatically idempotent:
- Creating a template with the same name/code will return existing template details
- Uploading a file with the same name will overwrite the existing file

## Retry Strategies

### Transient Errors
Retry these errors with exponential backoff:
- `RequestTimeout`
- `ServiceUnavailable`
- `InternalError`

### Non-Transient Errors
Do NOT retry these errors:
- `InvalidPhoneNumber`
- `InvalidTemplateCode`
- `AuthenticationFailed`
- `QuotaExceeded`

## Idempotency Test Checklist

Before deploying any voice messaging operation:
1. ✅ Test duplicate single calls with same `out-id` → same result
2. ✅ Test duplicate batch tasks with same name → no duplicate tasks
3. ✅ Test retry of failed operations → no side effects
4. ✅ Validate that no duplicate notifications are sent to recipients
5. ✅ Check that task status remains consistent across retries

## Best Practices

1. Always use unique `out-id` for single call operations
2. Use meaningful task names for batch operations
3. Implement idempotency checks in your application layer
4. Avoid retrying non-transient errors
5. Monitor duplicate calls via CloudMonitor metrics

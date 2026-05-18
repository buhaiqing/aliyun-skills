# Enhanced Self-Healing Framework — FC 3.0

## 1. CLI Installation — Self-Healing Paths

### Network Exception Handling

| Error | Self-Healing Path | Fallback |
|-------|-------------------|----------|
| Download timeout | Retry with extended timeout (60s → 120s) | Switch to China CDN mirror: `goproxy.cn` |
| DNS resolution failure | Use IP-based endpoint | Retry with `--resolve` flag |
| SSL certificate error | Retry once with `--insecure` | Verify CA certificates |

### Permission Exception Handling

| Error | Self-Healing Path | Fallback |
|-------|-------------------|----------|
| Permission denied to `/usr/local/bin` | Use user directory `$HOME/.local/bin` | Prompt user to use `sudo` |
| Insufficient RAM for SDK build | Use smaller memory SDK build | HALT; request more system memory |

## 2. Go Runtime JIT — Self-Healing Paths

### Go Download Exception

| Error | Self-Healing Path | Fallback |
|-------|-------------------|----------|
| Go URL blocked | Try `https://dl.google.com/go` | Try `https://mirrors.aliyun.com/golang` |
| Incomplete download | Verify checksum; re-download | Use alternate mirror |
| Extract failure | Re-download and verify tar.gz | HALT; report corrupted download |

## 3. Dependency Download — Self-Healing Paths

| Error | Self-Healing Path | Fallback |
|-------|-------------------|----------|
| `go get` timeout | Retry with `GOPROXY=https://goproxy.cn,direct` | Retry with `GOPROXY=https://goproxy.io,direct` |
| Module not found | Try latest `v4` version | HALT; verify correct SDK package |
| GOMODCACHE full | Clear cache (`go clean -modcache`) | Use `/tmp/go-modcache` with more space |

## 4. FC Operation — Self-Healing Paths

| Error | Self-Healing Path | Fallback |
|-------|-------------------|----------|
| `Throttling` (429) | Automatic retry with exponential backoff (2s → 4s → 8s) | HALT after 3 retries; report rate limit |
| `InternalError` (500) | Retry 3x; if persists, escalate with RequestId | Check FC service status page |
| `InvalidArgument` | Validate request body against known required fields | Present detailed schema error to user |
| `AccessDenied` | Check RAM policy; suggest missing permissions | Escalate to RAM admin |
| `ResourceNotFound` | List functions to find correct name | HALT; function may have been deleted |
| `Function.Timeout` (FC execution) | Suggest increasing timeout or optimizing code | Check downstream service health |
| `Function.OutOfMemory` (FC execution) | Suggest increasing `memorySize` | Profile function for memory leaks |

## 5. Health Check & Validation

### Post-Installation Health Check

```bash
# CLI health check
aliyun version

# Go runtime health check
go version

# FC endpoint connectivity
aliyun fc-open GET "/2023-03-30/functions?limit=1"
```

### FC Function Health Check

| Check | Method | Healthy Indicator |
|-------|--------|-------------------|
| Function exists | `GetFunction` | State = `ACTIVE` |
| Invocation works | `InvokeFunction` (test payload) | 200 OK response |
| Code accessible | Code download or OSS check | No `BucketAccessDenied` |
| Execution role | `GetFunction` → check `$.role` | Valid RAM role ARN |

## 6. Self-Healing Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| CLI install success rate (auto-recover) | > 90% | Successful installs / total install attempts |
| JIT SDK build success rate | > 85% | Successful builds / total build attempts |
| Self-healing duration | < 30s for CLI; < 60s for SDK | Time from error to recovery |
| User intervention rate | < 15% | Cases requiring human action / total cases |
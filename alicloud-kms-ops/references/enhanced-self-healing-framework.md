# Enhanced Self-Healing Framework — KMS

## Overview

All CLI and Go SDK installation flows for KMS follow the enhanced self-healing framework with pre-flight checks, error classification, multi-path recovery, health verification, and graceful degradation.

## Self-Healing Metrics

| Metric | Target |
|--------|--------|
| Health score | ≥ 8/10 |
| Self-healing duration | < 30s |
| User intervention rate | < 20% |

## CLI Installation Self-Healing

### Pre-flight Checks

```bash
# Check 1: aliyun CLI exists
if command -v aliyun &>/dev/null; then
    echo "✅ aliyun CLI found: $(aliyun version)"
else
    echo "⚠️ aliyun CLI not found — initiating install"
    # Auto-install
    /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
fi
```

### Error Classification & Recovery Paths

| Error Type | Detection | Recovery Path 1 | Recovery Path 2 | Recovery Path 3 |
|------------|-----------|-----------------|-----------------|-----------------|
| **Network** (curl fails) | `curl` exit code ≠ 0 | Retry with `--retry 3` | Try alternative mirror URL | Download tarball manually |
| **Permission** (install to /usr/local) | `Permission denied` | Use `sudo` | Install to user-writable `~/bin` | Use HOME-based install |
| **Resource** (disk full) | `No space left on device` | Clear /tmp cache | Check available disk; suggest cleanup | Use alternative install location |
| **Configuration** (invalid credentials) | KMS API returns auth error | Verify env vars set | Check `~/.aliyun/config.json` format | Guide interactive `aliyun configure` |

## Go Runtime JIT Self-Healing

### Pre-flight Checks

```bash
# Check Go runtime
if command -v go &>/dev/null; then
    GO_VERSION=$(go version | grep -oP '\d+\.\d+')
    if [ "$(echo "$GO_VERSION >= 1.21" | bc)" -eq 1 ]; then
        echo "✅ Go runtime OK: $(go version)"
    else
        echo "⚠️ Go version too old — JIT upgrading"
        # Download Go 1.24
    fi
else
    echo "⚠️ Go not found — JIT downloading Go 1.24"
    # Download Go 1.24
fi
```

### Error Classification & Recovery Paths

| Error Type | Detection | Recovery Path 1 | Recovery Path 2 | Recovery Path 3 |
|------------|-----------|-----------------|-----------------|-----------------|
| **Network** (Go download fails) | `curl` exit code ≠ 0 | Retry with China mirror (`golang.google.cn`) | Try official Go CDN | Use pre-cached Go binary |
| **Permission** (GOPATH write) | `Permission denied` | Use `/tmp/go-workspace` | Use `~/go` | Use in-memory workspace |
| **Resource** (disk full for Go SDK) | `No space left` | Clean GOMODCACHE | Use `GOPROXY=direct` to skip cache | Free /tmp space |
| **Configuration** (go mod init fails) | Exit code ≠ 0 | Clean workspace and retry | Verify Go module path | Create minimal `go.mod` manually |

## SDK Dependency Self-Healing

### Pre-flight Checks

```bash
cd /tmp/aliyun-sdk-workspace
if [ -f "go.mod" ]; then
    echo "✅ Workspace initialized"
else
    go mod init kms-jit
fi
```

### Error Classification & Recovery Paths

| Error Type | Detection | Recovery Path 1 | Recovery Path 2 | Recovery Path 3 |
|------------|-----------|-----------------|-----------------|-----------------|
| **Network** (go get fails) | `go get` exit code ≠ 0 | Set `GOPROXY=https://goproxy.cn,direct` | Set `GOPROXY=https://goproxy.io,direct` | Download SDK manually, copy to workspace |
| **Version Conflict** | `requires incompatible version` | Pin to known-good version (`v3.4.0`) | Use `go mod tidy` to resolve | Clean `go.sum` and retry |
| **Permission** (mod cache write) | `Permission denied` | Set `GOMODCACHE=/tmp/go-modcache` | Use `GOPATH=/tmp/go-workspace` | Run with `GOFLAGS=-mod=mod` |
| **Configuration** (build fails) | `go run` exit code ≠ 0 | Check import paths | Verify Go 1.21+ compatibility | Simplify to minimal working example |

## Health Verification

After any self-healing action, verify:

```bash
# 1. CLI health
aliyun kms DescribeRegions && echo "✅ CLI healthy"

# 2. Go SDK health
cd /tmp/aliyun-sdk-workspace && go build -o /dev/null ./main.go 2>/dev/null && echo "✅ SDK builds"

# 3. Credential health
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ Credentials configured (masked)"
```

## Graceful Degradation

When self-healing cannot fully recover:

1. **CLI unavailable, SDK available** → Fall back to JIT Go SDK for all operations
2. **SDK unavailable, CLI available** → Use CLI-only path (sufficient for all KMS operations)
3. **Neither available** → Provide clear error with step-by-step manual recovery instructions
4. **Credentials invalid** → HALT all operations; guide user through credential setup

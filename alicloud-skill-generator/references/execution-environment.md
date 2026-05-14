# Execution Environment Setup

> **Purpose:** Detailed environment setup for executing `aliyun` CLI and JIT Go SDK operations. This file provides progressive depth for the [alicloud-skill-generator](../SKILL.md) meta-skill's Step 0.
> **Version:** 1.0.0
> **Last Updated:** 2026-05-14

---

## Table of Contents

1. [CLI-First with JIT Go SDK Fallback](#1-cli-first-with-jit-go-sdk-fallback)
2. [Phase 1: aliyun CLI Setup](#2-phase-1-aliyun-cli-setup)
3. [Phase 2: JIT Go SDK Setup](#3-phase-2-jit-go-sdk-setup)
4. [Credential Configuration](#4-credential-configuration)
5. [Credential Security (Mandatory)](#5-credential-security-mandatory)
6. [Environment Variable Sources](#6-environment-variable-sources)
7. [Verification](#7-verification)
8. [Enhanced Self-Healing](#8-enhanced-self-healing)

---

## 1. CLI-First with JIT Go SDK Fallback

The execution environment follows a **CLI-first with JIT Go SDK fallback** strategy:

1. **Primary path:** `aliyun` CLI (static Go binary, covers 90%+ APIs)
2. **Fallback path:** JIT Go SDK (dynamic script generation + `go run`)
3. **Go runtime:** JIT download if not present

---

## 2. Phase 1: aliyun CLI Setup

### Primary Path

**Install `aliyun` CLI using official auto-detect installer:**

The official installer (`install.sh`) automatically detects OS (`uname`) and architecture (`uname -m`) and downloads the correct binary.

```bash
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

Or download and run manually:
```bash
curl -fsSL https://aliyuncli.alicdn.com/install.sh -o /tmp/install-aliyun.sh
bash /tmp/install-aliyun.sh
```

The installer downloads from the Alibaba Cloud CDN:
- **macOS**: `aliyun-cli-macosx-latest-universal.tgz` (Intel + Apple Silicon)
- **Linux AMD64**: `aliyun-cli-linux-latest-amd64.tgz`
- **Linux ARM64**: `aliyun-cli-linux-latest-arm64.tgz` (ARM/Graviton instances)
- Binary is installed to `/usr/local/bin/aliyun`

**Alternative — Homebrew (macOS only):**
```bash
brew install aliyun-cli
```

**Verification after bootstrap:**
```bash
aliyun version
```

### Self-Healing Installation

See [enhanced-self-healing-framework.md](enhanced-self-healing-framework.md) for complete self-healing installation procedures including:
1. Pre-flight checks (network, disk, permissions, system compatibility)
2. Intelligent error classification
3. Multi-path self-healing (mirror switch, timeout adjustment, cache clear)
4. Health verification (binary check, permission check, PATH check, functional test)
5. Graceful degradation (fallback to JIT Go SDK)

---

## 3. Phase 2: JIT Go SDK Setup

When `aliyun` CLI is unavailable or does not support a specific API, **JIT build a Go SDK script** on-demand.

### Step 3.1: Bootstrap Go Runtime

**Check existing Go runtime:**
```bash
if command -v go &> /dev/null; then
    GO_VERSION=$(go version | awk '{print $3}')
    GO_MAJOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f1)
    GO_MINOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f2)
    if [ "$GO_MAJOR" -ge 1 ] && [ "$GO_MINOR" -ge 21 ]; then
        echo "Compatible Go runtime: $GO_VERSION"
    fi
fi
```

**JIT download Go 1.24+ (auto-detects OS and architecture):**
```bash
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
[ "$ARCH" = "x86_64" ] && ARCH="amd64"
[ "$ARCH" = "aarch64" ] && ARCH="arm64"

mkdir -p /tmp/go-runtime
curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime

export PATH="/tmp/go-runtime/go/bin:$PATH"
export GOPATH="/tmp/go-workspace"
export GOCACHE="/tmp/go-cache"
export GOMODCACHE="/tmp/go-modcache"
export GOPROXY="https://goproxy.cn,direct"
```

**Go version strategy:**
- **Primary:** Go 1.24+ (latest stable, optimal performance)
- **Fallback:** Go 1.23 → 1.22 → 1.21 (minimum compatibility)
- **Mirrors:** `https://go.dev/dl`, `https://dl.google.com/go`, `https://mirrors.aliyun.com/golang`, `https://golang.google.cn/dl`
- **Module proxy:** `GOPROXY=https://goproxy.cn,direct` (China CDN mirror)

### Step 3.2: Initialize Go Workspace

```bash
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
```

### Step 3.3: Get SDK Dependencies

```bash
# Core dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/tea-utils/v2/service

# Product-specific SDK (example: ECS)
go get github.com/alibabacloud-go/ecs-20140526/v4/client
```

**Multi-GOPROXY strategy (self-healing):**
```bash
GOPROXY_MIRRORS=(
    "https://goproxy.cn,direct"      # China CDN (primary)
    "https://goproxy.io,direct"      # Alternative China CDN
    "https://proxy.golang.org,direct" # Official proxy
    "direct"                          # Direct download (fallback)
)
```

> **SDK package naming:** `github.com/alibabacloud-go/<product>-<YYYYMMDD>/v<version>/client`
> Find package names at: https://github.com/alibabacloud-go or SDK Center

### Step 3.4: Generate and Execute SDK Script

```go
// main.go (generated dynamically by Agent)
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    // Product-specific SDK import (generated based on operation)
    ecs "github.com/alibabacloud-go/ecs-20140526/v4/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("ecs.aliyuncs.com"),
    }

    client, err := ecs.NewClient(config)
    if err != nil {
        panic(err)
    }

    request := &ecs.DescribeInstancesRequest{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }

    response, err := client.DescribeInstances(request)
    if err != nil {
        panic(err)
    }

    fmt.Println(tea.ToString(response.Body))
}
```

Execute:
```bash
cd /tmp/aliyun-sdk-workspace
go run ./main.go
```

### JIT Build Time Estimate

| Step | First Run | Subsequent Runs |
|------|-----------|-----------------|
| Download Go runtime | ~30s | 0s (cached) |
| `go get` dependencies | ~10s | ~2s (cached) |
| `go run` | ~5s | ~3s |
| **Total** | **~45s** | **~5s** |

---

## 4. Credential Configuration

### Environment Variables (Recommended for Agent Execution)

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Interactive CLI Configuration

```bash
aliyun configure
```

### Config File (`~/.aliyun/config.json`)

```bash
mkdir -p ~/.aliyun
cat > ~/.aliyun/config.json << 'CONFIGEOF'
{
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AK",
      "access_key_id": "{{user.access_key_id}}",
      "access_key_secret": "{{user.access_key_secret}}",
      "region_id": "{{user.region}}"
    }
  ]
}
CONFIGEOF
```

### Custom Config Path (Sandbox / CI Environments)

```bash
mkdir -p /tmp/aliyun-home/.aliyun
# Write config to custom path
aliyun --config-path /tmp/aliyun-home/.aliyun/config.json <product> <command>
```

> The `aliyun` CLI also supports: `StsToken`, `RamRoleArn`, `EcsRamRole`, `OIDC`, `CloudSSO`, `OAuth`, `External`, `CredentialsURI`, `ChainableRamRoleArn`. See official CLI docs.

### `.env` File Support

For local development convenience, load environment variables from a `.env` file:

```ini
# Alibaba Cloud credentials (use ALIBABA_CLOUD_* prefix)
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

**Safety rules:**
- **NEVER** commit `.env` files to version control
- **NEVER** write `.env` values into generated skill documents
- Generated skills continue using `{{env.*}}` placeholders
- Shell environment variables **MUST** override `.env` values

---

## 5. Credential Security (Mandatory)

All generated skills MUST enforce these credential security rules across **every** execution path (CLI, JIT Go SDK, verification scripts, debugging output):

| Context | Required Behavior | Example |
|---------|------------------|---------|
| **Console output** (stdout/stderr) | Any field whose key matches `*secret*`, `*key*` (case-insensitive) MUST have its value replaced with `<masked>` or `***` | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` |
| **Local log files** | Same masking rule; log entries MUST NOT contain raw credential values | `[INFO] Credentials: AKID=***, Secret=***` |
| **Error messages** | Error objects containing credential fields MUST be sanitized before display | `Error: Request failed (credential omitted)` |
| **Debug/verbose mode** (`aliyun --debug`) | Warn user that credential values may appear; recommend isolated environments | `⚠️ Debug mode may expose credential values in output` |
| **JIT Go SDK scripts** | SDK script reads credentials from env vars (safe); but `fmt.Println`, log, or error dump MUST NOT include `AccessKeySecret` | `client, err := [product].NewClient(config)` — struct never printed |
| **Template generation** | Use `{{env.*}}` placeholders only; never include example values or real keys | `AccessKeySecret: "{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"` |
| **Credential verification** | Verify existence only; never `echo` or print the value | `✅ ALIBABA_CLOUD_ACCESS_KEY_SECRET is set` |

**Masking patterns (use one of the following):**
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>`
- `AccessKeySecret=***`
- `"accessKeySecret": "***"`
- `secret=****`

**Non-compliance consequence:** Any skill that outputs un-masked credential values in console or logs SHALL be treated as a **security incident** and blocked from merge.

---

## 6. Environment Variable Sources

| Priority | Source | Description |
|----------|--------|-------------|
| 1 (highest) | CLI flags | `--access-key-id`, `--access-key-secret`, `--region` override everything |
| 2 | Shell environment | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID` |
| 3 | `~/.aliyun/config.json` | Persistent profile config (JSON format) |
| 4 (lowest) | Default profile | `default` profile from config file |

**Supported env var aliases (in fallback order):**
- **AK**: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABACLOUD_ACCESS_KEY_ID`, `ALICLOUD_ACCESS_KEY_ID`, `ACCESS_KEY_ID`
- **Secret**: `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABACLOUD_ACCESS_KEY_SECRET`, `ALICLOUD_ACCESS_KEY_SECRET`, `ACCESS_KEY_SECRET`
- **Region**: `ALIBABA_CLOUD_REGION_ID`, `ALIBABACLOUD_REGION_ID`, `ALICLOUD_REGION_ID`, `REGION_ID`, `REGION`

---

## 7. Verification

After credential setup, verify before proceeding:

```bash
# Primary: aliyun CLI validation
aliyun ecs DescribeRegions --output json | head -5
```

If `aliyun` validation fails (3 retries with backoff), proceed to JIT Go SDK verification:

```bash
# Go SDK credential check (in /tmp/aliyun-sdk-workspace)
cat > /tmp/aliyun-sdk-workspace/verify.go << 'EOF'
package main
import (
    "fmt"
    "os"
)
func main() {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    if ak == "" || sk == "" {
        fmt.Println("Missing ALIBABA_CLOUD_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        os.Exit(1)
    }
    fmt.Println("Credentials OK (JIT Go SDK mode)")
}
EOF
go run /tmp/aliyun-sdk-workspace/verify.go
```

> **SECURITY:** The verification code above **ONLY checks for existence** of credentials. **NEVER** log, print, or expose secret values. Use masked placeholders for any credential status output.

If all verification paths fail:
- HALT with clear message: "Credentials invalid or environment not set up"
- Suggest: Check `.env` file or run `aliyun configure`

---

## 8. Enhanced Self-Healing

See [enhanced-self-healing-framework.md](enhanced-self-healing-framework.md) for the complete self-healing framework covering:

- **CLI Installation:** Pre-flight checks → intelligent download → installation execution → health verification → graceful degradation
- **Go Runtime JIT Download:** Multi-version multi-mirror strategy → integrity check → version compatibility → PATH setup → health check
- **Dependency Download:** Multi-GOPROXY strategy → timeout control → cache management → build verification
- **Error Classification:** Network errors, permission errors, resource errors, configuration errors with specific recovery actions per category
- **Success Criteria:** Health score ≥ 8/10, self-healing duration < 30s, user intervention rate < 20%
---
name: alicloud-skill-generator
description: >-
  Use when adding or scaffolding a new Alibaba Cloud operational Agent Skill under
  `alicloud-*-ops` in this repository, regenerating structure from official docs
  or OpenAPI, or aligning an existing ops skill to the API/SDK template and P0/P1
  bar. Not for executing live changes against an Alibaba Cloud account.
license: MIT
compatibility: >-
  Access to Alibaba Cloud official documentation, OpenAPI/Swagger for the product,
  `alicloud-skill-generator/references/alicloud-skill-template.md`,
  `references/governance-and-adversarial-review.md` (when present),
  `references/prompt-library.md` (structured prompt repository),
  `references/optimization-analysis.md` (three-dimensional optimization framework),
  `references/user-experience-spec.md` (mandatory UX requirements for generated skills),
  and agentskills.io frontmatter conventions.
metadata:
  author: alicloud
  version: "2.0.0"
  last_updated: "2026-05-14"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  type: meta-skill
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
---

# Alibaba Cloud Skill Generator (Meta-Skill)

## Overview

This **meta-skill** defines **how** to author a new **product-scoped** operational skill (e.g. `alicloud-ecs-ops`) **inside this repo**. It does **not** perform maintenance against a user's cloud account. Live work uses the generated **`alicloud-[product]-ops`** skills (official **`aliyun` CLI** with **JIT Go SDK fallback**).

**Repository scope:** All generated layout and policies apply **only** to the `aliyun-skills` monorepo unless explicitly stated elsewhere elsewhere.

**Execution surface — CLI-first with JIT Go SDK fallback:** For every **new or materially updated** ops skill, the Agent MUST attempt to use the **`aliyun` CLI** as the primary execution path. The `aliyun` CLI is a **static Go binary** with no runtime dependencies. If `aliyun` CLI does not support a specific API or operation, the Agent MUST **JIT build a Go SDK script** on-demand. The Go SDK script is generated dynamically based on the operation, then executed via `go run`. **Console click-paths** are not an agent execution surface in `SKILL.md` except brief optional notes in `references/troubleshooting.md`. Semantics MUST stay consistent with **OpenAPI/official API docs**—see [governance-and-adversarial-review.md](references/governance-and-adversarial-review.md) (when present).

**Core principle:** Generated skills are **agent-readable runbooks**: triggers, env vs user placeholders, pre-flight → execute → validate → recover, safety gates, and outputs **grounded in OpenAPI and verified CLI behavior**, not guessed.

**Technology stack:**
- **CLI:** `aliyun` (Go binary, static, no dependencies)
- **SDK:** Alibaba Cloud Go SDK (`github.com/alibabacloud-go/<product>`)
- **JIT execution:** `go run` (script mode, dynamic generation)
- **Future extension:** Pre-compiled SDK binaries for faster distribution

## Role Boundary (Agent-Readable)

| This meta-skill **does** | This meta-skill **does not** |
|--------------------------|------------------------------|
| Choose **extend** vs **new** `alicloud-[product]-ops` | Replace deep product knowledge already in an existing ops skill |
| Scaffold `SKILL.md`, `references/*`, `assets/*` from the template | Call Alibaba Cloud APIs on behalf of the user |
| Enforce naming, frontmatter, P0/P1, delegation, and **governance** hooks | Invent request/response fields or CLI flags without official doc verification |
| Point authors to **adversarial review** before merge (when governance doc exists) | Store or echo real credentials |

If the user wants **operational execution** (e.g. "create a resource"), load the appropriate **`alicloud-*-ops`** skill for that product—not this generator.

## When to Use This Skill

- A new Alibaba Cloud product needs a **first** ops skill in **this repo**.
- An existing skill lacks P0 elements (triggers, placeholders, flows, recovery, destructive gates).
- OpenAPI or official docs changed; the skill should be **realigned** (bump version/changelog).
- A contributor needs the **standard directory layout** for a new `alicloud-[product]-ops`.

## When **Not** to Use

- One-off debugging with no intent to maintain a reusable skill.
- Non–Alibaba-Cloud application work.
- You only need billing/IAM execution—use dedicated ops skills when they exist; this meta-skill **authors** skills, it does not bypass them.

## Before You Generate: Decisions

1. **Extend vs new directory**
   - **Extend** same product and resource model (new operation section, paths, troubleshooting rows).
   - **New** `alicloud-[product]-ops` when the **service/API surface** or **primary resource** is distinct (e.g. ECS vs RDS).

2. **Naming**
   - Pattern: `alicloud-[product]-ops` (lowercase, hyphenated). Search the repo for collisions.

3. **Dependencies**
   - Cross-product chains: document **delegation** in Trigger & Scope; avoid duplicating another product's full flows.

4. **Sources of truth**
   - **OpenAPI + official docs** beat forums and chat logs. Pin an **API/SDK profile** in skill `metadata` or `references/integration.md`.

5. **Secrets**
   - Only `{{env.*}}` **names** and documentation; never real keys or customer data.
   - **Credential masking is MANDATORY.** Any console output or local log that references `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field MUST mask the actual value. See [Credential Security](#credential-security) below.

### Credential Security (Mandatory)

All generated skills MUST enforce the following credential security rules across **every** execution path (CLI, JIT Go SDK, verification scripts, debugging output):

| Context | Required Behavior | Example |
|---------|------------------|---------|
| **Console output** (stdout/stderr) | Any field whose key matches `*secret*`, `*key*` (case-insensitive) MUST have its value replaced with `<masked>` or `***` | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` |
| **Local log files** | Same masking rule; log entries MUST NOT contain raw credential values | `[INFO] Credentials: AKID=***, Secret=***` |
| **Error messages** | Error objects containing credential fields MUST be sanitized before display | `Error: Request failed (credential omitted)` |
| **Debug/verbose mode** (`aliyun --debug`) | If debug output is enabled, warn the user that credential values may appear; recommend using `--debug` only in isolated environments | `⚠️ Debug mode may expose credential values in output` |
| **JIT Go SDK scripts** | The SDK script itself reads credentials from env vars (safe); but any `fmt.Println`, log, or error dump MUST NOT include the value of `AccessKeySecret` | `client, err := [product].NewClient(config)` — the config struct is never printed/logged |
| **Template generation** | When generating skill docs, use `{{env.*}}` placeholders only; never include example values or real keys | `AccessKeySecret: "{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"` |
| **Credential verification** | Verify existence only (e.g., `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` or `if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") != ""`); never `echo` or print the value | `✅ ALIBABA_CLOUD_ACCESS_KEY_SECRET is set` (not the value) |

**Masking patterns (use one of the following):**
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>`
- `AccessKeySecret=***`
- `"accessKeySecret": "***"`
- `secret=****`

**Non-compliance consequence:** Any skill that outputs un-masked credential values in console or logs SHALL be treated as a **security incident** and blocked from merge.

6. **CLI-first with JIT Go SDK fallback**
   - The **primary** execution path is the **`aliyun` CLI** (static Go binary, covers 90%+ APIs).
   - If `aliyun` CLI does not support a specific API/operation, **JIT build a Go SDK script** dynamically.
   - Go SDK scripts are single-file, self-contained, and executed via `go run`.
   - If Agent Runtime lacks Go runtime, **JIT download Go 1.24+** from official source.
   - Scripts MUST be compatible with **Go 1.21+** (minimum version for Agent Runtime compatibility).

## Input Requirements (from Requester)

1. **Product name** (English; Chinese/aliases in Trigger & Scope if useful for matching user wording).
2. **Primary resource type** and **API service** identifier (as in OpenAPI tags or SDK package).
3. **Official documentation URL(s)**.
4. **OpenAPI/Swagger URL or path** (**strongly recommended**; required to claim API-accurate fields and error mapping).
5. **Operation list** (create, describe, modify, delete, list, product-specific).
6. **SDK runtime:** Go 1.21+ (minimum), Go 1.24+ preferred for JIT download.
7. **CLI support evidence:** Confirm the official **`aliyun`** product slug (via `aliyun help <product>` or CLI metadata). If `aliyun` metadata does not include this product, note the **JIT Go SDK fallback** path.

## Generation Process

### Step 0: Environment Setup

### Step 0: Environment Setup

Before analyzing sources, the Agent MUST ensure a working execution environment. The setup follows a **CLI-first with JIT Go SDK fallback** strategy:

1. **Primary path:** `aliyun` CLI (static Go binary, covers 90%+ APIs)
2. **Fallback path:** JIT Go SDK (dynamic script generation + `go run`)
3. **Go runtime:** JIT download if not present

#### Phase 1: aliyun CLI Setup (Primary Path)

**Install `aliyun` CLI using official auto-detect installer:**

The official installer (`install.sh`) automatically detects OS (`uname`) and architecture (`uname -m`) and downloads the correct binary.

**Install Script (macOS/Linux, auto-detects platform):**
```bash
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
```

Or download and run manually:
```bash
curl -fsSL https://aliyuncli.alicdn.com/install.sh -o /tmp/install-aliyun.sh
bash /tmp/install-aliyun.sh
```

> The installer downloads from the Alibaba Cloud CDN:
> - **macOS**: `aliyun-cli-macosx-latest-universal.tgz` (covers both Intel and Apple Silicon)
> - **Linux AMD64**: `aliyun-cli-linux-latest-amd64.tgz`
> - **Linux ARM64**: `aliyun-cli-linux-latest-arm64.tgz` (ARM/Graviton instances)
> - Binary is installed to `/usr/local/bin/aliyun`

**Alternative — Homebrew (macOS only):**
```bash
brew install aliyun-cli
```

**Verification after bootstrap:**
```bash
aliyun version
```

##### Enhanced Self-Healing Installation (Mandatory)

The Agent MUST follow the **Enhanced Self-Healing Framework** defined in [references/enhanced-self-healing-framework.md](references/enhanced-self-healing-framework.md). This framework provides:

1. **Pre-flight Checks** — Network connectivity, disk space, permissions, system compatibility
2. **Intelligent Error Classification** — Network, permission, resource, configuration errors
3. **Multi-Path Self-Healing** — Multiple recovery strategies per error type
4. **Health Verification** — Post-installation validation and status tracking
5. **Graceful Degradation** — Clear fallback paths when self-healing fails

**Self-Healing Decision Tree:**

```
[CLI Installation Attempt]
    │
    ├── Phase 1: Pre-flight Checks
    │   Network → Disk → Permissions → Compatibility
    │   (Auto-heal: switch mirrors, clean temp, use user dir)
    │
    ├── Phase 2: Intelligent Download
    │   Multi-mirror + Integrity check + Retry with adaptation
    │   (Auto-heal: mirror switch, timeout adjustment, cache clear)
    │
    ├── Phase 3: Installation Execution
    │   Script execution + Manual fallback
    │   (Auto-heal: manual binary download, permission fix)
    │
    ├── Phase 4: Health Verification
    │   Binary check → Permission check → PATH check → Functional test
    │   (Auto-heal: chmod +x, PATH update, reinstall)
    │
    └── Self-Healing Exhausted → Proceed to Phase 2: JIT Go SDK Setup
```

**Key Self-Healing Capabilities:**

| Error Type | Self-Healing Actions | Max Attempts |
|------------|---------------------|--------------|
| Network timeout | Mirror switch, timeout increase, retry with backoff | 5 |
| Permission denied | Use user directory, chmod +x, PATH update | 3 |
| Disk full | Clean temp files, use alternative path | 2 |
| Binary corrupt | Delete and re-download, integrity check | 3 |
| PATH missing | Auto-add to PATH, provide permanent fix instruction | 1 |

**Self-Healing Success Criteria:**
- Health score ≥ 8/10 (binary exists, executable, in PATH, version works, API call works)
- Self-healing duration < 30s
- User intervention rate < 20%

**If self-healing exhausted:**
- Proceed to **Phase 2: JIT Go SDK Setup**
- Log self-healing failure with error code and diagnostic info
- Provide user guidance template with manual installation options

#### Phase 2: JIT Go SDK Setup (Fallback Path)

When `aliyun` CLI is unavailable or does not support a specific API, **JIT build a Go SDK script** on-demand.

##### Step 2.1: Bootstrap Go Runtime (Enhanced Self-Healing)

The Agent MUST follow the **Enhanced Self-Healing Framework** for Go runtime JIT download. This includes:

**Pre-flight Checks:**
- Check existing Go runtime version compatibility (minimum: go1.21)
- Verify system architecture support
- Check disk space for Go runtime (~150MB)

**Multi-Version & Multi-Mirror Strategy:**

```bash
# Enhanced Go runtime bootstrap with self-healing
bootstrap_go_runtime_enhanced() {
    # Pre-check: existing Go runtime
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}')
        GO_MAJOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f1)
        GO_MINOR=$(echo "$GO_VERSION" | sed 's/go//' | cut -d. -f2)
        
        if [ "$GO_MAJOR" -ge 1 ] && [ "$GO_MINOR" -ge 21 ]; then
            echo "✅ Compatible Go runtime: $GO_VERSION"
            return 0
        fi
    fi
    
    # Self-healing: Multi-version fallback
    GO_VERSIONS=("go1.24.0" "go1.23.0" "go1.22.0" "go1.21.0")
    
    # Self-healing: Multi-mirror fallback
    GO_MIRRORS=(
        "https://go.dev/dl"
        "https://dl.google.com/go"
        "https://mirrors.aliyun.com/golang"  # China mirror
        "https://golang.google.cn/dl"        # China mirror
    )
    
    # Download with integrity check
    for version in "${GO_VERSIONS[@]}"; do
        for mirror in "${GO_MIRRORS[@]}"; do
            URL="${mirror}/${version}.${OS}-${ARCH}.tar.gz"
            
            if curl -fsSL --max-time 120 "$URL" -o /tmp/go.tar.gz; then
                # Integrity check: file size > 100MB
                FILE_SIZE=$(stat -c%s /tmp/go.tar.gz)
                if [ "$FILE_SIZE" -gt 100000000 ]; then
                    # Extract and verify
                    if tar -xzf /tmp/go.tar.gz -C /tmp/go-runtime; then
                        if [ -f "/tmp/go-runtime/go/bin/go" ]; then
                            export PATH="/tmp/go-runtime/go/bin:$PATH"
                            export GOPROXY="https://goproxy.cn,direct"
                            return 0
                        fi
                    fi
                fi
            fi
            
            # Self-healing: Clean failed download
            rm -f /tmp/go.tar.gz
        done
    done
    
    return 1  # All attempts failed
}
```

**Self-Healing Capabilities:**

| Error Type | Self-Healing Actions | Max Attempts |
|------------|---------------------|--------------|
| Download timeout | Mirror switch, timeout increase, version fallback | 4 versions × 4 mirrors |
| Download incomplete | File size check, re-download, cache clear | 3 |
| Extract failure | Integrity check, re-download, clean workspace | 2 |
| Version incompatible | Fallback to compatible version (go1.21+) | 4 versions |
| PATH setup fail | Use absolute path, verify binary exists | 1 |

**Health Check:**
- Go binary exists and executable
- Version ≥ go1.21
- Workspace initialized
- Dependencies cached

> **Go version strategy:**
> - **Primary:** Go 1.24+ (latest stable, optimal performance)
> - **Fallback:** Go 1.23 → 1.22 → 1.21 (minimum compatibility)
> - **Mirrors:** Official + China CDN mirrors for reliability
> - **Module proxy:** `GOPROXY=https://goproxy.cn,direct` (China CDN mirror)

##### Step 2.2: Initialize Go Workspace

Create a temporary workspace for JIT SDK scripts:

```bash
# Create workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace

# Initialize Go module
go mod init sdk-script
```

##### Step 2.3: Get SDK Dependencies (Enhanced Self-Healing)

The Agent MUST use enhanced self-healing for SDK dependency download:

**Multi-GOPROXY Strategy:**

```bash
# Enhanced dependency download with self-healing
download_sdk_dependencies_enhanced() {
    # Core dependencies
    CORE_DEPS=(
        "github.com/alibabacloud-go/darabonba-openapi/v2/client"
        "github.com/alibabacloud-go/tea"
        "github.com/alibabacloud-go/tea-utils/v2/service"
    )
    
    # Self-healing: Multi-proxy fallback
    GOPROXY_MIRRORS=(
        "https://goproxy.cn,direct"      # China CDN (primary)
        "https://goproxy.io,direct"      # Alternative China CDN
        "https://proxy.golang.org,direct" # Official proxy
        "direct"                          # Direct download (fallback)
    )
    
    for proxy in "${GOPROXY_MIRRORS[@]}"; do
        export GOPROXY="$proxy"
        SUCCESS=true
        
        for dep in "${CORE_DEPS[@]}"; do
            # Self-healing: Timeout control + retry
            if timeout 120 go get "$dep"; then
                echo "✅ Downloaded: $dep"
            else
                echo "⚠️  Failed: $dep with proxy $proxy"
                SUCCESS=false
                break
            fi
        done
        
        if [ "$SUCCESS" = true ]; then
            return 0
        fi
        
        # Self-healing: Clean cache before next proxy
        go clean -modcache
    done
    
    return 1  # All proxies failed
}
```

**Self-Healing Capabilities:**

| Error Type | Self-Healing Actions | Max Attempts |
|------------|---------------------|--------------|
| Proxy timeout | Switch GOPROXY, increase timeout, retry | 4 proxies |
| Version not found | Use latest stable version, fallback to direct | 3 |
| Network failure | Proxy switch, cache clean, retry with backoff | 4 |
| Permission denied | Use /tmp directory, clean cache | 2 |
| Build failure | Check Go version, clean cache, retry | 3 |

**Health Check:**
- All core dependencies downloaded
- Module cache populated
- Go.mod updated
- Dependencies compilable

> **SDK package naming:** `github.com/alibabacloud-go/<product>-<YYYYMMDD>/v<version>/client`
> Find package names at: https://github.com/alibabacloud-go or SDK Center

##### Step 2.4: Generate and Execute SDK Script

Generate a Go script dynamically based on the operation:

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
    // Read credentials from environment variables
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("ecs.aliyuncs.com"), // Generated based on product
    }
    
    client, err := ecs.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    // Operation-specific request (generated dynamically)
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

Execute the script:

```bash
# Generate script (Agent dynamically writes main.go)
# ... Agent writes operation-specific code to main.go ...

# Execute
go run ./main.go
```

##### Step 2.5: JIT Build Time Estimate

| Step | First Run | Subsequent Runs |
|------|-----------|-----------------|
| Download Go runtime | ~30s | 0s (cached) |
| `go get` dependencies | ~10s | ~2s (cached) |
| `go run` | ~5s | ~3s |
| **Total** | **~45s** | **~5s** |

> Dependencies and Go runtime are cached in `/tmp/go-*` directories.

##### Step 2.6: Alternative — Pre-built SDK Binary (Future Extension)

For faster distribution, pre-compiled SDK binaries can be stored on CDN:

```bash
# Future: Download pre-compiled SDK binary (no runtime needed)
curl -fsSL https://your-cdn/aliyun-sdk-ecs-linux-amd64 -o /tmp/sdk
chmod +x /tmp/sdk
/tmp/sdk --region cn-hangzhou --operation DescribeInstances
```

> This is a future extension. Current implementation uses `go run` script mode.

#### Configure Credentials

The `aliyun` CLI supports **multiple authentication methods**:

**AK (Simple):**
```bash
# Interactive setup (safe — no credential visible in process list)
aliyun configure
```

> **Security:** Prefer `aliyun configure` interactive mode or env vars. Passing `--access-key-secret` as a CLI flag exposes the credential value in the process listing (`ps aux`). If you must use the non-interactive form, run it in a secure/isolated environment and clear shell history afterward.

**Env vars (Agent Runtime preferred — aliyun reads these natively; safest method):**
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
```

**Config file (`~/.aliyun/config.json` JSON format):**
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

**Custom config path (sandbox / CI environments):**
```bash
mkdir -p /tmp/aliyun-home/.aliyun
# ... write config.json to /tmp/aliyun-home/.aliyun/config.json ...
# Then use: aliyun --config-path /tmp/aliyun-home/.aliyun/config.json <product> <command>
```

> The `aliyun` CLI also supports other auth modes: `StsToken`, `RamRoleArn`, `EcsRamRole`, `OIDC`, `CloudSSO`, `OAuth`, `External`, `CredentialsURI`, `ChainableRamRoleArn`. See official CLI docs for details.

#### Environment Variable Sources (Priority Order)

| Priority | Source | Description |
|----------|--------|-------------|
| 1 (highest) | CLI flags | `--access-key-id`, `--access-key-secret`, `--region` override everything |
| 2 | Shell environment | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID` |
| 3 | `~/.aliyun/config.json` | Persistent profile config (JSON format) |
| 4 (lowest) | Default profile | `default` profile from config file |

#### `.env` File Support

For local development convenience, the Agent MAY load environment variables from a `.env` file:

**Location options:**
- **Working directory (cwd)**: Agent Runtime's current working directory (recommended for cross-project mixing)
- Project root: `/path/to/aliyun-skills/.env` (when working within this repo)
- Custom path: User specifies via `--env-file` parameter

**Format (INI-style):**
```ini
# Alibaba Cloud credentials
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

**Multi-cloud mixing (recommended namespace prefixes):**
```ini
# Alibaba Cloud - use ALIBABA_CLOUD_* prefix
ALIBABA_CLOUD_ACCESS_KEY_ID=...
ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# JD Cloud - use JDC_* prefix
JDC_ACCESS_KEY=...
JDC_SECRET_KEY=...
JDC_REGION=cn-north-1

# AWS - use AWS_* prefix (standard)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
```

> **Namespace best practice:** Use platform-specific prefixes to avoid credential conflicts when mixing multiple cloud provider Skills.

**Priority rule:**
- Shell environment variables **MUST** override `.env` values

#### Safety Rules (Per Governance)

- **NEVER** commit `.env` files to version control (already in `.gitignore`)
- **NEVER** write `.env` values into generated Skill documents
- Generated Skills continue using `{{env.*}}` placeholders
- `.env` is for **local development convenience only**, not production

#### Verification

After loading, the Agent SHOULD verify credentials before proceeding to Step 1:

```bash
# Primary: try aliyun CLI validation
aliyun ecs DescribeRegions --output json | head -5
```

If `aliyun` validation fails, attempt retries per the **Retry Logic** above. After 3 failures, proceed to **Phase 2: JIT Go SDK Setup** and verify credentials via Go:

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

> **SECURITY WARNING:** The verification code above **ONLY checks for existence** of credentials. **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET` (or any secret) in console output, debug messages, or logs. If you need to log credential status, use masked placeholders like `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` or `ALIBABA_CLOUD_ACCESS_KEY_SECRET=***`.

If all verification paths fail:
- HALT with clear message: "Credentials invalid or environment not set up"
- Suggest: Check `.env` file or run `aliyun configure`

## Critical aliyun CLI Behavioral Notes (Empirical from Source Code Analysis)

These notes document real behavioral of the `aliyun` CLI, verified through source code analysis. **Every generated skill MUST follow these conventions.**

### Note 1: Default output IS JSON — no `--output json` needed

The `aliyun` CLI's default `OutputFormat` is `json` (configured in `NewProfile()`). Unlike the JD Cloud `jdc` CLI, you do **NOT** need `--output json` for plain JSON output:

```bash
# Works fine — output is JSON by default
aliyun ecs DescribeInstances --RegionId cn-hangzhou

# --output is primarily for JMESPath transformations
aliyun ecs DescribeInstances --output cols=InstanceId,Status rows=Instances.Instance[]

# Using a JMESPath expression to extract specific fields
aliyun ecs DescribeInstances --output cols=InstanceId rows=Instances.Instance[*].InstanceId
```

**Fix:** In generated skills, plain JSON output does NOT require `--output json`. Use `--output cols=...,rows=...` only when tabular extraction is needed.

### Note 2: `--no-interactive` does NOT exist (same as jdc)

The `aliyun` CLI does not define `--no-interactive` anywhere. All commands are non-interactive by default.

```bash
# WRONG:
aliyun ecs DescribeInstances --no-interactive

# CORRECT (just omit it):
aliyun ecs DescribeInstances --RegionId cn-hangzhou
```

### Note 3: The `aliyun` CLI natively supports environment variables

Unlike `jdc`, the `aliyun` CLI reads credentials from environment variables natively (source: `profile.go::OverwriteWithFlags`):

```go
if cp.AccessKeyId == "" {
    cp.AccessKeyId = util.GetFromEnv(
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALIBABACLOUD_ACCESS_KEY_ID",
        "ALICLOUD_ACCESS_KEY_ID",
        "ACCESS_KEY_ID",
    )
}
```

Supported env vars (in fallback order):
- **AK**: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABACLOUD_ACCESS_KEY_ID`, `ALICLOUD_ACCESS_KEY_ID`, `ACCESS_KEY_ID`
- **Secret**: `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABACLOUD_ACCESS_KEY_SECRET`, `ALICLOUD_ACCESS_KEY_SECRET`, `ACCESS_KEY_SECRET`
- **STS Token**: `ALIBABA_CLOUD_SECURITY_TOKEN`, `ALIBABACLOUD_SECURITY_TOKEN`, `ALICLOUD_SECURITY_TOKEN`
- **Region**: `ALIBABA_CLOUD_REGION_ID`, `ALIBABACLOUD_REGION_ID`, `ALICLOUD_REGION_ID`, `REGION_ID`, `REGION`
- **Profile**: `ALIBABACLOUD_PROFILE`, `ALIBABA_CLOUD_PROFILE`, `ALICLOUD_PROFILE`
- **Endpoint**: `ALIBABA_CLOUD_ENDPOINT`, `ALIBABACLOUD_ENDPOINT`
- **Endpoint Type**: `ALIBABA_CLOUD_ENDPOINT_TYPE`
- **External Account Type**: `ALIBABA_CLOUD_EXTERNAL_ACCOUNT_TYPE`
- **Debug**: `DEBUG=sdk` (enable HTTP request logging)

### Note 4: Config file is JSON (not INI)

The `aliyun` CLI stores config in `~/.aliyun/config.json` as JSON:

```json
{
  "current": "default",
  "profiles": [
    {
      "name": "default",
      "mode": "AK",
      "access_key_id": "AKID",
      "access_key_secret": "SECRET",
      "region_id": "cn-hangzhou",
      "output_format": "json",
      "language": "en"
    }
  ]
}
```

### Note 5: Sandbox workaround — env vars + --config-path

For sandboxed/containerized environments:

```bash
# Option A (preferred): Set env vars directly (no file I/O needed)
export ALIBABA_CLOUD_ACCESS_KEY_ID="..."
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="..."
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"

# Option B: Custom config path with --config-path flag
mkdir -p /tmp/aliyun-home/.aliyun
cat > /tmp/aliyun-home/.aliyun/config.json << 'EOF'
{"current":"default","profiles":[{"name":"default","mode":"AK","access_key_id":"AKID","access_key_secret":"SECRET","region_id":"cn-hangzhou"}]}
EOF
aliyun --config-path /tmp/aliyun-home/.aliyun/config.json ecs DescribeRegions
```

### Note 6: Correct CLI invocation patterns

```bash
# RPC style APIs (most products):
aliyun <product> <OperationName> --RegionId <region> --Param1 value1

# Example:
aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 50
aliyun rds DescribeDBInstances --RegionId cn-hangzhou

# RESTful style APIs (Container Service etc.):
aliyun cs GET /clusters
aliyun cs POST /clusters --body "$(cat input.json)"

# Skip metadata validation for unknown APIs:
aliyun <product> --version 2024-01-01 --endpoint <product>.aliyuncs.com --force

# Polling with --waiter:
aliyun ecs DescribeInstances --InstanceIds '["i-xxx"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=300 interval=5
```

### Step 1: Analyze sources

Extract:

- Operations, parameters, enums, errors, and **response schemas** from OpenAPI.
- When `aliyun` applies: **full** command map vs SDK operation list; flag parity; **actual JSON** shape per command (may differ from raw API—verify).
- Async behavior (polling, terminal states) from docs or API patterns.
- Metrics/alarm dimensions if monitoring is in scope.
- **Delegation** targets (monitoring, VPC, SLB, RAM/billing).

### Step 2: Create directory layout

```text
alicloud-[product]-ops/
├── SKILL.md
├── references/
│   ├── core-concepts.md
│   ├── api-sdk-usage.md
│   ├── cli-usage.md              # aliyun CLI usage (primary path)
│   ├── troubleshooting.md
│   ├── monitoring.md
│   └── integration.md
└── assets/
    └── example-config.yaml
```

Add **`references/idempotency-checklist.md`** when retries or automation require documented idempotent behavior (pattern: `alicloud-vpc-ops/references/idempotency-checklist.md`).

### Step 3: Populate `SKILL.md` from template

Base: [alicloud-skill-template.md](references/alicloud-skill-template.md).

Replace placeholders and **wire JSON paths / SDK calls / `aliyun` invocations** to verified OpenAPI and **measured** CLI output where applicable. Generic examples in the template are not authoritative.

### Step 4: Fill reference files

- **core-concepts.md** — Architecture, limits, regions, quotas.
- **api-sdk-usage.md** — Operation map, required fields, pagination, example request/response snippets (**no secrets**).
- **cli-usage.md** — **`aliyun` CLI cheat sheet**: command map, default JSON output (no `--output json` needed), `--output cols=...,rows=...` for JMESPath, **no `--no-interactive`** (flag does NOT exist), **cli-metadata coverage gap** table, documented default JSON paths, and **credential note** (CLI natively reads env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` etc., plus config file `~/.aliyun/config.json` JSON). This is the **primary path** reference.
- **troubleshooting.md** — API/CLI error codes, ordered diagnostics.
- **monitoring.md** — Metrics, dashboards, alerts.
- **integration.md** — **Go runtime bootstrap**, **JIT Go SDK setup** (go mod init + go get), **`aliyun` install/config** (required for primary path), env vars, optional MCP notes.

### Step 5: Frontmatter and versioning

- `name` matches the directory.
- **`description`** on the **ops** skill: third person, **when to use** only (triggers); do not summarize the full workflow ([OpenSpec](https://agentskills.io/specification)).
- Bump `metadata.version` and `last_updated`; update **Changelog** in `SKILL.md`.

### Step 6: Verify

- Complete **P0/P1** below.
- Run **[governance adversarial scenarios](references/governance-and-adversarial-review.md#minimal-adversarial-scenarios)** (when present; mentally or with a fresh agent context) and patch gaps.

## Governance (Expert Recommendation)

**Minimal adversarial review** gives high return for low cost: it catches destructive-action shortcuts, credential leaks in instructions, and API hallucination **before** merge. Treat [governance-and-adversarial-review.md](references/governance-and-adversarial-review.md) (when present) as the **reviewer companion** to this meta-skill.

Optional later improvements: PR template checkbox linking to that doc; periodic check that CLI-documented skills stay aligned with OpenAPI when APIs change.

## Agent-Ready Quality Checklist

### P0 — MUST PASS

- [ ] **Trigger & Scope** with SHOULD-use / SHOULD-NOT-use and delegation.
- [ ] **Variables:** `{{env.*}}` vs `{{user.*}}`; no secret literals.
- [ ] **Flows:** Pre-flight → Execute → Validate → Recover for **each** critical operation; **each** flow documents **`aliyun` as primary path** and **SDK/API as fallback**.
- [ ] **Failure recovery:** HALT vs retry; throttling; non-retryable business errors.
- [ ] **API fidelity:** Fields and paths traceable to OpenAPI/SDK for the stated version.
- [ ] **aliyun-first with fallback:** `references/cli-usage.md` present as primary path; `SKILL.md` execution sections include both `aliyun` and SDK/API paths; explicit **enhanced self-healing** documented.
- [ ] **CLI fidelity:** Default output is JSON (NO `--output json` needed), `--output` used for JMESPath only; commands match official CLI docs; JSON paths **verified** with a real CLI run.
- [ ] **Safety gates** for destructive operations (before **each** documented path: `aliyun` **and** SDK fallback).
- [ ] **Timeouts** for polling and long-running operations.
- [ ] **Self-Healing Framework:** All installation flows follow [enhanced-self-healing-framework.md](references/enhanced-self-healing-framework.md) with pre-flight checks, error classification, multi-path recovery, health verification, and graceful degradation.
- [ ] **Self-Healing Coverage:** CLI install, Go runtime JIT, dependency download all have ≥ 3 self-healing paths per error type.
- [ ] **Self-Healing Metrics:** Health score ≥ 8/10, self-healing duration < 30s, user intervention rate < 20% documented as success criteria.
- [ ] **UX Onboarding:** Quick Start section present; first-time user can execute first command within 60 seconds per `references/user-experience-spec.md` Section 2.1.
- [ ] **UX Interaction:** Common operations require ≤ 3 prompts; smart defaults documented; destructive operations have explicit confirmation per `references/user-experience-spec.md` Section 3.
- [ ] **UX Feedback:** Success/failure messages follow standardized format; progress shown for operations > 5s per `references/user-experience-spec.md` Section 4.
- [ ] **UX Error Handling:** Error messages follow `[ERROR] code: summary → explanation → fix → next step` format per `references/user-experience-spec.md` Section 5.
- [ ] **Prompt Library Alignment:** Generation process uses structured prompts from `references/prompt-library.md` with effectiveness tracking.
- [ ] **Optimization Awareness:** Skill design considers Fault Diagnosis, Root Cause Localization, and Rapid Resolution dimensions per `references/optimization-analysis.md`.
- [ ] **AIOps Compliance (if skill involves monitoring/alarm/diagnosis):** Skill implements multi-metric correlation, cross-skill diagnosis decision tree, delegation matrix, proactive inspection, and alarm storm handling per `references/aiops-best-practices.md`.

### P1 — SHOULD PASS

- [ ] **Chaining:** Stable output fields for downstream skills.
- [ ] **Naming:** `alicloud-[product]-ops` consistent with repo.
- [ ] **Pinned** SDK/API baseline where drift matters.
- [ ] **Idempotency** or duplicate-resource behavior documented when automation applies.
- [ ] **Adversarial scenarios** considered using the governance doc (when present).
- [ ] **Path preference:** `SKILL.md` states when to prefer `aliyun` vs SDK fallback if non-obvious.
- [ ] **Metadata:** Ops skill frontmatter includes appropriate metadata per template.

## Example Request

> Add an Alibaba Cloud skill for ECS in this repo: instances, disks, snapshots. Docs: `https://help.aliyun.com/zh/ecs`. OpenAPI: [https://help.aliyun.com/zh/ecs/developer-reference/api-ecs-2014-05-26-overview](https://help.aliyun.com/zh/ecs/developer-reference/api-ecs-2014-05-26-overview). Go SDK (JIT fallback).

**Expected output:** `alicloud-ecs-ops` tree with **real** operationIds, Go SDK types, response paths, **and** matching `aliyun` commands (primary path), plus JIT Go SDK fallback documentation.

## See Also

- [Skill template](references/alicloud-skill-template.md)
- [Enhanced Self-Healing Framework](references/enhanced-self-healing-framework.md) — **MANDATORY** self-healing patterns for CLI/Go/dependency installation
- [Governance & adversarial review](references/governance-and-adversarial-review.md) (when present)
- [Prompt library](references/prompt-library.md) — structured prompts for generation lifecycle
- [Optimization analysis](references/optimization-analysis.md) — three-dimensional optimization framework
- [User experience specification](references/user-experience-spec.md) — mandatory UX requirements for all generated skills
- [AIOps best practices](references/aiops-best-practices.md) — mandatory AIOps patterns for monitoring/diagnosis skills
- [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- [Alibaba Cloud SDK for Go](https://github.com/alibabacloud-go)
- [Agent Skills Open Specification](https://agentskills.io/specification)
- Idempotency pattern: `alicloud-[product]-ops/references/idempotency-checklist.md` (when present)

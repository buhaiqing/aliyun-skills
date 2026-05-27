---
name: alicloud-[product-name]-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud [Product Name] — [Resource Type] lifecycle, configuration, and
  diagnostics. User mentions [Product Name], [Product Chinese Name],
  [Product Alias], or describes product-specific scenarios (e.g., connection
  drops, performance degradation, resource creation failures) even without
  naming the product directly. Not for billing, RAM, or related products that
  have their own ops skills.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "3.0.0"
  last_updated: "2026-05-14"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "[Paste OpenAPI title/version or doc link]"
  cli_applicability: "dual-path"  # Choose: cli-first / dual-path / sdk-only / cli-only
  cli_support_evidence: >-
    [If CLI covers this product: cite confirmation via `aliyun help <product>`.
    If CLI does NOT cover: note JIT Go SDK fallback required.]
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This template follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud [Product Name] Operations Skill

## Overview

[Product Name] on Alibaba Cloud provides [brief description]. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **dual-path execution** (official **SDK/API** and, when the product is supported by official **`aliyun`**, the matching **CLI** flows), response validation, and failure recovery. **Do not use the web console as the primary agent execution path** in `SKILL.md` or [阿里云控制台](https://www.aliyun.com).

> **UX Compliance:** This skill follows the [User Experience Specification](../references/user-experience-spec.md). All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** Official `aliyun` fully supports this product. CLI is the **primary** execution path. JIT Go SDK is the **fallback** only for edge-case operations CLI doesn't expose. Omit `references/cli-usage.md` content gaps unless partial coverage exists.
- **`cli_applicability: dual-path`:** Official `aliyun` supports this product. You **MUST** ship **`references/cli-usage.md`** and, in **each** execution flow below, document **both** the SDK step **and** the `aliyun` step for every operation the CLI exposes. If the CLI covers **only part** of the API, add a **coverage gap** table (SDK-only operations) in `references/cli-usage.md`.
- **`cli_applicability: sdk-only`:** Official `aliyun` does **not** expose this product. **Omit** `references/cli-usage.md`. Keep **`cli_support_evidence`** pointing at official proof. SDK/API remains mandatory for all operations.
- **`cli_applicability: cli-only`:** Read-only/discovery skills that ONLY query cloud resources (e.g., `alicloud-topo-discovery`). No write operations, no SDK fallback needed. No `references/cli-usage.md` required beyond basic usage examples.

## Five Core Standards (Quality Gates)

Every generated skill MUST satisfy these five standards. Use them as a design checklist during population:

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with ≥ 10 product-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product, one primary resource model; cross-product delegation to other skills |

Refer to the [meta-skill](../SKILL.md#five-core-standards-quality-gates) for detailed descriptions of each standard.

### Well-Architected Framework Integration (卓越架构)

In addition to the Five Core Standards, every generated skill MUST map its operations to Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html) five pillars:

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | IAM permissions, credential masking, network isolation | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | Backup/restore, multi-AZ, DR runbook, failure-oriented design | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | Billing model comparison, waste detection, right-sizing | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Batch operations, CI/CD integration, automation patterns | `references/well-architected-assessment.md` §2.4 |
| **性能 (Performance)** | Metrics, auto-scaling, performance baselines | `references/well-architected-assessment.md` §2.5 |

See [references/well-architected-assessment.md](references/well-architected-assessment.md) for the complete specification.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud [Product Name]" OR "[Product Chinese Name]" OR "[Product Alias]"
- Task involves CRUD or lifecycle operations on **[Resource Type]** (create, describe, modify, delete, list, and product-specific actions)
- Task keywords: [keyword1], [keyword2], [keyword3], …
- User asks to deploy, configure, troubleshoot, or monitor [Product Name] **via API, SDK, CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **[related product]** → delegate to: `alicloud-[other]-ops`
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

### Delegation Rules

- If resource B depends on resource A, complete or verify A (via the A skill) before B's SDK or CLI steps.
- Multi-product requests: handle each product with its skill; do not merge unrelated APIs into one ambiguous flow.

## Variable Convention (Agent-Readable)

Structured placeholders reduce injection ambiguity and unsafe prompts:

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.resource_name}}` | User-supplied name | Ask once; reuse |
| `{{output.resource_id}}` | From last API or CLI JSON response | Parse per **OpenAPI** (SDK) or **verified CLI** path for this operation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **Security Warning (Credential Masking — MANDATORY):** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `access_key_secret`, `AccessKeySecret`, or any credential field value in console output, debug messages, error messages, or logs.
>
> **Masking rules across all execution paths:**
> | Execution Path | Safe Pattern | Unsafe Pattern |
> |----------------|-------------|----------------|
> | Console output | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` | `ALIBABA_CLOUD_ACCESS_KEY_SECRET=LTAI5t...` |
> | Error messages | `Error: API call failed (credential omitted)` | `Error: InvalidAccessKeySecret.XXX ... actual secret...` |
> | Log files | `[INFO] Credentials configured: Secret=***` | `[INFO] AK Secret: LTAI5t...` |
> | Verification | `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "✅ Secret is set"` | `echo "Secret=$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` |
> | JIT Go SDK | `AccessKeySecret: tea.String(os.Getenv("..."))` (env read is safe) | `fmt.Printf("Config: %+v", config)` or `log.Printf("%+v", ...)` |
> | Debug/verbose | `⚠️ Debug mode may expose credential values` (warning only) | `--debug` with un-masked credential output |
>
> **Credential verification MUST check existence only**, never echo the value:
> - Bash: `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"` ✅ | `echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET` ❌
> - Go: `if os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") == ""` ✅ | `fmt.Println(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"))` ❌
>
> **If any execution flow violates this rule, the skill SHALL be blocked from merge as a security incident.**

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes. Replace generic JSON paths below with **real** schema field names.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec. Do not assume a single global shape across products.
- **Timestamps:** ISO 8601 with timezone when the API returns strings (e.g. `2026-04-28T10:00:00+08:00`).
- **Idempotency:** Document client request tokens, duplicate names, and `ResourceAlreadyExists` behavior per API.

### Example Response Field Table (Replace with OpenAPI-Accurate Paths)

| Operation | JSON Path (example) | Type | Description |
|-----------|---------------------|------|-------------|
| Create | `$.resourceId` | string | New resource ID (verify name in spec) |
| Describe | `$.status` | string | Lifecycle state |
| List | `$.resources[].resourceId` | array | IDs (verify array structure) |
| Modify / Delete | `$.requestId` or `$.error` | string / object | Per spec |

### Expected State Transitions (Adjust to Product)

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| Create | — | `running` or product equivalent | 5s | 300s |
| Start | `stopped` | `running` | 5s | 120s |
| Stop | `running` | `stopped` | 5s | 120s |
| Delete | any stable state | absent or `deleted` per describe | 5s | 300s |

## Quick Start

### What This Skill Does
This skill enables you to deploy, configure, troubleshoot, and monitor [Product Name] resources on Alibaba Cloud using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites
- [ ] `aliyun` CLI installed (or Go runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup
```bash
# Check CLI and credentials
aliyun [product] DescribeRegions
```

### Your First Command
```bash
# Example: List resources
aliyun [product] Describe[Resources] --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand [Product Name] architecture
- [Common Operations](#execution-flows) — Create, manage, and delete resources
- [Troubleshooting](references/troubleshooting.md) — Fix common issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| Create | Create a new [Resource] | Medium | Low |
| Describe | View [Resource] details | Low | None |
| Modify | Change [Resource] configuration | Medium | Medium |
| Delete | Remove a [Resource] | Low | **High** — irreversible |
| List | View all [Resources] | Low | None |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-14 | Initial API/SDK-oriented template with aliyun CLI support |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (SDK/API and, when applicable, `aliyun`) → Validate → Recover**. Do not skip phases.

**Preference hint:** When CLI does not support a specific operation, JIT build a Go SDK script. CLI is preferred for coverage and simplicity; Go SDK is used for operations CLI does not expose.

### Operation: Create [Resource]

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | Import client; version matches `metadata.api_profile` | No import error | Document install pin |
| CLI / deps | `aliyun version` (**required** when `cli_applicability: cli-first` / `dual-path` / `cli-only`) | Exit code 0 | Document CLI install |
| Credentials | Construct credential from env (SDK) or CLI config/env per official CLI docs | Non-empty keys / valid config | HALT; user configures env |
| Region | Call **DescribeRegions** (or equivalent) if applicable | `{{user.region}}` supported | Suggest valid region |
| Quota | Call quota/describe API per OpenAPI | Sufficient quota | HALT; user raises quota |

#### Execution — CLI (`aliyun`) (Primary Path)

Use the [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli) as the **primary execution path**.

> **Critical CLI Notes** (verified through source code analysis):
> - Output is **JSON by default** — NO `--output json` needed for plain JSON
> - `--output` is for JMESPath transformations: `--output cols=InstanceId,Status rows=Instances.Instance[]`
> - `--no-interactive` does NOT exist — CLI is non-interactive by default
> - Credentials can be passed via environment variables `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
> - For RPC-style APIs: `aliyun <product> <OperationName> --RegionId cn-hangzhou --Param1 value1`

```bash
# RPC-style API call (JSON output by default)
aliyun [product] Create[Resource] \
  --RegionId "<region-from-user>"
  # add --ParamName value per official `aliyun help <product> Create[Resource]`
```

#### Execution — JIT Go SDK (Fallback Path)

When `aliyun` CLI does not support a specific operation, **JIT build a Go SDK script** dynamically:

```go
// main.go (generated dynamically in /tmp/aliyun-sdk-workspace)
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    // Replace with product-specific SDK
    [product] "github.com/alibabacloud-go/[product]-[YYYYMMDD]/v[version]/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("[product].aliyuncs.com"),
    }
    
    client, err := [product].NewClient(config)
    if err != nil {
        panic(err)
    }
    
    // Operation-specific request (generated per OpenAPI)
    request := &[product].Create[Resource]Request{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
        // Add fields per OpenAPI request schema
    }
    
    response, err := client.Create[Resource](request)
    if err != nil {
        panic(err)
    }
    
    fmt.Println(tea.ToString(response.Body))
}
```

Execute:
```bash
# In /tmp/aliyun-sdk-workspace
go mod init sdk-script
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/[product]-[YYYYMMDD]/v[version]/client
go run ./main.go
```

#### Post-execution Validation

1. Read `{{output.resource_id}}` from the **documented** response path.
2. Poll **Describe** until terminal success state or timeout:

```bash
# CLI polling (via --waiter)
aliyun [product] Describe[Resource] \
  --[IdName] "{{output.resource_id}}" \
  --waiter expr='[Resource][0].Status' to=Running timeout=300 interval=5

# Or Go SDK polling (in main.go)
for i := 0; i < maxAttempts; i++ {
    resp, err := client.Describe[Resource](describeRequest)
    if err != nil { panic(err) }
    status := tea.ToString(resp.Body.Status)
    if status == "Running" { break }
    time.Sleep(pollInterval)
}
```

```bash
# Dual-path example: poll with aliyun + jq (adjust jq paths after verification)
# for i in $(seq 1 60); do
#   STATUS=$(aliyun [product] Describe[Resource] ... | jq -r '.path.to.status')
#   [ "$STATUS" = "Running" ] && break
#   sleep 5
# done

# Or use aliyun --waiter (if available for this product):
# aliyun [product] Describe[Resource] ... \
#   --waiter expr='[Resource][0].Status' to=Running timeout=300 interval=5

# Or use --output with JMESPath for extraction:
# aliyun [product] Describe[Resource] ... \
#   --output cols=Status rows=[Resource][].Status
```

3. On success, report `{{output.resource_id}}` and key fields to the user.
4. On terminal failure, go to **Failure Recovery**.

#### Failure Recovery

| Error pattern (from API/SDK or parsed CLI JSON) | Max retries | Backoff | Agent Action | UX Feedback |
|------------------------------|-------------|---------|--------------|-------------|
| `InvalidParameter` / 400 invalid input | 0–1 | — | Fix args from OpenAPI; retry once if safe | `[ERROR] InvalidParameter: The request parameter is invalid. What happened: One or more parameters do not meet the API specification. How to fix: Check the parameter against OpenAPI docs and retry. Next step: Review the parameter table above.` |
| `QuotaExceeded` / `InstanceQuota不足` | 0 | — | HALT | `[ERROR] QuotaExceeded: Resource quota limit reached. What happened: Your account has reached the maximum allowed number of this resource type. How to fix: Delete unused resources or request a quota increase. Next step: Contact support or delete unused resources.` |
| `InsufficientBalance` / `余额不足` | 0 | — | HALT | `[ERROR] InsufficientBalance: Account balance insufficient. What happened: Your account does not have enough balance to complete this operation. How to fix: Recharge your account. Next step: Go to Alibaba Cloud billing console to recharge.` |
| `ResourceAlreadyExists` / `InstanceAlreadyExists` | 0 | — | Ask reuse vs new name | `[ERROR] ResourceAlreadyExists: A resource with this name already exists. What happened: The specified resource name is already in use. How to fix: Use a different name or reuse the existing resource. Next step: Choose a unique name or describe the existing resource.` |
| Throttling / 429 / `Throttling` | 3 | exponential | Back off; respect `Retry-After` if present | `⚠️ Rate limit reached. Retrying in {backoff}s... (Attempt {current}/{max})` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with correlation id (RequestId) if any | `[ERROR] InternalError: Server-side error occurred. What happened: Alibaba Cloud encountered an internal error processing your request. How to fix: Retry the operation. If it persists, escalate with RequestId. Next step: Retry now or escalate with RequestId: {RequestId}.` |

### Operation: Describe [Resource]

#### Execution

Use the SDK **describe** or **get** API matching OpenAPI. When **`cli_applicability`** is `cli-first` / `dual-path` / `cli-only`, also document the equivalent `aliyun [product] Describe[Resource] ...`, passing `{{user.resource_id}}` and region.

```bash
# CLI — plain JSON (default output format)
aliyun [product] Describe[Resource] --RegionId cn-hangzhou --[IdName] "{{user.resource_id}}"

# CLI — extract specific fields with JMESPath
aliyun [product] Describe[Resource] --RegionId cn-hangzhou --[IdName] "{{user.resource_id}}" \
  --output cols=[Field1],[Field2] rows=[Resource][].[Field1,Field2]
```

#### Present to User

| Field | Path (example) | Notes |
|-------|----------------|-------|
| ID | from describe result | Plain text |
| Name | from describe result | Plain text |
| Status | from describe result | Human-readable state |
| Created time | from describe result | Format ISO per API |

### Operation: Delete [Resource]

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of `{{user.resource_name}}` (`{{user.resource_id}}`).
- **MUST NOT** proceed without clear user assent.

#### Execution

Call delete API per OpenAPI (skip for `cli-only`). When **`cli_applicability`** is `cli-first` / `dual-path`, also document the `aliyun` delete subcommand; capture `requestId`, success flag, or error per **verified** output shape for **each** path.

#### Post-execution Validation

Poll describe (or head/get) until **404**, **NotFound**, or status indicates deleted—per API semantics—within **max wait**.

### Operation: Backup [Resource]

> **Stability Pillar:** Following Alibaba Cloud Well-Architected Framework §面向风险的应急快恢 (Emergency Recovery), every writable skill MUST document backup and recovery operations.

#### When to Use
- Before any destructive operation (delete, resize, engine upgrade)
- Scheduled per organizational RPO requirements
- Migration or region transfer prerequisites

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Resource exists | Describe[Resource] with ID | Resource in stable state (Running/Available) | HALT — cannot backup non-existent or transitioning resource |
| Backup window | Check current time vs maintenance window | Within allowed backup window | Warn user; proceed with confirmation |
| Storage quota | Describe quota for snapshots/backups | Sufficient backup storage | HALT — user must free space or raise quota |
| Existing backup | DescribeBackups with resource filter | None or list existing backups | Inform user of existing backups |

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Create backup/snapshot (adjust per product API)
aliyun [product] Create[Backup/Snapshot] \
  --[ResourceIdName] "{{user.resource_id}}" \
  --[BackupName] "auto-backup-$(date +%Y%m%d-%H%M%S)"

# For cross-region backup (if supported)
aliyun [product] Copy[Snapshot/Backup] \
  --[SourceIdName] "{{output.backup_id}}" \
  --DestRegionId "{{user.dest_region}}"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
// main.go — backup operation
request := &[product].Create[Backup/Snapshot]Request{
    [ResourceIdName]: tea.String(os.Getenv("[RESOURCE_ID]")),
    [BackupName]:     tea.String("auto-backup-" + time.Now().Format("20060102-150405")),
}

response, err := client.Create[Backup/Snapshot](request)
if err != nil {
    panic(err)
}
fmt.Println(tea.ToString(response.Body))
```

#### Post-execution Validation

1. Capture `{{output.backup_id}}` from response
2. Poll backup status until terminal state (`Success`/`Completed`):

```bash
# Poll backup status
aliyun [product] Describe[Backups/Snapshots] \
  --[BackupIdName] "{{output.backup_id}}" \
  --waiter expr='[Backups/Snapshots].[0].Status' to=Success timeout=600 interval=10
```

3. Record backup metadata: creation time, size, retention policy

#### Failure Recovery

| Error pattern | Max retries | Agent Action | UX Feedback |
|--------------|-------------|--------------|-------------|
| `BackupInProgress` / `OperationConflict` | 3, 30s backoff | Wait for conflicting operation; retry | `⚠️ Another operation is in progress. Retrying after completion...` |
| `QuotaExceeded.Backup` | 0 | HALT | `[ERROR] Backup quota exceeded. How to fix: Delete old backups or raise quota.` |
| `InvalidResourceStatus` | 0 | HALT | `[ERROR] Resource not in a backup-ready state. How to fix: Wait for resource to reach stable state.` |

---

### Operation: Restore from Backup

> **Stability Pillar — Emergency Recovery:** Follow the Phase 1 → Phase 2 → Phase 3 runbook structure per `well-architected-assessment.md` §2.2.3.

#### Pre-flight (Safety Gate)

- **MUST** warn user: restore overwrites current data; suggest pre-restore backup
- **MUST** confirm: target resource `{{user.resource_id}}`, backup source `{{user.backup_id}}`, expected data loss window

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Restore from backup (adjust per product API)
aliyun [product] Restore[Resource] \
  --[ResourceIdName] "{{user.resource_id}}" \
  --[BackupIdName] "{{user.backup_id}}"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
request := &[product].Restore[Resource]Request{
    [ResourceIdName]: tea.String(os.Getenv("RESOURCE_ID")),
    [BackupIdName]:   tea.String(os.Getenv("BACKUP_ID")),
}
```

#### Post-execution Validation

1. Poll restore operation until terminal state (same intervals as create)
2. **Recovery verification:** run connectivity check against restored resource
3. Verify data integrity: compare row counts, checksums, or product-specific validation
4. Document actual recovery time vs RTO target

#### Failure Recovery

| Error pattern | Agent Action | UX Feedback |
|--------------|--------------|-------------|
| `BackupNotFound` | HALT | `[ERROR] Backup not found. How to fix: Verify backup ID with DescribeBackups.` |
| `RestoreConflict` | Wait and retry | `⚠️ Resource has conflicting operation. Retrying...` |
| `DataIntegrityError` | HALT + suggest support | `[ERROR] Data integrity check failed post-restore. Escalate with RequestId.` |

## Prerequisites

1. **Install `aliyun` CLI** (primary execution path — static Go binary, no runtime dependencies):

   ```bash
   # Official installer (auto-detects OS and architecture)
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   
   # Or Homebrew (macOS)
   brew install aliyun-cli
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback — only needed if CLI does not support operation):

   ```bash
   # Check if Go exists
   if ! command -v go &> /dev/null; then
       # JIT download Go 1.24 (auto-detects OS and architecture)
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       
       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       
       # Set environment variables
       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOCACHE="/tmp/go-cache"
       export GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"  # China CDN mirror
   fi
   
   go version
   ```

   > Go version strategy: **JIT download Go 1.24+**, **Script compatibility Go 1.21+** (minimum).

3. **Configure Credentials** — Environment variables (recommended for Agent execution):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

   **Alternative — Interactive CLI Configuration:**
   ```bash
   aliyun configure
   ```

   **Alternative — Config File (`~/.aliyun/config.json`):**
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

4. **Verify Configuration**:
   ```bash
   # Quick validation (JSON output by default)
   aliyun ecs DescribeRegions
   ```

> **Security:** Never commit `.env` to version control (already in `.gitignore`). All credentials use `{{env.*}}` placeholders in generated Skills — never real values.

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md) (**required** when `cli_applicability: cli-first` or `dual-path`; omit for `sdk-only`; basic examples for `cli-only`)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Knowledge Base](references/knowledge-base.md) — fault pattern library (AIOps diagnostic skills)
- [Observability Integration](references/observability.md) — Metrics/Logs/Traces linkage (AIOps diagnostic skills)
- [Prompts Handbook](references/prompts.md) — common prompt templates (AIOps diagnostic skills)
- [User Experience Specification](references/user-experience-spec.md) — mandatory UX compliance reference
- [AIOps Best Practices](references/aiops-best-practices.md) — mandatory AIOps patterns for monitoring/diagnosis skills
- [Optimization Analysis](references/optimization-analysis.md) — three-dimensional optimization framework
- [Execution Environment Setup](references/execution-environment.md) — CLI install, Go JIT download, credential config, verification
- [CLI Behavioral Reference](references/cli-behavior.md) — verified `aliyun` CLI conventions (JSON output, env vars, invocation patterns)
- [Enhanced Self-Healing Framework](references/enhanced-self-healing-framework.md) — **MANDATORY** self-healing patterns for all installation flows
- [Well-Architected Assessment](references/well-architected-assessment.md) — **MANDATORY** Alibaba Cloud Well-Architected Framework five-pillar integration

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required APIs only.
- **Availability:** Multi-AZ or product-specific HA patterns per docs.
- **Cost:** Right-size resources; use product cost controls where applicable.

## Token Efficiency Guidelines (P0 — 强制)

Generated skills MUST follow these 6 rules. See meta-skill SKILL.md for detailed examples.

### TE-1: API Query > Static Tables
Use API commands instead of hardcoding version/port/quota tables.
```markdown
aliyun [product] Describe[Versions]
| Engine | Port |
|--------|------|
```
### TE-2: No docstrings in code
Inline comments only. No function-level docstring.
```go
// DO: inline comment only
func createResource() { ... }
```
### TE-3: Compact error tables
| Error Code | Agent Action |
|------------|-------------|
### TE-4: Centralized JSON paths
File-top comment block; one per resource type.
### TE-5: YAML anchors in example-config.yaml
Use `&dev` / `&prod` to eliminate repeated fields.
### TE-6: Eliminate cross-file duplicate flows
SKILL.md already has full flow, no Complete Workflow in config or SDK files.

---

# Appendix: Reference File Templates

## references/troubleshooting.md

```markdown
# Troubleshooting [Product Name]

## Common API Error Codes
| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| InvalidParameter | Request failed validation | Align body with OpenAPI |
| Forbidden.RAM | Insufficient RAM permissions | User adds RAM policy |
| InternalError | Server-side error | Retry with backoff; then HALT |

## Diagnostic Order
1. Describe resource by ID.
2. List related resources if API supports filters.
3. Check regional endpoint and `RegionId` consistency.
4. Verify CLI metadata coverage: `aliyun help [product]`
```

## references/api-sdk-usage.md

```markdown
# API & SDK — [Product Name]

## OpenAPI
- Spec: [link or path]
- Base path and version: …

## SDK Operations Map
| Goal | API operationId | SDK method (if known) |
|------|-----------------|------------------------|
| Create | … | … |
| Describe | … | … |

## Request / Response Notes
- Required fields: …
- Pagination: …
```

## references/cli-usage.md

```markdown
# CLI — [Product Name] (`aliyun`)

## Install and config
- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json` (JSON format).
- For sandbox environments, set env vars directly (preferred) or use `--config-path`.

## Conventions (agent execution)
- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are non-interactive by default
- Document **exact** JSON paths after verifying with a real invocation

## CLI vs API coverage gap
| Operation (API / SDK) | Available via `aliyun`? | Notes |
|------------------------|---------------------|-------|
| Create | yes / no | … |
| Describe | yes / no | … |

## Command map
| Goal | Example `aliyun` invocation | Notes |
|------|--------------------------|-------|
| Create | `aliyun [product] Create[Resource] --RegionId cn-hangzhou` | JSON output by default |
| Describe | `aliyun [product] Describe[Resource] --RegionId cn-hangzhou` | JSON output by default |
| Extract fields | `aliyun [product] Describe[Resource] --output cols=[Field] rows=[Resource][].[Field]` | JMESPath tabular mode |
| Poll state | `aliyun [product] Describe[Resource] --waiter expr='[Resource][0].Status' to=Running` | Waiter polling |
```

## references/monitoring.md

```markdown
# Monitoring [Product Name]

## Key Metrics (examples — replace with product namespaces)
- Metric A: `acs_[product]_[metric]`
- Metric B: `acs_[product]_[metric]`

## Alert Example (structure only)
```

## references/integration.md

````markdown
# Integration

## Environment Setup

**Primary path:** `aliyun` CLI (static Go binary, no runtime dependencies)

**Fallback path:** JIT Go SDK (dynamic script generation + `go run`)

### Go Runtime Bootstrap

If Agent Runtime lacks Go, JIT download from official source:

```bash
# Check Go runtime
if ! command -v go &> /dev/null; then
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    [ "$ARCH" = "x86_64" ] && ARCH="amd64"
    [ "$ARCH" = "aarch64" ] && ARCH="arm64"
    
    mkdir -p /tmp/go-runtime
    curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
    export PATH="/tmp/go-runtime/go/bin:$PATH"
    export GOPATH="/tmp/go-workspace"
    export GOCACHE="/tmp/go-cache"
fi

go version
```

> **Go version strategy:**
> - **JIT download:** Go 1.24+ (latest stable)
> - **Script compatibility:** Go 1.21+ (minimum)

### JIT Go SDK Workflow

1. **Initialize workspace:**
   ```bash
   mkdir -p /tmp/aliyun-sdk-workspace
   cd /tmp/aliyun-sdk-workspace
   go mod init sdk-script
   ```

2. **Get dependencies:**
   ```bash
   # Set proxy for China CDN mirror (faster download)
   export GOPROXY="https://goproxy.cn,direct"
   
   # Core dependencies
   go get github.com/alibabacloud-go/darabonba-openapi/v2/client
   go get github.com/alibabacloud-go/tea
   go get github.com/alibabacloud-go/tea-utils/v2/service
   
   # Product-specific SDK
   go get github.com/alibabacloud-go/[product]-[YYYYMMDD]/v[version]/client
   ```

3. **Generate script** (Agent dynamically creates operation-specific .go file)

4. **Execute:**
   ```bash
   go run ./main.go
   ```

### SDK Package Naming

| Product | Go SDK Package |
|---------|---------------|
| ECS | `github.com/alibabacloud-go/ecs-20140526/v4/client` |
| RDS | `github.com/alibabacloud-go/rds-20140815/v2/client` |
| PolarDB MySQL | `github.com/alibabacloud-go/polardb-20220530/v3/client` |
| VPC | `github.com/alibabacloud-go/vpc-20160428/v3/client` |
| OSS | `github.com/alibabacloud-go/oss-20210407/v3/client` |

> Find package names at: https://github.com/alibabacloud-go

## Environment Variable Loading (`.env` support)

Credentials can be sourced from multiple locations:

```
Shell env (highest) > `.env` file > aliyun config.json > defaults (lowest)
```

### `.env` File Format

```ini
# Alibaba Cloud credentials
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

- **Security**: `.env` MUST be in `.gitignore` — never commit credentials
- **Multiple clouds**: Use platform-specific prefixes
  ```ini
  ALIBABA_CLOUD_ACCESS_KEY_ID=...
  JDC_ACCESS_KEY=...
  AWS_ACCESS_KEY_ID=...
  ```

### Go `.env` Loading (optional)

```go
// main.go - optional .env loading via godotenv
package main

import (
    "os"
    "github.com/joho/godotenv"
)

func init() {
    godotenv.Load(".env") // Optional: load .env if present
}

func main() {
    ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
    sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    // ...
}
```

> Note: `.env` loading is optional. Shell environment variables are sufficient for Agent execution.

## Go SDK Script Template

```go
// main.go (single-file script template)
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    [product] "github.com/alibabacloud-go/[product]-[YYYYMMDD]/v[version]/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("[product].aliyuncs.com"),
    }
    
    client, err := [product].NewClient(config)
    if err != nil {
        panic(err)
    }
    
    // Operation-specific code (generated per OpenAPI)
    request := &[product].Describe[Resource]Request{
        RegionId: tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    
    response, err := client.Describe[Resource](request)
    if err != nil {
        panic(err)
    }
    
    fmt.Println(tea.ToString(response.Body))
}
```

> Use `os.Getenv("KEY")` for all credentials. Never hardcode secrets in scripts.
````

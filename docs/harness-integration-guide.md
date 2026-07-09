# Runtime Harness Integration Guide

> **Canonical name**: **Runtime Harness** — this repo's runtime wrapper framework (see [`runtime-harness-glossary.md`](runtime-harness-glossary.md)).
>
> **Legacy filenames**: `skillopt-lib.sh`, `*-skillopt-wrapper.sh`, `SKILLOPT_*` env vars remain as backward-compatible shims (Strategy B PR-9). Prefer `harness-lib.sh`, `*-harness-wrapper.sh`, `HARNESS_*`.
>
> **Canonical framework skill**: [`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md) — `harness-core-lib.sh`, `harness-paths.sh`, `harness_runtime.py`. Legacy [`alicloud-skillopt-ops`](../alicloud-skillopt-ops/SKILL.md) retains thin shims.
>
> **Not Microsoft SkillOpt**: [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt) (2026) trains **skill document text** offline. This guide covers **runtime CLI harness** behavior only (auto-repair, traces, metrics, Langfuse).

---

## Table of Contents

1. [What is Runtime Harness?](#1-what-is-runtime-harness)
2. [Integration Files Overview](#2-integration-files-overview)
3. [File 1: `skillopt-lib.sh` — Core Library (Engine)](#3-file-1-skillopt-libsh--core-library-engine)
4. [File 2: `skillopt-integration.md` — Documentation (Manual)](#4-file-2-skillopt-integrationmd--documentation-manual)
5. [File 3: `*-skillopt-wrapper.sh` — Wrapper (Remote)](#5-file-3--skillopt-wrappersh--wrapper-remote)
6. [File 4: `test-skillopt-backward-compatibility.sh` — Test (Checkup)](#6-file-4-test-skillopt-backward-compatibilitysh--test-checkup)
7. [Complete Workflow](#7-complete-workflow)
8. [How to Add Runtime Harness to a New Skill](#8-how-to-add-runtime-harness-to-a-new-skill)
9. [Quality Standards](#9-quality-standards)
10. [Environment Variables & Enable Flags](#10-environment-variables--enable-flags)
11. [Multi-Skill Langfuse Session Testing](#11-multi-skill-langfuse-session-testing)

---

## 1. What is Runtime Harness?

Think of the Runtime Harness as an **auto-pilot for cloud CLI commands** (legacy log tag `[Product-SkillOpt]` may still appear):

| Without Runtime Harness | With Runtime Harness |
|-----------------|---------------|
| Command fails → you diagnose manually → fix and retry | Command fails → SkillOpt diagnoses → auto-repairs → retries |
| Repeated errors waste time | Errors are learned from, parameters auto-tuned |
| No memory of what went wrong | Runtime metrics persist across sessions |

### What Runtime Harness is NOT

- ❌ Not a replacement for proper error handling in scripts
- ❌ Not a magic bullet for all API errors (only handles known patterns with configured repairs)
- ❌ Not an AI model — it's a rule-based repair framework with dynamic parameter tuning

---

## 2. Integration Files Overview

Each `alicloud-*-ops` skill can include **4 optional files** that work together:

```
alicloud-[product]-ops/
├── references/
│   └── skillopt-integration.md      ← 📖 Manual — explains what it does
├── scripts/
│   ├── harness-lib.sh               ← 🔧 Overlay (canonical; skillopt-lib.sh = legacy symlink)
│   ├── skillopt-lib.sh              ← legacy symlink → harness-lib.sh (PR-9)
│   └── [product]-harness-wrapper.sh ← 🎮 Preferred entry (PR-6)
│   └── [product]-skillopt-wrapper.sh← legacy shim → harness wrapper
└── test-skillopt-backward-compatibility.sh ← ✅ Checkup — ensures nothing is broken

alicloud-runtime-harness-ops/        ← 🏗️ Shared framework (canonical, PR-8)
├── scripts/
│   ├── harness-core-lib.sh          ← init, logging, metrics, Langfuse, circuit breaker
│   ├── harness-paths.sh             ← resolves harness_runtime.py path
│   └── harness_runtime.py           ← Langfuse span-create (single copy)
├── references/                      ← framework docs (migrated PR-9c)
└── test-harness-integration.sh

alicloud-skillopt-ops/               ← legacy alias (PR-8 shims only)
├── scripts/skillopt-{core-lib,paths}.sh → delegate to runtime-harness-ops
└── test-skillopt-integration.sh     → delegates to test-harness-integration.sh
```

> **Directory rule (P0)**: `harness-lib.sh` / `skillopt-lib.sh` MUST live under `scripts/`, never `references/`.

### File Responsibility Matrix

| File | What | Audience | When to Read |
|------|------|----------|-------------|
| `skillopt-lib.sh` | Bash functions that auto-repair errors and optimize params | Runtime (sourced by wrapper or agent) | At execution time |
| `skillopt-integration.md` | Human/agent-readable documentation | Agents reading the skill | During skill loading or when troubleshooting |
| `*-wrapper.sh` | Thin entry-point script | CLI users and automated workflows | When invoking commands through SkillOpt |
| `test-*.sh` | Automated test suite | CI/CD and manual verification | After integration or modification |

### Complete Skills (current)

**39 product skills** have the full 4-file integration (lib overlay + doc + test + wrapper).

**Shared framework (canonical)**: [`alicloud-runtime-harness-ops`](../alicloud-runtime-harness-ops/SKILL.md) — `harness-core-lib.sh`, `harness-paths.sh`, `harness_runtime.py`. Product `scripts/harness-lib.sh` files are **thin overlays** that source the shared core. Legacy [`alicloud-skillopt-ops`](../alicloud-skillopt-ops/SKILL.md) retains shims.

ack, ask, actiontrail, alb, advisor, agentrun, bailian, billing, cen, cms, das, dts, eci, ecs, eip, elasticsearch, ess, fc, kms, mongodb, nas, nat, oss, polar-mysql, polar-oracle, polar-postgresql, pts, ram, rds, redis, resourcemanager, sas, slb, sls, sms, terraform, voice, vpc, waf

### GCL Runner (full 4/4 — Python entrypoint)

`alicloud-gcl-runner-ops` has full SkillOpt integration; wrapper invokes `python3 scripts/gcl_runner.py` (not `aliyun` CLI). See [`alicloud-gcl-runner-ops/references/skillopt-integration.md`](../alicloud-gcl-runner-ops/references/skillopt-integration.md).

---

## 3. File 1: `skillopt-lib.sh` — Core Library (Engine)

### Purpose

A bash function library (not a standalone script) that provides self-repair and dynamic optimization. It is `source`d (loaded) by other scripts, never executed directly.

### File Structure (2026-06+ shared architecture)

Product `harness-lib.sh` (or legacy `skillopt-lib.sh` symlink) is a **thin overlay** (~150–200 lines of product-specific repair + `skillopt_wrap`). Shared logic lives in `alicloud-runtime-harness-ops/scripts/harness-core-lib.sh`.

```
┌─────────────────────────────────────────────────────────────┐
│  alicloud-runtime-harness-ops/scripts/harness-core-lib.sh   │
├─────────────────────────────────────────────────────────────┤
│  skillopt_init()          — flags, .env, enable precedence  │
│  skillopt_log()           — text / JSON logs                  │
│  Langfuse tracing         — session, trace, span, ingest    │
│  skillopt_run_aliyun()    — capture stdout for traces       │
│  skillopt_wrap()          — orchestration (init/trace/repair)│
│  skillopt_report()        — Markdown ops summary             │
│  Circuit breaker + metrics                                    │
└─────────────────────────────────────────────────────────────┘
          ▲ source
┌─────────┴───────────────────────────────────────────────────┐
│  alicloud-[product]-ops/scripts/harness-lib.sh (overlay)    │
├─────────────────────────────────────────────────────────────┤
│  skillopt_repair_error()    — product error patterns        │
│  skillopt_optimize_params() — product tuning                │
│  skillopt_check_and_poll_empty() — optional (cms group)     │
└─────────────────────────────────────────────────────────────┘
```

Report title uses overlay `SKILLOPT_LOG_LABEL` (e.g. `ECS-SkillOpt` → `ECS SkillOpt 运营摘要`).

### 3.1 Enable Flags (two orthogonal switches)

| Variable | Controls | Default |
|----------|----------|---------|
| `SKILLOPT_ENABLED` | Self-repair, param optimization, circuit breaker | `false` |
| `SKILLOPT_LANGFUSE_ENABLED` | Remote Langfuse HTTP ingestion | `false` |

The two switches are **orthogonal** — either, both, or neither may be `true`:

| `SKILLOPT_ENABLED` | `SKILLOPT_LANGFUSE_ENABLED` | Runtime behavior |
|:------------------:|:-----------------------------:|------------------|
| `false` | `false` | Single `aliyun` call + **always** local trace JSON + Layer 1 `memory_store_lite`; allowlisted failure → Layer 2 plan **B** |
| `true` | `false` | Full repair/optimize/CB loop + local trace + Layer 1; allowlisted failure → Layer 2 plan **B** |
| `false` | `true` | Single `aliyun` call + local trace + Langfuse remote mirror |
| `true` | `true` | Full repair loop + local trace + Langfuse remote mirror |

**`SKILLOPT_ENABLED` precedence** (highest first): `--skillopt-disable` → `--skillopt-enable` → `SKILLOPT_ENABLED` env / `.env` → `false`.

**`SKILLOPT_LANGFUSE_ENABLED` precedence** (highest first): `--skillopt-langfuse-disable` → `--skillopt-langfuse-enable` → `SKILLOPT_LANGFUSE_ENABLED` env / `.env` → `false`.

When `SKILLOPT_LANGFUSE_ENABLED=true`, `skillopt_init()` **requires** `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY`; missing vars fail fast with `ERROR` (no silent no-op).

Local trace files (`${SKILLS_DIR}/.runtime/traces/<skill-tag>/`) are **always** written on every wrapper invocation (Local-first canonical store). `SKILLOPT_LANGFUSE_ENABLED=true` mirrors the same trace to Langfuse HTTP; it does not gate local JSON creation.

Product overlays do **not** hardcode `SKILLOPT_ENABLED=false`; resolution happens in `skillopt_init()`.

```bash
# Option A: environment / .env (recommended for CI or long-running agents)
export SKILLOPT_ENABLED=true
./scripts/ecs-skillopt-wrapper.sh DescribeRegions --RegionId cn-hangzhou

# Option B: per-invocation CLI flag
./scripts/ecs-skillopt-wrapper.sh DescribeRegions --skillopt-enable --RegionId cn-hangzhou

# Observability only (no self-repair) — local trace always; add Langfuse mirror optionally
./scripts/ecs-skillopt-wrapper.sh DescribeRegions --skillopt-langfuse-enable --RegionId cn-hangzhou
export SKILLOPT_ENABLED=false
export SKILLOPT_LANGFUSE_ENABLED=true
./scripts/ecs-skillopt-wrapper.sh DescribeRegions --skillopt-langfuse-enable --RegionId cn-hangzhou
```

### 3.2 Other Global Variables

```bash
SKILLOPT_LOG_FILE="${SKILLS_DIR}/.runtime/logs/alicloud-ecs-ops/ecs-skillopt-YYYYMMDD.log"
SKILLOPT_RETRIES=3
SKILLOPT_RUNTIME_DATA="${SKILLS_DIR}/.runtime/metrics/alicloud-ecs-ops/ecs-skillopt-runtime.json"
SKILLOPT_SESSION_ID=""                    # explicit multi-skill session
SKILLOPT_LANGFUSE_ENABLED=false           # remote Langfuse ingest
```


### 3.3 `skillopt_log()` — Structured Logging

```
[2026-06-16T10:30:00+0800] [ECS-SkillOpt] SkillOpt initialized: enabled=true, log_file=...
[2026-06-16T10:30:01+0800] [ECS-SkillOpt] Attempting to repair error: Throttling.User for command: ecs DescribeInstances
[2026-06-16T10:30:03+0800] [ECS-SkillOpt] Successfully repaired throttling error
```

### 3.4 `skillopt_repair_error()` — Auto-Repair (Core)

This is the heart of SkillOpt. It receives the error code, the original command, and the parameters, then attempts repair.

#### How it works

```
Error occurs → Extract error code (e.g. "Throttling.User")
                      ↓
            ┌── case "$error_code" ──┐
            │                         │
   "Throttling.User"       "InvalidParameter"    ...  (6-7 patterns per skill)
            │                         │
   ┌────────▼────────┐     ┌──────────▼──────────┐
   │ Apply backoff   │     │ Fix JSON syntax     │
   │ Retry with      │     │ Validate params     │
   │ adjusted period │     │ Retry with fixed    │
   └────────┬────────┘     └──────────┬──────────┘
            │                         │
            └──────────┬──────────────┘
                       ▼
              Was repair successful?
              ├─ Yes → return 0 (success)
              └─ No  → return 1 (failure)
```

#### Supported Error Patterns (same across all skills, with product-specific details)

| Error Code | Meaning | Auto-Repair Strategy | Product-Specific |
|-----------|---------|---------------------|-----------------|
| `Throttling.User` | API rate limit hit | Add `--Period 300`, exponential backoff retry | Same across all |
| `InvalidParameter` / `InvalidJSON` | Bad parameter format | Fix JSON syntax, validate param types | JSON param names differ per product |
| `*NotFound` / `ResourceNotFound` | Resource doesn't exist | Call Describe* API to verify, suggest correct region | Each product checks its own resource |
| `Forbidden` / `NoPermission` | No access rights | Output correct RAM policy template | Product name in policy differs (`ecs:*`, `dds:*`, `cs:*`...) |
| `ConnectionTimeout` | Network issue | Add `--Timeout 30`, retry | Same across all |
| `QuotaExceeded` | Resource quota full | Output cleanup suggestion | Quota type differs per product |

#### Product-Specific JSON Parameters (examples)

Each skill handles the JSON parameters its product actually uses:

| Skill | JSON Parameters Checked |
|-------|----------------------|
| ecs | `InstanceIds`, `SecurityGroupIds`, `Tags`, `IpAddress`, `SecurityIpList`, `DiskIds` |
| oss | `BucketPolicy`, `LifecycleRules`, `RefererConfig`, `CorsRule`, `ReplicationConfiguration`, `Metadata`, `Tags` |
| slb | `BackendServers`, `AclEntrys`, `RuleList`, `ListenerPorts`, `SecurityIpList` |
| vpc | `CidrBlock`, `SecurityIpList`, `RouteEntrys`, `Ipv6CidrBlock`, `NatGatewaySpec` |
| mongodb | `InstanceIds`, `SecurityIpList`, `Tag`, `DBInstanceIds` |
| rds | `InstanceIds`, `SecurityIpList`, `DBInstanceIds`, `Tag` |
| redis | `SecurityIps`, `InstanceIds`, `MonitorKeys` |
| ack | `ClusterIds`, `tags`, `instance_specs`, `security_group_ids` |
| cms | `Dimensions` (custom repair with `jq` validation) |

### 3.5 `skillopt_update_runtime()` — Metrics Tracking

Persists runtime statistics to a JSON file so SkillOpt can adapt based on historical data:

```json
{
  "last_error": "Throttling.User",
  "last_success": "0",
  "last_updated": "1718526600",
  "total_repairs": 5,
  "error_rate": 3.2,
  "query_count": 150
}
```

### 3.6 `skillopt_optimize_config()` — Pre-Execution Tuning

Before the command runs, checks runtime metrics and adjusts parameters:

- **Error rate > 5%**: Increase retry count by 1
- **Query count > 1000**: Increase `--Period` to 300s to reduce API call frequency

This is **proactive optimization** — preventing failures before they happen rather than reacting after the fact.

### 3.7 `skillopt_wrap()` — Main Entry Point

The function that orchestrates everything:

```bash
skillopt_wrap() {
    skillopt_init "$@"              # Parse --skillopt-* flags
    params=$(skillopt_optimize ...)  # Pre-execution tuning
    aliyun $command $params          # Execute the actual command
    if failed:
        error_code=$(extract error)
        skillopt_repair_error(...)   # Attempt repair
    skillopt_update_runtime(...)     # Record metrics
}
```

### 3.8 `export -f` — Function Export

The last line exports all functions so they're available in child shells:

```bash
export -f skillopt_init skillopt_log skillopt_repair_error skillopt_update_runtime skillopt_optimize_config skillopt_wrap
```

---

## 4. File 2: `skillopt-integration.md` — Documentation (Manual)

### Purpose

A human/agent-readable document explaining what SkillOpt does for this specific product skill. It serves as the "user manual" — read during skill loading or troubleshooting.

### Required Sections

| Section | Content | Purpose |
|---------|---------|---------|
| **Overview** | What SkillOpt is and why it's integrated | Quick understanding |
| **Dual Optimization** | Static pre-execution + dynamic runtime optimization | Explain both optimization modes |
| **Self-Repair Capabilities** | Table of error codes, repair strategies, and product-specific details | Quick reference for what errors can be auto-fixed |
| **Usage** | How to enable/disable SkillOpt, wrapper script examples | Practical instructions |
| **Implementation Details** | Workflow diagrams for self-repair and optimization | Deep understanding |

### Structure Template

```markdown
# Runtime Harness Integration for alicloud-[product]-ops

## Overview

## Dual Optimization Capabilities

### 1. Static Pre-Execution Optimization
- Parameter Format Fixing
- Default Parameter Completion
- Pre-flight Resource Validation
- Permission Pre-check

### 2. Dynamic Runtime Optimization
- Rate Limiting Adaptation
- Error Rate Driven Tuning
- Query Volume Optimization
- Adaptive Retry Strategy

## Self-Repair Capabilities

### Supported Error Repair Scenarios
1. **Throttling / Rate Limiting** (`Throttling.User`)
2. **Invalid Parameters** (`InvalidParameter` / `InvalidJSON`)
3. **Instance Not Found** (`InstanceNotFound` / `ResourceNotFound`)
4. **Permission Errors** (`Forbidden` / `NoPermission`)
5. **Connection Timeout** (`ConnectionTimeout` / `ConnectTimeout`)
6. **Quota Exceeded** (`QuotaExceeded`)

## Usage

### Enabling Runtime Harness
### Disabling Runtime Harness
### Viewing Optimization History

## Implementation Details
## Reference
```

---

## 5. File 3: `*-skillopt-wrapper.sh` — Wrapper (Remote)

### Purpose

A thin entry-point script so users don't need to manually `source` the library. It's the **one-button interface** to SkillOpt.

### Content (standardized template, 17-18 lines)

```bash
#!/bin/bash
# [Product] SkillOpt Wrapper - Integrates SkillOpt into aliyun [product] commands

set -euo pipefail

# Load SkillOpt library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/skillopt-lib.sh"

# Main execution
if [ "${#}" -lt 1 ]; then
    echo "Usage: $0 <[product]-command> [parameters]"
    echo "Example: $0 DescribeInstances --RegionId cn-hangzhou"
    exit 1
fi

# Wrap the command with SkillOpt
skillopt_wrap "[product] $@"
```

The only difference between skills is the **product prefix** (e.g. `ecs`, `mongodb`, `cs` for ACK).

### Usage Example

```bash
# Without wrapper:
source alicloud-ecs-ops/scripts/skillopt-lib.sh && skillopt_wrap ecs DescribeInstances

# With wrapper (much simpler):
alicloud-ecs-ops/scripts/ecs-skillopt-wrapper.sh DescribeInstances --RegionId cn-hangzhou
```

---

## 6. File 4: `test-skillopt-backward-compatibility.sh` — Test (Checkup)

### Purpose

An automated test script that verifies SkillOpt integration **doesn't break existing functionality**. Run after any skillopt changes or before committing.

### Test Structure (5 tests)

```bash
Test 1: Native DescribeInstances command...            ✓
  → Verifies the original aliyun CLI command still works unchanged

Test 2: SKILLOPT_ENABLED env + wrapper...               ✓
  → export SKILLOPT_ENABLED=true; wrapper without --skillopt-enable flag

Test 3: Wrapper script exists...                        ✓

Test 4: SkillOpt core library exists...                 ✓
  → Overlay sources alicloud-skillopt-ops shared core (oss: shared runtime path check)
```

### Running Tests

```bash
cd alicloud-ecs-ops
bash test-skillopt-backward-compatibility.sh
# Output:
# Testing backward compatibility of alicloud-ecs-ops with SkillOpt integration
# =====================================================================
# Test 1: Original DescribeInstances command... ✓ Success
# Test 2: DescribeInstances with SkillOpt flags... ✓ Success
# Test 3: Wrapper script exists and is executable... ✓ Success
# Test 4: SkillOpt core library exists... ✓ Success
# Test 5: SkillOpt integration documentation exists... ✓ Success
# =====================================================================
```

### Test Count by Skill

| Skill | Tests | Notes |
|-------|-------|-------|
| cms | 71 | Full suite (flags, repair, CB, Langfuse stubs) |
| ecs, redis, rds, slb | 4 | Native CLI + env-enabled wrapper |
| oss | 7 | Includes shared `skillopt_runtime.py` path resolution |

**Cross-skill E2E**: [`scripts/test-multi-skill-session.sh`](../scripts/test-multi-skill-session.sh) — see [§11](#11-multi-skill-langfuse-session-testing).

---

## 7. Complete Workflow

### End-to-End Flow

```
User invokes command
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  skillopt_wrap "[product] DescribeInstances --RegionId ..."      │
│                                                                  │
│  ① skillopt_init                                                │
│     → Parse --skillopt-enable/--skillopt-disable/--skillopt-*   │
│     → Strip SkillOpt flags from argument list                   │
│     → Create log directory                                       │
│                                                                  │
│  ② skillopt_optimize_config                                     │
│     → Read runtime metrics from JSON                            │
│     → If error_rate > 5%: increase retry count                  │
│     → If query_count > 1000: increase Period to 300s            │
│                                                                  │
│  ③ Execute: aliyun [product] DescribeInstances ...              │
│                                                                  │
│  ┌─────── Success? ────────┐                                    │
│  │                         │                                    │
│  ✅ Yes                    ❌ No                                │
│  │                         │                                    │
│  │                  skillopt_repair_error                        │
│  │                    → Match error code                        │
│  │                    → Apply product-specific repair           │
│  │                    → Retry with adjusted params              │
│  │                         │                                    │
│  │                  ┌──────┴──────┐                             │
│  │                  │             │                             │
│  │             ✅ Fixed      ❌ Still broken                    │
│  │                             │                                │
│  │                    Return original error                     │
│  │                         │                                    │
│  └─────────────────────────┘                                    │
│                                                                  │
│  ④ skillopt_update_runtime                                      │
│     → Record error code, success/failure, timestamp             │
│     → Increment total_repairs counter                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
   Return exit code to caller
```

### Log Output Example

```
[2026-06-16T10:30:00+0800] [ECS-SkillOpt] SkillOpt initialized: enabled=true
[2026-06-16T10:30:00+0800] [ECS-SkillOpt] Running dynamic configuration optimization
[2026-06-16T10:30:00+0800] [ECS-SkillOpt] Executing: aliyun ecs DescribeInstances ...
[2026-06-16T10:30:01+0800] [ECS-SkillOpt] Command failed with exit code 1
[2026-06-16T10:30:01+0800] [ECS-SkillOpt] Detected error code: Throttling.User
[2026-06-16T10:30:01+0800] [ECS-SkillOpt] Attempting to repair: Throttling.User
[2026-06-16T10:30:01+0800] [ECS-SkillOpt] Applying exponential backoff, adjusting period to 300
[2026-06-16T10:30:01+0800] [ECS-SkillOpt] Executing: aliyun ecs DescribeInstances --Period 300 --retries 3
[2026-06-16T10:30:03+0800] [ECS-SkillOpt] Successfully repaired throttling error
[2026-06-16T10:30:03+0800] [ECS-SkillOpt] Updated runtime metrics
```

---

## 8. How to Add Runtime Harness to a New Skill

### Prerequisites

Before adding SkillOpt to a skill, confirm:
- The skill uses `aliyun <product>` CLI commands
- The product has documented API error codes (at least 5-6 common ones)
- You have access to test with the product's CLI

### Step-by-Step

#### Step 1: Create `scripts/skillopt-lib.sh`

**Option A — generator (recommended for new skills):**

```bash
.scripts/gen-skillopt.sh alicloud-mongodb-ops MongoDB dds MongoDB 'dds:*' \
  'InstanceIds SecurityIpList Tag DBInstanceIds' '' DescribeRegions \
  'ResourceNotFound|InstanceNotFound' QuotaExceeded
```

Emits overlay stub + wrapper + backward-compat test + `references/skillopt-integration.md`. The lib sources `alicloud-skillopt-ops` shared core (no local `skillopt_wrap`).

**Option B — manual copy:**

1. Copy overlay from `alicloud-ecs-ops/scripts/skillopt-lib.sh` (sources `alicloud-skillopt-ops` shared core)
2. Replace product-specific values:

| What to Change | Example: ECS → MongoDB |
|---------------|----------------------|
| File header comment | `ECS` → `MongoDB` |
| Log prefix tag | `[ECS-SkillOpt]` → `[MongoDB-SkillOpt]` |
| Log file name | `ecs-skillopt-` → `mongodb-skillopt-` |
| Runtime file name | `ecs-skillopt-runtime` → `mongodb-skillopt-runtime` |
| JSON parameter list | `InstanceIds SecurityGroupIds Tags` → `InstanceIds SecurityIpList Tag DBInstanceIds` |
| Resource check API | `aliyun ecs DescribeInstances` → `aliyun dds DescribeDBInstances` |
| RAM policy action | `ecs:*` → `dds:*` |
| Error code patterns | `InstanceNotFound SecurityGroupNotFound` → `InstanceNotFound` |
| Wrapper product prefix | `ecs` → `mongodb` |

#### Step 2: Create `references/skillopt-integration.md`

1. Copy from an existing skill's integration doc
2. Replace product name throughout the document
3. Update product-specific error scenarios and JSON parameter examples
4. Update the API documentation link

#### Step 3: Create `scripts/[product]-skillopt-wrapper.sh`

Copy the 18-line template, changing:
- Comment header
- Usage examples
- `skillopt_wrap "[product] $@"` prefix

#### Step 4: Create `test-skillopt-backward-compatibility.sh`

Copy the 50-line test template, changing:
- Product name in comments
- CLI command (`DescribeInstances` → product-specific Describe*)
- Wrapper script filename
- Test assertions

#### Step 5: Make scripts executable

```bash
chmod +x scripts/[product]-skillopt-wrapper.sh
chmod +x test-skillopt-backward-compatibility.sh
```

### Verification Checklist

```markdown
- [ ] `skillopt-lib.sh` has correct product name, log prefix, and error codes
- [ ] `skillopt-lib.sh` JSON parameter list matches product API docs
- [ ] `skillopt-lib.sh` resource verification API exists for the product
- [ ] `skillopt-lib.sh` RAM policy action matches product
- [ ] `skillopt-integration.md` has all required sections
- [ ] `*-wrapper.sh` has correct product prefix in `skillopt_wrap` call
- [ ] Wrapper and test scripts have executable permissions
- [ ] `test-*.sh` passes all 5 tests (or minimum 3 for partial integration)
- [ ] Original CLI commands still work (backward compatibility verified)
```

---

## 9. Quality Standards

### Mandatory Requirements

| # | Rule | Severity | Description |
|---|------|----------|-------------|
| Q1 | Product-specific naming | P0 | All file names, log prefixes, and variables must use the product name, not generic |
| Q2 | Working resource verification | P0 | `skillopt_repair_error` must call a real Describe* API for the product, not a placeholder |
| Q3 | Correct RAM policy | P0 | The RAM policy template in `Forbidden` handler must use the correct product action prefix |
| Q4 | Backward compatibility | P0 | Test script must verify native CLI commands are unaffected |
| Q5 | Wrapper must be executable | P1 | `chmod +x` applied, shebang line present |
| Q6 | Integration doc completeness | P1 | All required sections present (Overview, Dual Optimization, Self-Repair, Usage, Workflow) |
| Q7 | No escaped quotes | P0 | All scripts must use real `"` not `\"` (bash syntax error otherwise) |
| Q8 | Overlay sources shared core | P0 | Product `skillopt-lib.sh` must `source` `alicloud-skillopt-ops/scripts/skillopt-core-lib.sh`; no local `skillopt_runtime.py` |

### Minimum Integration Level

For a skill to be considered "SkillOpt integrated":

1. ✅ `scripts/skillopt-lib.sh` exists with product-specific error handling
2. ✅ `references/skillopt-integration.md` exists with product-specific documentation
3. ✅ `scripts/[product]-skillopt-wrapper.sh` exists and is executable
4. ✅ `test-skillopt-backward-compatibility.sh` exists and passes

### File Size Reference (healthy files)

| File | Expected Size |
|------|-------------|
| `skillopt-lib.sh` (overlay) | ~150–600 lines (product repair + wrap) |
| `alicloud-skillopt-ops/scripts/skillopt-core-lib.sh` | ~800 lines (shared) |
| `skillopt-integration.md` | 95-120 lines |
| `*-skillopt-wrapper.sh` | 17-40 lines |
| `test-skillopt-backward-compatibility.sh` | 15–70 lines |

---

## 10. Environment Variables & Enable Flags

Copy [`.env.example`](../.env.example) to `.env` (gitignored). Minimum for Langfuse multi-skill testing:

```bash
HARNESS_ENABLED=true
HARNESS_LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://your-langfuse-host
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
ALIBABA_CLOUD_ACCESS_KEY_ID=...
ALIBABA_CLOUD_ACCESS_KEY_SECRET=...
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
```

| Variable | Default | Purpose | CLI override |
|----------|---------|---------|--------------|
| `HARNESS_ENABLED` | `false` | Master switch: param optimization, auto-repair, circuit breaker | `--harness-enable` / `--harness-disable` |
| `HARNESS_LANGFUSE_ENABLED` | `false` | Remote Langfuse HTTP mirror only (orthogonal to repair; local trace always written) | `--harness-langfuse-enable` / `--harness-langfuse-disable` |
| `TRACE_KEEP_DAYS` | `7` | Local trace + session index TTL (same tier as logs) | `runtime_cleanup.py --traces-keep-days` |
| `HARNESS_SESSION_ID` | auto | Explicit shared session across skills in one agent task | `--harness-session-id` |
| `ALIYUN_SKILLS_ROOT` | — | Repo root when running wrappers outside skill directory | — |

> **PR-7**: User-facing docs use `HARNESS_*` / `--harness-*` only. Runtime still accepts legacy `SKILLOPT_*` env and `--skillopt-*` CLI for backward compatibility (`HARNESS_*` wins when both are set).

Canonical semantics and precedence: [§3.1](#31-enable-flags-two-orthogonal-switches). Trace design: [harness-session-trace-system-design.md](./harness-session-trace-system-design.md).

Runtime artifacts: `${SKILLS_DIR}/.runtime/traces/<skill-tag>/`, `${SKILLS_DIR}/.runtime/sessions/<skill-tag>/` (gitignored). Legacy `alicloud-*/.runtime/` deprecated.

---

## 11. Multi-Skill Langfuse Session Testing

Validates that **cms + ecs + oss** share one `HARNESS_SESSION_ID` and traces appear in Langfuse with correct skill tags.

```bash
# From repo root — requires .env with Langfuse + Alibaba Cloud credentials
./scripts/test-multi-skill-session.sh

# Local traces always written; --local skips Langfuse HTTP verification only
./scripts/test-multi-skill-session.sh --local
```

**Pass criteria (full mode, 11 checks)**:

1. Five read-only API scenarios return data (CMS×2, ECS×2, OSS×1)
2. Local trace JSON files exist under `${SKILLS_DIR}/.runtime/traces/<skill-tag>/`
3. Langfuse `GET /api/public/traces/{id}` returns matching `sessionId`
4. Trace names include `alicloud-cms-ops`, `alicloud-ecs-ops`, `alicloud-oss-ops`

Shared framework integration test: `alicloud-skillopt-ops/test-skillopt-integration.sh`.

Gray rollout (ACK/DAS/ALB/CEN): `scripts/test-langfuse-gray-skills.sh`.

### 15.6 Production-Grade Hardening Standard (Mandatory for Updates)

Through the hardening of `alicloud-cms-ops`, we established five critical robust execution rules for all SkillOpt core libraries (`skillopt-lib.sh`) and wrappers:

1. **Parameter Array Integrity (No Space-Delimited Strings)**:
 - *Issue*: Storing CLI parameters as flat space-separated strings (e.g., `params="$*"`) breaks argument slicing when parameters contain inner spaces (like JSON parameters `--Dimensions '[{"instanceId":"i-123"}]'`).
 - *Rule*: Always capture and pass parameters using shell arrays (`SKILLOPT_PARAMS` and `SKILLOPT_REMAINING`) or standard Bash array variables. Never serialize/deserialize arrays as space-separated strings.

2. **Double-Execution Side-Effect Protection**:
 - *Issue*: Blindly re-running failing commands via `err_output="$(aliyun $cmd $opt 2>&1)"` to extract the error code causes mutating commands (e.g., `Put*`, `Delete*`) to run twice, which is dangerous.
 - *Rule*: For mutating actions, **never** retry or auto-repair. Maintain a read-only list (`Describe*`, `List*`, `Get*`, `Query*`) using `skillopt_is_readonly_action()`. Run the API command exactly once, capturing stdout/stderr to a temporary file, and only proceed to repair if the action is read-only.

3. **Float Throttling Prevention (Retries Cap)**:
 - *Issue*: Dynamically incrementing `SKILLOPT_RETRIES` on high error rate without a boundary can lead to an infinite request storm, degrading cloud performance.
 - *Rule*: Put a strict hard cap on the dynamic optimization of retries (e.g., maximum 6 retries).

4. **Shell Strict Mode Compatibility (`set -u`)**:
 - *Issue*: In strict mode (`set -uo pipefail`), dereferencing empty arrays triggers a fatal interpreter crash (`unbound variable`).
 - *Rule*: Always expand optional/empty arrays using the safe expansion format: `${MY_ARRAY[@]+"${MY_ARRAY[@]}"}`.

5. **Standard Output Passthrough on Repair Success**:
 - *Issue*: Swallowing command output or failing to return the JSON response upon a successful repair prevents the calling agent or user from receiving the requested data.
 - *Rule*: Always capture the underlying `aliyun` command output and print the correct stdout/stderr payload on successful repairs.

### 15.7 Langfuse Tracing Integration Lessons Learned (Mandatory for Runtime Harness Updates)

When adding Langfuse tracing to remaining `alicloud-*-ops` skills, agents MUST follow these lessons learned from the `alicloud-cms-ops` + `alicloud-ecs-ops` integration. These rules prevent silent trace loss, broken wrappers, and false-negative multi-skill validation.

#### A. Required implementation checklist

| Check | Rule | Why |
|-------|------|-----|
| L1 | Set `SKILLOPT_SKILL_TAG` to the full skill name, e.g. `alicloud-cms-ops`, not `cms` or `_CLI_` | Langfuse trace names and metrics must identify the exact skill |
| L2 | Load `.env` safely with `while IFS= read -r line || [[ -n "$line" ]]` | `.env` may not end with newline; otherwise the last variable (often `LANGFUSE_SECRET_KEY`) is skipped |
| L3 | Do not override existing environment variables when loading `.env` | Explicit runtime env must win over file defaults |
| L4 | Validate `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` when `SKILLOPT_LANGFUSE_ENABLED=true` | Avoid silent no-op tracing |
| L5 | Support explicit `--skillopt-session-id` and propagate it across skills | Multi-skill workflows require a shared session |
| L6 | Trace name MUST include full skill tag: `${SKILLOPT_SKILL_TAG} ${product} ${action}` | UI filtering and cross-skill analysis depend on this |
| L7 | Include trace-level `input` and `output`, not only span-level data | Langfuse list view displays trace-level Input/Output columns |
| L8 | Truncate large outputs before reporting, and parse JSON output as JSON when possible | Prevent oversized payloads while preserving structured API responses |
| L9 | When Trace-level final judgment is failed/error, set Trace `metadata.trace_display_severity="ERROR"` and create a `skillopt.trace_judgement` observation with `level="ERROR"` and non-empty `statusMessage`; do not put the error only in metadata | Langfuse Trace retrieve API exposes `level/statusMessage` on observations, not Trace top-level fields |
| L10 | Wrap `export -f` with `if [ -n "$BASH_VERSION" ]; then ... fi` | zsh does not support Bash function export |
| L11 | Ensure all functions called by `skillopt_wrap()` exist in the target skill | Missing helpers such as `skillopt_cb_check` break wrappers after partial migration |

#### B. Langfuse Ingestion API payload requirements

Every event in `/api/public/ingestion` batch MUST include top-level `id`, `type`, and `timestamp`. Do not put `timestamp` only inside `body`.

Correct pattern:

```json
{
 "batch": [{
 "id": "trace-xxx",
 "type": "trace-create",
 "timestamp": "2026-06-17T10:00:00+0800",
 "body": {
 "id": "trace-xxx",
 "sessionId": "sess-xxx",
 "name": "alicloud-cms-ops cms DescribeMetricRuleList",
 "input": ["--PageSize", "3"],
 "output": {"Code": 200},
 "level": "DEFAULT",
 "statusMessage": "",
 "metadata": {"skill": "alicloud-cms-ops"}
 }
 }]
}
```

Common failure: HTTP `207` with per-item errors because top-level `id`/`timestamp` are missing. Always inspect the response body when debugging, not only the HTTP status.

**Trace-level error visibility rule**: if the final Trace judgment is failed/error, the Trace update MUST include `metadata.trace_display_severity="ERROR"`, and the ingestion flow MUST create a `span-create` observation named `skillopt.trace_judgement` with `level="ERROR"` and non-empty `statusMessage`. Keeping the error only in `metadata.status`, `metadata.error_code`, or `output` is insufficient because Langfuse UI will not surface the failure clearly.

#### C. Bash/JQ pitfalls found during integration

| Pitfall | Symptom | Fix |
|--------|---------|-----|
| Default metadata written as `\{\}` | `jq: invalid JSON text passed to --argjson` | Use `local metadata="${3:-{}}"` |
| Last `.env` line has no newline | `LANGFUSE_SECRET_KEY is not set` | Use `while read ... || [[ -n "$line" ]]` |
| `source .env` is not enough in wrapper scripts | Variables missing in child process | Explicitly export required env vars or load `.env` inside `skillopt_init()` |
| `export -f` under zsh | Shell errors during `source scripts/skillopt-lib.sh` | Guard with `if [ -n "$BASH_VERSION" ]` |
| Trace output sent as stringified JSON only | Langfuse Output is hard to read | Try `jq '.'` first, fallback to `jq -R '.'` |
| Failed trace only writes `metadata.status=failed` | Langfuse UI does not visibly mark the trace as failed | Set trace `metadata.trace_display_severity="ERROR"` and create `skillopt.trace_judgement` observation with `level="ERROR"` and non-empty `statusMessage` |
| Querying `/traces?limit=20` for validation | False negative when trace is not in first page | Validate by direct `/api/public/traces/{trace_id}` lookups |

#### D. Multi-skill Session ID validation standard

For validating whether multiple skills share one Session ID, do not rely on Langfuse list pagination. Use this flow:

1. Generate one explicit shared session, e.g. `SKILLOPT_SESSION_ID="sess-multi-skill-test-$(date +%s)"`.
2. Invoke each skill wrapper with `--skillopt-session-id "$SKILLOPT_SESSION_ID"`.
3. Read local trace files: `${SKILLS_DIR}/.runtime/traces/<skill-tag>/trace-${SKILLOPT_SESSION_ID}-*.json` (legacy: `alicloud-*/.runtime/traces/`).
4. For every local trace id, call `GET ${LANGFUSE_HOST}/api/public/traces/{trace_id}`.
5. Pass only if returned `sessionId` equals the shared session and trace names include at least two different full skill tags.

Reference validation script: [`scripts/test-multi-skill-session.sh`](../scripts/test-multi-skill-session.sh).

#### E. Required verification commands before claiming done

After adding Langfuse to any skill, run at minimum:

```bash
bash -n alicloud-<product>-ops/scripts/skillopt-lib.sh

cd alicloud-<product>-ops
source ../.env
export ALIBABA_CLOUD_ACCESS_KEY_ID ALIBABA_CLOUD_ACCESS_KEY_SECRET ALIBABA_CLOUD_REGION_ID \
 SKILLOPT_LANGFUSE_ENABLED LANGFUSE_HOST LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY
./scripts/<product>-skillopt-wrapper.sh <ReadOnlyAction> \
 --skillopt-enable \
 --skillopt-langfuse-enable \
 --skillopt-session-id sess-debug-$(date +%s) \
 <safe read-only params>
```

Then verify Langfuse directly by trace id. Do not claim success based only on local JSON files or wrapper exit code.

### 15.8 Wrapper-First Execution Rule (MANDATORY for all skills with wrapper scripts)

> **⛔ P0 GLOBAL PRE-EXECUTION INTERCEPT — applies before ANY tool call**
>
> When a user request involves any Alibaba Cloud product that has a known SkillOpt wrapper
> (currently: **oss, ecs, cms, rds, redis, slb, mongodb, vpc, ack**), the Agent MUST:
>
> 1. **First**: check whether the corresponding `scripts/*-skillopt-wrapper.sh` exists in the skill directory.
> 2. **If wrapper exists**: execute via wrapper — `cd alicloud-<product>-ops && ./scripts/<product>-skillopt-wrapper.sh <verb> [args]`.
> 3. **Only if wrapper is confirmed missing** (file not found / not executable): fall back to native `aliyun <product>` CLI.
>
> **This check MUST happen even when the skill is not explicitly loaded.** Direct `aliyun <product>` calls without
> first verifying wrapper absence are a **P0 violation** — regardless of how simple the operation appears.
>
> Failure pattern to avoid:
> ```bash
> # ❌ WRONG — bypasses wrapper without checking
> aliyun oss ls
>
> # ✅ CORRECT — wrapper first
> cd alicloud-oss-ops && ./scripts/oss-skillopt-wrapper.sh ls
> ```

Every `alicloud-*-ops` skill that has a `scripts/*-skillopt-wrapper.sh` wrapper script MUST enforce wrapper-first execution in its SKILL.md:

1. **Runtime Rules table**: Each SKILL.md MUST include a `## Runtime Rules` section with a `CLI path` row marked **MANDATORY** that instructs agents to always prefer the SkillOpt wrapper. Fallback to native `aliyun <product>` is permitted only when the wrapper is confirmed missing.
2. **Execution Flows global note**: The `## Execution Flows (Agent-Readable)` section MUST begin with a mandatory note block stating that all CLI examples should be executed via the wrapper, with fallback to native CLI only when the wrapper is unavailable.
3. **No silent bypass**: Agents MUST NOT silently bypass the wrapper and call `aliyun <product>` directly unless the wrapper script is confirmed missing or `skillopt-lib.sh` cannot be sourced.
4. **Wrapper graceful fallback**: Wrapper scripts MUST handle missing `skillopt-lib.sh` gracefully — fall back to direct `aliyun` CLI execution rather than crashing with `set -e`.
5. **Audit check**: During Post-Update Self-Review (§11), verify that all CLI execution examples in SKILL.md either use the wrapper or are explicitly marked as fallback paths.

Rationale: The wrapper provides automated self-repair (throttling backoff, InvalidParameter fix, ResourceNotFound validation), Langfuse tracing, and circuit breaker protection. Bypassing it silently removes these safety nets and makes operations less observable.

### 15.9 Output Capture Rule (MANDATORY for skillopt-lib.sh)

**Root cause pattern**: When `SKILLOPT_ENABLED != "true"` (default), `skillopt_wrap()` MUST NOT call `aliyun` directly. Direct execution bypasses `SKILLOPT_LAST_OUTPUT` capture, causing Langfuse trace `output` to be `undefined` / empty.

**Correct pattern** (all skillopt-lib.sh implementations MUST follow):
```bash
if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
 local rc=0
 skillopt_run_aliyun "$product" "$action" "${SKILLOPT_PARAMS[@]+"${SKILLOPT_PARAMS[@]}"}" || rc=$?
 printf '%s\n' "$SKILLOPT_LAST_OUTPUT"
 if [[ $rc -eq 0 ]]; then
  skillopt_trace_end "success" "" "$SKILLOPT_LAST_OUTPUT"
 else
  skillopt_trace_end "failed" "exit_code_$rc" "$SKILLOPT_LAST_OUTPUT"
 fi
 return $rc
fi
```

**Banned pattern** (causes silent trace data loss):
```bash
# WRONG — output goes to stdout but SKILLOPT_LAST_OUTPUT remains empty
if [[ "$SKILLOPT_ENABLED" != "true" ]]; then
 aliyun "$product" "$action" ...
 local rc=$?
 skillopt_trace_end ... "$SKILLOPT_LAST_OUTPUT" # ← empty!
fi
```

**Why**: `skillopt_run_aliyun` captures both stdout and stderr to a temp file, assigns it to `SKILLOPT_LAST_OUTPUT`, and returns the exit code. `skillopt_trace_end` persists this output to the **local** trace JSON (always) and mirrors to Langfuse when enabled. Without this capture, local trace `output` and optional Langfuse payload stay empty.
---
name: alicloud-kms-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud Key Management Service (KMS) — key lifecycle (create, describe, enable,
  disable, schedule deletion, rotate), secret management (create, put value,
  rotate, restore, delete), cryptographic operations (encrypt, decrypt,
  generate-data-key, sign, verify), alias management, and KMS instance
  administration. User mentions "KMS", "密钥管理服务", "key management",
  "encryption key", "secret manager", "BYOK", "data key", "rotate key", or describes
  product-specific scenarios (e.g., encryption failures, secret rotation, key
  access denied) even without naming the product directly. Not for RAM permissions,
  billing, HSM-only operations, or VPC networking that have their own skills.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.24+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  KMS endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "KMS 2016-01-20 / https://help.aliyun.com/zh/kms/developer-reference/api-kms-2016-01-20-dir/"
  cli_applicability: "dual-path"
  cli_support_evidence: >-
    Confirmed via `aliyun help kms` — KMS is a standard Alibaba Cloud product
    covered by RPC-style CLI invocation (`aliyun kms <OperationName>`).
    https://help.aliyun.com/zh/kms/key-management-service/developer-reference/using-openapi
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud KMS Operations Skill

## Overview

Alibaba Cloud **Key Management Service (KMS)** provides centralized management of cryptographic keys and secrets on Alibaba Cloud. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **dual-path execution** (official **SDK/API** and official **`aliyun` CLI**), response validation, and failure recovery. **Do not use the web console as the primary agent execution path.**

KMS covers three primary resource domains:
- **Keys (CMK)** — Customer Master Keys for encryption, decryption, signing, and verification
- **Secrets** — Generic secret values with version management and automatic rotation
- **KMS Instances** — Dedicated KMS instances for enhanced security and compliance

> **UX Compliance:** This skill follows the User Experience Specification. All operations include onboarding guidance, minimal prompts, smart defaults, clear feedback, and user-friendly error handling.

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports KMS product. Both the SDK (via JIT Go) and `aliyun kms <Operation>` paths **MUST** be documented in each execution flow. CLI coverage gaps (if any) will be documented in `references/cli-usage.md`.

## Five Core Standards (Quality Gates)

Every generated skill MUST satisfy these five standards. Use them as a design checklist during population:

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholder conventions (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover, with numbered imperative steps |
| 4 | **Complete Failure Strategies** | Error taxonomy table with ≥ 10 product-specific codes; HALT vs retry per error type |
| 5 | **Absolute Single Responsibility** | One product (KMS), one primary resource model (Keys + Secrets); cross-product delegation to other skills |

Refer to the [meta-skill](../alicloud-skill-generator/SKILL.md#five-core-standards-quality-gates) for detailed descriptions of each standard.

### Well-Architected Framework Integration (卓越架构)

In addition to the Five Core Standards, every generated skill MUST map its operations to Alibaba Cloud's [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html) five pillars:

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | IAM permissions, credential masking, key policies, HSM protection | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | Key deletion protection, backup key material, DR runbook | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | KMS instance pricing model, symmetric vs asymmetric key cost | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Batch key alias management, automated rotation, CLI/API automation | `references/well-architected-assessment.md` §2.4 |
| **性能 (Performance)** | Cryptographic throughput, latency for encrypt/decrypt, HSM vs software | `references/well-architected-assessment.md` §2.5 |

See [references/well-architected-assessment.md](references/well-architected-assessment.md) for the complete specification.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud KMS" OR "密钥管理服务" OR "Key Management Service" OR "KMS实例" OR "加密密钥"
- Task involves CRUD or lifecycle operations on **Keys / Secrets / Aliases**
- Task keywords: KMS, key, CMK, symmetric key, asymmetric key, encrypt, decrypt, secret, rotation, BYOK, data key, alias, KMS instance, sign, verify
- User asks to deploy, configure, troubleshoot, or monitor KMS **via API, SDK, CLI, or automation**
- Cryptographic operation requirements: generate data keys, encrypt/decrypt data, sign/verify signatures

### SHOULD NOT Use This Skill When

- Task is purely RAM / permission model → delegate to: `alicloud-ram-ops`
- Task is about **VPC networking** for KMS instances → delegate to: `alicloud-vpc-ops`
- Task is about **CloudHSM** (Hardware Security Module) → delegate to: `alicloud-cloudhsm-ops` (when present)
- Task is purely billing / account management → delegate to: `alicloud-billing-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

Structured placeholders reduce injection ambiguity and unsafe prompts:

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.key_id}}` | User-supplied CMK ID | Ask once; reuse |
| `{{user.secret_name}}` | User-supplied secret name | Ask once; reuse |
| `{{user.alias_name}}` | User-supplied key alias | Ask once; reuse |
| `{{user.key_spec}}` | User-supplied key spec (Aliyun_AES_256, Aliyun_SM4, RSA_2048, EC_P256, EC_SM2) | Ask once; reuse |
| `{{output.key_id}}` | From last KMS API response (CreateKey) | Parse: `$.KeyId` |
| `{{output.secret_name}}` | From last KMS API response (CreateSecret) | Parse: `$.SecretName` |
| `{{output.request_id}}` | From API response (global) | Parse: `$.RequestId` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes. API version: **2016-01-20**. Protocol: **RPC-style** (HTTPS GET/POST).
- **Base endpoint**: `kms.aliyuncs.com` (or regional: `kms.{region}.aliyuncs.com`)
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec. KMS uses `Code`, `Message`, `RequestId` in responses.
- **Timestamps:** UTC ISO 8601 (e.g. `2026-05-20T10:00:00Z`).
- **Idempotency:** KMS does not use standard client tokens; duplicate resource prevention relies on unique names (alias, secret) and key lifecycle states.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateKey | `$.KeyId` | string | Globally unique CMK identifier |
| CreateKey | `$.KeyArn` | string | Alibaba Cloud Resource Name of the key |
| DescribeKey | `$.KeyState` | string | Lifecycle state: Enabled, Disabled, PendingDeletion, PendingImport |
| DescribeKey | `$.KeySpec` | string | Key type: Aliyun_AES_256, Aliyun_SM4, RSA_2048, EC_P256, EC_SM2 |
| DescribeKey | `$.ProtectionLevel` | string | Protection level: SOFTWARE, HSM |
| ListKeys | `$.Keys.Key[].KeyId` | array | CMK IDs on current page |
| ListKeys | `$.TotalCount` | integer | Total CMKs in region |
| CreateAlias | `$.RequestId` | string | Request ID |
| DeleteAlias | `$.RequestId` | string | Request ID |
| CreateSecret | `$.SecretName` | string | Created secret name |
| DescribeSecret | `$.SecretType` | string | Secret type: Generic, Extendable, Rds, RAMCredentials |
| DescribeSecret | `$.RotationInterval` | string | Auto rotation interval |
| GetSecretValue | `$.SecretData` | string | Retrieved secret value |
| Encrypt | `$.CiphertextBlob` | string | Base64-encoded ciphertext |
| Decrypt | `$.Plaintext` | string | Base64-encoded decrypted plaintext |
| GenerateDataKey | `$.Plaintext` | string | Base64-encoded plaintext data key |
| GenerateDataKey | `$.CiphertextBlob` | string | Base64-encoded encrypted data key |
| AsymmetricSign | `$.Value` | string | Base64-encoded signature |
| AsymmetricVerify | `$.Value` | boolean | Signature verification result |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateKey | — | Enabled | 2s | 30s |
| EnableKey | Disabled | Enabled | 2s | 15s |
| DisableKey | Enabled | Disabled | 2s | 15s |
| ScheduleKeyDeletion | Enabled/Disabled | PendingDeletion | N/A (async) | N/A |
| CancelKeyDeletion | PendingDeletion | Enabled | N/A (async) | N/A |
| CreateSecret | — | Available | 2s | 30s |
| DeleteSecret | Available | ScheduledDeletion | N/A (async) | N/A |
| RestoreSecret | ScheduledDeletion | Available | N/A (async) | N/A |

## Quick Start

### What This Skill Does
This skill enables you to deploy, configure, troubleshoot, and monitor KMS resources on Alibaba Cloud using the `aliyun` CLI (primary) or JIT Go SDK (fallback).

### Prerequisites
- [ ] `aliyun` CLI installed (or Go 1.24+ runtime for JIT fallback)
- [ ] Credentials configured: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region set: `ALIBABA_CLOUD_REGION_ID`

### Verify Setup
```bash
# Check CLI and KMS API connectivity
aliyun kms DescribeRegions
```

### Your First Command
```bash
# Example: List all KMS keys in current region
aliyun kms ListKeys --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}
```

### Next Steps
- [Core Concepts](references/core-concepts.md) — Understand KMS architecture, key lifecycle, and protection levels
- [Common Operations](#execution-flows) — Create, manage, and delete keys and secrets
- [Troubleshooting](references/troubleshooting.md) — Fix common KMS issues

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| CreateKey | Create a Customer Master Key (CMK) | Medium | Low |
| DescribeKey | View key details and state | Low | None |
| EnableKey / DisableKey | Change key lifecycle state | Low | Medium |
| ScheduleKeyDeletion | Schedule key deletion (30-day window) | Low | **High** |
| CancelKeyDeletion | Cancel scheduled key deletion | Low | Low |
| CreateAlias | Create/update alias for a key | Low | Low |
| DeleteAlias | Delete a key alias | Low | Low |
| ListKeys | List all CMKs in region | Low | None |
| CreateSecret | Create a managed secret | Medium | Low |
| GetSecretValue | Retrieve secret value | Low | Low |
| PutSecretValue | Store new secret version | Low | Low |
| RotateSecret | Manually rotate a secret | Medium | Low |
| DeleteSecret | Schedule secret deletion | Low | **High** |
| RestoreSecret | Restore a scheduled-deletion secret | Low | Medium |
| Encrypt | Encrypt data with symmetric key | Low | Low |
| Decrypt | Decrypt ciphertext | Low | Low |
| GenerateDataKey | Generate data key for envelope encryption | Low | Low |
| AsymmetricSign / AsymmetricVerify | Sign and verify with asymmetric key | Medium | Low |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-20 | Initial KMS ops skill — dual-path (CLI + SDK), 17 operations |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI primary + JIT Go SDK fallback) → Validate → Recover**. Do not skip phases.

**Preference hint:** KMS is fully supported by `aliyun` CLI via RPC-style API. CLI is the **primary** execution path. JIT Go SDK serves as fallback for edge cases or advanced Go SDK integration.

### Operation: CreateKey

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI | `aliyun version` | Exit code 0 | Document CLI install per self-healing framework |
| Credentials | Valid AK configured per `~/.aliyun/config.json` or env vars | Configured | HALT; user configures credentials |
| Region | `aliyun kms DescribeRegions` | `{{user.region}}` in returned list | Suggest valid region |
| KMS activated | `aliyun kms DescribeAccountKmsStatus` | Already activated | If not, call `OpenKmsService` to activate |

#### Execution — CLI (`aliyun`) (Primary Path)

```bash
# Create a symmetric encryption key with software protection
aliyun kms CreateKey \
  --KeyUsage ENCRYPT/DECRYPT \
  --KeySpec Aliyun_AES_256 \
  --ProtectionLevel SOFTWARE \
  --Description "{{user.description}}" \
  --RegionId "{{user.region}}"
```

```bash
# Create an asymmetric key for signing (SM2 — OSCCA-compliant regions only)
aliyun kms CreateKey \
  --KeyUsage SIGN/VERIFY \
  --KeySpec EC_SM2 \
  --ProtectionLevel SOFTWARE \
  --RegionId "{{user.region}}"
```

```bash
# Create a key with automatic rotation enabled (7–365 days; software symmetric keys only)
aliyun kms CreateKey \
  --KeyUsage ENCRYPT/DECRYPT \
  --KeySpec Aliyun_AES_256 \
  --ProtectionLevel SOFTWARE \
  --EnableAutomaticRotation true \
  --RotationInterval 365 \
  --RegionId "{{user.region}}"
```

#### Execution — JIT Go SDK (Fallback Path)

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    kmssdk "github.com/alibabacloud-go/kms-20160120/v3/client"
    "github.com/alibabacloud-go/tea/tea"
    "github.com/alibabacloud-go/tea-utils/v2/service"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.Sprintf("kms.%s.aliyuncs.com", os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }

    client, err := kmssdk.NewClient(config)
    if err != nil {
        fmt.Printf("Error: failed to create KMS client (credential omitted)\n")
        os.Exit(1)
    }

    request := &kmssdk.CreateKeyRequest{
        KeyUsage:        tea.String("ENCRYPT/DECRYPT"),
        KeySpec:         tea.String("Aliyun_AES_256"),
        ProtectionLevel: tea.String("SOFTWARE"),
        Description:     tea.String("JIT-created symmetric key"),
    }

    runtime := &service.RuntimeOptions{ConnectTimeout: tea.Int(5000), ReadTimeout: tea.Int(5000)}
    resp, err := client.CreateKeyWithOptions(request, runtime)
    if err != nil {
        fmt.Printf("Error: CreateKey failed — %v\n", err)
        os.Exit(1)
    }

    fmt.Println(tea.ToString(resp.Body.KeyId))
}
```

Execute:
```bash
mkdir -p /tmp/aliyun-sdk-workspace && cd /tmp/aliyun-sdk-workspace
go mod init kms-jit
export GOPROXY="https://goproxy.cn,direct"
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/kms-20160120/v3/client
go get github.com/alibabacloud-go/tea-utils/v2/service
go run ./main.go
```

#### Post-execution Validation

1. Capture `{{output.key_id}}` from response `$.KeyId`
2. Verify key state:
   ```bash
   aliyun kms DescribeKey --KeyId "{{output.key_id}}"
   ```
3. Confirm `KeyState` is `Enabled`. Report `{{output.key_id}}` and key spec to user.
4. On failure, go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action | UX Feedback |
|--------------|-------------|---------|--------------|-------------|
| `InvalidParameter` | 0–1 | — | Fix args per OpenAPI; retry once | `[ERROR] InvalidParameter: Request parameter invalid. How to fix: Check KeySpec, KeyUsage, ProtectionLevel against OpenAPI. Next step: Retry with corrected parameters.` |
| `Forbidden.RAM` | 0 | — | HALT | `[ERROR] Forbidden.RAM: Insufficient RAM permissions. How to fix: Add kms:CreateKey permission. Next step: Delegate to alicloud-ram-ops.` |
| `KMSNotActivate` | 0 | — | Call `OpenKmsService`, then retry | `[ERROR] KMSNotActivate: KMS service not activated. Auto-activating now...` |
| `InsufficientBalance` | 0 | — | HALT | `[ERROR] InsufficientBalance: Account balance insufficient. How to fix: Recharge account. Next step: Go to billing console.` |
| Throttling / 429 | 3 | exponential | Back off; respect Retry-After | `⚠️ Rate limit reached. Retrying in {backoff}s... (Attempt {current}/{max})` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId | `[ERROR] InternalError: Server-side error. Retrying... If persists, escalate with RequestId: {{output.request_id}}.` |

### Operation: DescribeKey

#### Execution

Use DescribeKey API with key ID or alias.

```bash
# CLI — describe key by ID
aliyun kms DescribeKey \
  --KeyId "{{user.key_id}}" \
  --RegionId "{{user.region}}"
```

```bash
# CLI — describe key by alias
aliyun kms DescribeKey \
  --KeyId "alias/{{user.alias_name}}" \
  --RegionId "{{user.region}}"
```

```bash
# CLI — extract key fields with JMESPath
aliyun kms DescribeKey \
  --KeyId "{{user.key_id}}" \
  --output cols=KeyId,KeyState,KeySpec,ProtectionLevel,Creator,CreateDate rows=Key.{KeyId,KeyState,KeySpec,ProtectionLevel,Creator,CreateDate}
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| KeyId | `$.Key.KeyId` | Plain text |
| KeyArn | `$.Key.KeyArn` | ARN format |
| KeyState | `$.Key.KeyState` | Human-readable: Enabled, Disabled, PendingDeletion, PendingImport |
| KeySpec | `$.Key.KeySpec` | Aliyun_AES_256, Aliyun_SM4, RSA_2048, EC_P256, EC_P256K, EC_SM2 |
| KeyUsage | `$.Key.KeyUsage` | ENCRYPT/DECRYPT or SIGN/VERIFY |
| ProtectionLevel | `$.Key.ProtectionLevel` | SOFTWARE or HSM |
| Origin | `$.Key.Origin` | Aliyun_KMS, EXTERNAL |
| Creator | `$.Key.Creator` | User or Service |
| CreateDate | `$.Key.CreateDate` | ISO 8601 UTC |
| AutomaticRotation | `$.Key.AutomaticRotation` | DISABLED, ENABLED |

### Operation: ListKeys

#### Execution

```bash
# List all keys in current region with pagination
aliyun kms ListKeys \
  --PageNumber 1 \
  --PageSize 100 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

```bash
# Filter keys by state (Enabled and Disabled) and key spec
aliyun kms ListKeys \
  --Filters '[{"Key":"KeyState","Values":["Enabled","Disabled"]},{"Key":"KeySpec","Values":["Aliyun_AES_256"]}]' \
  --PageSize 100 \
  --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}" \
  --output cols=KeyId,KeyArn rows=Keys.Key[].{KeyId,KeyArn}
```

### Operation: EnableKey / DisableKey

#### Pre-flight

Verify key exists and is in correct initial state (DisableKey requires Enabled, EnableKey requires Disabled).

#### Execution

```bash
# Enable a disabled key
aliyun kms EnableKey --KeyId "{{user.key_id}}" --RegionId "{{user.region}}"
```

```bash
# Disable an enabled key
aliyun kms DisableKey --KeyId "{{user.key_id}}" --RegionId "{{user.region}}"
```

#### Post-execution Validation

Poll `DescribeKey` until `KeyState` matches desired state (15s max):
```bash
for i in $(seq 1 15); do
  STATE=$(aliyun kms DescribeKey --KeyId "{{user.key_id}}" | jq -r '.Key.KeyState')
  [ "$STATE" = "{{desired_state}}" ] && break
  sleep 1
done
```

### Operation: CreateAlias

#### Pre-flight

- Verify target key exists via `DescribeKey`
- Alias name must start with `alias/` prefix
- Ensure alias name is unique (no `AliasAlreadyExists`)

#### Execution

```bash
# Create alias bound to a key
aliyun kms CreateAlias \
  --AliasName "alias/{{user.alias_name}}" \
  --KeyId "{{user.key_id}}" \
  --RegionId "{{user.region}}"
```

### Operation: DeleteAlias

#### Pre-flight

- Verify alias exists via `ListAliases`
- Confirm with user: deleting alias does NOT delete the underlying key

#### Execution

```bash
aliyun kms DeleteAlias \
  --AliasName "alias/{{user.alias_name}}" \
  --RegionId "{{user.region}}"
```

### Operation: ScheduleKeyDeletion

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible scheduled deletion of key `{{user.key_id}}`. Key enters 7–30 day PendingDeletion state, then automatically deleted.
- **MUST** confirm: all aliases will be unbound; dependent services may fail.
- **MUST** verify key is NOT the default service key for other Alibaba Cloud products.
- Confirm waiting period in days (must be 7–30).

#### Execution

```bash
aliyun kms ScheduleKeyDeletion \
  --KeyId "{{user.key_id}}" \
  --PendingWindowInDays 30 \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

1. Verify key state changed to `PendingDeletion`:
   ```bash
   aliyun kms DescribeKey --KeyId "{{user.key_id}}"
   ```
2. Note the actual deletion date for user reference.

#### Failure Recovery

| Error pattern | Agent Action | UX Feedback |
|--------------|--------------|-------------|
| `KeyStateInvalid` | HALT | `[ERROR] Key in invalid state for deletion. Key must be Enabled or Disabled.` |
| `PendingWindowInDays` invalid | Fix value (7–30), retry | `[ERROR] PendingWindowInDays must be between 7 and 30.` |

### Operation: CancelKeyDeletion

#### Execution

```bash
aliyun kms CancelKeyDeletion \
  --KeyId "{{user.key_id}}" \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

Verify key state returned to `Enabled`:
```bash
aliyun kms DescribeKey --KeyId "{{user.key_id}}"
```

### Operation: CreateSecret

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Key exists (for encryption) | `DescribeKey` with `{{user.key_id}}` | Key in `Enabled` state | HALT |
| Secret name unique | `DescribeSecret` with `{{user.secret_name}}` | Returns not found | Inform user of existing secret |
| KMS instance valid (if using DKMS) | `GetKmsInstance` | Instance `Available` | HALT |

#### Execution — CLI

```bash
# Create a generic secret
aliyun kms CreateSecret \
  --SecretName "{{user.secret_name}}" \
  --SecretData "{{user.secret_value}}" \
  --Description "{{user.description}}" \
  --VersionStages "[\"ACSCurrent\"]" \
  --RegionId "{{user.region}}"
```

```bash
# Create a secret with automatic rotation
aliyun kms CreateSecret \
  --SecretName "{{user.secret_name}}" \
  --SecretData "{{user.secret_value}}" \
  --Description "{{user.description}}" \
  --RotationInterval "7d" \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

1. Capture `{{output.secret_name}}` from response `$.SecretName`
2. Verify secret metadata:
   ```bash
   aliyun kms DescribeSecret --SecretName "{{output.secret_name}}"
   ```

#### Failure Recovery

| Error pattern | Agent Action | UX Feedback |
|--------------|--------------|-------------|
| `Forbidden.RAM` | HALT + delegate to RAM ops | `[ERROR] Insufficient RAM permissions. Delegate to alicloud-ram-ops.` |
| `SecretNameAlreadyExists` | Ask user to use different name or update existing | `[ERROR] Secret already exists. Use PutSecretValue to add new version or choose different name.` |
| `InvalidParameter` | Fix args, retry once | `[ERROR] Invalid parameter. Check SecretName, SecretData format.` |

### Operation: GetSecretValue

#### Execution

```bash
# Get current version secret value
aliyun kms GetSecretValue \
  --SecretName "{{user.secret_name}}" \
  --RegionId "{{user.region}}"
```

```bash
# Get specific version
aliyun kms GetSecretValue \
  --SecretName "{{user.secret_name}}" \
  --VersionId "{{user.version_id}}" \
  --RegionId "{{user.region}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| SecretName | `$.SecretName` | Secret name |
| SecretData | `$.SecretData` | **NEVER log**; display once to user only |
| VersionStages | `$.VersionStages.Stage[]` | Version stage labels |
| VersionId | `$.VersionId` | Secret version ID |

### Operation: RotateSecret

#### Pre-flight

- **MUST** verify secret is in `Available` state
- **MUST** verify automatic rotation is configured OR user provides new secret value

#### Execution — CLI

```bash
# Manual rotation (automatic rotation secrets only)
aliyun kms RotateSecret \
  --SecretName "{{user.secret_name}}" \
  --RegionId "{{user.region}}"
```

```bash
# Rotation with new secret value (generic secrets)
aliyun kms PutSecretValue \
  --SecretName "{{user.secret_name}}" \
  --SecretData "{{user.new_secret_value}}" \
  --VersionStages "[\"ACSCurrent\"]" \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

1. Verify new version exists:
   ```bash
   aliyun kms ListSecretVersionIds --SecretName "{{user.secret_name}}"
   ```
2. Validate secret data via `GetSecretValue`.

### Operation: DeleteSecret

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit user confirmation: secret will enter scheduled deletion state
- **MUST** verify no active dependencies reference this secret
- **MUST** suggest backup: `GetSecretValue` before deletion

#### Execution

```bash
# Schedule secret deletion (30-day recovery window)
aliyun kms DeleteSecret \
  --SecretName "{{user.secret_name}}" \
  --RecoveryWindowInDays 30 \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

Verify secret state is `ScheduledDeletion`:
```bash
aliyun kms DescribeSecret --SecretName "{{user.secret_name}}"
```

### Operation: RestoreSecret

#### Execution

```bash
aliyun kms RestoreSecret \
  --SecretName "{{user.secret_name}}" \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

Verify secret state returned to `Available`.

### Operation: Encrypt

#### Pre-flight

- Verify symmetric key exists and is `Enabled`
- Confirm `KeyUsage` is `ENCRYPT/DECRYPT`
- Plaintext ≤ 4096 bytes (KMS symmetric key limit)

#### Execution — CLI

```bash
aliyun kms Encrypt \
  --KeyId "{{user.key_id}}" \
  --Plaintext "{{base64_plaintext}}" \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

- Verify `CiphertextBlob` present in response
- Test roundtrip: decrypt with same key and compare plaintext

### Operation: Decrypt

#### Pre-flight

- Verify key exists and is `Enabled`
- Ciphertext is valid base64

#### Execution — CLI

```bash
aliyun kms Decrypt \
  --KeyId "{{user.key_id}}" \
  --CiphertextBlob "{{ciphertext_blob}}" \
  --RegionId "{{user.region}}"
```

### Operation: GenerateDataKey

#### Execution — CLI

```bash
# Generate 256-bit data key
aliyun kms GenerateDataKey \
  --KeyId "{{user.key_id}}" \
  --KeySpec AES_256 \
  --RegionId "{{user.region}}"
```

```bash
# Generate without plaintext (for server-side only usage)
aliyun kms GenerateDataKeyWithoutPlaintext \
  --KeyId "{{user.key_id}}" \
  --KeySpec AES_256 \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

- Verify both `Plaintext` (for GenerateDataKey) and `CiphertextBlob` present
- Note: `Plaintext` is returned as base64-encoded string

### Operation: AsymmetricSign / AsymmetricVerify

#### Pre-flight

- Verify asymmetric key exists, is `Enabled`, and `KeyUsage` is `SIGN/VERIFY`

#### Execution — AsymmetricSign

```bash
aliyun kms AsymmetricSign \
  --KeyId "{{user.key_id}}" \
  --Plaintext "{{base64_message}}" \
  --Algorithm "{{user.algorithm}}" \
  --RegionId "{{user.region}}"
```

#### Execution — AsymmetricVerify

```bash
aliyun kms AsymmetricVerify \
  --KeyId "{{user.key_id}}" \
  --Plaintext "{{base64_message}}" \
  --SignatureValue "{{signature_value}}" \
  --Algorithm "{{user.algorithm}}" \
  --RegionId "{{user.region}}"
```

## Prerequisites

1. **Install `aliyun` CLI** (static Go binary, no runtime dependencies):

   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback):

   ```bash
   if ! command -v go &> /dev/null; then
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"
       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime
       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOPROXY="https://goproxy.cn,direct"
   fi
   go version
   ```

3. **Configure Credentials**:

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

4. **Verify Configuration**:
   ```bash
   aliyun kms DescribeRegions
   ```

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [Enhanced Self-Healing Framework](references/enhanced-self-healing-framework.md)
- [GCL Rubric](references/rubric.md) — **Phase 1 rollout** GCL rubric (5 core + 3 Aliyun dimensions, 17 per-op Safety sub-rules, 10 key-material regex hot-spots, 4 worked examples)
- [GCL Prompt Templates](references/prompt-templates.md) — **Phase 1 rollout** Generator & Critic prompt templates (one-shot delivery + PendingWindowInDays validation)

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required KMS APIs only.
- **Availability:** Use key aliases for indirection; enables key rotation without application changes.
- **Security:** Enable automatic rotation for symmetric keys; use HSM protected keys for compliance.
- **Cost:** Prefer software-protected keys unless HSM is required for compliance.
- **Key lifecycle:** Always test with small-scale keys; document all key purposes and owners.

---

## Quality Gate (GCL)

This skill is the **fifth rollout** of the Generator-Critic-Loop (GCL)
adversarial quality gate defined in [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate).
Every runtime execution of an `alicloud-kms-ops` operation MUST be wrapped
in a GCL loop before the result is returned to the user.

> **Why KMS warrants the strictest GCL rules in the farm:**
>
> KMS is the **cryptographic root of trust** for the entire Alibaba Cloud
> account. Three consequences are reflected in the rubric and prompt templates:
>
> 1. **`ScheduleKeyDeletion` is the most irreversible op in the farm.**
>    After the 7-30 day `PendingWindowInDays` elapses, key material is
>    destroyed. Per `SKILL.md` "ScheduleKeyDeletion" Pre-flight:
>    "irreversible scheduled deletion of key".
> 2. **`GetSecretValue` / `Decrypt` / `GenerateDataKey` / `Encrypt` return
>    plaintext** that is **irrecoverable** after the response is discarded.
>    These are **double-strict** one-shot delivery contracts.
> 3. **Key material in a trace is a hard double-absolute** (Safety = 0
>    AND Credential Hygiene = 0) — stricter than any other skill because
>    plaintext key material can decrypt arbitrary ciphertext.

> **Two references in this directory carry the GCL contract:**
>
> | File | Purpose |
> |---|---|
> | [`references/rubric.md`](references/rubric.md) | The 5 core + 3 Aliyun-specific rubric dimensions, 17 per-op Safety sub-rules, §1.2.1 key-material detection (10 regex hot-spots), 4 worked examples |
> | [`references/prompt-templates.md`](references/prompt-templates.md) | The Generator and Critic prompt templates (with `{{env.*}}` / `{{user.*}}` / `{{output.*}}` placeholders) — includes one-shot delivery contract and PendingWindowInDays validation |

### GCL Scope for KMS

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1 rollout, fifth skill) |
| Default `max_iter` | **2** (inherited from `AGENTS.md` §12.8) |
| Operations covered | ALL operations in this SKILL.md (CreateKey, ScheduleKeyDeletion, CancelKeyDeletion, EnableKey/DisableKey, CreateAlias, DeleteAlias, CreateSecret, GetSecretValue, PutSecretValue, RotateSecret, DeleteSecret, RestoreSecret, Encrypt, Decrypt, GenerateDataKey, AsymmetricSign/Verify, OpenKmsService) |
| Operations most scrutinized | `ScheduleKeyDeletion` (irreversible), `DeleteSecret` (recovery-window), `DisableKey` (breaks dependents), `GetSecretValue` / `Decrypt` / `GenerateDataKey` / `Encrypt` (plaintext return), `CreateKey` with `EnableAutomaticRotation=true` (rotation policy) |

### Per-Op Safety Sub-Rules (Quick Reference)

For the **full** sub-rule table (17 operations), see
[`references/rubric.md` §1.2](../alicloud-kms-ops/references/rubric.md).
Highlights:

| Operation | Hard Safety condition (Score 1 requires) |
|---|---|
| `CreateKey` | Explicit user confirmation of `KeyUsage` / `KeySpec`; `ProtectionLevel` ∈ {`SOFTWARE`, `HSM`}; if `EnableAutomaticRotation=true`, `RotationInterval ∈ [7, 365]` days; returned `KeyId` is one-shot delivered |
| `ScheduleKeyDeletion` | Explicit user confirmation; **explicit warning that key material is DESTROYED after the pending window**; **`PendingWindowInDays ∈ [7, 30]`**; `DescribeKey` confirms `Enabled`/`Disabled`; aliases enumerated via `ListAliases`; **deletion date informed to user**; **`CancelKeyDeletion` mentioned as rescue op** |
| `CancelKeyDeletion` | `DescribeKey` confirms `PendingDeletion`; explicit user confirmation |
| `DisableKey` | Explicit user confirmation; `DescribeKey` confirms `Enabled`; explicit warning that dependents will fail |
| `CreateSecret` / `PutSecretValue` | `DescribeSecret` confirms name uniqueness; `SecretData` delivered via **env var or file reference, NOT inline CLI flag** |
| `RotateSecret` | Explicit user confirmation; secret is `Available`; rotation is automatic OR user provides new value via env var; applications warned to update retrieval |
| `DeleteSecret` | Explicit user confirmation; **`RecoveryWindowInDays ∈ [7, 30]`**; no active dependencies; **final `GetSecretValue` retrieved and saved by user in the same flow** |
| `RestoreSecret` | `DescribeSecret` confirms `ScheduledDeletion`; explicit user confirmation |
| `GetSecretValue` | Explicit user confirmation; secret is `Available`; **`SecretData` plaintext is one-shot delivered and redacted everywhere else** |
| `Decrypt` | Explicit user confirmation; `CiphertextBlob` is from this session; `Plaintext` is one-shot delivered |
| `GenerateDataKey` | Explicit user confirmation; BOTH `Plaintext` AND `CiphertextBlob` are one-shot delivered; agent recommends storing `CiphertextBlob` long-term and discarding `Plaintext` after envelope encryption |

### The PendingWindowInDays Rule (ScheduleKeyDeletion, hard gate)

Per `SKILL.md` "ScheduleKeyDeletion" Pre-flight: `PendingWindowInDays` must
be **in [7, 30]**. The Critic regex `pending_window_in_days["': =]+[1-6]\b`
or `=0\b` will catch violations. Values outside this range → **Safety = 0**.

Additionally, the user MUST be informed of:
- The **deletion date** (computed from `PendingWindowInDays`)
- `CancelKeyDeletion` as the **rescue op** within the window

### The One-Shot Delivery Contract (for plaintext-returning ops)

`GetSecretValue` / `Decrypt` / `GenerateDataKey` / `Encrypt` return
plaintext that is **irrecoverable** after the response is discarded. The
trace MUST encode:

```json
{
  "generator": {
    "command": "aliyun kms GetSecretValue --SecretName \"...\"",
    "output_mode": "json",  // MUST be "json"
    "one_shot_delivery": {
      "delivered": true,
      "delivered_to": "user",
      "delivered_at": "2026-06-04T10:00:00Z",
      "trace_value_after_delivery": "<redacted>",
      "ciphertext_blob_persisted": true,  // for Decrypt / GenerateDataKey
      "ciphertext_blob_value": "<available in trace for re-decrypt if needed>"
    }
  }
}
```

> `--output cols=` / `--output table` is **forbidden** for plaintext-returning
> ops for the same reason as RAM's `CreateAccessKey` (per
> `AGENTS.md` §12 cross-skill convention).

### The Key-Material Hard-Block (cross-cutting)

The Critic MUST scan the trace for the 10 key-material regex hot-spots in
`rubric.md` §1.2.1. A match is **both Safety = 0 AND Credential Hygiene = 0**:

| Pattern | Risk |
|---|---|
| `"Plaintext":"..."` (outside one-shot) | DESTRUCTIVE-MASS (key material leak) |
| `"SecretData":"..."` (outside one-shot) | DESTRUCTIVE-MASS (secret leak) |
| `"KeyMaterial":"..."` | DESTRUCTIVE-MASS (raw key material) |
| `BEGIN PRIVATE KEY` / `BEGIN RSA PRIVATE KEY` / `BEGIN EC PRIVATE KEY` | DESTRUCTIVE-MASS (private key in trace) |
| `--SecretData "rawvalue"` | Credential Hygiene = 0 (CLI flag leak) |
| `--Plaintext "rawvalue"` | Credential Hygiene = 0 (CLI flag leak) |
| `PendingWindowInDays` ∈ [1, 6] | Safety = 0 (too-short window) |
| `PendingWindowInDays = 0` | Safety = 0 (immediate delete) |

### KMS-Specific Additions (beyond the 5 core dimensions)

| Dimension | Threshold | Why it matters for KMS |
|---|---|---|
| **Region Compliance** | ≥ 0.5 | `--RegionId` must match `{{user.region}}`; **cross-region key access is impossible** without `ReplicateKey` — mixing `--RegionId` and `KeyId` from different regions is a Safety = 0 finding |
| **Credential Hygiene** | = 1 (**absolute, triple-strict**) | KMS issues AND consumes cryptographic material. The trace must contain no `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, no leaked `Plaintext` / `SecretData` / `KeyMaterial` / private keys. 12 KMS-specific patterns in `rubric.md` §2.2. |
| **Well-Architected** | ≥ 0.5 | The 5 WA pillars; **Security is the primary pillar** for KMS (cryptographic root). Security sub-score **must** be ≥ 0.5 or the overall WA score is 0. |

### Termination (inherited from `AGENTS.md` §12.5)

| Condition | Behavior |
|---|---|
| All dimensions ≥ threshold | **PASS** — return Generator's result |
| Safety = 0 **or** Credential Hygiene = 0 | **ABORT** — never return partial output |
| Other dimension < threshold AND iter < 2 | **RETRY** — inject Critic suggestions into next Generator prompt |
| Other dimension < threshold AND iter = 2 | **MAX_ITER** — return best-so-far + unresolved rubric items |

### Trace Persistence (mandatory)

Every GCL run MUST write `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`
with the schema defined in `AGENTS.md` §12.6. Apply the KMS-specific
sanitization regex helpers in `rubric.md` §2.2 to scrub all 12
KMS-specific secret / key material patterns before persisting.

### Changelog (this section only)

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-06-04 | Fifth rollout: added `## Quality Gate (GCL)` section + `references/rubric.md` + `references/prompt-templates.md`. Default `max_iter=2`. Aligned with `AGENTS.md` §12 and the ECS / Redis / RDS / RAM pilots. KMS-specific additions: 17 per-op Safety sub-rules; `PendingWindowInDays ∈ [7, 30]` hard rule; one-shot delivery contract for plaintext-returning ops; mandatory `--output json` for plaintext-returning ops; 10 key-material regex hot-spots (leak = Safety = 0 + Credential Hygiene = 0); 12 KMS-specific secret / key material patterns with sanitization helper; cross-region key access is a Safety = 0 finding. |

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，CLI/SDK 已覆盖，无需 code snippets.

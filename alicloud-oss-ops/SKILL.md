<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

---
name: alicloud-oss-ops
description: >-
  Use when the user needs to manage Alibaba Cloud Object Storage Service (OSS)
  — create, configure, list, and delete buckets; manage bucket ACL, lifecycle
  rules, CORS, logging, static website hosting, referer anti-leeching, cross-region
  replication, and access policies; upload, download, copy, delete, list, and
  restore objects; handle multipart uploads, presigned URLs, image processing,
  and Archive/ColdArchive data restore. User mentions OSS, Object Storage, 对象存储,
  OSS bucket, 存储空间, object, 对象, OSS文件, Bucket ACL, Bucket Policy, lifecycle,
  生命周期, CORS, 跨域, 静态网站, 防盗链, Referer白名单, 跨区域复制, 归档存储,
  分片上传, 断点续传, image processing, 图片处理, 签名URL, presign, S3-compatible
  — even without naming the product directly. Not for NAS file systems, HDFS,
  EBS disks, or CDN-only delivery (without OSS origin).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), `ossutil` (recommended for data plane), valid API
  credentials, network access to Alibaba Cloud endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: >-
    OSS 2019-05-17 (control plane) / https://help.aliyun.com/zh/oss/developer-reference/api-oss-2019-05-17-overview.
    Data plane uses S3-compatible REST API at <bucket>.<endpoint>.
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help oss` — Product Oss, Version 2019-05-17. Core
    control-plane operations (ListBuckets, PutBucket, GetBucketInfo, DeleteBucket,
    GetBucketLifecycle, PutBucketLifecycle, GetBucketReferer, PutBucketReferer,
    GetBucketPolicy, PutBucketReplication) have matching CLI commands. Data-plane
    operations are also exposed via `aliyun oss` subcommands; for high-volume data
    transfers, `ossutil` is recommended.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Object Storage Service (OSS) Operations Skill

## Overview

Alibaba Cloud **Object Storage Service (OSS)** is a secure, cost-effective, and
highly durable cloud storage service that provides 99.9999999999% (12 nines)
data durability. This skill is an **operational runbook** for agents: explicit
scope, credential rules, pre-flight checks, **dual-path execution** (official
**CLI / SDK** for control plane; **ossutil** or **OSS Go SDK V2** for data plane),
response validation, and failure recovery. **Do not use the web console as the
primary agent execution path** in `SKILL.md` or [阿里云 OSS 控制台](https://oss.console.aliyun.com).

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:**
  - **Control plane** (bucket/ACL/lifecycle/CORS/...): `aliyun oss <op>` is the
    primary path; JIT Go SDK is the fallback.
  - **Data plane** (object upload/download/list/...): both `aliyun oss <op>` and
    `ossutil` are supported. For bulk transfers (>1 GB) and multipart uploads,
    `ossutil` (or the OSS Go SDK V2) is strongly recommended over `aliyun oss`.

> **OSS-specific note:** The `aliyun oss` command is technically a sub-product
> wrapper that delegates to `ossutil` internally. The recommended tool for
> high-throughput data operations is `ossutil` (a Go binary distributed by the
> OSS team). Both share the same `~/.ossutilconfig` or env-var credentials.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud OSS" OR "Object Storage Service" OR "对象存储"
  OR "OSS" OR "存储空间" OR "Bucket"
- Task involves creating, configuring, listing, or deleting **OSS buckets**
- Task involves **bucket-level features**: ACL, lifecycle rules, CORS, logging,
  static website hosting, Referer anti-leech, cross-region replication, bucket
  policy, encryption, versioning, access monitor
- Task involves **object operations**: upload, download, copy, move, delete,
  list, head, restore (for Archive objects), presigned URL generation
- Task involves **multipart uploads**, large file transfers, or resumable uploads
- Task involves **image processing** (resize, watermark, format conversion) via
  OSS `?x-oss-process=` query parameters
- Task involves **data archiving** to Standard / IA / Archive / ColdArchive and
  restoring frozen objects
- Task involves **S3-compatible** API calls (e.g., migrate from AWS S3 to OSS)
- User mentions: 访问控制, 读写权限, 公共读, 公共读写, 私有, 防盗链, 跨域设置,
  静态网站托管, 镜像回源, 跨区域复制, CRR, 事件通知, 图片处理, 缩略图,
  数据湖, 冷归档, 解冻, lifecycle, multipart, presign, signature URL, RAM policy
- User asks to deploy, configure, troubleshoot, or monitor OSS **via API, SDK,
  CLI, ossutil, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to: `alicloud-billing-ops`
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is about **NAS file system (NFS/SMB)** → delegate to NAS skill (not yet present)
- Task is about **block storage / EBS disks** → delegate to: `alicloud-ecs-ops`
- Task is about **CDN edge delivery only** (and OSS is just origin) → use CDN skill
- Task is about **HDFS / Data Lake Analytics** storage backend → use the data
  analytics skill, not raw OSS
- User insists on **console-only** flows with no API → state limitation

### Delegation Rules

- If creating OSS buckets in a VPC, no VPC dependency exists; OSS is a public
  service accessed via endpoint URLs. Verify `RegionId` and endpoint reachability
  before operations.
- For cross-account OSS access, verify the destination RAM policy via
  `alicloud-ram-ops` before assuming cross-account is allowed.
- For CDN integration, the CDN skill should set OSS as the origin; this skill
  only manages the bucket-side configuration.
- For data migration into OSS, use the SMS or DTS skill (when present); this
  skill does not perform migration.
- If lifecycle rules delete objects needed by another product (e.g., logs for
  SLS), coordinate with the consuming skill before applying destructive
  lifecycle policies.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers; explicit delegation to RAM/CDN/SLS skills |
| 2 | **Structured I/O** | `{{env.*}}` / `{{user.*}}` / `{{output.*}}` placeholders; control-plane + data-plane paths documented |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute (CLI / ossutil / SDK) → Validate → Recover |
| 4 | **Complete Failure Strategies** | Error taxonomy ≥ 10 codes (NoSuchBucket, NoSuchKey, SignatureDoesNotMatch, etc.); HALT vs retry per type |
| 5 | **Absolute Single Responsibility** | One product (OSS), one primary resource (Bucket + Object); CDN/RAM/CDN delegated |

### Well-Architected Framework Integration

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | Bucket ACL, RAM Policy, Referer, encryption (SSE-KMS/SSE-OSS), presigned URL | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | Cross-region replication, versioning, lifecycle, multi-AZ durability | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | Storage class selection (Standard/IA/Archive/ColdArchive), lifecycle tier-down, request cost | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Multipart upload, ossutil, parallel transfer, image processing, batch operations | `references/well-architected-assessment.md` §2.4 |
| **性能 (Performance)** | CDN integration, transfer acceleration, max-PUT-object size (48.8 TB), QPS limits | `references/well-architected-assessment.md` §2.5 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Alibaba Cloud AK | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Alibaba Cloud SK | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region (e.g., `cn-hangzhou`) | Ask once; reuse |
| `{{user.bucket_name}}` | Bucket name (3-63 chars, lowercase, no underscores) | Ask once; validate format |
| `{{user.object_key}}` | Object key (full path within bucket) | Ask once; reuse |
| `{{user.storage_class}}` | `Standard` / `IA` / `Archive` / `ColdArchive` / `DeepColdArchive` | Ask once; default `Standard` |
| `{{user.acl}}` | `private` / `public-read` / `public-read-write` | Ask once; default `private` |
| `{{user.endpoint}}` | OSS endpoint (e.g., `oss-cn-hangzhou.aliyuncs.com`) | Derive from region or ask |
| `{{user.local_path}}` | Local file path for upload/download | Ask once |
| `{{output.bucket_name}}` | From last API response | Parse from `$.Bucket.Name` or `$.Buckets[].Name` |
| `{{output.object_etag}}` | Object ETag from response | Parse from `$.ETag` (control plane) or response header (data plane) |
| `{{output.request_id}}` | Request ID for support / correlation | Parse from `$.RequestId` (control plane) |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考
> [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)
>
> **Bucket naming validation — DEFENSIVE CHECK (mandatory before any bucket op):**
> Bucket names MUST be 3-63 characters, lowercase letters, digits, hyphens
> only; must start and end with a letter or digit. **Validate via
> [`validate_oss_bucket_name`](#operation-validate-bucket-name) BEFORE any
> API call** — OSS rejects invalid names with `InvalidBucketName` but **also
> bills the request and may rate-limit the caller**, so client-side validation
> is faster, cheaper, and more informative. The validation function is shown
> in the dedicated Operation below.

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
  Reference: `https://help.aliyun.com/zh/oss/developer-reference/api-oss-2019-05-17-overview`
- **Errors:** OSS uses `Code` and `Message` fields in the error response body,
  plus HTTP status. Example: `Code=NoSuchBucket`, `Code=SignatureDoesNotMatch`,
  `Code=InvalidArgument`, `Code=AccessDenied`.
- **Timestamps:** ISO 8601 with timezone (e.g., `2026-04-28T10:00:00+08:00`).
- **Idempotency:** Object uploads use `ETag` for verification. Multipart uploads
  use `uploadId` for resumption.
- **Data plane vs control plane:**
  - Control plane (this skill's primary focus): RPC-style via `aliyun oss`
    subcommands; JSON responses; accessed via regional endpoint.
  - Data plane: REST-style via HTTP against `<bucket>.<endpoint>/<key>`;
    supports S3-compatible signature v4 (when explicitly enabled) or v1 (default).

### Common Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| ListBuckets | `$.Buckets[].Name` | array | Bucket names |
| ListBuckets | `$.Buckets[].Region` | string | Bucket region |
| ListBuckets | `$.Buckets[].CreationDate` | string | ISO 8601 creation time |
| ListBuckets | `$.Buckets[].StorageClass` | string | Standard / IA / Archive / ColdArchive / DeepColdArchive |
| ListBuckets | `$.Buckets[].Location` | string | Bucket location constraint |
| PutBucket | `$.Location` | string | Bucket location (the actual created region) |
| GetBucketInfo | `$.Bucket.Name` | string | Bucket name |
| GetBucketInfo | `$.Bucket.StorageClass` | string | Default storage class |
| GetBucketInfo | `$.Bucket.CreationDate` | string | ISO 8601 |
| GetBucketInfo | `$.Bucket.ExtranetEndpoint` | string | Public endpoint |
| GetBucketInfo | `$.Bucket.IntranetEndpoint` | string | Internal endpoint |
| GetBucketInfo | `$.Bucket.Owner.Id` | string | Bucket owner UID |
| GetBucketAcl | `$.AccessControlList.Grant` | string | private / public-read / public-read-write |
| GetBucketLifecycle | `$.LifecycleRules.LifecycleRule[].Id` | array | Rule IDs |
| GetBucketLifecycle | `$.LifecycleRules.LifecycleRule[].Status` | string | Enabled / Disabled |
| GetBucketLifecycle | `$.LifecycleRules.LifecycleRule[].Expiration.Days` | integer | Object expiration in days |
| GetBucketLifecycle | `$.LifecycleRules.LifecycleRule[].Transition.Days` | integer | Days before tier-down |
| GetBucketReferer | `$.RefererConfiguration.AllowEmptyReferer` | boolean | Allow empty referer |
| GetBucketReferer | `$.RefererConfiguration.RefererList` | array | Allowed referer domains |
| GetBucketCors | `$.CORSRules.CORSRule[].AllowedOrigin` | array | Allowed origins |
| GetBucketCors | `$.CORSRules.CORSRule[].AllowedMethod` | array | GET / POST / PUT / DELETE / HEAD |
| GetBucketLogging | `$.BucketLoggingStatus.LoggingEnabled.TargetBucket` | string | Log destination bucket |
| GetBucketLogging | `$.BucketLoggingStatus.LoggingEnabled.TargetPrefix` | string | Log prefix |
| GetBucketReplication | `$.ReplicationConfiguration.Rules.ReplicationRule[].ID` | array | Replication rule IDs |
| GetBucketReplication | `$.ReplicationConfiguration.Rules.ReplicationRule[].Destination.Bucket` | string | Destination bucket |
| GetBucketReplication | `$.ReplicationConfiguration.Rules.ReplicationRule[].Status` | string | enabling / starting / syncing / active |
| GetBucketPolicy | (raw JSON) | string | Bucket policy JSON |
| ListObjects (v1) | `$.Contents[].Key` | array | Object keys |
| ListObjects (v1) | `$.Contents[].Size` | integer | Object size in bytes |
| ListObjects (v1) | `$.Contents[].ETag` | string | Object ETag |
| ListObjects (v1) | `$.Contents[].LastModified` | string | ISO 8601 |
| ListObjects (v1) | `$.Contents[].StorageClass` | string | Object storage class |
| ListObjects (v2) | `$.Contents[].Key` | array | Object keys (v2 returns Key directly) |
| GetBucketStat | `$.Storage` | integer | Total storage in bytes |
| GetBucketStat | `$.ObjectCount` | integer | Total object count |
| GetBucketStat | `$.MultipartUploadCount` | integer | In-progress multipart uploads |
| GetBucketReferer | `$.RefererConfiguration.AllowEmptyReferer` | boolean | Allow empty referer |

> **TE-4 compliance:** All JSON paths are declared once above. Each operation
> section uses these paths by reference (no inline duplication).

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| PutBucket | absent | exists in `GetBucketInfo` | 3s | 60s |
| DeleteBucket | exists, empty (or via lifecycle purge) | absent (`NoSuchBucket`) | 3s | 60s |
| PutObject (small) | absent | exists (`HeadObject` 200) | n/a | sync |
| PutObject (large, multipart) | absent | exists after `CompleteMultipartUpload` | 5s | 3600s |
| InitiateMultipartUpload | absent | `uploadId` returned | n/a | sync |
| RestoreObject | Archive / ColdArchive | Restored (expiry `ongoing-restore` / `Days`) | 30s | 14400s (Archive) / 86400s (ColdArchive) |
| PutBucketLifecycle | n/a | rules persisted | n/a | sync |
| PutBucketReplication | n/a | `active` | 30s | 600s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-04 | Initial OSS skill with dual-path (CLI/SDK) + ossutil data-plane support |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI / ossutil / SDK) → Validate → Recover**.

> **Path selection rule of thumb:**
> 1. **Control plane** (bucket/ACL/lifecycle/...): prefer `aliyun oss` first.
> 2. **Data plane** (object upload/download/list/...): prefer `ossutil` for files
>    > 100 MB or bulk operations; `aliyun oss` is fine for small/quick ops.
> 3. **Programmatic** (in Go pipeline): use **OSS Go SDK V2**
>    (`github.com/aliyun/aliyun-oss-go-sdk/oss`).

> **🛡️ Defensive Validation Rule (GLOBAL — applies to every bucket-scoped
> operation below):**
> Before executing ANY operation that takes a `Bucket` parameter — including
> `PutBucket`, `DeleteBucket`, `GetBucketInfo`, all `Get/Set Bucket *`
> operations, `ListObjects`, all object CRUD (upload/download/copy/delete),
> `RestoreObject`, `ListMultipartUploads`, presigned URL generation — the
> Agent **MUST** run both:
>
> 1. **`validate_oss_bucket_name "{{user.bucket_name}}"`** (see
>    [Operation: Validate Bucket Name](#operation-validate-bucket-name))
>    → exit 0 to continue; non-zero exit code 10-15 means **HALT** with the
>    helper's specific error message.
> 2. **`validate_oss_object_key "{{user.object_key}}"`** for any operation
>    that takes an object key → exit 0 to continue; non-zero exit code
>    30-32 means **HALT**.
>
> Skipping this validation is a P0 violation: invalid names cause wasted API
> calls, generic `InvalidBucketName` errors (no actionable detail), and
> unnecessary rate-limit pressure on the account. The 5-second check is
> always cheaper than the round trip.

---

### Operation: Validate Bucket Name

> **DEFENSIVE VALIDATION — call this BEFORE any bucket-scoped operation
> (Create / Delete / Get / ACL / Lifecycle / ...).**
> The regex `^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$` covers the most common
> rules; the helper below extends it with **consecutive-hyphens** and
> **IP-address-form** checks that the regex alone misses.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Helper available | `type validate_oss_bucket_name` | Function defined | Source-include helper from this file |
| User provided name | `[[ -n "$BUCKET_NAME" \|\| -n "{{user.bucket_name}}" ]]` | Non-empty | HALT; ask for bucket name |

#### Execution — Bash Helper (Authoritative)

```bash
# validate_oss_bucket_name <name>
# Exits 0 on success, prints a one-line error to stderr and exits non-zero on failure.
# Rule order is deliberately tuned for the most diagnostic error message first —
# e.g. "192.168.1.1" reports as an IP violation (specific) rather than
# "contains illegal characters" (generic).
validate_oss_bucket_name() {
  local name="$1"

  # Rule 1: non-empty
  if [[ -z "$name" ]]; then
    echo "ERROR: bucket name is empty" >&2
    return 10
  fi

  # Rule 2: length 3-63
  if [[ ${#name} -lt 3 || ${#name} -gt 63 ]]; then
    echo "ERROR: bucket name must be 3-63 characters (got ${#name}): '$name'" >&2
    return 11
  fi

  # Rule 3 (moved up): must not look like an IP address — check BEFORE the
  # generic character set so the user gets a specific diagnostic for dotted
  # inputs that happen to be digit-only.
  if [[ "$name" =~ ^[0-9.]+$ ]] && [[ "$name" =~ \. ]]; then
    echo "ERROR: bucket name looks like an IP address — OSS rejects these: '$name'" >&2
    return 15
  fi

  # Rule 4: only lowercase letters, digits, hyphens (NO underscore, NO uppercase)
  if ! [[ "$name" =~ ^[a-z0-9-]+$ ]]; then
    # Diagnose the most likely cause for the human:
    if [[ "$name" =~ [_] ]]; then
      echo "ERROR: bucket name contains underscore '_' which is not allowed — use hyphen '-': '$name'" >&2
    elif [[ "$name" =~ [A-Z] ]]; then
      echo "ERROR: bucket name contains uppercase letters — OSS requires all lowercase: '$name'" >&2
    else
      echo "ERROR: bucket name contains illegal characters (only a-z, 0-9, '-' are allowed): '$name'" >&2
    fi
    return 12
  fi

  # Rule 5: must start AND end with a letter or digit (no leading/trailing hyphen)
  if ! [[ "$name" =~ ^[a-z0-9].*[a-z0-9]$ ]] && [[ ${#name} -gt 1 ]]; then
    echo "ERROR: bucket name must start and end with a letter or digit (no leading/trailing hyphen): '$name'" >&2
    return 13
  fi
  if [[ ${#name} -eq 1 ]] && ! [[ "$name" =~ ^[a-z0-9]$ ]]; then
    echo "ERROR: single-character bucket name must be a lowercase letter or digit: '$name'" >&2
    return 13
  fi

  # Rule 6: no consecutive hyphens (RFC 952-style; OSS rejects these)
  if [[ "$name" == *"--"* ]]; then
    echo "ERROR: bucket name contains consecutive hyphens '--': '$name'" >&2
    return 14
  fi

  return 0
}

# Usage in any agent flow:
BUCKET_NAME="{{user.bucket_name}}"
if ! validate_oss_bucket_name "$BUCKET_NAME"; then
  echo "[HALT] Bucket name validation failed — fix the name and retry."
  exit 1
fi
```

#### Exit Code Reference

| Exit Code | Rule Violated | Fix |
|:---------:|---------------|-----|
| 10 | Empty name | Provide a non-empty name |
| 11 | Length not 3-63 | Adjust to 3-63 chars |
| 12 | Bad characters (uppercase / underscore / other) | Lowercase; replace `_` with `-` |
| 13 | Starts or ends with hyphen | Remove leading/trailing `-` |
| 14 | Consecutive hyphens (`--`) | Use single hyphens between segments |
| 15 | Looks like an IP address | Use a different naming scheme |

#### Agent-Side Hard Stops (Belt and Suspenders)

In addition to the bash helper, the Agent **MUST** also run a **read-only**
existence check (`GetBucketInfo` expecting `NoSuchBucket`) BEFORE attempting
to create. This catches the "globally unique" rule that client-side
validation cannot (another tenant may own the name).

```bash
# Defensive pre-create check (CLI)
EXIST=$(aliyun oss GetBucketInfo --Bucket "$BUCKET_NAME" 2>&1)
if ! echo "$EXIST" | grep -q "NoSuchBucket"; then
  echo "[HALT] Bucket '$BUCKET_NAME' already exists (or lookup failed). Pick a unique name." >&2
  exit 20
fi
```

> **Why client-side validation matters even though OSS returns 400:**
> 1. **Faster feedback** — no network round trip; the agent catches errors
>    in < 1 ms.
> 2. **Cheaper** — invalid requests still count toward the account-level
>    request rate limit and may incur rate limiting.
> 3. **More actionable errors** — `InvalidBucketName` from OSS just says
>    "invalid"; the helper pinpoints the exact rule violated.
> 4. **Idempotency safety** — `PutBucket` is **not idempotent**; if the
>    Agent retries on a transient network error after the bucket was
>    actually created, the retry fails with `BucketAlreadyExists`. Client-
>    side validation cannot prevent this, but a pre-`GetBucketInfo` check
>    gives the Agent a clean signal.

#### Companion: Object Key Validation (For Data-Plane Operations)

Object keys are more permissive than bucket names but still have constraints.
Use this lightweight check before `PutObject` / `CopyObject`:

```bash
# validate_oss_object_key <key>
# Exits 0 on success, non-zero on failure.
validate_oss_object_key() {
  local key="$1"

  # Rule 1: non-empty
  if [[ -z "$key" ]]; then
    echo "ERROR: object key is empty" >&2
    return 30
  fi

  # Rule 2: 1-1024 bytes after URL encoding (raw UTF-8 1-1023 is safe)
  local key_len=${#key}
  if [[ $key_len -lt 1 || $key_len -gt 1023 ]]; then
    echo "ERROR: object key must be 1-1023 UTF-8 bytes (got $key_len)" >&2
    return 31
  fi

  # Rule 3: must not start with '/' or '\' (OSS treats these specially)
  if [[ "$key" == /* || "$key" == \\* ]]; then
    echo "ERROR: object key must not start with '/' or '\\': '$key'" >&2
    return 32
  fi

  return 0
}
```

| Exit Code | Rule Violated | Fix |
|:---------:|---------------|-----|
| 30 | Empty key | Provide a non-empty key |
| 31 | Length 0 or > 1023 | Shorten the key |
| 32 | Starts with `/` or `\` | Remove leading slash |

---

### Operation: List Buckets

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Credentials | `aliyun sts GetCallerIdentity` | Non-empty UID | HALT; user configures env |
| CLI present | `aliyun --version` | Exit code 0 | Document CLI install |

#### Execution — CLI (Primary Path)

```bash
aliyun oss ListBuckets \
  --ResourceGroupId "{{user.resource_group_id|}}"
```

#### Execution — ossutil (Data-Plane Path)

```bash
ossutil ls
```

#### Post-execution Validation

Parse `$.Buckets[].Name` from JSON; present to user as a table. If `$.Buckets`
is empty, the account has zero buckets in this region scope (note: ListBuckets
is **global** by default — it returns buckets across all regions).

```bash
aliyun oss ListBuckets \
  --output cols=Name,Region,StorageClass,CreationDate rows=Buckets[].{Name,Region,StorageClass,CreationDate}
```

---

### Operation: Create Bucket

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| **Bucket name format (defensive)** | `validate_oss_bucket_name "{{user.bucket_name}}"` (see [Operation: Validate Bucket Name](#operation-validate-bucket-name)) | Exit 0 | **HALT** — show helper's specific error (exit code 10-15) |
| Region supports OSS | `aliyun oss DescribeRegions` (if available) or `ossutil ls oss://` | Region in list | HALT; suggest valid region |
| **Bucket does not exist (defensive)** | `aliyun oss GetBucketInfo --Bucket {{user.bucket_name}}` (expect `NoSuchBucket`) | `NoSuchBucket` error | **HALT** — bucket exists; ask reuse vs new name |
| Quota | RAM policy includes `oss:PutBucket` | Granted | HALT; user adds RAM policy |

> **Bucket name rules (MUST validate via the helper above):**
> - 3-63 characters
> - Lowercase letters, digits, hyphens (`-`) only
> - Must start AND end with a letter or digit
> - No underscores, no consecutive hyphens (`--`), no IP addresses
> - Globally unique across all of Alibaba Cloud (cannot reuse another tenant's name)
>
> The bash helper [`validate_oss_bucket_name`](#operation-validate-bucket-name)
> catches **all** of these rules client-side with **specific** error messages
> (uppercase vs underscore vs length vs ...) BEFORE any API call, avoiding
> the generic `InvalidBucketName` from OSS.

#### Execution — CLI (Primary Path)

```bash
aliyun oss PutBucket \
  --Bucket "{{user.bucket_name}}" \
  --StorageClass "{{user.storage_class|Standard}}" \
  --Acl "{{user.acl|private}}"
```

**Asynchronous note:** `PutBucket` returns immediately. Verify with `GetBucketInfo`.

#### Post-execution Validation

```bash
# Poll until bucket appears
for i in $(seq 1 20); do
  RESULT=$(aliyun oss GetBucketInfo --Bucket "{{user.bucket_name}}" 2>&1)
  if echo "$RESULT" | jq -e '.Bucket.Name' >/dev/null 2>&1; then
    echo "Bucket created: {{user.bucket_name}}"
    break
  fi
  sleep 3
done
```

Report:
- `{{output.bucket_name}}` from `$.Bucket.Name`
- Creation date from `$.Bucket.CreationDate`
- Internal/extranet endpoints from `$.Bucket.IntranetEndpoint` and `$.Bucket.ExtranetEndpoint`

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidBucketName` | 0 | — | HALT; show naming rules |
| `BucketAlreadyExists` | 0 | — | HALT; suggest reuse or new name |
| `TooManyBuckets` / `QuotaExceeded` | 0 | — | HALT; raise quota via ticket |
| `SignatureDoesNotMatch` | 1 | — | Check SK; retry once |
| Throttling / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Delete Bucket

#### Pre-flight (Safety Gate)

> **Defensive check:** `validate_oss_bucket_name "{{user.bucket_name}}"`
> MUST return exit 0 before proceeding. See
> [Operation: Validate Bucket Name](#operation-validate-bucket-name).

- **MUST** obtain explicit confirmation: deletion is irreversible.
- **MUST verify bucket is empty** (no objects, no incomplete multipart uploads).
  Use `GetBucketStat` to check `ObjectCount` and `MultipartUploadCount`.
- **MUST warn** if bucket has versioning enabled — current and delete-marker
  versions will also be removed only if lifecycle purge exists. Recommend
  suspending versioning first if data preservation is needed.

#### Execution — CLI (Primary Path)

```bash
# Step 1: Verify empty
OBJECTS=$(aliyun oss GetBucketStat --Bucket "{{user.bucket_name}}" \
  --output cols=ObjectCount rows=ObjectCount)
UPLOADS=$(aliyun oss GetBucketStat --Bucket "{{user.bucket_name}}" \
  --output cols=MultipartUploadCount rows=MultipartUploadCount)
[ "$OBJECTS" = "0" ] && [ "$UPLOADS" = "0" ] || { echo "Bucket not empty"; exit 1; }

# Step 2: Delete
aliyun oss DeleteBucket --Bucket "{{user.bucket_name}}"
```

#### Post-execution Validation

Poll `GetBucketInfo` until `NoSuchBucket`:

```bash
for i in $(seq 1 20); do
  RESULT=$(aliyun oss GetBucketInfo --Bucket "{{user.bucket_name}}" 2>&1)
  if echo "$RESULT" | grep -q "NoSuchBucket"; then
    echo "Bucket deleted: {{user.bucket_name}}"
    break
  fi
  sleep 3
done
```

#### Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| `BucketNotEmpty` | HALT; user must empty bucket or abort |
| `NoSuchBucket` | Inform user; treat as success (idempotent) |

---

### Operation: Get Bucket Info / Describe Bucket

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0. (Helper: [Operation: Validate Bucket Name](#operation-validate-bucket-name))

#### Execution — CLI (Primary Path)

```bash
aliyun oss GetBucketInfo --Bucket "{{user.bucket_name}}"
```

#### Execution — ossutil (Data-Plane Path)

```bash
ossutil stat oss://{{user.bucket_name}}
```

#### Present to User

| Field | JSON Path | Notes |
|-------|-----------|-------|
| Name | `$.Bucket.Name` | Bucket name |
| Region | `$.Bucket.Region` | Actual region |
| Storage Class | `$.Bucket.StorageClass` | Default storage class |
| Creation Date | `$.Bucket.CreationDate` | ISO 8601 |
| Extranet Endpoint | `$.Bucket.ExtranetEndpoint` | Public endpoint |
| Intranet Endpoint | `$.Bucket.IntranetEndpoint` | Internal VPC endpoint |
| Owner | `$.Bucket.Owner.Id` | Owner UID |
| Versioning | `$.Bucket.Versioning` | Enabled / Suspended / null |

---

### Operation: Get / Set Bucket ACL

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — Get ACL (CLI)

```bash
aliyun oss GetBucketAcl --Bucket "{{user.bucket_name}}"
```

Parse `$.AccessControlList.Grant`.

#### Execution — Set ACL (CLI)

```bash
aliyun oss PutBucketAcl \
  --Bucket "{{user.bucket_name}}" \
  --Acl "{{user.acl|private}}"
```

> **Available ACLs:** `private` (default), `public-read`, `public-read-write`.
> ⚠️ `public-read-write` removes ALL access control — only use for truly
> public-static assets (e.g., a static website origin).

#### Present to User

| Field | JSON Path | Notes |
|-------|-----------|-------|
| ACL | `$.AccessControlList.Grant` | private / public-read / public-read-write |

---

### Operation: Get / Set Bucket Lifecycle

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

Lifecycle rules transition objects between storage classes or expire them
automatically. **Cost Pillar** — this is the #1 cost optimization lever.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketLifecycle --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

Provide a JSON config file. See `assets/example-config.yaml` for the lifecycle
rule schema.

```bash
aliyun oss PutBucketLifecycle \
  --Bucket "{{user.bucket_name}}" \
  --LifecycleConfiguration file:///path/to/lifecycle.json
```

**Sample lifecycle rule structure** (illustrative):

```json
{
  "LifecycleRules": {
    "LifecycleRule": [
      {
        "ID": "tier-down-logs",
        "Status": "Enabled",
        "Prefix": "logs/",
        "Transition": [
          { "Days": 30, "StorageClass": "IA" },
          { "Days": 90, "StorageClass": "Archive" },
          { "Days": 365, "StorageClass": "ColdArchive" }
        ],
        "Expiration": { "Days": 2555 }
      }
    ]
  }
}
```

> **Storage class transition cost:** Each transition generates a request fee
> and may generate a data retrieval fee from the source class. Optimize
> transition days to balance cost savings vs. transition cost.

#### Post-execution Validation

```bash
aliyun oss GetBucketLifecycle --Bucket "{{user.bucket_name}}" \
  --output cols=ID,Status,Prefix rows=LifecycleRules.LifecycleRule[].{ID,Status,Prefix}
```

---

### Operation: Get / Set Bucket Referer (Anti-Leech)

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketReferer --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketReferer \
  --Bucket "{{user.bucket_name}}" \
  --RefererConfiguration file:///path/to/referer.json
```

**Sample referer config:**

```json
{
  "AllowEmptyReferer": false,
  "RefererList": [
    "https://example.com",
    "https://*.example.com"
  ]
}
```

> ⚠️ Setting `AllowEmptyReferer=true` weakens anti-leech protection. Default `false`.

---

### Operation: Get / Set Bucket CORS

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketCors --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketCors \
  --Bucket "{{user.bucket_name}}" \
  --CORSConfiguration file:///path/to/cors.json
```

**Sample CORS config:**

```json
{
  "CORSRules": {
    "CORSRule": [
      {
        "AllowedOrigin": ["https://example.com"],
        "AllowedMethod": ["GET", "HEAD"],
        "AllowedHeader": ["*"],
        "ExposeHeader": ["ETag", "x-oss-request-id"],
        "MaxAgeSeconds": 3600
      }
    ]
  }
}
```

---

### Operation: Get / Set Bucket Logging

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketLogging --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketLogging \
  --Bucket "{{user.bucket_name}}" \
  --BucketLoggingStatus file:///path/to/logging.json
```

**Sample logging config:**

```json
{
  "LoggingEnabled": {
    "TargetBucket": "my-log-bucket",
    "TargetPrefix": "access-log/"
  }
}
```

> ⚠️ The log destination bucket MUST be in the same region as the source.

---

### Operation: Get / Set Static Website Hosting

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketWebsite --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketWebsite \
  --Bucket "{{user.bucket_name}}" \
  --WebsiteConfiguration file:///path/to/website.json
```

**Sample website config:**

```json
{
  "IndexDocument": { "Suffix": "index.html" },
  "ErrorDocument": { "Key": "error.html" }
}
```

#### Execution — Delete (CLI)

```bash
aliyun oss DeleteBucketWebsite --Bucket "{{user.bucket_name}}"
```

---

### Operation: Get / Set Cross-Region Replication (CRR)

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0;
> same for `{{user.dest_bucket_name}}` if set.

#### Pre-flight (Safety Gate)

- **MUST obtain explicit confirmation:** CRR incurs replication traffic fees.
- Both source and destination buckets MUST exist; destination must NOT have
  versioning suspended (CRR requires versioning enabled on both).
- Source bucket versioning is auto-enabled by `PutBucketReplication`.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketReplication --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketReplication \
  --Bucket "{{user.bucket_name}}" \
  --ReplicationConfiguration file:///path/to/replication.json
```

**Sample replication config:**

```json
{
  "Rules": {
    "ReplicationRule": [
      {
        "ID": "replicate-all",
        "Status": "Enabled",
        "Prefix": "",
        "Destination": { "Bucket": "destination-bucket-name", "Location": "oss-cn-shanghai" }
      }
    ]
  }
}
```

#### Post-execution Validation

Poll `GetBucketReplication` until rule status is `active` (max 600s).

---

### Operation: Get / Set Bucket Policy

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

> **Security Pillar:** Bucket policies are JSON IAM documents attached to a
> bucket. They OVERRIDE bucket ACLs for the principals they mention.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketPolicy --Bucket "{{user.bucket_name}}"
```

> **Note:** `GetBucketPolicy` returns 404 (`NoSuchBucketPolicy`) if no policy
> is set — this is normal, not an error.

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketPolicy \
  --Bucket "{{user.bucket_name}}" \
  --Policy file:///path/to/policy.json
```

**Sample bucket policy (grant RAM user `alice` read-only access):**

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": ["acs:ram::1234567890*:user/alice"],
      "Action": ["oss:GetObject"],
      "Resource": ["acs:oss:*:*:{{user.bucket_name}}/*"]
    }
  ]
}
```

> ⚠️ Always validate the policy JSON before applying. Use a JSON schema
> validator; a malformed policy will silently disable all cross-principal
> access.

---

### Operation: Get / Set Bucket Versioning

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketVersioning --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketVersioning \
  --Bucket "{{user.bucket_name}}" \
  --VersioningConfiguration file:///path/to/versioning.json
```

**Versioning config:**

```json
{ "Status": "Enabled" }
```

> ⚠️ Versioning cannot be disabled once enabled — it can only be **Suspended**.
> Suspending retains existing versions but stops creating new ones.

---

### Operation: Get / Set Bucket Encryption

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — Get (CLI)

```bash
aliyun oss GetBucketEncryption --Bucket "{{user.bucket_name}}"
```

#### Execution — Set (CLI)

```bash
aliyun oss PutBucketEncryption \
  --Bucket "{{user.bucket_name}}" \
  --BucketEncryptionConfiguration file:///path/to/encryption.json
```

**Sample encryption config (SSE-KMS):**

```json
{
  "Rule": [
    {
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "KMS",
        "KMSMasterKeyID": "{{user.kms_key_id}}"
      }
    }
  ]
}
```

> **Two SSE modes:** `SSE-OSS` (OSS-managed keys, free) vs `SSE-KMS` (KMS
> managed, incurs KMS API fees). For regulated workloads, use `SSE-KMS`.

---

### Operation: List Objects

> **Defensive:** `validate_oss_bucket_name "{{user.bucket_name}}"` ⇒ exit 0.

#### Execution — CLI (Control-Plane API)

```bash
aliyun oss ListObjects \
  --Bucket "{{user.bucket_name}}" \
  --Prefix "{{user.prefix|}}" \
  --MaxKeys "{{user.max_keys|1000}}" \
  --Marker "{{user.marker|}}"
```

> **v1 vs v2:** The OpenAPI exposes `ListObjects` (v1) and `ListObjectsV2`
> (v2). Prefer v2 for new code (returns `Key` directly, not `Contents[].Key`).

#### Execution — ossutil (Data-Plane Path)

```bash
# Paginated listing of all objects
ossutil ls oss://{{user.bucket_name}}/{{user.prefix|}} -r

# With metadata
ossutil ls oss://{{user.bucket_name}}/{{user.prefix|}} --meta
```

#### Post-execution Validation

Present `$.Contents[].Key`, `$.Contents[].Size`, `$.Contents[].LastModified`
from the API response, or human-friendly output from `ossutil ls`.

---

### Operation: Upload Object (Small, < 100 MB)

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` ⇒ exit 0.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Local file exists | `ls -la {{user.local_path}}` | File exists | HALT |
| File size | `stat -c %s {{user.local_path}}` | < 100 MB | Use multipart upload instead |
| Bucket exists | `GetBucketInfo` | Exists | HALT |
| Credentials | `aliyun sts GetCallerIdentity` | OK | HALT |

#### Execution — ossutil (Recommended)

```bash
ossutil cp "{{user.local_path}}" \
  oss://{{user.bucket_name}}/{{user.object_key}} \
  --metadata "x-oss-meta-source=agent-upload"
```

> **ACL override:** Add `--acl public-read` for a single public object.

#### Execution — CLI (Alternate)

```bash
# Requires the local file content as a base64-encoded body; not recommended
# for files > 1 MB. Prefer ossutil.
aliyun oss PutObject \
  --Bucket "{{user.bucket_name}}" \
  --Key "{{user.object_key}}" \
  --Body "fileb://{{user.local_path}}"
```

#### Post-execution Validation

```bash
ossutil stat oss://{{user.bucket_name}}/{{user.object_key}}
```

Capture `{{output.object_etag}}` from `Etag` field for integrity verification.

#### Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| `NoSuchBucket` | HALT; verify bucket name |
| `AccessDenied` | HALT; verify RAM policy (needs `oss:PutObject`) |
| `InvalidObjectName` | HALT; show key naming rules |
| `RequestTimeTooSkewed` | Sync system clock |

---

### Operation: Upload Object (Large / Multipart)

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` ⇒ exit 0.

For files > 100 MB, OSS requires multipart upload.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| File size | `stat -c %s` | > 100 MB | Use small upload instead |
| Multipart available | `ossutil` version ≥ 1.7.0 | OK | Upgrade ossutil |

#### Execution — ossutil (Auto Multipart)

```bash
# ossutil automatically switches to multipart for large files
ossutil cp "{{user.local_path}}" \
  oss://{{user.bucket_name}}/{{user.object_key}} \
  --part-size 104857600 \
  --thread-count 10 \
  --checkpoint-dir /tmp/ossutil-checkpoint
```

> **Resumability:** `ossutil` writes a checkpoint file. Re-running the same
> command resumes from the last completed part. Delete the checkpoint file
> to start over.

#### Execution — SDK (Programmatic, ≥ 48.8 TB)

**For files in the 100 MB – 48.8 TB range, use the OSS Go SDK V2 multipart API.**
See [API & SDK Usage](references/api-sdk-usage.md#multipart-upload).

#### Post-execution Validation

```bash
ossutil stat oss://{{user.bucket_name}}/{{user.object_key}} \
  | grep -E "(Etag|Content-Length|StorageClass)"
```

> **Storage class:** Newly uploaded large files inherit the bucket's default
> storage class unless overridden with `--meta x-oss-storage-class=IA`.

---

### Operation: Download Object

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` ⇒ exit 0.

#### Execution — ossutil (Recommended)

```bash
ossutil cp \
  oss://{{user.bucket_name}}/{{user.object_key}} \
  "{{user.local_path}}"
```

#### Execution — CLI (Small Objects)

```bash
# Returns the object content as base64
aliyun oss GetObject \
  --Bucket "{{user.bucket_name}}" \
  --Key "{{user.object_key}}" \
  --output cols=Body rows=Body
```

> **Avoid `aliyun oss GetObject` for files > 1 MB** — base64 output bloats
> the response. Use ossutil for binary downloads.

#### Post-execution Validation

```bash
ls -la "{{user.local_path}}"
ossutil stat oss://{{user.bucket_name}}/{{user.object_key}}
```

Compare local size and ETag to the bucket's metadata.

---

### Operation: Delete Object(s)

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` (or pattern) ⇒ exit 0.

#### Pre-flight (Safety Gate)

- **MUST obtain explicit confirmation:** deletion is irreversible (unless
  versioning is enabled, in which case a delete marker is created).
- For bulk deletion (`--include` patterns), warn the user that the operation
  can affect many files; require an explicit count threshold.

#### Execution — Single Object (ossutil)

```bash
ossutil rm oss://{{user.bucket_name}}/{{user.object_key}}
```

#### Execution — Bulk Delete (ossutil)

```bash
# Delete all objects matching prefix
ossutil rm oss://{{user.bucket_name}}/{{user.prefix}} -r

# Delete all objects whose names match a wildcard
ossutil rm oss://{{user.bucket_name}} --include "*.log" -r
```

> **Pre-count safeguard:** Before `-r` deletion, run a `ls` and require
> the user to confirm the count matches expectations.

#### Post-execution Validation

```bash
ossutil ls oss://{{user.bucket_name}}/{{user.prefix}} | wc -l
```

---

### Operation: Copy Object

> **Defensive:** `validate_oss_bucket_name` for source & dest ⇒ exit 0;
> `validate_oss_object_key` for src & dest keys ⇒ exit 0.

#### Execution — CLI (Server-Side Copy)

```bash
aliyun oss CopyObject \
  --Bucket "{{user.dest_bucket}}" \
  --Key "{{user.dest_key}}" \
  --CopySource "/{{user.src_bucket}}/{{user.src_key}}"
```

#### Post-execution Validation

```bash
ossutil stat oss://{{user.dest_bucket}}/{{user.dest_key}}
```

> **Cross-region copy:** For > 1 GB cross-region copies, prefer
> `ossutil cp` with `--bigfile-threshold` and `--part-size`. Or use
> cross-region replication (CRR) for ongoing sync.

---

### Operation: Generate Presigned URL

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` ⇒ exit 0.

For temporary access without embedding credentials in client apps.

#### Execution — ossutil

```bash
# Generate a GET presigned URL valid for 3600 seconds
ossutil sign \
  oss://{{user.bucket_name}}/{{user.object_key}} \
  --timeout 3600
```

#### Execution — SDK (For Programmatic Use)

See [API & SDK Usage](references/api-sdk-usage.md#presigned-url).

#### Present to User

Output the URL string; remind the user that:
- The URL is sensitive — anyone with the URL can access the object.
- `timeout` is in seconds; default 60s, max 32400s (9 hours) for OSS.
- For longer-lived access, use RAM `sts:AssumeRole` with token expiry.

---

### Operation: Restore Archived Object

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` ⇒ exit 0.

> **Stability Pillar:** Restoring an Archive or ColdArchive object creates a
> temporary read-only copy in Standard storage.

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Object exists | `ossutil stat` | OK | HALT |
| Storage class | `ossutil stat` → `X-Oss-Storage-Class` | `Archive` or `ColdArchive` | HALT (already Standard / IA) |
| Restored state | `X-Oss-Restore` header | Either absent (not yet) or `ongoing-request="false"` (ready) | Skip if already restored |

#### Execution — CLI (RestoreObject)

```bash
aliyun oss RestoreObject \
  --Bucket "{{user.bucket_name}}" \
  --Key "{{user.object_key}}" \
  --Days "{{user.days|7}}" \
  --JobParameters '{"Tier":"Standard"}'
```

> **Restore speed tiers:** `Standard` (default, hours) / `Expedited` (1 min,
> extra fee) / `Bulk` (up to 5 hours, free for Archive).
> For `ColdArchive`: only `Standard` and `Bulk` are supported; no `Expedited`.

#### Post-execution Validation

Poll `ossutil stat` until `X-Oss-Restore` header shows `ongoing-request="false"`:

```bash
for i in $(seq 1 480); do
  HEADER=$(ossutil stat oss://{{user.bucket_name}}/{{user.object_key}} 2>&1 | grep "X-Oss-Restore")
  if echo "$HEADER" | grep -q 'ongoing-request="false"'; then
    echo "Restored"
    break
  fi
  sleep 30
done
```

#### Failure Recovery

| Error pattern | Agent Action |
|---------------|--------------|
| `ArchiveNotSupported` | HALT; verify storage class is `Archive` or `ColdArchive` |
| `RestoreAlreadyInProgress` | Inform user; keep polling |

---

### Operation: List Multipart Uploads (and Abort)

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` (for Abort) ⇒ exit 0.

#### Execution — CLI

```bash
aliyun oss ListMultipartUploads \
  --Bucket "{{user.bucket_name}}" \
  --Prefix "{{user.prefix|}}"
```

#### Execution — Abort (CLI)

```bash
aliyun oss AbortMultipartUpload \
  --Bucket "{{user.bucket_name}}" \
  --Key "{{user.object_key}}" \
  --UploadId "{{user.upload_id}}"
```

> **Stability Pillar — Storage leak prevention:** Incomplete multipart uploads
> continue to consume storage. **List + Abort** incomplete uploads periodically
> (or set lifecycle rule: `AbortMultipartUpload.DaysAfterInitiation: 7`).

---

### Operation: Image Processing

> **Defensive:** `validate_oss_bucket_name` ⇒ exit 0;
> `validate_oss_object_key` ⇒ exit 0.

OSS supports inline image processing via the `?x-oss-process=` query parameter
(only on **Standard or IA** objects; not on Archive / ColdArchive).

#### Resize, Watermark, Format Conversion

```bash
# Resize to 200x200
ossutil cp \
  oss://{{user.bucket_name}}/{{user.object_key}}?x-oss-process=image/resize,m_fixed,h_200,w_200 \
  "{{user.local_path}}"

# Add watermark
ossutil cp \
  oss://{{user.bucket_name}}/{{user.object_key}}?x-oss-process=image/watermark,text_<base64-encoded-text> \
  "{{user.local_path}}"
```

> See [Image Processing Parameters](https://help.aliyun.com/zh/oss/user-guide/image-processing-parameters-50) for the full grammar.

---

## Prerequisites

1. **Install `aliyun` CLI** (primary control-plane path):

   ```bash
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
   # Verify
   aliyun --version
   ```

2. **Install `ossutil`** (primary data-plane path — strongly recommended):

   ```bash
   # macOS / Linux
   curl -O https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64
   chmod 755 ossutil64
   sudo mv ossutil64 /usr/local/bin/ossutil

   # Verify
   ossutil --version
   ```

3. **Bootstrap Go runtime** (for JIT SDK fallback):

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

4. **Configure Credentials** (env vars — recommended for agent execution):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"   # always mask in displayed output
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

   > **IMPORTANT:** When outputting the above commands, the agent MUST replace
   > `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` with `****`. Never resolve the
   > secret to its real value in any visible output.

5. **Configure `ossutil`** (one-time):

   ```bash
   ossutil config
   # Interactive: enter AK, SK, default region, optional endpoint
   # Writes ~/.ossutilconfig (JSON)
   ```

6. **Verify Configuration**:

   ```bash
   aliyun oss ListBuckets
   ossutil ls
   ```

> **Security:** Never commit `.env` or `~/.ossutilconfig` to version control
> (already in `.gitignore`). All credentials use `{{env.*}}` placeholders in
> generated skills — never real values.

---

## Reference Directory

- [Core Concepts](references/core-concepts.md) — OSS architecture, storage classes, regions, endpoint format, durability
- [API & SDK Usage](references/api-sdk-usage.md) — Complete OpenAPI / SDK operation mapping, Go SDK V2 snippets, multipart upload walkthrough
- [CLI Usage](references/cli-usage.md) — `aliyun oss` + `ossutil` command reference, output formatting, polling patterns
- [Troubleshooting Guide](references/troubleshooting.md) — Symptom-based decision tree, error code reference, support escalation
- [Monitoring & Alerts](references/monitoring.md) — CMS metrics (storage, requests, traffic), alert thresholds, request statistics
- [Integration](references/integration.md) — Go SDK setup, `ossutil` config, CI/CD patterns, RAM integration
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar assessment (security, stability, cost, efficiency, performance)

## Operational Best Practices

- **Least privilege:** Use RAM policies with `oss:Action` scoped to specific
  buckets and prefixes; never use `oss:*`.
- **Bucket naming:** Validate bucket name format BEFORE any API call. Names
  with `_` (underscore) or uppercase letters will fail.
- **Cost:** Enable lifecycle rules to tier down Standard → IA → Archive based
  on access patterns. ColdArchive is the cheapest long-term tier.
- **Availability:** Cross-region replication (CRR) for DR; multi-AZ is built-in
  (12 nines durability).
- **Security:** Default ACL is `private`. Use bucket policies and RAM policies
  for fine-grained access. Enable bucket encryption (SSE-KMS for regulated data).
- **Performance:** Use `ossutil` with `--thread-count 10` for large parallel
  transfers. Avoid `GetObject` via `aliyun` CLI for files > 1 MB.
- **Storage hygiene:** List and abort incomplete multipart uploads; they
  consume storage until aborted or lifecycle-purged.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `dual-path`，`aliyun oss` + `ossutil` 已覆盖
  控制面和数据面，无需 code snippets.

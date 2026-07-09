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
  version: "1.1.0"
  last_updated: "2026-06-21"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: >-
    OSS 2019-05-17 (control plane) / https://help.aliyun.com/zh/oss/developer-reference/api-oss-2019-05-17-overview.
    Data plane uses S3-compatible REST API at <bucket>.<endpoint>.
  cli_applicability: sdk-only
  cli_support_evidence: >-
    `aliyun oss <subcommand>` is DEPRECATED — `aliyun --help` itself notes
    "阿里云OSS对象存储（废弃，请使用aliyun ossutil）". It only accepts ossutil
    shorthand verbs (ls, mb, cp, rm, stat, set-acl, set-meta, restore, sign,
    create-symlink, read-symlink, hash, help, config), NOT the OpenAPI operation
    names (ListBuckets / PutBucket / GetBucketInfo / ...) shown in the Operation
    tables below. Those tables document the OpenAPI surface; for actual
    execution, use one of:
      1. `./scripts/oss-skillopt-wrapper.sh <ossutil-verb> [args]` (primary,
         enables self-repair + Langfuse tracing), or
      2. `ossutil <ossutil-verb> [args]` (direct, no SkillOpt), or
      3. OSS Go SDK V2 (`github.com/aliyun/aliyun-oss-go-sdk/oss`) for the
         full API surface including those not in ossutil (lifecycle, CORS,
         replication, policy, encryption, versioning).
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Object Storage Service (OSS) Operations Skill

## Overview

Operational runbook for Alibaba Cloud OSS (12-nines durability). Execution paths:

| Path | When | Examples |
|------|------|----------|
| **Wrapper** → `ossutil` | ossutil-coverable operations | `ls`, `mb`, `cp`, `rm`, `stat`, `set-acl`, `restore`, `sign` |
| **OSS Go SDK V2** | Operations ossutil cannot cover | lifecycle, CORS, logging, referer, replication, policy, versioning, encryption, multipart |

> **Do not use the web console as the primary agent execution path.**

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path (control plane) | **MANDATORY**: Always prefer `./scripts/oss-skillopt-wrapper.sh` for ossutil-coverable operations; fallback to `ossutil` only when wrapper is unavailable. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |
| CLI path (data plane) | For upload/download/list, use `ossutil` directly (native data-plane tool). | [CLI](references/cli-usage.md) |
| Non-ossutil ops | Use OSS Go SDK V2 (`github.com/aliyun/aliyun-oss-go-sdk/oss`). | [API & SDK](references/api-sdk-usage.md) |
| Credentials | Read `{{env.*}}` from environment; wrapper auto-loads `.env` — never ask user to paste secrets. | [Integration](references/integration.md), [SkillOpt](references/skillopt-integration.md) |
| GCL | All write operations MUST pass GCL adversarial review before execution. | [GCL Rubric](references/rubric.md) |

> **`aliyun oss <Operation>` is DEPRECATED.** The operation tables below document the **OpenAPI surface** (PascalCase names: `ListBuckets`, `PutBucket`, ...). The `aliyun oss` CLI subcommand accepts **only ossutil-shorthand verbs** (`ls`, `mb`, `cp`, `rm`, `stat`, `set-acl`, ...). Use the Wrapper or `ossutil` at runtime. See [CLI Usage](references/cli-usage.md) for the full command map.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud OSS" / "Object Storage Service" / "对象存储" / "OSS" / "存储空间" / "Bucket"
- Task involves creating, configuring, listing, or deleting **OSS buckets**
- Task involves **bucket-level features**: ACL, lifecycle, CORS, logging, static website, Referer anti-leech, cross-region replication, bucket policy, encryption, versioning
- Task involves **object operations**: upload, download, copy, move, delete, list, head, restore, presigned URL
- Task involves **multipart uploads**, large file transfers, or resumable uploads
- Task involves **image processing** via `?x-oss-process=` query parameters
- Task involves **data archiving** (Standard / IA / Archive / ColdArchive) and restoring frozen objects
- Task involves **S3-compatible** API calls (e.g., migrate from AWS S3 to OSS)
- User mentions: 访问控制, 读写权限, 公共读, 公共读写, 私有, 防盗链, 跨域设置, 静态网站托管, 镜像回源, 跨区域复制, CRR, 事件通知, 图片处理, 缩略图, 数据湖, 冷归档, 解冻, lifecycle, multipart, presign, signature URL, RAM policy
- User asks to deploy, configure, troubleshoot, or monitor OSS **via API, SDK, CLI, ossutil, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → `alicloud-billing-ops`
- Task is RAM / permission model only → `alicloud-ram-ops`
- Task is about **NAS file system (NFS/SMB)** → NAS skill (not yet present)
- Task is about **block storage / EBS disks** → `alicloud-ecs-ops`
- Task is about **CDN edge delivery only** (OSS is just origin) → CDN skill
- Task is about **HDFS / Data Lake Analytics** storage backend → data analytics skill
- User insists on **console-only** flows with no API → state limitation

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT conditions with precise triggers; explicit delegation to RAM/CDN/SLS skills |
| 2 | **Structured I/O** | `{{env.*}}` / `{{user.*}}` / `{{output.*}}` placeholders; control-plane + data-plane paths documented |
| 3 | **Explicit Actionable Steps** | Every operation follows Pre-flight → Execute → Validate → Recover pattern (see [CLI](references/cli-usage.md) and [API & SDK](references/api-sdk-usage.md)) |
| 4 | **Complete Failure Strategies** | Error taxonomy ≥ 15 codes; HALT vs retry per type (see [Troubleshooting](references/troubleshooting.md)) |
| 5 | **Absolute Single Responsibility** | One product (OSS), one primary resource (Bucket + Object); CDN/RAM delegated |

### Well-Architected Framework Integration

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | Bucket ACL, RAM Policy, Referer, encryption (SSE-KMS/SSE-OSS), presigned URL | [Well-Architected](references/well-architected-assessment.md) §2.1 |
| **稳定 (Stability)** | Cross-region replication, versioning, lifecycle, multi-AZ durability | [Well-Architected](references/well-architected-assessment.md) §2.2 |
| **成本 (Cost)** | Storage class selection, lifecycle tier-down, request cost | [Well-Architected](references/well-architected-assessment.md) §2.3 |
| **效率 (Efficiency)** | Multipart upload, ossutil, parallel transfer, image processing, batch operations | [Well-Architected](references/well-architected-assessment.md) §2.4 |
| **性能 (Performance)** | CDN integration, transfer acceleration, max-PUT-object size (48.8 TB), QPS limits | [Well-Architected](references/well-architected-assessment.md) §2.5 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Alibaba Cloud AK | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Alibaba Cloud SK | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region (e.g., `cn-hangzhou`) | Ask once; reuse |
| `{{user.bucket_name}}` | Bucket name (3-63 chars, lowercase, no underscores) | Ask once; validate via `validate_oss_bucket_name` |
| `{{user.object_key}}` | Object key (full path within bucket) | Ask once; validate via `validate_oss_object_key` |
| `{{user.storage_class}}` | `Standard` / `IA` / `Archive` / `ColdArchive` / `DeepColdArchive` | Ask once; default `Standard` |
| `{{user.acl}}` | `private` / `public-read` / `public-read-write` | Ask once; default `private` |
| `{{user.endpoint}}` | OSS endpoint (e.g., `oss-cn-hangzhou.aliyuncs.com`) | Derive from region or ask |
| `{{user.local_path}}` | Local file path for upload/download | Ask once |
| `{{output.bucket_name}}` | From last API response | Parse from `$.Bucket.Name` or `$.Buckets[].Name` |
| `{{output.object_etag}}` | Object ETag from response | Parse from `$.ETag` or response header |
| `{{output.request_id}}` | Request ID for support / correlation | Parse from `$.RequestId` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.
>
> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

### Defensive Validation (MANDATORY — Before Every Bucket/Object Operation)

Before executing ANY operation that takes a `Bucket` or `Object Key` parameter, the Agent **MUST** run:

```bash
# Source validation helpers from cli-usage.md
# validate_oss_bucket_name <name> — exits 0 on valid, non-zero with specific error
# validate_oss_object_key <key> — exits 0 on valid, non-zero with specific error

if ! validate_oss_bucket_name "{{user.bucket_name}}"; then
  echo "[HALT] Bucket name validation failed — fix the name and retry."
  exit 1
fi

if ! validate_oss_object_key "{{user.object_key}}"; then
  echo "[HALT] Object key validation failed — fix the key and retry."
  exit 1
fi
```

> Full validation functions (with exit code reference 10-15 for bucket, 30-32 for object key) at [CLI Usage → Defensive Validation Helpers](references/cli-usage.md#defensive-validation-helpers).

## API & Response Conventions (Agent-Readable)

- **OpenAPI reference:** `https://help.aliyun.com/zh/oss/developer-reference/api-oss-2019-05-17-overview`
- **Errors:** OSS uses `Code` and `Message` in error response body + HTTP status. See [Troubleshooting](references/troubleshooting.md) for ≥15 error codes.
- **Timestamps:** ISO 8601 with timezone (e.g., `2026-04-28T10:00:00+08:00`).
- **Idempotency:** Object uploads use `ETag` for verification. Multipart uploads use `uploadId` for resumption.
- **Data plane vs control plane:** Control plane via `ossutil` / wrapper; data plane via REST against `<bucket>.<endpoint>/<key>` (S3-compatible signature v4 when enabled).

### Key Response Fields

| Operation | Key JSON Paths |
|-----------|---------------|
| ListBuckets | `$.Buckets[].{Name,Region,StorageClass,CreationDate}` |
| GetBucketInfo | `$.Bucket.{Name,StorageClass,CreationDate,ExtranetEndpoint,IntranetEndpoint,Owner.Id,Versioning}` |
| GetBucketAcl | `$.AccessControlList.Grant` → `private` / `public-read` / `public-read-write` |
| GetBucketLifecycle | `$.LifecycleRules.LifecycleRule[].{Id,Status,Expiration.Days,Transition.Days}` |
| GetBucketReplication | `$.ReplicationConfiguration.Rules.ReplicationRule[].{ID,Destination.Bucket,Status}` |
| ListObjects | `$.Contents[].{Key,Size,ETag,LastModified,StorageClass}` |
| GetBucketStat | `$.{Storage,ObjectCount,MultipartUploadCount}` |

Full response schemas → [API & SDK Usage](references/api-sdk-usage.md).

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| PutBucket | absent | exists in `GetBucketInfo` | 3s | 60s |
| DeleteBucket | exists, empty | absent (`NoSuchBucket`) | 3s | 60s |
| PutObject (small) | absent | exists (`HeadObject` 200) | n/a | sync |
| PutObject (large, multipart) | absent | exists after `CompleteMultipartUpload` | 5s | 3600s |
| RestoreObject (Archive) | Archive | Restored (`ongoing-request="false"`) | 30s | 14400s |
| RestoreObject (ColdArchive) | ColdArchive | Restored | 30s | 86400s |
| PutBucketReplication | n/a | `active` | 30s | 600s |

## Execution Flows (Agent-Readable)

Every operation follows: **Pre-flight → Execute → Validate → Recover**.

> **EXECUTION MANDATORY RULE:** 所有 CLI 步骤优先通过 `./scripts/oss-skillopt-wrapper.sh` 运行；wrapper 不可用时降级到 `ossutil`；ossutil 无法覆盖的操作使用 OSS Go SDK V2。参考 `## Runtime Rules`。

### Operation Index

| # | Operation | Tool Path | Key Variables | Reference |
|---|-----------|-----------|---------------|-----------|
| 1 | **Validate Bucket Name** | Bash helper | `{{user.bucket_name}}` | [CLI → Defensive Validation](references/cli-usage.md#defensive-validation-helpers) |
| 2 | **Validate Object Key** | Bash helper | `{{user.object_key}}` | [CLI → Defensive Validation](references/cli-usage.md#defensive-validation-helpers) |
| 3 | **List Buckets** | Wrapper: `./scripts/oss-skillopt-wrapper.sh ls` · Fallback: `ossutil ls` | — | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 4 | **Create Bucket** | Wrapper: `./scripts/oss-skillopt-wrapper.sh mb oss://{{user.bucket_name}} --storage-class "{{user.storage_class|Standard}}" --acl "{{user.acl|private}}"` · Fallback: `ossutil mb` | `{{user.bucket_name}}`, `{{user.storage_class}}`, `{{user.acl}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 5 | **Delete Bucket** | Wrapper: `./scripts/oss-skillopt-wrapper.sh rm oss://{{user.bucket_name}}` · Fallback: `ossutil rm` | `{{user.bucket_name}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 6 | **Get Bucket Info** | Wrapper: `./scripts/oss-skillopt-wrapper.sh stat oss://{{user.bucket_name}}` · Fallback: `ossutil stat` | `{{user.bucket_name}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 7 | **Get/Set Bucket ACL** | Wrapper: `./scripts/oss-skillopt-wrapper.sh stat` (get) / `set-acl` (set) · Fallback: `ossutil stat` / `ossutil set-acl` | `{{user.bucket_name}}`, `{{user.acl}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 8 | **Get/Set Bucket Lifecycle** | OSS Go SDK V2 (`GetBucketLifecycle` / `PutBucketLifecycle`) | `{{user.bucket_name}}`, lifecycle rules JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 9 | **Get/Set Bucket Referer** | OSS Go SDK V2 (`GetBucketReferer` / `PutBucketReferer`) | `{{user.bucket_name}}`, referer config JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 10 | **Get/Set Bucket CORS** | OSS Go SDK V2 (`GetBucketCors` / `PutBucketCors`) | `{{user.bucket_name}}`, CORS config JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 11 | **Get/Set Bucket Logging** | OSS Go SDK V2 (`GetBucketLogging` / `PutBucketLogging`) | `{{user.bucket_name}}`, logging config JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 12 | **Get/Set Static Website** | OSS Go SDK V2 (`GetBucketWebsite` / `PutBucketWebsite`) | `{{user.bucket_name}}`, website config JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 13 | **Get/Set CRR** | OSS Go SDK V2 (`GetBucketReplication` / `PutBucketReplication`) | `{{user.bucket_name}}`, `{{user.dest_bucket_name}}`, replication config JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 14 | **Get/Set Bucket Policy** | OSS Go SDK V2 (`GetBucketPolicy` / `PutBucketPolicy`) | `{{user.bucket_name}}`, policy JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 15 | **Get/Set Bucket Versioning** | OSS Go SDK V2 (`GetBucketVersioning` / `PutBucketVersioning`) | `{{user.bucket_name}}`, versioning config JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 16 | **Get/Set Bucket Encryption** | OSS Go SDK V2 (`GetBucketEncryption` / `PutBucketEncryption`) | `{{user.bucket_name}}`, encryption config JSON | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 17 | **List Objects** | Wrapper: `./scripts/oss-skillopt-wrapper.sh ls oss://{{user.bucket_name}}/{{user.prefix|}} -r` · Fallback: `ossutil ls` | `{{user.bucket_name}}`, `{{user.prefix}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 18 | **Upload Object (Small)** | `ossutil cp "{{user.local_path}}" oss://{{user.bucket_name}}/{{user.object_key}}` | `{{user.local_path}}`, `{{user.bucket_name}}`, `{{user.object_key}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 19 | **Upload Object (Large/Multipart)** | `ossutil cp --part-size 104857600 --thread-count 10 --checkpoint-dir /tmp/ossutil-checkpoint` | `{{user.local_path}}`, `{{user.bucket_name}}`, `{{user.object_key}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 20 | **Download Object** | `ossutil cp oss://{{user.bucket_name}}/{{user.object_key}} "{{user.local_path}}"` | `{{user.bucket_name}}`, `{{user.object_key}}`, `{{user.local_path}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 21 | **Delete Object(s)** | `ossutil rm oss://{{user.bucket_name}}/{{user.object_key}}` · Bulk: `ossutil rm oss://{{user.bucket_name}}/{{user.prefix}} -r` | `{{user.bucket_name}}`, `{{user.object_key}}`, `{{user.prefix}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 22 | **Copy Object** | Wrapper: `./scripts/oss-skillopt-wrapper.sh cp oss://{{user.src_bucket}}/{{user.src_key}} oss://{{user.dest_bucket}}/{{user.dest_key}}` · Fallback: `ossutil cp` | `{{user.src_bucket}}`, `{{user.src_key}}`, `{{user.dest_bucket}}`, `{{user.dest_key}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 23 | **Generate Presigned URL** | `ossutil sign oss://{{user.bucket_name}}/{{user.object_key}} --timeout 3600` | `{{user.bucket_name}}`, `{{user.object_key}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 24 | **Restore Archived Object** | Wrapper: `./scripts/oss-skillopt-wrapper.sh restore oss://{{user.bucket_name}}/{{user.object_key}}` · Fallback: `ossutil restore` | `{{user.bucket_name}}`, `{{user.object_key}}` | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |
| 25 | **List/Abort Multipart Uploads** | OSS Go SDK V2 (`ListMultipartUploads` / `AbortMultipartUpload`) | `{{user.bucket_name}}`, `{{user.object_key}}`, `uploadId` | [API & SDK](references/api-sdk-usage.md#sdk-operations-map-control-plane-openapi-2019-05-17) |
| 26 | **Image Processing** | `ossutil cp oss://{{user.bucket_name}}/{{user.object_key}}?x-oss-process=image/... "{{user.local_path}}"` | `{{user.bucket_name}}`, `{{user.object_key}}`, image params | [CLI](references/cli-usage.md#command-map--ossutil-data-plane) |

> **Pre-flight Checks (common to all operations):**
> 1. Credentials valid: `aliyun sts GetCallerIdentity` → non-empty UID
> 2. Bucket name valid: `validate_oss_bucket_name` → exit 0
> 3. Object key valid (if applicable): `validate_oss_object_key` → exit 0
> 4. Bucket exists (for existing-bucket ops): `ossutil stat oss://{{user.bucket_name}}` → no error
> 5. Wrapper present (for wrapper path): `ls alicloud-oss-ops/scripts/oss-skillopt-wrapper.sh` → file exists
>
> **Post-execution Validation (common):**
> - Poll state transition table above for async operations
> - Capture `{{output.request_id}}` from response for correlation
> - For object ops: verify via `ossutil stat oss://{{user.bucket_name}}/{{user.object_key}}`
>
> **Failure Recovery (common):** See [Troubleshooting](references/troubleshooting.md) for error taxonomy, diagnostic order, and symptom-based decision tree.

## Prerequisites

1. **`aliyun` CLI** — `curl -fsSL https://aliyuncli.alicdn.com/install.sh | bash`
2. **`ossutil`** — `curl -O https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64 && chmod +x ossutil64 && sudo mv ossutil64 /usr/local/bin/ossutil`
3. **Go runtime** (for SDK fallback) — `./alicloud-jit-setup.sh` or see [Integration](references/integration.md)
4. **Credentials** — set `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` / `ALIBABA_CLOUD_REGION_ID`; **NEVER** output the secret value — always display as `****`
5. **Configure ossutil** — `ossutil config` (one-time interactive; writes `~/.ossutilconfig`)
6. **Verify** — `cd alicloud-oss-ops && ./scripts/oss-skillopt-wrapper.sh ls` (fallback: `ossutil ls`)

> **Security:** Never commit `.env` or `~/.ossutilconfig` to version control. Full setup guide → [Integration](references/integration.md).

## Reference Directory

- [Core Concepts](references/core-concepts.md) — OSS architecture, storage classes, regions, endpoint format, durability
- [API & SDK Usage](references/api-sdk-usage.md) — Complete OpenAPI / SDK operation mapping, Go SDK V2 snippets, multipart upload walkthrough
- [CLI Usage](references/cli-usage.md) — `aliyun oss` + `ossutil` command reference, output formatting, polling patterns, defensive validation helpers
- [Troubleshooting Guide](references/troubleshooting.md) — Symptom-based decision tree, error code reference, support escalation
- [Monitoring & Alerts](references/monitoring.md) — CMS metrics (storage, requests, traffic), alert thresholds, request statistics
- [Integration](references/integration.md) — Go SDK setup, `ossutil` config, CI/CD patterns, RAM integration
- [Well-Architected Assessment](references/well-architected-assessment.md) — Five-pillar assessment (security, stability, cost, efficiency, performance)
- [Runtime Harness Integration](references/skillopt-integration.md) — Runtime Harness wrapper for self-repair, dynamic optimization, and Langfuse tracing
- [GCL Rubric](references/rubric.md) — Phase 5 extension GCL rubric (bucket/object delete, ACL/policy, wrapper compliance)
- [GCL Prompt Templates](references/prompt-templates.md) — Generator & Critic prompt templates for GCL delegation

## Operational Best Practices

| Area | Rule |
|------|------|
| Security | Default ACL `private`; scope RAM policies to specific buckets (`oss:Action`), never `oss:*`; SSE-KMS for regulated data |
| Cost | Lifecycle tier-down: Standard→IA (30d)→Archive (90d)→ColdArchive (365d) |
| Reliability | Enable CRR for DR; versioning for accidental-delete protection |
| Performance | `ossutil --thread-count 10` for bulk transfers; multipart for files > 100 MB |
| Hygiene | Abort incomplete multipart uploads (lifecycle `AbortMultipartUpload.DaysAfterInitiation: 7`) |

## Quality Gate (GCL)

Phase 5 extension rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5 extension, `max_iter=3`) |
| Most-scrutinized | `DeleteBucket` / `ossutil rb` (empty-bucket check; CRR/versioning), `ossutil rm -r` (wildcard mass delete), `public-read-write` ACL |
| Cross-skill delegation | `alicloud-ram-ops` for bucket policy; CDN origin check before bucket delete |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-06-21 | GCL rollout: `references/rubric.md`, `references/prompt-templates.md`, `## Quality Gate (GCL)` section |
| 1.0.2 | 2026-06-18 | Token efficiency optimization: consolidated 26 operations into index table; moved validation helpers to references/cli-usage.md; removed duplicate Go SDK code blocks and per-operation step templates (now in references/). Reduced from ~1400 to ~297 lines. |
| 1.0.1 | 2026-06-16 | Added Microsoft SkillOpt integration for self-repair and dynamic configuration optimization capabilities for OSS operations |
| 1.0.0 | 2026-06-04 | Initial OSS skill with dual-path (CLI/SDK) + ossutil data-plane support |
# Core Concepts — Alibaba Cloud Object Storage Service (OSS)

## Product Overview

Alibaba Cloud **Object Storage Service (OSS)** is a secure, highly durable,
cost-effective cloud object storage service. It is **S3-compatible** at the
REST API layer (via signature v4 or v1) and supports massive scale (single
object up to **48.8 TB**).

| Attribute | Value |
|-----------|-------|
| **Service Name** | Object Storage Service (OSS) |
| **API Version (control plane)** | 2019-05-17 |
| **API Version (data plane)** | S3-compatible (signature v1 by default, v4 supported) |
| **Data Durability** | 99.9999999999% (12 nines) |
| **Service Availability** | 99.995% |
| **Max Object Size** | 48.8 TB |
| **Min Object Size** | 0 bytes (1 byte minimum chargeable) |
| **Max Buckets per Account** | 100 (raiseable via ticket) |
| **Global Endpoint (control plane)** | `oss.aliyuncs.com` |
| **Regional Endpoint (data plane)** | `<bucket>.<region>.aliyuncs.com` |

## Object Model

OSS uses a flat namespace with a single resource type (Object) inside a
container (Bucket). There is **no directory hierarchy** — object keys
containing `/` are not real directories, only lexical path separators that
the console renders as folders.

```
oss://my-bucket/        ← Bucket
  ├── logs/2026-06-04/access.log      ← Object (key: "logs/2026-06-04/access.log")
  ├── images/hero.jpg                  ← Object
  └── archive/2025/db-backup.tar.gz   ← Object
```

> **Key encoding:** Object keys are UTF-8, max 1024 bytes after URL encoding.
> Avoid `?`, `#`, `*` in raw key names — these may need URL encoding.

## Storage Classes

OSS offers five storage classes with different cost / access trade-offs.

| Class | Min Storage Duration | Use Case | Relative Cost |
|-------|---------------------|----------|---------------|
| **Standard** | None | Hot data, frequent access | Baseline |
| **IA (Infrequent Access)** | 30 days | Accessed < 1 / month | ~50% of Standard |
| **Archive** | 60 days | Accessed < 1 / quarter | ~25% of Standard |
| **ColdArchive** | 180 days | Accessed < 1 / year | ~10% of Standard |
| **DeepColdArchive** | 180 days | Disaster recovery, 7+ year retention | ~7.5% of Standard |

> **Important — Early-deletion penalty:** Each class has a minimum storage
> duration. Deleting or transitioning out before the minimum incurs a
> prorated charge equal to the remaining minimum.

| Class | Retrieval | Read |
|-------|-----------|------|
| Standard | Free | Free |
| IA | Per-GB fee (small) | Free |
| Archive | Restore first (3 modes) | Per-GB fee |
| ColdArchive | Restore first (Standard/Bulk) | Per-GB fee |
| DeepColdArchive | Restore first (Standard/Bulk) | Per-GB fee |

## Region / Endpoint Format

| Format | Example | When to Use |
|--------|---------|-------------|
| **Public (default)** | `oss-cn-hangzhou.aliyuncs.com` | Public internet access |
| **Internal** | `oss-cn-hangzhou-internal.aliyuncs.com` | Same-region ECS access (no egress fee) |
| **Accelerate** | `oss-accelerate.aliyuncs.com` | Global upload/download acceleration |
| **Accelerate-Internal** | `oss-accelerate-internal.aliyuncs.com` | Same-region accelerate over VPC |

> **Cost tip:** Use `<region>-internal` endpoints for ECS-to-OSS traffic to
> avoid public egress fees.

## Bucket Naming Rules

- **Length:** 3–63 characters
- **Allowed:** lowercase letters, digits, hyphens (`-`)
- **Must start AND end** with a letter or digit
- **No** underscores, no consecutive hyphens, no IP address form
- **Globally unique** across all of Alibaba Cloud

> Bucket names cannot be reused across tenants (even after the original
> tenant releases the bucket). The namespace is permanent.

## Resource Relationship

```
Account
  └── Bucket (globally unique name)
        ├── Object (key, size, storage class, metadata)
        ├── Lifecycle Rule (transition + expiration)
        ├── CORS Rule
        ├── Replication Rule
        ├── Cross-Region Logging Target (another bucket, same region)
        ├── Static Website Configuration
        ├── Referer (Anti-Leech) Whitelist
        ├── Versioning State
        ├── Encryption Configuration (SSE-OSS / SSE-KMS)
        ├── Access Monitor
        └── Inventory Rule
```

## Authentication & Authorization

OSS supports **three layers** of access control:

1. **Bucket ACL** — coarse-grained (`private` / `public-read` / `public-read-write`)
2. **RAM Policy** — attached to RAM users/roles (action + resource scoping)
3. **Bucket Policy** — JSON IAM doc attached directly to a bucket
   (overrides ACL for the principals it mentions)

> **Precedence:** Bucket Policy > RAM Policy > Bucket ACL (for matching principals).

For temporary access, OSS supports **STS tokens** (short-lived credentials
from `AssumeRole`) — strongly preferred over long-lived AK/SK for apps.

## Multipart Upload

For files > 100 MB (and **required** for files > 5 GB), OSS uses multipart
upload:

1. `InitiateMultipartUpload` → returns `UploadId`
2. Split file into parts (each 100 KB – 5 GB, last part can be smaller)
3. `UploadPart` for each part (parts can be uploaded in parallel)
4. `CompleteMultipartUpload` with ordered `ETag` list
5. `AbortMultipartUpload` to cancel; **always abort incomplete uploads** to
   avoid storage leak

> **Recommended part size:** 100 MB for stable networks, 10–20 MB for
> unreliable networks.

## Data Consistency & SPOF Analysis

OSS is **strongly consistent** for all read-after-write, list, and delete
operations. There is **no SPOF** for the data plane — all data is
replicated across at least 3 zones within a region. For DR, enable
**Cross-Region Replication (CRR)**.

## Access Patterns

| Pattern | Recommendation |
|---------|---------------|
| Static website hosting | PutBucketWebsite + public-read ACL or bucket policy |
| Image processing | `?x-oss-process=image/...` on Standard / IA objects only |
| CDN origin | Set CDN as frontend, OSS bucket as origin; private ACL + CDN auth |
| Log archive | Lifecycle: Standard → IA (30d) → Archive (180d) → Expire (2555d) |
| Static assets for app | Lifecycle tier-down; bucket policy granting only `GetObject` |
| Backup target | Direct upload via SDK; lifecycle: Archive or ColdArchive |

## Quotas and Limits

| Limit | Default | Note |
|-------|---------|------|
| Max buckets per account | 100 | Per region; raiseable |
| Max object size | 48.8 TB | Multipart required > 5 GB |
| Max part size | 5 GB | Per `UploadPart` call |
| Max part count | 10,000 | Per object |
| Max key length | 1024 bytes | URL-encoded |
| Max prefix list | 1000 per page | `ListObjects` pagination |
| Lifecycle rules per bucket | 1000 | |
| CORS rules per bucket | 10 | |
| Replication rules per bucket | 100 | |
| `PutBucket` rate limit | 100 req/s per account | Throttled at account level |

## Key APIs (Control Plane, 2019-05-17)

The OpenAPI control plane covers **bucket-level management**. All control-plane
operations are RPC-style and return JSON.

| Category | Operations |
|----------|-----------|
| **Bucket CRUD** | `ListBuckets`, `PutBucket`, `GetBucketInfo`, `DeleteBucket` |
| **ACL** | `GetBucketAcl`, `PutBucketAcl` |
| **Lifecycle** | `GetBucketLifecycle`, `PutBucketLifecycle`, `DeleteBucketLifecycle` |
| **CORS** | `GetBucketCors`, `PutBucketCors`, `DeleteBucketCors` |
| **Logging** | `GetBucketLogging`, `PutBucketLogging`, `DeleteBucketLogging` |
| **Static Website** | `GetBucketWebsite`, `PutBucketWebsite`, `DeleteBucketWebsite` |
| **Referer** | `GetBucketReferer`, `PutBucketReferer`, `DeleteBucketReferer` |
| **Replication** | `GetBucketReplication`, `PutBucketReplication`, `DeleteBucketReplication` |
| **Policy** | `GetBucketPolicy`, `PutBucketPolicy`, `DeleteBucketPolicy` |
| **Versioning** | `GetBucketVersioning`, `PutBucketVersioning` |
| **Encryption** | `GetBucketEncryption`, `PutBucketEncryption`, `DeleteBucketEncryption` |
| **Tagging** | `GetBucketTagging`, `PutBucketTagging`, `DeleteBucketTagging` |
| **Stat** | `GetBucketStat`, `GetBucketInfo`, `GetBucketLocation` |
| **Inventory** | `GetBucketInventory`, `PutBucketInventory`, `ListBucketInventory`, `DeleteBucketInventory` |
| **Access Monitor** | `GetBucketAccessMonitor`, `PutBucketAccessMonitor` |
| **Resource Group** | `GetBucketResourceGroup`, `PutBucketResourceGroup` |

## Key APIs (Data Plane, S3-compatible)

Data-plane operations are REST-style against `<bucket>.<endpoint>/<key>`.

| Category | Operations |
|----------|-----------|
| **Object CRUD** | `PutObject`, `GetObject`, `HeadObject`, `DeleteObject`, `CopyObject` |
| **Listing** | `GetBucket` (ListObjects v1), `ListObjectsV2`, `ListObjectVersions` |
| **Multipart** | `InitiateMultipartUpload`, `UploadPart`, `CompleteMultipartUpload`, `AbortMultipartUpload`, `ListMultipartUploads`, `ListParts` |
| **ACL** | `GetObjectAcl`, `PutObjectAcl` |
| **Tagging** | `GetObjectTagging`, `PutObjectTagging`, `DeleteObjectTagging` |
| **Restore** | `RestoreObject` (for Archive / ColdArchive) |
| **Symlink** | `PutSymlink`, `GetSymlink` |
| **Post** | `PostObject` (browser-based upload) |
| **Append** | `AppendObject` (append-only writes) |
| **Select** | `SelectObject` (SQL queries on CSV/JSON objects) |

> **Recommendation:** Use the official OSS Go SDK V2
> (`github.com/aliyun/aliyun-oss-go-sdk/oss`) for production Go applications
> instead of the OpenAPI SDK — it provides richer data-plane support and
> is actively maintained by the OSS team.

# Well-Architected Assessment — Alibaba Cloud OSS

This document evaluates the OSS skill's operations against Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).
It is a companion to [SKILL.md §Well-Architected Framework Integration](../SKILL.md#well-architected-framework-integration).

## §2.1 安全 (Security)

### Identity & Access Management

| Requirement | Guidance |
|-------------|----------|
| **Default ACL** | Always start with `private`. Apply `public-read` only to public-static-website buckets. **NEVER** apply `public-read-write` to any bucket holding sensitive data. |
| **RAM Policy** | Scoped to `oss:GetObject` on specific resource: `acs:oss:*:*:bucket-name/*`. Avoid `oss:*` wildcard. |
| **Bucket Policy** | Use for cross-account access; use IAM notation `acs:ram::<uid>:*` to restrict to specific accounts. |
| **STS Tokens** | For apps, use `AssumeRole` with 1-hour expiry. Do not embed long-lived AK/SK in clients. |
| **AccessKey rotation** | Rotate AK at least every 90 days; use `DisableAccessKey` to revoke. |

### Network Isolation

| Requirement | Guidance |
|-------------|----------|
| **Endpoint type** | Use `<region>-internal.aliyuncs.com` for ECS-to-OSS traffic to avoid public egress. |
| **VPC integration** | For tighter isolation, configure a [VPC endpoint](https://help.aliyun.com/zh/oss/user-guide/oss-vpc-endpoint) (付费服务) so OSS traffic never leaves the VPC. |
| **Referer anti-leech** | Always set `Referer` whitelist for any `public-read` bucket. Default `AllowEmptyReferer=false`. |
| **CORS** | Restrict `AllowedOrigin` to specific domains — never `*` for production. |

### Data Protection

| Requirement | Guidance |
|-------------|----------|
| **Encryption at rest** | Enable `PutBucketEncryption` with `SSE-KMS` for regulated data (PII, financial). `SSE-OSS` is OSS-managed and free — use for non-sensitive data. |
| **Encryption in transit** | OSS always uses HTTPS for the control plane. For the data plane, always use HTTPS endpoints. |
| **Presigned URL expiry** | Cap at 1 hour for sensitive downloads. Use IP-conditional signatures for additional safety. |
| **Versioning** | Enable on critical buckets — protects against accidental deletion. Cannot be disabled once enabled. |
| **Object Lock** | Available for compliance use cases; must be enabled at bucket creation. |

### Threat Detection

| Capability | Recommendation |
|------------|----------------|
| **ActionTrail** | Enable — records all OSS API calls for audit. |
| **Bucket Access Monitor** | Enable `PutBucketAccessMonitor` to detect unusual access patterns. |
| **WAF** | Place WAF in front of OSS static website for `public-read` buckets. |

### Sample RAM Policy (Read-Only to Single Bucket)

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["oss:GetObject", "oss:ListObjects"],
      "Resource": [
        "acs:oss:*:*:my-bucket",
        "acs:oss:*:*:my-bucket/*"
      ]
    }
  ]
}
```

## §2.2 稳定 (Stability)

### Multi-AZ / Multi-Region

| Requirement | Guidance |
|-------------|----------|
| **Default durability** | OSS data is replicated across **at least 3 zones** within a region by default. 12 nines durability. |
| **DR** | Enable **Cross-Region Replication (CRR)** for mission-critical data. Both source and destination must have versioning enabled. |
| **Cross-region failover** | OSS does not have automatic DNS failover. Use DNS with health checks (e.g., Alibaba Cloud DNS + custom monitors) to switch between source and replicated destination. |

### Backup & Recovery

| Requirement | Guidance |
|-------------|----------|
| **Lifecycle** | Configure tier-down + expiration rules to keep storage cost low. Use `AbortMultipartUpload` lifecycle to clean up incomplete uploads. |
| **Versioning** | Critical for recovery from accidental deletion. Restore by promoting an older version. |
| **Cross-region backup** | Use CRR or scheduled HBR (Hybrid Backup Recovery) for off-region backup. |
| **Restore drill** | Quarterly: test restore of a representative object from Archive / ColdArchive. |
| **RTO target** | For replicated CRR: minutes (depends on object size). For Archive restore: 1 min (Expedited) – 5 h (Bulk). |
| **RPO target** | For CRR: typically seconds. For Archive: object-level, RPO = 0 (data is in OSS already). |

### Failure-Oriented Design

| Pattern | Recommendation |
|---------|----------------|
| **Multipart with resume** | Always enable `ossutil --checkpoint-dir` for large uploads. |
| **Idempotent uploads** | Use content-hash (`MD5` or `SHA-256`) as object key prefix to dedupe. |
| **List+abort orphans** | Weekly: list and abort stale multipart uploads to prevent storage leak. |
| **Retry on 5xx** | Implement exponential backoff (1s, 2s, 4s, 8s) on 5xx / `InternalError`; idempotent retries are safe. |

## §2.3 成本 (Cost)

### Billing Model Comparison

| Storage Class | Min Storage Duration | Retrieval Cost | Best For |
|---------------|---------------------|----------------|----------|
| **Standard** | 0 | Free | Hot data |
| **IA** | 30 days | Small per-GB | < 1 access / month |
| **Archive** | 60 days | Per-GB restore | < 1 access / quarter |
| **ColdArchive** | 180 days | Per-GB restore | < 1 access / year |
| **DeepColdArchive** | 180 days | Per-GB restore | 7+ year retention |

### Cost Levers

| Lever | Description |
|-------|-------------|
| **Lifecycle tier-down** | Most important. Tier down Standard → IA → Archive based on age. |
| **Lifecycle expiration** | Set `Expiration.Days` for true deletes (after transitioning through tiers). |
| **Multipart abort** | Set `AbortMultipartUpload.DaysAfterInitiation=7` to clean up incomplete uploads. |
| **Region selection** | Mainland China (cn-hangzhou, etc.) is generally cheaper than Hong Kong or overseas. |
| **Storage class on upload** | Set `x-oss-storage-class: Archive` directly on upload to skip Standard. |
| **Internal endpoint** | Use `<region>-internal.aliyuncs.com` to avoid public egress from ECS. |
| **HTTP/HTTPS choice** | HTTPS is no extra cost; use HTTPS always. |

### Waste Detection

| Pattern | Detection | Action |
|---------|-----------|--------|
| Standard objects > 90 days old with no access in 30 days | `ossutil ls` + age analysis | Apply IA lifecycle transition |
| Archive objects > 1 year untouched | `ossutil ls --meta \| grep Archive` | Already optimal; consider expiration |
| Incomplete multipart uploads > 7 days | `ossutil list-multipart-uploads` | Set lifecycle abort |
| Buckets with `public-read-write` ACL | `aliyun oss GetBucketAcl` | Tighten to `private` or `public-read` |

### Billing Items Reference

| Billing Item | Description |
|--------------|-------------|
| `OSS-Storage` | Storage × class × hours |
| `OSS-Traffic` | Public egress only; **internal and CDN traffic free** |
| `OSS-Request-Tier1` | PUT/POST/DELETE / List operations |
| `OSS-Request-Tier2` | GET / HEAD operations |
| `OSS-Data-Processing` | Image processing, SelectObject |
| `OSS-CR-Traffic` | Cross-region replication traffic |
| `OSS-Restore` | Archive / ColdArchive restoration |

## §2.4 效率 (Efficiency)

### Batch Operations

| Pattern | Tool | Notes |
|---------|------|-------|
| Bulk upload directory | `ossutil sync /local/dir/ oss://bucket/prefix/` | Incremental by default |
| Bulk download | `ossutil cp oss://bucket/prefix/ /local/ --recursive` | Use `--thread-count 10` |
| Bulk delete | `ossutil rm oss://bucket/prefix/ -r` | Confirm count first |
| Bulk tag | `ossutil set-meta oss://bucket/prefix -r --meta "x-oss-meta-key=value"` | |
| Multi-object copy | `ossutil cp oss://src/ oss://dst/ --recursive` | Server-side copy |

### Automation

| Pattern | Tool | Notes |
|---------|------|-------|
| Scheduled lifecycle check | Function Compute + cron | Verify expected tier transitions occurred |
| Storage class auto-tier | Lifecycle rules | No custom code needed |
| Cross-region backup | CRR (built-in) | No custom code needed |
| Object metadata index | OSS Inventory | Daily/weekly CSV of all object metadata |
| Serverless event handling | OSS event → Function Compute / MNS | ObjectCreated, ObjectRemoved triggers |

### CI/CD

OSS integrates natively with major CI tools as a build artifact store.

```yaml
# GitHub Actions — Terraform
- uses: hashicorp/setup-terraform@v2
- run: terraform init -backend-config="bucket=my-tf-state"
```

```yaml
# GitLab CI — build artifact
artifacts:
  paths:
    - build/
  expire_in: 1 day

deploy_oss:
  stage: deploy
  script:
    - ossutil cp build/ oss://my-bucket/builds/$CI_COMMIT_SHA/ --recursive
```

## §2.5 性能 (Performance)

### Throughput Limits

| Resource | Default | Raiseable |
|----------|---------|-----------|
| Single bucket QPS | 10,000 GET/s, 3,000 PUT/s | Per ticket |
| Single object download | 5 Gbps public | Higher with acceleration |
| `ossutil` parallel threads | 10 (default) | Set via `--thread-count` (max ~100) |

### Latency Targets

| Operation | Target Latency | p99 SLO |
|-----------|----------------|---------|
| GET (small object, same-region) | 10-30 ms | < 100 ms |
| GET (large object, public) | 50-200 ms | < 500 ms |
| PUT (small, 1 MB) | 30-80 ms | < 200 ms |
| Multipart upload (5 GB) | 30-60 s on 1 Gbps | n/a |

### Auto-Scaling

OSS is **fully managed** — no instance sizing, no auto-scaling config needed.
The service scales automatically with load.

### Transfer Acceleration

| Use Case | Solution |
|----------|----------|
| Cross-region uploads | `oss-accelerate.aliyuncs.com` (global accelerate) |
| Same-region uploads from ECUs with no in-region endpoint | `<region>-internal.aliyuncs.com` |
| Bulk transfer | `ossutil --thread-count 10 --part-size 100MB` |
| Mobile clients | Use the OSS Mobile SDK (iOS / Android) with multipart + resume |
| Long-haul file distribution | Combine OSS with CDN (set OSS as origin) |

### Key Performance Patterns

| Pattern | Recommendation |
|---------|----------------|
| **Large file upload** | Multipart, 10-20 parallel parts, 100 MB part size |
| **Bulk small object upload** | `ossutil sync` (parallel) rather than serial `cp` |
| **Bulk small object list** | Paginate with `MaxKeys=1000` |
| **Latency-sensitive GET** | Use `oss-cn-hangzhou-internal.aliyuncs.com` for ECS in same region |
| **Cross-region replication** | CRR is async; CRR is not a substitute for synchronous read replicas |

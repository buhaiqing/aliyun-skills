# Troubleshooting — Alibaba Cloud OSS

## Common Error Codes (Top 15)

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `NoSuchBucket` / 404 | Bucket does not exist | Verify name; create if needed; check region |
| `NoSuchKey` / 404 | Object does not exist | Verify key; treat as success in upsert |
| `BucketAlreadyExists` / 409 | Bucket name in use (any tenant) | Pick a different name; check prior usage |
| `BucketNotEmpty` / 409 | Cannot delete non-empty bucket | Empty bucket first (or abort multipart uploads) |
| `AccessDenied` / 403 | RAM policy denies action | Check RAM policy; verify `oss:Action` is granted |
| `SignatureDoesNotMatch` / 403 | AK/SK mismatch or clock skew | Verify SK; check system clock (NTP) |
| `InvalidArgument` / 400 | Bad request parameter | Inspect message; align with OpenAPI |
| `InvalidBucketName` / 400 | Bucket name format invalid | Show naming rules (3-63 chars, lowercase, no `_`) |
| `InvalidObjectName` / 400 | Object key format invalid | Show key rules (≤ 1024 bytes URL-encoded) |
| `MalformedXML` / 400 | XML body in PutBucketLifecycle/Cors/... is invalid | Validate JSON/XML; check `Rule` vs `Rules` |
| `RequestTimeTooSkewed` / 403 | Local clock > 15 min off from server | Sync NTP |
| `TooManyBuckets` / 409 | Account bucket quota exceeded (default 100) | Raise quota via ticket |
| `QuotaExceeded.Storage` / 400 | Storage quota exceeded | Delete data or raise quota |
| `KmsServiceError` / 500 | KMS service issue (SSE-KMS) | Retry; check KMS status |
| `ServerError` / 500 | OSS internal error | Retry with backoff; then HALT with RequestId |
| `NoSuchBucketPolicy` / 404 | No policy set | Normal — treat as "no policy configured" |

## Diagnostic Order

1. **Capture RequestId** — every OSS response includes `RequestId`. Required
   for any support ticket. For `aliyun oss`, look in `$.RequestId` (control
   plane). For data plane (ossutil), use the `--log-path` option or
   `--enable-symlink-dir`.
2. **Verify credentials** — `aliyun sts GetCallerIdentity`. Confirms AK is
   valid and SK is correct.
3. **Verify region** — bucket region ≠ caller region can cause `SignatureDoesNotMatch`
   or `AccessDenied`. Use `GetBucketInfo` to confirm.
4. **Verify network** — `curl -I https://oss-<region>.aliyuncs.com`.
5. **Verify RAM policy** — `aliyun ram ListPoliciesForUser --UserName <user>`
   to see attached policies; cross-check with `GetBucketInfo.Owner.Id` to
   confirm the bucket is owned by the caller's account.

## Symptom-Based Decision Tree

### "Upload fails with `SignatureDoesNotMatch`"

1. **Check AK/SK** — `echo $ALIBABA_CLOUD_ACCESS_KEY_ID` (length should be ~20
   chars starting with `LTAI`).
2. **Check clock** — `date -u`. If drift > 5 min, sync NTP:
   `sudo ntpdate ntp.aliyun.com`.
3. **Check encoding** — special characters in `Key` may need URL encoding.

### "Bucket creation fails with `InvalidBucketName`"

Common causes:
- Uppercase letters → **must be lowercase**
- Underscore `_` → **not allowed**; use hyphen `-`
- Length < 3 or > 63 → **invalid**
- Looks like an IP address (e.g., `192-168-1-1`) → **not allowed**
- Starts or ends with hyphen → **not allowed**

> **Common gotcha:** Many users migrate from S3 buckets with `My_Bucket`
> format. OSS rejects underscores — must rename.

### "Cannot delete bucket"

1. **Bucket is not empty** — check `GetBucketStat`:
   - `ObjectCount` must be 0
   - `MultipartUploadCount` must be 0
2. **Versioned objects** — if versioning was ever enabled, all historical
   versions + delete markers must be removed (set lifecycle to expire them).
3. **Lifecycle policies** — pending lifecycle expirations may block deletion
   for a short period.

> **Recovery:** Use `ossutil rm oss://<bucket> -r` to clear all objects, then
> `ossutil abort-multipart-uploads oss://<bucket> -r` to abort incomplete
> multipart uploads.

### "Restore stuck in `ongoing-request="true"`"

| Storage Class | Standard Restore | Expedited | Bulk |
|---------------|------------------|-----------|------|
| Archive | 1-5 min | < 1 min | 1-5 hours |
| ColdArchive | 1-5 min (limited) | ❌ | 5-12 hours |

> If a restore has been pending > 24 hours, capture the `RequestId` and
> contact support.

### "GetObject returns `NoSuchKey` but the file exists"

1. **Region mismatch** — file is in a different region. Use `ossutil ls
   oss://bucket-name/prefix/ -r` to discover.
2. **Bucket policy** — bucket policy may explicitly deny `GetObject` for the
   caller's principal. Check with `GetBucketPolicy`.
3. **Lifecycle** — the object was expired or transitioned to ColdArchive and
   needs restore first.

### "High request costs (charges spike)"

OSS charges per 10,000 requests. High cost usually indicates:
- **Lifecycle is missing** — Standard-class objects accumulate forever.
- **List operations are chatty** — each `ListObjects` page is 1 request.
- **Image processing** — every `?x-oss-process=` query is a request.
- **Cross-region replication** — CRR traffic is billable.

> **Cost-pillar remediation:** Apply [tier-down lifecycle rules](core-concepts.md#storage-classes)
> and check bucket statistics for object age distribution.

### "Cannot upload large file (single PUT times out)"

For files > 100 MB, **multipart upload is required**. Use:

```bash
ossutil cp /local/bigfile oss://bucket/key \
  --part-size 104857600 \
  --thread-count 10 \
  --checkpoint-dir /tmp/ossutil-checkpoint
```

> **Resumability:** If the upload fails, re-run the SAME command. ossutil
> resumes from the last completed part via the checkpoint file.

### "Presigned URL returns 403"

1. **Signature expired** — `timeout` was too short. Re-generate.
2. **HTTP method mismatch** — URL was signed for `GET` but used as `PUT`.
3. **Path mismatch** — signed key differs from accessed key (case-sensitive).
4. **Bucket policy conflict** — explicit `Deny` overrides the presigned
   signature's temporary grant.

## Common Configuration Issues

### Credentials Not Found

```bash
$ aliyun oss ListBuckets
ERROR: AccessKeyId is mandatory for this action
```

**Fix:** Export env vars or run `aliyun configure`:

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="LTAI******"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="****"   # mask in displayed output
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
```

### Wrong Endpoint

```bash
$ ossutil ls oss://my-bucket
ERROR: The bucket you are accessing is in another region.
```

**Fix:** Use the correct regional endpoint, or set the region in
`~/.ossutilconfig`:

```ini
[default]
region=cn-shanghai
```

### `ossutil` Permission Denied on `~/.ossutilconfig`

```bash
$ ossutil config
ERROR: open ~/.ossutilconfig: permission denied
```

**Fix:** `chmod 600 ~/.ossutilconfig` or use `--config-file /tmp/ossutilconfig`.

## Support Escalation

When submitting a ticket to Alibaba Cloud support, ALWAYS include:

1. **Bucket name** and **region**
2. **RequestId** from the failed response (every OSS response includes it)
3. **Time** of the failure (with timezone)
4. **Failed operation** name (e.g., `PutBucket`, `GetObject`)
5. **HTTP status code** and **error code** from the response
6. **AK ID** (NOT the SK!) of the calling identity

> **Security:** Never include `AccessKeySecret` in support tickets.

# API & SDK — Alibaba Cloud Object Storage Service (OSS)

## OpenAPI

- **Control Plane:** API version `2019-05-17`, RPC-style
  - Endpoint: `oss.aliyuncs.com`
  - Base path: `/`
  - Style: `POST /?Action=PutBucket&...&Bucket=...&Signature=...`
- **Data Plane:** S3-compatible REST API
  - Endpoint: `<bucket>.<region>.aliyuncs.com`
  - Base path: `/<key>`
  - Style: `PUT /<key>`, `GET /<key>`, `DELETE /<key>`
- **Official OpenAPI Explorer:**
  `https://api.aliyun.com/api/oss/2019-05-17`
- **Full API reference:**
  `https://help.aliyun.com/zh/oss/developer-reference/api-oss-2019-05-17-overview`

## SDK Packages

| Use Case | Go Package | Notes |
|----------|-----------|-------|
| **Control plane + general data plane** | `github.com/alibabacloud-go/oss-20190517/v4/client` | Auto-generated from OpenAPI; wide coverage |
| **Production data plane (recommended)** | `github.com/aliyun/aliyun-oss-go-sdk/oss` | Official OSS team SDK V2; richer features, better perf |
| **S3-compatible mode** | `github.com/aws/aws-sdk-go-v2/service/s3` | When migrating from AWS S3; configure endpoint |

> **Recommendation:** Use `github.com/aliyun/aliyun-oss-go-sdk/oss` (OSS V2 SDK)
> for all data-plane operations. Use the OpenAPI SDK (`oss-20190517`) only
> when the V2 SDK lacks a specific control-plane operation.

## SDK Operations Map (Control Plane, OpenAPI 2019-05-17)

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| List all buckets | ListBuckets | `ListBuckets` | `aliyun oss ListBuckets` |
| Create bucket | PutBucket | `PutBucket` | `aliyun oss PutBucket` |
| Get bucket info | GetBucketInfo | `GetBucketInfo` | `aliyun oss GetBucketInfo` |
| Delete bucket | DeleteBucket | `DeleteBucket` | `aliyun oss DeleteBucket` |
| Get bucket ACL | GetBucketAcl | `GetBucketAcl` | `aliyun oss GetBucketAcl` |
| Set bucket ACL | PutBucketAcl | `PutBucketAcl` | `aliyun oss PutBucketAcl` |
| Get lifecycle | GetBucketLifecycle | `GetBucketLifecycle` | `aliyun oss GetBucketLifecycle` |
| Set lifecycle | PutBucketLifecycle | `PutBucketLifecycle` | `aliyun oss PutBucketLifecycle` |
| Delete lifecycle | DeleteBucketLifecycle | `DeleteBucketLifecycle` | `aliyun oss DeleteBucketLifecycle` |
| Get CORS | GetBucketCors | `GetBucketCors` | `aliyun oss GetBucketCors` |
| Set CORS | PutBucketCors | `PutBucketCors` | `aliyun oss PutBucketCors` |
| Delete CORS | DeleteBucketCors | `DeleteBucketCors` | `aliyun oss DeleteBucketCors` |
| Get logging | GetBucketLogging | `GetBucketLogging` | `aliyun oss GetBucketLogging` |
| Set logging | PutBucketLogging | `PutBucketLogging` | `aliyun oss PutBucketLogging` |
| Get website | GetBucketWebsite | `GetBucketWebsite` | `aliyun oss GetBucketWebsite` |
| Set website | PutBucketWebsite | `PutBucketWebsite` | `aliyun oss PutBucketWebsite` |
| Delete website | DeleteBucketWebsite | `DeleteBucketWebsite` | `aliyun oss DeleteBucketWebsite` |
| Get referer | GetBucketReferer | `GetBucketReferer` | `aliyun oss GetBucketReferer` |
| Set referer | PutBucketReferer | `PutBucketReferer` | `aliyun oss PutBucketReferer` |
| Get replication | GetBucketReplication | `GetBucketReplication` | `aliyun oss GetBucketReplication` |
| Set replication | PutBucketReplication | `PutBucketReplication` | `aliyun oss PutBucketReplication` |
| Get policy | GetBucketPolicy | `GetBucketPolicy` | `aliyun oss GetBucketPolicy` |
| Set policy | PutBucketPolicy | `PutBucketPolicy` | `aliyun oss PutBucketPolicy` |
| Delete policy | DeleteBucketPolicy | `DeleteBucketPolicy` | `aliyun oss DeleteBucketPolicy` |
| Get versioning | GetBucketVersioning | `GetBucketVersioning` | `aliyun oss GetBucketVersioning` |
| Set versioning | PutBucketVersioning | `PutBucketVersioning` | `aliyun oss PutBucketVersioning` |
| Get encryption | GetBucketEncryption | `GetBucketEncryption` | `aliyun oss GetBucketEncryption` |
| Set encryption | PutBucketEncryption | `PutBucketEncryption` | `aliyun oss PutBucketEncryption` |
| Get bucket stat | GetBucketStat | `GetBucketStat` | `aliyun oss GetBucketStat` |
| Get bucket location | GetBucketLocation | `GetBucketLocation` | `aliyun oss GetBucketLocation` |
| List multipart uploads | ListMultipartUploads | `ListMultipartUploads` | `aliyun oss ListMultipartUploads` |
| Abort multipart upload | AbortMultipartUpload | `AbortMultipartUpload` | `aliyun oss AbortMultipartUpload` |
| Restore object | RestoreObject | `RestoreObject` | `aliyun oss RestoreObject` |
| Get object ACL | GetObjectAcl | `GetObjectAcl` | `aliyun oss GetObjectAcl` |
| Set object ACL | PutObjectAcl | `PutObjectAcl` | `aliyun oss PutObjectAcl` |

## Request / Response Notes

- **Time format:** All time parameters use ISO 8601 UTC: `YYYY-MM-DDTHH:mm:ssZ`.
- **Pagination:** `ListBuckets` returns ALL buckets in a single call (no
  pagination parameter). `ListObjects` supports `Marker` / `MaxKeys`; v2
  supports `ContinuationToken`.
- **ListObjectsV2 vs v1:** Prefer v2. v2 returns `Key` directly in `Contents`;
  v1 returns `Contents[].Key`.
- **Idempotency:** OSS does not have a built-in client request token
  mechanism. For safe retries, use a deterministic `Key` (e.g., based on
  source ETag or content hash).
- **Object keys with special characters:** `/` is allowed and treated as a
  path separator. `?` and `#` in keys require URL encoding in URLs.

## Common JSON Paths (TE-4 Centralized)

See [SKILL.md §API and Response Conventions](../SKILL.md#api-and-response-conventions-agent-readable)
for the complete table. Highlights:

```
# Control plane
ListBuckets:            $.Buckets[].Name, $.Buckets[].Region, $.Buckets[].StorageClass
GetBucketInfo:          $.Bucket.Name, $.Bucket.Region, $.Bucket.StorageClass
GetBucketAcl:           $.AccessControlList.Grant
GetBucketLifecycle:     $.LifecycleRules.LifecycleRule[].Id, $.LifecycleRules.LifecycleRule[].Status
GetBucketCors:          $.CORSRules.CORSRule[].AllowedOrigin, $.CORSRules.CORSRule[].AllowedMethod
GetBucketReferer:       $.RefererConfiguration.AllowEmptyReferer, $.RefererConfiguration.RefererList
GetBucketReplication:   $.ReplicationConfiguration.Rules.ReplicationRule[].Status

# Data plane (control-plane API surface)
ListObjects:            $.Contents[].Key, $.Contents[].Size, $.Contents[].ETag
ListMultipartUploads:   $.Upload[].Key, $.Upload[].UploadId, $.Upload[].Initiated

# Request tracking
Any op:                 $.RequestId
```

## Go SDK V2 — Multipart Upload Walkthrough

For files > 100 MB. Uses `github.com/aliyun/aliyun-oss-go-sdk/oss`.

```go
// main.go
package main

import (
	"fmt"
	"os"

	"github.com/aliyun/aliyun-oss-go-sdk/oss"
)

func main() {
	ak := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
	sk := os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
	region := os.Getenv("ALIBABA_CLOUD_REGION_ID")
	bucket := os.Getenv("BUCKET_NAME")
	objectKey := os.Getenv("OBJECT_KEY")
	localFile := os.Getenv("LOCAL_FILE")

	// credentials MUST come from os.Getenv — never hardcode
	client, err := oss.New(
		fmt.Sprintf("https://oss-%s.aliyuncs.com", region),
		ak,
		sk,
	)
	if err != nil {
		panic(err)
	}

	bucketPtr, err := client.Bucket(bucket)
	if err != nil {
		panic(err)
	}

	// Step 1: Initiate multipart upload
	imur, err := bucketPtr.InitiateMultipartUpload(objectKey)
	if err != nil {
		panic(err)
	}
	uploadID := imur.UploadID

	// Step 2: Upload parts (split file manually, then call UploadPart)
	// For auto-partitioning, use bucketPtr.UploadFile with options
	err = bucketPtr.UploadFile(objectKey, localFile, 100*1024*1024,
		oss.Routines(10),
		oss.Checkpoint(true, "/tmp/oss-checkpoint"),
	)
	if err != nil {
		// Abort on failure
		_, _ = bucketPtr.AbortMultipartUpload(objectKey, uploadID)
		panic(err)
	}

	// Step 3: Validate via HeadObject
	head, err := bucketPtr.GetObjectMeta(objectKey)
	if err != nil {
		panic(err)
	}
	fmt.Printf("Uploaded: size=%d, etag=%s, storage-class=%s\n",
		head.ContentLength, head.Get("ETag"), head.Get("X-Oss-Storage-Class"))
}
```

**Run:**

```bash
export BUCKET_NAME="my-bucket"
export OBJECT_KEY="videos/2026/big-file.zip"
export LOCAL_FILE="/tmp/big-file.zip"
go run ./main.go
```

> **Resumability:** Pass `oss.Checkpoint(true, "/path")` to enable resumable
> upload. Re-running the same command resumes from the last completed part.
> Delete the checkpoint file to start over.

## Presigned URL — Go SDK V2

```go
package main

import (
	"fmt"
	"os"
	"time"

	"github.com/aliyun/aliyun-oss-go-sdk/oss"
)

func main() {
	client, _ := oss.New(
		fmt.Sprintf("https://oss-%s.aliyuncs.com", os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
		os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
	)
	bucketPtr, _ := client.Bucket(os.Getenv("BUCKET_NAME"))

	// Sign GetObject URL valid for 3600 seconds
	signedURL, err := bucketPtr.SignURL(os.Getenv("OBJECT_KEY"), oss.HTTPGet, 3600)
	if err != nil {
		panic(err)
	}
	fmt.Println(signedURL)
}
```

> **Sensitive:** Anyone with the URL can access the object. Use short
> expiry (≤ 1 hour) and consider IP-conditional signatures for additional
> safety.

## Pagination Patterns

```go
// ListObjectsV2 iteration
marker := ""
for {
	result, err := bucketPtr.ListObjectsV2(oss.Marker(marker), oss.MaxKeys(1000))
	if err != nil {
		panic(err)
	}
	for _, obj := range result.Objects {
		fmt.Printf("%s %d %s\n", obj.Key, obj.Size, obj.ETag)
	}
	if !result.IsTruncated {
		break
	}
	marker = result.NextContinuationToken
}
```

## Error Code Reference

OSS returns errors with `Code` (e.g., `NoSuchBucket`, `SignatureDoesNotMatch`)
and `Message`. The `RequestId` is critical for support tickets.

| Code | HTTP | Meaning | Agent Action |
|------|------|---------|--------------|
| `NoSuchBucket` | 404 | Bucket does not exist | Verify name; create if needed |
| `NoSuchKey` | 404 | Object does not exist | Verify key; treat as success in upsert |
| `BucketAlreadyExists` | 409 | Bucket name in use (by any tenant) | Pick a different name |
| `BucketNotEmpty` | 409 | Cannot delete non-empty bucket | Empty bucket first |
| `AccessDenied` | 403 | RAM policy denies | Verify policy; check OSS Action |
| `SignatureDoesNotMatch` | 403 | AK/SK mismatch or clock skew | Check SK; sync clock |
| `InvalidArgument` | 400 | Bad request parameter | Inspect message; align with OpenAPI |
| `InvalidBucketName` | 400 | Bucket name format invalid | Show naming rules |
| `InvalidObjectName` | 400 | Object key format invalid | Show key rules |
| `MalformedXML` | 400 | XML body in PutBucketLifecycle/Cors/etc. is invalid | Validate JSON / XML before send |
| `RequestTimeTooSkewed` | 403 | Local clock > 15 min off from server | Sync NTP |
| `TooManyBuckets` | 409 | Account bucket quota exceeded | Raise quota via ticket |
| `QuotaExceeded.Storage` | 400 | Storage quota exceeded | Delete old data or raise quota |
| `KmsServiceError` | 500 | KMS service issue (SSE-KMS) | Retry; check KMS status |

> **Note:** OSS error codes are documented in the [OpenAPI error
> reference](https://help.aliyun.com/zh/oss/developer-reference/error-code-list).

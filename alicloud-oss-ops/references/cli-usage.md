# CLI — Alibaba Cloud OSS (`aliyun oss` + `ossutil`)

## Install and Config

### `aliyun` CLI (control-plane)

```bash
/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"
aliyun --version
```

Reads credentials from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` /
`ALIBABA_CLOUD_ACCESS_KEY_SECRET` or `~/.aliyun/config.json`.

### `ossutil` (data-plane — recommended)

```bash
# macOS / Linux
curl -O https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64
chmod 755 ossutil64
sudo mv ossutil64 /usr/local/bin/ossutil

# Verify
ossutil --version
```

Reads credentials from env vars (same as `aliyun`) or `~/.ossutilconfig`
(JSON). Run `ossutil config` for interactive setup.

> **CRITICAL Credentials:** Neither `aliyun` nor `ossutil` accepts `--ak` /
> `--sk` in a production-safe way. Always use env vars or the config file.
> Never pass secrets as command-line arguments (visible in `ps aux`).

## Conventions (Agent Execution)

### JSON Output

- `aliyun oss <op>` returns JSON by default — no `--output json` needed.
- Use `--output cols=...,rows=...` for JMESPath tabular extraction.
- `ossutil` returns human-friendly text by default; add `--output-format json`
  for machine parsing. Use `-j` shortcut.

### Suffix Behavior

- `--output` is for JMESPath transformations only.
- `--no-interactive` does NOT exist in `aliyun` — all commands are non-interactive by default.

### Document Exact JSON Paths

Always run a real invocation first, capture the response, and use **verified**
JSON paths in the SKILL.md. Do NOT guess.

## CLI vs ossutil Coverage Gap

| Operation | `aliyun oss` | `ossutil` | Notes |
|-----------|--------------|-----------|-------|
| `ListBuckets` | ✅ | ✅ | Use `aliyun` for control plane; `ossutil ls` for quick scan |
| `PutBucket` | ✅ | ❌ | Use `aliyun` |
| `GetBucketInfo` | ✅ | ✅ (`stat`) | `ossutil stat` is richer |
| `DeleteBucket` | ✅ | ❌ | Use `aliyun` |
| `GetBucketAcl` / `PutBucketAcl` | ✅ | ❌ | Use `aliyun` |
| Lifecycle / CORS / Logging / Referer / Replication | ✅ | ❌ | Use `aliyun` |
| Static Website | ✅ | ❌ | Use `aliyun` |
| Versioning / Encryption / Policy | ✅ | ❌ | Use `aliyun` |
| `ListObjects` / `ListObjectsV2` | ✅ | ✅ (`ls`) | `ossutil ls -r` for recursive |
| `GetObject` (download) | ✅ (small) | ✅ (recommended) | Avoid `aliyun` GetObject for files > 1 MB |
| `PutObject` (upload) | ✅ (small) | ✅ (recommended) | `ossutil cp` auto multipart |
| `DeleteObject` (single) | ✅ | ✅ | `ossutil rm` is faster |
| Bulk delete by prefix / wildcard | ❌ | ✅ | `ossutil rm -r`, `ossutil rm --include *.log` |
| Multipart upload (auto) | ❌ | ✅ | `ossutil cp --thread-count 10` |
| Multipart abort | ✅ | ✅ | Either works |
| `RestoreObject` | ✅ | ✅ | `ossutil restore` |
| `CopyObject` | ✅ | ✅ | `ossutil cp` |
| `HeadObject` | ✅ | ✅ (`stat`) | `ossutil stat` |
| Presigned URL | ❌ | ✅ | `ossutil sign` |

> **Rule of thumb:**
> - **Control plane** (bucket config) → `aliyun oss`
> - **Data plane** (objects) → `ossutil` (or OSS Go SDK V2 in code)
> - **Bulk operations** → `ossutil` only

## Command Map — `aliyun oss` (Control Plane)

| Goal | Example `aliyun` invocation | Notes |
|------|--------------------------|-------|
| List buckets | `aliyun oss ListBuckets` | JSON by default |
| Create bucket | `aliyun oss PutBucket --Bucket my-bucket --StorageClass Standard --Acl private` | Returns location |
| Get bucket info | `aliyun oss GetBucketInfo --Bucket my-bucket` | Region, creation date, endpoints |
| Delete bucket | `aliyun oss DeleteBucket --Bucket my-bucket` | Must be empty |
| Get ACL | `aliyun oss GetBucketAcl --Bucket my-bucket` | Returns grant |
| Set ACL | `aliyun oss PutBucketAcl --Bucket my-bucket --Acl public-read` | |
| Get lifecycle | `aliyun oss GetBucketLifecycle --Bucket my-bucket` | Returns rules array |
| Set lifecycle | `aliyun oss PutBucketLifecycle --Bucket my-bucket --LifecycleConfiguration file:///path/lifecycle.json` | JSON body |
| Delete lifecycle | `aliyun oss DeleteBucketLifecycle --Bucket my-bucket` | |
| Get CORS | `aliyun oss GetBucketCors --Bucket my-bucket` | |
| Set CORS | `aliyun oss PutBucketCors --Bucket my-bucket --CORSConfiguration file:///path/cors.json` | |
| Get logging | `aliyun oss GetBucketLogging --Bucket my-bucket` | |
| Set logging | `aliyun oss PutBucketLogging --Bucket my-bucket --BucketLoggingStatus file:///path/logging.json` | |
| Get website | `aliyun oss GetBucketWebsite --Bucket my-bucket` | |
| Set website | `aliyun oss PutBucketWebsite --Bucket my-bucket --WebsiteConfiguration file:///path/website.json` | |
| Get referer | `aliyun oss GetBucketReferer --Bucket my-bucket` | |
| Set referer | `aliyun oss PutBucketReferer --Bucket my-bucket --RefererConfiguration file:///path/referer.json` | |
| Get replication | `aliyun oss GetBucketReplication --Bucket my-bucket` | |
| Set replication | `aliyun oss PutBucketReplication --Bucket my-bucket --ReplicationConfiguration file:///path/replication.json` | |
| Get policy | `aliyun oss GetBucketPolicy --Bucket my-bucket` | 404 if no policy |
| Set policy | `aliyun oss PutBucketPolicy --Bucket my-bucket --Policy file:///path/policy.json` | |
| Delete policy | `aliyun oss DeleteBucketPolicy --Bucket my-bucket` | |
| Get versioning | `aliyun oss GetBucketVersioning --Bucket my-bucket` | |
| Set versioning | `aliyun oss PutBucketVersioning --Bucket my-bucket --VersioningConfiguration file:///path/versioning.json` | |
| Get encryption | `aliyun oss GetBucketEncryption --Bucket my-bucket` | |
| Set encryption | `aliyun oss PutBucketEncryption --Bucket my-bucket --BucketEncryptionConfiguration file:///path/encryption.json` | |
| Get bucket stat | `aliyun oss GetBucketStat --Bucket my-bucket` | Storage / object count / multipart count |
| List multipart uploads | `aliyun oss ListMultipartUploads --Bucket my-bucket --Prefix logs/` | |
| Abort multipart upload | `aliyun oss AbortMultipartUpload --Bucket my-bucket --Key logs/big.tar.gz --UploadId xxx` | |
| List objects | `aliyun oss ListObjects --Bucket my-bucket --Prefix logs/ --MaxKeys 100` | Use v2 for new code |

## Command Map — `ossutil` (Data Plane)

| Goal | Example `ossutil` invocation | Notes |
|------|------------------------------|-------|
| List buckets | `ossutil ls` | |
| List objects | `ossutil ls oss://my-bucket/prefix/ -r` | Recursive with `-r` |
| Get object metadata | `ossutil stat oss://my-bucket/key/path` | |
| Upload small file | `ossutil cp /local/file oss://my-bucket/key/path` | Auto multipart for large files |
| Upload large file | `ossutil cp /local/bigfile oss://my-bucket/key --part-size 104857600 --thread-count 10` | |
| Download file | `ossutil cp oss://my-bucket/key/path /local/dest` | |
| Copy object | `ossutil cp oss://src-bucket/key oss://dest-bucket/key` | Server-side copy |
| Delete single object | `ossutil rm oss://my-bucket/key/path` | |
| Delete all by prefix | `ossutil rm oss://my-bucket/prefix/ -r` | Recursive |
| Delete with wildcard | `ossutil rm oss://my-bucket --include "*.log" -r` | Pattern match |
| Restore archived | `ossutil restore oss://my-bucket/key/path` | |
| Sign URL (GET, 3600s) | `ossutil sign oss://my-bucket/key/path --timeout 3600` | |
| Bucket stat | `ossutil stat oss://my-bucket` | |
| Create bucket | `ossutil mb oss://my-bucket` | Region inferred from config |
| Set ACL | `ossutil set-acl oss://my-bucket --acl public-read` | |

## Polling Patterns

### Bucket Existence

```bash
for i in $(seq 1 20); do
  RESULT=$(aliyun oss GetBucketInfo --Bucket "{{user.bucket_name}}" 2>&1)
  if echo "$RESULT" | jq -e '.Bucket.Name' >/dev/null 2>&1; then
    echo "Bucket ready"
    break
  fi
  sleep 3
done
```

### Bucket Deletion

```bash
for i in $(seq 1 20); do
  RESULT=$(aliyun oss GetBucketInfo --Bucket "{{user.bucket_name}}" 2>&1)
  if echo "$RESULT" | grep -q "NoSuchBucket"; then
    echo "Bucket deleted"
    break
  fi
  sleep 3
done
```

### RestoreObject Polling

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

### CRR Active Status

```bash
for i in $(seq 1 20); do
  STATUS=$(aliyun oss GetBucketReplication --Bucket "{{user.bucket_name}}" \
    --output cols=Status rows=ReplicationConfiguration.Rules.ReplicationRule[0].Status)
  [ "$STATUS" = "active" ] && break
  sleep 30
done
```

## Extract Specific Fields with JMESPath

```bash
# List buckets: name + region + storage class
aliyun oss ListBuckets \
  --output cols=Name,Region,StorageClass rows=Buckets[].{Name,Region,StorageClass}

# Get lifecycle rule IDs
aliyun oss GetBucketLifecycle --Bucket my-bucket \
  --output cols=ID,Status rows=LifecycleRules.LifecycleRule[].{ID,Status}
```

## Defensive Validation Helpers

> These bash functions MUST be called before any bucket/object operation.
> Invalid names cause wasted API calls, generic errors, and rate-limit pressure.
> The 5-second check is always cheaper than the round trip.

### `validate_oss_bucket_name`

```bash
# validate_oss_bucket_name <name>
# Exits 0 on success, prints a one-line error to stderr and exits non-zero on failure.
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

  # Rule 3: must not look like an IP address
  if [[ "$name" =~ ^[0-9.]+$ ]] && [[ "$name" =~ \. ]]; then
    echo "ERROR: bucket name looks like an IP address — OSS rejects these: '$name'" >&2
    return 15
  fi

  # Rule 4: only lowercase letters, digits, hyphens
  if ! [[ "$name" =~ ^[a-z0-9-]+$ ]]; then
    if [[ "$name" =~ [_] ]]; then
      echo "ERROR: bucket name contains underscore '_' — use hyphen '-': '$name'" >&2
    elif [[ "$name" =~ [A-Z] ]]; then
      echo "ERROR: bucket name contains uppercase letters — OSS requires all lowercase: '$name'" >&2
    else
      echo "ERROR: bucket name contains illegal characters (only a-z, 0-9, '-' allowed): '$name'" >&2
    fi
    return 12
  fi

  # Rule 5: must start AND end with a letter or digit
  if ! [[ "$name" =~ ^[a-z0-9].*[a-z0-9]$ ]] && [[ ${#name} -gt 1 ]]; then
    echo "ERROR: bucket name must start and end with a letter or digit (no leading/trailing hyphen): '$name'" >&2
    return 13
  fi
  if [[ ${#name} -eq 1 ]] && ! [[ "$name" =~ ^[a-z0-9]$ ]]; then
    echo "ERROR: single-character bucket name must be a lowercase letter or digit: '$name'" >&2
    return 13
  fi

  # Rule 6: no consecutive hyphens
  if [[ "$name" == *"--"* ]]; then
    echo "ERROR: bucket name contains consecutive hyphens '--': '$name'" >&2
    return 14
  fi

  return 0
}
```

| Exit Code | Rule Violated | Fix |
|:---------:|---------------|-----|
| 10 | Empty name | Provide a non-empty name |
| 11 | Length not 3-63 | Adjust to 3-63 chars |
| 12 | Bad characters (uppercase / underscore / other) | Lowercase; replace `_` with `-` |
| 13 | Starts or ends with hyphen | Remove leading/trailing `-` |
| 14 | Consecutive hyphens (`--`) | Use single hyphens between segments |
| 15 | Looks like an IP address | Use a different naming scheme |

### `validate_oss_object_key`

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

  # Rule 2: 1-1023 UTF-8 bytes
  local key_len=${#key}
  if [[ $key_len -lt 1 || $key_len -gt 1023 ]]; then
    echo "ERROR: object key must be 1-1023 UTF-8 bytes (got $key_len)" >&2
    return 31
  fi

  # Rule 3: must not start with '/' or '\'
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

### Agent-Side Existence Check (For Create Only)

Run BEFORE `PutBucket` — catches "globally unique" constraint that client-side validation cannot:

```bash
EXIST=$(ossutil stat oss://"$BUCKET_NAME" 2>&1)
if ! echo "$EXIST" | grep -qi "NoSuchBucket\|does not exist\|no such"; then
  echo "[HALT] Bucket '$BUCKET_NAME' already exists. Pick a unique name." >&2
  exit 20
fi
```

### Usage in Agent Flow

```bash
BUCKET_NAME="{{user.bucket_name}}"
if ! validate_oss_bucket_name "$BUCKET_NAME"; then
  echo "[HALT] Bucket name validation failed — fix the name and retry."
  exit 1
fi

OBJECT_KEY="{{user.object_key}}"
if ! validate_oss_object_key "$OBJECT_KEY"; then
  echo "[HALT] Object key validation failed — fix the key and retry."
  exit 1
fi
```

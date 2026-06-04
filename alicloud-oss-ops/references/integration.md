# Integration — Alibaba Cloud OSS

## Environment Setup

OSS supports three execution paths:

1. **`aliyun oss`** — control plane only (bucket config, ACL, lifecycle, ...).
2. **`ossutil`** — both control and data plane; **recommended for data plane**
   (object upload/download, bulk operations, multipart, presigned URLs).
3. **OSS Go SDK V2** — programmatic access in Go; richest data-plane features.

### `ossutil` Installation (Data Plane)

```bash
# macOS / Linux (amd64)
curl -O https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64
chmod 755 ossutil64
sudo mv ossutil64 /usr/local/bin/ossutil
ossutil --version

# macOS Apple Silicon
curl -O https://gosspublic.alicdn.com/ossutil/1.7.18/ossutilmac64
chmod 755 ossutilmac64
sudo mv ossutilmac64 /usr/local/bin/ossutil
```

### `ossutil` Configuration

`ossutil` reads credentials from env vars (same as `aliyun` CLI) or
`~/.ossutilconfig`. One-time interactive setup:

```bash
ossutil config
# Enter: endpoint, access key ID, access key secret, STSToken (empty for AK auth)
```

> **MUST NOT** include real SK in scripts. Use the config file with
> `chmod 600 ~/.ossutilconfig`.

### Go Runtime Bootstrap

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

### JIT Go SDK Workflow (OSS V2 SDK)

```bash
mkdir -p /tmp/oss-sdk-workspace
cd /tmp/oss-sdk-workspace
go mod init oss-script

# OSS V2 SDK (recommended for data plane)
go get github.com/aliyun/aliyun-oss-go-sdk/oss

# OpenAPI SDK (control plane, when V2 lacks the op)
go get github.com/alibabacloud-go/oss-20190517/v4/client
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea/tea
```

## SDK Package Reference

| Product / Use Case | Go SDK Package |
|--------------------|---------------|
| OSS (OpenAPI control plane) | `github.com/alibabacloud-go/oss-20190517/v4/client` |
| OSS (data plane, recommended) | `github.com/aliyun/aliyun-oss-go-sdk/oss` |
| OSS via S3-compat | `github.com/aws/aws-sdk-go-v2/service/s3` |

## Endpoints Quick Reference

| Region | Public Endpoint | Internal Endpoint |
|--------|-----------------|-------------------|
| cn-hangzhou | `oss-cn-hangzhou.aliyuncs.com` | `oss-cn-hangzhou-internal.aliyuncs.com` |
| cn-shanghai | `oss-cn-shanghai.aliyuncs.com` | `oss-cn-shanghai-internal.aliyuncs.com` |
| cn-beijing | `oss-cn-beijing.aliyuncs.com` | `oss-cn-beijing-internal.aliyuncs.com` |
| cn-shenzhen | `oss-cn-shenzhen.aliyuncs.com` | `oss-cn-shenzhen-internal.aliyuncs.com` |
| cn-hongkong | `oss-cn-hongkong.aliyuncs.com` | `oss-cn-hongkong-internal.aliyuncs.com` |
| us-west-1 | `oss-us-west-1.aliyuncs.com` | `oss-us-west-1-internal.aliyuncs.com` |
| ap-southeast-1 | `oss-ap-southeast-1.aliyuncs.com` | `oss-ap-southeast-1-internal.aliyuncs.com` |

> **List all regions:** `aliyun oss DescribeRegions` (if exposed) or
> `ossutil config` to discover via the wizard.

## RAM Policy Integration

OSS operations require `oss:Action` granted on the appropriate resource. Sample
read-only policy for a single bucket:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "oss:GetObject",
        "oss:ListObjects",
        "oss:GetBucketInfo",
        "oss:GetBucketAcl"
      ],
      "Resource": [
        "acs:oss:*:*:my-bucket",
        "acs:oss:*:*:my-bucket/*"
      ]
    }
  ]
}
```

> **Note:** Cross-account OSS access requires **both**:
> 1. The destination RAM user has `oss:Action` permission.
> 2. The destination bucket's **bucket policy** explicitly allows the source
>    account's UID / RAM user.

## Cross-Skill Integration

| Scenario | Delegate To |
|----------|-------------|
| **Generate a presigned URL from Go SDK** | This skill (data plane) |
| **CDN origin setup with OSS as origin** | `alicloud-cdn-ops` (not yet present) |
| **Move data into OSS** | `alicloud-dts-ops` / `alicloud-sms-ops` (not yet present) |
| **Trigger Lambda / Function Compute on object events** | `alicloud-fc-ops` (event source) |
| **Logs from access logs** | `alicloud-sls-ops` (not yet present) |
| **Billing per bucket** | `alicloud-billing-ops` |
| **Alerts via Cloud Monitor** | `alicloud-cms-ops` |
| **RAM policy authoring** | `alicloud-ram-ops` |
| **Lifecycle tier-down (this skill) + KMS keys** | `alicloud-kms-ops` (SSE-KMS) |
| **Cross-region replication** | This skill (CRR config) — destination bucket must be pre-created |

## CI/CD Patterns

### GitHub Actions — Upload Artifact

```yaml
- name: Upload to OSS
  env:
    ALIBABA_CLOUD_ACCESS_KEY_ID: ${{ secrets.ALIYUN_AK }}
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: ${{ secrets.ALIYUN_SK }}
    ALIBABA_CLOUD_REGION_ID: cn-hangzhou
  run: |
    curl -O https://gosspublic.alicdn.com/ossutil/1.7.18/ossutil64
    chmod 755 ossutil64 && sudo mv ossutil64 /usr/local/bin/ossutil
    ossutil cp build/artifact.zip \
      oss://my-bucket/ci-builds/${{ github.sha }}/artifact.zip
```

### Terraform (state storage backend)

```hcl
terraform {
  backend "oss" {
    bucket   = "my-terraform-state"
    key      = "prod/terraform.tfstate"
    region   = "cn-hangzhou"
    tablestorage_endpoint = "https://my-terraform-locks.cn-hangzhou.ots.aliyuncs.com"
  }
}
```

## Common Patterns

### Generate Presigned URL for Limited-Time Access

Use case: Email link that allows download for 1 hour.

```bash
ossutil sign oss://my-bucket/reports/q1.pdf --timeout 3600
```

### Batch Upload with `ossutil`

```bash
# Sync a local directory to OSS
ossutil sync /local/data/ oss://my-bucket/data/

# With pattern filter
ossutil sync /local/logs/ oss://my-bucket/logs/ --include "*.log.gz"
```

### Audit Recent Access (via logging)

```bash
# Enable logging to log-bucket first (one-time)
aliyun oss PutBucketLogging --Bucket my-bucket \
  --BucketLoggingStatus '{"LoggingEnabled":{"TargetBucket":"log-bucket","TargetPrefix":"access/"}}'

# Tail recent access logs
ossutil cat oss://log-bucket/access/2026-06-04-*
```

## Environment Variable Loading

Credentials can be sourced from multiple locations:

```
Shell env (highest) > `.env` file > ossutil config > aliyun config > defaults (lowest)
```

### `.env` File Format

```ini
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
ALIBABA_CLOUD_REGION_ID=cn-hangzhou
OSS_BUCKET=my-bucket
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

> **Security:** `.env` MUST be in `.gitignore`. Never commit credentials.

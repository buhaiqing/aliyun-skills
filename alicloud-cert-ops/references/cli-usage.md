---
name: alicloud-cert-ops-cli-usage
description: >-
  CAS CLI usage guide for alicloud-cert-ops — 50+ operations,
  JSON paths, JMESPath examples, coverage gaps. Part of alicloud-cert-ops.
license: MIT
metadata:
  type: reference
  skill: alicloud-cert-ops
  version: "1.0.0"
  last_updated: "2026-06-25"
---

# CLI Usage — CAS

## Install

```bash
aliyun plugin install --names aliyun-cli-cas
```

## Credential Configuration

CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
or `~/.aliyun/config.json`. Never hardcode secrets.

## Output Conventions

- JSON by default — no `--output json` needed
- `--output cols=A,B rows=X.Y[]` for tabular JMESPath extraction
- `--output table` for full table format

## Coverage Matrix

| Category | Operations | CLI Coverage |
|----------|-----------|-------------|
| **Read** | ListUserCertificateOrder, ListCert, GetUserCertificateDetail, DescribeCertificateState, DescribeDeploymentJob, DescribeDeploymentJobStatus, ListCloudResources, ListDeploymentJob, ListDeploymentJobCert, ListDeploymentJobResource, ListContact, DescribePackageState, GetInstanceSummary | Full |
| **Write** | UploadUserCertificate, CreateDeploymentJob, CreateCsr, UpdateDeploymentJob, UpdateDeploymentJobStatus, UpdateWorkerResourceStatus, MoveResourceGroup | Full |
| **Delete** | RevokeCertificate, DeleteUserCertificate, DeleteCertificateRequest, DeleteDeploymentJob, DeleteCsr, DeleteCloudAccess | Full |
| **Deploy** | CreateDeploymentJob, DescribeDeploymentJob, DescribeDeploymentJobStatus, ListDeploymentJob, ListDeploymentJobCert, ListDeploymentJobResource, ListWorkerResource | Full |

## Key JSON Paths

```bash
# ListUserCertificateOrder — extract certificate IDs
aliyun cas ListUserCertificateOrder --OrderType CERT --ShowSize 50 \
  --output cols=CertificateId,Domain,Status,NotAfter rows=Orders[].{CertificateId,Domain,Status,NotAfter}

# GetUserCertificateDetail — extract key fields
aliyun cas GetUserCertificateDetail --CertId 123456789 \
  --output cols=CertificateId,Domain,NotBefore,NotAfter,Status,Issuer rows=.

# ListCloudResources — extract deployment targets
aliyun cas ListCloudResources --CertIds '["123456789"]' \
  --output cols=ResourceId,CloudProduct,Region rows=Resources[].

# DescribeDeploymentJobStatus — extract job state
aliyun cas DescribeDeploymentJobStatus --JobId 111222 \
  --output cols=Status,TotalCount,SuccessCount,FailedCount rows=.

# DescribePackageState — extract quota usage
aliyun cas DescribePackageState \
  --output cols=TotalCount,UsedCount rows=.
```

## Core Commands

### Certificate Operations

```bash
# List all certificates (with pagination)
aliyun cas ListUserCertificateOrder \
  --OrderType CERT \
  --ShowSize 50 \
  --CurrentPage 1

# Filter by status
aliyun cas ListUserCertificateOrder \
  --OrderType CERT \
  --Status WILLEXPIRED \
  --ShowSize 50

# Get certificate detail
aliyun cas GetUserCertificateDetail \
  --CertId {{user.cert_id}}

# Describe certificate application state
aliyun cas DescribeCertificateState \
  --OrderId {{user.order_id}}

# List certificates in warehouse
aliyun cas ListCert \
  --SourceType upload \
  --Status ISSUE \
  --ShowSize 50
```

### Upload Operations

```bash
# Upload non-SM2 certificate
aliyun cas UploadUserCertificate \
  --Name "{{user.cert_name}}" \
  --Cert "{{user.cert_pem}}" \
  --Key "{{user.key_pem}}"

# Upload SM2 (国密) certificate
aliyun cas UploadUserCertificate \
  --Name "{{user.cert_name}}" \
  --SignCert "{{user.sign_cert_pem}}" \
  --SignPrivateKey "{{user.sign_key_pem}}" \
  --EncryptCert "{{user.encrypt_cert_pem}}" \
  --EncryptPrivateKey "{{user.encrypt_key_pem}}"
```

### Deployment Operations

```bash
# Create deployment job
aliyun cas CreateDeploymentJob \
  --CertIds "{{user.new_cert_id}}" \
  --ContactIds "{{user.contact_id}}" \
  --JobType "{{user.job_type}}" \
  --Name "cert-replacement-$(date +%Y%m%d-%H%M%S)" \
  --ResourceIds "{{user.resource_ids}}"

# Poll deployment status (bash loop)
for i in $(seq 1 30); do
  STATUS=$(aliyun cas DescribeDeploymentJobStatus --JobId {{user.job_id}} | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Status',''))")
  echo "[$(date +%H:%M:%S)] Status: $STATUS"
  [ "$STATUS" = "success" ] && echo "SUCCESS" && break
  [ "$STATUS" = "failed" ] && echo "FAILED" && break
  [ $i -eq 30 ] && echo "TIMEOUT" && break
  sleep 10
done

# Get deployment job detail
aliyun cas DescribeDeploymentJob \
  --JobId {{user.job_id}}

# List deployment job certificates
aliyun cas ListDeploymentJobCert \
  --JobId {{user.job_id}}
```

### Revocation / Deletion

```bash
# Revoke certificate (irreversible)
aliyun cas RevokeCertificate \
  --InstanceId "{{user.old_cert_id}}"

# Delete uploaded certificate
aliyun cas DeleteUserCertificate \
  --CertId "{{user.old_cert_id}}"
```

### Resource Discovery

```bash
# List cloud resources using a certificate
aliyun cas ListCloudResources \
  --CertIds '["{{user.cert_id}}"]'

# List resources by product
aliyun cas ListCloudResources \
  --CloudProduct ALB \
  --CloudName aliyun

# List contacts
aliyun cas ListContact

# Describe package state (quota)
aliyun cas DescribePackageState

# List deployment jobs
aliyun cas ListDeploymentJob \
  --JobType CLB \
  --ShowSize 50
```

## Deployment Product Verification

```bash
# ALB — verify certificate bound
aliyun alb DescribeLoadBalancerCertificates \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --LoadBalancerId "{{user.lb_id}}"

# SLB — verify certificate bound
aliyun slb DescribeServerCertificates \
  --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}

# CDN — verify HTTPS config
aliyun cdn DescribeDomainCertificateInfo \
  --DomainName "{{user.domain}}"

# OSS — verify HTTPS config
aliyun oss GetBucketWebsite \
  --BucketName "{{user.bucket}}"
```

## Credential Masking Rules

> NEVER log or echo certificate private key content.
> PEM content via `--Cert` / `--Key` flags is acceptable when passed through CLI.
> SKILL.md ensures `--Key` value is injected via variable, not hardcoded.

| Safe Pattern | Unsafe Pattern |
|-------------|---------------|
| `--Key "{{user.key_pem}}"` | `--Key "MIIEowI..."` (inline secret) |
| `test -n "$CERT_KEY" && echo "Key configured"` | `echo "$CERT_KEY"` |
| Mask in logs: `Key=***` | `Key=MIIEowI...` |

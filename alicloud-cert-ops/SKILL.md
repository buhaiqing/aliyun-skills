---
name: alicloud-cert-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba Cloud
  SSL/TLS certificates — including certificate replacement, upload, deployment to cloud
  products (ALB/SLB/NLB/CDN/WAF/OSS/APIGateway/FC), verification, revocation, and
  lifecycle management. User mentions "SSL证书", "TLS证书", "证书替换", "证书续费",
  "证书部署", "HTTPS证书", "CAS", "数字证书", "certificate", "SSL", "TLS", or describes
  scenarios (e.g. "证书快过期了", "替换证书", "部署证书到SLB") even without naming
  the product directly. Not for KMS key management, RAM permissions, or billing.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  CAS endpoints.
metadata:
  author: alicloud
  version: "1.0.2"
  last_updated: "2026-07-24"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "CAS 2020-04-07 / https://help.aliyun.com/zh/certificate-certificate-service"
  cli_applicability: "cli-first"
  cli_support_evidence: >-
    Confirmed via `aliyun help cas` — CAS supports 50+ ops via `aliyun cas <ApiName>`.
    Key ops: ListUserCertificateOrder, UploadUserCertificate, CreateDeploymentJob,
    DescribeDeploymentJob, DescribeDeploymentJobStatus, RevokeCertificate,
    GetUserCertificateDetail, ListCloudResources, ListCert.
    Install: `aliyun plugin install --names aliyun-cli-cas`.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_SECRET_KEY
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud Certificate (CAS) Operations Skill

## Overview

Alibaba Cloud **Certificate Service (CAS / 数字证书管理服务)** provides centralized
SSL/TLS certificate lifecycle management — upload, purchase, deploy to cloud products,
monitor expiration, and revoke. This skill covers the **complete SSL certificate
replacement workflow** end-to-end.

**Key deployment targets:**
| Product | CloudProduct Code | 说明 |
|---------|------------------|------|
| ALB | `ALB` | Application Load Balancer |
| SLB | `SLB` | Server Load Balancer (传统型) |
| NLB | `NLB` | Network Load Balancer |
| CDN | `CDN` | Content Delivery Network |
| DCDN | `DCDN` | Dynamic CDN |
| WAF | `WAF` | Web Application Firewall |
| APIGateway | `APIGateway` | API Gateway |
| OSS | `OSS` | Object Storage Service |
| FC | `FC` | Function Compute |
| SAE | `SAE` | Serverless App Engine |
| GA | `GA` | Global Accelerator |
| MSE | `MSE` | Microservices Engine |
| Cross-cloud | AWS/Tencent/Huawei | AWS CloudFront/CLB/ALB, Tencent CDN/CLB/WAF, Huawei CDN |

## Product Skill Mission

| Pillar | Mission | This skill |
|--------|---------|-----------|
| **Domain colleague** | SSL cert lifecycle expertise + deployment context | Pre-flight, `{{user.*}}`/`{{env.*}}`/`{{output.*}}`, Delegation Rules |
| **Harnessed delivery** | Complete cert replacement with observable outcomes | GCL gate, wrapper-first CLI, diagnostic logging |

## Trigger & Scope

### SHOULD Use This Skill When
- User mentions "SSL证书替换" / "证书替换" / "certificate replacement"
- User mentions "证书部署" / "部署证书到XX" / "deploy certificate"
- User mentions "证书续费" / "certificate renewal"
- User mentions "证书快过期" / "certificate expiring" / "证书过期"
- User mentions "CAS" / "数字证书管理服务" / "SSL证书服务"
- User mentions "上传证书" / "upload certificate"
- User mentions "证书吊销" / "revoke certificate"
- User asks to check which resources use a certificate
- User asks to monitor certificate expiration

### SHOULD NOT Use This Skill When
- Task is about **KMS encryption keys** → delegate to: `alicloud-kms-ops`
- Task is about **RAM permissions** for certificates → delegate to: `alicloud-ram-ops`
- Task is about **SLB/ALB/NLB full configuration** beyond certificate binding → delegate to respective skill
- Task is about **CDN/WAF/OSS full configuration** beyond certificate → delegate to respective skill
- User insists on **console-only** flows → state limitation

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作（上传/部署/吊销/删除）执行 GCL 评审 |
| SLB 证书绑定 | `alicloud-slb-ops` | 通过 SLB API 绑定已有证书到监听器 |
| ALB 证书绑定 | `alicloud-alb-ops` | 通过 ALB API 绑定已有证书 |
| CDN HTTPS 配置 | `aliyun cdn` CLI | 通过 CDN API 配置 HTTPS 证书 |
| OSS HTTPS 配置 | `alicloud-oss-ops` | 通过 OSS API 配置 Bucket HTTPS |

## Variable Convention

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | AK from environment | NEVER ask user |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | SK from environment | NEVER ask user |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Region from environment | Use default if skill allows |
| `{{user.region}}` | User-supplied region | Ask once |
| `{{user.cert_id}}` | CAS CertificateId | From ListUserCertificateOrder |
| `{{user.order_id}}` | CAS OrderId | From ListUserCertificateOrder |
| `{{user.cert_name}}` | User-supplied cert name | Ask once |
| `{{user.job_id}}` | Deployment JobId | From CreateDeploymentJob |
| `{{user.cloud_product}}` | Target product code | ALB/SLB/NLB/CDN/WAF/... |
| `{{output.cert_id}}` | CertificateId from API | Parse `$.CertificateId` |
| `{{output.job_id}}` | JobId from API | Parse `$.ID` |
| `{{output.request_id}}` | Global RequestId | Parse `$.RequestId` |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be collected interactively when missing.

> **Credential Masking (MANDATORY):** NEVER log, print, or expose SK, private key content,
> or certificate private key. Replace all secrets with `***`.

## Diagnostic Log Format

Every CAS operation MUST emit structured diagnostic logs per
[`docs/diagnostic-logging-standard.md`](../docs/diagnostic-logging-standard.md):

```
[HH:MM:SS] [PHASE] key=value
```

| PHASE | CAS Skill Usage |
|-------|---------------|
| `DIAG` | Environment snapshot, pre-flight checks |
| `EXEC` | `aliyun cas <Action>` being executed |
| `RESULT` | Key=cert_id, domain, status, job_id |
| `WARN` | Retrying, non-critical failures |
| `ERROR` | Error type + fix suggestion |
| `SUMMARY` | End of phase summary |

**Example trace output:**
```
[13:45:01] [DIAG] PHASE=discovery SKILL=cert-ops REGION=cn-hangzhou
[13:45:02] [EXEC] aliyun cas ListUserCertificateOrder --OrderType UPLOAD --ShowSize 50
[13:45:03] [RESULT] Found=3 certs Domain=*.example.com Status=ISSUED
[13:45:05] [EXEC] aliyun cas GetUserCertificateDetail --CertId 123456789
[13:45:06] [RESULT] CertId=123456789 Domain=*.example.com NotAfter=2026-12-31
[13:45:08] [EXEC] aliyun cas ListCloudResources --CertIds '["123456789"]'
[13:45:09] [RESULT] Resources=2 CloudProduct=ALB,SLB
[13:45:10] [SUMMARY] PHASE=discovery Found=1 certs DeployedTo=ALB,SLB
```

**ERROR TYPE — CAS specific (extend per product):**
```
[ERROR] TYPE=INVALID_PARAM   FIX=Verify param names per CAS API spec
[ERROR] TYPE=RESOURCE_NOT_FOUND FIX=Run ListUserCertificateOrder to get valid CertId
[ERROR] TYPE=CERT_EXPIRED    FIX=Upload a new certificate before deployment
[ERROR] TYPE=CERT_REVOKED    FIX=Certificate is already revoked — cannot deploy
[ERROR] TYPE=QUOTA_EXCEEDED  FIX=Check DescribePackageState for quota usage
[ERROR] TYPE=CONTACT_INVALID FIX=Run ListContact to get valid ContactId
[ERROR] TYPE=DEPLOYMENT_FAILED FIX=Run DescribeDeploymentJob for per-resource status
[WARN ] TYPE=THROTTLING     FIX=Retry after backoff (retryable)
[WARN ] TYPE=INTERNAL_ERROR  FIX=Retry after backoff (retryable)
```

### Credential Masking in Traces

| Field | Safe in Trace? | Mask Example |
|-------|--------------|-------------|
| `CertId` (number) | Yes | `CertId=123456789` |
| `Domain` | Yes | `Domain=*.example.com` |
| `Status` | Yes | `Status=ISSUED` |
| `NotAfter` | Yes | `NotAfter=2026-12-31` |
| `--Key` / `--Cert` inline content | **NEVER** | `Key=***` |
| `PlaintextKey` in response | **NEVER** | redact immediately |
| `BEGIN CERTIFICATE` in logs | **NEVER** | `Cert=***` |
| JobId / RequestId | Yes | `JobId=111222` |

## GCL Trace Artifact

GCL traces MUST be persisted to:
```
./audit-results/gcl-trace-cert-ops-{ISO-timestamp}.json
```

Per [`AGENTS.md` §12.6`](../docs/gcl-spec.md#generator-critic-loop-gcl--implementation-spec).

## Quick Start

### Prerequisites
```bash
# 1. Install CAS CLI plugin
aliyun plugin install --names aliyun-cli-cas

# 2. Verify CLI
aliyun cas ListUserCertificateOrder --ShowSize 10

# 3. Configure credentials (if not already)
# Uses env vars ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET or ~/.aliyun/config.json
```

### Your First Command — List All Certificates
```bash
aliyun cas ListUserCertificateOrder \
  --OrderType CERT \
  --ShowSize 50
```

---

## Five Core Standards

| # | Standard | How This Skill Fulfills It |
|---|----------|----------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT triggers + delegation rules |
| 2 | **Structured I/O** | `{{env.*}}`/`{{user.*}}`/`{{output.*}}` placeholders |
| 3 | **Explicit Steps** | Pre-flight → Execute → Validate → Recover for every op |
| 4 | **Failure Strategies** | ≥10 error codes with HALT vs retry |
| 5 | **Single Responsibility** | CAS cert lifecycle only; cross-product via delegation |

---

## ⭐ SSL Certificate Replacement — Complete Workflow

> **This is the primary workflow this skill serves.** Follow these 5 phases in order.

### Phase 1: Discovery — Find the Certificate to Replace

#### Step 1.1: List all certificates
```bash
aliyun cas ListUserCertificateOrder \
  --OrderType CERT \
  --ShowSize 50
```

**Parse the response** — for each cert, record:
- `CertificateId` → `{{user.cert_id}}`
- `OrderId` → `{{user.order_id}}`
- `Domain` — the domain name
- `Status` — `ISSUED` (已签发) / `WILLEXPIRED` (即将过期) / `EXPIRED` (已过期) / `REVOKED` (已吊销)

#### Step 1.2: Get certificate details (including expiration date)
```bash
aliyun cas GetUserCertificateDetail \
  --CertId {{user.cert_id}}
```

**Present to user:**

| Field | JSON Path | Description |
|-------|-----------|-------------|
| CertificateId | `$.CertificateId` | Cert ID |
| Domain | `$.Domain` | Domain name |
| Sans | `$.Sans` | Subject Alternative Names |
| Status | `$.Status` | ISSUED / WILLEXPIRED / EXPIRED |
| Issuer | `$.Issuer` | CA issuer |
| NotBefore | `$.NotBefore` | Valid from (UTC) |
| NotAfter | `$.NotAfter` | Expires on (UTC) |
| FirstDomain | `$.FirstDomain` | Primary domain |

#### Step 1.3: Check which cloud products use this certificate
```bash
aliyun cas ListCloudResources \
  --CertIds '["{{user.cert_id}}"]'
```

**Present to user — current deployment map:**

| Field | JSON Path | Description |
|-------|-----------|-------------|
| ResourceId | `$.Resources[].ResourceId` | Instance ID on target product |
| CloudProduct | `$.Resources[].CloudProduct` | Target product code (ALB/SLB/CDN/...) |
| CloudProductInstanceId | `$.Resources[].CloudProductInstanceId` | Instance identifier |
| Region | `$.Resources[].Region` | Deployment region |

> **Critical context:** This tells you **exactly which products need redeployment** after upload.

---

### Phase 2: Upload New Certificate to CAS

#### Step 2.1: Collect certificate files from user

| Item | Source | Format | Required |
|------|--------|--------|----------|
| Certificate (PEM) | CA issued / user provided | PEM text | Yes (非国密) |
| Private Key (PEM) | User generated | PEM text | Yes (非国密) |
| SignCert | 国密签名证书 | PEM text | Yes (国密) |
| SignPrivateKey | 国密签名私钥 | PEM text | Yes (国密) |
| EncryptCert | 国密加密证书 | PEM text | Conditional |
| EncryptPrivateKey | 国密加密私钥 | PEM text | Conditional |
| Cert Name | User picks | String ≤ 63 chars | Yes |

#### Step 2.2: Pre-flight — validate PEM content (NON-DESTRUCTIVE)

```bash
# Verify certificate is valid PEM format
python3 -c "
import sys
data = sys.stdin.read()
if '-----BEGIN CERTIFICATE-----' not in data:
    print('ERROR: Not a valid PEM certificate')
    sys.exit(1)
if '-----END CERTIFICATE-----' not in data:
    print('ERROR: PEM end marker missing')
    sys.exit(1)
print('OK: Valid PEM certificate format')
"
```

> **Security:** Private key must be PEM format too. Never log key content.

#### Step 2.3: Check for duplicate names
```bash
aliyun cas ListUserCertificateOrder \
  --OrderType UPLOAD \
  --Keyword "{{user.cert_name}}"
```

If a cert with the same name exists → ask user to choose a different name.

#### Step 2.4: Upload certificate (Pre-flight Safety Gate)

> **GCL REQUIRED:** This is a write operation. Run GCL before executing.

**Upload non-SM2 (standard) certificate:**
```bash
aliyun cas UploadUserCertificate \
  --Name "{{user.cert_name}}" \
  --Cert "{{user.cert_pem_content}}" \
  --Key "{{user.key_pem_content}}"
```

**Upload SM2 (国密) certificate:**
```bash
aliyun cas UploadUserCertificate \
  --Name "{{user.cert_name}}" \
  --SignCert "{{user.sign_cert_pem}}" \
  --SignPrivateKey "{{user.sign_key_pem}}" \
  --EncryptCert "{{user.encrypt_cert_pem}}" \
  --EncryptPrivateKey "{{user.encrypt_key_pem}}"
```

#### Step 2.5: Validate upload — find the new cert's ID
```bash
aliyun cas ListUserCertificateOrder \
  --OrderType UPLOAD \
  --Keyword "{{user.cert_name}}"
```

Parse `$.Orders[].CertificateId` → `{{output.new_cert_id}}`

---

### Phase 3: Deploy New Certificate to Target Products

#### Step 3.1: Pre-flight — get contact list for deployment

```bash
aliyun cas ListContact
```

Parse `$.Contacts[].Id` → `{{user.contact_id}}`
If no contacts exist → create one first via console or API.

#### Step 3.2: Pre-flight — get resource IDs to deploy to

Based on Phase 1.3 output (current deployment map), collect the `ResourceId` values
for the target products.

If redeploying to **different resources**, query available resources:
```bash
aliyun cas ListCloudResources \
  --CloudProduct {{user.cloud_product}}
```

#### Step 3.3: Determine JobType

| Scenario | JobType | 说明 |
|----------|---------|------|
| Deploy to ALB/SLB/NLB | `CLB` | 负载均衡 |
| Deploy to CDN/DCDN | `CDN` | 内容分发 |
| Deploy to OSS | `OSS` | 对象存储 |
| Deploy to WAF | `WAF` | Web应用防火墙 |
| Deploy to APIGateway | `APIGateway` | API网关 |
| Deploy to multiple product types | `Mutiple` | 混合部署 |
| Deploy to FC/SAE/MSE/GA | `FC`/`SAE`/`MSE`/`GA` | 各产品对应类型 |

#### Step 3.4: Create deployment job (Pre-flight Safety Gate)

> **GCL REQUIRED:** This deploys certificates to production systems.

```bash
aliyun cas CreateDeploymentJob \
  --CertIds "{{user.new_cert_id}}" \
  --ContactIds "{{user.contact_id}}" \
  --JobType "{{user.job_type}}" \
  --Name "cert-replacement-$(date +%Y%m%d-%H%M%S)" \
  --ResourceIds "{{user.resource_ids}}"
```

**Parse `$.ID`** → `{{output.job_id}}`

#### Step 3.5: Monitor deployment progress

Poll every 10 seconds until terminal state:
```bash
aliyun cas DescribeDeploymentJobStatus \
  --JobId {{output.job_id}}
```

**Valid states:**
| State | Meaning | Action |
|-------|---------|--------|
| `pending` | 等待执行 | Wait 10s, poll again |
| `running` | 部署中 | Wait 10s, poll again |
| `success` | 部署成功 | Proceed to Phase 4 |
| `failed` | 部署失败 | Go to Failure Recovery |
| `partial_success` | 部分成功 | Report which failed, retry failed ones |
| `canceled` | 已取消 | Investigate and retry |

**Poll loop (30 × 10s = 5min max):**
```bash
for i in $(seq 1 30); do
  STATUS=$(aliyun cas DescribeDeploymentJobStatus --JobId {{output.job_id}} | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Status',''))")
  echo "[$(date +%H:%M:%S)] Status: $STATUS"
  [ "$STATUS" = "success" ] && echo "✅ Deployment succeeded" && break
  [ "$STATUS" = "failed" ] && echo "❌ Deployment failed" && break
  [ "$STATUS" = "partial_success" ] && echo "⚠️ Partial success" && break
  [ "$STATUS" = "canceled" ] && echo "❌ Deployment canceled" && break
  [ $i -eq 30 ] && echo "❌ Timeout after 5min" && break
  sleep 10
done
```

---

### Phase 4: Verify Deployment

#### Step 4.1: Check deployment job details
```bash
aliyun cas DescribeDeploymentJob \
  --JobId {{output.job_id}}
```

Present: total count, success count, failed count.

#### Step 4.2: Verify per-resource deployment status
```bash
aliyun cas ListDeploymentJobCert \
  --JobId {{output.job_id}}
```

For each resource — verify `Status = deployed`.

#### Step 4.3: Product-specific verification

**ALB/SLB:**
```bash
aliyun alb DescribeLoadBalancerCertificates --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} \
  --LoadBalancerId "{{user.lb_id}}"
```

**CDN:**
```bash
aliyun cdn DescribeDomainCertificateInfo --DomainName "{{user.domain}}"
```

**OSS:**
```bash
aliyun oss GetBucketWebsite --Bucket {{user.bucket}}
```

> **Tip:** The fastest verification is to open the domain in a browser and check
> the certificate details (Issuer, Expiry, Domain match).

---

### Phase 5: Post-Deployment Cleanup (Optional)

#### Step 5.1: Revoke old certificate (if replacing, Pre-flight Safety Gate)

> **GCL REQUIRED + EXPLICIT USER CONFIRMATION MANDATORY.** Revocation is irreversible.

**Confirm with user:**
- Old cert: `{{user.old_cert_id}}` (domain: `{{user.domain}}`)
- New cert: `{{output.new_cert_id}}`
- Revocation reason: `certificate replacement`

```bash
aliyun cas RevokeCertificate \
  --InstanceId "{{user.old_cert_id}}"
```

#### Step 5.2: Delete old certificate from CAS (after confirmation)
> **GCL REQUIRED + SAFETY GATE.**

```bash
aliyun cas DeleteUserCertificate \
  --CertId "{{user.old_cert_id}}"
```

---

## Quality Gate (GCL)

**Recommended** rollout per [`AGENTS.md` §12](../docs/gcl-spec.md#generator-critic-loop-gcl--implementation-spec).

| Aspect | Setting |
|--------|---------|
| Required? | **Recommended** (Phase 1, first rollout) |
| `max_iter` | 3 |
| Most-scrutinized | `UploadUserCertificate`, `CreateDeploymentJob`, `RevokeCertificate`, `DeleteUserCertificate` |
| Hard rule | Private key / PEM cert content MUST NOT appear in any trace value |

### Risk Classification

| Operation | Risk Level | GCL? | Hard Gate |
|-----------|-----------|-------|-----------|
| `UploadUserCertificate` | Medium | Recommended | User confirms name uniqueness; no inline secret |
| `CreateDeploymentJob` | High | Recommended | User confirms target resources; JobType matches product |
| `RevokeCertificate` | High | Recommended | **Safety Gate**: explicit user confirmation — irreversible |
| `DeleteUserCertificate` | High | Recommended | **Safety Gate**: explicit user confirmation — irreversible |
| `Describe/List/Get` | Low | Skip | Single-shot pre-flight sufficient |

### Credential Hygiene (Critical for CAS)

CAS operations pass PEM certificate content and private keys. **These MUST NOT appear in traces.**

| Pattern | Risk | Action |
|---------|------|--------|
| `--Key "MIIEow..."` (inline secret) | Credential Hygiene = 0 | Use `--Key "{{user.key_var}}"` via env/file |
| `--Cert "-----BEGIN..."` (inline cert) | Credential Hygiene = 0 | Pass via variable reference |
| `PlaintextKey: "..."` in JSON response | Safety = 0 | One-shot display; redact in trace |
| `BEGIN PRIVATE KEY` in logs | Safety = 0 | ABORT immediately |
| `BEGIN CERTIFICATE` in logs | Credential Hygiene = 0 | Redact; keep domain name only |

### Suggested Hard Rules for GCL

- `UploadUserCertificate`: User must confirm cert name is unique; PEM content passed via variable, not inline
- `CreateDeploymentJob`: User must confirm target ResourceIds are correct; JobType matches product type
- `RevokeCertificate`: User must explicitly type "CONFIRM REVOKE" for the specific CertId + Domain
- `DeleteUserCertificate`: User must confirm cert is no longer deployed (via ListCloudResources)

### Delegation

| Operation | Delegates To | For |
|-----------|-------------|-----|
| ALB HTTPS binding | `alicloud-alb-ops` | Certificate binding to ALB listener |
| SLB HTTPS binding | `alicloud-slb-ops` | Certificate binding to SLB listener |
| CDN HTTPS config | `aliyun cdn` | CDN HTTPS certificate configuration |
| OSS HTTPS config | `alicloud-oss-ops` | OSS bucket HTTPS configuration |

### Changelog
1.0.0 | 2026-06-25 | Initial GCL recommended section.

---

## Reference Operations

### Operation: ListCertificates (快速查询)

```bash
aliyun cas ListCert \
  --SourceType upload \
  --Status ISSUE \
  --ShowSize 50
```

### Operation: GetUserCertificateDetail (获取证书详情)

```bash
aliyun cas GetUserCertificateDetail \
  --CertId {{user.cert_id}}
```

**提示词示例：**
- "查看证书详情" / "证书信息" / "证书什么时候到期"
- "查询这个证书的域名和有效期" / "看看证书状态"

**输出字段：**

| Field | JSON Path | Description |
|-------|-----------|-------------|
| CertificateId | `$.CertificateId` | 证书 ID |
| Domain | `$.Domain` | 主域名 |
| Sans | `$.Sans` | 泛域名（SAN） |
| Status | `$.Status` | ISSUED / WILLEXPIRED / EXPIRED / REVOKED |
| Issuer | `$.Issuer` | 签发机构 |
| NotBefore | `$.NotBefore` | 有效期起始（UTC） |
| NotAfter | `$.NotAfter` | 过期时间（UTC） |
| FirstDomain | `$.FirstDomain` | 首个域名 |

**注意：** `--CertFilter true` 可防止返回私钥内容（Cert/Key 字段不返回）。

### Operation: DescribeCertificateState (查询申请订单状态)

```bash
aliyun cas DescribeCertificateState \
  --OrderId {{user.order_id}}
```

States: `pending` → `verifying` → `checking` → `issued` (or `failed`)

### Operation: DescribeDeploymentJob (查看部署任务详情)

```bash
aliyun cas DescribeDeploymentJob \
  --JobId {{user.job_id}}
```

### Operation: ListDeploymentJob (查看部署任务列表)

```bash
aliyun cas ListDeploymentJob \
  --JobType {{user.job_type}} \
  --ShowSize 50
```

### Operation: ListUserCertificateOrder (完整证书+订单列表)

```bash
aliyun cas ListUserCertificateOrder \
  --OrderType CERT \
  --Status WILLEXPIRED \
  --ShowSize 50
```

Filter by status to find expiring certificates proactively.

### Operation: CancelCertificateForPackageRequest (取消/吊销证书)

- If order is `ISSUED` → **revokes** the certificate
- If order is `CHECKING` → **cancels** the pending application

```bash
aliyun cas CancelCertificateForPackageRequest \
  --OrderId {{user.order_id}}
```

---

## Prerequisites

```bash
# 1. Install CAS plugin
aliyun plugin install --names aliyun-cli-cas

# 2. Verify
aliyun cas ListUserCertificateOrder --ShowSize 5

# 3. Credentials (env vars — preferred for agent)
export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIYUN_ACCESS_KEY_ID}}"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIYUN_ACCESS_KEY_SECRET}}"
export ALIYUN_DEFAULT_REGION="{{env.ALIYUN_DEFAULT_REGION:-cn-hangzhou}}"
```

---

## Reference Directory

| File | Purpose |
|------|---------|
| [references/core-concepts.md](references/core-concepts.md) | CAS architecture, cert types, limits |
| [references/cli-usage.md](references/cli-usage.md) | Full CLI command reference |
| [references/troubleshooting.md](references/troubleshooting.md) | ≥10 error codes + recovery |
| [references/api-sdk-usage.md](references/api-sdk-usage.md) | API operation map |
| [references/integration.md](references/integration.md) | Go SDK fallback |
| [references/well-architected-assessment.md](references/well-architected-assessment.md) | Security/Stability/Cost pillars |
| [assets/eval_queries.json](assets/eval_queries.json) | Trigger accuracy queries |
| [scripts/harness-lib.sh](scripts/harness-lib.sh) | Runtime harness + auto-repair |

---

## Well-Architected Framework

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| **安全 (Security)** | Private key never logged; cert upload via env var; HTTPS enforcement | `references/well-architected-assessment.md` §2.1 |
| **稳定 (Stability)** | Pre-deployment discovery; rollback plan; phased deployment | `references/well-architected-assessment.md` §2.2 |
| **成本 (Cost)** | Cert pack quota tracking; avoid duplicate purchases | `references/well-architected-assessment.md` §2.3 |
| **效率 (Efficiency)** | Batch deployment; one job → multiple products; CLI automation | `references/well-architected-assessment.md` §2.4 |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-25 | Initial CAS ops skill — complete SSL cert replacement workflow, 5 phases, 15 operations |

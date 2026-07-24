---
name: alicloud-cert-ops-core-concepts
description: >-
  CAS core concepts: certificate types, deployment targets, state machines,
  limits, and KMS differentiation. Part of alicloud-cert-ops.
license: MIT
metadata:
  type: reference
  skill: alicloud-cert-ops
  version: "1.0.0"
  last_updated: "2026-06-25"
---

# CAS Core Concepts

## 1. Product Overview

Alibaba Cloud Certificate Service (CAS / 数字证书管理服务, 原 SSL 证书)
provides centralized SSL/TLS certificate lifecycle management.

- **API version**: 2020-04-07
- **Base endpoint**: cas.aliyuncs.com
- **CLI product**: `cas`
- **CAS ≠ KMS**: CAS manages certificates; KMS manages encryption keys

## 2. Certificate Types

### By Validation Level

| Type | 说明 | Issuance Time |
|------|------|--------------|
| DV | Domain Validation — 域名验证 | Minutes |
| OV | Organization Validation — 组织验证 | 1-3 days |
| EV | Extended Validation — 扩展验证 | 3-7 days |

### By Algorithm

| Type | 说明 | Fields |
|------|------|--------|
| 标准证书 (非国密) | RSA/ECC | `--Cert` + `--Key` |
| 国密证书 (SM2) | OSCCA-compliant | `--SignCert` + `--SignPrivateKey` + `--EncryptCert` + `--EncryptPrivateKey` |

### By Source

| Source | 说明 | OrderType |
|--------|------|-----------|
| upload | 用户上传的证书 | UPLOAD |
| aliyun | 阿里云签发证书 | CERT |

## 3. Certificate Status Machine

| Status | 中文 | 说明 | Next State |
|--------|------|------|-----------|
| PAYED | 待申请 | 已购买，等待提交申请 | CHECKING |
| CHECKING | 审核中 | 域名所有权审核 | ISSUED / CHECKED_FAIL |
| CHECKED_FAIL | 审核失败 | 审核未通过 | — |
| ISSUED | 已签发 | 证书有效 | WILLEXPIRED / REVOKED |
| WILLEXPIRED | 即将过期 | 30天内到期 | EXPIRED |
| EXPIRED | 已过期 | 证书已过期 | — |
| NOTACTIVATED | 未激活 | 证书未激活 | ISSUED |
| REVOKED | 已吊销 | 证书已被吊销 | — |

## 4. Deployment Target Products

### Alibaba Cloud Products

| CloudProduct Code | Product | 说明 |
|-------------------|---------|------|
| ALB | Application Load Balancer | 应用负载均衡 |
| SLB | Server Load Balancer | 传统型负载均衡 |
| NLB | Network Load Balancer | 网络型负载均衡 |
| CDN | CDN | 内容分发网络 |
| DCDN | Dynamic CDN | 全站加速 |
| WAF | Web Application Firewall | Web应用防火墙 |
| APIGateway | API Gateway | API网关 |
| OSS | Object Storage Service | 对象存储 |
| FC | Function Compute | 函数计算 |
| SAE | Serverless App Engine | Serverless应用引擎 |
| GA | Global Accelerator | 全球加速 |
| MSE | Microservices Engine | 微服务引擎 |
| LIVE | Video Live | 视频直播 |
| VOD | Video on Demand | 视频点播 |
| CR | Container Registry | 容器镜像服务 |
| DDoS | DDoS Protection | DDoS防护 |

### Cross-Cloud Products

| Cloud | Prefix | Products |
|-------|--------|---------|
| AWS | AWS | CloudFront, CLB, ALB, NLB |
| Tencent | Tencent | CDN, CLB, WAF |
| Huawei | Huawei | CDN |

## 5. Deployment Job Types

| JobType | Target Products | 说明 |
|---------|---------------|------|
| CLB | SLB, ALB, NLB | 负载均衡类 |
| CDN | CDN, DCDN | 内容分发类 |
| OSS | OSS | 对象存储 |
| WAF | WAF | Web应用防火墙 |
| FC | FC | 函数计算 |
| SAE | SAE | Serverless应用 |
| GA | GA | 全球加速 |
| MSE | MSE | 微服务引擎 |
| Multiple | Mixed | 混合部署 |

## 6. Deployment Job Status Machine

| Status | 中文 | 说明 | Action |
|--------|------|------|--------|
| pending | 等待执行 | 任务等待调度 | Wait 10s, poll again |
| running | 部署中 | 正在部署 | Wait 10s, poll again |
| success | 部署成功 | 全部部署完成 | Proceed to Phase 4 |
| failed | 部署失败 | 部署失败 | Investigate via DescribeDeploymentJob |
| partial_success | 部分成功 | 部分成功部分失败 | Report failed items, retry |
| canceled | 已取消 | 任务被取消 | Investigate and retry |

## 7. Limits and Quotas

| Resource | Limit | Notes |
|----------|-------|-------|
| 单账户证书仓库额度 | 按套餐 | 查询: DescribePackageState |
| 单次部署任务资源数 | ≤50 | ResourceIds 最多50个 |
| 联系人数量 | 按账户 | 查询: ListContact |
| 证书名称长度 | ≤63字符 | 同一账户不可重复 |

## 8. CAS vs KMS

| Dimension | CAS | KMS |
|-----------|-----|-----|
| Manages | SSL/TLS certificates | Encryption keys, secrets |
| Use case | HTTPS, TLS termination | Data encryption, signing |
| CLI product | cas | kms |
| Key operations | Upload, deploy, revoke | CreateKey, Encrypt, Decrypt |
| Has private key | Yes (user-uploaded) | No (never exports key material) |

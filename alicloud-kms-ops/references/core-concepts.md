# Core Concepts — KMS

## Architecture

Alibaba Cloud KMS provides a regional, highly available cryptographic key management service. It operates in two modes:

1. **Default KMS** — Managed by Alibaba Cloud; available in all regions upon activation.
2. **Dedicated KMS Instance (DKMS)** — Dedicated resources offering enhanced security, higher throughput, and compliance. Requires purchasing a KMS instance.

### Service Model

```
┌─────────────────────────────────────────────────┐
│                  KMS Service                     │
│                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │   Keys     │  │  Secrets   │  │  Instances │ │
│  │  (CMK)     │  │ (Generic/  │  │ (Dedicated) │ │
│  │            │  │  DB/RAM)   │  │            │ │
│  └────────────┘  └────────────┘  └────────────┘ │
│                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │  Aliases   │  │    Apps    │  │   Tags     │ │
│  │            │  │ (AAP/CKey) │  │            │ │
│  └────────────┘  └────────────┘  └────────────┘ │
└─────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌──────────────┐              ┌──────────────┐
  │ Cryptographic│              │  Applications│
  │ Operations   │              │  (ECS,RDS,   │
  │ (Encrypt/    │              │  OSS,ACK)    │
  │  Decrypt)    │              │              │
  └──────────────┘              └──────────────┘
```

## Resource Types

### 1. Customer Master Keys (CMK / Keys)

The primary KMS resource. Each key has:

| Attribute | Description |
|-----------|-------------|
| **KeyId** | Globally unique identifier |
| **KeyArn** | Alibaba Cloud Resource Name |
| **KeySpec** | Key type (see below) |
| **KeyUsage** | `ENCRYPT/DECRYPT` or `SIGN/VERIFY` |
| **ProtectionLevel** | `SOFTWARE` (default) or `HSM` (hardware protected) |
| **Origin** | `Aliyun_KMS` (KMS-generated) or `EXTERNAL` (BYOK) |
| **KeyState** | Lifecycle state (see below) |
| ~~Creator~~ | `User` or `Service` |

### KeySpec (Key Types)

| KeySpec | Algorithm | Usage | Max Plaintext | Notes |
|---------|-----------|-------|---------------|-------|
| `Aliyun_AES_256` | AES-256 | ENCRYPT/DECRYPT | 4096 bytes | Default symmetric key |
| `Aliyun_SM4` | SM4 (Chinese standard) | ENCRYPT/DECRYPT | 4096 bytes | OSCCA-compliant regions only |
| `RSA_2048` | RSA-2048 | SIGN/VERIFY; AsymmetricEncrypt/Decrypt | N/A | PKCS#1 v1.5 / OAEP |
| `EC_P256` | ECDSA P-256 | SIGN/VERIFY | N/A | |
| `EC_P256K` | ECDSA P-256K | SIGN/VERIFY | N/A | |
| `EC_SM2` | SM2 (Chinese standard) | SIGN/VERIFY | N/A | OSCCA-compliant regions only |

### Key Lifecycle States

| State | Description | Transitions Allowed |
|-------|-------------|---------------------|
| `Enabled` | Key is active and usable for crypto ops | → Disabled, → PendingDeletion |
| `Disabled` | Key exists but cannot be used | → Enabled, → PendingDeletion |
| `PendingDeletion` | Scheduled for deletion (7–30 day window) | → Enabled (via CancelKeyDeletion) |
| `PendingImport` | Waiting for external key material (BYOK) | → Enabled (after ImportKeyMaterial) |

### Key Rotation

- **Automatic rotation**: Available for software symmetric keys (`Aliyun_AES_256`). Rotation interval: 7–365 days. Creates new key version while preserving key ID.
- **Manual rotation**: Call `CreateKeyVersion` to create a new version.
- Aliases automatically point to the key (not a specific version), enabling transparent rotation.

### 2. Secrets

KMS Secrets provide secure management of credential-like data.

| Secret Type | Description |
|-------------|-------------|
| `Generic` | General plaintext secret (API keys, passwords, certificates) |
| `Extendable` | Custom extensible secrets |
| `Rds` | RDS database credentials (auto-sync) |
| `RAMCredentials` | Short-lived RAM credentials |

Key secret concepts:
- **Versions**: Each secret has multiple versions; `ACSCurrent` marks the active version, `ACSPrevious` marks the prior version
- **Rotation**: Automatic (via rotation policy) or manual (via `PutSecretValue` or `RotateSecret`)
- **Deletion**: Enters 7–30 day scheduled deletion state; can be restored with `RestoreSecret`

### 3. KMS Instances (Dedicated)

Dedicated KMS instances provide:
- VPC-bound networking
- Application Access Points (AAP) for authentication
- Network Rules for IP-based access control
- Client Keys for application identity

## Endpoints

| Endpoint Type | Format | Example |
|---------------|--------|---------|
| Public | `kms.{region}.aliyuncs.com` | `kms.cn-hangzhou.aliyuncs.com` |
| VPC (DKMS) | `kms-vpc.{region}.aliyuncs.com` | `kms-vpc.cn-hangzhou.aliyuncs.com` |
| DKMS Instance | `{instance-id}.cryptoservice.kms.aliyuncs.com` | Per-instance |

## Regional Service

KMS is a **regional service** (not global). Keys are created within a specific region and cannot be directly used across regions. Use `CopyImage` for cross-region scenarios or export/import key material for BYOK.

## Quotas and Limits

| Quota | Default | Notes |
|-------|---------|-------|
| Keys per region | 10,000 | Can raise via support ticket |
| Aliases per region | 1,000 | Per account |
| Secrets per region | 1,000 | Per account |
| Secrets per KMS instance | 10,000 | Per instance |
| Key versions per key | 100 | Symmetric keys |
| Encrypt API data size | 4,096 bytes | Symmetric keys only |
| QPS per API | 50–200 | Depends on operation |
| Monthly Encrypt/Decrypt calls | Unlimited (free tier: 20,000/month for basic) | |

## Dependency Graph

```
KMS Key ──► ECS Disk Encryption
       ──► RDS TDE
       ──► OSS SSE-KMS
       ──► ACK Secrets
       ──► FunctionCompute Encryption
       ──► ActionTrail Log Encryption

KMS Secret ──► RDS Automatic Password Rotation
          ──► Application Credential Store
          ──► ACK Secret Sync

KMS Instance ──► AAP Authentication
            ──► Network Rule ACL
            ──► Client Key Auth
```

## SPOF Analysis

- **Single-region risk**: Keys are region-scoped. If a region has an outage, keys are unavailable.
- **Mitigation**: For cross-region workloads, use BYOK to recreate the same key material in another region.
- **Dedicated instances**: Provide VPC isolation and enhanced SLA; reduce cloud-side SPOF risk.
- **Key deletion protection**: `SetDeletionProtection` prevents accidental deletion.

## Key Policies and Access Control

- KMS uses **RAM** for user/role-based access control
- **Key policies** define who can use a key and for what operations
- **Resource policies** on secrets control access
- AAP (Application Access Points) control application-level access to DKMS instances
- RAM policy actions: `kms:CreateKey`, `kms:DescribeKey`, `kms:Encrypt`, `kms:Decrypt`, etc.

## Cross-Service Integration

| Service | Integration | How |
|---------|-------------|-----|
| ECS | Disk encryption | Specify CMK KeyId when creating encrypted disks |
| RDS | TDE (Transparent Data Encryption) | Select CMK when creating encrypted instance |
| OSS | Server-Side Encryption (SSE-KMS) | Provide CMK in PUT object request |
| ActionTrail | Log encryption | KMS encrypts ActionTrail logs automatically |
| ACK | Kubernetes secrets | KMS-backed secret encryption at rest |

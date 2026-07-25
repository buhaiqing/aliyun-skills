---
name: alicloud-cert-ops-api-sdk-usage
description: >-
  CAS API & SDK operation map for alicloud-cert-ops.
  Part of alicloud-cert-ops.
license: MIT
metadata:
  type: reference
  skill: alicloud-cert-ops
  version: "1.0.1"
  last_updated: "2026-07-24"
---

# API & SDK Usage — CAS

## OpenAPI

- **Spec**: CAS 2020-04-07
- **Base endpoint**: cas.aliyuncs.com
- **Protocol**: RPC-style HTTPS

## Operation Map

| Goal | API OperationId | CLI Subcommand | Risk |
|------|----------------|---------------|------|
| List certs | ListUserCertificateOrder | ListUserCertificateOrder | None |
| Get cert detail | GetUserCertificateDetail | GetUserCertificateDetail | None |
| Describe cert state | DescribeCertificateState | DescribeCertificateState | None |
| List warehouse certs | ListCert | ListCert | None |
| List cloud resources | ListCloudResources | ListCloudResources | None |
| Describe deployment job | DescribeDeploymentJob | DescribeDeploymentJob | None |
| Describe job status | DescribeDeploymentJobStatus | DescribeDeploymentJobStatus | None |
| List deployment jobs | ListDeploymentJob | ListDeploymentJob | None |
| List job certs | ListDeploymentJobCert | ListDeploymentJobCert | None |
| List contacts | ListContact | ListContact | None |
| Describe package state | DescribePackageState | DescribePackageState | None |
| Get asset count | GetAssetCount | GetAssetCount | None |
| Get risk count | GetRiskCount | GetRiskCount | None |
| **Upload cert** | **UploadUserCertificate** | **UploadUserCertificate** | **Medium** |
| **Create deployment job** | **CreateDeploymentJob** | **CreateDeploymentJob** | **High** |
| **Revoke cert** | **RevokeCertificate** | **RevokeCertificate** | **High** |
| **Delete cert** | **DeleteUserCertificate** | **DeleteUserCertificate** | **High** |
| Update job status | UpdateDeploymentJobStatus | UpdateDeploymentJobStatus | Medium |
| Update worker status | UpdateWorkerResourceStatus | UpdateWorkerResourceStatus | Medium |
| Create CSR | CreateCsr | CreateCsr | None |
| Delete CSR | DeleteCsr | DeleteCsr | None |

## Key Request/Response Fields

### UploadUserCertificate

```json
// Request
{
  "Name": "string",          // required, ≤63 chars, unique per account
  "Cert": "string",          // PEM cert (non-SM2)
  "Key": "string",           // PEM key (non-SM2)
  "SignCert": "string",      // SM2 sign cert
  "SignPrivateKey": "string",// SM2 sign key
  "EncryptCert": "string",   // SM2 encrypt cert
  "EncryptPrivateKey": "string" // SM2 encrypt key
}
// Response
{
  "CertId": 123456789,      // new certificate ID
  "RequestId": "..."
}
```

### CreateDeploymentJob

```json
// Request
{
  "CertIds": "123,456",     // comma-separated CertificateIds (max 10)
  "ContactIds": "789",        // comma-separated ContactIds
  "JobType": "CLB",           // CLB/CDN/OSS/WAF/FC/SAE/GA/MSE/Multiple
  "Name": "string",
  "ResourceIds": "res1,res2"  // comma-separated ResourceIds (max 50)
}
// Response
{
  "ID": 111222,             // JobId
  "RequestId": "..."
}
```

### DescribeDeploymentJobStatus

```json
// Response
{
  "Status": "success",      // pending/running/success/failed/partial_success/canceled
  "TotalCount": 10,
  "SuccessCount": 9,
  "FailedCount": 1,
  "RequestId": "..."
}
```

### ListCloudResources

```json
// Response
{
  "Resources": [{
    "ResourceId": "lb-xxx",
    "CloudProduct": "ALB",
    "CloudProductInstanceId": "lb-xxx",
    "Region": "cn-hangzhou"
  }]
}
```

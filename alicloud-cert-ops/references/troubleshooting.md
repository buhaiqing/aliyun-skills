---
name: alicloud-cert-ops-troubleshooting
description: >-
  CAS troubleshooting guide: 12+ error codes, diagnostic order,
  common failure scenarios. Part of alicloud-cert-ops.
license: MIT
metadata:
  type: reference
  skill: alicloud-cert-ops
  version: "1.0.0"
  last_updated: "2026-06-25"
---

# Troubleshooting — CAS

## Diagnostic Order

When certificate deployment fails, follow this order:

```
1. DescribeDeploymentJobStatus
   -> Why: Is the job pending/running/failed/canceled?

2. DescribeDeploymentJob (if failed)
   -> Why: Which specific resource failed?

3. ListCloudResources
   -> Why: Is the target resource still accessible?

4. ListContact
   -> Why: Is the contact valid? ContactId may be stale.

5. GetUserCertificateDetail
   -> Why: Is the certificate still ISSUED and not expired?

6. DescribePackageState
   -> Why: Quota exhausted?
```

## Error Codes (12+)

| Error Code | HTTP | Meaning | Agent Action |
|-----------|------|---------|-------------|
| InvalidParameter | 400 | Request parameter invalid | Fix parameter per API spec; retry once |
| InvalidCertContent | 400 | Certificate PEM format invalid | Verify PEM with `openssl x509 -in cert.pem -text` |
| InvalidKeyContent | 400 | Private key PEM format invalid | Verify key with `openssl rsa -in key.pem -check` |
| CertAlreadyExists | 409 | Certificate name already exists | Use different name; or update existing |
| ResourceNotFound.Certificate | 404 | Certificate does not exist | Verify CertId via ListUserCertificateOrder |
| ResourceNotFound.Job | 404 | Deployment job does not exist | Verify JobId via ListDeploymentJob |
| ResourceNotFound.Contact | 404 | Contact does not exist | ListContact to get valid IDs |
| DeploymentFailed | 500 | Deployment task failed | Check DescribeDeploymentJob for per-resource status |
| ContactInvalid | 400 | Contact ID invalid or expired | ListContact; recreate if needed |
| CertExpired | 400 | Certificate has expired | Upload new certificate; cannot deploy expired cert |
| CertRevoked | 400 | Certificate has been revoked | Cannot deploy revoked certificate |
| QuotaExceeded | 400 | Certificate quota exhausted | Check DescribePackageState; request quota increase |
| InsufficientBalance | 400 | Account balance insufficient | Recharge account |
| Throttling | 429 | API rate limit | Retry with exponential backoff (3x, 10s, 30s) |
| InternalError | 500 | Alibaba Cloud internal error | Retry with backoff; escalate with RequestId |
| Unauthorized | 403 | RAM permission denied | Add cas:* RAM policy |

## Common Failure Scenarios

### Scenario 1: Deployment job stuck in "pending"

**Symptoms**: `DescribeDeploymentJobStatus` returns `pending` after 5 minutes.

**Diagnosis**:
```bash
aliyun cas ListContact
aliyun cas GetUserCertificateDetail --CertId {{user.cert_id}}
```

**Cause**: ContactId may be invalid or deleted; OR certificate is expired/revoked.

**Fix**: Provide a valid active ContactId; check certificate NotAfter.

---

### Scenario 2: Deployment partial_success with failed resources

**Symptoms**: Job status = `partial_success`.

**Diagnosis**:
```bash
aliyun cas DescribeDeploymentJob --JobId {{user.job_id}}
aliyun cas ListDeploymentJobCert --JobId {{user.job_id}}
```

**Cause**: Some resources have outdated certificate bindings; or permission denied on specific product.

**Fix**: Retry failed workers via `UpdateWorkerResourceStatus`; or check product-specific permissions.

---

### Scenario 3: UploadUserCertificate fails with "InvalidCertContent"

**Symptoms**: Upload returns 400 with InvalidCertContent.

**Diagnosis**:
```bash
openssl x509 -in user_cert.pem -text -noout
```

**Cause**: PEM may have extra whitespace, wrong encoding, or missing BEGIN/END markers.

**Fix**: Clean the PEM content; ensure no BOM; BEGIN CERTIFICATE / END CERTIFICATE markers present.

---

### Scenario 4: ListCloudResources returns empty after new upload

**Symptoms**: New certificate not yet visible to ListCloudResources.

**Cause**: ListCloudResources indexes certificates; new uploads may take a few minutes.

**Fix**: Wait 2-5 minutes; retry. This is expected behavior, not an error.

---

### Scenario 5: Certificate status is WILLEXPIRED but still deployed

**Symptoms**: Certificate in CAS shows `WILLEXPIRED`; services still running.

**Cause**: Certificate technically still valid until NotAfter date.

**Fix**: Upload new certificate; deploy via CreateDeploymentJob; verify new cert on services; then revoke old cert.

---

### Scenario 6: RevokeCertificate fails with "CertAlreadyRevoked"

**Symptoms**: Revoke returns error about certificate already revoked.

**Cause**: Certificate was already revoked (status = REVOKED).

**Fix**: No action needed. Log the state. Move to DeleteUserCertificate if needed.

---

### Scenario 7: CreateDeploymentJob fails with "ResourceNotFound.Contact"

**Symptoms**: Deployment job creation fails with 404 Contact.

**Diagnosis**:
```bash
aliyun cas ListContact
```

**Cause**: Contact ID is stale (deleted or invalid).

**Fix**: Create new contact via console (API does not support contact creation); use console to add contact first.

---

### Scenario 8: Deployment to OSS fails with permission error

**Symptoms**: Job shows failed for OSS targets; DescribeDeploymentJobCert shows permission error.

**Cause**: CAS service role may lack OSS write permission.

**Fix**: Grant CAS service role `AliyunCASDefaultRole` the `AliyunOSSFullAccess` policy; retry deployment.

## Escalation

| Situation | Action |
|-----------|--------|
| All retries exhausted | Escalate with RequestId from failed API call |
| CAS service role issue | Check RAM -> CAS -> Trust relationships |
| Cross-cloud deployment failure | Verify cloud account AK/SK permissions in ListCloudAccess |
| Quota exceeded | Contact account manager or submit ticket |

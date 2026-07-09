# Troubleshooting KMS

## Common API Error Codes

| Error Code | HTTP Status | Meaning | Agent Action |
|------------|-------------|---------|--------------|
| `InvalidParameter` | 400 | Request parameter validation failed | Align args with OpenAPI spec; retry once if safe |
| `Forbidden.RAM` | 403 | Insufficient RAM permissions for KMS operation | HALT; delegate to `alicloud-ram-ops` to add `kms:*` policy |
| `KmsNotActivate` | 403 | KMS service not activated for this account | Call `OpenKmsService` to activate, then retry |
| `InvalidAccessKeyId.NotFound` | 404 | AccessKey ID does not exist | HALT; user verifies credential config |
| `SignatureDoesNotMatch` | 403 | Signature verification failed (wrong secret) | HALT; user checks AccessKeySecret |
| `Forbidden.HmacTimestampExpired` | 403 | Request timestamp too old (> 15 min) | HALT; user checks system clock |
| `Forbidden.Throttling` | 429 | API rate limit exceeded | Retry with exponential backoff (3 attempts max) |
| `Forbidden.RequestTooLong` | 400 | Request body exceeds size limits | Split operation or reduce data size |
| `AliasAlreadyExists` | 400 | Alias name already in use | Use different alias name or `UpdateAlias` |
| `AliasNotFound` | 404 | Specified alias does not exist | Verify alias name; suggest `ListAliases` |
| `KeyNotFound` / `InvalidKeyId.NotFound` | 404 | Specified key does not exist | Check KeyId; suggest `ListKeys` |
| `KeyStateInvalid` | 400 | Key in wrong state for operation | Check key state; transition to required state first |
| `PendingDeletion` | 400 | Key is in PendingDeletion state | HALT; suggest `CancelKeyDeletion` to recover |
| `Forbidden.KeyService` | 403 | Key cannot be used for this operation type | Check KeyUsage matches (ENCRYPT/DECRYPT vs SIGN/VERIFY) |
| `QuotaExceeded.Key` | 400 | Key quota exceeded for region | HALT; delete unused keys or raise quota |
| `QuotaExceeded.Secret` | 400 | Secret quota exceeded | HALT; delete unused secrets or raise quota |
| `SecretNameAlreadyExists` | 400 | Secret with this name already exists | Use `PutSecretValue` for new version or choose different name |
| `SecretNotFound` | 404 | Secret does not exist | Check secret name; suggest `ListSecrets` |
| `BackupKeyNotFound` | 404 | Backup key for rotation not found | HALT; verify rotation configuration |
| `InternalError` | 500 | KMS internal server error | Retry with backoff; if persists, escalate with RequestId |
| `ServiceUnavailable` | 503 | KMS service temporarily unavailable | Retry with backoff; check service status page |
| `IllegalParamter.DKMSInstance` | 400 | DKMS instance configuration invalid | Verify instance ID and status via `GetKmsInstance` |

## Diagnostic Order

1. **Check credential validity:**
   ```bash
   aliyun kms DescribeRegions
   ```

2. **Describe the resource by ID:**
   ```bash
   # For keys
   aliyun kms DescribeKey --KeyId "{{user.key_id}}"
   # For secrets
   aliyun kms DescribeSecret --SecretName "{{user.secret_name}}"
   ```

3. **List related resources if API supports filters:**
   ```bash
   aliyun kms ListKeys --Filters '[{"Key":"KeyState","Values":["Enabled"]}]'
   ```

4. **Check regional endpoint and `RegionId` consistency:**
   - KMS is regional; verify the KeyId/Secret exists in the specified region
   - Cross-region key access requires cross-region key material export/import

5. **Verify CLI metadata coverage:**
   ```bash
   aliyun help kms
   ```

6. **Check KMS service activation:**
   ```bash
   aliyun kms DescribeAccountKmsStatus --RegionId "{{user.region}}"
   ```

## Multi-Round Diagnosis

| Symptom | Round 1 | Round 2 | Round 3 (HALT) |
|---------|---------|---------|----------------|
| "Cannot encrypt data" | Verify key is `Enabled` | Check `KeyUsage` is `ENCRYPT/DECRYPT` | Escalate with RequestId |
| "Key not found" | Try with full KeyId (not alias) | Cross-check region; keys are regional | Check if key was deleted |
| "Secret rotation failed" | Verify secret type supports rotation | Check rotation interval config | Verify external service connectivity |
| "Permission denied" | Check RAM policy for `kms:` action | Verify resource ARN in policy | Delegate to `alicloud-ram-ops` |
| "Rate limit hit" | Retry with 2s backoff | Backoff 4s, then 8s | HALT; check for runaway script loop |

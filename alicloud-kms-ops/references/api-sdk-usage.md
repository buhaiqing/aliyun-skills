# API & SDK — KMS

## OpenAPI

- **API Version**: `2016-01-20`
- **Protocol**: RPC-style (HTTPS GET/POST)
- **Base Endpoint**: `kms.aliyuncs.com` (or regional: `kms.{region}.aliyuncs.com`)
- **API Explorer**: https://api.alibabacloud.com/api/Kms/2016-01-20
- **Documentation**: https://help.aliyun.com/zh/kms/developer-reference/api-kms-2016-01-20-dir/

## Go SDK Package

| Item | Value |
|------|-------|
| Package | `github.com/alibabacloud-go/kms-20160120/v3/client` |
| Latest Version | v3.4.0 (Dec 2025) |
| OpenAPI | `github.com/alibabacloud-go/darabonba-openapi/v2/client` |
| Utils | `github.com/alibabacloud-go/tea-utils/v2/service` |
| Tea | `github.com/alibabacloud-go/tea/tea` |

## SDK Operations Map

### Service Management

| Goal | API OperationId | SDK Method |
|------|-----------------|------------|
| Query regions | `DescribeRegions` | `DescribeRegionsWithOptions` |
| Activate KMS | `OpenKmsService` | `OpenKmsServiceWithOptions` |
| Check KMS status | `DescribeAccountKmsStatus` | `DescribeAccountKmsStatusWithOptions` |

### Key Management (P0)

| Goal | API OperationId | SDK Method |
|------|-----------------|------------|
| Create key | `CreateKey` | `CreateKeyWithOptions` |
| Describe key | `DescribeKey` | `DescribeKeyWithOptions` |
| List keys | `ListKeys` | `ListKeysWithOptions` |
| Enable key | `EnableKey` | `EnableKeyWithOptions` |
| Disable key | `DisableKey` | `DisableKeyWithOptions` |
| Schedule deletion | `ScheduleKeyDeletion` | `ScheduleKeyDeletionWithOptions` |
| Cancel deletion | `CancelKeyDeletion` | `CancelKeyDeletionWithOptions` |
| Update description | `UpdateKeyDescription` | `UpdateKeyDescriptionWithOptions` |
| Set deletion protection | `SetDeletionProtection` | `SetDeletionProtectionWithOptions` |
| Delete key material | `DeleteKeyMaterial` | `DeleteKeyMaterialWithOptions` |
| Create alias | `CreateAlias` | `CreateAliasWithOptions` |
| Update alias | `UpdateAlias` | `UpdateAliasWithOptions` |
| List aliases | `ListAliases` | `ListAliasesWithOptions` |
| List aliases by key | `ListAliasesByKeyId` | `ListAliasesByKeyIdWithOptions` |
| Delete alias | `DeleteAlias` | `DeleteAliasWithOptions` |

### Key Version & Rotation (P1)

| Goal | API OperationId | SDK Method |
|------|-----------------|------------|
| Create key version | `CreateKeyVersion` | `CreateKeyVersionWithOptions` |
| Describe key version | `DescribeKeyVersion` | `DescribeKeyVersionWithOptions` |
| List key versions | `ListKeyVersions` | `ListKeyVersionsWithOptions` |
| Update rotation policy | `UpdateRotationPolicy` | `UpdateRotationPolicyWithOptions` |

### Cryptographic Operations (P0)

| Goal | API OperationId | SDK Method |
|------|-----------------|------------|
| Encrypt | `Encrypt` | `EncryptWithOptions` |
| Decrypt | `Decrypt` | `DecryptWithOptions` |
| Generate data key | `GenerateDataKey` | `GenerateDataKeyWithOptions` |
| Generate data key (no plaintext) | `GenerateDataKeyWithoutPlaintext` | `GenerateDataKeyWithoutPlaintextWithOptions` |
| Re-encrypt | `ReEncrypt` | `ReEncryptWithOptions` |
| Asymmetric encrypt | `AsymmetricEncrypt` | `AsymmetricEncryptWithOptions` |
| Asymmetric decrypt | `AsymmetricDecrypt` | `AsymmetricDecryptWithOptions` |
| Asymmetric sign | `AsymmetricSign` | `AsymmetricSignWithOptions` |
| Asymmetric verify | `AsymmetricVerify` | `AsymmetricVerifyWithOptions` |
| Get public key | `GetPublicKey` | `GetPublicKeyWithOptions` |
| Export data key | `ExportDataKey` | `ExportDataKeyWithOptions` |
| Generate & export data key | `GenerateAndExportDataKey` | `GenerateAndExportDataKeyWithOptions` |

### Secret Management (P0)

| Goal | API OperationId | SDK Method |
|------|-----------------|------------|
| Create secret | `CreateSecret` | `CreateSecretWithOptions` |
| Describe secret | `DescribeSecret` | `DescribeSecretWithOptions` |
| List secrets | `ListSecrets` | `ListSecretsWithOptions` |
| Update secret | `UpdateSecret` | `UpdateSecretWithOptions` |
| Put secret value | `PutSecretValue` | `PutSecretValueWithOptions` |
| Get secret value | `GetSecretValue` | `GetSecretValueWithOptions` |
| Rotate secret | `RotateSecret` | `RotateSecretWithOptions` |
| Restore secret | `RestoreSecret` | `RestoreSecretWithOptions` |
| Delete secret | `DeleteSecret` | `DeleteSecretWithOptions` |
| List secret versions | `ListSecretVersionIds` | `ListSecretVersionIdsWithOptions` |
| Update secret version stage | `UpdateSecretVersionStage` | `UpdateSecretVersionStageWithOptions` |
| Get random password | `GetRandomPassword` | `GetRandomPasswordWithOptions` |
| Update secret rotation policy | `UpdateSecretRotationPolicy` | `UpdateSecretRotationPolicyWithOptions` |

### Tag Management (P1)

| Goal | API OperationId | SDK Method |
|------|-----------------|------------|
| Tag resource | `TagResource` | `TagResourceWithOptions` |
| Untag resource | `UntagResource` | `UntagResourceWithOptions` |
| List resource tags | `ListResourceTags` | `ListResourceTagsWithOptions` |
| Tag resources (batch) | `TagResources` | `TagResourcesWithOptions` |
| Untag resources (batch) | `UntagResources` | `UntagResourcesWithOptions` |
| List tag resources (batch) | `ListTagResources` | `ListTagResourcesWithOptions` |

### KMS Instance Management (P1)

| Goal | API OperationId | SDK Method |
|------|-----------------|------------|
| List KMS instances | `ListKmsInstances` | `ListKmsInstancesWithOptions` |
| Get KMS instance | `GetKmsInstance` | `GetKmsInstanceWithOptions` |
| Connect KMS instance | `ConnectKmsInstance` | `ConnectKmsInstanceWithOptions` |
| Update VPC binding | `UpdateKmsInstanceBindVpc` | `UpdateKmsInstanceBindVpcWithOptions` |

## SDK Initialization Pattern

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    kmssdk "github.com/alibabacloud-go/kms-20160120/v3/client"
    "github.com/alibabacloud-go/tea-utils/v2/service"
    "github.com/alibabacloud-go/tea/tea"
)

func createClient() (*kmssdk.Client, error) {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.Sprintf("kms.%s.aliyuncs.com", os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    }
    return kmssdk.NewClient(config)
}

func main() {
    client, err := createClient()
    if err != nil {
        panic(err)
    }

    runtime := &service.RuntimeOptions{
        ConnectTimeout: tea.Int(5000),
        ReadTimeout:    tea.Int(5000),
    }

    // Example: DescribeKey
    resp, err := client.DescribeKeyWithOptions(&kmssdk.DescribeKeyRequest{
        KeyId: tea.String("key-id-here"),
    }, runtime)
    if err != nil {
        panic(err)
    }
    fmt.Printf("KeyId: %s, State: %s\n",
        tea.ToString(resp.Body.Key.KeyId),
        tea.ToString(resp.Body.Key.KeyState))
}
```

## Pagination

List operations support pagination via `PageNumber` and `PageSize`:

| Parameter | Type | Default | Max |
|-----------|------|---------|-----|
| `PageNumber` | Integer | 1 | - |
| `PageSize` | Integer | 10 | 100 |

Use `NextToken` for cursor-based pagination where supported (e.g., `GetSecretValue` does not support pagination, but `ListSecrets` does).

## Request/Response Conventions

- All API responses include a `RequestId` field for support/troubleshooting
- KMS uses standard RPC error format with `Code`, `Message`, `RequestId`
- Cryptographic operations return data as Base64-encoded strings
- Timestamps are in UTC ISO 8601 format

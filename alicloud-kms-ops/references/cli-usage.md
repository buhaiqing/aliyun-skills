# CLI — KMS (`aliyun`)

## Install and config
- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **Credentials:** The `aliyun` CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json`.
- KMS is a **regional service** — always pass `--RegionId` unless configured in profile.

## Conventions (agent execution)
- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI
- KMS uses **RPC-style** API: `aliyun kms <OperationName> --ParamName value`

## CLI vs API coverage

All KMS OpenAPI operations are callable via CLI using RPC-style invocation. The coverage is complete for the 2016-01-20 API version.

| Operation Category | Available via `aliyun kms`? | Notes |
|--------------------|----------------------------|-------|
| Service Management (DescribeRegions, OpenKmsService) | Yes | RPC-style |
| Key Management (CreateKey, DescribeKey, ListKeys, Enable/Disable, ScheduleDeletion, CancelDeletion, Alias) | Yes | Full coverage |
| Cryptographic Operations (Encrypt, Decrypt, GenerateDataKey, AsymmetricSign/Verify) | Yes | Full coverage |
| Secret Management (CreateSecret, GetSecretValue, RotateSecret, DeleteSecret) | Yes | Full coverage |
| Tag Management (TagResource, ListResourceTags) | Yes | Full coverage |
| KMS Instance (ListKmsInstances, GetKmsInstance) | Yes | Full coverage |
| App Management (CreateApplicationAccessPoint, CreateClientKey) | Yes | Full coverage |

## Command Map

| Goal | Example `aliyun` invocation |
|------|---------------------------|
| Verify setup | `aliyun kms DescribeRegions` |
| Activate KMS | `aliyun kms OpenKmsService --RegionId cn-hangzhou` |
| Create symmetric key | `aliyun kms CreateKey --KeyUsage ENCRYPT/DECRYPT --KeySpec Aliyun_AES_256 --ProtectionLevel SOFTWARE --RegionId cn-hangzhou` |
| Describe key | `aliyun kms DescribeKey --KeyId "key-id-or-alias/name"` |
| List keys (paginated) | `aliyun kms ListKeys --PageNumber 1 --PageSize 20 --RegionId cn-hangzhou` |
| Filter keys | `aliyun kms ListKeys --Filters '[{"Key":"KeyState","Values":["Enabled"]}]' --RegionId cn-hangzhou` |
| Enable key | `aliyun kms EnableKey --KeyId "key-id" --RegionId cn-hangzhou` |
| Disable key | `aliyun kms DisableKey --KeyId "key-id" --RegionId cn-hangzhou` |
| Schedule deletion | `aliyun kms ScheduleKeyDeletion --KeyId "key-id" --PendingWindowInDays 30 --RegionId cn-hangzhou` |
| Cancel deletion | `aliyun kms CancelKeyDeletion --KeyId "key-id" --RegionId cn-hangzhou` |
| Create alias | `aliyun kms CreateAlias --AliasName "alias/my-key" --KeyId "key-id" --RegionId cn-hangzhou` |
| Delete alias | `aliyun kms DeleteAlias --AliasName "alias/my-key" --RegionId cn-hangzhou` |
| List aliases | `aliyun kms ListAliases --RegionId cn-hangzhou` |
| Encrypt data | `aliyun kms Encrypt --KeyId "key-id" --Plaintext "base64-data" --RegionId cn-hangzhou` |
| Decrypt data | `aliyun kms Decrypt --KeyId "key-id" --CiphertextBlob "base64-cipher" --RegionId cn-hangzhou` |
| Generate data key | `aliyun kms GenerateDataKey --KeyId "key-id" --KeySpec AES_256 --RegionId cn-hangzhou` |
| Create secret | `aliyun kms CreateSecret --SecretName "my-db-password" --SecretData "s3cr3t" --RegionId cn-hangzhou` |
| Get secret value | `aliyun kms GetSecretValue --SecretName "my-db-password" --RegionId cn-hangzhou` |
| Rotate secret | `aliyun kms RotateSecret --SecretName "my-secret" --RegionId cn-hangzhou` |
| Delete secret | `aliyun kms DeleteSecret --SecretName "my-secret" --RecoveryWindowInDays 30 --RegionId cn-hangzhou` |
| Restore secret | `aliyun kms RestoreSecret --SecretName "my-secret" --RegionId cn-hangzhou` |
| Tag key | `aliyun kms TagResource --ResourceId "key-id" --Tag.1.TagKey "env" --Tag.1.TagValue "production" --RegionId cn-hangzhou` |
| List key tags | `aliyun kms ListResourceTags --ResourceId "key-id" --RegionId cn-hangzhou` |
| Extract fields (JMESPath) | `aliyun kms DescribeKey --KeyId "key-id" --output cols=KeyId,KeyState,KeySpec rows=Key.{KeyId,KeyState,KeySpec}` |

## JMESPath JSON Paths

| Resource | JMESPath Expression | Returns |
|----------|-------------------|---------|
| Key ID | `Key.KeyId` | String |
| Key State | `Key.KeyState` | String |
| Key Spec | `Key.KeySpec` | String |
| Key ARN | `Key.KeyArn` | String |
| All key IDs (list) | `Keys.Key[].KeyId` | Array |
| Secret Name | `SecretName` | String |
| Secret Data | `SecretData` | String (NEVER log) |
| Encryption result | `CiphertextBlob` | String |
| Decryption result | `Plaintext` | String |
| Total count (list) | `TotalCount` | Integer |
| Request ID | `RequestId` | String |

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```


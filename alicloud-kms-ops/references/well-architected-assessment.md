# Well-Architected Assessment — KMS

## §2.1 安全 (Security)

### Minimum RAM Permissions

| Operation | Minimum RAM Action | Resource |
|-----------|-------------------|----------|
| View keys | `kms:DescribeKey`, `kms:ListKeys` | `acs:kms:*:*:key/*` |
| Create keys | `kms:CreateKey` | `*` |
| Encrypt/Decrypt | `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey` | `acs:kms:*:*:key/{keyId}` |
| Sign/Verify | `kms:AsymmetricSign`, `kms:AsymmetricVerify` | `acs:kms:*:*:key/{keyId}` |
| Manage secrets | `kms:CreateSecret`, `kms:GetSecretValue`, `kms:PutSecretValue` | `acs:kms:*:*:secret/*` |
| Delete keys | `kms:ScheduleKeyDeletion`, `kms:CancelKeyDeletion` | `acs:kms:*:*:key/{keyId}` |

### Credential Masking

- `ALIBABA_CLOUD_ACCESS_KEY_SECRET` MUST NEVER appear in logs, output, or error messages
- All JIT Go SDK scripts use `os.Getenv()` — never interpolate credential values into code
- KMS secret values (`SecretData`) displayed once to user, never stored in conversation history

### VPC Endpoint Recommendation

- **Public endpoint**: `kms.{region}.aliyuncs.com` — suitable for development/testing
- **VPC endpoint**: `kms-vpc.{region}.aliyuncs.com` — recommended for production; traffic stays within VPC
- **DKMS instance endpoint**: `{instance-id}.cryptoservice.kms.aliyuncs.com` — VPC-bound, highest security

### Key Policy Recommendations

- Use least-privilege key policies; avoid `kms:*` wildcard
- Separate encryption keys from signing keys (different `KeyUsage`)
- Enable deletion protection for production keys via `SetDeletionProtection`
- Prefer `alias/` indirection for application key references (enables transparent key rotation)

---

## §2.2 稳定 (Stability)

### Backup & Recovery

| Resource | Backup Mechanism | RTO | RPO |
|----------|------------------|-----|-----|
| Keys | Key material export (for EXTERNAL keys) | Minutes | N/A (keys are stateless) |
| Secrets | Secret version history (all versions retained) | Seconds | Per rotation interval |
| DKMS Instances | Automated backup (enabled by default) | Per backup schedule | Per backup frequency |

### DR Runbook: Key Loss Scenario

**Phase 1 — Assessment (0–5 min)**
1. Identify affected key(s) via `ListKeys` and `DescribeKey`
2. Determine key state: Enabled, Disabled, or PendingDeletion
3. If PendingDeletion and within window → `CancelKeyDeletion` immediately

**Phase 2 — Recovery (5–30 min)**
4. If key is Enabled/Disabled but not deleted → no action needed, just re-enable
5. If key material was external → re-import key material via `GetParametersForImport` + `ImportKeyMaterial`
6. If key is irrecoverably deleted → create new key, update all alias references

**Phase 3 — Verification (30–60 min)**
7. Test encryption/decryption with recovered key
8. Verify dependent services (ECS, RDS, OSS) can still access encrypted resources
9. Update runbook documentation

### Multi-AZ/Region Deployment

- KMS is a regional service with built-in multi-AZ redundancy within each region
- Keys cannot be natively replicated across regions
- **Cross-region strategy**: Export key material (EXTERNAL keys) and re-import in target region
- Use key aliases to maintain consistent references across environments

### Explicit Confirmation on Destructive Operations

All destructive operations require explicit confirmation:
- `ScheduleKeyDeletion` — confirm key ID, waiting period, impact on dependent services
- `DeleteSecret` — confirm secret name, recovery window, no active dependencies
- `DeleteAlias` — confirm alias name (note: does NOT delete the underlying key)

---

## §2.3 成本 (Cost)

### Billing Model Comparison

| Plan | Price Model | Free Tier | Best For |
|------|------------|-----------|----------|
| **Default KMS (Standard)** | Pay-per-use | 20,000 API calls/month free | Small projects, dev/test |
| **Default KMS (Advanced)** | Pay-per-use + feature tier | — | Production workloads |
| **Dedicated KMS Instance** | Fixed monthly fee + usage | — | Compliance, high-throughput, dedicated HSM |
| **HSM-protected keys** | Per-key premium charge | — | Regulatory compliance (OSCCA, FIPS) |

### Idle Resource Detection

| Pattern | Detection Method | Recommendation |
|---------|-----------------|----------------|
| Key with no API calls in 30+ days | `DescribeKey` + audit log analysis | Consider disabling via `DisableKey` |
| Secret with no GetSecretValue calls in 60+ days | `DescribeSecret` + audit logs | Evaluate if secret is still needed |
| DKMS instance at < 10% capacity utilization | `GetKmsInstance` metrics | Right-size to lower instance tier |
| More keys than needed | `ListKeys` + tag analysis | Delete unused keys (after audit) |

### Cost Optimization Recommendations

1. Use key aliases to avoid recreating keys; each key has associated costs
2. Prefer software protection level unless compliance requires HSM
3. Batch KMS operations where possible to reduce API call count
4. Monitor `Encrypt`/`Decrypt` call volumes — consider envelope encryption for high-volume scenarios

---

## §2.4 效率 (Efficiency)

### Batch Operations

| Pattern | API | Description |
|---------|-----|-------------|
| Batch key tagging | `TagResources` | Apply tags to multiple keys/secrets in single call |
| Batch untagging | `UntagResources` | Remove tags from multiple resources |
| Bulk key listing | `ListKeys` with `PageSize=100` | Retrieve up to 100 keys per request |
| Bulk alias listing | `ListAliases` | All aliases in region |

### Automation Patterns

- **CLI automation**: All KMS operations are scriptable via `aliyun kms` commands
- **Go automation**: JIT SDK scripts enable programmatic key/secret management
- **Infrastructure-as-Code**: KMS resources support Terraform and ROS

### CI/CD Integration

- KMS secrets can be injected into CI/CD pipelines via `GetSecretValue`
- Key aliases enable seamless key rotation in CI/CD without pipeline changes
- Service-linked keys (`Creator: Service`) are auto-managed by Alibaba Cloud services

---

## §2.5 性能 (Performance)

### Key Performance Metrics

| Metric | Threshold | Notes |
|--------|-----------|-------|
| Encrypt latency | < 10ms (software), < 5ms (HSM) | p95 latency for symmetric keys |
| Decrypt latency | < 10ms (software), < 5ms (HSM) | |
| GenerateDataKey latency | < 15ms | Includes both plaintext + ciphertext generation |
| Sign/Verify latency | < 20ms (RSA-2048), < 5ms (EC) | Asymmetric operations are slower |
| GetSecretValue latency | < 10ms | |
| API QPS limit | 50–200 (varies by operation) | Enforced per account per region |

### Auto-Scaling Trigger Table

| Condition | Threshold | Action |
|-----------|-----------|--------|
| High Encrypt/Decrypt volume | > 1000 ops/sec | Consider Dedicated KMS Instance |
| API throttling (429 errors) | > 5 per minute | Implement client-side rate limiting |
| Latency spike | > 100ms p95 | Check network path; consider VPC endpoint |
| Secret access latency | > 50ms | Verify DKMS instance health |

### Performance Optimization Recommendations

1. **Envelope encryption**: For large data, use `GenerateDataKey` and encrypt locally; only the data key goes through KMS
2. **Local caching**: Cache Decrypt results for static data; avoid repeated KMS calls
3. **Connection reuse**: For JIT Go SDK, reuse the KMS client across operations
4. **Regional proximity**: Use the KMS endpoint in the same region as your compute resources
5. **VPC endpoints**: Reduce network latency by using `kms-vpc` endpoints within VPC

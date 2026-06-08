# Troubleshooting — Terraform IaC (Alibaba Cloud)

> **Purpose:** Terraform CLI errors, state/backend failures, and import drift diagnostics for `alicloud-terraform-ops`.

## Error Codes & Messages

| Error / Symptom | Category | Agent Action |
|-----------------|----------|--------------|
| `Error acquiring the state lock` | Lock contention | Check OTS lock row; verify no running CI apply; `terraform force-unlock <ID>` only after confirmation |
| `Error: Bucket not found` | Backend config | Verify `TF_BACKEND_BUCKET`; create OSS bucket; update `backend.tf` |
| `Error: Provider configuration` | Credentials | HALT — verify `ALIBABA_CLOUD_ACCESS_KEY_*` and region |
| `Error: Cycle detected` | Dependency graph | Review `depends_on` and module outputs; break circular references |
| `Error: Resource already exists` | Import needed | Run reverse engineering or `terraform import alicloud_*.* <id>` |
| `Error: Invalid configuration` | HCL syntax/validation | Run `terraform validate`; fix attribute names against provider docs |
| `Error: Plugin schema mismatch` | Provider version drift | Run `terraform init -upgrade`; pin provider in `required_providers` |
| `Error: Unsupported argument` | Provider API change | Check provider changelog; remove/rename deprecated arguments |
| `Error: Import id format` | Wrong import ID | Use product-specific format (e.g. `disk_id:instance_id` for attachments) |
| `Error: Cannot import non-existent remote object` | ID/region mismatch | Verify resource ID and `provider "alicloud" { region }` |
| `Error: Backend initialization required` | Skipped init | Run `terraform init`; for dry-run use `-backend=false` |
| `AccessDenied` on OSS state | RAM/OSS ACL | Grant OSS + OTS permissions to CI role; check bucket policy |
| Plan shows unexpected destroy | Drift / config mismatch | Compare live API via `aliyun` Describe*; adjust HCL or refresh state |
| `prevent_destroy` blocked destroy | Safety gate | Expected in prod — remove only with explicit user confirmation + GCL PASS |
| NL2HCL empty resources | Intent parse failure | Rephrase `--request`; use wizard or explicit resource list |
| Reverse engineering query failed | API / ID error | Verify `--resource-id` format; check PreFlight supported types |

## Diagnostic Order

1. **Verify toolchain:** `terraform -version` (≥ 1.5.0), `aliyun configure get current`
2. **Verify backend:** OSS bucket exists, OTS lock table accessible, region matches
3. **Verify credentials:** env vars set; never embed in HCL
4. **Initialize:** `terraform init` (or `init -backend=false` for offline validate)
5. **Validate syntax:** `terraform validate`
6. **Plan before mutate:** `terraform plan -out=tfplan` — parse add/change/destroy counts
7. **State inspection:** `terraform state list` / `terraform state show <addr>`
8. **Cloud-side verify:** `aliyun <product> Describe*` for resource existence and attributes
9. **Import drift:** after import, plan MUST be empty or user-approved diffs only
10. **GCL trace:** inspect `./audit-results/gcl-trace-*.json` for blocked Safety dimension

## Common Scenarios

### State Lock Stuck After CI Failure

Symptoms: all `plan`/`apply` fail with lock error.

1. Identify lock ID from error message
2. Confirm no active pipeline holds the lock
3. `terraform force-unlock <LOCK_ID>`
4. Re-run `terraform plan`

### Import Succeeds but Plan Shows Changes

Symptoms: post-import plan wants to modify/delete resources.

1. Compare HCL attributes with `aliyun` API response
2. Add `ignore_changes` for read-only/computed fields if intentional
3. Regenerate HCL via reverse engineering with updated mapper
4. Re-import only if state address changed

### OSS Backend Permission Denied

Symptoms: `init` or state write fails with 403.

1. RAM policy needs `oss:GetObject`, `PutObject`, `ListObjects` on state prefix
2. OTS needs `GetRow`, `PutRow`, `DeleteRow` on lock table
3. Bucket encryption/KMS key must be accessible to CI role

### NL2HCL / Module Generation Fails Validate

Symptoms: `terraform validate` errors on generated files.

1. Check provider version constraint in `provider.tf`
2. Verify required variables have defaults in `terraform.tfvars`
3. Run with `--dry-run` and read `[DRY-RUN]` validate output
4. Fix intent or switch to wizard for guided parameter collection

## Recovery Commands

```bash
# State backup before destructive work
terraform state pull > "backup-$(date +%Y%m%d-%H%M%S).tfstate"

# Refresh state from cloud (non-destructive)
terraform refresh

# Remove single resource from state without cloud delete
terraform state rm 'alicloud_instance.example'

# Re-run plan after config fix
terraform plan -out=tfplan
```

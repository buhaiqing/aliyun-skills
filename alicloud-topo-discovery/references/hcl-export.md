# HCL Export Engine Design

This document describes the architecture of the HCL export engine
used by `export-hcl.py` and consumed by `baseline-manager.py`.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CLI Layer:                                                 │
│    export-hcl.py (orchestrator)                             │
│    baseline-manager.py (wraps export-hcl + baseline store) │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Library Layer (scripts/lib/):                              │
│    manifest_validator  - schema compliance                 │
│    manifest_builder    - dict construction                 │
│    sensitive_masker    - password/key masking              │
│    provider_locker     - Aliyun Provider version           │
│    field_mapper        - JSON → HCL conversion             │
│    dependency_inference - topological sort                │
│    baseline_local/git/oss - storage backends               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Data Layer:                                                │
│    MAPPINGS registry (scripts/lib/mappings.py)             │
│    fixtures/*.json (test data)                             │
│    references/field-mappings/*.md (mapping specs)          │
└─────────────────────────────────────────────────────────────┘
```

## Resource Type Coverage (18 types)

| Type | terraform_type | Phase |
|------|----------------|-------|
| vpc | alicloud_vpc | 1 |
| vswitch | alicloud_vswitch | 1 |
| ecs | alicloud_instance | 1 |
| rds | alicloud_db_instance | 1 |
| slb | alicloud_slb | 1 |
| nat | alicloud_nat_gateway | 3 |
| eip | alicloud_eip | 3 |
| sg | alicloud_security_group | 3 |
| oss | alicloud_oss_bucket | 3 |
| ram | alicloud_ram_role | 3 |
| polardb | alicloud_polardb_cluster | 3 |
| redis | alicloud_redis_instance | 3 |
| kms | alicloud_kms_key | 3 |
| actiontrail | alicloud_actiontrail | 3 |
| nas | alicloud_nas_file_system | 3 |
| fc | alicloud_fc_service | 3 |
| vpn | alicloud_vpn_connection | 3 |
| ack | alicloud_cs_kubernetes | 3 |
| sag | alicloud_sag | 3 |

## Output File Schema

For each export, 8 files are written atomically:

| File | Content |
|------|---------|
| `provider.tf` | `terraform{}` and `provider "alicloud" {}` blocks |
| `main.tf` | All resource blocks, topologically ordered |
| `variables.tf` | Variable declarations (e.g. rds_password) |
| `outputs.tf` | Important resource ID outputs |
| `terraform.tfstate` | Import helper state (empty) |
| `import.sh` | One `terraform import` per resource |
| `unsupported.tf` | Comments for unsupported types |
| `manifest.json` | Schema-validated export metadata |

## Error Codes

| Code | Range | Meaning | Action |
|------|-------|---------|--------|
| 0 | - | Success | Read SUMMARY, no human action |
| 10-19 | env | Credential/network | Re-run with valid AK |
| 20-29 | config | Invalid arguments | Check CLI args |
| 30-39 | I/O | Filesystem | Check output dir perms |
| 40-49 | API | Mapping/dependency | Check fixtures, review HCL output |

## Sensitive Data Handling

The following fields are masked to variable references:
- `rds.accountpassword` → `var.rds_password`
- `ecs.password` → `var.ecs_password`

Sensitive values NEVER appear in:
- HCL output (replaced with var ref)
- manifest.json sensitive_masked (path only)
- import.sh (only IDs, not values)
- stderr/log (paths only, never values)
# Well-Architected Assessment — Terraform IaC

> **Purpose:** Five-pillar assessment for Alibaba Cloud Terraform workflows managed by `alicloud-terraform-ops`.

## 2.1 安全支柱 Security

### State & Credential Hygiene
- Remote state MUST use OSS with server-side encryption (SSE-KMS recommended)
- State files contain resource IDs and sometimes secrets — restrict bucket ACL/RAM to CI/CD roles only
- Provider credentials MUST come from `ALIBABA_CLOUD_ACCESS_KEY_*` env vars — never hardcode in HCL
- **MANDATORY:** Never log or print `ALIBABA_CLOUD_ACCESS_KEY_SECRET`; mask as `****` in traces and GCL output

### Network & Access
- Security groups: avoid `0.0.0.0/0` ingress on admin ports (22/3389); use bastion or Cloud Assistant
- RDS/Redis: prefer private VSwitch placement; disable public endpoint unless required
- OSS backend bucket: disable public read; enable versioning for state rollback

### HITL & GCL Gates
- Production `terraform apply` / `destroy` MUST pass HITL CP3/CP5 and GCL Safety=1
- NL2HCL output MUST pass secret-pattern scan (see [rubric.md](rubric.md) NL2HCL-001)

## 2.2 稳定支柱 Stability

### State Locking & Recovery
- OTS tablestore lock MUST be configured for team workflows — prevents concurrent apply corruption
- Before destructive ops: `terraform state pull > backup-$(date +%Y%m%d).tfstate`
- On lock contention: verify no stale CI job before `terraform force-unlock`

### Lifecycle Protection
- Production critical resources: `lifecycle { prevent_destroy = true }`
- Imported resources (reverse engineering): default `prevent_destroy = true` until drift is resolved

### Drift Management
- Schedule periodic `terraform plan` in CI; non-zero diff triggers review
- Import workflows: post-import `terraform plan` MUST show no unexpected changes

## 2.3 成本支柱 Cost

### Resource Right-Sizing
- Use variables for `instance_type`, `db_instance_class` — avoid hardcoding oversized SKUs in modules
- Dev/staging: prefer spot/preemptible patterns where modules support them
- Tag all resources (`Environment`, `Project`, `Owner`) for cost allocation

### Environment Lifecycle
- Non-prod environments SHOULD have TTL tags and automated `terraform destroy` in CI pipelines
- NL2HCL defaults: flag PayAsYouGo high-spec instances in GCL WAF cost checks

## 2.4 效率支柱 Efficiency

### Module Reuse
- Prefer `modules/` catalog over inline resource blocks — reduces duplication across environments
- Environment-specific values in `terraform.tfvars`, not duplicated HCL

### GitOps Workflow
- All HCL changes via PR (Mode B) for uat/production
- Plan artifact (`tfplan`) stored in CI artifact store — apply uses exact reviewed plan

### NL2HCL & Reverse Engineering
- NL2HCL for greenfield scaffolding; reverse engineering for brownfield import — do not mix without explicit user intent
- Batch imports: use `--discover-associated` to reduce manual ID collection

## 2.5 性能支柱 Performance

### Parallelism
- Terraform builds dependency graphs — avoid unnecessary `depends_on` that serializes creation
- Large stacks: tune `-parallelism` only when API throttling occurs (document in trace)

### Plan Performance
- Use `-target` sparingly for emergency fixes — full plan required before production apply
- Remote state in same region as managed resources reduces OSS latency

### Validation Pipeline
- Dry-run path: `init -backend=false` → `validate` → `plan` (see [core-concepts.md](core-concepts.md))
- CP3 real plan via `terraform_plan_runner.py` — prefer over resource-count estimates

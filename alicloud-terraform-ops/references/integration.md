# Integration — Terraform IaC (Alibaba Cloud)

> **Purpose:** Toolchain bootstrap, credentials, backend setup, and GCL runner integration.

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | Provider authentication |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | Provider authentication |
| `ALIBABA_CLOUD_REGION` / `ALIBABA_CLOUD_REGION_ID` | Yes | Default region |
| `TF_BACKEND_BUCKET` | Yes (remote state) | OSS bucket for `terraform.tfstate` |
| `TF_BACKEND_TABLE` | Yes (locking) | OTS table for state lock |
| `TF_OPS_CONFIG` | No | HITL config path (`terraform_ops --config`) |
| `GCL_TRACE_RETENTION_DAYS` | No | Trace retention override (default 30) |

**Credential rule:** NEVER ask the user for `{{env.*}}` values. HALT if missing.

## Toolchain Bootstrap

```bash
# Terraform CLI
terraform -version   # expect >= 1.5.0

# Alibaba Cloud CLI (for reverse engineering + post-apply validation)
aliyun configure get current

# Optional: unified entry
python3 alicloud-terraform-ops/scripts/terraform_ops.py --help
```

## OSS Backend Setup (Minimal)

```hcl
terraform {
  backend "oss" {
    bucket              = "my-terraform-state"
    prefix              = "environments/dev"
    key                 = "terraform.tfstate"
    tablestore_endpoint = "https://my-terraform.ots.cn-hangzhou.aliyuncs.com"
    tablestore_table    = "terraform_state_lock"
  }
}
```

Pre-create bucket and OTS table before first `terraform init` in CI.

## Unified CLI Entry Points

| Workflow | Command |
|----------|---------|
| NL2HCL + HITL | `python terraform_ops.py create -r "..." -e dev -o ./generated` |
| Import + HITL | `python terraform_ops.py import -t vpc -i vpc-xxx -e dev` |
| Dry-run only | append `--dry-run` |
| Wizard | `python terraform_ops.py wizard nl2hcl --quick` |

## GCL Runner Integration

Delegate destructive or high-risk operations to `alicloud-gcl-runner-ops`:

```bash
python alicloud-gcl-runner-ops/scripts/gcl_runner.py \
  --skill alicloud-terraform-ops \
  --op Apply \
  --command "terraform apply tfplan" \
  --rubric alicloud-terraform-ops/references/rubric.md \
  --enable-hallucination-check
```

- **Classification:** `required`, `max_iter=2` (see [docs/gcl-spec.md](../../docs/gcl-spec.md))
- **Trace output:** `./audit-results/gcl-trace-*.json` (gitignored)
- **Rubric / prompts:** [rubric.md](rubric.md), [prompt-templates.md](prompt-templates.md)

## HITL Mode Selection

| Mode | Use Case | Entry |
|------|----------|-------|
| A (CLI) | Dev/uat interactive confirm | default `--mode cli` |
| B (PR) | Team review, GitOps | `--mode pr` + `pr-create` |
| C (Checkpoint) | Long import, resume | `terraform_ops pause/resume` |

Full workflow: [hitl-workflow.md](hitl-workflow.md), [hitl-implementation.md](hitl-implementation.md).

## Cross-Skill Composition

| Phase | Skill | Action |
|-------|-------|--------|
| 1 — Skeleton | `alicloud-terraform-ops` | `terraform apply` creates VPC/ECS/RDS/SLB |
| 2 — Runtime | product-ops skills | SQL init, Redis ops, ECS RunCommand, SLB tuning |

Terraform owns **control plane provisioning**; product-ops skills own **data plane and runtime tuning**.

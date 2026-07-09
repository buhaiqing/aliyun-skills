# API & SDK — Alibaba Cloud Terraform Operations

## Overview

This skill uses Terraform CLI for infrastructure management rather than direct Alibaba Cloud API calls.

## Terraform Operations Map

| Goal | Terraform Command | Description |
|------|-------------------|-------------|
| Initialize | `terraform init` | Download providers and modules |
| Validate | `terraform validate` | Check configuration syntax |
| Plan | `terraform plan` | Preview infrastructure changes |
| Apply | `terraform apply` | Execute infrastructure changes |
| Destroy | `terraform destroy` | Remove all managed resources |
| Import | `terraform import` | Import existing resources |
| State | `terraform state` | Manage state file |
| Workspace | `terraform workspace` | Manage multiple environments |

## Provider Configuration

```hcl
terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = ">= 1.200.0"
    }
  }
  
  backend "oss" {
    bucket = "my-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "cn-hangzhou"
  }
}

provider "alicloud" {
  region = var.region
}
```

## State Management

### OSS Backend
- Store state remotely for team collaboration
- Enable state locking to prevent conflicts
- Version state files for rollback capability

### State Commands
```bash
terraform state list                    # List all resources
terraform state show <resource>         # Show resource details
terraform state rm <resource>           # Remove from state
terraform state mv <old> <new>          # Rename resource
```

## Module Structure

```
modules/
├── vpc/                    # VPC network module
├── ecs/                    # ECS instance module
├── rds/                    # RDS database module
└── security/               # Security group module
```

## Multi-Environment Pattern

```
environments/
├── dev/
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars
├── staging/
│   └── ...
└── prod/
    └── ...
```

## NL2HCL (Natural Language to HCL)

Convert natural language descriptions to Terraform HCL:
- Resource type detection
- Parameter inference
- Dependency analysis
- Best practice enforcement

## Reverse Engineering

Generate Terraform configurations from existing Alibaba Cloud resources:
- Resource discovery
- HCL generation
- Import command generation
- State reconciliation

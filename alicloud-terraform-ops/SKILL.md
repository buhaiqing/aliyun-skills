---
triggers:
  - terraform
  - iac
  - infrastructure-as-code
  - 基础设施即代码
  - 多环境管理
  - terraform destroy
  - terraform plan
  - terraform apply
  - terraform state
  - 环境销毁
  - 环境创建
  - workspace
  - module
  - backend
  # NL2HCL - Natural Language to HCL
  - "生成terraform配置"
  - "terraform代码生成"
  - "自然语言生成基础设施"
  - "帮我把这段描述转成terraform"
  - "用terraform创建..."
  - "terraform hcl生成"
  # Reverse Engineering
  - "导入现有资源"
  - "生成terraform导入配置"
  - "逆向生成terraform"
  - "现有资源转terraform"
  - "terraform import生成"
  - "已有资源生成hcl"
should:
  - 管理阿里云基础设施的全生命周期（创建、变更、销毁）
  - 使用 Terraform HCL 声明式定义资源
  - 通过 workspaces 或目录结构管理多环境（dev/staging/prod）
  - 配置 OSS backend 实现状态远程存储和团队协作
  - 执行 terraform plan 预览变更，避免意外操作
  - 使用模块化设计提高可复用性
  - 集成 GitOps 流程，实现基础设施版本化管理
  - 定期销毁和重建临时环境
  - **NL2HCL: 将自然语言描述转换为 Terraform HCL 配置**
  - **Reverse Engineering: 从现有阿里云资源逆向生成 Terraform 配置和导入脚本**
should_not:
  - 执行数据平面操作（SQL 执行、Redis 命令等）
  - 替代日常运维诊断和故障排查（使用对应 product-ops skills）
  - 处理需要即时响应的临时操作
  - 管理 Terraform 不支持的细粒度配置（如参数模板调优）
delegation_rules:
  - trigger: "执行 SQL 文件/数据库初始化"
    delegate_to: "alicloud-rds-ops"
  - trigger: "Redis 数据操作/内存分析"
    delegate_to: "alicloud-redis-ops"
  - trigger: "ECS 性能诊断/日志分析"
    delegate_to: "alicloud-ecs-ops"
  - trigger: "RDS 慢查询优化"
    delegate_to: "alicloud-rds-ops"
  - trigger: "PolarDB 集群监控"
    delegate_to: "alicloud-polar-mysql-ops"
---

# alicloud-terraform-ops

Terraform IaC skill for Alibaba Cloud infrastructure lifecycle management. Declarative, version-controlled, multi-environment orchestration.

## 1. Overview

This skill enables GitOps-style infrastructure management using Terraform:
- **Declarative**: Define desired state in HCL, let Terraform figure out how to get there
- **Multi-environment**: Workspaces or directory-based isolation for dev/staging/prod
- **State-managed**: OSS backend for remote state storage and locking
- **Modular**: Reusable components for common infrastructure patterns
- **Collaborative**: State locking prevents concurrent modifications

## 2. Triggers

Use this skill when:
- User mentions "Terraform", "IaC", "infrastructure as code", "基础设施即代码"
- User needs multi-environment management (dev/staging/prod)
- User wants to create/destroy complete environments
- User mentions "terraform plan/apply/destroy"
- User needs modular, reusable infrastructure components
- User wants GitOps-style infrastructure versioning

## 3. Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Terraform CLI | `terraform -version` | ≥ 1.5.0 | HALT — install Terraform |
| OSS Backend Bucket | `aliyun oss head-object --bucket {{env.TF_BACKEND_BUCKET}} --key env:/` | 200 OK | HALT — create OSS bucket first |
| Alibaba Cloud Credentials | `aliyun configure get current` | Valid profile | HALT — run `aliyun configure` |
| State Lock Table | OTS table existence check | Table exists | HALT — create OTS table for locking |
| Git Repository | `git rev-parse --git-dir` | Valid repo | WARN — initialize git repo |
| Environment Isolation | Workspace or directory check | Isolated env | HALT — create workspace/directory |

## 4. Variable Convention

| Variable | Meaning | Source |
|----------|---------|--------|
| `{{user.environment}}` | Target environment | Ask: dev/staging/prod |
| `{{user.module}}` | Module to use | Ask or infer from context |
| `{{user.action}}` | Terraform action | Ask: plan/apply/destroy/init |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Access Key ID | NEVER ask, HALT if missing |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Access Key Secret | NEVER ask, HALT if missing |
| `{{env.ALIBABA_CLOUD_REGION}}` | Default region | NEVER ask, use as default |
| `{{env.TF_BACKEND_BUCKET}}` | OSS bucket for state | NEVER ask, HALT if missing |
| `{{env.TF_BACKEND_TABLE}}` | OTS table for locking | NEVER ask, HALT if missing |
| `{{output.state_key}}` | State file path | Generated from env + module |

## 5. Execution

### 5.1 Quick Start Flow

```bash
# 1. Initialize with backend
cd environments/{{user.environment}}
terraform init

# 2. Plan changes
terraform plan -out=tfplan

# 3. Apply (after review)
terraform apply tfplan

# 4. Destroy when needed
terraform destroy
```

### 5.2 Multi-Environment Strategy

**Option A: Workspace-based (recommended for similar environments)**

```bash
# Create workspaces
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod

# Switch and apply
terraform workspace select dev
terraform plan
terraform apply
```

**Option B: Directory-based (recommended for significantly different environments)**

```
environments/
├── dev/
│   ├── main.tf
│   ├── variables.tf
│   └── backend.tf
├── staging/
│   ├── main.tf
│   ├── variables.tf
│   └── backend.tf
└── prod/
    ├── main.tf
    ├── variables.tf
    └── backend.tf
```

### 5.3 Module Usage

```hcl
module "web_stack" {
  source = "../../modules/web-stack"
  
  environment = var.environment
  region      = var.region
  
  vpc_cidr    = "10.0.0.0/16"
  az_count    = 2
  
  ecs_instance_type = var.ecs_instance_type
  ecs_count         = var.ecs_count
  
  rds_instance_class = var.rds_instance_class
  rds_engine_version = "8.0"
  
  slb_spec = var.slb_spec
}
```

Full module design guidelines are covered in the NL2HCL generator spec: [references/nl2hcl-generator.md](references/nl2hcl-generator.md)

### 5.4 Backend Configuration

```hcl
# backend.tf
terraform {
  backend "oss" {
    bucket     = "my-terraform-state"
    prefix     = "environments/dev"
    key        = "terraform.tfstate"
    tablestore_endpoint = "https://my-terraform.ots.cn-hangzhou.aliyuncs.com"
    tablestore_table    = "terraform_state_lock"
  }
}
```

## 6. Post-execution Validation

| Check | Command | Expected |
|-------|---------|----------|
| State persistence | `aliyun oss cat oss://{{env.TF_BACKEND_BUCKET}}/{{user.environment}}/terraform.tfstate` | Valid JSON |
| Resource creation | `aliyun {{resource}} Describe{{Resource}}s` | Resources exist |
| Output values | `terraform output -json` | Expected outputs |
| State lock released | OTS row existence check | No lock rows |

## 7. Failure Recovery

| Error | Category | Recovery |
|-------|----------|----------|
| `Error: Error acquiring the state lock` | Lock contention | `terraform force-unlock <LOCK_ID>` after verification |
| `Error: Bucket not found` | Backend config | Create OSS bucket, update backend.tf |
| `Error: Resource already exists` | Import needed | `terraform import alicloud_{{resource}}.{{name}} {{id}}` |
| `Error: Provider configuration` | Credentials | Check `ALIBABA_CLOUD_ACCESS_KEY_*` env vars |
| `Error: Cycle detected` | Dependency issue | Review resource dependencies in HCL |

## 8. Integration with CLI/SDK Skills

Terraform manages **infrastructure skeleton**, CLI skills manage **runtime operations**:

```bash
# Phase 1: Terraform creates infrastructure
terraform apply  # Creates ECS, RDS, SLB

# Phase 2: CLI skills perform data operations
# (delegated to respective skills)
alicloud-ecs-ops: RunCommand on ECS for app deployment
alicloud-rds-ops: Execute SQL for database initialization
alicloud-slb-ops: Configure health checks and listeners
```

## 9. Safety Gates

### 9.1 Destruction Protection

```hcl
# Use prevent_destroy for critical resources
resource "alicloud_instance" "web" {
  # ...
  
  lifecycle {
    prevent_destroy = var.environment == "prod"
  }
}
```

### 9.2 Plan Review Requirement

Always run `terraform plan` before `apply`. Never use `auto-approve` in production.

### 9.3 State Backup

```bash
# Backup before destructive operations
terraform state pull > backup-$(date +%Y%m%d-%H%M%S).tfstate
```

## 10. Well-Architected Assessment

| Pillar | Assessment | Implementation |
|--------|-----------|----------------|
| **Security** | State contains sensitive data | OSS bucket encryption, least privilege access |
| **Stability** | State corruption risk | Remote backend, locking, versioning |
| **Cost** | Resource tracking | Terraform state as inventory, tag-based cost allocation |
| **Efficiency** | Environment consistency | Module reuse, GitOps workflow |
| **Performance** | Parallel resource creation | Terraform parallel resource graph |

## 11. Core Features

### 11.1 NL2HCL - Natural Language to Terraform

将自然语言描述转换为可执行的 Terraform HCL 配置。

**Trigger examples:**
- "帮我创建一个 VPC，包含两个可用区的交换机，以及一个 NAT 网关"
- "生成 Terraform 配置：3 台 ECS 挂载到 SLB，后端连接 RDS MySQL"
- "用 Terraform 搭建一个带有 Redis 缓存的 Web 服务架构"

**Output:**
- `main.tf` - 资源配置
- `variables.tf` - 变量定义
- `outputs.tf` - 输出定义
- `terraform.tfvars` - 默认值
- `README.md` - 使用说明

**Process:**
1. Parse natural language intent
2. Identify required resources and dependencies
3. Generate HCL with best practices (tags, naming conventions)
4. Validate with `terraform validate`
5. **Dry-run support**: Execute `terraform plan` to preview changes without applying

**Dry-run Mode:**
- Preview resource creation before actual deployment
- Show estimated costs and risk warnings
- Validate configuration without backend initialization
- Support in HITL CP3 (Plan Confirmation) checkpoint

**Dry-Run 标识规范:**
所有 dry-run 输出均包含清晰的视觉标识:
```
╔════════════════════════════════════════════════════════════════╗
║                    🔍 DRY-RUN MODE (干运行模式)                  ║
║         此执行仅用于预览和验证，不会创建或修改任何资源            ║
╚════════════════════════════════════════════════════════════════╝
```
每条日志行前缀: `[DRY-RUN]`

Full spec: [references/nl2hcl-generator.md](references/nl2hcl-generator.md)

### 11.2 Reverse Engineering - Import Existing Resources

从现有阿里云资源逆向生成 Terraform 配置，实现存量资源纳管。

**Trigger examples:**
- "把这些 ECS 实例导入到 Terraform 管理"
- "生成现有 VPC 的 Terraform 配置"
- "帮我把这个 RDS 实例转成 HCL 代码"
- "已有资源生成 terraform import 脚本"

**Input formats:**
- Resource IDs (e.g., `i-bp1xxxxxxxxxx`, `vpc-bp1xxxxxxxx`)
- `aliyun` CLI output (JSON)
- Console screenshot/resource list

**Output:**
- `generated/` - HCL configuration files
- `import.sh` - Import script for `terraform import`
- `import.tf` - Generated resource blocks

**Process:**
1. Query resource details via `aliyun` CLI
2. Map cloud resource attributes to Terraform schema
3. Generate HCL with lifecycle rules
4. Create import script
5. **Dry-run support**: Validate configuration with `terraform plan` without modifying state
6. Execute import and verify with `terraform plan`

**Dry-run Mode:**
- Generate HCL and validate syntax before actual import
- Detect configuration drift before state modification
- Preview import result without changing Terraform state
- Required step in HITL CheckPoint Mode C before final confirmation

**Dry-Run 标识规范:**
所有 dry-run 输出均包含清晰的视觉标识:
```
╔════════════════════════════════════════════════════════════════╗
║                    🔍 DRY-RUN MODE (干运行模式)                  ║
║         此执行仅用于预览和验证，未修改 Terraform 状态            ║
╚════════════════════════════════════════════════════════════════╝
```
每条日志行前缀: `[DRY-RUN]`

Full spec: [references/reverse-engineering.md](references/reverse-engineering.md)

### 11.3 HITL Multi-Mode Workflow

人工介入 (Human-in-the-Loop) 工作流程，支持三种协作模式：

**模式 A: 交互式 CLI (默认)** ✅ 已实现
- 命令行实时问答确认
- 适用于开发/测试环境快速迭代
- 支持五级环境差异化确认策略 (int/dev/uat/performance/production)
- **实现**: `scripts/hitl_mode_a.py`

**模式 B: PR 式审核** ✅ 已实现
- Git PR 驱动的异步审批流程
- 自动生成 PLAN.md 变更摘要
- 评论指令系统 (/approve, /plan, /apply)
- 适用于生产环境发布、团队协作
- **实现**: `scripts/hitl_mode_b.py`

**模式 C: CheckPoint 暂停** ✅ 已实现
- 会话状态持久化，支持中断恢复
- 资源分级标记 ([PASS]/[WARN]/[SKIP])
- 批量选择、分步执行
- 适用于复杂架构导入、长时间任务
- **实现**: `scripts/hitl_mode_c.py`

**CheckPoint 机制:**
| 检查点 | 触发时机 | 人工操作 | 环境要求 |
|--------|----------|----------|----------|
| CP1 意图确认 | NL2HCL 解析后 | 确认/修改资源清单 | **全部环境: 必须** |
| CP2 配置审核 | HCL 生成后 | 审核代码、修改变量 | uat+:必须 |
| CP3 Plan 确认 | terraform plan 后 | 确认变更范围 | production:严格模式 |
| CP4 导入确认 | Reverse Engineering 后 | 选择导入范围 | 导入场景必须 |
| CP5 销毁确认 | terraform destroy 前 | 双重确认 | production:冷却期 |

Full spec: [references/hitl-workflow.md](references/hitl-workflow.md)

## 12. References

- [Core Concepts](references/core-concepts.md) - Terraform fundamentals, backend, workspaces
- [NL2HCL Generator](references/nl2hcl-generator.md) - Natural language to HCL conversion
- [Reverse Engineering](references/reverse-engineering.md) - Import existing resources
- [HITL Workflow](references/hitl-workflow.md) - Human-in-the-Loop approval and confirmation flows
- [HITL Implementation](references/hitl-implementation.md) - Multi-mode HITL implementation details
- [Interactive Wizard](references/interactive-wizard.md) - Terraform IaC interactive wizard
- [Prompt Templates](references/prompt-templates.md) - GCL prompt templates for Generator, Critic, H
- [Rubric](references/rubric.md) - GCL scoring rubric and safety rules

## 13. Token Efficiency Notes

- Use `terraform plan -out=tfplan` to avoid re-planning
- Module sources use relative paths: `source = "../../modules/xxx"`
- Environment-specific values in `terraform.tfvars`, not inline
- Common tags defined in locals, merged per resource

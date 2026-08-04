---
name: alicloud-terraform-ops
description: >-
  Use when the user needs to manage Alibaba Cloud infrastructure using Terraform —
  create, modify, and destroy resources through Infrastructure-as-Code. Supports
  multi-environment management, remote state storage, NL2HCL (natural language to
  HCL), and reverse engineering from existing resources.
license: MIT
metadata:
  author: alicloud
  version: "1.0.0"
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
  - "NL2HCL: 将自然语言描述转换为 Terraform HCL 配置"
  - "Reverse Engineering: 从现有阿里云资源逆向生成 Terraform 配置和导入脚本"
should_not:
  - 执行数据平面操作（SQL 执行、Redis 命令等）
  - 替代日常运维诊断和故障排查（使用对应 product-ops skills）
  - 处理需要即时响应的临时操作
  - 管理 Terraform 不支持的细粒度配置（如参数模板调优）
delegation_rules:
  - trigger: "GCL 质量门禁 / apply / destroy / import 执行前评审"
    delegate_to: "alicloud-gcl-runner-ops"
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

> **Agent 开发/扩展本 skill**（改 `modules/`、`scripts/`、新增 NL2HCL 模块）→ 先读 [`AGENTS.md`](AGENTS.md)。

# alicloud-terraform-ops

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Prefer `./scripts/terraform-harness-wrapper.sh` when using Alibaba Cloud CLI paths; primary IaC execution uses Python scripts + `terraform` binary. Legacy `terraform-harness-wrapper.sh` shim supported. Fallback: when the wrapper is unavailable or `skillopt-lib.sh` is missing, call the `terraform` binary directly (driven by `scripts/` Python orchestrators); native `aliyun terraform` CLI is only used for the small subset of data-plane reads not covered by `terraform show`/`state`. `terraform-skillopt-wrapper.sh` is a legacy delegate that forwards to the harness wrapper — prefer the harness wrapper directly. | [Scripts](scripts/README.md), [Harness](references/skillopt-integration.md) |

Terraform IaC skill for Alibaba Cloud infrastructure lifecycle management. Declarative, version-controlled, multi-environment orchestration.


> **EXECUTION MANDATORY RULE**: 所有 CLI 执行步骤 **必须** 通过 wrapper `./scripts/terraform-harness-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun terraform ...` 命令在执行时应替换为 `./scripts/terraform-harness-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用时，才退回到原生 `aliyun terraform` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。
>
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
cd .runtime/terraform-ops/environments/{{user.environment}}
terraform init

# 2. Plan changes
terraform plan -out=tfplan

# 3. Apply (after review)
terraform apply tfplan

# 4. Destroy when needed
terraform destroy
```markdown

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

预置模板见 `environments/`（`dev` / `staging` / `prod`）。运行时工作目录为 **`.runtime/terraform-ops/environments/<env>/`**（gitignored，首次 apply 自动从模板复制）。

```text
environments/                              # 模板（进 Git）
.runtime/terraform-ops/
├── nl2hcl/<env>/                          # NL2HCL 生成物
├── import/<batch>/                        # 逆向工程 HCL
├── environments/<env>/                    # apply/destroy 工作区
└── pr-store/                              # HITL Mode B
```markdown

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

#### 5.3.1 Module Catalog

| 模块 | 用途 | 主要变量 |
|------|------|----------|
| `addon-cms-alarm` | 云监控告警规则 + 联系人组 | `environment`, `cpu_threshold`, `memory_threshold`, `alarm_resources` |
| `compute-ecs` | 安全组 + ECS | `vpc_id`, `instance_type`, `instance_count` |
| `addon-rds` | RDS MySQL | `engine_version`, `instance_class`, `storage` |
| `addon-redis` | Redis | `instance_type`, `vpc_auth_mode` |
| `addon-slb` | 负载均衡 | `backend_servers`, `listener_protocol` |
| `vpc-network` | VPC + vSwitch | `cidr`, `az_count` |

> **CMS 告警模块**（`addon-cms-alarm`）支持：
> - 预置 CPU/内存/磁盘/SLB 502 告警规则
> - 按资源 ID 指定告警对象（`alarm_resources`）
> - 钉钉 Webhook 通知
> - 静默周期配置

### 5.4 Backend Configuration

```hcl
# backend.tf
terraform {
  backend "oss" {
    bucket     = "my-terraform-state"
    prefix     = "terraform-ops/environments/dev"
    key        = "terraform.tfstate"
    tablestore_endpoint = "https://my-terraform.ots.cn-hangzhou.aliyuncs.com"
    tablestore_table    = "terraform_state_lock"
  }
}
```markdown

## 6. Post-execution Validation

| Check | Command | Expected |
|-------|---------|----------|
| State persistence | `aliyun oss cat oss://{{env.TF_BACKEND_BUCKET}}/{{user.environment}}/terraform.tfstate` | Valid JSON |
| Resource creation | `aliyun {{resource}} Describe{{Resource}}s` | Resources exist |
| Output values | `terraform output -json` | Expected outputs |
| State lock released | OTS row existence check | No lock rows |

## 7. Failure Recovery

Full diagnostic guide: [references/troubleshooting.md](references/troubleshooting.md)

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
```markdown

### 9.2 Plan Review Requirement

Always run `terraform plan` before `apply`. Never use `auto-approve` in production.

### 9.3 State Backup

```bash
# Backup before destructive operations
terraform state pull > backup-$(date +%Y%m%d-%H%M%S).tfstate
```

## 10. Well-Architected Assessment

Full five-pillar guide: [references/well-architected-assessment.md](references/well-architected-assessment.md)

| Pillar | Assessment | Implementation |
|--------|-----------|----------------|
| **Security** | State contains sensitive data | OSS encryption, least privilege, GCL secret scan |
| **Stability** | State corruption risk | Remote backend, OTS locking, state backup before destroy |
| **Cost** | Resource tracking | Module reuse, tags, environment TTL |
| **Efficiency** | Environment consistency | GitOps + HITL Mode B for uat/prod |
| **Performance** | Parallel resource creation | Terraform dependency graph; tune parallelism on throttle |

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

```text
╔════════════════════════════════════════════════════════════════╗
║                    🔍 DRY-RUN MODE (干运行模式)                  ║
║         此执行仅用于预览和验证，不会创建或修改任何资源            ║
╚════════════════════════════════════════════════════════════════╝
```markdown

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

**Output (runtime, gitignored under `.runtime/terraform-ops/`):**

- `import/<batch>/` — HCL configuration files
- `import.sh` — Import script for `terraform import`
- `import.tf` — Generated resource blocks

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

```text
╔════════════════════════════════════════════════════════════════╗
║                    🔍 DRY-RUN MODE (干运行模式)                  ║
║         此执行仅用于预览和验证，未修改 Terraform 状态            ║
╚════════════════════════════════════════════════════════════════╝
```

每条日志行前缀: `[DRY-RUN]`

Full spec: [references/reverse-engineering.md](references/reverse-engineering.md)

### 11.3 CMS Alarm — 云监控告警 AGI 能力

用户友好的云监控告警管理，支持自然语言交互。

#### 触发模式

| 用户说 | AGI 理解 | 执行操作 |
|--------|----------|----------|
| "为 ECS 创建 CPU 告警" | 创建 `cpu_alarm` 规则 | `alicloud_cms_alarm` |
| "配置钉钉告警通知" | 设置 `dingtalk_webhook` | 钉钉通知 |
| "配置飞书通知" | 设置 `feishu_webhook` | 飞书通知 |
| "配置企业微信通知" | 设置 `wecom_webhook` | 企业微信通知 |
| "配置多渠道通知" | 同时设置多个 Webhook | 多渠道通知 |
| "添加运维团队到告警联系人" | 更新 `contact_group` | 联系人管理 |
| "CPU 超过 90% 告警" | 设置 `cpu_threshold = 90` | 阈值配置 |
| "查看当前告警规则" | 查询已有告警 | `terraform state list` |
| "删除这个告警" | `terraform destroy -target` | 资源删除 |
| "把现有告警导入 Terraform" | Reverse Engineering | `terraform import` |

#### 自然语言示例

**场景 1: 创建告警**

```
用户: "为生产环境的 ECS 实例创建 CPU 和内存告警，阈值分别是 80% 和 85%，同时配置钉钉和飞书通知"

AGI 执行:
1. 生成 HCL:
   module "cms_alarm" {
     source = "../../modules/addon-cms-alarm"
     environment = "production"
     cpu_threshold = 80
     memory_threshold = 85
     dingtalk_webhook = var.dingtalk_webhook
     feishu_webhook = var.feishu_webhook
     alarm_resources = [{ resource_type = "acs_ecs", metric_name = "cpu_total", ... }]
   }
2. terraform plan (dry-run)
3. 用户确认后 apply
```

**场景 2: 批量告警**

```
用户: "为这 5 台 RDS 实例都添加磁盘使用率超过 80% 的告警，配置企业微信通知"

AGI 执行:
1. 解析用户提供的 RDS 实例列表
2. 生成 for_each 循环的告警配置
3. 配置 wecom_webhook
4. plan → apply
```

**场景 3: 多渠道通知**

```
用户: "配置钉钉、飞书、企业微信三个渠道的告警通知"

AGI 执行:
1. 询问用户三个渠道的 Webhook URL
2. 生成多渠道配置:
   dingtalk_webhook = "https://oapi.dingtalk.com/..."
   feishu_webhook = "https://open.feishu.cn/..."
   wecom_webhook = "https://qyapi.weixin.qq.com/..."
3. terraform plan → apply
```

**场景 4: 告警恢复**

```
用户: "生产环境磁盘告警阈值从 85% 调整到 90%"

AGI 执行:
1. 修改 variables.tf 中 disk_threshold
2. terraform plan (显示变更)
3. 用户确认后 apply
```

#### 告警模板变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `environment` | 环境名称 | 必填 |
| `cpu_threshold` | CPU 告警阈值 | 80% |
| `memory_threshold` | 内存告警阈值 | 85% |
| `disk_threshold` | 磁盘告警阈值 | 85% |
| `slb_502_threshold` | SLB 5xx 阈值 | 5% |
| `alarm_resources` | 指定告警的资源 | 全量 |
| `dingtalk_webhook` | 钉钉 Webhook URL | 可选 |
| `feishu_webhook` | 飞书 Webhook URL | 可选 |
| `wecom_webhook` | 企业微信 Webhook URL | 可选 |
| `email_contacts` | 邮件联系人 | 可选 |
| `sms_contacts` | 短信联系人 | 可选 |
| `silence_minutes` | 静默周期 | 15 分钟 |

#### AGI 意图解析规则

```python
# 意图解析逻辑
INTENT_PATTERNS = {
    # 创建类
    "创建.*告警": CreateAlarm,
    "添加.*告警": CreateAlarm,
    "配置.*告警": CreateAlarm,
    
    # 修改类
    "调整.*阈值": UpdateThreshold,
    "修改.*告警": UpdateAlarm,
    
    # 删除类
    "删除.*告警": DeleteAlarm,
    "移除.*告警": DeleteAlarm,
    
    # 查询类
    "查看.*告警": QueryAlarm,
    "列出.*告警": ListAlarm,
    
    # 导入类
    "导入.*告警": ImportAlarm,
    "纳管.*告警": ImportAlarm,
}

# 阈值提取
THRESHOLD_PATTERNS = {
    "cpu.*超过.*(\d+)%": ("cpu_threshold", int(match)),
    "cpu.*大于.*(\d+)%": ("cpu_threshold", int(match)),
    "内存.*超过.*(\d+)%": ("memory_threshold", int(match)),
    "磁盘.*超过.*(\d+)%": ("disk_threshold", int(match)),
}
# 通知渠道提取
WEBHOOK_PATTERNS = {
    "钉钉": "dingtalk_webhook",
    "飞书": "feishu_webhook",
    "lark": "feishu_webhook",
    "企业微信": "wecom_webhook",
}
```

#### 输出规范

**创建告警输出示例:**

```markdown
## CMS 告警配置

### 环境: production

### 告警规则

| 规则 | 指标 | 阈值 | 监控资源 |
|------|------|------|----------|
| CPU 告警 | cpu_total | 80% | 所有 ECS |
| 内存告警 | memory_usedutilization | 85% | 所有 ECS |
| 磁盘告警 | diskusage_utilization | 85% | 所有 ECS |

### 通知配置

| 渠道 | 状态 | 配置 |
|------|------|------|
| 钉钉 | ✅ 已配置 / ⏳ 未配置 | dingtalk_webhook |
| 飞书 | ✅ 已配置 / ⏳ 未配置 | feishu_webhook |
| 企业微信 | ✅ 已配置 / ⏳ 未配置 | wecom_webhook |
| 邮件 | ✅ 已配置 / ⏳ 未配置 | email_contacts |
| 短信 | ✅ 已配置 / ⏳ 未配置 | sms_contacts |

### 下一步

```bash
# 预览变更
terraform plan

# 确认后应用
terraform apply
```
```

#### 相关文档

- **规格**: [references/Spec-cms-alarm.md](references/Spec-cms-alarm.md)
- **ADR**: [references/adr/ADR-001-terraform-cms-alarm-management.md](references/adr/ADR-001-terraform-cms-alarm-management.md)
- **知识库**: [references/knowledge-cms-alarm.md](references/knowledge-cms-alarm.md)
- **模块**: `modules/addon-cms-alarm/`

### 11.4 HITL Multi-Mode Workflow

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

## 12. Quality Gate (GCL)

This skill is registered in [`docs/gcl-spec.md` §8](../docs/gcl-spec.md#8-per-skill-defaults) as
**GCL required** (`max_iter=2`). Every runtime execution of `terraform apply`, `terraform destroy`,
reverse-engineering import, or NL2HCL generation that mutates state MUST pass a GCL loop before
returning results to the user.

> **GCL contract files:** [`references/rubric.md`](references/rubric.md) and
> [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|--------|---------|
| Classification | **required** |
| Default `max_iter` | **2** |
| Hallucination check | **MANDATORY** (CLI/HCL parameter + secret patterns) |
| Most-scrutinized ops | `terraform destroy`, production `apply`, state import, NL2HCL with destroy in plan |

### Per-Op Safety Highlights

| Operation | Hard condition |
|-----------|----------------|
| `terraform destroy` | Environment confirmation + state backup + no `auto-approve` in prod (DESTROY-001~005) |
| `terraform apply` | Plan file exists and reviewed; destructive changes flagged (APPLY-001~004) |
| Reverse engineering import | User acknowledges state modification (REV-003); HITL CP4 |
| NL2HCL | No hardcoded secrets; validate before apply (NL2HCL-001~003) |

### GCL Execution

Delegate to `alicloud-gcl-runner-ops`:

```bash
python alicloud-gcl-runner-ops/scripts/gcl_runner.py \
  --skill alicloud-terraform-ops \
  --op Apply \
  --command "terraform apply tfplan" \
  --rubric alicloud-terraform-ops/references/rubric.md
```markdown

Setup and env vars: [references/integration.md](references/integration.md).

## 13. References

- [Core Concepts](references/core-concepts.md) - Terraform fundamentals, backend, workspaces
- [Integration](references/integration.md) - Toolchain, credentials, backend, GCL runner wiring
- [Troubleshooting](references/troubleshooting.md) - Error codes, diagnostics, recovery
- [Well-Architected Assessment](references/well-architected-assessment.md) - Five-pillar assessment
- [NL2HCL Generator](references/nl2hcl-generator.md) - Natural language to HCL conversion
- [Reverse Engineering](references/reverse-engineering.md) - Import existing resources
- [HITL Workflow](references/hitl-workflow.md) - Human-in-the-Loop approval and confirmation flows
- [HITL Implementation](references/hitl-implementation.md) - Multi-mode HITL implementation details
- [Interactive Wizard](references/interactive-wizard.md) - Terraform IaC interactive wizard
- [Prompt Templates](references/prompt-templates.md) - GCL prompt templates for Generator, Critic, H
- [Rubric](references/rubric.md) - GCL scoring rubric and safety rules

## 14. Token Efficiency Notes

- Use `terraform plan -out=tfplan` to avoid re-planning
- Module sources use relative paths: `source = "../../modules/xxx"`
- Environment-specific values in `terraform.tfvars`, not inline
- Common tags defined in locals, merged per resource

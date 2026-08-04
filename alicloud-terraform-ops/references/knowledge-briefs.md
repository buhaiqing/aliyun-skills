# Terraform Knowledge Briefs — 知识简报

> 运维必备 Terraform 知识点速查

---

## Brief 1: Terraform 工作流

```
┌─────────────────────────────────────────────────────────────┐
│  init        plan         apply          destroy           │
│    │           │            │              │              │
│    ▼           ▼            ▼              ▼              │
│ ┌──────┐   ┌──────┐    ┌──────┐      ┌──────┐           │
│ │获取   │   │预览  │    │执行  │      │删除  │           │
│ │Provider│   │变更  │    │变更  │      │资源  │           │
│ │Backend │   │      │    │      │      │      │           │
│ └──────┘   └──────┘    └──────┘      └──────┘           │
└─────────────────────────────────────────────────────────────┘
```

| 命令 | 作用 | 幂等性 |
|------|------|--------|
| `terraform init` | 初始化 Provider/Backend | 幂等 |
| `terraform plan` | 预览变更计划 | 只读 |
| `terraform apply` | 执行变更 | 幂等 |
| `terraform destroy` | 删除所有资源 | 破坏性 |
| `terraform validate` | HCL 语法校验 | 只读 |

**黄金法则**: **始终先 `plan` 再 `apply`**

---

## Brief 2: HCL 核心语法

### 资源定义
```hcl
resource "alicloud_vpc" "main" {
  name       = "my-vpc"
  cidr_block = "10.0.0.0/16"
  
  tags = {
    Environment = "production"
  }
}
```

### 变量与输出
```hcl
# variables.tf
variable "environment" {
  type    = string
  default = "dev"
}

# outputs.tf
output "vpc_id" {
  value       = alicloud_vpc.main.id
  description = "VPC ID"
}
```

### 依赖管理
```hcl
# 隐式依赖 (referencing)
vpc_id = alicloud_vpc.main.id

# 显式依赖 (when no reference)
resource "alicloud_instance" "ecs" {
  # ...
  depends_on = [alicloud_vpc.main]
}
```

### 动态配置
```hcl
# 条件表达式
count = var.create_ecs ? 3 : 0

# 三元运算
instance_type = var.env == "prod" ? "ecs.g6.large" : "ecs.n4.small"

# for_each
for_each = toset(["web", "api", "worker"])
name     = "${var.env}-${each.value}"
```

---

## Brief 3: State 管理

### State 是什么
- **State = Terraform 的内存**: 记录"实际创建了哪些资源"
- **State ≠ 实际云资源**: 云上真实资源由 State 追踪
- **State 文件**: `terraform.tfstate`（本地）或远程存储

### State 锁定机制
```
┌─────────┐     Lock      ┌─────────────┐
│  Terraform│ ─────────────▶│ Backend     │
│  apply   │ ◀─────────────│ (OSS+S3)   │
└─────────┘   Unlock      └─────────────┘
```

| Backend | 锁存储 |
|---------|--------|
| OSS + TableStore | TableStore 行锁 |
| S3 + DynamoDB | DynamoDB 行锁 |
| Consul | Consul KV 锁 |

### State 命令
```bash
# 查看当前 State
terraform state list

# 查看指定资源
terraform state show alicloud_vpc.main

# 手动删除资源（从 State 中移除，但不删除云资源）
terraform state rm alicloud_vpc.main

# 移动资源
terraform state mv alicloud_vpc.main module.vpc

# 备份
terraform state pull > backup.tfstate
```

---

## Brief 4: Provider 配置

### 阿里云 Provider
```hcl
terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.200"
    }
  }
}

provider "alicloud" {
  access_key = var.access_key
  secret_key = var.secret_key
  region     = var.region
  
  # 可选: AssumeRole
  # assume_role {}
}

variable "access_key" {
  sensitive = true
}
```

### 认证方式优先级
```
1. 环境变量 (ALIBABA_CLOUD_ACCESS_KEY_ID / _SECRET)
2. AK/SK 直接配置
3. RAM Role (assume_role)
4. STS 临时凭证
```

---

## Brief 5: Module 开发

### 标准结构
```
module-name/
├── main.tf          # 资源定义
├── variables.tf     # 输入变量
├── outputs.tf       # 输出值
├── versions.tf      # 版本约束
└── README.md        # 使用文档
```

### Module 调用
```hcl
module "rds" {
  source = "../../modules/addon-rds"
  
  environment      = var.environment
  instance_class   = "mysql.n4.large"
  engine_version   = "8.0"
  storage          = 200
}

# 引用输出
vpc_id = module.rds.vpc_id
```

### Module 设计原则
| 原则 | 说明 |
|------|------|
| 单一职责 | 一个 Module 只管理一类资源 |
| 可组合 | 通过变量组合出不同配置 |
| 最小暴露 | 暴露必要变量，隐藏实现细节 |
| 幂等 | 重复 apply 不产生副作用 |

---

## Brief 6: Workspaces 与多环境

### Workspace 模式
```bash
# 创建/切换环境
terraform workspace new production
terraform workspace select production

# 查看所有 workspace
terraform workspace list
```

### 目录模式 vs Workspace
| 场景 | 推荐方式 |
|------|----------|
| 环境差异小（仅参数不同） | Workspace |
| 环境差异大（资源类型不同） | 目录隔离 |
| 严格环境隔离 | 目录 + 独立 Backend |
| 临时测试环境 | Workspace |

### 多环境 Backend 隔离
```hcl
# environments/dev/backend.tf
terraform {
  backend "oss" {
    bucket = "tf-state-dev"
    prefix = "project/dev"
  }
}

# environments/prod/backend.tf
terraform {
  backend "oss" {
    bucket = "tf-state-prod"
    prefix = "project/prod"
  }
}
```

---

## Brief 7: 常见错误与解决

| 错误 | 原因 | 解决 |
|------|------|------|
| `Error acquiring the state lock` | State 被其他操作锁定 | 等待或 `terraform force-unlock` |
| `Cycle detected` | 资源依赖循环 | 检查 `depends_on`，打破循环 |
| `Resource already exists` | 资源已在云上 | 使用 `terraform import` |
| `Provider not initialized` | 未执行 `init` | `terraform init` |
| `No value for variable` | 变量未赋值 | 检查 `terraform.tfvars` |
| `Invalid for_each argument` | `for_each` 类型错误 | 改用 `toset()` 或 `tomap()` |
| `Permission denied` | AK/SK 权限不足 | 检查 RAM 策略 |

### Drift 检测
```bash
# 检测配置与实际的差异
terraform plan

# 输出示例
~ update in-place
-/+ destroy and then create replacement
-/+ destroy to recreate
```

---

## Brief 8: 安全实践

### 敏感信息管理
```hcl
# 敏感变量
variable "password" {
  sensitive = true  # apply 时不显示
}

# Secret 存储位置
# ✅ 环境变量
# ✅ Vault
# ❌ terraform.tfvars (不要提交到 Git)
# ❌ 代码注释
```

### .gitignore
```
# 敏感文件
*.tfstate
*.tfstate.*
secrets.tfvars
terraform.tfvars

# 备份
*.backup
```

### Lifecycle 保护
```hcl
resource "alicloud_db_instance" "main" {
  # 防止意外删除
  lifecycle {
    prevent_destroy = true
  }
}
```

---

## Brief 9: 性能优化

### 并行度控制
```bash
# 默认并行度 10
terraform apply -parallelism=5

# 大规模资源减少并发
terraform apply -parallelism=2
```

### State 优化
| 优化项 | 方法 |
|--------|------|
| State 文件大小 | 定期清理已删除资源 (`terraform state rm`) |
| Lock 等待时间 | `terraform apply -lock-timeout=5m` |
| Provider 缓存 | `./.terraform/plugin-cache` |

### 增量更新
```bash
# 只 plan 变更的部分
terraform plan -target=alicloud_vpc.main

# 只 apply 目标
terraform apply -target=alicloud_instance.web
```

---

## Brief 10: CLI 速查

```bash
# 初始化
terraform init [-upgrade]

# 预览
terraform plan [-out=tfplan] [-var-file=xxx.tfvars]
terraform plan -target=resource

# 执行
terraform apply [tfplan]
terraform apply -auto-approve  # 非交互模式

# 销毁
terraform destroy [-target=resource]
terraform destroy -auto-approve

# State
terraform state list
terraform state show address
terraform state mv source dest
terraform state rm address
terraform state pull > backup.tfstate

# Workspace
terraform workspace new|select|delete|list

# Import
terraform import address id

# 格式化
terraform fmt
terraform validate
```

---

## 快速导航

| 需求 | 参考 Brief |
|------|-----------|
| 新手上路 | Brief 1 工作流 |
| 写 Terraform 配置 | Brief 2 HCL 语法 |
| State 出问题 | Brief 3 State 管理 |
| 认证配置 | Brief 4 Provider |
| 复用配置 | Brief 5 Module |
| 多环境管理 | Brief 6 Workspaces |
| 报错处理 | Brief 7 常见错误 |
| 安全加固 | Brief 8 安全实践 |
| 性能调优 | Brief 9 性能优化 |
| 命令速查 | Brief 10 CLI |

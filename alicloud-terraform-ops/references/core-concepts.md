# Core Concepts

Terraform 基础概念与阿里云 Provider 配置。

## 1. Terraform 核心概念

### 1.1 声明式 vs 命令式

| 命令式 (CLI/SDK) | 声明式 (Terraform) |
|-----------------|-------------------|
| "创建一台 ECS" | "我想要一台 ECS，配置是..." |
| 关注操作步骤 | 关注期望状态 |
| 需要手动处理依赖顺序 | 自动构建资源依赖图 |
| 重复执行可能出错 | 幂等，重复执行无副作用 |

### 1.2 核心工作流

```
Write (HCL) → Init → Plan → Apply → Destroy
     ↑                                    ↓
     └──────── State 记录当前状态 ─────────┘
```

### 1.3 关键文件

| 文件 | 用途 |
|------|------|
| `*.tf` | 资源配置（HCL 语法） |
| `terraform.tfvars` | 变量值（环境特定） |
| `.terraform/` | Provider 插件和模块缓存 |
| `terraform.tfstate` | 状态文件（资源映射） |
| `.terraform.lock.hcl` | Provider 版本锁定 |

## 2. 阿里云 Provider 配置

### 2.1 基础配置

```hcl
# provider.tf
terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.220"
    }
  }
  required_version = ">= 1.5.0"
}

provider "alicloud" {
  region = var.region
  
  # 凭证从环境变量读取
  # ALIBABA_CLOUD_ACCESS_KEY_ID
  # ALIBABA_CLOUD_ACCESS_KEY_SECRET
}
```

### 2.2 多区域配置

```hcl
# 主区域
provider "alicloud" {
  alias  = "hangzhou"
  region = "cn-hangzhou"
}

# 备用区域
provider "alicloud" {
  alias  = "shanghai"
  region = "cn-shanghai"
}

# 使用特定 Provider
resource "alicloud_instance" "backup" {
  provider = alicloud.shanghai
  # ...
}
```

## 3. Backend 配置

### 3.1 OSS Backend

```hcl
# backend.tf
terraform {
  backend "oss" {
    bucket              = "mycompany-terraform-state"
    prefix              = "projects/web-app"
    key                 = "terraform.tfstate"
    region              = "cn-hangzhou"
    tablestore_endpoint = "https://terraform-state.cn-hangzhou.ots.aliyuncs.com"
    tablestore_table    = "state_lock"
  }
}
```

### 3.2 Backend 初始化

```bash
# 首次初始化（交互式）
terraform init

# 使用配置文件
terraform init -backend-config=backend.hcl

# 迁移本地状态到远程
terraform init -migrate-state
```

### 3.3 Backend 配置分离

```hcl
# backend.hcl（不提交到 Git）
bucket              = "mycompany-terraform-state"
prefix              = "projects/web-app"
tablestore_endpoint = "https://terraform-state.cn-hangzhou.ots.aliyuncs.com"
tablestore_table    = "state_lock"
```

```bash
terraform init -backend-config=backend.hcl
```

## 4. Workspaces

### 4.1 Workspace 命令

```bash
# 列出 workspaces
terraform workspace list

# 创建新 workspace
terraform workspace new dev

# 切换到 workspace
terraform workspace select dev

# 显示当前 workspace
terraform workspace show

# 删除 workspace
terraform workspace delete dev
```

### 4.2 Workspace 与变量

```hcl
# 根据 workspace 设置变量
locals {
  env_config = {
    dev = {
      instance_type = "ecs.t6-c1m1.large"
      count         = 1
    }
    staging = {
      instance_type = "ecs.c6.large"
      count         = 2
    }
    prod = {
      instance_type = "ecs.c6.xlarge"
      count         = 3
    }
  }
  
  current_env = local.env_config[terraform.workspace]
}

resource "alicloud_instance" "web" {
  instance_type = local.current_env.instance_type
  count         = local.current_env.count
  # ...
}
```

### 4.3 Workspace 隔离策略

| 场景 | 推荐策略 |
|------|---------|
| 环境配置差异小 | Workspaces + 条件逻辑 |
| 环境配置差异大 | 目录隔离（完全独立的配置） |
| 临时测试环境 | Workspace（快速创建/销毁） |
| 严格环境隔离 | 目录 + 独立 backend |

## 5. 资源依赖

### 5.1 隐式依赖

Terraform 自动分析引用关系：

```hcl
resource "alicloud_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

# 自动依赖 VPC
resource "alicloud_vswitch" "subnet" {
  vpc_id     = alicloud_vpc.main.id  # 隐式依赖
  cidr_block = "10.0.1.0/24"
}
```

### 5.2 显式依赖

```hcl
resource "alicloud_instance" "web" {
  # ...
  
  depends_on = [
    alicloud_nat_gateway.nat,
    alicloud_route_entry.nat_route
  ]
}
```

### 5.3 依赖图查看

```bash
# 生成依赖图
terraform graph | dot -Tpng > graph.png

# 查看执行顺序
terraform plan -out=tfplan && terraform show -json tfplan | jq '.resource_changes[].address'
```

## 6. 生命周期管理

### 6.1 Lifecycle 元参数

```hcl
resource "alicloud_instance" "web" {
  # ...
  
  lifecycle {
    # 防止意外销毁
    prevent_destroy = true
    
    # 忽略特定字段变更
    ignore_changes = [
      image_id,  # 允许控制台升级镜像
      user_data, # 忽略启动脚本变更
    ]
    
    # 先创建新资源再销毁旧资源
    create_before_destroy = true
  }
}
```

### 6.2 替换策略

```hcl
# 触发替换的条件
resource "alicloud_instance" "web" {
  image_id = var.image_id
  
  # 当 image_id 变更时，触发替换
  lifecycle {
    replace_triggered_by = [
      terraform_data.image_update
    ]
  }
}
```

## 7. 输出与数据

### 7.1 输出定义

```hcl
# outputs.tf
output "vpc_id" {
  description = "VPC ID"
  value       = alicloud_vpc.main.id
}

output "ecs_ips" {
  description = "ECS 内网 IP 列表"
  value       = alicloud_instance.web[*].private_ip
  sensitive   = false
}

output "rds_password" {
  description = "RDS 初始密码"
  value       = random_password.db_password.result
  sensitive   = true  # 标记敏感，不在控制台显示
}
```

### 7.2 数据源查询

```hcl
# 查询现有资源
data "alicloud_zones" "available" {
  available_disk_category     = "cloud_efficiency"
  available_resource_creation = "VSwitch"
}

# 使用查询结果
resource "alicloud_vswitch" "subnet" {
  availability_zone = data.alicloud_zones.available.zones[0].id
  # ...
}
```

### 7.3 远程状态引用

```hcl
# 引用其他 Terraform 配置的状态
data "terraform_remote_state" "network" {
  backend = "oss"
  config = {
    bucket = "mycompany-terraform-state"
    prefix = "shared/network"
    region = "cn-hangzhou"
  }
}

resource "alicloud_instance" "web" {
  vswitch_id = data.terraform_remote_state.network.outputs.vswitch_id
  # ...
}
```

## 8. 变量与类型

### 8.1 变量定义

```hcl
# variables.tf
variable "region" {
  description = "阿里云区域"
  type        = string
  default     = "cn-hangzhou"
}

variable "instance_config" {
  description = "ECS 配置"
  type = object({
    type  = string
    count = number
    image = optional(string, "centos_8")
  })
  default = {
    type  = "ecs.t6-c1m1.large"
    count = 1
  }
}

variable "allowed_ips" {
  description = "允许访问的 IP 列表"
  type        = list(string)
  default     = []
}
```

### 8.2 变量验证

```hcl
variable "environment" {
  description = "环境名称"
  type        = string
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "环境必须是 dev、staging 或 prod"
  }
}

variable "vpc_cidr" {
  description = "VPC CIDR"
  type        = string
  
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "必须是有效的 CIDR 格式"
  }
}
```

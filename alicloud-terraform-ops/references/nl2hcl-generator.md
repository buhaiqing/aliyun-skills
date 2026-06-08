# NL2HCL Generator - 自然语言生成 Terraform 配置

将自然语言描述转换为可执行 Terraform HCL 配置的完整规范。

## 1. 概述

### 1.1 功能定位

| 维度 | 说明 |
|------|------|
| **输入** | 中文/英文自然语言描述（如"创建 VPC 和两个可用区的交换机"） |
| **输出** | 完整 Terraform 配置文件（main.tf/variables.tf/outputs.tf） |
| **核心能力** | 语义理解 → 资源映射 → 依赖构建 → HCL 生成 |
| **约束** | 仅生成声明式配置，不执行 terraform 命令 |

### 1.2 架构分层

```
┌─────────────────────────────────────────┐
│  Input: 自然语言描述                      │
│  "创建一个 VPC，两个交换机，3台 ECS"        │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 1: 语义解析层 (Semantic Parser)     │
│  - 意图识别 (创建/修改/销毁)               │
│  - 实体抽取 (资源类型、数量、属性)          │
│  - 关系建模 (资源间拓扑关系)               │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 2: 资源映射层 (Resource Mapper)     │
│  - 术语标准化 (ECS → alicloud_instance)   │
│  - 属性映射 (规格 → instance_type)        │
│  - 默认值填充                           │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 3: 依赖构建层 (Dependency Builder)  │
│  - 隐式依赖分析 (ECS 依赖 VPC)            │
│  - 显式依赖声明                         │
│  - 拓扑排序                             │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 4: HCL 生成层 (HCL Generator)      │
│  - 代码格式化                           │
│  - 变量抽象                             │
│  - 最佳实践注入 (tags/lifecycle)          │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Output: Terraform 配置文件               │
│  main.tf / variables.tf / outputs.tf      │
└─────────────────────────────────────────┘
```

## 2. 语义解析层

### 2.1 意图识别

| 意图类型 | 关键词 | 示例 |
|----------|--------|------|
| **Create** | 创建、搭建、新建、部署 | "创建一个 VPC" |
| **Extend** | 扩容、增加、添加 | "给 VPC 添加一个交换机" |
| **Modify** | 修改、变更、升级 | "把 ECS 规格改为 4 核" |
| **Destroy** | 删除、销毁、清理 | "销毁测试环境的资源" |

**输出格式**:
```json
{
  "intent": "create",
  "confidence": 0.95,
  "scope": "full_stack"
}
```

### 2.2 实体抽取

#### 资源实体

| 字段 | 类型 | 示例 |
|------|------|------|
| `resource_type` | enum | vpc, vswitch, ecs, rds, slb, redis |
| `quantity` | number | 2, "多台"(默认3) |
| `name_hint` | string | "web-server", "主数据库" |
| `attributes` | map | {"规格": "ecs.c6.large", "可用区": "cn-hangzhou-b"} |

#### 抽取示例

输入: "创建 3 台 ecs.c6.large 规格的 ECS，部署在 cn-hangzhou-b 可用区"

```json
{
  "entities": [
    {
      "type": "ecs",
      "quantity": 3,
      "attributes": {
        "instance_type": "ecs.c6.large",
        "availability_zone": "cn-hangzhou-b"
      }
    }
  ]
}
```

### 2.3 关系建模

自动识别资源间关系:

| 关系类型 | 描述 | 示例 |
|----------|------|------|
| **Contain** | A 包含 B | VPC 包含 VSwitch |
| **Attach** | A 挂载到 B | ECS 挂载到 SLB |
| **Connect** | A 连接到 B | ECS 连接到 RDS |
| **Depend** | A 依赖 B | ECS 依赖 SecurityGroup |

**关系图表示**:
```json
{
  "relations": [
    {"from": "vpc-1", "to": "vswitch-1", "type": "contain"},
    {"from": "vswitch-1", "to": "ecs-1", "type": "contain"},
    {"from": "ecs-1", "to": "slb-1", "type": "attach"}
  ]
}
```

## 3. 资源映射表

### 3.1 术语映射

#### 核心资源

| 自然语言 | Terraform 资源 | 说明 |
|----------|---------------|------|
| VPC / 专有网络 | `alicloud_vpc` | 虚拟私有云 |
| 交换机 / VSwitch | `alicloud_vswitch` | 子网 |
| ECS / 云服务器 | `alicloud_instance` | 虚拟机 |
| RDS / 数据库 | `alicloud_db_instance` | 关系型数据库 |
| SLB / 负载均衡 | `alicloud_slb_load_balancer` | 负载均衡 |
| Redis / 缓存 | `alicloud_kvstore_instance` | 云数据库 Redis |
| OSS / 对象存储 | `alicloud_oss_bucket` | 存储桶 |
| NAT / 网关 | `alicloud_nat_gateway` | NAT 网关 |
| 安全组 / SecurityGroup | `alicloud_security_group` | 防火墙 |

#### 网络资源

| 自然语言 | Terraform 资源 | 说明 |
|----------|---------------|------|
| EIP / 公网 IP | `alicloud_eip` | 弹性公网 IP |
| 路由表 / RouteTable | `alicloud_route_table` | 路由表 |
| 弹性网卡 / ENI | `alicloud_network_interface` | 辅助网卡 |

### 3.2 属性映射

#### ECS 属性

| 自然语言 | TF 属性 | 示例值 |
|----------|---------|--------|
| 规格 / 实例类型 | `instance_type` | ecs.c6.large, ecs.g7.xlarge |
| 镜像 / 操作系统 | `image_id` | centos_8, ubuntu_22 |
| 系统盘大小 | `system_disk_size` | 40, 100 |
| 系统盘类型 | `system_disk_category` | cloud_efficiency, cloud_ssd |
| 数据盘 | `data_disks` | [{"size": 100, "category": "cloud_ssd"}] |
| 可用区 | `availability_zone` | cn-hangzhou-b |
| 密码 | `password` | (变量化) |
| 密钥对 | `key_name` | my-key-pair |

#### VPC 属性

| 自然语言 | TF 属性 | 示例值 |
|----------|---------|--------|
| CIDR / 网段 | `cidr_block` | 10.0.0.0/16 |
| 名称 | `vpc_name` / `name` | my-vpc |
| 描述 | `description` | 生产环境 VPC |

#### RDS 属性

| 自然语言 | TF 属性 | 示例值 |
|----------|---------|--------|
| 引擎 | `engine` | MySQL, PostgreSQL |
| 版本 | `engine_version` | 8.0, 13.0 |
| 规格 | `db_instance_class` | rds.mysql.c1.large |
| 存储空间 | `db_instance_storage` | 100 |
| 存储类型 | `db_instance_storage_type` | local_ssd, cloud_ssd |

### 3.3 默认值策略

当用户未指定时，使用环境敏感的默认值:

```yaml
defaults:
  vpc:
    cidr_block: "10.0.0.0/16"  # 自动分配，避免冲突
    
  ecs:
    instance_type: 
      dev: "ecs.t6-c1m1.large"      # 低成本
      prod: "ecs.c6.large"          # 标准规格
    image_id: "centos_8"
    system_disk_size: 40
    
  vswitch:
    cidr_block: "10.0.{index}.0/24"  # 自动子网划分
    
  rds:
    engine: "MySQL"
    engine_version: "8.0"
    db_instance_class:
      dev: "rds.mysql.t1.small"
      prod: "rds.mysql.c1.large"
```

## 4. 生成流程

### 4.1 五步流程

```
Step 1: 语义解析 (Semantic Parsing)
   └─ 输入: 自然语言文本
   └─ 输出: 结构化意图 + 实体列表 + 关系图
   └─ 工具: LLM + 规则校验

Step 2: 资源标准化 (Resource Normalization)
   └─ 输入: 实体列表
   └─ 输出: Terraform 资源定义草案
   └─ 操作: 术语映射、属性转换、默认值填充

Step 3: 依赖图构建 (Dependency Graph Building)
   └─ 输入: 资源定义 + 关系图
   └─ 输出: 有向无环图 (DAG)
   └─ 算法: 拓扑排序，检测循环依赖

Step 4: HCL 代码生成 (HCL Code Generation)
   └─ 输入: DAG + 资源配置
   └─ 输出: 格式化 HCL 代码
   └─ 规则: 依赖优先、变量抽象、最佳实践

Step 5: 验证与优化 (Validation & Optimization)
   └─ 输入: HCL 文件集合
   └─ 输出: 通过 `terraform validate` 的配置
   └─ 操作: 语法检查、变量优化、注释添加
   
Step 6: Dry-Run 预览 (可选)
   └─ 输入: 验证后的 HCL
   └─ 输出: terraform plan 结果预览
   └─ 操作: 初始化 backend，执行 plan，展示变更摘要
```

### 4.2 详细流程示例

**输入**: "创建一个 VPC，包含两个可用区的交换机，每个交换机下挂 2 台 ECS"

**Step 1 - 语义解析**:
```json
{
  "intent": "create",
  "entities": [
    {"type": "vpc", "quantity": 1, "name": "main"},
    {"type": "vswitch", "quantity": 2, "attributes": {"zone_count": 2}},
    {"type": "ecs", "quantity": 4, "distribution": "vswitch:2"}
  ],
  "relations": [
    {"from": "vpc", "to": "vswitch", "type": "contain", "multiplicity": "1:n"},
    {"from": "vswitch", "to": "ecs", "type": "contain", "multiplicity": "1:n"}
  ]
}
```

**Step 2 - 资源标准化**:
```json
{
  "resources": [
    {
      "tf_type": "alicloud_vpc",
      "name": "main",
      "attributes": {"cidr_block": "10.0.0.0/16"}
    },
    {
      "tf_type": "alicloud_vswitch",
      "name": "subnet",
      "count": 2,
      "attributes": {
        "cidr_block": "10.0.${count.index+1}.0/24",
        "availability_zone": "${data.alicloud_zones.available.zones[count.index].id}"
      },
      "depends_on": ["alicloud_vpc.main"]
    },
    {
      "tf_type": "alicloud_instance",
      "name": "web",
      "count": 4,
      "attributes": {
        "vswitch_id": "${alicloud_vswitch.subnet[count.index % 2].id}"
      },
      "depends_on": ["alicloud_vswitch.subnet"]
    }
  ]
}
```

**Step 3 - 依赖图**:
```
alicloud_vpc.main
       │
       ▼
alicloud_vswitch.subnet[0] ──┐
       │                     │
       ▼                     │
alicloud_instance.web[0]     │
alicloud_instance.web[1]     │
                             │
alicloud_vswitch.subnet[1] ──┘
       │
       ▼
alicloud_instance.web[2]
alicloud_instance.web[3]
```

**Step 4 - HCL 生成**: (见第 7 节输出规范)

**Step 5 - 验证**:
```bash
$ terraform validate
[PASS] Configuration is valid.
```

## 5. 依赖图构建

### 5.1 隐式依赖规则

| 资源 A | 资源 B | 依赖关系 | 说明 |
|--------|--------|----------|------|
| ECS | VSwitch | A → B | ECS 必须部署在 VSwitch |
| ECS | SecurityGroup | A → B | ECS 需要安全组 |
| VSwitch | VPC | A → B | VSwitch 属于 VPC |
| RDS | VSwitch | A → B | RDS 需要 VSwitch |
| SLB | VSwitch | A → B | SLB 需要 VSwitch |
| SLB | ECS | A → B | SLB 后端挂载 ECS |
| NAT | VSwitch | A → B | NAT 绑定 VSwitch |

### 5.2 显式依赖声明

当隐式规则不足时，支持显式声明:

```json
{
  "explicit_dependencies": [
    {"from": "custom_ecs", "to": "custom_vpc", "reason": "业务逻辑依赖"}
  ]
}
```

### 5.3 拓扑排序算法

```python
def topological_sort(resources, dependencies):
    """
    Kahn's Algorithm
    确保依赖资源先于被依赖资源创建
    """
    in_degree = {r: 0 for r in resources}
    graph = {r: [] for r in resources}
    
    for dep in dependencies:
        graph[dep.from].append(dep.to)
        in_degree[dep.to] += 1
    
    queue = [r for r in resources if in_degree[r] == 0]
    result = []
    
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    if len(result) != len(resources):
        raise CycleDependencyError("检测到循环依赖")
    
    return result
```

## 6. 变量化抽象

### 6.1 抽象策略

识别应提取为变量的字段:

| 抽象级别 | 识别规则 | 示例 |
|----------|----------|------|
| **Environment** | 不同环境值不同 | 规格、数量、密码 |
| **Naming** | 可能需要自定义 | 资源名称、标签 |
| **Networking** | 网络规划相关 | CIDR、可用区 |
| **Optional** | 有合理默认值 | 磁盘大小、描述 |

### 6.2 变量生成规则

**原始属性**:
```hcl
resource "alicloud_instance" "web" {
  instance_type = "ecs.c6.large"
  image_id      = "centos_8"
  vswitch_id    = alicloud_vswitch.subnet.id
}
```

**变量化后**:
```hcl
# variables.tf
variable "ecs_instance_type" {
  description = "ECS 实例规格"
  type        = string
  default     = "ecs.c6.large"
}

variable "ecs_image_id" {
  description = "ECS 镜像 ID"
  type        = string
  default     = "centos_8"
}

# main.tf
resource "alicloud_instance" "web" {
  instance_type = var.ecs_instance_type
  image_id      = var.ecs_image_id
  vswitch_id    = alicloud_vswitch.subnet.id
}
```

### 6.3 环境覆盖策略

```hcl
# terraform.tfvars (dev)
ecs_instance_type = "ecs.t6-c1m1.large"
ecs_count         = 1

# terraform.tfvars (prod)
ecs_instance_type = "ecs.c6.xlarge"
ecs_count         = 4
```

## 7. 输出规范

### 7.1 文件结构

```
generated/
├── main.tf          # 资源定义
├── variables.tf     # 变量声明
├── outputs.tf       # 输出值
├── terraform.tfvars # 默认值（示例）
├── versions.tf      # Provider 版本约束
└── README.md        # 使用说明
```

### 7.2 main.tf 格式

```hcl
# generated/main.tf
# Generated from: "创建一个 VPC，两个交换机，3 台 ECS"
# Environment: dev
# Timestamp: 2024-06-08T10:30:00Z

terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.220"
    }
  }
}

provider "alicloud" {
  region = var.region
}

# VPC
resource "alicloud_vpc" "main" {
  cidr_block = var.vpc_cidr
  vpc_name   = "${var.project_name}-vpc"
  
  tags = merge(var.common_tags, {
    Component = "network"
  })
}

# VSwitch - 跨可用区
resource "alicloud_vswitch" "subnet" {
  count = var.az_count

  vpc_id       = alicloud_vpc.main.id
  cidr_block   = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  zone_id      = data.alicloud_zones.available.zones[count.index].id
  vswitch_name = "${var.project_name}-subnet-${count.index + 1}"
  
  tags = var.common_tags
}

# ECS
resource "alicloud_instance" "web" {
  count = var.ecs_count

  instance_name = "${var.project_name}-web-${count.index + 1}"
  instance_type = var.ecs_instance_type
  image_id      = var.ecs_image_id
  
  vswitch_id           = alicloud_vswitch.subnet[count.index % var.az_count].id
  security_groups      = [alicloud_security_group.web.id]
  system_disk_category = "cloud_efficiency"
  system_disk_size     = 40
  
  internet_max_bandwidth_out = var.enable_public_ip ? 10 : 0
  
  tags = merge(var.common_tags, {
    Component = "web"
  })
  
  depends_on = [alicloud_vswitch.subnet]
}

# Security Group
resource "alicloud_security_group" "web" {
  name   = "${var.project_name}-web-sg"
  vpc_id = alicloud_vpc.main.id
  
  tags = var.common_tags
}

resource "alicloud_security_group_rule" "allow_http" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "80/80"
  priority          = 1
  security_group_id = alicloud_security_group.web.id
  cidr_ip           = "0.0.0.0/0"
}

# Data Sources
data "alicloud_zones" "available" {
  available_disk_category     = "cloud_efficiency"
  available_resource_creation = "VSwitch"
}
```

### 7.3 variables.tf 格式

```hcl
# generated/variables.tf

variable "region" {
  description = "阿里云区域"
  type        = string
  default     = "cn-hangzhou"
}

variable "project_name" {
  description = "项目名称，用于资源命名"
  type        = string
  default     = "myapp"
}

variable "environment" {
  description = "环境标识"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["int", "dev", "uat", "performance", "production"], var.environment)
    error_message = "环境必须是 int, dev, uat, performance, production 之一"
  }
}

variable "vpc_cidr" {
  description = "VPC CIDR 网段"
  type        = string
  default     = "10.0.0.0/16"
  
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "必须是有效的 CIDR 格式"
  }
}

variable "az_count" {
  description = "可用区数量"
  type        = number
  default     = 2
}

variable "ecs_count" {
  description = "ECS 实例数量"
  type        = number
  default     = 2
}

variable "ecs_instance_type" {
  description = "ECS 实例规格"
  type        = string
  default     = "ecs.c6.large"
}

variable "ecs_image_id" {
  description = "ECS 镜像 ID"
  type        = string
  default     = "centos_8"
}

variable "enable_public_ip" {
  description = "是否分配公网 IP"
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "通用标签"
  type        = map(string)
  default = {
    ManagedBy = "terraform"
    Project   = "myapp"
  }
}
```

### 7.4 outputs.tf 格式

```hcl
# generated/outputs.tf

output "vpc_id" {
  description = "VPC ID"
  value       = alicloud_vpc.main.id
}

output "vswitch_ids" {
  description = "VSwitch ID 列表"
  value       = alicloud_vswitch.subnet[*].id
}

output "ecs_instance_ids" {
  description = "ECS 实例 ID 列表"
  value       = alicloud_instance.web[*].id
}

output "ecs_private_ips" {
  description = "ECS 内网 IP 列表"
  value       = alicloud_instance.web[*].private_ip
}

output "security_group_id" {
  description = "安全组 ID"
  value       = alicloud_security_group.web.id
}
```

## 8. Dry-Run 支持

### 8.1 Dry-Run 模式定义

| 模式 | 行为 | 输出 |
|------|------|------|
| **生成模式** (默认) | 仅生成 HCL 文件 | main.tf, variables.tf, outputs.tf |
| **验证模式** | 生成 + terraform validate | 验证报告 |
| **Dry-Run 模式** | 生成 + validate + plan | Plan 结果预览 |

### 8.2 Dry-Run 流程

```
用户: "生成一个 VPC 和 2 台 ECS 的配置，先 preview 一下"

Agent: [NL2HCL 生成中...]
       [PASS] 生成完成
       
       [Dry-Run 模式] 执行 terraform init...
       [PASS] 初始化完成
       
       [Dry-Run 模式] 执行 terraform plan...
       
═══════════════════════════════════════════════════
  Dry-Run 结果 (terraform plan)
═══════════════════════════════════════════════════

变更摘要:
  + 创建: 5 个资源
    - alicloud_vpc.main
    - alicloud_vswitch.subnet[0]
    - alicloud_vswitch.subnet[1]
    - alicloud_instance.web[0]
    - alicloud_instance.web[1]

预计费用:
  - VPC: 免费
  - ECS (ecs.c6.large × 2): ~¥ 1.2/小时
  - 公网流量: 按实际使用

风险检查:
  [PASS] 无资源销毁
  [PASS] 非生产环境
  [WARN] 将创建公网 IP (可能产生流量费)

详细变更: (可展开查看)
  
选项:
  [Y] 保存配置到文件
  [A] 直接执行 apply (需要确认)
  [M] 修改配置
  [N] 放弃

> Y
[保存中...]
输出目录: ./generated/vpc-ecs-20240608/
```

### 8.3 Dry-Run 在 HITL 中的使用

在 **CP3 Plan 确认** 阶段，dry-run 结果作为人工决策依据：

```yaml
hitl:
  checkpoints:
    cp3_plan:
      dry_run: true  # 强制 dry-run 后再确认
      show_cost: true  # 显示预估费用
      show_risk: true  # 显示风险提示
```

### 8.4 限制

Dry-Run 需要：
- 有效的阿里云凭证 (用于查询数据源)
- 有效的 backend 配置 (或本地临时 backend)
- 网络连通性 (查询可用区等数据)

若条件不满足，降级为仅 validate 模式。

## 9. 示例库

### 9.1 示例 1: 基础 Web 服务栈

**自然语言**: "创建一个 Web 服务栈，包含 VPC、2 台 ECS、1 个 SLB，ECS 要能访问公网"

**生成要点**:
- VPC + VSwitch (多可用区)
- ECS × 2 (带公网带宽)
- SLB (绑定 ECS)
- SecurityGroup (允许 HTTP/HTTPS)
- NAT Gateway (可选，ECS 出网)

### 9.2 示例 2: 数据库集群

**自然语言**: "创建一个高可用 RDS MySQL 集群，一主一从，部署在多可用区，只有应用服务器能访问"

**生成要点**:
- VPC + 2× VSwitch (不同可用区)
- RDS MySQL (主可用区 + 备可用区)
- SecurityGroup (限制内网访问)
- 应用服务器 SecurityGroup 授权

### 9.3 示例 3: 缓存加速

**自然语言**: "在现有架构上添加 Redis 缓存，与数据库同 VPC，只允许 ECS 访问"

**生成要点**:
- 引用现有 VPC (data source)
- Redis 实例 (云数据库版)
- SecurityGroup 规则 (限制 ECS IP 段)

### 9.4 示例 4: 对象存储

**自然语言**: "创建一个私有 OSS bucket，用于存储用户上传文件，需要通过 CDN 加速"

**生成要点**:
- OSS Bucket (私有读写)
- CDN Domain (加速域名)
- Referer 防盗链配置

### 9.5 示例 5: 完整微服务架构

**自然语言**: "搭建一个完整的微服务基础设施：VPC 跨 3 可用区，每区 2 台 ECS，共享 SLB，后端 RDS + Redis，ECS 能出网但外网不能直接访问"

**生成要点**:
- VPC / 3× VSwitch
- ECS × 6 (跨可用区分布)
- SLB (健康检查配置)
- RDS (高可用)
- Redis (主从)
- NAT Gateway (统一出网)
- SecurityGroup (分层访问控制)

## 10. 错误处理

### 10.1 解析失败类型

| 错误类型 | 原因 | 处理策略 |
|----------|------|----------|
| **UnknownResource** | 无法识别资源类型 | 提示用户确认术语，提供资源列表 |
| **AmbiguousIntent** | 意图不明确 | 询问澄清，提供选项 |
| **InvalidAttribute** | 属性值无效 | 提示有效值范围 |
| **CyclicDependency** | 循环依赖 | 报错，要求人工调整 |
| **QuotaExceeded** | 资源数量超限 | 提示配额限制，建议分批 |

### 10.2 歧义消解策略

**示例**: "创建一个大的 ECS"

歧义: "大的"可能指 CPU 多、内存大、还是磁盘大?

**处理**:
```
[歧义检测] "大的"规格不明确，请选择:
  [1] 高 CPU (ecs.c6.xlarge - 4核4G)
  [2] 高内存 (ecs.r6.xlarge - 2核16G)  
  [3] 均衡型 (ecs.g7.xlarge - 4核16G)
  [4] 自定义规格 > 
```

### 10.3 回退机制

当 LLM 解析不可靠时:
1. 使用规则引擎做初筛
2. 关键字段必须匹配资源映射表
3. 生成后强制 `terraform validate`
4. 失败时提供手动编辑入口

## 11. Prompt 工程模板

### 11.1 语义解析 Prompt

```
你是一位 Terraform 专家，负责将自然语言描述转换为结构化配置。

任务: 解析用户的基础设施需求，提取以下信息:
1. 意图类型 (create/extend/modify/destroy)
2. 资源实体列表 (类型、数量、属性)
3. 资源间关系 (依赖、包含、连接)

资源类型映射表:
- VPC / 专有网络 → vpc
- ECS / 云服务器 → ecs
- RDS / 数据库 → rds
- SLB / 负载均衡 → slb
- Redis / 缓存 → redis

输出格式必须是 JSON:
{
  "intent": "create",
  "entities": [...],
  "relations": [...]
}

用户输入: {{user_input}}
```

### 11.2 HCL 生成 Prompt

```
你是一位 Terraform HCL 代码生成专家。

根据以下结构化配置，生成符合最佳实践的 Terraform HCL 代码:

输入配置: {{structured_config}}

生成要求:
1. 使用 Terraform 1.5+ 语法
2. 所有可变参数提取为 variables
3. 添加必要的 data sources (如可用区查询)
4. 包含标准标签 (Environment, ManagedBy, Project)
5. 敏感数据标记为 sensitive
6. 添加适当的 lifecycle 规则
7. 代码注释说明资源用途

输出格式:
- main.tf: 资源定义
- variables.tf: 变量声明
- outputs.tf: 输出值
```

## 12. 性能优化

### 12.1 缓存策略

| 缓存项 | 有效期 | 说明 |
|--------|--------|------|
| 资源映射表 | 长期 | 术语到 TF 资源的映射 |
| 可用区数据 | 1小时 | 阿里云可用区列表 |
| 规格族信息 | 24小时 | ECS/RDS 规格列表 |
| 生成模板 | 长期 | 常见架构模式模板 |

### 12.2 增量生成

支持对现有配置的增量修改:
```
用户: "给现有 VPC 再添加一个交换机"
→ 读取现有 main.tf
→ 仅生成新增资源
→ 保持已有格式和变量
```

---

*该规范用于驱动 alicloud-terraform-ops Skill 的 NL2HCL 功能实现。*

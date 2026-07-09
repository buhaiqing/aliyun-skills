# Reverse Engineering - 现有资源逆向导入

从现有阿里云资源逆向生成 Terraform 配置的完整规范，实现存量资源纳管。

## 1. 概述

### 1.1 功能定位

| 维度 | 说明 |
|------|------|
| **输入** | 现有阿里云资源（ID/标签/资源组） |
| **输出** | Terraform 配置 + Import 脚本 + 状态管理 |
| **核心能力** | 资源发现 → 属性映射 → HCL 生成 → 导入执行 |
| **约束** | 仅导入支持的资源类型，敏感数据需人工确认 |

### 1.2 适用场景

| 场景 | 描述 | 示例 |
|------|------|------|
| **存量纳管** | 已有资源纳入 Terraform 管理 | 控制台创建的资源转 IaC |
| **架构复制** | 复制现有架构到新环境 | 生产环境架构复制到测试 |
| **灾备重建** | 基于现有资源生成可重建配置 | 灾难恢复预案 |
| **配置审计** | 生成配置与现有状态比对 | 漂移检测 |

### 1.3 架构分层

```
┌─────────────────────────────────────────┐
│  Input: 资源标识                          │
│  - 资源 ID 列表                            │
│  - 标签过滤                               │
│  - VPC/资源组范围                          │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 1: 资源发现层 (Discovery)           │
│  - 主资源查询 (通过 CLI/SDK)               │
│  - 关联资源探测 (自动发现依赖)              │
│  - 资源图谱构建                            │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 2: 属性采集层 (Attribute Collector) │
│  - API 响应解析                           │
│  - 敏感数据识别 (密码/密钥)                │
│  - 默认值剔除                             │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 3: 属性映射层 (Attribute Mapping)   │
│  - API 字段 → TF Schema 映射               │
│  - 引用关系转换 (ID → TF Resource Ref)     │
│  - 计算属性处理 (只读字段)                  │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 4: HCL 生成层 (HCL Generator)       │
│  - 资源块生成                             │
│  - Import 块/脚本生成                      │
│  - Lifecycle 规则注入 (ignore_changes)     │
└────────────┬────────────────────────────┘
             ▼
┌─────────────────────────────────────────┐
│  Layer 5: 导入执行层 (Import Executor)     │
│  - terraform import 执行                 │
│  - State 验证                             │
│  - Drift 检测                             │
└─────────────────────────────────────────┘
```

## 2. 资源发现

### 2.1 发现策略

| 策略 | 输入 | 说明 | 示例 |
|------|------|------|------|
| **ID 精确匹配** | 资源 ID 列表 | 直接查询指定资源 | `i-bp1xxxxxx,vpc-bp1yyyyy` |
| **标签过滤** | Key=Value | 查询带指定标签的资源 | `Environment=production` |
| **资源组** | 资源组 ID | 查询资源组内所有资源 | `rg-acfmxwv5xxxxxx` |
| **VPC 范围** | VPC ID | 查询 VPC 内所有资源 | `vpc-bp1xxxxxx` |
| **级联发现** | 主资源 | 自动发现关联资源 | ECS → 磁盘/网卡/安全组 |

### 2.2 支持资源类型

#### P0 核心资源（优先支持）

| 资源类型 | CLI 查询命令 | Terraform 资源 | 关联资源 |
|----------|-------------|----------------|----------|
| ECS | `aliyun ecs DescribeInstances` | `alicloud_instance` | Disk, ENI, SG |
| VPC | `aliyun vpc DescribeVpcs` | `alicloud_vpc` | VSwitch, RouteTable |
| VSwitch | `aliyun vpc DescribeVSwitches` | `alicloud_vswitch` | - |
| SecurityGroup | `aliyun ecs DescribeSecurityGroups` | `alicloud_security_group` | SecurityGroupRule |
| SLB | `aliyun slb DescribeLoadBalancers` | `alicloud_slb_load_balancer` | Listener, BackendServer |
| RDS | `aliyun rds DescribeDBInstances` | `alicloud_db_instance` | Account, Database |
| Redis | `aliyun r-kvstore DescribeInstances` | `alicloud_kvstore_instance` | - |
| OSS | `aliyun oss ls` | `alicloud_oss_bucket` | - |

#### P1 扩展资源

| 资源类型 | CLI 查询命令 | Terraform 资源 | 说明 |
|----------|-------------|----------------|------|
| NAT Gateway | `aliyun vpc DescribeNatGateways` | `alicloud_nat_gateway` | 含 SNAT/DNAT 规则 |
| EIP | `aliyun vpc DescribeEipAddresses` | `alicloud_eip` | 绑定关系 |
| AutoScaling | `aliyun ess DescribeScalingGroups` | `alicloud_ess_scaling_group` | 含配置规则 |
| RAM Role | `aliyun ram ListRoles` | `alicloud_ram_role` | 权限策略 |

### 2.3 关联资源探测规则

```yaml
# 关联探测规则
association_rules:
  alicloud_instance:
    - source_field: "Disks.Disk"
      target_type: "alicloud_disk"
      target_id_field: "DiskId"
      
    - source_field: "NetworkInterfaces.NetworkInterface"
      target_type: "alicloud_network_interface"
      target_id_field: "NetworkInterfaceId"
      
    - source_field: "SecurityGroupIds.SecurityGroupId"
      target_type: "alicloud_security_group"
      target_id_field: "SecurityGroupId"
      
    - source_field: "VpcAttributes.VSwitchId"
      target_type: "alicloud_vswitch"
      target_id_field: "VSwitchId"
      
  alicloud_vpc:
    - source_field: "VSwitches.VSwitch"
      target_type: "alicloud_vswitch"
      target_id_field: "VSwitchId"
      
    - source_field: "RouteTables.RouteTable"
      target_type: "alicloud_route_table"
      target_id_field: "RouteTableId"
      
  alicloud_slb_load_balancer:
    - source_field: "BackendServers.BackendServer"
      target_type: "alicloud_instance"
      target_id_field: "ServerId"
      # 注：BackendServer 可能是 ECS 或 ENI
```

### 2.4 发现流程示例

**输入**: `vpc-bp1xxxxxx`

```
Step 1: 查询 VPC
  └─ aliyun vpc DescribeVpcs --VpcId vpc-bp1xxxxxx
     └─ 获取 VPC 基础信息

Step 2: 探测关联资源
  ├─ 查询 VSwitch (VPC 包含)
  │   └─ vswitch-1, vswitch-2
  │
  ├─ 查询 RouteTable
  │   └─ vtb-1 (主路由表)
  │
  └─ 查询 SecurityGroup (归属 VPC)
      └─ sg-1, sg-2

Step 3: 级联探测
  ├─ VSwitch vswitch-1
  │   └─ 查询 ECS (在该交换机)
  │       └─ i-1, i-2
  │
  └─ VSwitch vswitch-2
      └─ 查询 ECS
          └─ i-3

Step 4: ECS 关联资源
  ├─ i-1
  │   ├─ Disk: d-1, d-2
  │   ├─ ENI: eni-1
  │   └─ SG: sg-1 (已发现)
  │
  ├─ i-2
  │   └─ ...
  └─ i-3
      └─ ...

Step 5: 去重与排序
  └─ 生成资源图谱
```

## 3. 属性映射

### 3.1 映射规则

#### ECS 属性映射

| API 字段路径 | Terraform 属性 | 处理方式 | 说明 |
|-------------|----------------|----------|------|
| `InstanceId` | `id` | 只读，用于 import | 资源标识 |
| `InstanceName` | `instance_name` | 直接映射 | 实例名称 |
| `InstanceType` | `instance_type` | 直接映射 | 规格 |
| `ImageId` | `image_id` | 直接映射 | 镜像 |
| `VpcAttributes.VSwitchId` | `vswitch_id` | 引用转换 | TF 引用 |
| `SecurityGroupIds[]` | `security_groups` | 数组映射 | 安全组列表 |
| `InternetChargeType` | `internet_charge_type` | 直接映射 | 计费方式 |
| `InternetMaxBandwidthOut` | `internet_max_bandwidth_out` | 直接映射 | 带宽 |
| `SystemDisk.DiskSize` | `system_disk_size` | 直接映射 | 系统盘大小 |
| `SystemDisk.DiskCategory` | `system_disk_category` | 直接映射 | 系统盘类型 |
| `Password` | `password` | **敏感，标记为变量** | 不导出值 |
| `KeyPairName` | `key_name` | 直接映射 | 密钥对 |
| `UserData` | `user_data` | Base64 解码后映射 | 启动脚本 |
| `ZoneId` | `availability_zone` | 直接映射 | 可用区 |
| `Tags.Tag[]` | `tags` | Map 转换 | 标签 |

#### VPC 属性映射

| API 字段路径 | Terraform 属性 | 处理方式 |
|-------------|----------------|----------|
| `VpcId` | `id` | 只读 |
| `VpcName` | `vpc_name` | 直接映射 |
| `CidrBlock` | `cidr_block` | 直接映射 |
| `Description` | `description` | 直接映射 |
| `IsDefault` | `is_default` | 只读，忽略 |
| `Tags.Tag[]` | `tags` | Map 转换 |

### 3.2 引用关系转换

**问题**: API 返回的是资源 ID，但 Terraform 需要资源引用。

**方案**:
```hcl
# 原始 API 数据
{
  "VSwitchId": "vsw-bp1xxxxxx",
  "SecurityGroupIds": ["sg-bp1xxxxxx", "sg-bp1yyyyyy"]
}

# 转换为 TF 引用
resource "alicloud_instance" "imported" {
  vswitch_id = alicloud_vswitch.imported_vsw.id
  security_groups = [
    alicloud_security_group.imported_sg_1.id,
    alicloud_security_group.imported_sg_2.id
  ]
}
```

**转换规则**:
1. 如果关联资源也在导入列表 → 使用 TF 引用
2. 如果关联资源不在列表 → 使用 Data Source 查询
3. 如果无法确定 → 标记为变量，需人工填写

### 3.3 计算属性处理

| 属性类型 | 处理方式 | 示例 |
|----------|----------|------|
| **只读属性** | 不写入 HCL，仅用于 import | `id`, `create_time` |
| **计算属性** | 使用 `lifecycle { ignore_changes }` | `public_ip` (可能变更) |
| **敏感属性** | 提取为敏感变量 | `password` |
| **复杂结构** | 使用 `dynamic` 块或单独资源 | `data_disks` |

### 3.4 敏感数据处理

```yaml
sensitive_fields:
  alicloud_instance:
    - password
    - user_data  # 可能含敏感脚本
    
  alicloud_db_instance:
    - account_password
    
  alicloud_ram_role:
    - assume_role_policy

handling_strategy:
  - 不导出实际值到 HCL
  - 生成敏感变量声明
  - 标记 `sensitive = true`
  - 提示用户后续设置
```

## 4. 分级导入策略

### 4.1 资源分级

| 分级 | 标识 | 条件 | 人工介入 |
|------|------|------|----------|
| **PASS** | [PASS] | 标准资源，完全支持 | 可自动导入 |
| **WARN** | [WARN] | 支持但有注意事项 | 需确认后导入 |
| **SKIP** | [SKIP] | 不支持或风险过高 | 跳过，需手工处理 |

### 4.2 分级规则

#### PASS 条件
- 资源类型在支持列表
- 所有必需属性可获取
- 无敏感数据或敏感数据可脱敏
- 关联资源可解析

#### WARN 条件
- 资源配置复杂（如 SLB 大量监听规则）
- 包含可能变更的属性（如公网 IP）
- 关联资源不在导入范围内
- 使用了已废弃的规格/镜像
- 存在自定义脚本（UserData）

#### SKIP 条件
- 资源类型不支持
- 使用了 Terraform 无法管理的特殊配置
- 资源处于异常状态
- 包含无法脱敏的敏感数据
- 依赖外部未纳管资源且无法替代

### 4.3 CheckPoint 集成

```yaml
# checkpoint 状态
checkpoint_status:
  phase: "review"  # discover / classify / select / generate / import / done
  
  resources:
    pass:
      - id: "i-bp1xxxxxx"
        type: "alicloud_instance"
        selected: true
        
    warn:
      - id: "lb-bp1xxxxxx"
        type: "alicloud_slb_load_balancer"
        reason: "复杂监听规则 (7 条)"
        selected: false  # 待用户确认
        
    skip:
      - id: "img-bp1xxxxxx"
        type: "custom_image"
        reason: "不支持导入"
```

## 5. 生成流程

### 5.1 五步流程

```
Step 1: 资源发现 (Discovery)
   └─ 输入: 资源标识
   └─ 输出: 资源列表 + 关联图谱
   └─ 工具: aliyun CLI + 关联规则引擎

Step 2: 属性采集 (Collection)
   └─ 输入: 资源列表
   └─ 输出: 完整资源属性 (API 原始数据)
   └─ 操作: 批量 API 查询，敏感数据标记

Step 3: 资源分级 (Classification)
   └─ 输入: 资源属性
   └─ 输出: PASS/WARN/SKIP 分级 + 原因
   └─ 规则: 分级规则引擎

Step 4: HCL 生成 (Generation)
   └─ 输入: 分级后的资源
   └─ 输出: main.tf + import.tf + import.sh
   └─ 操作: 属性映射，引用转换，lifecycle 注入

Step 5: 验证与 Dry-Run (Verification)
   └─ 输入: HCL + import 脚本
   └─ 操作: terraform init → validate → plan (dry-run)
   └─ 输出: 漂移检测报告
   └─ 目的: 验证配置正确性，不修改实际资源

Step 6: 导入执行 (Execution)
   └─ 输入: 验证通过的 HCL
   └─ 输出: terraform state
   └─ 操作: terraform import / apply
   └─ 验证: terraform plan 无漂移
```

### 5.2 输出文件结构

```
import-<vpc-id>-20240608/
├── main.tf              # 生成的 HCL 配置
├── import.tf            # terraform import 块 (1.5+)
├── import.sh            # 传统 import 脚本
├── variables.tf         # 敏感变量定义
├── generated/           # 原始生成文件
│   ├── ecs-
│   ├── vpc-
│   └── ...
├── checkpoint.json      # 检查点状态
├── report.md            # 导入报告
└── README.md            # 使用说明
```

### 5.3 import.tf 格式（Terraform 1.5+）

```hcl
# import.tf
# Generated by reverse-engineering
# Timestamp: 2024-06-08T10:30:00Z

import {
  to = alicloud_vpc.imported_vpc
  id = "vpc-bp1xxxxxx"
}

import {
  to = alicloud_vswitch.imported_vswitch_1
  id = "vsw-bp1xxxxxx"
}

import {
  to = alicloud_instance.imported_ecs_1
  id = "i-bp1xxxxxx"
}

# ... 更多 import 块
```

### 5.4 import.sh 格式（兼容旧版本）

```bash
#!/bin/bash
# import.sh
# Generated by reverse-engineering
# Timestamp: 2024-06-08T10:30:00Z

set -e

echo "[INFO] 开始导入资源..."

# VPC
echo "[INFO] 导入 VPC..."
terraform import alicloud_vpc.imported_vpc vpc-bp1xxxxxx

# VSwitch
echo "[INFO] 导入 VSwitch..."
terraform import alicloud_vswitch.imported_vswitch_1 vsw-bp1xxxxxx
terraform import alicloud_vswitch.imported_vswitch_2 vsw-bp1yyyyyy

# ECS
echo "[INFO] 导入 ECS..."
terraform import alicloud_instance.imported_ecs_1 i-bp1xxxxxx

# ...

echo "[PASS] 导入完成"
echo "[INFO] 运行 'terraform plan' 验证配置..."
terraform plan
```

### 5.5 main.tf 生成示例

```hcl
# main.tf
# Generated from VPC: vpc-bp1xxxxxx
# Resources: 1 VPC, 2 VSwitches, 3 ECS

# VPC
resource "alicloud_vpc" "imported_vpc" {
  vpc_name   = "production-vpc"
  cidr_block = "10.0.0.0/16"
  
  tags = {
    Environment = "production"
    ManagedBy   = "terraform-imported"
  }
  
  # 忽略由系统自动维护的字段
  lifecycle {
    ignore_changes = [
      is_default,
      resource_group_id
    ]
  }
}

# VSwitch
resource "alicloud_vswitch" "imported_vswitch_1" {
  vswitch_name = "subnet-app-1"
  vpc_id       = alicloud_vpc.imported_vpc.id
  cidr_block   = "10.0.1.0/24"
  zone_id      = "cn-hangzhou-b"
  
  lifecycle {
    ignore_changes = [
      available_ip_address_count
    ]
  }
}

resource "alicloud_vswitch" "imported_vswitch_2" {
  vswitch_name = "subnet-app-2"
  vpc_id       = alicloud_vpc.imported_vpc.id
  cidr_block   = "10.0.2.0/24"
  zone_id      = "cn-hangzhou-g"
  
  lifecycle {
    ignore_changes = [
      available_ip_address_count
    ]
  }
}

# ECS
resource "alicloud_instance" "imported_ecs_1" {
  instance_name = "web-server-1"
  instance_type = "ecs.c6.large"
  image_id      = "centos_8_5_x64_20G_alibase_20220322.vhd"
  
  vswitch_id           = alicloud_vswitch.imported_vswitch_1.id
  security_groups      = [alicloud_security_group.imported_sg.id]
  system_disk_category = "cloud_efficiency"
  system_disk_size     = 40
  
  # 敏感数据使用变量
  password = var.ecs_initial_password
  
  internet_max_bandwidth_out = 10
  
  tags = {
    Role = "web"
  }
  
  lifecycle {
    ignore_changes = [
      public_ip,           # 可能变更
      system_disk_snapshot # 自动维护
    ]
  }
}

# ... 更多资源
```

## 6. 与 HITL 集成

### 6.1 CheckPoint 模式工作流

```
User: "导入这个 VPC 的所有资源: vpc-bp1xxxxxx"

Agent: [发现中...]
       [PASS] 发现 12 个资源
       
═══════════════════════════════════════════════════
  资源分级结果 (CheckPoint: review)
═══════════════════════════════════════════════════

[PASS] 可自动导入 (8个):
  [x] VPC vpc-bp1xxxxxx
  [x] VSwitch vsw-bp1aaaa (可用区 B)
  [x] VSwitch vsw-bp1bbbb (可用区 G)
  [x] ECS i-bp1xxxxxx (Web服务器)
  [x] ECS i-bp1yyyyyy (Web服务器)
  [x] Disk d-bp1xxxxxx (数据盘)
  [x] Disk d-bp1yyyyyy (数据盘)
  [x] SecurityGroup sg-bp1xxxxxx

[WARN] 需要确认 (3个):
  [ ] SLB lb-bp1xxxxxx
      └─ 原因: 监听规则复杂 (7 条)，可能含业务逻辑
      
  [ ] RDS rm-bp1xxxxxx
      └─ 原因: 白名单包含敏感 IP (10.0.x.x)
      
  [ ] NAT Gateway nat-bp1xxxxxx
      └─ 原因: SNAT 表项较多 (20+ 条)

[SKIP] 不支持 (1个):
  [ ] Custom Image img-bp1xxxxxx
      └─ 原因: 自定义镜像不支持 Terraform 导入

请选择:
  [1] 导入全部 [PASS] (8个)
  [2] 逐一审核 [WARN] (3个)
  [3] 自定义选择
  [4] 干运行 (dry-run)
  [5] 保存并退出 (稍后继续)

> 2

═══════════════════════════════════════════════════
  审核: SLB lb-bp1xxxxxx
═══════════════════════════════════════════════════

配置摘要:
  - 监听: 80→8080, 443→8443, 8080→8080
  - 证书: 已绑定 (2024-12-31 到期)
  - 后端: 2 台 ECS (已选择导入)
  - 转发规则: 7 条 (域名/路径匹配)

警告: 发现复杂转发规则，可能包含业务逻辑
      导入后建议人工验证规则完整性

选项:
  [I]  导入 (完整配置)
  [M]  导入并标记为维护模式 (ignore_changes)
  [S]  跳过，后续手动配置
  [V]  查看完整规则

> M

[标记] 添加 lifecycle { ignore_changes = [listener] }

[继续审核下一个 WARN 资源...]

═══════════════════════════════════════════════════
  最终确认
═══════════════════════════════════════════════════

导入清单:
  [PASS] 8个 (全部)
  [WARN] 3个 (2个导入，1个跳过)
  [SKIP] 1个

总计: 11 个资源将被导入

确认生成配置并导入? [Y/save-exit/N]

> Y

[生成中...]
  ✓ main.tf
  ✓ import.tf
  ✓ import.sh
  ✓ variables.tf
  
[执行 terraform init...]
[PASS]

[执行 terraform plan...]
[PASS] 无漂移，配置匹配

[执行 terraform apply...]
[PASS] 11 个资源导入成功

[清理检查点]
[PASS] 完成
```

### 6.2 会话恢复

```bash
# 用户之前选择了 [5] 保存并退出
$ pi "继续上次的导入任务"

[发现检查点] checkpoint-20240608-vpc-import.json
[创建时间] 2024-06-08 10:30 (30分钟前)
[当前状态] 已审核 2/3 个 WARN 资源，等待最终确认

恢复上下文:
  - VPC: vpc-bp1xxxxxx
  - 已选择: 10 个资源导入
  - 剩余: 1 个 WARN 资源待审核

选项:
  [1] 继续审核剩余资源
  [2] 跳过剩余，直接确认当前选择
  [3] 重新从头开始
  [4] 删除检查点

> 1

[恢复会话，继续审核...]
```

## 7. Dry-Run 支持

### 7.1 Dry-Run 模式定义

| 模式 | 行为 | 是否修改 State | 适用场景 |
|------|------|---------------|----------|
| **生成模式** (默认) | 仅生成 HCL + import 脚本 | 否 | 配置审核 |
| **Dry-Run 模式** | 生成 + init + validate + plan | 否 | 验证配置正确性 |
| **导入模式** | 完整流程 + terraform import | **是** | 实际纳管 |

### 7.2 Dry-Run 流程 (Reverse Engineering)

```
用户: "导入这个 VPC 的所有资源，先 dry-run 验证"

Agent: [资源发现中...]
       [PASS] 发现 12 个资源
       [分级] [PASS] 8, [WARN] 3, [SKIP] 1

═══════════════════════════════════════════════════
  Dry-Run: 生成配置并验证
═══════════════════════════════════════════════════

[Step 1] 生成 HCL 配置
  ✓ main.tf (8 个资源)
  ✓ import.tf
  ✓ variables.tf

[Step 2] terraform init
  ✓ 初始化完成 (本地 backend)

[Step 3] terraform validate
  ✓ 语法验证通过
  ✓ 变量引用检查通过

[Step 4] terraform plan (模拟)
  ─────────────────────────────────────────────────
  注意: 当前为 Dry-Run，未实际导入
  
  预计变更:
    + 创建: 0 (导入不会创建新资源)
    ~ 修改: 0
    - 销毁: 0
    
  漂移检测:
    [INFO] 8 个 [PASS] 资源可正常导入
    [WARN] 3 个 [WARN] 资源可能存在漂移:
      - SLB lb-bp1xxx: 监听规则需人工核对
      - RDS rm-bp1xxx: 白名单 IP 建议变量化
      - NAT nat-bp1xxx: SNAT 条目较多
    
  建议操作:
    1. 查看 generated/ 目录下的 HCL 配置
    2. 对 [WARN] 资源人工审核
    3. 确认无误后执行实际导入

═══════════════════════════════════════════════════

选项:
  [1] 查看详细 drift 报告
  [2] 导出配置，稍后手动导入
  [3] 进入 HITL 审核流程 ([WARN] 资源)
  [4] 直接执行实际导入 (需要再次确认)
  [5] 放弃

> 3
```

### 7.3 Dry-Run 的价值

| 验证项 | Dry-Run 检查 | 意义 |
|--------|-------------|------|
| **语法正确性** | terraform validate | 确保生成代码无语法错误 |
| **引用完整性** | terraform plan | 确保资源间引用关系正确 |
| **漂移预警** | 配置 vs 实际比对 | 提前发现不支持的属性 |
| **敏感数据** | 变量化检查 | 确保密码等未硬编码 |
| **成本影响** | 资源清单 | 确认无意外创建/删除 |

### 7.4 Dry-Run 与 HITL 集成

在 **CheckPoint 模式 C** 中，dry-run 是必经步骤：

```yaml
hitl:
  mode: "checkpoint"
  
  checkpoint:
    phases:
      - discover      # 资源发现
      - classify      # 分级标记
      - select        # 用户选择
      - generate      # HCL 生成
      - dry_run:      # 新增: dry-run 验证
          required: true
          show_drift: true
          show_cost: false  # 导入不产生新费用
      - review        # 人工审核
      - import        # 实际导入
```

### 7.5 限制

Reverse Engineering 的 Dry-Run 有特定限制：

1. **无法 100% 验证**: 某些属性只有在实际 import 后才能确定
2. **依赖外部资源**: 如果引用的资源不在导入列表，plan 可能报错
3. **Provider 限制**: 部分资源的 `terraform plan` 需要实际 state 才能完整验证

**建议**: Dry-Run 通过后，先导入单个资源验证，再批量导入。

## 8. 验证与漂移检测

### 8.1 导入后验证

```bash
# 1. 验证 state 正确性
terraform state list
terraform state show alicloud_vpc.imported_vpc

# 2. 检测漂移
terraform plan
# 期望输出: No changes. Your infrastructure matches the configuration.

# 3. 属性比对（工具脚本）
./scripts/verify-import.sh
# 输出: [PASS] 所有导入资源属性匹配
```

### 8.2 常见漂移处理

| 漂移类型 | 原因 | 处理 |
|----------|------|------|
| `public_ip` 变更 | 公网 IP 动态分配 | 添加 ignore_changes |
| `system_disk_snapshot` | 自动快照策略 | 添加 ignore_changes |
| `available_ip_address_count` | VSwitch 可用 IP 变化 | 添加 ignore_changes |
| `security_group_rule` 缺失 | 规则单独管理 | 拆分独立资源 |

## 9. 示例场景

### 9.1 场景 1: 单 ECS 导入

**输入**: `i-bp1xxxxxx`

**输出**:
- main.tf: ECS + 关联 Disk + SecurityGroup
- import.sh: 3 个 import 命令
- 分级: [PASS]

### 9.2 场景 2: VPC 完整架构

**输入**: `vpc-bp1xxxxxx` (含 2 VSwitch, 3 ECS, 1 SLB, 1 RDS)

**输出**:
- 资源图谱
- 分级: [PASS] 10, [WARN] 2 (SLB, RDS), [SKIP] 1 (Custom Image)
- 完整 Terraform 模块

### 9.3 场景 3: 标签批量导入

**输入**: `tag:Project=legacy,Environment=production`

**输出**:
- 跨 VPC 的所有带标签资源
- 资源清单报表
- 分批导入建议（按依赖关系分组）

## 10. 限制与注意事项

### 10.1 已知限制

| 限制 | 说明 |  workaround |
|------|------|-------------|
| 自定义镜像 | 不支持 Terraform 导入 | 手动注册为官方镜像后使用 |
| 部分高级配置 | 某些 SLB 高级特性不支持 | 使用 ignore_changes |
| 历史状态 | 无法还原创建历史 | 仅导入当前状态 |
| 依赖外部资源 | 引用的外部资源需手工处理 | Data Source 或变量 |

### 10.2 安全警告

- ⚠️ 导入前务必创建阿里云资源快照/备份
- ⚠️ 敏感数据（密码）不会导出，需后续配置
- ⚠️ 导入后先执行 `terraform plan` 验证无漂移再 `apply`

---

*该规范用于驱动 alicloud-terraform-ops Skill 的 Reverse Engineering 功能实现。*

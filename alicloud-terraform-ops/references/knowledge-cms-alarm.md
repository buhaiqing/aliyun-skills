# Knowledge: 阿里云云监控（CMS）告警体系

> **范围**: Terraform IaC 管理云监控告警规则、联系人、通知渠道
> **模块**: `addon-cms-alarm`
> **适用角色**: 运维工程师、SRE、DevOps

---

## 1. 概念速查

### 1.1 云监控核心概念

```
┌─────────────────────────────────────────────────────────────┐
│                    阿里云云监控 (CMS)                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │  告警规则   │   │  联系人组   │   │   通知渠道   │      │
│  │ Alarm Rule  │   │   Contact   │   │ Notification│      │
│  │             │   │    Group    │   │             │      │
│  │ - 指标      │   │ - 邮件     │   │ - 钉钉     │      │
│  │ - 阈值      │   │ - 短信     │   │ - 飞书     │      │
│  │ - 周期      │   │ - 回调     │   │ - 企业微信  │      │
│  └──────┬──────┘   └──────┬──────┘   │ - 邮件     │      │
│         │                  │          │ - 短信     │      │
│         └──────────────────┼──────────┴─────────────┘      │
│                            │                                 │
│                            ▼                                 │
│                   ┌─────────────────┐                       │
│                   │   触发通知      │                       │
│                   └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 术语对照

| 中文 | English | 说明 |
|------|---------|------|
| 告警规则 | Alarm Rule | 触发条件定义 |
| 联系人组 | Contact Group | 告警通知对象组 |
| 指标 | Metric | 监控数据项 |
| 阈值 | Threshold | 触发告警的数值 |
| 静默 | Silence/Mute | 抑制告警通知 |
| 升级 | Escalation | 告警未响应时升级 |

---

## 2. 告警规则详解

### 2.1 告警规则结构

```hcl
resource "alicloud_cms_alarm" "example" {
  name           = "cpu-high-alarm"
  project        = "acs_ecs"           # 监控项目
  metric         = "cpu_total"          # 指标名
  dimensions     = jsonencode({          # 监控维度
    instanceId = "i-xxxxx"
  })
  period        = 300                   # 采样周期(秒)
  threshold     = 80                     # 阈值
  statistics    = "Average"             # 统计方法
  interval      = 900                   # 告警间隔(秒)
  alarm_actions = [contact_group_id]    # 告警触发动作
  ok_actions    = [contact_group_id]    # 恢复触发动作
}
```

### 2.2 常用指标速查

#### ECS 指标

| 指标名 | 说明 | 单位 | 典型阈值 |
|--------|------|------|----------|
| `cpu_total` | CPU 使用率 | % | 80 |
| `memory_usedutilization` | 内存使用率 | % | 85 |
| `diskusage_utilization` | 磁盘使用率 | % | 85 |
| `BpsRead` | 磁盘读取速率 | Bps | - |
| `BpsWrite` | 磁盘写入速率 | Bps | - |
| `net_in_rate` | 网络入带宽 | bps | - |
| `net_out_rate` | 网络出带宽 | bps | - |

#### SLB 指标

| 指标名 | 说明 | 单位 | 典型阈值 |
|--------|------|------|----------|
| `SlbHttpCode_5xx` | 5xx 错误率 | % | 5 |
| `SlbHttpCode_4xx` | 4xx 错误率 | % | 20 |
| `TrafficRxNew` | 入流量 | bps | - |
| `TrafficTxNew` | 出流量 | bps | - |
| `HeathyServerCount` | 活跃后端数 | 数量 | ≥1 |

#### RDS 指标

| 指标名 | 说明 | 单位 | 典型阈值 |
|--------|------|------|----------|
| `CpuUsage` | CPU 使用率 | % | 80 |
| `DiskUsage` | 磁盘使用率 | % | 85 |
| `MemoryUsage` | 内存使用率 | % | 85 |
| `QPS` | 每秒查询数 | count | 10000 |
| `ConnectionUsage` | 连接数使用率 | % | 80 |

#### Redis 指标

| 指标名 | 说明 | 单位 | 典型阈值 |
|--------|------|------|----------|
| `MemoryUsage` | 内存使用率 | % | 85 |
| `QPS` | 每秒操作数 | count | 10000 |
| `ConnectionsUsage` | 连接数使用率 | % | 80 |
| `InvokedFrequency` | 调用频率 | count | - |

### 2.3 统计方法

| 方法 | 说明 | 适用场景 |
|------|------|----------|
| `Average` | 平均值 | CPU、内存等持续性指标 |
| `Minimum` | 最小值 | 可用性类指标 |
| `Maximum` | 最大值 | 峰值类指标 |
| `SampleCount` | 采样数 | 计数类指标 |

### 2.4 采样周期

| 周期 | 说明 | 支持指标 |
|------|------|----------|
| 60s | 1分钟 | 云产品监控 |
| 300s | 5分钟 | 云产品监控（默认） |
| 900s | 15分钟 | 云产品监控 |
| 3600s | 1小时 | 自定义监控 |

---

## 3. 联系人组详解

### 3.1 联系人组结构

```hcl
resource "alicloud_cms_contact_group" "main" {
  name                        = "production-alarm-contact"
  description                = "生产环境告警联系人组"
  contact_lists              = ["user1@example.com"]
  
  # 邮件通知触发器
  # 短信通知触发器
  dynamic "sms_notify_triggers" {
    for_each = toset(var.sms_contacts)
    content {
      name = sms_notify_triggers.value
    }
  }
}
```

### 3.2 通知方式

| 方式 | 配置变量 | 触发 |
|------|----------|------|
| 邮件 | `email_contacts` | 告警/恢复 |
| 短信 | `sms_contacts` | 告警/恢复 |
| 钉钉 | `dingtalk_webhook` | 告警/恢复 |
| 飞书 | `feishu_webhook` | 告警/恢复 |
| 企业微信 | `wecom_webhook` | 告警/恢复 |
| 电话 | 需控制台开通 | - |

### 3.3 钉钉 Webhook

```hcl
resource "alicloud_cms_alarm" "example" {
  # ...
  dynamic "webhook" {
    for_each = var.dingtalk_webhook != "" ? [1] : []
    content {
      url = var.dingtalk_webhook
    }
  }
}
```

**钉钉机器人配置**:
1. 群设置 → 智能群助手 → 添加机器人
2. 选择「自定义」机器人
3. 安全设置选择「加签」或「关键词」
4. 复制 Webhook URL

### 3.4 飞书 (Feishu/Lark) Webhook

```hcl
# Terraform 配置
resource "alicloud_cms_alarm" "example" {
  # ...
  dynamic "webhook" {
    for_each = var.feishu_webhook != "" ? [1] : []
    content {
      url = var.feishu_webhook
    }
  }
}
```

**飞书机器人配置**:
1. 打开飞书群 → 设置 → 群机器人
2. 点击「添加机器人」→ 选择「自定义机器人」
3. 设置机器人名称和安全设置（可选：关键词/签名）
4. 复制 Webhook URL

**飞书 Webhook URL 格式**:
```
https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 3.5 企业微信 (WeCom) Webhook

```hcl
# Terraform 配置
resource "alicloud_cms_alarm" "example" {
  # ...
  dynamic "webhook" {
    for_each = var.wecom_webhook != "" ? [1] : []
    content {
      url = var.wecom_webhook
    }
  }
}
```

**企业微信机器人配置**:
1. 打开企业微信群 → 添加群机器人
2. 点击「添加机器人」→ 选择「自定义机器人」
3. 设置机器人名称和安全设置（可选）
4. 复制 Webhook URL

**企业微信 Webhook URL 格式**:
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 3.6 多渠道通知配置示例

```hcl
module "cms_alarm" {
  source = "../../modules/addon-cms-alarm"

  environment = "production"
  project_name = "my-app"

  # 告警阈值
  cpu_threshold    = 80
  memory_threshold = 85

  # 邮件联系人
  email_contacts = ["ops-team@company.com", "sre@company.com"]

  # 多渠道 Webhook (至少配置一个)
  dingtalk_webhook = "https://oapi.dingtalk.com/robot/send?access_token=xxx"
  feishu_webhook   = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
  wecom_webhook    = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
}
```

**输出确认**:
```bash
terraform apply

# 查看启用的通知渠道
terraform output notification_channels
# {
#   "dingtalk" = "enabled"
#   "feishu" = "enabled"
#   "wecom" = "enabled"
#   "email" = "enabled"
#   "sms" = "disabled"
# }
```

---

## 4. 告警生命周期

### 4.1 状态流转

```
        ┌─────────────────────────────────────────┐
        │                                         │
        ▼                                         │
   ┌─────────┐     指标超阈值      ┌───────────┐  │
   │  正常   │ ────────────────▶  │   告警    │  │
   │  OK    │                     │   ALARM   │  │
   └─────────┘ ◀───────────────  └───────────┘  │
        │        指标恢复+间隔         │         │
        │                               │         │
        │      ┌───────────┐            │         │
        └─────▶│   静默    │◀─────────┘         │
               │  SILENCE  │                     │
               └───────────┘                     │
                      ▲                          │
                      │ 静默周期结束              │
                      └──────────────────────────┘
```

### 4.2 静默周期

```hcl
# 告警触发后，15分钟不重复告警
interval = 15 * 60  # 900 秒

# 禁用静默
escalation_minutes = 0
```

### 4.3 告警升级

```hcl
# 告警触发 5 分钟后，如果未确认，则升级
# 0 = 禁用升级
escalation_minutes = 5
```

---

## 5. 运维场景

### 5.1 创建新告警

**场景**: 为 ECS 实例添加 CPU 告警

```hcl
module "cms_alarm" {
  source = "../../modules/addon-cms-alarm"

  environment = "production"
  project_name = "my-app"

  # 告警资源
  alarm_resources = [
    {
      resource_id   = "i-uf6exampleid"
      resource_type = "acs_ecs"
      metric_name   = "cpu_total"
    }
  ]

  # 阈值
  cpu_threshold = 80

  # 通知
  dingtalk_webhook = var.dingtalk_webhook
}
```

**执行**:
```bash
terraform plan
# 确认无误后
terraform apply
```

### 5.2 批量添加告警

**场景**: 为多个 RDS 实例添加磁盘告警

```hcl
locals {
  rds_instances = [
    { id = "rm-001", name = "主库" },
    { id = "rm-002", name = "从库" },
  ]
}

module "cms_alarm" {
  source = "../../modules/addon-cms-alarm"

  environment = "production"

  alarm_resources = [
    for rds in local.rds_instances : {
      resource_id   = rds.id
      resource_type = "acs_rds"
      metric_name   = "DiskUsage"
    }
  ]

  disk_threshold = 80
}
```

### 5.3 导入已有告警

**场景**: 将控制台创建的告警纳入 Terraform 管理

```bash
# 查询告警 ID
terraform import alicloud_cms_alarm.main <alarm_id>

# 导入联系人组
terraform import alicloud_cms_contact_group.main <group_id>

# 验证 drift
terraform plan
# 期望: 无变更（或仅 tag 变更）
```

### 5.4 告警变更审批

**场景**: 修改生产环境告警阈值

```bash
# 1. 修改配置
vim variables.tf
# cpu_threshold = 80 -> 75

# 2. Plan 预览变更
terraform plan -var="environment=production"

# 3. 如有变更，提交 HITL 审批
# ...

# 4. 审批通过后 apply
terraform apply
```

---

## 6. 故障排查

### 6.1 告警未触发

| 检查项 | 命令/步骤 |
|--------|----------|
| 指标是否上报 | 云监控控制台 → 指标监控 |
| 阈值设置 | 检查 `threshold` 值 |
| 维度匹配 | 确认 `dimensions` 与资源 ID |
| 联系人有效 | 检查联系人是否在联系人组 |
| 通知渠道 | 测试钉钉 Webhook |

### 6.2 告警风暴

**原因**: 大量资源同时触发告警

**解决**:
1. 设置 `silence_minutes = 30`（更长静默周期）
2. 使用聚合告警
3. 按服务分组，分别设置联系人

### 6.3 联系人收不到通知

| 检查项 | 解决方案 |
|--------|----------|
| 邮件在垃圾箱 | 添加白名单 |
| 短信限额 | 控制台提升限额 |
| 钉钉机器人 | 检查 Webhook URL 是否有效 |

---

## 7. 最佳实践

### 7.1 阈值设计

| 环境 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| dev | 90% | 90% | 90% | 开发环境宽松 |
| staging | 85% | 85% | 85% | 预发环境适中 |
| prod | 80% | 80% | 80% | 生产环境严格 |

### 7.2 通知策略

```hcl
# 生产环境: 钉钉 + 邮件
dingtalk_webhook = var.prod_webhook
email_contacts   = ["sre-team@company.com"]

# 测试环境: 仅钉钉
dingtalk_webhook = var.test_webhook
email_contacts   = []
```

### 7.3 资源标签

```hcl
# 必填标签
tags = {
  Environment = "production"
  ManagedBy   = "terraform"
  Project     = "my-project"
}
```

### 7.4 定期审计

```bash
# 导出告警列表
aliyun cms DescribeMetricRuleList --PageSize 100

# 导出联系人列表
aliyun cms DescribeContactList --PageSize 100

# 检查孤立告警（无联系人）
# 云监控控制台 → 告警规则管理
```

---

## 8. API 参考

### 8.1 Terraform 资源

| 资源 | 说明 |
|------|------|
| `alicloud_cms_alarm` | 告警规则 |
| `alicloud_cms_contact_group` | 联系人组 |

### 8.2 相关 CLI

```bash
# 查看告警规则
aliyun cms DescribeMetricRuleList

# 查看联系人组
aliyun cms DescribeContactGroupList

# 禁用告警
aliyun cms DisableAlerting

# 启用告警
aliyun cms EnableAlerting
```

---

## 9. 快速命令

```bash
# 初始化
cd modules/addon-cms-alarm
terraform init

# 验证
terraform validate

# 预览
terraform plan -var="environment=test" \
  -var="email_contacts=[\"test@example.com\"]"

# 应用
terraform apply

# 查看告警
terraform state list | grep cms

# 销毁
terraform destroy -var="environment=test"
```

---

## 10. 相关文档

| 文档 | 说明 |
|------|------|
| [SPEC-cms-alarm.md](./Spec-cms-alarm.md) | 模块规格 |
| [ADR-001](./adr/ADR-001-terraform-cms-alarm-management.md) | 架构决策 |
| [knowledge-briefs.md](./knowledge-briefs.md) | Terraform 速查 |
| [troubleshooting.md](./troubleshooting.md) | 通用故障排查 |

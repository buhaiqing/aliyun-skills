# SPEC-cms-alarm: 云监控告警 Terraform 模块规格

> **模块**: `addon-cms-alarm`
> **版本**: 1.0.0
> **状态**: Ready

---

## 1. 概述

### 1.1 模块职责

使用 Terraform 声明式管理阿里云云监控（CMS）的告警规则、联系人组和通知渠道，实现告警配置的 IaC 化管理。

### 1.2 适用范围

| 场景 | 支持 |
|------|------|
| 新建告警规则 | ✅ |
| 导入已有告警 | ✅ |
| 多环境告警（dev/staging/prod） | ✅ |
| 按资源类型告警 | ✅ |
| 钉钉/短信/邮件通知 | ✅ |

### 1.3 依赖资源

```
Required:
  └─ 无硬依赖（可独立部署）

Optional:
  ├─ alicloud_vpc (用于标签关联)
  ├─ alicloud_ecs_instance (用于指定实例告警)
  ├─ alicloud_slb_load_balancer (用于 SLB 告警)
  └─ alicloud_db_instance (用于 RDS 告警)
```

---

## 2. 资源定义

### 2.1 资源清单

| Terraform 资源 | 说明 | 数量 |
|----------------|------|------|
| `alicloud_cms_contact_group` | 告警联系人组 | 1 |
| `alicloud_cms_alarm` | 告警规则 | N (按配置) |

### 2.2 告警规则类型

#### 预置规则（按环境自动创建）

| 规则 Key | 指标名 | 项目 | 默认阈值 | 适用资源 |
|----------|--------|------|----------|----------|
| `cpu` | `cpu_total` | acs_ecs | 80% | 所有 ECS |
| `memory` | `memory_usedutilization` | acs_ecs | 85% | 所有 ECS |
| `disk` | `diskusage_utilization` | acs_ecs | 85% | 所有 ECS |
| `slb_502` | `SlbHttpCode_5xx` | acs_slb | 5% | 所有 SLB |

#### 自定义规则（按资源指定）

```hcl
alarm_resources = [
  {
    resource_id   = "i-xxxxxxxxxx"
    resource_type = "acs_ecs"
    metric_name   = "cpu_total"
  },
  {
    resource_id   = "rm-xxxxxxxxxx"
    resource_type = "acs_rds"
    metric_name   = "CpuUsage"
  }
]
```

---

## 3. 变量规格

### 3.1 必填变量

| 变量名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `environment` | `string` | 环境名称 | `"production"` |

### 3.2 告警阈值变量

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `cpu_threshold` | `number` | `80` | CPU 使用率阈值 (%) |
| `memory_threshold` | `number` | `85` | 内存使用率阈值 (%) |
| `disk_threshold` | `number` | `85` | 磁盘使用率阈值 (%) |
| `slb_502_threshold` | `number` | `5` | SLB 5xx 错误率阈值 (%) |

### 3.3 通知渠道变量

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `dingtalk_webhook` | `string` | `""` | 钉钉 Webhook URL |
| `feishu_webhook` | `string` | `""` | 飞书 Webhook URL |
| `wecom_webhook` | `string` | `""` | 企业微信 Webhook URL |
| `contact_groups` | `list(string)` | `["Default"]` | 联系人组名称列表 |
| `email_contacts` | `list(string)` | `[]` | 邮件联系人 |
| `sms_contacts` | `list(string)` | `[]` | 短信联系人 |

### 3.4 通知策略变量

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `silence_minutes` | `number` | `15` | 告警静默周期（分钟） |
| `escalation_minutes` | `number` | `5` | 告警升级等待时间（分钟，0=禁用） |

### 3.5 资源关联变量

| 变量名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `alarm_resources` | `list(object)` | `[]` | 指定告警的资源列表 |
| `vpc_id` | `string` | `""` | VPC ID（用于标签） |
| `project_name` | `string` | `""` | 项目名称（用于标签） |

---

## 4. 输出规格

### 4.1 输出清单

| 输出名 | 类型 | 说明 |
|--------|------|------|
| `alarm_ids` | `map(string)` | 告警规则 ID 映射 |
| `contact_group_id` | `string` | 联系人组 ID |
| `alarm_summary` | `object` | 告警汇总信息 |

### 4.2 输出示例

```hcl
alarm_ids = {
  "cpu"        = "a1b2c3d4-xxxx"
  "memory"     = "a1b2c3d4-yyyy"
  "disk"       = "a1b2c3d4-zzzz"
  "slb_502"    = "a1b2c3d4-wwww"
}

contact_group_id = "group-xxxxxxxx"

alarm_summary = {
  "total_alarms"     = 4
  "contact_group"    = "production-alarm-contact"
  "environment"      = "production"
  "escalation_min"   = 5
}
```

---

## 5. 告警配置详情

### 5.1 通用配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `period` | `300` | 采样周期（秒） |
| `statistics` | `"Average"` | 统计方法 |
| `interval` | `silence_minutes * 60` | 告警间隔（秒） |
| `alarm_state` | `"ALARM"` | 告警状态 |
| `effective_interval` | `"00:00-23:59"` | 生效时间 |

### 5.2 告警流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Metric   │ ──▶ │  Threshold  │ ──▶ │  Alarm ON   │
│  Exceeds   │     │   Breached  │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                     ┌─────────────┐            │
                     │  Silence    │ ◀───────────┘
                     │  Period    │
                     └─────────────┘
```

### 5.3 通知渠道

| 渠道 | 触发条件 | 配置变量 | Webhook URL 格式 |
|------|----------|----------|------------------|
| 钉钉 | 告警触发/恢复 | `dingtalk_webhook` | `https://oapi.dingtalk.com/robot/send?access_token=xxx` |
| 飞书 | 告警触发/恢复 | `feishu_webhook` | `https://open.feishu.cn/open-apis/bot/v2/hook/xxx` |
| 企业微信 | 告警触发/恢复 | `wecom_webhook` | `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` |
| 邮件 | 告警触发/恢复 | `email_contacts` | - |
| 短信 | 告警触发/恢复 | `sms_contacts` | - |

---

## 6. 标签规范

### 6.1 通用标签

```hcl
common_tags = {
  Environment = var.environment  # 必填
  ManagedBy   = "terraform"     # 必填
  Project     = var.project_name # 可选
}
```

### 6.2 告警规则标签

```hcl
# 预置规则
tags = merge(common_tags, {
  AlarmType = "cpu" | "memory" | "disk" | "slb_502"
})

# 自定义规则
tags = merge(common_tags, {
  ResourceType = "acs_ecs" | "acs_rds" | ...
  Metric       = "cpu_total" | ...
})
```

---

## 7. 安全规格

### 7.1 敏感变量

| 变量 | 敏感 | 处理方式 |
|------|------|----------|
| `dingtalk_webhook` | ✅ | `sensitive = true`，不打印 |

### 7.2 生命周期保护

```hcl
# 默认不保护，允许更新
# 如需保护，在外部模块添加:
lifecycle {
  prevent_destroy = true
}
```

---

## 8. NL2HCL 自然语言接口

### 8.1 触发关键词

| 关键词 | 映射 |
|--------|------|
| 告警、alarm、监控告警 | `addon-cms-alarm` |
| 联系人、contact | `alicloud_cms_contact_group` |
| 钉钉、webhook | `dingtalk_webhook` |
| 阈值、threshold | `cpu_threshold` 等 |

### 8.2 自然语言示例

| 用户输入 | 解析意图 |
|----------|----------|
| "为 ECS 创建 CPU 告警，阈值 80%" | 创建 cpu 告警规则 |
| "配置钉钉通知" | 设置 `dingtalk_webhook` |
| "告警联系人添加运维团队" | 添加 `email_contacts` |
| "CPU 超过 90% 告警" | 设置 `cpu_threshold = 90` |

### 8.3 NL2HCL 输出模板

```hcl
module "cms_alarm" {
  source = "../../modules/addon-cms-alarm"

  environment = "{{env}}"
  project_name = "{{project}}"

  # 阈值
  cpu_threshold    = {{cpu_threshold | default: 80}}
  memory_threshold = {{memory_threshold | default: 85}}
  disk_threshold   = {{disk_threshold | default: 85}}

  # 通知
  dingtalk_webhook = "{{dingtalk_webhook}}"
  contact_groups   = ["{{environment}}-alarm-contact"]

  # 资源
  alarm_resources = {{alarm_resources | tojson}}
}
```

---

## 9. 测试规格

### 9.1 Terraform Validate

```bash
cd modules/addon-cms-alarm
terraform init
terraform validate
# 期望: 无错误
```

### 9.2 Plan 验证

```bash
terraform plan -var="environment=test" -var="email_contacts=[\"test@example.com\"]"
# 期望: 创建 1 个 contact_group + 4 个告警规则
```

### 9.3 覆盖率检查

```bash
python3 scripts/module_coverage.py --verify
# 期望: addon-cms-alarm 通过
```

---

## 10. 参考信息

| 项目 | 值 |
|------|-----|
| Terraform 资源 | `alicloud_cms_alarm`, `alicloud_cms_contact_group` |
| Provider 版本 | `~> 1.200` |
| 阿里云产品 | 云监控 CMS |
| 相关 ADR | [ADR-001](./adr/ADR-001-terraform-cms-alarm-management.md) |
| 知识库 | [knowledge-cms-alarm.md](./knowledge-cms-alarm.md) |

# Runbook: CMS Alarm Configuration via Terraform

> **Scope**: CloudMonitor (CMS) 告警规则、联系组、通知渠道的 Terraform 配置管理

---

## 1. Module Overview

| Item | Value |
|------|-------|
| **Module** | `modules/addon-cms-alarm/` |
| **Resources** | `alicloud_cms_alarm`, `alicloud_cms_contact_group` |
| **Provider** | `aliyun/alicloud` ≥ 1.200.0 |

---

## 2. Quick Start

### 2.1 Basic Usage (Production)

```hcl
module "cms_alarms_prod" {
  source = "./modules/addon-cms-alarm"

  environment      = "production"
  contact_groups   = ["ops-team", "sre-team"]
  vpc_id           = alicloud_vpc.main.id
  project_name     = "my-project"

  # Thresholds
  cpu_threshold    = 70      # 生产更严格
  memory_threshold = 80
  disk_threshold  = 85

  # Escalation
  escalation_minutes = 5
  silence_minutes   = 15

  # Notifications
  dingtalk_webhook = var.dingtalk_prod_webhook
  email_contacts   = ["ops@example.com"]
}
```

### 2.2 Development Environment

```hcl
module "cms_alarms_dev" {
  source = "./modules/addon-cms-alarm"

  environment      = "development"
  contact_groups   = ["dev-team"]
  project_name     = "my-project"

  # 更宽松的阈值
  cpu_threshold    = 90
  memory_threshold = 90
  disk_threshold   = 95

  # 开发环境不升级
  escalation_minutes = 0
  silence_minutes   = 60
}
```

---

## 3. Scenario-Based Configuration

### 3.1 Per-Environment Thresholds

| Scenario | CPU% | Memory% | Disk% | SLB 502% | Escalation |
|----------|------|---------|-------|----------|------------|
| **production** | 70 | 80 | 85 | 5 | 5 min |
| **staging** | 80 | 85 | 90 | 10 | 15 min |
| **development** | 90 | 90 | 95 | 20 | disabled |

### 3.2 Scenario Variables File

```hcl
# environments/production/cms-alarm.tfvars
environment        = "production"
contact_groups    = ["ops-team", "sre-team", "dba-team"]
cpu_threshold     = 70
memory_threshold  = 80
disk_threshold    = 85
escalation_minutes = 5
dingtalk_webhook = ""  # Set via TF_VAR_ env var

email_contacts = [
  "ops@example.com",
  "sre@example.com"
]
```

### 3.3 Apply Command

```bash
cd environments/production
terraform init
terraform plan -var-file=cms-alarm.tfvars -out=cms-alarm.tfplan
terraform apply cms-alarm.tfplan
```

---

## 4. Alarm Types

### 4.1 Built-in Alarms

| Alarm | Metric | Description |
|-------|--------|-------------|
| `cpu` | `cpu_total` | CPU 使用率超过阈值 |
| `memory` | `memory_usedutilization` | 内存使用率超过阈值 |
| `disk` | `diskusage_utilization` | 磁盘使用率超过阈值 |
| `slb_502` | `SlbHttpCode_5xx` | SLB 5xx 错误率 |

### 4.2 Custom Resource Alarms

```hcl
module "cms_custom" {
  source = "./modules/addon-cms-alarm"

  environment    = "production"
  contact_groups = ["ops-team"]

  alarm_resources = [
    {
      resource_id   = "i-xxxxx"
      resource_type = "acs_ecs"
      metric_name   = "cpu_total"
    },
    {
      resource_id   = "rm-xxxxx"
      resource_type = "acs_rds"
      metric_name   = "CpuUsage"
    },
    {
      resource_id   = "mr-xxxxx"
      resource_type = "acs_redis"
      metric_name   = "MemoryUsage"
    }
  ]
}
```

### 4.3 Supported Resource Types

| Product | Resource Type | Common Metrics |
|---------|---------------|----------------|
| ECS | `acs_ecs` | `cpu_total`, `memory_usedutilization`, `diskusage_utilization` |
| RDS | `acs_rds` | `CpuUsage`, `MemoryUsage`, `DiskUsage`, `QPS`, `ConnectionUsage` |
| Redis | `acs_redis` | `MemoryUsage`, `CpuUsage`, `KeysUsage` |
| SLB | `acs_slb` | `SlbHttpCode_5xx`, `TrafficRxNew`, `TrafficTxNew` |
| OSS | `acs_ocs` | `BaseDiskUsage`, `NetworkInRate` |
| POLARDB | `acs_polardb` | `CpuUtilization`, `MemoryUtilization`, `DataNodeDiskUsage` |

---

## 5. Contact Management

### 5.1 Contact Group Structure

```
Contact Group
├── Email notifications
├── SMS notifications
└── Webhook (DingTalk)
```

### 5.2 Multi-Team Contacts

```hcl
# 按团队分离联系组
resource "alicloud_cms_contact_group" "ops" {
  name            = "production-ops"
  contact_lists   = ["ops-lead@example.com"]
  email_list      = ["ops-lead@example.com"]
}

resource "alicloud_cms_contact_group" "sre" {
  name            = "production-sre"
  contact_lists   = ["sre-lead@example.com"]
}

resource "alicloud_cms_contact_group" "dba" {
  name            = "production-dba"
  contact_lists   = ["dba-lead@example.com"]
}
```

---

## 6. Notification Channels

### 6.1 DingTalk Webhook

```hcl
# 生产环境：钉钉群通知
module "cms_prod" {
  source = "./modules/addon-cms-alarm"
  
  environment       = "production"
  dingtalk_webhook  = var.dingtalk_prod_webhook  # 从变量获取
}

# 测试环境：仅邮件
module "cms_dev" {
  source = "./modules/addon-cms-alarm"
  
  environment       = "development"
  dingtalk_webhook  = ""  # 不发钉钉
  email_contacts    = ["dev@example.com"]
}
```

### 6.2 Security: Webhook URL via Environment Variable

```bash
# 安全注入 webhook（不写入 tfvars）
export TF_VAR_dingtalk_prod_webhook="https://oapi.dingtalk.com/robot/send?access_token=xxx"
terraform plan
```

⚠️ **警告**: 禁止将真实 webhook token 写入 tfvars 或 git 仓库。

---

## 7. Multi-Project Alarms

### 7.1 Shared Contact Group

```hcl
# 基础联系组（跨项目共享）
module "shared_contacts" {
  source = "./modules/addon-cms-alarm"
  
  environment     = "shared"
  contact_groups  = ["global-ops"]
  email_contacts  = ["ops@example.com"]
}

# 项目 A 告警
module "cms_project_a" {
  source = "./modules/addon-cms-alarm"
  
  environment     = "project-a"
  contact_groups   = ["project-a-team", "global-ops"]
  cpu_threshold    = 70
}

# 项目 B 告警（不同阈值）
module "cms_project_b" {
  source = "./modules-cms-alarm"
  
  environment     = "project-b"
  contact_groups   = ["project-b-team", "global-ops"]
  cpu_threshold    = 85  # 更宽松
}
```

---

## 8. State Management

### 8.1 Backend Configuration

```hcl
# versions.tf
terraform {
  backend "oss" {
    bucket = "tf-state-alarms"
    prefix = "environments/${var.environment}/cms-alarm"
  }
}
```

### 8.2 State Isolation

```
OSS Bucket: tf-state-alarms
├── environments/
│   ├── production/cms-alarm/
│   │   └── terraform.tfstate
│   ├── staging/cms-alarm/
│   │   └── terraform.tfstate
│   └── development/cms-alarm/
│       └── terraform.tfstate
```

---

## 9. Drift Detection

```bash
# 检测配置漂移
terraform plan -detailed-exitcode

# 输出告警差异
terraform plan 2>&1 | grep -E "^(~|\+|-)"

# 恢复漂移
terraform apply
```

---

## 10. Disaster Recovery

### 10.1 Backup & Restore

```bash
# 导出当前告警配置
terraform state pull > cms-alarm-backup-$(date +%Y%m%d).tfstate

# 导入到新环境
terraform import module.cms_prod.alicloud_cms_contact_group.main <group_id>
terraform import module.cms_prod.alicloud_cms_alarm.main["cpu"] <alarm_id>
```

### 10.2 Cross-Region Copy

```hcl
# 使用 providers 块指定目标 region
provider "alicloud" {
  alias = "cn-beijing"
  region = "cn-beijing"
}

provider "alicloud" {
  alias = "cn-shanghai"
  region = "cn-shanghai"
}

module "cms_beijing" {
  source  = "./modules/addon-cms-alarm"
  providers = {
    alicloud = alicloud.cn-beijing
  }
  # ...
}
```

---

## 11. Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Alarm not firing | Threshold too high | 降低阈值或检查 metric 是否正确 |
| Duplicate alarms | Multiple resources with same name | 排查是否有重复 `alicloud_cms_alarm` 资源 |
| Contact not receiving | Contact group not linked | 确认 `alarm_actions` 包含正确的 contact_group_id |
| Webhook failing | Token expired | 更新 `dingtalk_webhook` 变量 |
| Import failed | Resource ID unknown | 使用 CMS 控制台获取正确的资源 ID |

---

## 12. Import Existing Alarms

```bash
# 导入已有告警到 Terraform
terraform import alicloud_cms_alarm.main <alarm_id>

# 批量导入同类型
for id in $(cat alarm_ids.txt); do
  terraform import alicloud_cms_alarm.main $id
done
```

---

## 13. Cleanup

```bash
# 删除告警（先 plan 确认）
terraform plan -destroy
terraform destroy

# 仅删除特定资源
terraform destroy -target=module.cms_prod.alicloud_cms_alarm.main["cpu"]
```

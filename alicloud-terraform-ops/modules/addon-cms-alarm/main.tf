# =============================================================================
# addon-cms-alarm — CloudMonitor alarm configuration
#
# Supports: 钉钉 / 飞书 (Lark) / 企业微信 (WeCom)
#
# Usage:
#   module "cms_alarms" {
#     source = "./modules/addon-cms-alarm"
#
#     environment     = "production"
#     contact_groups  = ["ops-team", "sre-team"]
#     project_name    = "my-project"
#
#     # 通知渠道 (至少配置一个)
#     dingtalk_webhook  = "https://oapi.dingtalk.com/..."
#     feishu_webhook    = "https://open.feishu.cn/..."
#     wecom_webhook     = "https://qyapi.weixin.qq.com/..."
#
#     # 告警阈值
#     cpu_threshold    = 80
#     memory_threshold = 85
#     disk_threshold   = 85
#   }
# =============================================================================

locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = var.project_name
  }

  # Alarm definitions per environment scenario
  alarm_defs = {
    cpu = {
      metric_name = "cpu_total"
      description = "${var.environment} CPU usage exceeds ${var.cpu_threshold}%"
    },
    memory = {
      metric_name = "memory_usedutilization"
      description = "${var.environment} Memory usage exceeds ${var.memory_threshold}%"
    },
    disk = {
      metric_name = "diskusage_utilization"
      description = "${var.environment} Disk usage exceeds ${var.disk_threshold}%"
    },
    slb_502 = {
      metric_name = "SlbHttpCode_5xx"
      description = "${var.environment} SLB 502 error rate exceeds ${var.slb_502_threshold}%"
    }
  }

  # 通知渠道检测
  has_webhook = (
    var.dingtalk_webhook != "" ||
    var.feishu_webhook != "" ||
    var.wecom_webhook != ""
  )
}

# -----------------------------------------------------------------------------
# Contact Group (联系人组)
# -----------------------------------------------------------------------------

resource "alicloud_cms_contact_group" "main" {
  name                               = "${var.environment}-alarm-contact"
  description                        = "Alarm contacts for ${var.environment} environment"
  contact_lists                      = var.email_contacts
  enable_subscribed_notification     = true

  dynamic "sms_notify_triggers" {
    for_each = toset(var.sms_contacts)
    content {
      name = sms_notify_triggers.value
    }
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Alarm Rules — 预置告警规则
# -----------------------------------------------------------------------------

resource "alicloud_cms_alarm" "main" {
  for_each = toset([
    "cpu",
    "memory",
    "disk",
    "slb_502"
  ])

  name           = "${var.environment}-${each.key}-alarm"
  project        = "acs_ecs"
  metric         = local.alarm_defs[each.key].metric_name
  dimensions     = jsonencode({
    instanceId = "*"
  })
  period         = 300
  threshold      = each.key == "cpu" ? var.cpu_threshold :
                   each.key == "memory" ? var.memory_threshold :
                   each.key == "disk" ? var.disk_threshold :
                   var.slb_502_threshold
  statistics     = "Average"
  alarm_actions  = [alicloud_cms_contact_group.main.id]
  ok_actions     = [alicloud_cms_contact_group.main.id]
  interval       = var.silence_minutes * 60

  # 钉钉 Webhook
  dynamic "webhook" {
    for_each = var.dingtalk_webhook != "" ? [1] : []
    content {
      url = var.dingtalk_webhook
    }
  }

  # 飞书 Webhook (与钉钉共用阿里云 CMS webhook 格式)
  # 注: 飞书使用相同的 webhook 协议，只需提供飞书机器人的 Webhook URL
  dynamic "webhook" {
    for_each = var.feishu_webhook != "" ? [1] : []
    content {
      url = var.feishu_webhook
    }
  }

  # 企业微信 Webhook
  dynamic "webhook" {
    for_each = var.wecom_webhook != "" ? [1] : []
    content {
      url = var.wecom_webhook
    }
  }

  tags = merge(local.common_tags, {
    AlarmType = each.key
  })
}

# -----------------------------------------------------------------------------
# Alarm Rules — 自定义资源告警
# -----------------------------------------------------------------------------

resource "alicloud_cms_alarm" "by_resource" {
  for_each = {
    for r in var.alarm_resources : "${r.resource_type}_${r.metric_name}_${r.resource_id}" => r
  }

  name           = "${var.environment}-${each.value.resource_type}-${each.value.metric_name}"
  project        = each.value.resource_type
  metric         = each.value.metric_name
  dimensions     = jsonencode({
    instanceId = each.value.resource_id
  })
  period         = 300
  threshold      = contains(["cpu_total", "memory_usedutilization"], each.value.metric_name) ?
                   (each.value.metric_name == "cpu_total" ? var.cpu_threshold : var.memory_threshold) :
                   var.disk_threshold
  statistics     = "Average"
  alarm_actions  = [alicloud_cms_contact_group.main.id]
  ok_actions     = [alicloud_cms_contact_group.main.id]
  interval       = var.silence_minutes * 60

  # 钉钉 Webhook
  dynamic "webhook" {
    for_each = var.dingtalk_webhook != "" ? [1] : []
    content {
      url = var.dingtalk_webhook
    }
  }

  # 飞书 Webhook
  dynamic "webhook" {
    for_each = var.feishu_webhook != "" ? [1] : []
    content {
      url = var.feishu_webhook
    }
  }

  # 企业微信 Webhook
  dynamic "webhook" {
    for_each = var.wecom_webhook != "" ? [1] : []
    content {
      url = var.wecom_webhook
    }
  }

  tags = merge(local.common_tags, {
    ResourceType = each.value.resource_type
    Metric       = each.value.metric_name
  })
}

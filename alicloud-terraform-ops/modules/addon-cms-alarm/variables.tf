# =============================================================================
# addon-cms-alarm — Variables
# =============================================================================

# -----------------------------------------------------------------------------
# 基础配置
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Environment name (production/staging/development)"
  type        = string
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
  default     = ""
}

variable "vpc_id" {
  description = "VPC ID for tag-based alarm targeting"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# 告警资源
# -----------------------------------------------------------------------------

variable "alarm_resources" {
  description = <<-EOT
    Resources to attach alarms to.
    Each resource should have:
    - resource_id: The instance/resource ID
    - resource_type: The cloud product (acs_ecs, acs_rds, acs_slb, etc.)
    - metric_name: The metric to monitor
  EOT
  type = list(object({
    resource_id   = string
    resource_type = string
    metric_name   = string
  }))
  default = []
}

# -----------------------------------------------------------------------------
# 告警阈值
# -----------------------------------------------------------------------------

variable "cpu_threshold" {
  description = "CPU usage threshold (%)"
  type        = number
  default     = 80
}

variable "memory_threshold" {
  description = "Memory usage threshold (%)"
  type        = number
  default     = 85
}

variable "disk_threshold" {
  description = "Disk usage threshold (%)"
  type        = number
  default     = 85
}

variable "slb_502_threshold" {
  description = "SLB 502 error rate threshold (%)"
  type        = number
  default     = 5
}

# -----------------------------------------------------------------------------
# 通知渠道配置
# -----------------------------------------------------------------------------

variable "dingtalk_webhook" {
  description = <<-EOT
    DingTalk webhook URL for alarm notifications.
    Format: https://oapi.dingtalk.com/robot/send?access_token=xxx
    Leave empty to disable DingTalk notifications.
  EOT
  type      = string
  sensitive = true
  default   = ""
}

variable "feishu_webhook" {
  description = <<-EOT
    Feishu (Lark) webhook URL for alarm notifications.
    Format: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    Leave empty to disable Feishu notifications.

    Setup:
    1. Open Feishu group → Settings → Bots → Add Bot
    2. Select "Custom Bot"
    3. Set bot name and security settings
    4. Copy the Webhook URL
  EOT
  type      = string
  sensitive = true
  default   = ""
}

variable "wecom_webhook" {
  description = <<-EOT
    WeCom (Enterprise WeChat) webhook URL for alarm notifications.
    Format: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
    Leave empty to disable WeCom notifications.

    Setup:
    1. Open WeCom group → Add群机器人
    2. Select "Custom Robot"
    3. Set robot name and security settings (optional)
    4. Copy the Webhook URL
  EOT
  type      = string
  sensitive = true
  default   = ""
}

# -----------------------------------------------------------------------------
# 联系人配置
# -----------------------------------------------------------------------------

variable "contact_groups" {
  description = "Alarm contact group names"
  type        = list(string)
  default     = ["Default"]
}

variable "email_contacts" {
  description = "Email addresses for alarm notifications"
  type        = list(string)
  default     = []
}

variable "sms_contacts" {
  description = "Phone numbers for SMS alarm notifications"
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# 告警策略
# -----------------------------------------------------------------------------

variable "silence_minutes" {
  description = "Silence period after alarm fires (minutes)"
  type        = number
  default     = 15
}

variable "escalation_minutes" {
  description = "Minutes before escalating alarm (0=disabled)"
  type        = number
  default     = 5
}

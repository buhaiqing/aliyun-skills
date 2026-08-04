# =============================================================================
# addon-cms-alarm — Outputs
# =============================================================================

output "alarm_ids" {
  description = "IDs of created alarm rules"
  value = merge(
    { for k, v in alicloud_cms_alarm.main : k => v.id },
    { for k, v in alicloud_cms_alarm.by_resource : k => v.id }
  )
}

output "alarm_ids_preset" {
  description = "IDs of preset alarm rules (cpu/memory/disk/slb_502)"
  value = { for k, v in alicloud_cms_alarm.main : k => v.id }
}

output "alarm_ids_custom" {
  description = "IDs of custom resource-specific alarm rules"
  value = { for k, v in alicloud_cms_alarm.by_resource : k => v.id }
}

output "contact_group_id" {
  description = "Contact group ID"
  value       = alicloud_cms_contact_group.main.id
}

output "contact_group_name" {
  description = "Contact group name"
  value       = alicloud_cms_contact_group.main.name
}

output "alarm_summary" {
  description = "Summary of created alarms"
  value = {
    total_alarms       = length(alicloud_cms_alarm.main) + length(alicloud_cms_alarm.by_resource)
    preset_alarms       = length(alicloud_cms_alarm.main)
    custom_alarms       = length(alicloud_cms_alarm.by_resource)
    contact_group       = alicloud_cms_contact_group.main.name
    environment         = var.environment
    silence_minutes    = var.silence_minutes
    escalation_minutes = var.escalation_minutes
  }
}

output "notification_channels" {
  description = "Enabled notification channels"
  value = {
    dingtalk = var.dingtalk_webhook != "" ? "enabled" : "disabled"
    feishu    = var.feishu_webhook != "" ? "enabled" : "disabled"
    wecom     = var.wecom_webhook != "" ? "enabled" : "disabled"
    email     = length(var.email_contacts) > 0 ? "enabled" : "disabled"
    sms       = length(var.sms_contacts) > 0 ? "enabled" : "disabled"
  }
}

output "alarm_rule_names" {
  description = "Names of all created alarm rules"
  value = merge(
    { for k, v in alicloud_cms_alarm.main : k => v.name },
    { for k, v in alicloud_cms_alarm.by_resource : k => v.name }
  )
}

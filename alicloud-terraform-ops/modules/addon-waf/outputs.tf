output "waf_instance_id" {
  value = alicloud_wafv3_instance.main.id
}

output "waf_instance_name" {
  value = alicloud_wafv3_instance.main.instance_name
}

output "waf_domains" {
  value = [for d in alicloud_wafv3_domain.main : d.domain]
}
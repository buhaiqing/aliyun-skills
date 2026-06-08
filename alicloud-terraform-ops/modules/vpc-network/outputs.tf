output "vpc_id" {
  description = "VPC ID"
  value       = alicloud_vpc.main.id
}

output "vpc_cidr" {
  description = "VPC CIDR"
  value       = alicloud_vpc.main.cidr_block
}

output "vpc_name" {
  description = "VPC name"
  value       = alicloud_vpc.main.vpc_name
}

output "vswitch_ids" {
  description = "vSwitch IDs keyed by AZ suffix"
  value       = { for k, v in alicloud_vswitch.main : k => v.id }
}

output "vswitch_cidrs" {
  description = "vSwitch CIDRs keyed by AZ suffix"
  value       = { for k, v in alicloud_vswitch.main : k => v.cidr_block }
}

output "vswitch_zone_ids" {
  description = "vSwitch zone IDs keyed by AZ suffix"
  value       = { for k, v in alicloud_vswitch.main : k => v.zone_id }
}

output "primary_vswitch_id" {
  description = "First vSwitch ID (AZ-a)"
  value       = alicloud_vswitch.main["a"].id
}

output "primary_zone_id" {
  description = "First vSwitch zone ID"
  value       = alicloud_vswitch.main["a"].zone_id
}

output "security_group_id" {
  value = alicloud_security_group.main.id
}

output "security_group_name" {
  value = alicloud_security_group.main.security_group_name
}

output "ecs_instance_ids" {
  value = alicloud_instance.main[*].id
}

output "ecs_instance_names" {
  value = alicloud_instance.main[*].instance_name
}

output "ecs_private_ips" {
  value = alicloud_instance.main[*].primary_ip_address
}

output "ecs_public_ips" {
  value = alicloud_instance.main[*].public_ip
}

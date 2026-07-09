output "security_group_id" {
  value = alicloud_security_group.main.id
}

output "security_group_name" {
  value = alicloud_security_group.main.security_group_name
}
output "rds_instance_id" {
  value = alicloud_db_instance.main.id
}

output "rds_instance_name" {
  value = alicloud_db_instance.main.instance_name
}

output "rds_connection_string" {
  value = alicloud_db_instance.main.connection_string
}

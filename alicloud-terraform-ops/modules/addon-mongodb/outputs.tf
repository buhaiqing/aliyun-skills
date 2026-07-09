output "mongodb_instance_id" {
  value = alicloud_mongodb_instance.main.id
}

output "mongodb_instance_name" {
  value = alicloud_mongodb_instance.main.instance_name
}

output "mongodb_connection_string" {
  value = alicloud_mongodb_instance.main.connection_string
}
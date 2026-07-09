output "redis_instance_id" {
  value = alicloud_kvstore_instance.main.id
}

output "redis_instance_name" {
  value = alicloud_kvstore_instance.main.db_instance_name
}

output "redis_connection_domain" {
  value = alicloud_kvstore_instance.main.connection_domain
}

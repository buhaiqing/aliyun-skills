resource "alicloud_kvstore_instance" "main" {
  db_instance_name = "${var.environment}-redis-main"
  instance_class   = "redis.master.small.default"
  instance_type    = "Redis"
  engine_version   = "6.0"
  vswitch_id       = var.vswitch_id

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

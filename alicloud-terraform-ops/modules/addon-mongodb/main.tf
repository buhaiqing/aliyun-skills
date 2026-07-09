resource "alicloud_mongodb_instance" "main" {
  engine_version      = var.mongodb_engine_version
  db_instance_class   = var.mongodb_instance_class
  db_instance_storage = var.mongodb_storage
  vswitch_id          = var.vswitch_id

  instance_name = "${var.environment}-mongodb-main"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
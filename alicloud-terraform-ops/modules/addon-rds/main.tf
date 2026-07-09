resource "alicloud_db_instance" "main" {
  engine           = "MySQL"
  engine_version   = "8.0"
  instance_type    = var.rds_instance_class
  instance_storage = 20
  vswitch_id       = var.vswitch_id
  instance_name    = "${var.environment}-rds-main"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "alicloud_polardb_cluster" "main" {
  db_type      = var.polardb_engine
  db_version   = var.polardb_engine_version
  db_node_class = var.polardb_instance_class
  pay_type     = "PostPaid"

  vswitch_id    = var.vswitch_id
  cluster_name  = "${var.environment}-polardb-main"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
resource "alicloud_slb_load_balancer" "main" {
  load_balancer_name = "${var.environment}-web-slb"
  load_balancer_spec = "slb.s1.small"
  address_type       = "internet"
  vswitch_id         = var.vswitch_id

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "alicloud_alb_load_balancer" "main" {
  load_balancer_name = "${var.environment}-alb-main"
  load_balancer_edition = var.alb_edition
  address_type       = var.alb_address_type
  vpc_id             = var.vpc_id

  zone_mappings {
    vswitch_id = var.vswitch_id
    zone_id    = var.zone_id
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
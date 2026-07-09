resource "alicloud_nat_gateway" "main" {
  vpc_id           = var.vpc_id
  vswitch_id       = var.vswitch_id
  nat_gateway_name = "${var.environment}-nat-main"
  payment_type     = "PayAsYouGo"
  nat_type         = "Enhanced"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

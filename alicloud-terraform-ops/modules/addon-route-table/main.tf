resource "alicloud_route_table" "main" {
  vpc_id           = var.vpc_id
  route_table_name = "${var.environment}-rt-main"
  description      = "Route table for ${var.environment}"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

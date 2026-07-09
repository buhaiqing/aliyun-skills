resource "alicloud_eip_address" "main" {
  address_name         = "${var.environment}-eip-main"
  isp                  = "BGP"
  internet_charge_type = "PayByTraffic"
  bandwidth            = "10"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

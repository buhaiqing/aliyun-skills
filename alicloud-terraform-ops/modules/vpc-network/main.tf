resource "alicloud_vpc" "main" {
  vpc_name   = "${var.environment}-vpc"
  cidr_block = var.vpc_cidr

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

locals {
  az_suffixes = slice(["a", "b", "c", "d", "e", "f", "g", "h"], 0, var.az_count)
}

resource "alicloud_vswitch" "main" {
  for_each = toset(local.az_suffixes)

  vpc_id       = alicloud_vpc.main.id
  cidr_block   = cidrsubnet(alicloud_vpc.main.cidr_block, 8, index(local.az_suffixes, each.key) + 1)
  zone_id      = "${var.region}-${each.key}"
  vswitch_name = "${var.environment}-vswitch-${each.key}"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

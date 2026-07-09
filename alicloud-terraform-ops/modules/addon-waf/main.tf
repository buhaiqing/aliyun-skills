resource "alicloud_wafv3_instance" "main" {
  instance_name = "${var.environment}-waf-main"
  region_id     = var.region
  instance_charge_type = "PostPaid"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "alicloud_wafv3_domain" "main" {
  count       = length(var.domains)
  instance_id = alicloud_wafv3_instance.main.id
  domain      = var.domains[count.index]
  region_id   = var.region

  access_type = var.access_type

  source_ips = var.source_ips

  listen {
    protocol     = "http"
    http_port    = [80]
  }

  listen {
    protocol     = "https"
    https_port   = [443]
  }

  redirect {
    load_balancing = "IpHash"
    keepalive      = true
    retry          = true
  }
}
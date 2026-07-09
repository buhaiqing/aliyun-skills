resource "alicloud_security_group" "main" {
  security_group_name = "${var.environment}-sg-main"
  description         = "Security group for ${var.environment} resources"
  vpc_id              = var.vpc_id

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "alicloud_security_group_rule" "allow_tcp" {
  count             = length(var.ingress_rules)
  type              = "ingress"
  ip_protocol       = var.ingress_rules[count.index].protocol
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = var.ingress_rules[count.index].port_range
  priority          = var.ingress_rules[count.index].priority
  cidr_ip           = var.ingress_rules[count.index].cidr_ip
  security_group_id = alicloud_security_group.main.id
  description       = var.ingress_rules[count.index].description
}

resource "alicloud_security_group_rule" "allow_udp" {
  count             = length(var.ingress_rules_udp)
  type              = "ingress"
  ip_protocol       = "udp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = var.ingress_rules_udp[count.index].port_range
  priority          = var.ingress_rules_udp[count.index].priority
  cidr_ip           = var.ingress_rules_udp[count.index].cidr_ip
  security_group_id = alicloud_security_group.main.id
  description       = var.ingress_rules_udp[count.index].description
}
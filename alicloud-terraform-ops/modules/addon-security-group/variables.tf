variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "ingress_rules" {
  type = list(object({
    protocol   = string
    port_range = string
    priority   = optional(number, 1)
    cidr_ip    = optional(string, "0.0.0.0/0")
    description = optional(string, "")
  }))
  default = [
    {
      protocol    = "tcp"
      port_range  = "22/22"
      priority    = 1
      cidr_ip     = "0.0.0.0/0"
      description = "SSH"
    },
    {
      protocol    = "tcp"
      port_range  = "80/80"
      priority    = 1
      cidr_ip     = "0.0.0.0/0"
      description = "HTTP"
    },
    {
      protocol    = "tcp"
      port_range  = "443/443"
      priority    = 1
      cidr_ip     = "0.0.0.0/0"
      description = "HTTPS"
    },
  ]
}

variable "ingress_rules_udp" {
  type = list(object({
    port_range = string
    priority   = optional(number, 1)
    cidr_ip    = optional(string, "0.0.0.0/0")
    description = optional(string, "")
  }))
  default = []
}
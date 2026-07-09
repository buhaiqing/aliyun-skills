variable "environment" {
  type = string
}

variable "region" {
  type = string
}

variable "domains" {
  type        = list(string)
  description = "List of domain names to protect"
}

variable "access_type" {
  type    = string
  default = "waf-cloud-dns"
}

variable "source_ips" {
  type        = list(string)
  default     = []
  description = "Origin server IPs for WAF to forward traffic to"
}
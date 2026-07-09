variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "region" {
  description = "Alibaba Cloud region"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "az_count" {
  description = "Number of availability zones (vSwitches)"
  type        = number
  default     = 2
}

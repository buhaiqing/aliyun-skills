variable "environment" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vswitch_id" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "instance_count" {
  type    = number
  default = 1
}

variable "data_disk_size" {
  type        = number
  default     = 0
  description = "Optional inline data disk size in GB; 0 disables"
}

variable "name" {
  type    = string
  default = "web"
}

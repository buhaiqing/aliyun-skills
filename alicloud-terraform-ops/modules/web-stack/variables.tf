variable "environment" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "az_count" {
  type    = number
  default = 2
}

variable "ecs_instance_type" {
  type = string
}

variable "ecs_count" {
  type    = number
  default = 1
}

variable "ecs_data_disk_size" {
  type    = number
  default = 0
}

variable "enable_ecs" {
  type    = bool
  default = true
}

variable "rds_instance_class" {
  type    = string
  default = ""
}

variable "enable_rds" {
  type    = bool
  default = false
}

variable "enable_redis" {
  type    = bool
  default = false
}

variable "enable_slb" {
  type    = bool
  default = false
}

variable "enable_nat" {
  type    = bool
  default = false
}

variable "enable_eip" {
  type    = bool
  default = false
}

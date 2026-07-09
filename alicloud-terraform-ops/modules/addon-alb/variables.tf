variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vswitch_id" {
  type = string
}

variable "zone_id" {
  type = string
}

variable "alb_edition" {
  type    = string
  default = "Basic"
}

variable "alb_address_type" {
  type    = string
  default = "Internet"
}
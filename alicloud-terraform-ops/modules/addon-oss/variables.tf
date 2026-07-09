variable "environment" {
  type = string
}

variable "bucket_name" {
  type = string
}

variable "bucket_acl" {
  type    = string
  default = "private"
}

variable "storage_class" {
  type    = string
  default = "Standard"
}
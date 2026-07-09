resource "alicloud_oss_bucket" "main" {
  bucket = var.bucket_name

  acl           = var.bucket_acl
  storage_class = var.storage_class

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
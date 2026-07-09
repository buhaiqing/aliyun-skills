output "bucket_name" {
  value = alicloud_oss_bucket.main.bucket
}

output "bucket_id" {
  value = alicloud_oss_bucket.main.id
}

output "bucket_acl" {
  value = alicloud_oss_bucket.main.acl
}

output "bucket_extranet_endpoint" {
  value = alicloud_oss_bucket.main.extranet_endpoint
}

output "bucket_intranet_endpoint" {
  value = alicloud_oss_bucket.main.intranet_endpoint
}
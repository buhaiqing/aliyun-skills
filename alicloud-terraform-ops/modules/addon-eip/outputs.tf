output "eip_id" {
  value = alicloud_eip_address.main.id
}

output "eip_address" {
  value = alicloud_eip_address.main.ip_address
}

output "eip_bandwidth" {
  value = alicloud_eip_address.main.bandwidth
}

output "slb_id" {
  value = alicloud_slb_load_balancer.main.id
}

output "slb_name" {
  value = alicloud_slb_load_balancer.main.load_balancer_name
}

output "slb_address" {
  value = alicloud_slb_load_balancer.main.address
}

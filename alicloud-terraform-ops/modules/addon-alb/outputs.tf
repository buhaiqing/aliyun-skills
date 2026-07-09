output "alb_id" {
  value = alicloud_alb_load_balancer.main.id
}

output "alb_name" {
  value = alicloud_alb_load_balancer.main.load_balancer_name
}

output "alb_dns_name" {
  value = alicloud_alb_load_balancer.main.dns_name
}
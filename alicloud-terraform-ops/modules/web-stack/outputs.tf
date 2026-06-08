output "vpc_id" {
  value = module.network.vpc_id
}

output "vpc_cidr" {
  value = module.network.vpc_cidr
}

output "vpc_name" {
  value = module.network.vpc_name
}

output "vswitch_ids" {
  value = module.network.vswitch_ids
}

output "vswitch_cidrs" {
  value = module.network.vswitch_cidrs
}

output "vswitch_zone_ids" {
  value = module.network.vswitch_zone_ids
}

output "security_group_id" {
  value = var.enable_ecs ? module.compute[0].security_group_id : null
}

output "ecs_instance_ids" {
  value = var.enable_ecs ? module.compute[0].ecs_instance_ids : []
}

output "ecs_instance_names" {
  value = var.enable_ecs ? module.compute[0].ecs_instance_names : []
}

output "ecs_private_ips" {
  value = var.enable_ecs ? module.compute[0].ecs_private_ips : []
}

output "ecs_public_ips" {
  value = var.enable_ecs ? module.compute[0].ecs_public_ips : []
}

output "rds_instance_id" {
  value = var.enable_rds ? module.rds[0].rds_instance_id : null
}

output "redis_instance_id" {
  value = var.enable_redis ? module.redis[0].redis_instance_id : null
}

output "slb_id" {
  value = var.enable_slb ? module.slb[0].slb_id : null
}

output "nat_gateway_id" {
  value = var.enable_nat ? module.nat[0].nat_gateway_id : null
}

output "eip_id" {
  value = var.enable_eip ? module.eip[0].eip_id : null
}

output "eip_address" {
  value = var.enable_eip ? module.eip[0].eip_address : null
}

module "network" {
  source = "../vpc-network"

  providers = {
    alicloud = alicloud
  }

  environment = var.environment
  region      = var.region
  vpc_cidr    = var.vpc_cidr
  az_count    = var.az_count
}

module "compute" {
  count  = var.enable_ecs ? 1 : 0
  source = "../compute-ecs"

  providers = {
    alicloud = alicloud
  }

  environment      = var.environment
  region           = var.region
  vpc_id           = module.network.vpc_id
  vswitch_id       = module.network.primary_vswitch_id
  instance_type    = var.ecs_instance_type
  instance_count   = var.ecs_count
  data_disk_size   = var.ecs_data_disk_size
}

module "rds" {
  count  = var.enable_rds ? 1 : 0
  source = "../addon-rds"

  providers = {
    alicloud = alicloud
  }

  environment        = var.environment
  vswitch_id         = module.network.primary_vswitch_id
  rds_instance_class = var.rds_instance_class
}

module "redis" {
  count  = var.enable_redis ? 1 : 0
  source = "../addon-redis"

  providers = {
    alicloud = alicloud
  }

  environment = var.environment
  vswitch_id  = module.network.primary_vswitch_id
}

module "slb" {
  count  = var.enable_slb ? 1 : 0
  source = "../addon-slb"

  providers = {
    alicloud = alicloud
  }

  environment = var.environment
  vswitch_id  = module.network.primary_vswitch_id
}

module "nat" {
  count  = var.enable_nat ? 1 : 0
  source = "../addon-nat"

  providers = {
    alicloud = alicloud
  }

  environment = var.environment
  vpc_id      = module.network.vpc_id
  vswitch_id  = module.network.primary_vswitch_id
}

module "eip" {
  count  = var.enable_eip ? 1 : 0
  source = "../addon-eip"

  providers = {
    alicloud = alicloud
  }

  environment = var.environment
}

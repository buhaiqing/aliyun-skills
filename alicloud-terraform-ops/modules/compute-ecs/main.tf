resource "alicloud_security_group" "main" {
  security_group_name = "${var.environment}-${var.name}-sg"
  description         = "Security group for ${var.environment} ${var.name} resources"
  vpc_id              = var.vpc_id

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

data "alicloud_images" "ubuntu" {
  most_recent = true
  owners      = "system"
  name_regex  = "^ubuntu_22"
}

resource "alicloud_instance" "main" {
  count         = var.instance_count
  image_id      = data.alicloud_images.ubuntu.images[0].id
  instance_type = var.instance_type

  instance_name = "${var.environment}-${var.name}-${count.index + 1}"

  system_disk_category = "cloud_essd"
  system_disk_size     = 40

  dynamic "data_disks" {
    for_each = var.data_disk_size > 0 ? [var.data_disk_size] : []
    content {
      size     = data_disks.value
      category = "cloud_essd"
    }
  }

  vswitch_id      = var.vswitch_id
  security_groups = [alicloud_security_group.main.id]

  internet_max_bandwidth_out = 10

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

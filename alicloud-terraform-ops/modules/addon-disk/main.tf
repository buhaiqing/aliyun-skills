resource "alicloud_disk" "main" {
  disk_name = "${var.environment}-data-disk"
  zone_id   = var.zone_id
  size      = var.size
  category  = "cloud_essd"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

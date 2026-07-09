output "polardb_cluster_id" {
  value = alicloud_polardb_cluster.main.id
}

output "polardb_cluster_name" {
  value = alicloud_polardb_cluster.main.cluster_name
}

output "polardb_connection_string" {
  value = alicloud_polardb_cluster.main.connection_string
}
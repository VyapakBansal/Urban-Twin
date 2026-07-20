output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "location" {
  value = azurerm_resource_group.main.location
}

output "enable_demo_vm" {
  value = var.enable_demo_vm
}

output "monthly_budget_amount" {
  value = var.monthly_budget_amount
}

output "demo_vm_public_ip" {
  description = "Public IP of the demo VM (null when enable_demo_vm = false)."
  value       = try(azurerm_public_ip.demo[0].ip_address, null)
}

output "demo_http_url" {
  description = "Map URL (nginx on :80)."
  value       = try("http://${azurerm_public_ip.demo[0].ip_address}/", null)
}

output "demo_api_health_url" {
  description = "Proxied API health check."
  value       = try("http://${azurerm_public_ip.demo[0].ip_address}/api/health", null)
}

output "ssh_command" {
  description = "SSH into the demo VM."
  value = try(
    "ssh ${var.admin_username}@${azurerm_public_ip.demo[0].ip_address}",
    null,
  )
}

output "bootstrap_log_hint" {
  value = try(
    "ssh … then: sudo tail -f /var/log/urban-twin-bootstrap.log",
    null,
  )
}

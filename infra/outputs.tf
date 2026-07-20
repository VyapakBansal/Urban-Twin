output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "location" {
  value = azurerm_resource_group.main.location
}

output "demo_vm_public_ip" {
  description = "Public IP of the demo VM (null when enable_demo_vm = false)."
  value       = try(azurerm_public_ip.demo[0].ip_address, null)
}

output "enable_demo_vm" {
  value = var.enable_demo_vm
}

output "monthly_budget_amount" {
  value = var.monthly_budget_amount
}

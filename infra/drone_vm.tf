# Optional, disposable PX4/Gazebo simulation VM. OFF by default.
# The lightweight MAVSDK bridge stays on the demo host; only MAVLink UDP
# crosses the private VNet (or a single explicitly allowed public /32).

resource "azurerm_network_security_rule" "drone_from_local" {
  count = (
    var.enable_demo_vm &&
    var.enable_drone_bridge &&
    trimspace(var.drone_mavlink_source_cidr) != ""
  ) ? 1 : 0

  name                        = "MAVLinkFromLocalSimulator"
  priority                    = 1003
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Udp"
  source_port_range           = "*"
  destination_port_range      = "14540"
  source_address_prefix       = var.drone_mavlink_source_cidr
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.demo[0].name
}

resource "azurerm_network_security_group" "drone" {
  count               = var.enable_drone_vm ? 1 : 0
  name                = "nsg-${local.name_prefix}-drone"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = merge(local.tags, { purpose = "short-lived-px4-simulation" })

  security_rule {
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = var.allowed_ssh_cidr
    destination_address_prefix = "*"
  }
}

resource "azurerm_public_ip" "drone" {
  count               = var.enable_drone_vm ? 1 : 0
  name                = "pip-${local.name_prefix}-drone"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = merge(local.tags, { purpose = "short-lived-px4-simulation" })
}

resource "azurerm_network_interface" "drone" {
  count               = var.enable_drone_vm ? 1 : 0
  name                = "nic-${local.name_prefix}-drone"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = merge(local.tags, { purpose = "short-lived-px4-simulation" })

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.demo[0].id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.drone[0].id
  }
}

resource "azurerm_network_interface_security_group_association" "drone" {
  count                     = var.enable_drone_vm ? 1 : 0
  network_interface_id      = azurerm_network_interface.drone[0].id
  network_security_group_id = azurerm_network_security_group.drone[0].id
}

resource "azurerm_network_security_rule" "drone_to_demo" {
  count = var.enable_drone_vm && var.enable_drone_bridge ? 1 : 0

  name                        = "MAVLinkFromDroneVM"
  priority                    = 1004
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Udp"
  source_port_range           = "*"
  destination_port_range      = "14540"
  source_address_prefix       = azurerm_network_interface.drone[0].private_ip_address
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.demo[0].name
}

resource "azurerm_linux_virtual_machine" "drone" {
  count               = var.enable_drone_vm ? 1 : 0
  name                = "vm-${local.name_prefix}-drone"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  size                = var.drone_vm_size
  admin_username      = var.admin_username
  priority            = var.drone_vm_spot ? "Spot" : "Regular"
  eviction_policy     = var.drone_vm_spot ? "Deallocate" : null
  max_bid_price       = var.drone_vm_spot ? -1 : null
  tags                = merge(local.tags, { purpose = "short-lived-px4-simulation" })

  network_interface_ids = [
    azurerm_network_interface.drone[0].id,
  ]

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 64
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(templatefile(
    "${path.module}/../deploy/drone-cloud-init.yaml.tftpl",
    {
      admin_username      = var.admin_username
      demo_private_ip     = azurerm_network_interface.demo[0].private_ip_address
      drone_home_lat      = 51.053
      drone_home_lon      = -114.081
      drone_home_alt_m    = 1045.0
      drone_sim_autostart = var.drone_sim_autostart
      px4_git_ref         = var.px4_git_ref
    }
  ))

  lifecycle {
    precondition {
      condition     = var.ssh_public_key != ""
      error_message = "ssh_public_key must be set when enable_drone_vm = true."
    }
    precondition {
      condition     = var.enable_drone_bridge
      error_message = "enable_drone_bridge must be true when enable_drone_vm is enabled."
    }
    precondition {
      condition     = can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/32$", var.allowed_ssh_cidr)) && var.allowed_ssh_cidr != "0.0.0.0/32"
      error_message = "allowed_ssh_cidr must be your public IP /32 (not 0.0.0.0/0) when enable_drone_vm = true."
    }
  }
}

resource "azurerm_dev_test_global_vm_shutdown_schedule" "drone" {
  count              = var.enable_drone_vm ? 1 : 0
  virtual_machine_id = azurerm_linux_virtual_machine.drone[0].id
  location           = azurerm_resource_group.main.location
  enabled            = true

  daily_recurrence_time = var.drone_vm_auto_shutdown_time
  timezone              = "Mountain Standard Time"

  notification_settings {
    enabled = false
  }

  tags = merge(local.tags, { purpose = "drone-cost-guard" })
}


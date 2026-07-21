# Optional demo VM — OFF by default (enable_demo_vm = false).
# When enabled: one B-series VM runs Docker Compose + Python services + nginx.

resource "azurerm_virtual_network" "demo" {
  count               = var.enable_demo_vm ? 1 : 0
  name                = "vnet-${local.name_prefix}"
  address_space       = ["10.40.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_subnet" "demo" {
  count                = var.enable_demo_vm ? 1 : 0
  name                 = "snet-demo"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.demo[0].name
  address_prefixes     = ["10.40.1.0/24"]
}

resource "azurerm_network_security_group" "demo" {
  count               = var.enable_demo_vm ? 1 : 0
  name                = "nsg-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

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

  # Public map + reverse-proxied API/WS (API and WS stay on localhost only)
  security_rule {
    name                       = "HTTP"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_public_ip" "demo" {
  count               = var.enable_demo_vm ? 1 : 0
  name                = "pip-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_network_interface" "demo" {
  count               = var.enable_demo_vm ? 1 : 0
  name                = "nic-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.demo[0].id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.demo[0].id
  }
}

resource "azurerm_network_interface_security_group_association" "demo" {
  count                     = var.enable_demo_vm ? 1 : 0
  network_interface_id      = azurerm_network_interface.demo[0].id
  network_security_group_id = azurerm_network_security_group.demo[0].id
}

resource "azurerm_linux_virtual_machine" "demo" {
  count               = var.enable_demo_vm ? 1 : 0
  name                = "vm-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  size                = var.vm_size
  admin_username      = var.admin_username
  tags                = local.tags

  network_interface_ids = [
    azurerm_network_interface.demo[0].id,
  ]

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("${path.module}/../deploy/cloud-init.yaml.tftpl", {
    openweather_api_key = var.openweather_api_key
    openaq_api_key      = var.openaq_api_key
    git_repo_url        = var.git_repo_url
    git_branch          = var.git_branch
    enable_drone_bridge = var.enable_drone_bridge
  }))

  lifecycle {
    precondition {
      condition     = var.ssh_public_key != ""
      error_message = "ssh_public_key must be set when enable_demo_vm = true."
    }
    precondition {
      condition     = var.openweather_api_key != ""
      error_message = "openweather_api_key must be set when enable_demo_vm = true."
    }
    precondition {
      condition     = can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/32$", var.allowed_ssh_cidr)) && var.allowed_ssh_cidr != "0.0.0.0/32"
      error_message = "allowed_ssh_cidr must be your public IP /32 (not 0.0.0.0/0) when enable_demo_vm = true."
    }
  }
}

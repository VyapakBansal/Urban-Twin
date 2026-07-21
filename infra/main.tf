locals {
  name_prefix = "${var.project_name}-${var.environment}"
  tags = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "portfolio-demo"
  }
}

check "drone_vm_requires_demo_host" {
  assert {
    condition     = !var.enable_drone_vm || var.enable_demo_vm
    error_message = "enable_drone_vm requires enable_demo_vm so the simulator has a private bridge target."
  }
}

check "drone_vm_requires_tested_px4_ref" {
  assert {
    condition     = !var.enable_drone_vm || trimspace(var.px4_git_ref) != ""
    error_message = "Set px4_git_ref to the exact locally tested PX4 tag/commit before enabling the drone VM."
  }
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_consumption_budget_subscription" "monthly" {
  count = length(var.budget_contact_emails) > 0 ? 1 : 0

  name            = "budget-${local.name_prefix}"
  subscription_id = "/subscriptions/${var.subscription_id}"

  amount     = var.monthly_budget_amount
  time_grain = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    enabled        = true
    threshold      = 50.0
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = var.budget_contact_emails
  }

  notification {
    enabled        = true
    threshold      = 90.0
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = var.budget_contact_emails
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

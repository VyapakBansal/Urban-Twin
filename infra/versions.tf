terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Local state by default (fine for learning).
  # Before any shared/cloud apply, move state to Azure Storage + lock —
  # never commit *.tfstate.
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

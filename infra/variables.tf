variable "subscription_id" {
  type        = string
  description = "Azure subscription ID (from `az account show`)."
}

variable "location" {
  type        = string
  description = "Azure region."
  default     = "canadacentral"
}

variable "project_name" {
  type        = string
  description = "Short name used in resource names."
  default     = "urbantwin"
}

variable "environment" {
  type        = string
  description = "Environment label (single env for learning)."
  default     = "demo"
}

variable "monthly_budget_amount" {
  type        = number
  description = "Soft monthly budget in USD for alerts (preserve ~$100 credits)."
  default     = 40
}

variable "budget_contact_emails" {
  type        = list(string)
  description = "Emails for budget alerts."
  default     = []
}

variable "enable_demo_vm" {
  type        = bool
  description = "If true, create a small Ubuntu VM (COSTS MONEY). Keep false until demo day."
  default     = false
}

variable "admin_username" {
  type        = string
  description = "VM admin username (only used when enable_demo_vm = true)."
  default     = "urbanadmin"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key for the demo VM. Required when enable_demo_vm = true."
  default     = ""
  sensitive   = true
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR allowed to SSH (your public IP /32). Never 0.0.0.0/0 for long-lived demos."
  default     = "0.0.0.0/0" # override in tfvars before apply
}

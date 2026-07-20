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
  description = "CIDR allowed to SSH (your public IP /32). Never leave 0.0.0.0/0 for long."
  default     = "0.0.0.0/0"
}

variable "git_repo_url" {
  type        = string
  description = "Public git clone URL for bootstrap."
  default     = "https://github.com/VyapakBansal/Urban-Twin.git"
}

variable "git_branch" {
  type        = string
  description = "Branch to clone on the VM."
  default     = "main"
}

variable "openweather_api_key" {
  type        = string
  description = "OpenWeather API key written to the VM .env via cloud-init."
  default     = ""
  sensitive   = true
}

variable "openaq_api_key" {
  type        = string
  description = "Optional OpenAQ API key."
  default     = ""
  sensitive   = true
}

variable "vm_size" {
  type        = string
  description = "Azure VM size for the demo host."
  default     = "Standard_B2s"
}

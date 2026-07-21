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

variable "enable_drone_bridge" {
  type        = bool
  description = "Start the lightweight MAVSDK bridge on the demo VM. No extra Azure resource."
  default     = false
}

variable "drone_mavlink_source_cidr" {
  type        = string
  description = "Optional public CIDR allowed to send MAVLink UDP 14540 to the demo VM (normally your Linux laptop IP /32)."
  default     = ""
}

variable "enable_drone_vm" {
  type        = bool
  description = "Create a separate PX4/Gazebo simulation VM (COSTS MONEY). Requires enable_demo_vm."
  default     = false
}

variable "drone_vm_size" {
  type        = string
  description = "Simulation VM size; 4 vCPU / 16 GiB is the practical minimum for headless Gazebo."
  default     = "Standard_D4as_v5"
}

variable "drone_vm_spot" {
  type        = bool
  description = "Use lower-cost interruptible Spot capacity for the disposable simulator."
  default     = true
}

variable "drone_vm_auto_shutdown_time" {
  type        = string
  description = "Daily auto-shutdown time in HHmm (Mountain Standard Time)."
  default     = "0200"

  validation {
    condition     = can(regex("^([01][0-9]|2[0-3])[0-5][0-9]$", var.drone_vm_auto_shutdown_time))
    error_message = "drone_vm_auto_shutdown_time must be a valid 24-hour HHmm value."
  }
}

variable "px4_git_ref" {
  type        = string
  description = "Exact locally tested PX4 tag/commit to install on the optional simulation VM."
  default     = ""
}

variable "drone_sim_autostart" {
  type        = bool
  description = "Build and start headless Gazebo during cloud-init. Keep false until a short demo window."
  default     = false
}
